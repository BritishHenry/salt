"""Collection management.

These calls use the management API host and a management key. The inference
API key is never sent here. Searching a collection uses DocumentsResource on
the inference API instead.
"""

from __future__ import annotations

from services.grok.constants import MAX_PAGINATION_PAGES
from services.grok.errors import GrokUsageError
from services.grok.resources.base import Resource
from services.grok.safety import (
    optional_dict,
    optional_identifier,
    optional_int,
    optional_text,
    require_non_empty_list,
    require_resource_id,
    require_text,
    without_none,
)

_METRIC_SPACES = frozenset(
    {
        "HNSW_METRIC_UNKNOWN",
        "HNSW_METRIC_COSINE",
        "HNSW_METRIC_EUCLIDEAN",
        "HNSW_METRIC_INNER_PRODUCT",
    }
)
_COLLECTION_ORDERS = frozenset(
    {"ORDERING_UNKNOWN", "ORDERING_ASCENDING", "ORDERING_DESCENDING"}
)
_COLLECTION_SORTS = frozenset({"COLLECTIONS_SORT_BY_NAME", "COLLECTIONS_SORT_BY_AGE"})
_DOCUMENT_SORTS = frozenset(
    {"DOCUMENTS_SORT_BY_NAME", "DOCUMENTS_SORT_BY_SIZE", "DOCUMENTS_SORT_BY_AGE"}
)


