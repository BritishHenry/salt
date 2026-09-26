"""Login pages and secret hosts for the marketplaces Willow signs into."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketplaceSite:
    """One marketplace Willow can open on the seller's browser profile."""

    slug: str
    label: str
    login_url: str
    allowed_hosts: tuple[str, ...]

    @property
    def secret_alias(self):
        return f"{self.slug}_password"


VINTED = MarketplaceSite(
    slug="vinted",
    label="Vinted",
    login_url="https://www.vinted.co.uk/member/signup/select_type",
    allowed_hosts=("vinted.co.uk", "www.vinted.co.uk"),
)
DEPOP = MarketplaceSite(
    slug="depop",
    label="Depop",
    login_url="https://www.depop.com/login/",
    allowed_hosts=("depop.com", "www.depop.com"),
)
EBAY = MarketplaceSite(
    slug="ebay",
    label="eBay",
    login_url="https://signin.ebay.co.uk/signin/",
    allowed_hosts=("ebay.co.uk", "www.ebay.co.uk", "signin.ebay.co.uk"),
)

SITES = {site.slug: site for site in (VINTED, DEPOP, EBAY)}
