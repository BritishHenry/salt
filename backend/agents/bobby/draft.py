"""Turn a confirmed item into draft marketplace listings."""

import base64
import json
import mimetypes

from django.db import transaction

from listings.models import Item, Listing
from listings.services import ListingError, create_listing, item_for_user, update_listing
from services.grok import GrokClient
from services.grok.builders import (
    chat_json_schema_response_format,
    image_reference,
    system_text_message,
)
from services.grok.errors import GrokError
from services.grok.parsing import extract_chat_message_text, parse_json_object

MODEL = "grok-4.7"
MAX_PHOTOS = 4

MARKETPLACES = ("vinted", "depop", "ebay")

LIMITS = {
    "vinted": {"title": 100, "description": 2000},
    "depop": {"title": 80, "description": 1000},
    "ebay": {"title": 80, "description": 4000},
}

LABELS = {
    "vinted": "Vinted",
    "depop": "Depop",
    "ebay": "eBay",
}

UNTOUCHABLE = frozenset(
    {
        Listing.Status.PUBLISHING,
        Listing.Status.LIVE,
        Listing.Status.PAUSED,
        Listing.Status.SOLD,
        Listing.Status.ENDED,
    }
)

ATTRIBUTE_FIELDS = (
    "department",
    "category",
    "garment_type",
    "brand",
    "colour",
    "colour_secondary",
    "size_label",
    "size_system",
    "condition",
    "material",
    "flaws",
)

REQUIRED_FIELDS = (
    ("category", "a category"),
    ("colour", "a colour"),
    ("size_label", "a size"),
    ("size_system", "a size system"),
    ("condition", "a condition"),
)

INSTRUCTIONS = """You write a title and a description for a second-hand clothes listing.
Use only the facts in the message. Do not invent a brand, size, condition, flaw, measurement, or price.
Do not put a price in the title.
When a brand is given, use that brand in the title or the description.
Write one title and one description for each marketplace in the request.
Stay inside the title and description character limits in the request.
"""

COPY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "listings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "marketplace": {
                        "type": "string",
                        "enum": list(MARKETPLACES),
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["marketplace", "title", "description"],
            },
        }
    },
    "required": ["listings"],
}

_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})


class DraftError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def draft_listings(user, arguments, *, grok=None):
    """Write draft listings for the seller's item.

    A missing item or bad arguments are a failed result. An item that still
    needs facts or a photo is needs_details. Grok is not called in either case.
    """
    if not isinstance(arguments, dict):
        return _failed(None, "Tool arguments must be an object.")
    item_id = _item_id(arguments.get("item_id"))
    if arguments.get("action") != "draft":
        return _failed(item_id, "action must be draft.")
    if item_id is None:
        return _failed(None, "item_id must be an integer.")
    try:
        marketplaces = _marketplaces(arguments.get("marketplaces", None))
    except DraftError as exc:
        return _failed(item_id, exc.message)
    try:
        item = item_for_user(user, item_id)
    except ListingError:
        return _failed(item_id, _missing_item_message(item_id))
    missing = _missing(item)
    if missing:
        return _result(item.pk, "needs_details", _needs_message(missing), [])
    writable, skipped = _split(item, marketplaces)
    if not writable:
        return _result(item.pk, "failed", _skipped_message(skipped), [_view(row) for _, row in skipped])
    try:
        payload = _ask(grok, item, [name for name, _row in writable])
        copies = _copies(payload, [name for name, _row in writable], item.brand)
        saved = _save_all(item, writable, copies)
    except DraftError as exc:
        return _failed(item.pk, exc.message)
    by_marketplace = {listing.marketplace: listing for listing in saved}
    listings = []
    written = []
    for marketplace in marketplaces:
        if marketplace in by_marketplace:
            listings.append(_view(by_marketplace[marketplace]))
            written.append(marketplace)
            continue
        existing = dict(skipped).get(marketplace)
        if existing is not None:
            listings.append(_view(existing))
    return _result(item.pk, "ready", _ready_message(written, skipped), listings)


def _ask(grok, item, marketplaces):
    client = grok if grok is not None else GrokClient.from_environment()
    try:
        response = client.chat.create_chat_completion(
            model=MODEL,
            messages=_messages(item, marketplaces),
            response_format=chat_json_schema_response_format(
                "listing_copy",
                COPY_SCHEMA,
                strict=True,
            ),
            temperature=0,
        )
        return parse_json_object(extract_chat_message_text(response))
    except (GrokError, json.JSONDecodeError) as exc:
        raise DraftError("I couldn't write listing copy for that item.") from exc


def _messages(item, marketplaces):
    content = [{"type": "text", "text": _prompt(item, marketplaces)}]
    for url in _photo_urls(item):
        content.append({"type": "image_url", "image_url": image_reference(url=url)})
    return [
        system_text_message(INSTRUCTIONS),
        {"role": "user", "content": content},
    ]


def _prompt(item, marketplaces):
    body = {
        "facts": _facts(item),
        "marketplaces": [
            {
                "marketplace": marketplace,
                "title_limit": LIMITS[marketplace]["title"],
                "description_limit": LIMITS[marketplace]["description"],
            }
            for marketplace in marketplaces
        ],
    }
    return "Write a title and a description for each marketplace.\n" + json.dumps(
        body, ensure_ascii=False
    )


def _facts(item):
    facts = _attributes(item)
    if not (item.brand or "").strip():
        facts = {**facts, "brand": "unbranded"}
    return facts


def _photo_urls(item):
    urls = []
    for photo in item.photos.order_by("position")[:MAX_PHOTOS]:
        urls.append(_data_url(photo))
    return urls


