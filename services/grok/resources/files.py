"""Files API. Uploaded files can be attached to chat, image, and video calls."""

from __future__ import annotations

import mimetypes

from services.grok.constants import MAX_FILE_UPLOAD_BYTES, MAX_PAGINATION_PAGES, MAX_RESPONSE_BYTES
from services.grok.resources.base import Resource
from services.grok.safety import (
    optional_identifier,
    optional_int,
    optional_text,
    optional_token,
    read_file_with_limit,
    require_resource_id,
    safe_content_type,
    safe_filename,
    without_none,
)
from services.grok.transport import encode_multipart_form


class FilesResource(Resource):
    def list_files_page(
        self,
        *,
        limit=None,
        order=None,
        sort_by=None,
        pagination_token=None,
        filter_expression=None,
        timeout_seconds=None,
    ):
        """GET /v1/files. Pass pagination_token from the previous page to continue."""
        query = without_none(
            {
                "limit": optional_int(limit, "limit", minimum=1, maximum=1000),
                "order": _order(order),
                "sort_by": _sort_by(sort_by),
                "pagination_token": optional_identifier(pagination_token, "pagination_token"),
                "filter": optional_text(filter_expression, "filter_expression", max_length=2000),
            }
        )
        return self._json("GET", "/v1/files", query=query, timeout_seconds=timeout_seconds)

    def list_all_files(
        self,
        *,
        limit=100,
        order=None,
        sort_by=None,
        filter_expression=None,
        max_pages=MAX_PAGINATION_PAGES,
        timeout_seconds=None,
    ):
        """Follow pagination tokens until the file list ends."""

        def fetch(token):
            return self.list_files_page(
                limit=limit,
                order=order,
                sort_by=sort_by,
                pagination_token=token,
                filter_expression=filter_expression,
                timeout_seconds=timeout_seconds,
            )

        return self._collect_token_pages(fetch, items_key="data", max_pages=max_pages)

    def upload_file_bytes(
        self,
        data,
        *,
        filename,
        content_type=None,
        purpose=None,
        expires_after_seconds=None,
        timeout_seconds=None,
    ):
        """POST /v1/files. Maximum size is 50 MB."""
        from services.grok.errors import GrokUsageError

        if not isinstance(data, (bytes, bytearray)):
            raise GrokUsageError("data must be bytes.")
        if len(data) > MAX_FILE_UPLOAD_BYTES:
            raise GrokUsageError(
                f"Files sent to /v1/files must be at most {MAX_FILE_UPLOAD_BYTES} bytes."
            )
        return self._upload(
            bytes(data),
            filename=filename,
            content_type=content_type,
            purpose=purpose,
            expires_after_seconds=expires_after_seconds,
            timeout_seconds=timeout_seconds,
        )

    def upload_file_from_path(
        self,
        path,
        *,
        content_type=None,
        purpose=None,
        expires_after_seconds=None,
        timeout_seconds=None,
    ):
        """POST /v1/files using a local file path."""
        data, filename = read_file_with_limit(path, MAX_FILE_UPLOAD_BYTES, "path")
        guessed = content_type or mimetypes.guess_type(filename)[0]
        return self._upload(
            data,
            filename=filename,
            content_type=guessed,
            purpose=purpose,
            expires_after_seconds=expires_after_seconds,
            timeout_seconds=timeout_seconds,
        )

    def retrieve_file_metadata(self, file_id, *, timeout_seconds=None):
        """GET /v1/files/{file_id}."""
        return self._json(
            "GET",
            f"/v1/files/{require_resource_id(file_id, 'file_id')}",
            timeout_seconds=timeout_seconds,
        )

    def delete_file(self, file_id, *, timeout_seconds=None):
        """DELETE /v1/files/{file_id}."""
        return self._json(
            "DELETE",
            f"/v1/files/{require_resource_id(file_id, 'file_id')}",
            timeout_seconds=timeout_seconds,
        )

    def download_file_bytes(self, file_id, *, content_format=None, timeout_seconds=None):
        """GET /v1/files/{file_id}/content. content_format is 'original' or 'text'."""
        if content_format not in (None, "original", "text"):
            from services.grok.errors import GrokUsageError

            raise GrokUsageError("content_format must be 'original' or 'text'.")
        return self._bytes(
            "GET",
            f"/v1/files/{require_resource_id(file_id, 'file_id')}/content",
            query=without_none({"format": content_format}),
            timeout_seconds=timeout_seconds,
            max_response_bytes=MAX_RESPONSE_BYTES,
        )

    def create_unauthenticated_public_url_for_file(
        self,
        file_id,
        *,
        expires_after_seconds=None,
        timeout_seconds=None,
    ):
        """POST /v1/files/{file_id}/public-url.

        This makes the file readable without an API key until you revoke it
        or the expiry elapses. The file itself is not deleted.
        """
        body = without_none(
            {
                "expires_after": optional_int(
                    expires_after_seconds,
                    "expires_after_seconds",
                    minimum=1,
                    maximum=60 * 60 * 24 * 365,
                )
            }
        )
        return self._json(
            "POST",
            f"/v1/files/{require_resource_id(file_id, 'file_id')}/public-url",
            body=body or None,
            timeout_seconds=timeout_seconds,
        )

    def revoke_public_file_url(self, file_id, *, timeout_seconds=None):
        """POST /v1/files/{file_id}/public-url/revoke. The stored file remains."""
        return self._json(
            "POST",
            f"/v1/files/{require_resource_id(file_id, 'file_id')}/public-url/revoke",
            timeout_seconds=timeout_seconds,
        )

    def _upload(
        self,
        data,
        *,
        filename,
        content_type,
        purpose,
        expires_after_seconds,
        timeout_seconds,
    ):
        fields = []
        if purpose is not None:
            fields.append(("purpose", optional_token(purpose, "purpose")))
        if expires_after_seconds is not None:
            seconds = optional_int(
                expires_after_seconds,
                "expires_after_seconds",
                minimum=1,
                maximum=60 * 60 * 24 * 365,
            )
            fields.append(("expires_after", seconds))
        raw, form_type = encode_multipart_form(
            fields,
            [
                (
                    "file",
                    safe_filename(filename),
                    safe_content_type(content_type),
                    data,
                )
            ],
        )
        result = self._http.send(
            "POST",
            "/v1/files",
            raw_body=raw,
            content_type=form_type,
            timeout_seconds=timeout_seconds or 300,
            max_request_bytes=MAX_FILE_UPLOAD_BYTES + 1_000_000,
            parse_json=True,
        )
        return result.json_body or {}


def _order(value):
    if value is None:
        return None
    if value not in {"asc", "desc"}:
        from services.grok.errors import GrokUsageError

        raise GrokUsageError("order must be 'asc' or 'desc'.")
    return value


def _sort_by(value):
    if value is None:
        return None
    if value not in {"created_at", "filename", "size"}:
        from services.grok.errors import GrokUsageError

        raise GrokUsageError("sort_by must be 'created_at', 'filename', or 'size'.")
    return value
