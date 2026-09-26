"""Argument checks and redaction shared by every Grok resource."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

from services.grok.errors import GrokConfigurationError, GrokSafetyError, GrokUsageError

_RESOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,200}$")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,128}$")
_FUNCTION_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
_LANGUAGE = re.compile(r"^(auto|[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)$")
_SIMPLE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MEDIA_TYPE = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FORBIDDEN_ADDITIONAL_FIELDS = frozenset(
    {"authorization", "api_key", "api-key", "x-api-key", "bearer"}
)


class _UnsetType:
    def __repr__(self):
        return "UNSET"


UNSET = _UnsetType()


def require_api_key(value, name):
    if not isinstance(value, str):
        raise GrokConfigurationError(f"{name} must be a string.")
    key = value.strip()
    if len(key) < 8 or any(character.isspace() for character in key):
        raise GrokConfigurationError(f"{name} is missing or not a usable key.")
    return key


def validate_base_url(url, *, allowed_hosts, allow_non_default_host, name):
    """Return an origin that is allowed to receive this client's API key."""
    if not isinstance(url, str) or not url.strip():
        raise GrokConfigurationError(f"{name} is missing.")
    parsed = urlparse(url.strip())
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise GrokSafetyError(
            f"{name} must be an origin without credentials, a query, or a fragment."
        )
    if parsed.path not in ("", "/"):
        raise GrokConfigurationError(
            f"{name} must be the origin only. The client adds the /v1 path itself."
        )
    host = (parsed.hostname or "").rstrip(".").lower()
    if not host:
        raise GrokConfigurationError(f"{name} does not include a host.")
    official = host in allowed_hosts and parsed.scheme == "https"
    local_http = (
        allow_non_default_host
        and parsed.scheme == "http"
        and host in {"localhost", "127.0.0.1"}
    )
    custom_https = (
        allow_non_default_host
        and parsed.scheme == "https"
        and not _is_ip_address(host)
    )
    if not (official or local_http or custom_https):
        allowed = ", ".join(f"https://{item}" for item in sorted(allowed_hosts))
        raise GrokSafetyError(
            f"{name} must be one of {allowed}. "
            "The API key is not sent to other hosts unless allow_non_default_host is set, "
            "and even then IP addresses and plain HTTP (except localhost) are refused."
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def require_api_path(path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise GrokSafetyError("API paths must start with /.")
    if path.startswith("//") or "\\" in path or "?" in path or "#" in path or ".." in path:
        raise GrokSafetyError(f"Refusing API path {path!r}.")
    if not (path.startswith("/v1/") or path.startswith("/v2/")):
        raise GrokSafetyError("Only /v1 and /v2 Grok API paths can be called.")
    if any(ord(character) < 32 or character == " " for character in path):
        raise GrokSafetyError("API paths cannot contain spaces or control characters.")
    return path


def require_resource_id(value, name):
    if not isinstance(value, str) or not _RESOURCE_ID.fullmatch(value) or ".." in value:
        raise GrokUsageError(f"{name} must be a single API id, not a path or URL.")
    return value


def require_model_name(value):
    if not isinstance(value, str) or not _MODEL_ID.fullmatch(value):
        raise GrokUsageError("model must be a model id such as 'grok-4.6'.")
    return value


def require_text(value, name, *, max_length=None, allow_blank=False):
    if not isinstance(value, str):
        raise GrokUsageError(f"{name} must be a string.")
    if not allow_blank and not value.strip():
        raise GrokUsageError(f"{name} must not be empty.")
    if max_length is not None and len(value) > max_length:
        raise GrokUsageError(f"{name} must be at most {max_length} characters.")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
        raise GrokSafetyError(f"{name} contains control characters.")
    return value


def optional_text(value, name, *, max_length=None):
    if value is None:
        return None
    return require_text(value, name, max_length=max_length)


def optional_identifier(value, name, *, max_length=256):
    if value is None:
        return None
    text = require_text(value, name, max_length=max_length)
    if any(character.isspace() for character in text):
        raise GrokUsageError(f"{name} must be a single token without spaces.")
    return text


def optional_language(value, name="language"):
    if value is None:
        return None
    if not isinstance(value, str) or not _LANGUAGE.fullmatch(value):
        raise GrokUsageError(f"{name} must be 'auto' or a BCP-47 language tag such as 'en'.")
    return value


def require_language(value, name="language"):
    if value is None:
        raise GrokUsageError(f"{name} is required.")
    return optional_language(value, name)


def optional_choice(value, name, choices):
    if value is None:
        return None
    if value not in choices:
        allowed = ", ".join(sorted(str(item) for item in choices))
        raise GrokUsageError(f"{name} must be one of: {allowed}.")
    return value


def optional_token(value, name):
    if value is None:
        return None
    if not isinstance(value, str) or not _SIMPLE_TOKEN.fullmatch(value):
        raise GrokUsageError(f"{name} must be a short token.")
    return value


def optional_int(value, name, *, minimum, maximum):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise GrokUsageError(f"{name} must be an integer.")
    if value < minimum or value > maximum:
        raise GrokUsageError(f"{name} must be between {minimum} and {maximum}.")
    return value


def optional_number(value, name, *, minimum, maximum):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GrokUsageError(f"{name} must be a number.")
    if value < minimum or value > maximum:
        raise GrokUsageError(f"{name} must be between {minimum} and {maximum}.")
    return value


def optional_bool(value, name):
    if value is None:
        return None
    if not isinstance(value, bool):
        raise GrokUsageError(f"{name} must be a boolean.")
    return value


def optional_date(value, name):
    if value is None:
        return None
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise GrokUsageError(f"{name} must be an ISO date, YYYY-MM-DD.")
    return value


def require_dict(value, name):
    if not isinstance(value, dict):
        raise GrokUsageError(f"{name} must be an object.")
    return value


def optional_dict(value, name):
    if value is None:
        return None
    return require_dict(value, name)


def require_non_empty_list(value, name):
    if not isinstance(value, list) or not value:
        raise GrokUsageError(f"{name} must be a non-empty list.")
    return value


def optional_string_list(value, name, *, max_items, max_item_length):
    if value is None:
        return None
    if not isinstance(value, list):
        raise GrokUsageError(f"{name} must be a list of strings.")
    if len(value) > max_items:
        raise GrokUsageError(f"{name} accepts at most {max_items} items.")
    cleaned = []
    for item in value:
        cleaned.append(require_text(item, name, max_length=max_item_length))
    return cleaned


def require_https_or_data_url(url, *, allowed_data_prefix, name="url", max_length=30_000_000):
    if not isinstance(url, str) or not url:
        raise GrokUsageError(f"{name} must be a URL.")
    if any(character in url for character in "\r\n\x00"):
        raise GrokSafetyError(f"{name} contains a control character.")
    if len(url) > max_length:
        raise GrokUsageError(f"{name} is too long to send.")
    if url.startswith("data:"):
        if not url.startswith(allowed_data_prefix):
            raise GrokUsageError(f"{name} data URLs must start with {allowed_data_prefix}.")
        return url
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise GrokUsageError(f"{name} must be an https URL or a data URL.")
    if parsed.username or parsed.password:
        raise GrokSafetyError(f"{name} must not include credentials.")
    return url


def require_https_url(url, name="url"):
    if not isinstance(url, str) or not url.startswith("https://"):
        raise GrokUsageError(f"{name} must be an https URL.")
    return require_https_or_data_url(url, allowed_data_prefix="https://", name=name, max_length=4096)


def exclusive_reference(*, file_id, url, allowed_data_prefix, label):
    if (file_id is None) == (url is None):
        raise GrokUsageError(f"Provide exactly one of {label}_file_id or {label}_url.")
    if file_id is not None:
        return {"file_id": require_resource_id(file_id, f"{label}_file_id")}
    return {
        "url": require_https_or_data_url(
            url,
            allowed_data_prefix=allowed_data_prefix,
            name=f"{label}_url",
        )
    }


def without_none(fields):
    return {key: value for key, value in fields.items() if value is not None}


def merge_additional_fields(body, additional_fields):
    if additional_fields is None:
        return body
    if not isinstance(additional_fields, dict):
        raise GrokUsageError("additional_fields must be an object.")
    for key in additional_fields:
        if not isinstance(key, str) or key.strip().lower() in _FORBIDDEN_ADDITIONAL_FIELDS:
            raise GrokSafetyError(f"Refusing additional field {key!r}.")
    merged = dict(additional_fields)
    merged.update(body)
    return merged


def safe_filename(name):
    if not isinstance(name, str) or not name.strip():
        raise GrokUsageError("filename must be a non-empty string.")
    cleaned = Path(name).name.replace('"', "").replace("\r", "").replace("\n", "")
    if not cleaned or cleaned in {".", ".."}:
        raise GrokUsageError("filename must not be a path.")
    return cleaned[:200]


def safe_content_type(value):
    if value is None:
        return "application/octet-stream"
    if not isinstance(value, str) or not _MEDIA_TYPE.fullmatch(value):
        raise GrokUsageError("content_type must be a simple media type such as 'image/jpeg'.")
    return value


def read_file_with_limit(path, max_bytes, label):
    file_path = Path(path)
    if not file_path.is_file():
        raise GrokUsageError(f"{label} does not point at a file.")
    size = file_path.stat().st_size
    if size > max_bytes:
        raise GrokUsageError(
            f"{label} is {size} bytes. This endpoint accepts at most {max_bytes} bytes."
        )
    return file_path.read_bytes(), safe_filename(file_path.name)


def function_name(value):
    if not isinstance(value, str) or not _FUNCTION_NAME.fullmatch(value):
        raise GrokUsageError("function name must be letters, digits, underscores, or hyphens.")
    return value


def redact_text(text, secrets):
    redacted = text
    for secret in secrets:
        if isinstance(secret, str) and len(secret) >= 8:
            redacted = redacted.replace(secret, "***")
            redacted = redacted.replace(f"Bearer {secret}", "Bearer ***")
    return redacted


def redact_object(value, secrets):
    if isinstance(value, str):
        return redact_text(value, secrets)
    if isinstance(value, list):
        return [redact_object(item, secrets) for item in value]
    if isinstance(value, Mapping):
        return {key: redact_object(item, secrets) for key, item in value.items()}
    return value


def _is_ip_address(host):
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True
