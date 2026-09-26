"""HTTPS transport for the Grok API.

The API key is sent only as an Authorization header to an allowed origin.
Redirects are refused so the key cannot follow a Location header elsewhere.
Unsafe methods are not retried after a connection drop or a 5xx response.
"""

from __future__ import annotations

import json
import random
import socket
import time
import urllib.error
import urllib.request
import uuid
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode, urlparse

from services.grok.constants import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_MAX_RETRIES,
    MAX_HTTP_TIMEOUT_SECONDS,
    MAX_JSON_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    USER_AGENT,
)
from services.grok.errors import (
    GrokApiError,
    GrokAuthenticationError,
    GrokNotFoundError,
    GrokRateLimitError,
    GrokResponseTooLargeError,
    GrokSafetyError,
    GrokTimeoutError,
    GrokTransportError,
    GrokUsageError,
)
from services.grok.safety import (
    redact_object,
    redact_text,
    require_api_key,
    require_api_path,
    validate_base_url,
)

_IDEMPOTENT_METHODS = frozenset({"GET", "DELETE", "PUT", "HEAD"})
_IDEMPOTENT_RETRY_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_UNSAFE_RETRY_STATUSES = frozenset({429})


class _RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise GrokSafetyError(
            f"Refusing to follow an HTTP {code} redirect from the Grok API."
        )


class WebsocketConnection:
    """URL and headers for a Grok websocket. The API key is not in the URL."""

    def __init__(self, url, authorization_header):
        self.url = url
        self._authorization_header = authorization_header

    @property
    def headers(self):
        return _RedactedHeaders({"Authorization": self._authorization_header})

    def __repr__(self):
        return (
            f"WebsocketConnection(url={self.url!r}, "
            "headers={'Authorization': 'Bearer ***'})"
        )


class _RedactedHeaders(dict):
    def __repr__(self):
        return "{'Authorization': 'Bearer ***'}"


class ApiResult:
    """A completed HTTP response whose body has already been read."""

    def __init__(self, *, status_code, headers, body, json_body, content_type):
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.json_body = json_body
        self.content_type = content_type


class ServerSentEventStream:
    """A text/event-stream body. Use it as a context manager or iterate it."""

    def __init__(self, response, *, max_bytes, secrets):
        self._response = response
        self._max_bytes = max_bytes
        self._secrets = secrets
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def __iter__(self):
        try:
            yield from self._events()
        finally:
            self.close()

    def close(self):
        if not self._closed:
            self._closed = True
            self._response.close()

    def _events(self):
        total = 0
        while True:
            line = self._response.readline()
            if not line:
                break
            total += len(line)
            if total > self._max_bytes:
                raise GrokResponseTooLargeError("The streamed response exceeded its byte cap.")
            if len(line) > 2_000_000:
                raise GrokResponseTooLargeError("A streamed event line was too large.")
            if not line.startswith(b"data:"):
                continue
            event = _decode_event_payload(line[5:].strip(), self._secrets)
            if event is _DONE:
                break
            if event is not None:
                yield event


class _DoneSentinel:
    pass


_DONE = _DoneSentinel()


