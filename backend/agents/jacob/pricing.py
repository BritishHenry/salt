"""Turn comparable listings into one GBP list price."""

import json
from dataclasses import dataclass

from django.db import transaction

from agents.jacob.search import collect_comps
from listings.models import Comparable, PriceQuote
from services.grok import GrokClient
from services.grok.errors import GrokError

SUPPORTING = frozenset({Comparable.Similarity.HIGH, Comparable.Similarity.MEDIUM})

PRICE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "price_pence": {"type": "integer"},
        "rationale": {"type": "string"},
        "comps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {"type": "string"},
                    "similarity": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "reason": {"type": "string"},
                },
                "required": ["url", "similarity", "reason"],
            },
        },
    },
    "required": ["price_pence", "rationale", "comps"],
}

INSTRUCTIONS = (
    "You price second-hand clothes in GBP pence. "
    "Choose one list price from the comparable listings. "
    "Weigh condition and size. Unknown condition or size means the match is weaker. "
    "Sold listings show what buyers paid. Active listings show asking prices. "
    "Mark each comparable high, medium, or low. "
    "The price must sit between the lowest and highest high or medium comparable."
)


class PricingError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass(frozen=True)
class PriceDecision:
    price_minor: int | None
    rationale: str
    error: str
    comps: tuple


def item_can_be_priced(item):
    return any(
        (getattr(item, name, "") or "").strip()
        for name in ("title", "brand", "garment_type")
    )


def price_item(item, *, browser=None, grok=None):
    """Search for comps and store one list price on a new quote.

    A blank item is refused before a quote or a browser run exists. Search
    and model failures are stored on the quote. An empty item price is filled
    from a ready quote. A price already on the item is left as it is.
    """
    if not item_can_be_priced(item):
        raise PricingError(
            "Add a title, brand, or garment type before pricing this item."
        )
    quote = PriceQuote.objects.create(item=item)
    try:
        return _finish_quote(quote, item, browser=browser, grok=grok)
    except Exception as exc:
        if quote.status == PriceQuote.Status.RUNNING:
            quote.status = PriceQuote.Status.FAILED
            quote.error = str(exc)
            quote.save(update_fields=["status", "error", "updated_at"])
        if isinstance(exc, (PricingError, GrokError)):
            return quote
        raise


def choose_price(item, comps, *, grok=None):
    """Ask Grok for one price inside the range of the close comps."""
    client = grok if grok is not None else GrokClient.from_environment()
    raw = client.ask_for_json_object(
        _prompt(item, comps),
        instructions=INSTRUCTIONS,
        schema=PRICE_SCHEMA,
        schema_name="list_price",
    )
    if not isinstance(raw, dict):
        raise PricingError("Grok did not return a price.")
    annotated = _annotate(comps, raw.get("comps"))
    rationale = str(raw.get("rationale") or "").strip()
    supporting = [comp for comp in annotated if comp["similarity"] in SUPPORTING]
    if not supporting:
        return PriceDecision(
            price_minor=None,
            rationale=rationale,
            error="None of the comparable listings were close enough to set a price.",
            comps=tuple(annotated),
        )
    price = raw.get("price_pence")
    if type(price) is not int or price <= 0:
        return PriceDecision(
            price_minor=None,
            rationale=rationale,
            error="Grok did not return a price in pence.",
            comps=tuple(annotated),
        )
    prices = [comp["price_minor"] for comp in supporting]
    low, high = min(prices), max(prices)
    if price < low or price > high:
        return PriceDecision(
            price_minor=None,
            rationale=rationale,
            error=(
                f"The suggested price of {price} pence sits outside the close "
                f"comparable listings ({low} to {high} pence)."
            ),
            comps=tuple(annotated),
        )
    return PriceDecision(
        price_minor=price,
        rationale=rationale,
        error="",
        comps=tuple(annotated),
    )


