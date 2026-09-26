"""Errors raised by the Grok client.

Messages never include the API key. Request bodies are not attached.
"""


class GrokError(Exception):
    """Base error for every failure in this client."""


class GrokConfigurationError(GrokError):
    """The client is missing a key, host, or other startup setting."""


class GrokUsageError(GrokError):
    """The caller passed arguments this client will not send."""


class GrokSafetyError(GrokError):
    """A request was refused because it could leak the key or leave the API."""


class GrokTransportError(GrokError):
    """The API host could not be reached."""


class GrokTimeoutError(GrokError):
    """A request or a polled operation exceeded its time limit."""


class GrokResponseTooLargeError(GrokSafetyError):
    """The response exceeded the configured byte cap."""


class GrokApiError(GrokError):
    """The API returned an error status."""

    def __init__(self, message, *, status_code=None, error_code=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class GrokAuthenticationError(GrokApiError):
    """The API key was missing, rejected, or not allowed to call that route."""


class GrokNotFoundError(GrokApiError):
    """The requested record does not exist."""


class GrokRateLimitError(GrokApiError):
    """The API asked the client to slow down."""
