"""HTTP transport for the Browser Use API v4."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from services.browser_use.errors import BrowserUseAPIError, BrowserUseError, QueueFull, SessionBusy

DEFAULT_BASE_URL = "https://api.browser-use.com/api/v4"
_MAX_BACKOFF_SECONDS = 30


def detail_text(body):
    if body is None:
        return ""
    if isinstance(body, str):
        return body
    if not isinstance(body, dict):
        return str(body)
    detail = body.get("detail", body)
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str):
            return message
        return json.dumps(detail)
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict) and "msg" in item:
                parts.append(str(item["msg"]))
            else:
                parts.append(str(item))
        return "; ".join(parts)
    return str(detail)


def retry_delay(headers, body):
    """Seconds to wait after a throttle, when the response says how long."""
    if isinstance(body, dict):
        sources = [body]
        detail = body.get("detail")
        if isinstance(detail, dict):
            sources.append(detail)
        for source in sources:
            if "retry_after_seconds" in source:
                return float(source["retry_after_seconds"])
    if headers is None:
        return None
    header = headers.get("Retry-After")
    if header is None:
        return None
    try:
        return float(header)
    except (TypeError, ValueError):
        return None


def _parse_body(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"detail": raw.decode("utf-8", errors="replace")}


def _error_for(status, body, path):
    detail = detail_text(body) or "request failed"
    if status == 409 and path.rstrip("/") == "/runs":
        return SessionBusy(status, detail, body=body)
    if status == 429 and "/queue" in path and retry_delay(None, body) is None:
        return QueueFull(status, detail or "The session message queue is full.", body=body)
    return BrowserUseAPIError(status, detail, body=body)


class UrllibTransport:
    """Calls api.browser-use.com with the X-Browser-Use-API-Key header.

    A 429 that includes Retry-After or retry_after_seconds is retried.
    A full session queue is also a 429 and is returned immediately.
    """

    def __init__(
        self,
        api_key,
        *,
        base_url=DEFAULT_BASE_URL,
        timeout=30,
        sleep=time.sleep,
        max_retries=4,
        opener=None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._sleep = sleep
        self._max_retries = max_retries
        self._opener = opener or urlopen

    def put_bytes(self, url, data, content_type):
        """PUT file bytes to a presigned URL. The API key is not sent."""
        if not isinstance(url, str) or not url.startswith("https://"):
            raise BrowserUseError("Upload URL must use https.")
        if not isinstance(data, (bytes, bytearray)) or len(data) < 1:
            raise ValueError("file data must be non-empty bytes")
        headers = {
            "Content-Type": content_type or "application/octet-stream",
            "Content-Length": str(len(data)),
        }
        request = Request(url, data=bytes(data), headers=headers, method="PUT")
        try:
            with self._opener(request, timeout=self._timeout) as response:
                response.read()
        except HTTPError as exc:
            body = _parse_body(exc.read())
            raise BrowserUseAPIError(
                exc.code, detail_text(body) or "upload failed", body=body
            ) from exc
        except URLError as exc:
            raise BrowserUseError(f"Browser Use upload failed: {exc.reason}") from exc

    def request(self, method, path, *, json_body=None, query=None):
        url = self._base_url + path
        if query:
            pairs = []
            for key, value in query.items():
                if value is None:
                    continue
                if isinstance(value, (list, tuple)):
                    for item in value:
                        pairs.append((key, item))
                else:
                    pairs.append((key, value))
            if pairs:
                url = f"{url}?{urlencode(pairs)}"
        data = None if json_body is None else json.dumps(json_body).encode()
        headers = {
            "X-Browser-Use-API-Key": self._api_key,
            "Accept": "application/json",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"

        attempt = 0
        while True:
            request = Request(url, data=data, headers=headers, method=method)
            try:
                with self._opener(request, timeout=self._timeout) as response:
                    return _parse_body(response.read())
            except HTTPError as exc:
                body = _parse_body(exc.read())
                delay = retry_delay(exc.headers, body)
                queue_full = exc.code == 429 and "/queue" in path and delay is None
                if exc.code == 429 and delay is not None and attempt < self._max_retries and not queue_full:
                    self._sleep(min(_MAX_BACKOFF_SECONDS, max(0, delay)))
                    attempt += 1
                    continue
                raise _error_for(exc.code, body, path) from exc
            except URLError as exc:
                raise BrowserUseError(f"Browser Use request failed: {exc.reason}") from exc
