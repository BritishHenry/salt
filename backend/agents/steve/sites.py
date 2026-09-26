"""Inbox pages Steve opens on the seller's connected session."""

from dataclasses import dataclass


@dataclass(frozen=True)
class InboxSite:
    slug: str
    label: str
    inbox_url: str


VINTED = InboxSite("vinted", "Vinted", "https://www.vinted.co.uk/inbox")
DEPOP = InboxSite("depop", "Depop", "https://www.depop.com/messages/")
EBAY = InboxSite("ebay", "eBay", "https://www.ebay.co.uk/mesg/messagecenter")

SITES = {site.slug: site for site in (VINTED, DEPOP, EBAY)}
