"""Rules for recording a marketplace sale and authorizing a Stripe transfer.

A transfer can only move funds that are already in Salt's Stripe balance.
Nothing here reads a marketplace session or moves a marketplace balance.
"""

import re

MARKETPLACE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
CURRENCY = "gbp"


class AttributionError(Exception):
    pass


def normalize_marketplace(value):
    marketplace = (value or "").strip().lower()
    if not MARKETPLACE_RE.fullmatch(marketplace):
        raise AttributionError(
            "marketplace must be a short slug such as vinted or depop."
        )
    return marketplace


def normalize_external_sale_id(value):
    sale_id = (value or "").strip()
    if not sale_id or len(sale_id) > 255:
        raise AttributionError("external_sale_id is required.")
    return sale_id


def normalize_amount(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise AttributionError("amount_minor must be a positive integer.")
    if value < 1:
        raise AttributionError("amount_minor must be a positive integer.")
    return value


def transfers_status_from_account(account):
    """Read stripe_transfers status from a v2 Account, defaulting to pending."""
    current = account
    for key in (
        "configuration",
        "recipient",
        "capabilities",
        "stripe_balance",
        "stripe_transfers",
        "status",
    ):
        if current is None:
            return "pending"
        if isinstance(current, dict):
            current = current.get(key)
            continue
        try:
            current = current[key]
        except (KeyError, TypeError, AttributeError):
            current = getattr(current, key, None)
    if not current:
        return "pending"
    return str(current)


def authorization_statement(sale):
    amount = f"{sale.amount_minor / 100:.2f}"
    return (
        f"I authorize Salt to transfer {amount} {sale.currency.upper()} "
        f"for {sale.marketplace} sale {sale.external_sale_id} from the Salt "
        "Stripe balance to my connected Stripe account."
    )