def _finish_quote(quote, item, *, browser, grok):
    comps, errors = collect_comps(item, browser=browser)
    if not comps:
        quote.status = PriceQuote.Status.FAILED
        quote.error = " ".join(errors) or "No comparable GBP listings were found."
        quote.save(update_fields=["status", "error", "updated_at"])
        return quote
    try:
        decision = choose_price(item, comps, grok=grok)
    except (GrokError, PricingError) as exc:
        message = exc.message if isinstance(exc, PricingError) else str(exc)
        with transaction.atomic():
            _store_comps(quote, comps)
            quote.status = PriceQuote.Status.FAILED
            quote.error = message
            quote.save(update_fields=["status", "error", "updated_at"])
        return quote
    with transaction.atomic():
        _store_comps(quote, decision.comps)
        if decision.price_minor is None:
            quote.status = PriceQuote.Status.FAILED
            quote.error = decision.error
            quote.rationale = decision.rationale
            quote.save(update_fields=["status", "error", "rationale", "updated_at"])
            return quote
        quote.status = PriceQuote.Status.READY
        quote.price_minor = decision.price_minor
        quote.currency = "gbp"
        quote.rationale = decision.rationale
        quote.error = ""
        quote.save(
            update_fields=[
                "status",
                "price_minor",
                "currency",
                "rationale",
                "error",
                "updated_at",
            ]
        )
        if item.price_minor is None:
            item.price_minor = decision.price_minor
            item.currency = "gbp"
            item.save(update_fields=["price_minor", "currency", "updated_at"])
    return quote


def _store_comps(quote, comps):
    Comparable.objects.bulk_create(
        Comparable(
            quote=quote,
            marketplace=comp["marketplace"],
            title=comp["title"],
            price_minor=comp["price_minor"],
            currency=comp["currency"],
            condition=comp["condition"],
            size=comp["size"],
            url=comp["url"],
            sold=comp["sold"],
            similarity=comp.get("similarity", ""),
            reason=comp.get("reason", ""),
        )
        for comp in comps
    )


def _prompt(item, comps):
    listed = [
        {
            "marketplace": comp["marketplace"],
            "title": comp["title"],
            "price_pence": comp["price_minor"],
            "condition": comp["condition"] or "unknown",
            "size": comp["size"] or "unknown",
            "url": comp["url"],
            "sold": comp["sold"],
        }
        for comp in comps
    ]
    return (
        "Price this item in pence.\n\n"
        f"Item:\n{json.dumps(_item_brief(item), indent=2)}\n\n"
        f"Comparable listings:\n{json.dumps(listed, indent=2)}"
    )


def _item_brief(item):
    return {
        "title": (item.title or "").strip(),
        "brand": (item.brand or "").strip(),
        "garment_type": _garment(item),
        "colour": (item.colour or "").strip() or "unknown",
        "size": (item.size_label or "").strip() or "unknown",
        "size_system": (item.size_system or "").strip() or "unknown",
        "condition": _choice(item, "condition"),
        "flaws": (item.flaws or "").strip() or "none noted",
        "measurements_cm": {
            "chest": _cm(item.chest_cm),
            "waist": _cm(item.waist_cm),
            "length": _cm(item.length_cm),
            "inseam": _cm(item.inseam_cm),
        },
    }


def _garment(item):
    garment = (item.garment_type or "").strip()
    if garment:
        return garment
    return _choice(item, "category")


def _choice(item, field):
    value = (getattr(item, field, "") or "").strip()
    if not value:
        return "unknown"
    display = getattr(item, f"get_{field}_display", None)
    if callable(display):
        return display()
    return value


def _cm(value):
    if value is None:
        return None
    return str(value)


def _annotate(comps, judgments):
    by_url = {}
    if isinstance(judgments, list):
        for row in judgments:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "").strip()
            if not url or url in by_url:
                continue
            similarity = str(row.get("similarity") or "").strip().lower()
            if similarity not in SUPPORTING and similarity != Comparable.Similarity.LOW:
                similarity = Comparable.Similarity.LOW
            by_url[url] = {
                "similarity": similarity,
                "reason": str(row.get("reason") or "").strip(),
            }
    annotated = []
    for comp in comps:
        judgment = by_url.get(
            comp["url"],
            {"similarity": Comparable.Similarity.LOW, "reason": ""},
        )
        annotated.append({**comp, **judgment})
    return annotated
