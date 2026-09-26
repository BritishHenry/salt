"""UK marketplace searches for comparable listings."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import quote_plus

from services.browser_use import BrowserUseClient
from services.browser_use.errors import BrowserUseError

MAX_COMPS = 8
SEARCH_TIMEOUT_SECONDS = 120
MAX_COST_USD = 1
MARKETPLACES = ("vinted", "depop", "ebay")

COMP_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "comps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "price_pence": {"type": "integer"},
                    "currency": {"type": "string"},
                    "condition": {"type": "string"},
                    "size": {"type": "string"},
                    "url": {"type": "string"},
                    "sold": {"type": "boolean"},
                },
                "required": ["title", "price_pence", "currency", "url", "sold"],
            },
        }
    },
    "required": ["comps"],
}


@dataclass(frozen=True)
class MarketplaceSearch:
    marketplace: str
    urls: tuple[str, ...]


def search_query(item):
    """Words used to find comparable listings.

    Brand, garment, colour, and size identify the item. A title is used only
    when those fields are empty, so a title-only item still has something to search.
    """
    garment = (getattr(item, "garment_type", "") or "").strip()
    if not garment:
        category = (getattr(item, "category", "") or "").strip()
        if category:
            display = getattr(item, "get_category_display", None)
            garment = display() if callable(display) else category
    parts = [
        (getattr(item, "brand", "") or "").strip(),
        garment,
        (getattr(item, "colour", "") or "").strip(),
        (getattr(item, "size_label", "") or "").strip(),
    ]
    query = " ".join(part for part in parts if part)
    if query:
        return query
    return (getattr(item, "title", "") or "").strip()


def marketplace_searches(query):
    """Fixed UK search pages for Vinted, Depop, and eBay."""
    encoded = quote_plus(query)
    ebay_active = f"https://www.ebay.co.uk/sch/i.html?_nkw={encoded}&LH_PrefLoc=1"
    ebay_sold = (
        f"https://www.ebay.co.uk/sch/i.html?_nkw={encoded}"
        "&LH_Sold=1&LH_Complete=1&LH_PrefLoc=1"
    )
    return (
        MarketplaceSearch(
            "vinted",
            (f"https://www.vinted.co.uk/catalog?search_text={encoded}",),
        ),
        MarketplaceSearch(
            "depop",
            (f"https://www.depop.com/search/?q={encoded}",),
        ),
        MarketplaceSearch("ebay", (ebay_active, ebay_sold)),
    )


def task_for(search):
    """Instructions that open the search pages and return structured comps."""
    pages = "\n".join(search.urls)
    sold_note = ""
    if search.marketplace == "ebay":
        sold_note = (
            " The second page is sold and completed listings. "
            "Mark those rows sold."
        )
    return (
        "Open these UK search pages and collect comparable clothing listings.\n"
        f"{pages}\n"
        "Return at most 8 listings that match the search. "
        "For each one include the title, price_pence as a whole number of pence, "
        "currency as gbp, condition, size, the listing url, and sold. "
        "Skip ads and unrelated items. Use only prices shown on the page."
        f"{sold_note}"
    )


def accept_comp(raw, marketplace):
    """Keep one GBP listing with a positive price, or drop it."""
    if not isinstance(raw, dict):
        return None
    currency = str(raw.get("currency") or "").strip().lower()
    if currency != "gbp":
        return None
    price = raw.get("price_pence")
    if type(price) is not int or price <= 0:
        return None
    url = str(raw.get("url") or "").strip()
    if not url.startswith(("https://", "http://")) or len(url) > 500:
        return None
    sold = raw.get("sold")
    return {
        "marketplace": marketplace,
        "title": str(raw.get("title") or "").strip()[:255],
        "price_minor": price,
        "currency": "gbp",
        "condition": str(raw.get("condition") or "").strip()[:64],
        "size": str(raw.get("size") or "").strip()[:64],
        "url": url,
        "sold": sold if isinstance(sold, bool) else False,
    }


def comps_from_output(output, marketplace):
    if isinstance(output, str):
        output = json.loads(output)
    rows = output.get("comps") if isinstance(output, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"{marketplace} did not return a list of listings.")
    kept = []
    for raw in rows:
        comp = accept_comp(raw, marketplace)
        if comp is None:
            continue
        kept.append(comp)
        if len(kept) == MAX_COMPS:
            break
    return kept


def profile_id_for(item):
    user = item.user
    if user.browser_profile_id and user.browser_profile_status == "ready":
        return user.browser_profile_id
    return None


def collect_comps(item, *, browser=None):
    """Search the three marketplaces. A failed site is reported and skipped."""
    client = browser if browser is not None else BrowserUseClient()
    profile_id = profile_id_for(item)
    searches = marketplace_searches(search_query(item))
    comps = []
    errors = []
    with ThreadPoolExecutor(max_workers=len(searches)) as pool:
        futures = [
            pool.submit(_search_one, client, search, profile_id) for search in searches
        ]
        for future in as_completed(futures):
            found, error = future.result()
            comps.extend(found)
            if error:
                errors.append(error)
    return comps, errors


def _search_one(browser, search, profile_id):
    try:
        run = browser.run(
            task_for(search),
            timeout=SEARCH_TIMEOUT_SECONDS,
            output_schema=COMP_OUTPUT_SCHEMA,
            max_cost_usd=MAX_COST_USD,
            profile_id=profile_id,
            proxy_country_code="gb",
        )
        return comps_from_output(run.output, search.marketplace), ""
    except BrowserUseError as exc:
        return [], f"{search.marketplace}: {exc}"
    except (ValueError, TypeError) as exc:
        return [], f"{search.marketplace}: {exc}"
