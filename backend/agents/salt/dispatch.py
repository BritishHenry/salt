"""Dispatch the tools Salt's model is allowed to call."""

from agents.buttons.errors import ButtonsError
from agents.buttons.service import handle
from agents.buttons.tool import BUTTONS_TOOL

TOOLS = [BUTTONS_TOOL]


class DispatchError(Exception):
    """Salt asked for a tool she does not have."""


def dispatch(name, arguments, user, *, grok=None):
    """Run a tool call. The authenticated user is injected here, never taken from the model."""
    if name != "buttons":
        raise DispatchError(f"Unknown tool {name!r}.")
    if not isinstance(arguments, dict):
        raise ButtonsError("Tool arguments must be an object.")
    if grok is None:
        from services.grok import GrokClient

        grok = GrokClient.from_environment()
    cleaned = {key: value for key, value in arguments.items() if key != "user_id"}
    return handle(user, cleaned, grok=grok)
