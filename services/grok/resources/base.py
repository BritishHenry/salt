"""Shared request helpers for Grok resources."""

from __future__ import annotations

import time

from services.grok.constants import MAX_PAGINATION_PAGES
from services.grok.errors import GrokApiError, GrokSafetyError, GrokTimeoutError, GrokUsageError
from services.grok.parsing import DeferredOperation


class Resource:
    def __init__(self, transport):
        self._http = transport

    def _json(
        self,
        method,
        path,
        *,
        query=None,
        body=None,
        accepted_statuses=(200,),
        timeout_seconds=None,
        max_request_bytes=None,
    ):
        result = self._http.send(
            method,
            path,
            query=query,
            json_body=body,
            accepted_statuses=accepted_statuses,
            timeout_seconds=timeout_seconds,
            parse_json=True,
            max_request_bytes=max_request_bytes,
        )
        if result.json_body is None:
            return {}
        if not isinstance(result.json_body, dict):
            raise GrokApiError(
                "Expected a JSON object from the Grok API.",
                status_code=result.status_code,
            )
        return result.json_body

    def _bytes(self, method, path, *, query=None, timeout_seconds=None, max_response_bytes=None):
        result = self._http.send(
            method,
            path,
            query=query,
            accepted_statuses=(200,),
            timeout_seconds=timeout_seconds,
            parse_json=False,
            max_response_bytes=max_response_bytes,
        )
        content_type = result.content_type
        if content_type == "application/json":
            message = "The API returned JSON instead of file bytes."
            if result.body:
                message = result.body.decode("utf-8", errors="replace")[:500]
            raise GrokApiError(message, status_code=result.status_code)
        return result.body

    def _deferred(self, method, path, *, body=None, timeout_seconds=None):
        result = self._http.send(
            method,
            path,
            json_body=body,
            accepted_statuses=(200, 202),
            timeout_seconds=timeout_seconds,
            parse_json=True,
        )
        payload = result.json_body if isinstance(result.json_body, dict) else {}
        pending = result.status_code == 202 or payload.get("status") == "pending"
        return DeferredOperation(
            pending=pending,
            body=payload,
            status_code=result.status_code,
        )

    def _collect_token_pages(self, fetch_page, *, items_key, max_pages):
        return _collect_pages(
            fetch_page,
            items_key=items_key,
            max_pages=max_pages,
            token_of=lambda page: page.get("pagination_token") or None,
        )

    def _collect_cursor_pages(self, fetch_page, *, items_key, max_pages):
        def token_of(page):
            if not page.get("has_more"):
                return None
            cursor = page.get("last_id")
            if not cursor:
                raise GrokSafetyError(
                    "The API did not advance the page cursor, so listing stopped."
                )
            return cursor

        return _collect_pages(
            fetch_page,
            items_key=items_key,
            max_pages=max_pages,
            token_of=token_of,
        )

    def _wait_until_ready(
        self,
        fetch,
        *,
        request_id,
        poll_interval_seconds,
        timeout_seconds,
        sleep,
        monotonic,
        operation_name,
        failed_message,
    ):
        if poll_interval_seconds < 0.2:
            raise GrokUsageError("poll_interval_seconds must be at least 0.2.")
        if timeout_seconds <= 0 or timeout_seconds > 3600:
            raise GrokUsageError("timeout_seconds must be between 0 and 3600.")
        sleep = sleep or time.sleep
        monotonic = monotonic or time.monotonic
        deadline = monotonic() + timeout_seconds
        while True:
            operation = fetch()
            if not operation.pending:
                status = str(operation.body.get("status") or "").lower()
                if status == "failed":
                    raise GrokApiError(failed_message(operation.body), status_code=operation.status_code)
                return operation.body
            if monotonic() >= deadline:
                raise GrokTimeoutError(
                    f"{operation_name} {request_id} was still pending after {timeout_seconds:g} seconds."
                )
            sleep(poll_interval_seconds)


def _collect_pages(fetch_page, *, items_key, max_pages, token_of):
    if max_pages < 1 or max_pages > MAX_PAGINATION_PAGES:
        raise GrokSafetyError(f"max_pages must be between 1 and {MAX_PAGINATION_PAGES}.")
    items = []
    token = None
    seen = set()
    for _ in range(max_pages):
        page = fetch_page(token)
        page_items = page.get(items_key) or []
        if not isinstance(page_items, list):
            raise GrokApiError(f"Expected a list in {items_key}.")
        items.extend(page_items)
        next_token = token_of(page)
        if not next_token:
            return items
        if next_token in seen:
            raise GrokSafetyError("The API repeated a pagination token, so listing stopped.")
        seen.add(next_token)
        token = next_token
    raise GrokSafetyError(
        f"Stopped after {max_pages} pages. Pass a higher max_pages if this list is expected to be longer."
    )
