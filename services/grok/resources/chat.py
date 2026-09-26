"""Chat Completions API, including deferred completions."""

from __future__ import annotations

from services.grok.constants import SERVICE_TIERS
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
    optional_string_list,
    optional_token,
    require_model_name,
    require_non_empty_list,
    require_resource_id,
    without_none,
)


class ChatResource(Resource):
    def create_chat_completion(
        self,
        *,
        model,
        messages,
        deferred=None,
        frequency_penalty=None,
        logit_bias=None,
        logprobs=None,
        max_completion_tokens=None,
        max_tokens=None,
        n=None,
        parallel_tool_calls=None,
        presence_penalty=None,
        prompt_cache_key=None,
        reasoning_effort=None,
        response_format=None,
        safety_identifier=None,
        search_parameters=None,
        seed=None,
        service_tier=None,
        stop=None,
        temperature=None,
        tool_choice=None,
        tools=None,
        top_logprobs=None,
        top_p=None,
        user=None,
        web_search_options=None,
        additional_fields=None,
        timeout_seconds=None,
    ):
        """POST /v1/chat/completions.

        Set deferred=True to receive a request id and poll with
        fetch_deferred_chat_completion. Streaming has its own method.
        """
        body = _chat_body(
            model=model,
            messages=messages,
            deferred=deferred,
            frequency_penalty=frequency_penalty,
            logit_bias=logit_bias,
            logprobs=logprobs,
            max_completion_tokens=max_completion_tokens,
            max_tokens=max_tokens,
            n=n,
            parallel_tool_calls=parallel_tool_calls,
            presence_penalty=presence_penalty,
            prompt_cache_key=prompt_cache_key,
            reasoning_effort=reasoning_effort,
            response_format=response_format,
            safety_identifier=safety_identifier,
            search_parameters=search_parameters,
            seed=seed,
            service_tier=service_tier,
            stop=stop,
            temperature=temperature,
            tool_choice=tool_choice,
            tools=tools,
            top_logprobs=top_logprobs,
            top_p=top_p,
            user=user,
            web_search_options=web_search_options,
            additional_fields=additional_fields,
        )
        return self._json("POST", "/v1/chat/completions", body=body, timeout_seconds=timeout_seconds)

    def stream_chat_completion(self, **kwargs):
        """POST /v1/chat/completions with stream=true. Yields server-sent events."""
        if kwargs.get("deferred"):
            raise GrokUsageError("A deferred chat completion cannot also stream.")
        timeout_seconds = kwargs.pop("timeout_seconds", None)
        body = _chat_body(**kwargs)
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}
        return self._http.send(
            "POST",
            "/v1/chat/completions",
            json_body=body,
            stream=True,
            timeout_seconds=timeout_seconds,
        )

    def fetch_deferred_chat_completion(self, request_id, *, timeout_seconds=None):
        """GET /v1/chat/deferred-completion/{request_id}.

        pending is true while the API still returns 202.
        """
        return self._deferred(
            "GET",
            f"/v1/chat/deferred-completion/{require_resource_id(request_id, 'request_id')}",
            timeout_seconds=timeout_seconds,
        )

    def wait_for_deferred_chat_completion(
        self,
        request_id,
        *,
        poll_interval_seconds=1.0,
        timeout_seconds=180.0,
        sleep=None,
        monotonic=None,
    ):
        """Poll a deferred chat completion until it finishes or the timeout elapses."""
        return self._wait_until_ready(
            lambda: self.fetch_deferred_chat_completion(request_id),
            request_id=request_id,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
            sleep=sleep,
            monotonic=monotonic,
            operation_name="Deferred chat completion",
            failed_message=lambda body: "Deferred chat completion failed.",
        )


def _chat_body(
    *,
    model,
    messages,
    deferred=None,
    frequency_penalty=None,
    logit_bias=None,
    logprobs=None,
    max_completion_tokens=None,
    max_tokens=None,
    n=None,
    parallel_tool_calls=None,
    presence_penalty=None,
    prompt_cache_key=None,
    reasoning_effort=None,
    response_format=None,
    safety_identifier=None,
    search_parameters=None,
    seed=None,
    service_tier=None,
    stop=None,
    temperature=None,
    tool_choice=None,
    tools=None,
    top_logprobs=None,
    top_p=None,
    user=None,
    web_search_options=None,
    additional_fields=None,
    stream=None,
):
    if stream:
        raise GrokUsageError("Use stream_chat_completion to stream a chat completion.")
    body = without_none(
        {
            "model": require_model_name(model),
            "messages": require_non_empty_list(messages, "messages"),
            "deferred": optional_bool(deferred, "deferred"),
            "frequency_penalty": optional_number(
                frequency_penalty, "frequency_penalty", minimum=-2, maximum=2
            ),
            "logit_bias": optional_dict(logit_bias, "logit_bias"),
            "logprobs": optional_bool(logprobs, "logprobs"),
            "max_completion_tokens": optional_int(
                max_completion_tokens, "max_completion_tokens", minimum=1, maximum=200_000
            ),
            "max_tokens": optional_int(max_tokens, "max_tokens", minimum=1, maximum=200_000),
            "n": optional_int(n, "n", minimum=1, maximum=8),
            "parallel_tool_calls": optional_bool(parallel_tool_calls, "parallel_tool_calls"),
            "presence_penalty": optional_number(
                presence_penalty, "presence_penalty", minimum=-2, maximum=2
            ),
            "prompt_cache_key": optional_identifier(prompt_cache_key, "prompt_cache_key"),
            "reasoning_effort": optional_token(reasoning_effort, "reasoning_effort"),
            "response_format": optional_dict(response_format, "response_format"),
            "safety_identifier": optional_identifier(safety_identifier, "safety_identifier"),
            "search_parameters": optional_dict(search_parameters, "search_parameters"),
            "seed": optional_int(seed, "seed", minimum=0, maximum=2**31 - 1),
            "service_tier": optional_choice(service_tier, "service_tier", SERVICE_TIERS),
            "stop": optional_string_list(stop, "stop", max_items=4, max_item_length=256),
            "temperature": optional_number(temperature, "temperature", minimum=0, maximum=2),
            "tool_choice": tool_choice,
            "tools": tools,
            "top_logprobs": optional_int(top_logprobs, "top_logprobs", minimum=0, maximum=20),
            "top_p": optional_number(top_p, "top_p", minimum=0, maximum=1),
            "user": optional_identifier(user, "user"),
            "web_search_options": optional_dict(web_search_options, "web_search_options"),
        }
    )
    body = merge_additional_fields(body, additional_fields)
    body.pop("stream", None)
    return body
