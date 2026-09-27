"""Bobby as a function tool Salt can call."""

from services.grok import responses_function_tool

from agents.bobby.draft import draft_listings

BOBBY_DESCRIPTION = (
    "Write draft listing copy for a confirmed item: title, description, "
    "category, and attributes, adapted for Vinted, Depop, or eBay."
)

BOBBY_PARAMETERS = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["draft"],
            "description": "draft writes title, description, category, and attributes.",
        },
        "item_id": {
            "type": "integer",
            "description": "The seller's item to draft. Never send user_id.",
        },
        "marketplaces": {
            "type": "array",
            "items": {"type": "string", "enum": ["vinted", "depop", "ebay"]},
            "description": "Marketplaces to draft. Omit to draft Vinted, Depop, and eBay.",
        },
    },
    "required": ["action", "item_id"],
    "additionalProperties": False,
}

_STATUSES = frozenset({"ready", "needs_details", "failed"})


def bobby_schema():
    return responses_function_tool(
        "bobby",
        BOBBY_PARAMETERS,
        description=BOBBY_DESCRIPTION,
    )


def handle_bobby(user, arguments, *, grok=None, browser=None):
    """Draft listings for one item. Invalid arguments come back as a failed result."""
    return draft_listings(user, arguments, grok=grok)


def present_bobby(result, arguments):
    """Return the draft result Salt can say back."""
    password = arguments.get("password") if isinstance(arguments, dict) else None
    status = result.get("status")
    if status not in _STATUSES:
        status = "failed"
    message = _plain(result.get("message"), password)
    if not message:
        message = "That tool could not finish. Ask the seller to try again."
    item_id = result.get("item_id")
    if type(item_id) is not int:
        item_id = None
    listings = []
    raw_listings = result.get("listings")
    if isinstance(raw_listings, list):
        for row in raw_listings:
            if not isinstance(row, dict):
                continue
            listings.append(
                {
                    "marketplace": _plain(row.get("marketplace"), password),
                    "status": _plain(row.get("status"), password),
                    "title": _plain(row.get("title"), password),
                    "description": _plain(row.get("description"), password),
                }
            )
    return {
        "status": status,
        "item_id": item_id,
        "message": message,
        "listings": listings,
    }


def _plain(value, password):
    if not isinstance(value, str):
        return ""
    if isinstance(password, str) and len(password) >= 4 and password in value:
        value = value.replace(password, "")
    return " ".join(value.split())
