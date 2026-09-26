"""Sell pages Maggie opens on the seller's browser profile."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketplaceSite:
    """One marketplace Maggie can publish to."""

    slug: str
    label: str
    sell_url: str


VINTED = MarketplaceSite(
    slug="vinted",
    label="Vinted",
    sell_url="https://www.vinted.co.uk/items/new",
)
DEPOP = MarketplaceSite(
    slug="depop",
    label="Depop",
    sell_url="https://www.depop.com/products/create/",
)
EBAY = MarketplaceSite(
    slug="ebay",
    label="eBay",
    sell_url="https://www.ebay.co.uk/sl/sell",
)

SITES = {site.slug: site for site in (VINTED, DEPOP, EBAY)}
MARKETPLACES = tuple(SITES)
