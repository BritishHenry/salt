"""Model catalog endpoints."""

from __future__ import annotations

from services.grok.resources.base import Resource
from services.grok.safety import require_model_name


class ModelsResource(Resource):
    def list_all_models(self, *, timeout_seconds=None):
        """GET /v1/models. Includes names and pricing for the current API key."""
        return self._json("GET", "/v1/models", timeout_seconds=timeout_seconds)

    def retrieve_model(self, model_id, *, timeout_seconds=None):
        """GET /v1/models/{model_id}."""
        return self._json(
            "GET",
            f"/v1/models/{require_model_name(model_id)}",
            timeout_seconds=timeout_seconds,
        )

    def list_language_models(self, *, timeout_seconds=None):
        """GET /v1/language-models."""
        return self._json("GET", "/v1/language-models", timeout_seconds=timeout_seconds)

    def retrieve_language_model(self, model_id, *, timeout_seconds=None):
        """GET /v1/language-models/{model_id}."""
        return self._json(
            "GET",
            f"/v1/language-models/{require_model_name(model_id)}",
            timeout_seconds=timeout_seconds,
        )

    def list_image_generation_models(self, *, timeout_seconds=None):
        """GET /v1/image-generation-models."""
        return self._json("GET", "/v1/image-generation-models", timeout_seconds=timeout_seconds)

    def retrieve_image_generation_model(self, model_id, *, timeout_seconds=None):
        """GET /v1/image-generation-models/{model_id}."""
        return self._json(
            "GET",
            f"/v1/image-generation-models/{require_model_name(model_id)}",
            timeout_seconds=timeout_seconds,
        )

    def list_video_generation_models(self, *, timeout_seconds=None):
        """GET /v1/video-generation-models."""
        return self._json("GET", "/v1/video-generation-models", timeout_seconds=timeout_seconds)

    def retrieve_video_generation_model(self, model_id, *, timeout_seconds=None):
        """GET /v1/video-generation-models/{model_id}."""
        return self._json(
            "GET",
            f"/v1/video-generation-models/{require_model_name(model_id)}",
            timeout_seconds=timeout_seconds,
        )

    def list_embedding_models(self, *, timeout_seconds=None):
        """GET /v1/embedding-models."""
        return self._json("GET", "/v1/embedding-models", timeout_seconds=timeout_seconds)

    def retrieve_embedding_model(self, model_id, *, timeout_seconds=None):
        """GET /v1/embedding-models/{model_id}."""
        return self._json(
            "GET",
            f"/v1/embedding-models/{require_model_name(model_id)}",
            timeout_seconds=timeout_seconds,
        )
