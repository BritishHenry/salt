"""Embedding vectors."""

from __future__ import annotations

from services.grok.constants import DEFAULT_EMBEDDING_MODEL
from services.grok.errors import GrokUsageError
from services.grok.resources.base import Resource
from services.grok.safety import (
    merge_additional_fields,
    optional_identifier,
    optional_int,
    require_model_name,
    require_text,
    without_none,
)


class EmbeddingsResource(Resource):
    def create_embedding_vectors(
        self,
        texts,
        *,
        model=DEFAULT_EMBEDDING_MODEL,
        dimensions=None,
        encoding_format=None,
        user=None,
        additional_fields=None,
        timeout_seconds=None,
    ):
        """POST /v1/embeddings.

        texts may be one string or a list of strings. Vectors come back in data,
        each with an index matching the input order.
        """
        model_input = _embedding_input(texts)
        if encoding_format is not None and encoding_format not in {"float", "base64"}:
            raise GrokUsageError("encoding_format must be 'float' or 'base64'.")
        body = without_none(
            {
                "model": require_model_name(model),
                "input": model_input,
                "dimensions": optional_int(dimensions, "dimensions", minimum=1, maximum=8192),
                "encoding_format": encoding_format,
                "user": optional_identifier(user, "user"),
            }
        )
        body = merge_additional_fields(body, additional_fields)
        return self._json("POST", "/v1/embeddings", body=body, timeout_seconds=timeout_seconds)


def _embedding_input(texts):
    if isinstance(texts, str):
        return require_text(texts, "texts", max_length=200_000)
    if not isinstance(texts, list) or not texts:
        raise GrokUsageError("texts must be a string or a non-empty list of strings.")
    if len(texts) > 2048:
        raise GrokUsageError("texts accepts at most 2048 strings per request.")
    return [require_text(item, "texts", max_length=200_000) for item in texts]
