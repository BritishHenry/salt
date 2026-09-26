"""Count tokens before sending a paid generation request."""

from __future__ import annotations

from services.grok.resources.base import Resource
from services.grok.safety import optional_identifier, require_model_name, require_text, without_none


class TokenizeResource(Resource):
    def tokenize_text(self, text, *, model, user=None, timeout_seconds=None):
        """POST /v1/tokenize-text. Returns token ids for the given model."""
        body = without_none(
            {
                "model": require_model_name(model),
                "text": require_text(text, "text", max_length=2_000_000),
                "user": optional_identifier(user, "user"),
            }
        )
        return self._json("POST", "/v1/tokenize-text", body=body, timeout_seconds=timeout_seconds)

    def count_tokens_in_text(self, text, *, model, timeout_seconds=None):
        """Return how many tokens tokenize_text produced."""
        body = self.tokenize_text(text, model=model, timeout_seconds=timeout_seconds)
        token_ids = body.get("token_ids") or []
        if not isinstance(token_ids, list):
            from services.grok.errors import GrokApiError

            raise GrokApiError("The tokenize response did not include token_ids.")
        return len(token_ids)
