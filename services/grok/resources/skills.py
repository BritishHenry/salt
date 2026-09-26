"""Reusable skill bundles the Responses API can load."""

from __future__ import annotations

from services.grok.constants import MAX_FILE_UPLOAD_BYTES, MAX_PAGINATION_PAGES, MAX_RESPONSE_BYTES
from services.grok.errors import GrokUsageError
from services.grok.resources.base import Resource
from services.grok.safety import (
    optional_identifier,
    optional_int,
    optional_token,
    read_file_with_limit,
    require_resource_id,
    safe_content_type,
    safe_filename,
    without_none,
)
from services.grok.transport import encode_multipart_form


class SkillsResource(Resource):
    def list_skills_page(
        self,
        *,
        limit=None,
        after=None,
        order=None,
        timeout_seconds=None,
    ):
        """GET /v1/skills."""
        query = without_none(
            {
                "limit": optional_int(limit, "limit", minimum=1, maximum=100),
                "after": optional_identifier(after, "after"),
                "order": optional_token(order, "order"),
            }
        )
        return self._json("GET", "/v1/skills", query=query, timeout_seconds=timeout_seconds)

    def list_all_skills(
        self,
        *,
        limit=None,
        order=None,
        max_pages=MAX_PAGINATION_PAGES,
        timeout_seconds=None,
    ):
        """Follow skill pages until has_more is false."""

        def fetch(cursor):
            return self.list_skills_page(
                limit=limit,
                after=cursor,
                order=order,
                timeout_seconds=timeout_seconds,
            )

        return self._collect_cursor_pages(fetch, items_key="data", max_pages=max_pages)

    def upload_skill_files(self, files, *, timeout_seconds=None):
        """POST /v1/skills.

        files is a list of (filename, bytes) or (filename, bytes, content_type).
        Send one zip, or repeat the field with the files from a skill directory.
        """
        if not isinstance(files, list) or not files:
            raise GrokUsageError("files must be a non-empty list of skill files.")
        parts = []
        total = 0
        for item in files:
            if len(item) == 2:
                filename, data = item
                content_type = "application/octet-stream"
            elif len(item) == 3:
                filename, data, content_type = item
            else:
                raise GrokUsageError("Each skill file must be (filename, bytes) or (filename, bytes, content_type).")
            if not isinstance(data, (bytes, bytearray)):
                raise GrokUsageError("Skill file contents must be bytes.")
            total += len(data)
            parts.append(
                ("files", safe_filename(filename), safe_content_type(content_type), bytes(data))
            )
        if total > MAX_FILE_UPLOAD_BYTES:
            raise GrokUsageError(
                f"Skill uploads must be at most {MAX_FILE_UPLOAD_BYTES} bytes."
            )
        raw, form_type = encode_multipart_form([], parts)
        result = self._http.send(
            "POST",
            "/v1/skills",
            raw_body=raw,
            content_type=form_type,
            timeout_seconds=timeout_seconds or 300,
            max_request_bytes=MAX_FILE_UPLOAD_BYTES + 1_000_000,
            parse_json=True,
        )
        return result.json_body or {}

    def upload_skill_from_path(self, path, *, content_type=None, timeout_seconds=None):
        """POST /v1/skills with one local zip or file."""
        data, filename = read_file_with_limit(path, MAX_FILE_UPLOAD_BYTES, "path")
        return self.upload_skill_files(
            [(filename, data, content_type or "application/zip")],
            timeout_seconds=timeout_seconds,
        )

    def retrieve_skill(self, skill_id, *, timeout_seconds=None):
        """GET /v1/skills/{skill_id}."""
        return self._json(
            "GET",
            f"/v1/skills/{require_resource_id(skill_id, 'skill_id')}",
            timeout_seconds=timeout_seconds,
        )

    def delete_skill(self, skill_id, *, timeout_seconds=None):
        """DELETE /v1/skills/{skill_id}."""
        return self._json(
            "DELETE",
            f"/v1/skills/{require_resource_id(skill_id, 'skill_id')}",
            timeout_seconds=timeout_seconds,
        )

    def download_skill_content(self, skill_id, *, timeout_seconds=None):
        """GET /v1/skills/{skill_id}/content."""
        return self._bytes(
            "GET",
            f"/v1/skills/{require_resource_id(skill_id, 'skill_id')}/content",
            timeout_seconds=timeout_seconds,
            max_response_bytes=MAX_RESPONSE_BYTES,
        )
