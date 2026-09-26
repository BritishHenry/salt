"""Legacy completion endpoints.

Reasoning models do not support /v1/completions or /v1/complete.
Prefer ResponsesResource.create_model_response for new code.
"""

from __future__ import annotations

from services.grok.errors import GrokUsageError
from services.grok.resources.base import Resource
from services.grok.safety import (
    optional_bool,
    optional_dict,
    optional_identifier,
    optional_int,
    optional_number,
    optional_string_list,
    optional_text,
    require_model_name,
    require_non_empty_list,
    require_text,
    without_none,
)


class LegacyResource(Resource):
    def create_legacy_anthropic_text_completion(
        self,
        *,
        model,
        prompt,
        max_tokens_to_sample,
        stop_sequences=None,
        temperature=None,
        top_k=None,
        top_p=None,
        metadata=None,
        timeout_seconds=None,
    ):
        """POST /v1/complete. Anthropic-compatible and not for reasoning models."""
        body = without_none(
            {
                "model": require_model_name(model),
                "prompt": require_text(prompt, "prompt", max_length=2_000_000),
                "max_tokens_to_sample": optional_int(
                    max_tokens_to_sample, "max_tokens_to_sample", minimum=1, maximum=200_000
                ),
                "stop_sequences": optional_string_list(
                    stop_sequences, "stop_sequences", max_items=8, max_item_length=256
                ),
                "temperature": optional_number(temperature, "temperature", minimum=0, maximum=2),
                "top_k": optional_int(top_k, "top_k", minimum=1, maximum=1000),
                "top_p": optional_number(top_p, "top_p", minimum=0, maximum=1),
                "metadata": optional_dict(metadata, "metadata"),
            }
        )
        if body.get("max_tokens_to_sample") is None:
            raise GrokUsageError("max_tokens_to_sample is required.")
        return self._json("POST", "/v1/complete", body=body, timeout_seconds=timeout_seconds)

    def create_legacy_prompt_completion(
        self,
        *,
        model,
        prompt,
        max_tokens=None,
        temperature=None,
        top_p=None,
        n=None,
        stop=None,
        suffix=None,
        user=None,
        timeout_seconds=None,
    ):
        """POST /v1/completions. Replaced by chat completions and the Responses API."""
        if isinstance(prompt, str):
            prompt_value = require_text(prompt, "prompt", max_length=2_000_000)
        elif isinstance(prompt, list) and prompt:
            prompt_value = prompt
        else:
            raise GrokUsageError("prompt must be a string or a non-empty list.")
        body = without_none(
            {
                "model": require_model_name(model),
                "prompt": prompt_value,
                "max_tokens": optional_int(max_tokens, "max_tokens", minimum=1, maximum=200_000),
                "temperature": optional_number(temperature, "temperature", minimum=0, maximum=2),
                "top_p": optional_number(top_p, "top_p", minimum=0, maximum=1),
                "n": optional_int(n, "n", minimum=1, maximum=8),
                "stop": optional_string_list(stop, "stop", max_items=4, max_item_length=256),
                "suffix": require_text(suffix, "suffix") if suffix is not None else None,
                "user": optional_identifier(user, "user"),
            }
        )
        return self._json("POST", "/v1/completions", body=body, timeout_seconds=timeout_seconds)

    def create_anthropic_compatible_message(
        self,
        *,
        model,
        messages,
        max_tokens,
        system=None,
        stop_sequences=None,
        temperature=None,
        top_k=None,
        top_p=None,
        tool_choice=None,
        tools=None,
        metadata=None,
        timeout_seconds=None,
    ):
        """POST /v1/messages. Anthropic-compatible messages."""
        body = without_none(
            {
                "model": require_model_name(model),
                "messages": require_non_empty_list(messages, "messages"),
                "max_tokens": optional_int(max_tokens, "max_tokens", minimum=1, maximum=200_000),
                "system": system if isinstance(system, (str, list)) else optional_text(system, "system"),
                "stop_sequences": optional_string_list(
                    stop_sequences, "stop_sequences", max_items=8, max_item_length=256
                ),
                "temperature": optional_number(temperature, "temperature", minimum=0, maximum=2),
                "top_k": optional_int(top_k, "top_k", minimum=1, maximum=1000),
                "top_p": optional_number(top_p, "top_p", minimum=0, maximum=1),
                "tool_choice": optional_dict(tool_choice, "tool_choice")
                if isinstance(tool_choice, dict)
                else tool_choice,
                "tools": tools,
                "metadata": optional_dict(metadata, "metadata"),
            }
        )
        if body.get("max_tokens") is None:
            raise GrokUsageError("max_tokens is required.")
        if system is not None and not isinstance(system, (str, list)):
            raise GrokUsageError("system must be a string or a list of content blocks.")
        return self._json("POST", "/v1/messages", body=body, timeout_seconds=timeout_seconds)