class CollectionsResource(Resource):
    def create_collection(
        self,
        collection_name,
        *,
        collection_description=None,
        index_configuration=None,
        chunk_configuration=None,
        metric_space=None,
        field_definitions=None,
        team_id=None,
        timeout_seconds=None,
    ):
        """POST /v1/collections on the management API."""
        body = without_none(
            {
                "collection_name": require_text(collection_name, "collection_name", max_length=200),
                "collection_description": optional_text(
                    collection_description, "collection_description", max_length=2000
                ),
                "index_configuration": optional_dict(index_configuration, "index_configuration"),
                "chunk_configuration": optional_dict(chunk_configuration, "chunk_configuration"),
                "metric_space": _choice(metric_space, "metric_space", _METRIC_SPACES),
                "field_definitions": field_definitions,
                "team_id": optional_identifier(team_id, "team_id"),
            }
        )
        return self._json("POST", "/v1/collections", body=body, timeout_seconds=timeout_seconds)

    def list_collections_page(
        self,
        *,
        team_id=None,
        limit=None,
        order=None,
        sort_by=None,
        pagination_token=None,
        filter_expression=None,
        timeout_seconds=None,
    ):
        """GET /v1/collections."""
        query = without_none(
            {
                "team_id": optional_identifier(team_id, "team_id"),
                "limit": optional_int(limit, "limit", minimum=1, maximum=100),
                "order": _choice(order, "order", _COLLECTION_ORDERS),
                "sort_by": _choice(sort_by, "sort_by", _COLLECTION_SORTS),
                "pagination_token": optional_identifier(pagination_token, "pagination_token"),
                "filter": optional_text(filter_expression, "filter_expression", max_length=2000),
            }
        )
        return self._json("GET", "/v1/collections", query=query, timeout_seconds=timeout_seconds)

    def list_all_collections(self, *, max_pages=MAX_PAGINATION_PAGES, timeout_seconds=None, **filters):
        def fetch(token):
            return self.list_collections_page(
                pagination_token=token,
                timeout_seconds=timeout_seconds,
                **filters,
            )

        return self._collect_token_pages(fetch, items_key="collections", max_pages=max_pages)

    def retrieve_collection(self, collection_id, *, team_id=None, timeout_seconds=None):
        """GET /v1/collections/{collection_id}."""
        return self._json(
            "GET",
            f"/v1/collections/{require_resource_id(collection_id, 'collection_id')}",
            query=without_none({"team_id": optional_identifier(team_id, "team_id")}),
            timeout_seconds=timeout_seconds,
        )

    def update_collection(
        self,
        collection_id,
        *,
        collection_name=None,
        collection_description=None,
        chunk_configuration=None,
        field_definition_updates=None,
        team_id=None,
        timeout_seconds=None,
    ):
        """PUT /v1/collections/{collection_id}."""
        body = without_none(
            {
                "collection_name": optional_text(collection_name, "collection_name", max_length=200),
                "collection_description": optional_text(
                    collection_description, "collection_description", max_length=2000
                ),
                "chunk_configuration": optional_dict(chunk_configuration, "chunk_configuration"),
                "field_definition_updates": field_definition_updates,
                "team_id": optional_identifier(team_id, "team_id"),
            }
        )
        if not body or set(body) == {"team_id"}:
            raise GrokUsageError("Provide at least one collection field to update.")
        return self._json(
            "PUT",
            f"/v1/collections/{require_resource_id(collection_id, 'collection_id')}",
            body=body,
            timeout_seconds=timeout_seconds,
        )

    def delete_collection(self, collection_id, *, team_id=None, timeout_seconds=None):
        """DELETE /v1/collections/{collection_id}."""
        return self._json(
            "DELETE",
            f"/v1/collections/{require_resource_id(collection_id, 'collection_id')}",
            query=without_none({"team_id": optional_identifier(team_id, "team_id")}),
            timeout_seconds=timeout_seconds,
        )

    def add_file_to_collection(
        self,
        collection_id,
        file_id,
        *,
        fields=None,
        team_id=None,
        timeout_seconds=None,
    ):
        """POST /v1/collections/{collection_id}/documents/{file_id}."""
        body = without_none(
            {
                "fields": optional_dict(fields, "fields"),
                "team_id": optional_identifier(team_id, "team_id"),
            }
        )
        return self._json(
            "POST",
            _document_path(collection_id, file_id),
            body=body or None,
            timeout_seconds=timeout_seconds,
        )

    def list_collection_documents_page(
        self,
        collection_id,
        *,
        team_id=None,
        limit=None,
        order=None,
        sort_by=None,
        pagination_token=None,
        filter_expression=None,
        timeout_seconds=None,
    ):
        """GET /v1/collections/{collection_id}/documents."""
        query = without_none(
            {
                "team_id": optional_identifier(team_id, "team_id"),
                "limit": optional_int(limit, "limit", minimum=1, maximum=100),
                "order": _choice(order, "order", _COLLECTION_ORDERS),
                "sort_by": _choice(sort_by, "sort_by", _DOCUMENT_SORTS),
                "pagination_token": optional_identifier(pagination_token, "pagination_token"),
                "filter": optional_text(filter_expression, "filter_expression", max_length=2000),
            }
        )
        return self._json(
            "GET",
            f"/v1/collections/{require_resource_id(collection_id, 'collection_id')}/documents",
            query=query,
            timeout_seconds=timeout_seconds,
        )

    def list_all_collection_documents(
        self,
        collection_id,
        *,
        max_pages=MAX_PAGINATION_PAGES,
        timeout_seconds=None,
        **filters,
    ):
        def fetch(token):
            return self.list_collection_documents_page(
                collection_id,
                pagination_token=token,
                timeout_seconds=timeout_seconds,
                **filters,
            )

        return self._collect_token_pages(fetch, items_key="documents", max_pages=max_pages)

    def retrieve_collection_document(
        self,
        collection_id,
        file_id,
        *,
        team_id=None,
        timeout_seconds=None,
    ):
        """GET /v1/collections/{collection_id}/documents/{file_id}."""
        return self._json(
            "GET",
            _document_path(collection_id, file_id),
            query=without_none({"team_id": optional_identifier(team_id, "team_id")}),
            timeout_seconds=timeout_seconds,
        )

    def reindex_collection_document(
        self,
        collection_id,
        file_id,
        *,
        team_id=None,
        timeout_seconds=None,
    ):
        """PATCH /v1/collections/{collection_id}/documents/{file_id}."""
        return self._json(
            "PATCH",
            _document_path(collection_id, file_id),
            query=without_none({"team_id": optional_identifier(team_id, "team_id")}),
            timeout_seconds=timeout_seconds,
        )

    def remove_file_from_collection(
        self,
        collection_id,
        file_id,
        *,
        team_id=None,
        timeout_seconds=None,
    ):
        """DELETE /v1/collections/{collection_id}/documents/{file_id}."""
        return self._json(
            "DELETE",
            _document_path(collection_id, file_id),
            query=without_none({"team_id": optional_identifier(team_id, "team_id")}),
            timeout_seconds=timeout_seconds,
        )

    def batch_get_collection_documents(
        self,
        collection_id,
        file_ids,
        *,
        team_id=None,
        timeout_seconds=None,
    ):
        """GET /v1/collections/{collection_id}/documents:batchGet."""
        ids = require_non_empty_list(list(file_ids), "file_ids")
        if len(ids) > 100:
            raise GrokUsageError("batch_get accepts at most 100 file ids.")
        query = {
            "file_ids": [require_resource_id(item, "file_id") for item in ids],
        }
        team = optional_identifier(team_id, "team_id")
        if team is not None:
            query["team_id"] = team
        return self._json(
            "GET",
            f"/v1/collections/{require_resource_id(collection_id, 'collection_id')}/documents:batchGet",
            query=query,
            timeout_seconds=timeout_seconds,
        )


def _document_path(collection_id, file_id):
    return (
        f"/v1/collections/{require_resource_id(collection_id, 'collection_id')}"
        f"/documents/{require_resource_id(file_id, 'file_id')}"
    )


def _choice(value, name, choices):
    if value is None:
        return None
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise GrokUsageError(f"{name} must be one of: {allowed}.")
    return value
