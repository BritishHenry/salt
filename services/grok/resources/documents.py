"""Search documents that already live in collections."""

from __future__ import annotations

from services.grok.errors import GrokUsageError
from services.grok.resources.base import Resource
from services.grok.safety import (
    optional_dict,
    optional_int,
    optional_text,
    require_non_empty_list,
    require_resource_id,
    require_text,
    without_none,
)

_RETRIEVAL_MODES = frozenset({"hybrid", "semantic", "keyword"})
_RANKING_METRICS = frozenset(
    {
        "RANKING_METRIC_UNKNOWN",
        "RANKING_METRIC_L2_DISTANCE",
        "RANKING_METRIC_COSINE_SIMILARITY",
    }
)


class DocumentsResource(Resource):
    def search_collection_documents(
        self,
        query,
        collection_ids,
        *,
        limit=None,
        instructions=None,
        filter_expression=None,
        retrieval_mode=None,
        ranking_metric=None,
        group_by=None,
        timeout_seconds=None,
    ):
        """POST /v1/documents/search on the inference API.

        collection_ids are collection ids from the management Collections API.
        retrieval_mode may be 'hybrid', 'semantic', 'keyword', or a full object.
        """
        ids = require_non_empty_list(list(collection_ids), "collection_ids")
        body = without_none(
            {
                "query": require_text(query, "query", max_length=20_000),
                "source": {
                    "collection_ids": [
                        require_resource_id(item, "collection_id") for item in ids
                    ]
                },
                "limit": optional_int(limit, "limit", minimum=1, maximum=100),
                "instructions": optional_text(instructions, "instructions", max_length=10_000),
                "filter": optional_text(filter_expression, "filter_expression", max_length=2000),
                "retrieval_mode": _retrieval_mode(retrieval_mode),
                "ranking_metric": _ranking_metric(ranking_metric),
                "group_by": optional_dict(group_by, "group_by"),
            }
        )
        return self._json(
            "POST",
            "/v1/documents/search",
            body=body,
            timeout_seconds=timeout_seconds,
        )


def _retrieval_mode(value):
    if value is None:
        return None
    if isinstance(value, str):
        if value not in _RETRIEVAL_MODES:
            raise GrokUsageError("retrieval_mode must be 'hybrid', 'semantic', or 'keyword'.")
        return {"type": value}
    if isinstance(value, dict) and value.get("type") in _RETRIEVAL_MODES:
        return value
    raise GrokUsageError("retrieval_mode must be 'hybrid', 'semantic', 'keyword', or an object.")


def _ranking_metric(value):
    if value is None:
        return None
    if value not in _RANKING_METRICS:
        allowed = ", ".join(sorted(_RANKING_METRICS))
        raise GrokUsageError(f"ranking_metric must be one of: {allowed}.")
    return value
