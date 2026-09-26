"""Verbose builders for messages, tools, and media references.

These return plain dictionaries the resource methods accept, so call sites
stay explicit about which Grok feature they are turning on.
"""

from __future__ import annotations

from services.grok.safety import (
    exclusive_reference,
    function_name,
    optional_bool,
    optional_date,
    optional_dict,
    optional_int,
    optional_text,
    require_dict,
    require_https_url,
    require_non_empty_list,
    require_resource_id,
    require_text,
    without_none,
)

_IMAGE_DATA_PREFIX = "data:image/"
_AUDIO_DATA_PREFIX = "data:audio/"
_VIDEO_DATA_PREFIX = "data:video/"


def image_reference(*, file_id=None, url=None):
    """Build an image input from either a Files API id or an https/data URL."""
    return exclusive_reference(
        file_id=file_id,
        url=url,
        allowed_data_prefix=_IMAGE_DATA_PREFIX,
        label="image",
    )


def video_reference(*, file_id=None, url=None):
    """Build a video input from either a Files API id or an https/data URL."""
    return exclusive_reference(
        file_id=file_id,
        url=url,
        allowed_data_prefix=_VIDEO_DATA_PREFIX,
        label="video",
    )


def audio_reference(*, voice_id=None, url=None):
    """Build a reference-audio input for video generation."""
    from services.grok.errors import GrokUsageError
    from services.grok.safety import require_https_or_data_url

    if (voice_id is None) == (url is None):
        raise GrokUsageError("Provide exactly one of voice_id or url for reference audio.")
    if voice_id is not None:
        return {"voice_id": require_resource_id(voice_id, "voice_id")}
    return {
        "url": require_https_or_data_url(
            url,
            allowed_data_prefix=_AUDIO_DATA_PREFIX,
            name="audio_url",
        )
    }


def system_text_message(text):
    return {"role": "system", "content": require_text(text, "text")}


def user_text_message(text):
    return {"role": "user", "content": require_text(text, "text")}


def assistant_text_message(text):
    return {"role": "assistant", "content": require_text(text, "text")}


def user_message_with_image(text, *, image_url=None, image_file_id=None):
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": require_text(text, "text")},
            {
                "type": "image_url",
                "image_url": image_reference(file_id=image_file_id, url=image_url),
            },
        ],
    }


def user_message_with_file(text, *, file_id=None, file_url=None):
    reference = exclusive_reference(
        file_id=file_id,
        url=file_url,
        allowed_data_prefix="data:application/",
        label="file",
    )
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": require_text(text, "text")},
            {"type": "file", "file": reference},
        ],
    }


def responses_function_tool(name, parameters, *, description=None, defer_loading=None):
    """Function tool for POST /v1/responses. The definition is flat, not nested."""
    return without_none(
        {
            "type": "function",
            "name": function_name(name),
            "parameters": require_dict(parameters, "parameters"),
            "description": optional_text(description, "description"),
            "defer_loading": optional_bool(defer_loading, "defer_loading"),
        }
    )


def chat_function_tool(name, parameters, *, description=None):
    """Function tool for POST /v1/chat/completions."""
    return {
        "type": "function",
        "function": without_none(
            {
                "name": function_name(name),
                "parameters": require_dict(parameters, "parameters"),
                "description": optional_text(description, "description"),
            }
        ),
    }


def web_search_tool(
    *,
    allowed_domains=None,
    excluded_domains=None,
    enable_image_search=None,
    enable_image_understanding=None,
):
    """Server-side web search tool for the Responses API."""
    from services.grok.errors import GrokUsageError

    if allowed_domains and excluded_domains:
        raise GrokUsageError("Set allowed_domains or excluded_domains, not both.")
    return without_none(
        {
            "type": "web_search",
            "allowed_domains": _domains(allowed_domains, "allowed_domains"),
            "excluded_domains": _domains(excluded_domains, "excluded_domains"),
            "enable_image_search": optional_bool(enable_image_search, "enable_image_search"),
            "enable_image_understanding": optional_bool(
                enable_image_understanding, "enable_image_understanding"
            ),
        }
    )


def x_search_tool(
    *,
    allowed_x_handles=None,
    excluded_x_handles=None,
    from_date=None,
    to_date=None,
    enable_image_understanding=None,
    enable_video_understanding=None,
):
    """Server-side X search tool for the Responses API."""
    from services.grok.errors import GrokUsageError

    if allowed_x_handles and excluded_x_handles:
        raise GrokUsageError("Set allowed_x_handles or excluded_x_handles, not both.")
    return without_none(
        {
            "type": "x_search",
            "allowed_x_handles": _handles(allowed_x_handles, "allowed_x_handles"),
            "excluded_x_handles": _handles(excluded_x_handles, "excluded_x_handles"),
            "from_date": optional_date(from_date, "from_date"),
            "to_date": optional_date(to_date, "to_date"),
            "enable_image_understanding": optional_bool(
                enable_image_understanding, "enable_image_understanding"
            ),
            "enable_video_understanding": optional_bool(
                enable_video_understanding, "enable_video_understanding"
            ),
        }
    )


def file_search_tool(vector_store_ids, *, max_num_results=None):
    """Search collections previously indexed for this team."""
    ids = require_non_empty_list(vector_store_ids, "vector_store_ids")
    return without_none(
        {
            "type": "file_search",
            "vector_store_ids": [require_resource_id(item, "vector_store_id") for item in ids],
            "max_num_results": optional_int(max_num_results, "max_num_results", minimum=1, maximum=50),
        }
    )


