"""Small helpers for reading Grok JSON and server-sent events."""

from __future__ import annotations

import json
import re

from services.grok.errors import GrokApiError, GrokUsageError


class DeferredOperation:
    """One poll of an asynchronous Grok operation."""

    def __init__(self, *, pending, body, status_code):
        self.pending = pending
        self.body = body
        self.status_code = status_code

    def __repr__(self):
        return (
            f"DeferredOperation(pending={self.pending}, status_code={self.status_code})"
        )


def extract_output_text(response):
    """Return the assistant text from a Responses API payload."""
    if not isinstance(response, dict):
        return ""
    parts = []
    for item in response.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "output_text" and isinstance(item.get("text"), str):
            parts.append(item["text"])
        content = item.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    if block.get("type") in (None, "output_text", "text"):
                        parts.append(block["text"])
        elif isinstance(content, str) and item.get("type") == "message":
            parts.append(content)
    if parts:
        return "".join(parts)
    output_text = response.get("output_text")
    return output_text if isinstance(output_text, str) else ""


def extract_chat_message_text(response):
    """Return the assistant text from a chat completion payload."""
    if not isinstance(response, dict):
        return ""
    choices = response.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    return ""


_REASONING_DELTA_TYPES = frozenset(
    {
        "response.reasoning_text.delta",
        "response.reasoning_summary_text.delta",
    }
)
_REASONING_DONE_TYPES = frozenset(
    {
        "response.reasoning_text.done",
        "response.reasoning_summary_text.done",
    }
)


def extract_text_delta(event):
    """Return a text fragment from one streaming event, or an empty string."""
    if not isinstance(event, dict):
        return ""
    if event.get("type") in {"response.output_text.delta", "response.text.delta"}:
        delta = event.get("delta")
        return delta if isinstance(delta, str) else ""
    choices = event.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        delta = choices[0].get("delta") or {}
        if isinstance(delta, dict) and isinstance(delta.get("content"), str):
            return delta["content"]
    return ""


def extract_completed_output_text(event):
    """Return the full assistant text from a completed output event, or empty."""
    if not isinstance(event, dict):
        return ""
    if event.get("type") != "response.output_text.done":
        return ""
    text = event.get("text")
    return text if isinstance(text, str) else ""


def extract_reasoning_delta(event):
    """Return a thinking fragment from one streaming event, or an empty string."""
    if not isinstance(event, dict):
        return ""
    if event.get("type") in _REASONING_DELTA_TYPES:
        delta = event.get("delta")
        return delta if isinstance(delta, str) else ""
    choices = event.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        delta = choices[0].get("delta") or {}
        if isinstance(delta, dict):
            reasoning = delta.get("reasoning_content")
            if isinstance(reasoning, str):
                return reasoning
    return ""


def extract_completed_reasoning(event):
    """Return a finished thinking trace when the stream did not send deltas."""
    if not isinstance(event, dict):
        return ""
    if event.get("type") in _REASONING_DONE_TYPES:
        text = event.get("text")
        return text if isinstance(text, str) else ""
    if event.get("type") != "response.output_item.done":
        return ""
    item = event.get("item")
    if not isinstance(item, dict) or item.get("type") != "reasoning":
        return ""
    parts = []
    for block in item.get("summary") or []:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    for block in item.get("content") or []:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "".join(parts)


def parse_json_object(text):
    """Parse a model response that should be one JSON object."""
    if not isinstance(text, str) or not text.strip():
        raise GrokUsageError("The model returned no JSON text.")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        stripped = text.strip()
        fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.IGNORECASE)
        try:
            value = json.loads(fenced)
        except json.JSONDecodeError as exc:
            raise GrokApiError("The model did not return a JSON object.") from exc
    if not isinstance(value, dict):
        raise GrokApiError("The model returned JSON that is not an object.")
    return value


def video_failure_message(body):
    response = body.get("response") if isinstance(body, dict) else None
    error = response.get("error") if isinstance(response, dict) else None
    if isinstance(error, dict):
        message = error.get("message") or error.get("code")
        if message:
            return str(message)
    if isinstance(error, str) and error:
        return error
    return "Video generation failed."
