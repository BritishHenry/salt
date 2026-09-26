"""Callable chat with Salt.

Salt streams a reply from grok-4.7 at low reasoning effort and emits the
thinking trace as it arrives. Specialist tools are attached, but tool_choice
is none so this turn only responds.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.grok import GrokClient
from services.grok.errors import GrokSafetyError, GrokUsageError
from services.grok.parsing import (
    extract_completed_output_text,
    extract_completed_reasoning,
    extract_reasoning_delta,
    extract_text_delta,
)
from services.grok.safety import require_text

from agents.salt.tools import specialist_tools

MODEL = "grok-4.7"
REASONING_EFFORT = "low"
MAX_MESSAGES = 40
MAX_MESSAGE_CHARS = 8_000

INSTRUCTIONS = """You are Salt, the seller's chief of staff for a second-hand clothes shop on Vinted, Depop, and eBay.

Talk with the seller directly. Understand the request, say what is going on, and report progress or a problem. Ask before spending money, changing a live listing, or accepting a buyer's offer.

You work with five specialists. Their tools are attached for later turns. In this conversation answer the seller yourself and do not call them:
- Willow connects and refreshes Vinted, Depop, and eBay sessions.
- Bobby turns a confirmed item and its photos into draft listings for Vinted, Depop, and eBay.
- Jacob recommends one list price from comparable listings.
- Maggie publishes approved listings and keeps marketplace copies in sync.
- Steve answers buyers and haggles within the seller's limits.

Do not invent sales, prices, offers, or login state. If you do not know, say what is missing.
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

    def chat(self, messages, *, safety_identifier=None):
        """Yield thinking deltas, then the reply, as grok-4.7 streams them.

        Specialist tools are sent with tool_choice "none", so the model
        responds instead of calling Willow, Bobby, Jacob, Maggie, or Steve.
        """
        prepared = prepare_messages(messages)
        client = self._client if self._client is not None else GrokClient.from_environment()
        stream = client.responses.stream_model_response_events(
            model=MODEL,
            input=prepared,
            instructions=INSTRUCTIONS,
            tools=specialist_tools(),
            tool_choice="none",
            reasoning_effort=REASONING_EFFORT,
            safety_identifier=safety_identifier,
            store_response_on_xai_servers=False,
        )
        saw_thinking = False
        saw_message = False
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
                message = extract_text_delta(event)
                if message:
                    saw_message = True
                    yield SaltEvent("message", message)
                    continue
                if not saw_message:
                    completed_message = extract_completed_output_text(event)
                    if completed_message:
                        saw_message = True
                        yield SaltEvent("message", completed_message)


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
