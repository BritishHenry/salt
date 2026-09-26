"""Identity of the current API key. This does not create or rotate keys."""

from __future__ import annotations

from services.grok.resources.base import Resource


class AccountResource(Resource):
    def get_api_key_information(self, *, timeout_seconds=None):
        """GET /v1/api-key. Returns the redacted key, name, status, and permissions."""
        return self._json("GET", "/v1/api-key", timeout_seconds=timeout_seconds)

    def get_authenticated_caller(self, *, timeout_seconds=None):
        """GET /v1/me. Works with an API key or an OAuth token."""
        return self._json("GET", "/v1/me", timeout_seconds=timeout_seconds)