def code_interpreter_tool():
    """Server-side code execution tool for the Responses API."""
    return {"type": "code_interpreter"}


def image_generation_tool(*, action=None):
    return without_none(
        {
            "type": "image_generation",
            "action": optional_text(action, "action", max_length=64),
        }
    )


def mcp_server_tool(
    *,
    server_label,
    server_url,
    allowed_tools=None,
    authorization=None,
    server_description=None,
    require_approval=None,
):
    """Remote MCP server the Responses API may call. authorization is a credential."""
    return without_none(
        {
            "type": "mcp",
            "server_label": require_text(server_label, "server_label", max_length=128),
            "server_url": require_https_url(server_url, "server_url"),
            "allowed_tools": allowed_tools,
            "authorization": optional_text(authorization, "authorization", max_length=4096),
            "server_description": optional_text(server_description, "server_description"),
            "require_approval": require_approval,
        }
    )


def chat_live_search_tool(sources):
    """Live search tool for POST /v1/chat/completions."""
    items = require_non_empty_list(sources, "sources")
    for item in items:
        require_dict(item, "sources item")
    return {"type": "live_search", "sources": items}


def live_search_parameters(
    *,
    mode=None,
    return_citations=None,
    max_search_results=None,
    from_date=None,
    to_date=None,
    sources=None,
):
    """search_parameters object for chat completions."""
    from services.grok.errors import GrokUsageError

    if mode is not None and mode not in {"off", "on", "auto"}:
        raise GrokUsageError("mode must be 'off', 'on', or 'auto'.")
    return without_none(
        {
            "mode": mode,
            "return_citations": optional_bool(return_citations, "return_citations"),
            "max_search_results": optional_int(
                max_search_results, "max_search_results", minimum=1, maximum=50
            ),
            "from_date": optional_date(from_date, "from_date"),
            "to_date": optional_date(to_date, "to_date"),
            "sources": sources,
        }
    )


def json_object_text_format():
    """Ask a Responses request to return a JSON object."""
    return {"format": {"type": "json_object"}}


def json_schema_text_format(name, schema, *, description=None, strict=None):
    """Ask a Responses request to follow a JSON schema."""
    json_schema = {
        "name": function_name(name),
        "schema": require_dict(schema, "schema"),
    }
    if description is not None:
        json_schema["description"] = optional_text(description, "description")
    if strict is not None:
        json_schema["strict"] = optional_bool(strict, "strict")
    return {"format": {"type": "json_schema", "json_schema": json_schema}}


def chat_json_object_response_format():
    return {"type": "json_object"}


def chat_json_schema_response_format(name, schema, *, description=None, strict=None):
    payload = {
        "name": function_name(name),
        "schema": require_dict(schema, "schema"),
    }
    if description is not None:
        payload["description"] = optional_text(description, "description")
    if strict is not None:
        payload["strict"] = optional_bool(strict, "strict")
    return {"type": "json_schema", "json_schema": payload}


def storage_options(filename, *, expires_after_seconds=None, public_url=None):
    """Where image and video bytes should be stored after generation."""
    return without_none(
        {
            "filename": require_text(filename, "filename", max_length=200),
            "expires_after": optional_int(
                expires_after_seconds, "expires_after_seconds", minimum=1, maximum=60 * 60 * 24 * 30
            ),
            "public_url": public_url,
        }
    )


def text_to_speech_delta_message(text):
    from services.grok.constants import MAX_TTS_CHARACTERS

    return {
        "type": "text.delta",
        "delta": require_text(text, "text", max_length=MAX_TTS_CHARACTERS),
    }


def text_to_speech_done_message():
    return {"type": "text.done"}


def speech_to_text_finalize_message(*, channel=None):
    return without_none(
        {
            "type": "finalize",
            "channel": optional_int(channel, "channel", minimum=0, maximum=7),
        }
    )


def speech_to_text_audio_done_message():
    return {"type": "audio.done"}


def realtime_session_update_message(session):
    return {"type": "session.update", "session": require_dict(session, "session")}


def realtime_append_audio_message(audio_base64):
    return {
        "type": "input_audio_buffer.append",
        "audio": require_text(audio_base64, "audio", max_length=8_000_000),
    }


def realtime_commit_audio_message():
    return {"type": "input_audio_buffer.commit"}


def realtime_clear_audio_message():
    return {"type": "input_audio_buffer.clear"}


def realtime_create_response_message():
    return {"type": "response.create"}


def realtime_cancel_response_message():
    return {"type": "response.cancel"}


def realtime_conversation_item_message(item):
    return {"type": "conversation.item.create", "item": require_dict(item, "item")}


def _domains(values, name):
    from services.grok.errors import GrokUsageError

    if values is None:
        return None
    if not isinstance(values, list) or not values or len(values) > 5:
        raise GrokUsageError(f"{name} must contain 1 to 5 bare domains.")
    cleaned = []
    for domain in values:
        text = require_text(domain, name, max_length=253)
        if "://" in text or "/" in text or " " in text:
            raise GrokUsageError(f"{name} entries must be bare domains, not URLs.")
        cleaned.append(text.lower())
    return cleaned


def _handles(values, name):
    from services.grok.errors import GrokUsageError

    if values is None:
        return None
    if not isinstance(values, list) or not values or len(values) > 10:
        raise GrokUsageError(f"{name} must contain 1 to 10 handles.")
    cleaned = []
    for handle in values:
        text = require_text(handle, name, max_length=32).lstrip("@")
        if not text.replace("_", "").isalnum():
            raise GrokUsageError(f"{name} entries must be X handles.")
        cleaned.append(text)
    return cleaned
