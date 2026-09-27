"""Jacob as a function tool Salt can call."""

from services.grok import responses_function_tool

from agents.jacob.pricing import PricingError, price_item
from listings.services import ListingError, item_for_user

JACOB_DESCRIPTION = (
    "Recommend one list price in GBP from comparable listings on Vinted, Depop, "
    "and eBay, including condition and size. Pass the seller's item_id. "
    "Never send user_id."
)

JACOB_PARAMETERS = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["price"],
            "description": "price searches comparable listings and stores one list price.",
        },
        "item_id": {
            "type": "integer",
            "description": "The seller's item to price. Never send user_id.",
        },
    },
    "required": ["action", "item_id"],
    "additionalProperties": False,
}


def jacob_schema():
    return responses_function_tool(
        "jacob",
        JACOB_PARAMETERS,
        description=JACOB_DESCRIPTION,
    )


def handle_jacob(user, arguments, *, grok=None, browser=None):
    """Price one item. A blank item or a failed quote is a failed result."""
    item_id = _item_id(arguments.get("item_id"))
    if arguments.get("action") != "price":
        return _failed(item_id, "action must be price.")
    if item_id is None:
        return _failed(None, "item_id must be an integer.")
    try:
        item = item_for_user(user, item_id)
    except ListingError:
        return _failed(item_id, "That item was not found.")
    try:
        quote = price_item(item, browser=browser, grok=grok)
    except PricingError as exc:
        return _failed(item.pk, exc.message)
    item.refresh_from_db()
    if quote.status != quote.Status.READY or quote.price_minor is None:
        message = (quote.error or "").strip() or "No list price was found."
        return _failed(item.pk, message)
    pounds = _pounds(quote.price_minor)
    return {
        "status": "ready",
        "item_id": item.pk,
        "price_minor": quote.price_minor,
        "currency": quote.currency or "gbp",
        "rationale": quote.rationale or "",
        "message": f"List this at {pounds}. {quote.rationale or ''}".strip(),
    }


def present_jacob(result, arguments):
    """Return the price result Salt can say back."""
    password = arguments.get("password") if isinstance(arguments, dict) else None
    status = result.get("status") if isinstance(result, dict) else None
    if status not in {"ready", "failed"}:
        status = "failed"
    message = _plain(result.get("message") if isinstance(result, dict) else "", password)
    if not message:
        message = "That tool could not finish. Ask the seller to try again."
    item_id = result.get("item_id") if isinstance(result, dict) else None
    if type(item_id) is not int:
        item_id = None
    price_minor = result.get("price_minor") if isinstance(result, dict) else None
    if type(price_minor) is not int:
        price_minor = None
    currency = _plain(result.get("currency") if isinstance(result, dict) else "", password) or "gbp"
    rationale = _plain(result.get("rationale") if isinstance(result, dict) else "", password)
    return {
        "status": status,
        "item_id": item_id,
        "price_minor": price_minor,
        "currency": currency,
        "rationale": rationale,
        "message": message,
    }


def _item_id(value):
    if type(value) is int and value >= 1:
        return value
    return None


def _failed(item_id, message):
    return {
        "status": "failed",
        "item_id": item_id,
        "price_minor": None,
        "currency": "gbp",
        "rationale": "",
        "message": message,
    }


def _pounds(price_minor):
    pounds = price_minor // 100
    pence = price_minor % 100
    return f"£{pounds}.{pence:02d}"


def _plain(value, password):
    if not isinstance(value, str):
        return ""
    if isinstance(password, str) and len(password) >= 4 and password in value:
        value = value.replace(password, "")
    return " ".join(value.split())