def _data_url(photo):
    mime, _encoding = mimetypes.guess_type(photo.image.name or "")
    if mime not in _IMAGE_TYPES:
        mime = "image/jpeg"
    with photo.image.open("rb") as handle:
        data = handle.read()
    if not data:
        raise DraftError("A photo on this item is empty.")
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _copies(payload, marketplaces, brand):
    rows = payload.get("listings") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise DraftError("I couldn't write listing copy for that item.")
    found = {}
    allowed = set(marketplaces)
    for row in rows:
        if not isinstance(row, dict):
            raise DraftError("I couldn't write listing copy for that item.")
        marketplace = row.get("marketplace")
        if marketplace not in allowed:
            continue
        if marketplace in found:
            raise DraftError("I couldn't write listing copy for that item.")
        found[marketplace] = {
            "title": _bounded(row.get("title"), LIMITS[marketplace]["title"], marketplace, "title"),
            "description": _bounded(
                row.get("description"),
                LIMITS[marketplace]["description"],
                marketplace,
                "description",
            ),
        }
    if set(found) != allowed:
        raise DraftError("I couldn't write listing copy for that item.")
    named = (brand or "").strip()
    if named:
        for marketplace, copy in found.items():
            haystack = f"{copy['title']} {copy['description']}".casefold()
            if named.casefold() not in haystack:
                raise DraftError(
                    f"The {LABELS[marketplace]} copy must include the brand {named}."
                )
    return found


def _bounded(value, limit, marketplace, field):
    if not isinstance(value, str):
        raise DraftError("I couldn't write listing copy for that item.")
    cleaned = " ".join(value.split())
    if not cleaned:
        raise DraftError(f"The {LABELS[marketplace]} {field} is empty.")
    if len(cleaned) > limit:
        raise DraftError(
            f"The {LABELS[marketplace]} {field} must be {limit} characters or fewer."
        )
    return cleaned


def _save_all(item, writable, copies):
    attributes = _attributes(item)
    category = _category_ref(item)
    price = item.price_minor
    currency = item.currency
    try:
        with transaction.atomic():
            saved = []
            for marketplace, _existing in writable:
                saved.append(
                    _save_one(
                        item,
                        marketplace,
                        copies[marketplace],
                        attributes,
                        category,
                        price,
                        currency,
                    )
                )
            return saved
    except ListingError as exc:
        raise DraftError("I couldn't save those draft listings.") from exc


def _save_one(item, marketplace, copy, attributes, category, price, currency):
    data = {
        "title": copy["title"],
        "description": copy["description"],
        "category_ref": category,
        "attributes": attributes,
        "price_minor": price,
    }
    if price is not None:
        data["currency"] = currency
    try:
        listing = item.listings.get(marketplace=marketplace)
    except Listing.DoesNotExist:
        data["marketplace"] = marketplace
        return create_listing(item, data)
    data["status"] = Listing.Status.DRAFT
    return update_listing(listing, data)


def _split(item, marketplaces):
    existing = {listing.marketplace: listing for listing in item.listings.all()}
    writable = []
    skipped = []
    for marketplace in marketplaces:
        listing = existing.get(marketplace)
        if listing is not None and listing.status in UNTOUCHABLE:
            skipped.append((marketplace, listing))
        else:
            writable.append((marketplace, listing))
    return writable, skipped


def _missing(item):
    missing = [label for field, label in REQUIRED_FIELDS if not (getattr(item, field) or "").strip()]
    if not item.photos.exists():
        missing.append("at least one photo")
    return missing


def _attributes(item):
    attributes = {}
    for field in ATTRIBUTE_FIELDS:
        value = getattr(item, field)
        if isinstance(value, str):
            value = value.strip()
        if value:
            attributes[field] = value
    return attributes


def _category_ref(item):
    parts = []
    for value in (item.department, item.category, item.garment_type):
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return "/".join(parts)[:255]


def _marketplaces(value):
    if value is None:
        return list(MARKETPLACES)
    if not isinstance(value, list) or not value:
        raise DraftError("marketplaces must be vinted, depop, or ebay.")
    cleaned = []
    for name in value:
        if not isinstance(name, str) or name not in MARKETPLACES or name in cleaned:
            raise DraftError("marketplaces must be vinted, depop, or ebay.")
        cleaned.append(name)
    return cleaned


def _item_id(value):
    if type(value) is int and value >= 1:
        return value
    return None


def _missing_item_message(item_id):
    if Item.objects.filter(pk=item_id).exists():
        return "That item belongs to someone else."
    return "That item does not exist."


def _needs_message(missing):
    return f"Add {_join(missing)} before I draft this listing."


def _ready_message(written, skipped):
    sentence = f"Draft listings are ready for {_join([LABELS[name] for name in written])}."
    if not skipped:
        return sentence
    return f"{sentence} {_left_alone(skipped)}"


def _skipped_message(skipped):
    return _left_alone(skipped)


def _left_alone(skipped):
    if len(skipped) == 1:
        marketplace, listing = skipped[0]
        return (
            f"The {LABELS[marketplace]} listing is already {listing.status}, "
            "so I left it as it is."
        )
    parts = [
        f"the {LABELS[marketplace]} listing is already {listing.status}"
        for marketplace, listing in skipped
    ]
    return f"I left them as they are: {_join(parts)}."


def _join(parts):
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _view(listing):
    return {
        "marketplace": listing.marketplace,
        "status": listing.status,
        "title": listing.title,
        "description": listing.description,
    }


def _result(item_id, status, message, listings):
    return {
        "status": status,
        "item_id": item_id,
        "message": message,
        "listings": listings,
    }


def _failed(item_id, message):
    return _result(item_id, "failed", message, [])
