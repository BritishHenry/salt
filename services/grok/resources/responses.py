"""Responses API. This is the preferred way to talk to Grok text models."""

from __future__ import annotations

from services.grok.constants import MAX_PAGINATION_PAGES, SERVICE_TIERS
from services.grok.errors import GrokUsageError
from services.grok.resources.base import Resource
from services.grok.safety import (
    merge_additional_fields,
    optional_bool,
    optional_choice,
    optional_dict,
    optional_identifier,
    optional_int,
    optional_number,
    optional_text,
    optional_token,
    require_model_name,
    require_resource_id,
    require_text,
    without_none,
)

_REASONING_EFFORTS = frozenset({"low", "medium", "high", "xhigh"})


class ResponsesResource(Resource):
    def create_model_response(
        self,
        *,
        model,
        input,
        instructions=None,
        max_output_tokens=None,
        temperature=None,
        top_p=None,
        top_k=None,
        min_p=None,
        previous_response_id=None,
        store_response_on_xai_servers=False,
        tools=None,
        tool_choice=None,
        parallel_tool_calls=None,
        reasoning_effort=None,
        include=None,
        text=None,
        metadata=None,
        safety_identifier=None,
        user=None,
        service_tier=None,
        prompt_cache_key=None,
        max_turns=None,
        truncation=None,
        background=None,
        search_parameters=None,
        logprobs=None,
        top_logprobs=None,
        additional_fields=None,
        timeout_seconds=None,
    ):
        """POST /v1/responses.

        Responses are not stored on xAI unless store_response_on_xai_servers is true.
        Stored responses are kept for 30 days and can be continued or deleted.
        """
        if background and not store_response_on_xai_servers:
            raise GrokUsageError(
                "background=True requires store_response_on_xai_servers=True. "
                "xAI cannot resume a response it was told not to store."
            )
        body = _response_body(
            model=model,
            input=input,
            instructions=instructions,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            min_p=min_p,
            previous_response_id=previous_response_id,
            store_response_on_xai_servers=store_response_on_xai_servers,
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
            reasoning_effort=reasoning_effort,
            include=include,
            text=text,
            metadata=metadata,
            safety_identifier=safety_identifier,
            user=user,
            service_tier=service_tier,
            prompt_cache_key=prompt_cache_key,
            max_turns=max_turns,
            truncation=truncation,
            background=background,
            search_parameters=search_parameters,
            logprobs=logprobs,
            top_logprobs=top_logprobs,
            additional_fields=additional_fields,
            stream=False,
        )
        return self._json("POST", "/v1/responses", body=body, timeout_seconds=timeout_seconds)

    def stream_model_response_events(self, **kwargs):
        """POST /v1/responses with stream=true. Iterate the returned stream.

        The response is not stored unless store_response_on_xai_servers is true.
        """
        timeout_seconds = kwargs.pop("timeout_seconds", None)
        body = _response_body(stream=True, **kwargs)
        return self._http.send(
            "POST",
            "/v1/responses",
            json_body=body,
            stream=True,
            timeout_seconds=timeout_seconds,
        )

    def compact_response_input(self, *, model, input, timeout_seconds=None):
        """POST /v1/responses/compact. Shorten a long input window."""
        body = {
            "model": require_model_name(model),
            "input": _require_model_input(input),
        }
        return self._json("POST", "/v1/responses/compact", body=body, timeout_seconds=timeout_seconds)

    def retrieve_stored_model_response(self, response_id, *, timeout_seconds=None):
        """GET /v1/responses/{response_id}."""
        return self._json(
            "GET",
            f"/v1/responses/{require_resource_id(response_id, 'response_id')}",
            timeout_seconds=timeout_seconds,
        )

    def delete_stored_model_response(self, response_id, *, timeout_seconds=None):
        """DELETE /v1/responses/{response_id}."""
        return self._json(
            "DELETE",
            f"/v1/responses/{require_resource_id(response_id, 'response_id')}",
            timeout_seconds=timeout_seconds,
        )

    def list_stored_response_input_items(
        self,
        response_id,
        *,
        limit=None,
        order=None,
        after=None,
        timeout_seconds=None,
    ):
        """GET /v1/responses/{response_id}/input_items."""
        query = without_none(
            {
                "limit": optional_int(limit, "limit", minimum=1, maximum=100),
                "order": optional_token(order, "order"),
                "after": optional_identifier(after, "after"),
            }
        )
        return self._json(
            "GET",
            f"/v1/responses/{require_resource_id(response_id, 'response_id')}/input_items",
            query=query,
            timeout_seconds=timeout_seconds,
        )

    def list_all_stored_response_input_items(
        self,
        response_id,
        *,
        order=None,
        limit=None,
        max_pages=MAX_PAGINATION_PAGES,
        timeout_seconds=None,
    ):
        """Follow input-item pages until has_more is false."""

        def fetch(cursor):
            return self.list_stored_response_input_items(
                response_id,
                limit=limit,
                order=order,
                after=cursor,
                timeout_seconds=timeout_seconds,
            )

        return self._collect_cursor_pages(fetch, items_key="data", max_pages=max_pages)


