import stripe
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

from payments.attribution import transfers_status_from_account

SIGNER_SALT = "payments.seller-onboarding"
REFRESH_MAX_AGE = 60 * 60 * 24


class StripeCallError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def client():
    secret = settings.STRIPE_SECRET_KEY
    if not secret:
        raise ImproperlyConfigured(
            "STRIPE_SECRET_KEY is missing. Set it in backend/.env."
        )
    return stripe.StripeClient(secret)


def _options(idempotency_key=None):
    options = {"stripe_version": settings.STRIPE_API_VERSION}
    if idempotency_key:
        options["idempotency_key"] = idempotency_key
    return options


def _raise_stripe(exc):
    message = getattr(exc, "user_message", None) or str(exc)
    raise StripeCallError(message) from exc


def create_recipient_account(*, display_name, contact_email, user_id):
    try:
        account = client().v2.core.accounts.create(
            {
                "contact_email": contact_email,
                "display_name": display_name,
                "dashboard": "express",
                "identity": {"country": "gb"},
                "defaults": {
                    "responsibilities": {
                        "fees_collector": "application",
                        "losses_collector": "application",
                    }
                },
                "configuration": {
                    "recipient": {
                        "capabilities": {
                            "stripe_balance": {
                                "stripe_transfers": {"requested": True}
                            }
                        }
                    }
                },
                "metadata": {"salt_user_id": str(user_id)},
                "include": ["configuration.recipient"],
            },
            _options(idempotency_key=f"salt-user-{user_id}"),
        )
    except stripe.StripeError as exc:
        _raise_stripe(exc)
    return account.id, transfers_status_from_account(account)


def signed_seller(seller_id):
    return TimestampSigner(salt=SIGNER_SALT).sign(str(seller_id))


def unsigned_seller(token):
    try:
        return int(
            TimestampSigner(salt=SIGNER_SALT).unsign(
                token, max_age=REFRESH_MAX_AGE
            )
        )
    except (BadSignature, SignatureExpired, ValueError) as exc:
        raise StripeCallError("Onboarding link is invalid or expired.", status=400) from exc


def onboarding_link(account_id, seller_id):
    refresh_url = (
        f"{settings.STRIPE_CONNECT_REFRESH_URL}?seller={signed_seller(seller_id)}"
    )
    try:
        link = client().v2.core.account_links.create(
            {
                "account": account_id,
                "use_case": {
                    "type": "account_onboarding",
                    "account_onboarding": {
                        "configurations": ["recipient"],
                        "refresh_url": refresh_url,
                        "return_url": settings.STRIPE_CONNECT_RETURN_URL,
                    },
                },
            },
            _options(),
        )
    except stripe.StripeError as exc:
        _raise_stripe(exc)
    return link.url


def refresh_transfers_status(account_id):
    try:
        account = client().v2.core.accounts.retrieve(
            account_id,
            {"include": ["configuration.recipient"]},
            _options(),
        )
    except stripe.StripeError as exc:
        _raise_stripe(exc)
    return transfers_status_from_account(account)


def express_login_link(account_id):
    try:
        link = client().v1.accounts.login_links.create(account_id)
    except stripe.StripeError as exc:
        _raise_stripe(exc)
    return link.url


def create_transfer(*, account_id, amount_minor, currency, metadata, idempotency_key, transfer_group):
    try:
        transfer = client().v1.transfers.create(
            {
                "amount": amount_minor,
                "currency": currency,
                "destination": account_id,
                "metadata": metadata,
                "transfer_group": transfer_group,
            },
            {"idempotency_key": idempotency_key},
        )
    except stripe.StripeError as exc:
        _raise_stripe(exc)
    return transfer.id
