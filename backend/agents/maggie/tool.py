"""Maggie as a function tool Salt can call."""

from services.grok import responses_function_tool

from agents.maggie.publish import run

MAGGIE_DESCRIPTION = (
    "Publish an approved listing, check its status, apply an update, "
    "or remove the other marketplace listings when an item sells."
)

MAGGIE_PARAMETERS = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["publish", "status", "update", "delist"],
            "description": (
                "publish posts a draft. status reads a live listing. "
                "update pushes the saved copy. delist removes the other copies."
            ),
        },
        "item_id": {
            "type": "integer",
            "description": "The seller's item. Never send user_id.",
        },
        "marketplaces": {
            "type": "array",
            "items": {"type": "string", "enum": ["vinted", "depop", "ebay"]},
            "description": "Marketplaces to change. Omit to use every eligible listing.",
        },
    },
    "required": ["action", "item_id"],
    "additionalProperties": False,
}

_STATUSES = frozenset({"ready", "needs_login", "needs_details", "failed"})


def maggie_schema():
    return responses_function_tool(
        "maggie",
        MAGGIE_PARAMETERS,
        description=MAGGIE_DESCRIPTION,
    )


def handle_maggie(user, arguments, *, grok=None, browser=None):
    """Run one Maggie action. Invalid arguments come back as a failed result."""
    return run(user, arguments, client=browser)


def present_maggie(result, arguments):
    """Return the publish result Salt can say back."""
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
        if isinstance(arguments, dict) and type(arguments.get("item_id")) is int:
            candidate = arguments["item_id"]
            if candidate >= 1:
                item_id = candidate
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
                    "external_url": _plain(row.get("external_url"), password),
                    "message": _plain(row.get("message"), password),
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