def _response_body(
    *,
    model,
    input,
    instructions=None,
    max_output_tokens=None,
    temperature=None,
    top_p=None,
    top_k=None,
    min_p=None,
    previous_response_id=None,
    store_response_on_xai_servers=False,
    tools=None,
    tool_choice=None,
    parallel_tool_calls=None,
    reasoning_effort=None,
    include=None,
    text=None,
    metadata=None,
    safety_identifier=None,
    user=None,
    service_tier=None,
    prompt_cache_key=None,
    max_turns=None,
    truncation=None,
    background=None,
    search_parameters=None,
    logprobs=None,
    top_logprobs=None,
    additional_fields=None,
    stream=False,
):
    if background and not store_response_on_xai_servers:
        raise GrokUsageError(
            "background=True requires store_response_on_xai_servers=True. "
            "xAI cannot resume a response it was told not to store."
        )
    body = without_none(
        {
            "model": require_model_name(model),
            "input": _require_model_input(input),
            "instructions": optional_text(instructions, "instructions"),
            "max_output_tokens": optional_int(
                max_output_tokens, "max_output_tokens", minimum=1, maximum=200_000
            ),
            "temperature": optional_number(temperature, "temperature", minimum=0, maximum=2),
            "top_p": optional_number(top_p, "top_p", minimum=0, maximum=1),
            "top_k": optional_int(top_k, "top_k", minimum=1, maximum=1000),
            "min_p": optional_number(min_p, "min_p", minimum=0, maximum=1),
            "previous_response_id": _optional_response_id(previous_response_id),
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": optional_bool(parallel_tool_calls, "parallel_tool_calls"),
            "reasoning": _reasoning_setting(reasoning_effort),
            "include": include,
            "text": optional_dict(text, "text"),
            "metadata": optional_dict(metadata, "metadata"),
            "safety_identifier": optional_identifier(safety_identifier, "safety_identifier"),
            "user": optional_identifier(user, "user"),
            "service_tier": optional_choice(service_tier, "service_tier", SERVICE_TIERS),
            "prompt_cache_key": optional_identifier(prompt_cache_key, "prompt_cache_key"),
            "max_turns": optional_int(max_turns, "max_turns", minimum=1, maximum=100),
            "truncation": optional_token(truncation, "truncation"),
            "background": optional_bool(background, "background"),
            "search_parameters": optional_dict(search_parameters, "search_parameters"),
            "logprobs": optional_bool(logprobs, "logprobs"),
            "top_logprobs": optional_int(top_logprobs, "top_logprobs", minimum=0, maximum=20),
            "stream": True if stream else None,
        }
    )
    body = merge_additional_fields(body, additional_fields)
    body["store"] = bool(store_response_on_xai_servers)
    body.pop("stream", None)
    if stream:
        body["stream"] = True
    return body


def _reasoning_setting(effort):
    """Map reasoning_effort onto the Responses API object, {"effort": "..."}."""
    token = optional_token(effort, "reasoning_effort")
    if token is None:
        return None
    if token not in _REASONING_EFFORTS:
        raise GrokUsageError("reasoning_effort must be low, medium, high, or xhigh.")
    return {"effort": token}


def _require_model_input(value):
    if isinstance(value, str):
        return require_text(value, "input", max_length=2_000_000)
    if isinstance(value, list) and value:
        return value
    raise GrokUsageError("input must be a non-empty string or a list of items.")


def _optional_response_id(value):
    if value is None:
        return None
    return require_resource_id(value, "previous_response_id")
