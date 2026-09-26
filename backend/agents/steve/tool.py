"""Steve as a function tool Salt can call."""

from services.grok import responses_function_tool

from agents.steve.service import run_steve

STEVE_DESCRIPTION = (
    "Check buyer messages, answer from the confirmed item details, or handle an offer. "
    "Below the seller's minimum, suggest that minimum and do not message the buyer. "
    "At or above the minimum, return needs_confirmation unless confirmed is true. "
    "Unusual requests come back to Salt. Never send user_id or a password."
)

STEVE_PARAMETERS = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["check", "reply", "offer"],
            "description": (
                "check reads the inbox. reply answers one conversation from the item facts. "
                "offer handles an amount in pence."
            ),
        },
        "thread_id": {
            "type": "integer",
            "description": "Buyer conversation. Required for reply and offer.",
        },
        "amount_minor": {
            "type": "integer",
            "description": "Offer in pence. Required for offer.",
        },
        "confirmed": {
            "type": "boolean",
            "description": "True only after the seller has agreed to accept this offer.",
        },
        "marketplaces": {
            "type": "array",
            "items": {"type": "string", "enum": ["vinted", "depop", "ebay"]},
            "description": "Inboxes to check. Omit to check every connected marketplace.",
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}

_STATUSES = frozenset(
    {"ready", "needs_login", "needs_confirmation", "escalate", "failed"}
)


def steve_schema():
    return responses_function_tool(
        "steve",
        STEVE_PARAMETERS,
        description=STEVE_DESCRIPTION,
    )


def handle_steve(user, arguments, *, grok=None, browser=None):
    """Check, reply, or handle an offer. Invalid arguments are a failed result."""
    return run_steve(user, arguments, grok=grok, browser=browser)


def present_steve(result, arguments):
    """Return the buyer-conversation result Salt can say back."""
    password = arguments.get("password") if isinstance(arguments, dict) else None
    status = result.get("status") if isinstance(result, dict) else None
    if status not in _STATUSES:
        status = "failed"
    message = _plain(result.get("message") if isinstance(result, dict) else "", password)
    if not message:
        message = "That tool could not finish. Ask the seller to try again."
    threads = []
    raw = result.get("threads") if isinstance(result, dict) else None
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            thread_id = row.get("thread_id")
            item_id = row.get("item_id")
            threads.append(
                {
                    "thread_id": thread_id if type(thread_id) is int else None,
                    "marketplace": _plain(row.get("marketplace"), password),
                    "buyer_name": _plain(row.get("buyer_name"), password),
                    "item_id": item_id if type(item_id) is int else None,
                    "message": _plain(row.get("message"), password),
                }
            )
    payload = {
        "status": status,
        "message": message,
        "threads": threads,
    }
    if isinstance(result, dict) and type(result.get("counter_minor")) is int:
        payload["counter_minor"] = result["counter_minor"]
    if isinstance(result, dict) and type(result.get("amount_minor")) is int:
        payload["amount_minor"] = result["amount_minor"]
    return payload


def _plain(value, password):
    if not isinstance(value, str):
        return ""
    if isinstance(password, str) and len(password) >= 4 and password in value:
        value = value.replace(password, "")
    return " ".join(value.split())
