from django.db import IntegrityError, transaction

from payments.attribution import (
    AttributionError,
    authorization_statement,
    normalize_amount,
    normalize_external_sale_id,
    normalize_marketplace,
)
from listings.models import Item, Listing
from payments.models import BalanceTransfer, FundAuthorization, MarketplaceSale, Seller
from payments.stripe_api import (
    StripeCallError,
    create_recipient_account,
    create_transfer,
    onboarding_link,
    refresh_transfers_status,
)


class PaymentError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def start_onboarding(*, user, display_name, contact_email):
    name = (display_name or "").strip()
    email = (contact_email or "").strip()
    if not name or not email or "@" not in email:
        raise PaymentError("display_name and contact_email are required.")

    seller = Seller.objects.filter(user=user).first()
    if seller is None:
        account_id, status = create_recipient_account(
            display_name=name, contact_email=email, user_id=user.pk
        )
        seller = Seller.objects.create(
            user=user,
            stripe_account_id=account_id,
            display_name=name,
            contact_email=email,
            transfers_status=status,
        )
    url = onboarding_link(seller.stripe_account_id, seller.pk)
    return seller, url


def sync_seller(seller):
    seller.transfers_status = refresh_transfers_status(seller.stripe_account_id)
    seller.save(update_fields=["transfers_status", "updated_at"])
    return seller


def record_sale(
    *, seller, marketplace, external_sale_id, amount_minor, listing=None
):
    try:
        marketplace = normalize_marketplace(marketplace)
        external_sale_id = normalize_external_sale_id(external_sale_id)
        amount_minor = normalize_amount(amount_minor)
    except AttributionError as exc:
        raise PaymentError(str(exc)) from exc
    if listing is not None:
        if listing.item.user_id != seller.user_id:
            raise PaymentError("Listing does not belong to this seller.")
        if listing.marketplace != marketplace:
            raise PaymentError("Listing marketplace does not match the sale.")
    try:
        with transaction.atomic():
            pending_delist = []
            if listing is not None:
                item = Item.objects.select_for_update().get(pk=listing.item_id)
                listing = item.listings.select_for_update().get(pk=listing.pk)
                pending_delist = _open_copies(item, listing.pk)
            sale = MarketplaceSale.objects.create(
                seller=seller,
                listing=listing,
                marketplace=marketplace,
                external_sale_id=external_sale_id,
                amount_minor=amount_minor,
                currency="gbp",
            )
            if listing is not None:
                listing.mark_sold()
            if pending_delist:
                user_id = seller.user_id
                targets = tuple(pending_delist)
                transaction.on_commit(lambda: _delist_sold_copies(user_id, targets))
            return sale
    except (Item.DoesNotExist, Listing.DoesNotExist) as exc:
        raise PaymentError("Listing not found.", status=404) from exc
    except IntegrityError as exc:
        raise PaymentError(
            "A sale with this marketplace id is already recorded.", status=409
        ) from exc


def _open_copies(item, sold_listing_id):
    """Live copies that still need to come down on the marketplace."""
    targets = []
    for row in item.listings.all():
        if row.pk == sold_listing_id or not row.external_url:
            continue
        if row.status in (
            Listing.Status.LIVE,
            Listing.Status.PAUSED,
            Listing.Status.PUBLISHING,
        ):
            targets.append((row.pk, row.status))
    return targets


def _delist_sold_copies(user_id, targets):
    from agents.maggie.publish import delist_after_sale

    delist_after_sale(user_id, targets)


def authorize_sale(*, seller, sale_id, user):
    sale = _seller_sale(seller, sale_id)
    statement = authorization_statement(sale)
    authorization, _created = FundAuthorization.objects.get_or_create(
        sale=sale,
        defaults={"authorized_by": user, "statement": statement},
    )
    return authorization


def transfer_sale(*, seller, sale_id):
    with transaction.atomic():
        sale = _seller_sale(seller, sale_id, lock=True)
        if not FundAuthorization.objects.filter(sale=sale).exists():
            raise PaymentError(
                "The seller must authorize this sale before funds can move.",
                status=403,
            )
        if seller.transfers_status != "active":
            raise PaymentError(
                "Stripe has not enabled transfers for this seller yet.",
                status=409,
            )
        existing = BalanceTransfer.objects.filter(sale=sale).first()
        if existing and existing.stripe_transfer_id:
            return existing
        if existing and existing.status == "pending":
            raise PaymentError("A transfer is already in progress.", status=409)
        retry_suffix = ""
        if existing and existing.status == "failed":
            retry_suffix = f"-{int(existing.updated_at.timestamp())}"
            existing.status = "pending"
            existing.failure_message = ""
            existing.save(update_fields=["status", "failure_message", "updated_at"])
        transfer_row = existing or BalanceTransfer.objects.create(
            sale=sale, status="pending"
        )

        authorization = sale.authorization
        try:
            stripe_id = create_transfer(
                account_id=seller.stripe_account_id,
                amount_minor=sale.amount_minor,
                currency=sale.currency,
                transfer_group=f"sale_{sale.pk}",
                idempotency_key=f"salt-sale-{sale.pk}{retry_suffix}",
                metadata={
                    "salt_sale_id": str(sale.pk),
                    "salt_seller_id": str(seller.pk),
                    "marketplace": sale.marketplace,
                    "external_sale_id": sale.external_sale_id,
                    "authorization_id": str(authorization.pk),
                },
            )
        except StripeCallError as exc:
            transfer_row.status = "failed"
            transfer_row.failure_message = exc.message
            transfer_row.save(
                update_fields=["status", "failure_message", "updated_at"]
            )
            raise PaymentError(exc.message, status=exc.status) from exc

        transfer_row.stripe_transfer_id = stripe_id
        transfer_row.status = "created"
        transfer_row.failure_message = ""
        transfer_row.save(
            update_fields=[
                "stripe_transfer_id",
                "status",
                "failure_message",
                "updated_at",
            ]
        )
        return transfer_row


def _seller_sale(seller, sale_id, lock=False):
    queryset = MarketplaceSale.objects.filter(seller=seller)
    if lock:
        queryset = queryset.select_for_update()
    try:
        return queryset.get(pk=sale_id)
    except MarketplaceSale.DoesNotExist as exc:
        raise PaymentError("Sale not found.", status=404) from exc
