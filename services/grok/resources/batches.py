"""Batch API. Submit many chat completions and collect results later."""

from __future__ import annotations

from services.grok.constants import MAX_PAGINATION_PAGES
from services.grok.errors import GrokUsageError
from services.grok.resources.base import Resource
from services.grok.safety import (
    optional_identifier,
    optional_int,
    require_resource_id,
    require_text,
    without_none,
)


class BatchesResource(Resource):
    def create_batch(self, name, *, timeout_seconds=None):
        """POST /v1/batches."""
        return self._json(
            "POST",
            "/v1/batches",
            body={"name": require_text(name, "name", max_length=200)},
            timeout_seconds=timeout_seconds,
        )

    def list_batches_page(self, *, limit=None, pagination_token=None, timeout_seconds=None):
        """GET /v1/batches."""
        query = without_none(
            {
                "limit": optional_int(limit, "limit", minimum=1, maximum=1000),
                "pagination_token": optional_identifier(pagination_token, "pagination_token"),
            }
        )
        return self._json("GET", "/v1/batches", query=query, timeout_seconds=timeout_seconds)

    def list_all_batches(
        self,
        *,
        limit=100,
        max_pages=MAX_PAGINATION_PAGES,
        timeout_seconds=None,
    ):
        def fetch(token):
            return self.list_batches_page(
                limit=limit,
                pagination_token=token,
                timeout_seconds=timeout_seconds,
            )

        return self._collect_token_pages(fetch, items_key="batches", max_pages=max_pages)

    def retrieve_batch(self, batch_id, *, timeout_seconds=None):
        """GET /v1/batches/{batch_id}."""
        return self._json(
            "GET",
            f"/v1/batches/{require_resource_id(batch_id, 'batch_id')}",
            timeout_seconds=timeout_seconds,
        )

    def list_batch_requests_page(
        self,
        batch_id,
        *,
        limit=None,
        pagination_token=None,
        timeout_seconds=None,
    ):
        """GET /v1/batches/{batch_id}/requests."""
        query = without_none(
            {
                "limit": optional_int(limit, "limit", minimum=1, maximum=1000),
                "pagination_token": optional_identifier(pagination_token, "pagination_token"),
            }
        )
        return self._json(
            "GET",
            f"/v1/batches/{require_resource_id(batch_id, 'batch_id')}/requests",
            query=query,
            timeout_seconds=timeout_seconds,
        )

    def list_all_batch_requests(
        self,
        batch_id,
        *,
        limit=100,
        max_pages=MAX_PAGINATION_PAGES,
        timeout_seconds=None,
    ):
        def fetch(token):
            return self.list_batch_requests_page(
                batch_id,
                limit=limit,
                pagination_token=token,
                timeout_seconds=timeout_seconds,
            )

        return self._collect_token_pages(
            fetch, items_key="batch_request_metadata", max_pages=max_pages
        )

    def add_chat_completion_requests_to_batch(
        self,
        batch_id,
        chat_completion_requests,
        *,
        timeout_seconds=None,
    ):
        """POST /v1/batches/{batch_id}/requests.

        Each item is a dict with batch_request_id and the chat completion fields
        (model and messages at minimum). The client wraps them in the
        chat_get_completion envelope the batch API expects.
        """
        if not isinstance(chat_completion_requests, list) or not chat_completion_requests:
            raise GrokUsageError("chat_completion_requests must be a non-empty list.")
        if len(chat_completion_requests) > 1000:
            raise GrokUsageError("Add at most 1000 requests to a batch in one call.")
        wrapped = []
        seen_ids = set()
        for item in chat_completion_requests:
            if not isinstance(item, dict):
                raise GrokUsageError("Each batch request must be an object.")
            request_id = item.get("batch_request_id")
            if request_id is not None:
                request_id = require_text(str(request_id), "batch_request_id", max_length=200)
                if any(character.isspace() for character in request_id):
                    raise GrokUsageError("batch_request_id must not contain spaces.")
                if request_id in seen_ids:
                    raise GrokUsageError(f"batch_request_id {request_id!r} is duplicated.")
                seen_ids.add(request_id)
            chat_body = {key: value for key, value in item.items() if key != "batch_request_id"}
            if "model" not in chat_body or "messages" not in chat_body:
                raise GrokUsageError("Each batch chat request needs model and messages.")
            wrapped.append(
                without_none(
                    {
                        "batch_request_id": request_id,
                        "batch_request": {"chat_get_completion": chat_body},
                    }
                )
            )
        return self._json(
            "POST",
            f"/v1/batches/{require_resource_id(batch_id, 'batch_id')}/requests",
            body={"batch_requests": wrapped},
            timeout_seconds=timeout_seconds,
        )

    def list_batch_results_page(
        self,
        batch_id,
        *,
        limit=None,
        pagination_token=None,
        timeout_seconds=None,
    ):
        """GET /v1/batches/{batch_id}/results."""
        query = without_none(
            {
                "limit": optional_int(limit, "limit", minimum=1, maximum=1000),
                "pagination_token": optional_identifier(pagination_token, "pagination_token"),
            }
        )
        return self._json(
            "GET",
            f"/v1/batches/{require_resource_id(batch_id, 'batch_id')}/results",
            query=query,
            timeout_seconds=timeout_seconds,
        )

    def list_all_batch_results(
        self,
        batch_id,
        *,
        limit=100,
        max_pages=MAX_PAGINATION_PAGES,
        timeout_seconds=None,
    ):
        def fetch(token):
            return self.list_batch_results_page(
                batch_id,
                limit=limit,
                pagination_token=token,
                timeout_seconds=timeout_seconds,
            )

        return self._collect_token_pages(fetch, items_key="results", max_pages=max_pages)

    def cancel_batch(self, batch_id, *, timeout_seconds=None):
        """POST /v1/batches/{batch_id}:cancel."""
        return self._json(
            "POST",
            f"/v1/batches/{require_resource_id(batch_id, 'batch_id')}:cancel",
            timeout_seconds=timeout_seconds,
        )