class HttpTransport:
    def __init__(
        self,
        api_key,
        *,
        base_url,
        allowed_hosts,
        timeout_seconds=DEFAULT_HTTP_TIMEOUT_SECONDS,
        max_retries=DEFAULT_MAX_RETRIES,
        max_response_bytes=MAX_RESPONSE_BYTES,
        allow_non_default_host=False,
        urlopen=None,
        sleep=None,
        random_unit_interval=None,
    ):
        self._api_key = require_api_key(api_key, "api_key")
        self.base_url = validate_base_url(
            base_url,
            allowed_hosts=allowed_hosts,
            allow_non_default_host=allow_non_default_host,
            name="base_url",
        )
        self._timeout_seconds = _require_timeout(timeout_seconds)
        self._max_retries = optional_retry_count(max_retries)
        self._max_response_bytes = max_response_bytes
        self._urlopen = urlopen or urllib.request.build_opener(_RejectRedirect).open
        self._sleep = sleep or time.sleep
        self._random = random_unit_interval or random.random

    def __repr__(self):
        return f"HttpTransport(base_url={self.base_url!r}, api_key='***')"

    def websocket_connection(self, path, query=None):
        """Build a websocket URL on this transport's host. The key stays in the header."""
        path = require_api_path(path)
        parsed = urlparse(self.base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        query_string = urlencode(_query_pairs(query or {}), doseq=True)
        url = f"{scheme}://{parsed.netloc}{path}"
        if query_string:
            url = url + "?" + query_string
        if self._api_key in url:
            raise GrokSafetyError("Refusing to put the API key in a websocket URL.")
        return WebsocketConnection(url, f"Bearer {self._api_key}")

    def send(
        self,
        method,
        path,
        *,
        query=None,
        json_body=None,
        raw_body=None,
        content_type=None,
        accepted_statuses=(200,),
        timeout_seconds=None,
        parse_json=True,
        stream=False,
        max_request_bytes=None,
        max_response_bytes=None,
    ):
        method = method.upper()
        path = require_api_path(path)
        if json_body is not None and raw_body is not None:
            raise GrokUsageError("Pass JSON or raw bytes, not both.")
        body = _encode_json(json_body) if json_body is not None else raw_body
        request_limit = max_request_bytes or MAX_JSON_REQUEST_BYTES
        if body is not None and len(body) > request_limit:
            raise GrokUsageError(
                f"The request body is {len(body)} bytes, above the {request_limit} byte cap."
            )
        url = self.base_url + path
        if query:
            encoded = urlencode(_query_pairs(query), doseq=True)
            if encoded:
                url = url + "?" + encoded
        if self._api_key in url:
            raise GrokSafetyError("Refusing to put the API key in the request URL.")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json, text/event-stream, */*;q=0.8",
            "User-Agent": USER_AGENT,
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        elif content_type is not None:
            headers["Content-Type"] = content_type
        timeout = _require_timeout(timeout_seconds or self._timeout_seconds)
        response_limit = max_response_bytes or self._max_response_bytes
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                request = urllib.request.Request(url, data=body, headers=headers, method=method)
                response = self._open(request, timeout)
            except GrokTimeoutError as exc:
                last_error = exc
                if self._can_retry_transport(method) and attempt < self._max_retries:
                    self._sleep(self._delay(attempt, None))
                    continue
                raise
            except GrokTransportError as exc:
                last_error = exc
                if self._can_retry_transport(method) and attempt < self._max_retries:
                    self._sleep(self._delay(attempt, None))
                    continue
                raise
            status = _status(response)
            if status in accepted_statuses:
                if stream:
                    return self._stream_result(response, response_limit)
                try:
                    raw = _read_limited(response, response_limit)
                finally:
                    response.close()
                return self._completed_result(status, response, raw, parse_json)
            retry_after = _retry_after_seconds(response)
            try:
                raw = _read_limited(response, min(response_limit, 64_000))
            finally:
                response.close()
            error = self._error_for_status(status, raw)
            last_error = error
            if self._can_retry_status(method, status) and attempt < self._max_retries:
                self._sleep(self._delay(attempt, retry_after))
                continue
            raise error
        raise last_error or GrokTransportError("The Grok API request failed.")

    def _open(self, request, timeout):
        try:
            return self._urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            return exc
        except (TimeoutError, socket.timeout) as exc:
            raise GrokTimeoutError("The Grok API request timed out.") from exc
        except GrokSafetyError:
            raise
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                raise GrokTimeoutError("The Grok API request timed out.") from exc
            raise GrokTransportError("Could not reach the Grok API.") from exc

    def _completed_result(self, status, response, raw, parse_json):
        content_type = _header(response, "Content-Type") or ""
        json_body = None
        if parse_json and raw:
            try:
                json_body = json.loads(raw.decode("utf-8-sig"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise GrokApiError(
                    "The Grok API returned a success status with a body that is not JSON.",
                    status_code=status,
                ) from exc
            if any(secret.encode("utf-8") in raw for secret in (self._api_key,)):
                json_body = redact_object(json_body, [self._api_key])
        return ApiResult(
            status_code=status,
            headers={"content-type": content_type},
            body=raw,
            json_body=json_body,
            content_type=content_type.split(";")[0].strip().lower(),
        )

    def _stream_result(self, response, response_limit):
        content_type = (_header(response, "Content-Type") or "").lower()
        if "text/event-stream" not in content_type:
            try:
                raw = _read_limited(response, min(response_limit, 64_000))
            finally:
                response.close()
            message = _error_message(raw, [self._api_key])
            raise GrokApiError(
                "The API returned JSON instead of a server-sent event stream. "
                + message,
                status_code=_status(response),
            )
        return ServerSentEventStream(
            response,
            max_bytes=response_limit,
            secrets=[self._api_key],
        )

    def _error_for_status(self, status, raw):
        message = _error_message(raw, [self._api_key])
        error_code = _error_code(raw)
        if status in {401, 403}:
            return GrokAuthenticationError(message, status_code=status, error_code=error_code)
        if status == 404:
            return GrokNotFoundError(message, status_code=status, error_code=error_code)
        if status == 429:
            return GrokRateLimitError(message, status_code=status, error_code=error_code)
        return GrokApiError(message, status_code=status, error_code=error_code)

    def _can_retry_transport(self, method):
        return method in _IDEMPOTENT_METHODS

    def _can_retry_status(self, method, status):
        if status in _UNSAFE_RETRY_STATUSES:
            return True
        return method in _IDEMPOTENT_METHODS and status in _IDEMPOTENT_RETRY_STATUSES

    def _delay(self, attempt, retry_after):
        if retry_after is not None:
            return min(60.0, max(0.0, retry_after))
        base = min(30.0, 0.5 * (2**attempt))
        return base + (self._random() * 0.25 * base)


def encode_multipart_form(fields, files):
    """Encode multipart form data. File parts are written after text fields."""
    boundary = _multipart_boundary(fields, files)
    chunks = []
    for name, value in fields:
        _require_form_token(name, "field name")
        text = str(value)
        if any(character in text for character in "\r\n\x00"):
            raise GrokSafetyError(f"Multipart field {name} contains a control character.")
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{text}\r\n"
            ).encode("utf-8")
        )
    for name, filename, content_type, data in files:
        _require_form_token(name, "file field name")
        if any(character in filename for character in '"\r\n'):
            raise GrokSafetyError("Upload filenames cannot change multipart headers.")
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
            + data
            + b"\r\n"
        )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)
    return body, f"multipart/form-data; boundary={boundary}"


def _multipart_boundary(fields, files):
    payloads = [item[3] for item in files]
    payloads.extend(str(value).encode("utf-8") for _, value in fields)
    for _ in range(5):
        boundary = "----saltgrok" + uuid.uuid4().hex
        token = boundary.encode("utf-8")
        if all(token not in payload for payload in payloads):
            return boundary
    raise GrokSafetyError("Could not encode the upload without colliding with the file bytes.")


def _require_form_token(value, name):
    if not isinstance(value, str) or not value or any(character in value for character in '"\r\n ;'):
        raise GrokSafetyError(f"Unsafe multipart {name}.")


def _encode_json(body):
    try:
        return json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GrokUsageError("The request body is not JSON serializable.") from exc


def _query_pairs(query):
    pairs = []
    for key, value in query.items():
        if value is None:
            continue
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            if isinstance(item, bool):
                item = "true" if item else "false"
            pairs.append((key, item))
    return pairs


def _read_limited(response, max_bytes):
    chunks = []
    remaining = max_bytes + 1
    while remaining > 0:
        chunk = response.read(min(65_536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    data = b"".join(chunks)
    if len(data) > max_bytes:
        raise GrokResponseTooLargeError(
            f"The response is larger than {max_bytes} bytes and was discarded."
        )
    return data


def _status(response):
    status = getattr(response, "status", None)
    if status is None:
        status = response.getcode()
    return int(status)


def _header(response, name):
    headers = getattr(response, "headers", None)
    if headers is not None and hasattr(headers, "get"):
        for candidate in (name, name.lower(), name.title()):
            try:
                value = headers.get(candidate)
            except Exception:
                value = None
            if value:
                return value
    getter = getattr(response, "getheader", None)
    if getter is not None:
        return getter(name)
    return None


def _retry_after_seconds(response):
    value = _header(response, "Retry-After")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if moment is None:
        return None
    return max(0.0, moment.timestamp() - time.time())


def _error_message(raw, secrets):
    text = raw.decode("utf-8", errors="replace") if raw else "The Grok API request failed."
    message = text
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        error = parsed.get("error", parsed.get("message"))
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("code") or error)
        elif error is not None:
            message = str(error)
    message = redact_text(message, secrets).strip()
    if len(message) > 2000:
        message = message[:2000] + "…"
    return message or "The Grok API request failed."


def _error_code(raw):
    try:
        parsed = json.loads(raw.decode("utf-8", errors="replace")) if raw else None
    except (UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    error = parsed.get("error")
    if isinstance(error, dict) and error.get("code"):
        return str(error["code"])
    code = parsed.get("code")
    return str(code) if code else None


def _decode_event_payload(payload, secrets):
    if not payload or payload == b"[DONE]":
        return _DONE if payload == b"[DONE]" else None
    try:
        event = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise GrokApiError("The Grok API sent a stream event that is not JSON.") from exc
    if isinstance(event, (dict, list)) and any(secret.encode("utf-8") in payload for secret in secrets):
        return redact_object(event, secrets)
    return event


def _require_timeout(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GrokUsageError("timeout_seconds must be a number of seconds.")
    if value <= 0 or value > MAX_HTTP_TIMEOUT_SECONDS:
        raise GrokUsageError(
            f"timeout_seconds must be greater than 0 and at most {MAX_HTTP_TIMEOUT_SECONDS:g}."
        )
    return float(value)


def optional_retry_count(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise GrokUsageError("max_retries must be an integer.")
    if value < 0 or value > 5:
        raise GrokUsageError("max_retries must be between 0 and 5.")
    return value
