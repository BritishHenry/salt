"""Callable chat with Salt.

Salt streams a reply from grok-4.7 at low reasoning effort and emits the
thinking trace as it arrives. She can call the specialist tools, then say
what they returned.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from services.grok import GrokClient
from services.grok.errors import GrokSafetyError, GrokUsageError
from services.grok.parsing import (
    extract_completed_output_text,
    extract_completed_reasoning,
    extract_function_call,
    extract_reasoning_delta,
    extract_text_delta,
)
from services.grok.safety import require_text

from agents.salt.tools import specialist_tools
from agents.tools import call_tool

MODEL = "grok-4.7"
REASONING_EFFORT = "low"
MAX_MESSAGES = 40
MAX_MESSAGE_CHARS = 8_000
MAX_TOOL_ROUNDS = 4

INSTRUCTIONS = """You are Salt, the seller's chief of staff for a second-hand clothes shop on Vinted, Depop, and eBay.

Talk with the seller directly. Understand the request, say what is going on, and report progress or a problem. Ask before spending money, changing a live listing, or accepting a buyer's offer.

You can call these specialists. Use their results. Do not invent sales, prices, offers, or login state. If you do not know, say what is missing.
- Willow connects and refreshes Vinted, Depop, and eBay sessions. Never invent a password or repeat one.
- Bobby turns a confirmed item and its photos into draft listings for Vinted, Depop, and eBay.
- Jacob recommends one list price from comparable listings.
- Buttons reads a photo into a draft item, then confirms or corrects the details.
- Maggie publishes approved listings and keeps marketplace copies in sync.
- Steve answers buyers and haggles within the seller's limits. Unusual requests come back to you.

The seller is already signed in. Never send user_id. Pass item_id for the seller's item.
"""


class SaltChatError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass(frozen=True)
class SaltEvent:
    """One streamed fragment. kind is "thinking" or "message"."""

    kind: str
    delta: str


class SaltAgent:
    """Primary seller chat. Call chat() and iterate the events."""

    def __init__(self, client=None):
        self._client = client

    def chat(
        self,
        messages,
        *,
        user=None,
        image_url=None,
        safety_identifier=None,
        grok=None,
        browser=None,
    ):
        """Yield thinking deltas, tool progress, then the reply.

        Up to four model turns. The last turn speaks instead of calling a tool.
        The seller on user is injected into every tool call.
        """
        prepared = prepare_messages(messages)
        if image_url:
            prepared[-1] = _with_image(prepared[-1], image_url)
        client = self._client if self._client is not None else GrokClient.from_environment()
        tool_client = grok if grok is not None else client
        conversation = list(prepared)
        instructions = INSTRUCTIONS
        if image_url:
            instructions += (
                "\n\nThe seller attached a photo on this turn. "
                "When you call buttons, pass that same image_url. Do not invent a different photo."
            )
        for round_index in range(MAX_TOOL_ROUNDS):
            tool_choice = "none" if round_index == MAX_TOOL_ROUNDS - 1 else "auto"
            calls = []
            message_parts = []
            saw_thinking = False
            saw_message = False
            stream = client.responses.stream_model_response_events(
                model=MODEL,
                input=conversation,
                instructions=instructions,
                tools=specialist_tools(),
                tool_choice=tool_choice,
                reasoning_effort=REASONING_EFFORT,
                safety_identifier=safety_identifier,
                store_response_on_xai_servers=False,
            )
            with stream as events:
                for event in events:
                    thinking = extract_reasoning_delta(event)
                    if thinking:
                        saw_thinking = True
                        yield SaltEvent("thinking", thinking)
                        continue
                    if not saw_thinking:
                        completed_thinking = extract_completed_reasoning(event)
                        if completed_thinking:
                            saw_thinking = True
                            yield SaltEvent("thinking", completed_thinking)
                            continue
                    call = extract_function_call(event)
                    if call is not None:
                        if not call["call_id"]:
                            call["call_id"] = f"call_{round_index}_{len(calls)}"
                        calls.append(call)
                        continue
                    message = extract_text_delta(event)
                    if message:
                        saw_message = True
                        message_parts.append(message)
                        continue
                    if not saw_message:
                        completed_message = extract_completed_output_text(event)
                        if completed_message:
                            saw_message = True
                            message_parts.append(completed_message)
            if calls and tool_choice != "none":
                for call in calls:
                    yield SaltEvent("thinking", _progress(call["name"]))
                    arguments = _arguments(call, image_url)
                    result = call_tool(
                        call["name"],
                        user,
                        arguments,
                        grok=tool_client,
                        browser=browser,
                    )
                    conversation.append(
                        {
                            "type": "function_call",
                            "call_id": call["call_id"],
                            "name": call["name"],
                            "arguments": call["arguments"],
                        }
                    )
                    conversation.append(
                        {
                            "type": "function_call_output",
                            "call_id": call["call_id"],
                            "output": json.dumps(result),
                        }
                    )
                continue
            for part in message_parts:
                yield SaltEvent("message", part)
            return
        return


def _with_image(message, image_url):
    return {
        "role": "user",
        "content": [
            {"type": "input_text", "text": message["content"]},
            {"type": "input_image", "image_url": image_url},
        ],
    }


def _progress(name):
    label = name[:1].upper() + name[1:] if name else "a specialist"
    return f"Asking {label}."


def _arguments(call, image_url):
    try:
        arguments = json.loads(call["arguments"]) if call["arguments"] else {}
    except json.JSONDecodeError:
        arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}
    arguments.pop("user_id", None)
    if (
        call["name"] == "buttons"
        and image_url
        and not arguments.get("image_url")
        and not arguments.get("image_file_id")
        and arguments.get("action") in {"read_photo", "add_photo", None}
    ):
        arguments["image_url"] = image_url
    return arguments


def prepare_messages(messages):
    """Return Responses API input, or raise SaltChatError."""
    if not isinstance(messages, list) or not messages:
        raise SaltChatError("messages must be a non-empty list.")
    if len(messages) > MAX_MESSAGES:
        raise SaltChatError(f"messages must contain at most {MAX_MESSAGES} items.")
    prepared = []
    for message in messages:
        if not isinstance(message, dict):
            raise SaltChatError("Each message must be an object with role and content.")
        role = message.get("role")
        if role not in {"user", "assistant"}:
            raise SaltChatError("Each message role must be user or assistant.")
        try:
            content = require_text(
                message.get("content"),
                "content",
                max_length=MAX_MESSAGE_CHARS,
            )
        except (GrokUsageError, GrokSafetyError) as exc:
            raise SaltChatError(str(exc)) from exc
        prepared.append({"role": role, "content": content})
    if prepared[-1]["role"] != "user":
        raise SaltChatError("The last message must be from the user.")
    return prepared
