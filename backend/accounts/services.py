import json

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from accounts.models import ApiToken, User
from payments.models import Seller
from payments.services import start_onboarding
from payments.stripe_api import onboarding_link
from services.browser_use import BrowserUseClient


class AccountError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def parse_body(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as exc:
        raise AccountError("Request body must be JSON.") from exc
    if not isinstance(data, dict):
        raise AccountError("Request body must be a JSON object.")
    return data


def register(*, email, password, display_name):
    email, password, display_name = _signup_fields(email, password, display_name)
    if User.objects.filter(email=email).exists():
        raise AccountError("An account with this email already exists.", status=409)
    candidate = User(email=email, display_name=display_name)
    try:
        validate_password(password, candidate)
    except ValidationError as exc:
        raise AccountError(" ".join(exc.messages)) from exc
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email, display_name=display_name, password=password
            )
            token = ApiToken.objects.create(user=user)
    except IntegrityError as exc:
        raise AccountError(
            "An account with this email already exists.", status=409
        ) from exc
    provision(user)
    return user, token


def log_in(request, *, email, password):
    email = _email(email) or ""
    user = authenticate(request, email=email, password=password or "")
    if user is None:
        raise AccountError("Email or password is incorrect.", status=401)
    token = rotate_token(user)
    return user, token


def rotate_token(user):
    with transaction.atomic():
        ApiToken.objects.filter(user=user).delete()
        return ApiToken.objects.create(user=user)


def provision(user):
    """Create the Stripe recipient and Browser Use profile that are still missing.

    External calls run outside the signup transaction. One failure does not
    block the other, and a later call only retries the missing piece.
    """
    _provision_stripe(user)
    _provision_browser(user)
    user.refresh_from_db()
    return user


def account_payload(user, token=None):
    payload = {
        "user": {
            "id": user.pk,
            "email": user.email,
            "display_name": user.display_name,
        },
        "stripe": _stripe_payload(user),
        "browser_profile": _browser_payload(user),
    }
    if token is not None:
        payload["token"] = token.key
    return payload


def _signup_fields(email, password, display_name):
    cleaned_email = _email(email)
    if cleaned_email is None:
        raise AccountError("Enter a valid email address.")
    name = (display_name or "").strip()
    if not name:
        raise AccountError("display_name is required.")
    if len(name) > 255:
        raise AccountError("display_name must be 255 characters or fewer.")
    if not password:
        raise AccountError("password is required.")
    return cleaned_email, password, name


def _email(value):
    email = (value or "").strip().lower()
    if not email:
        return None
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


def _provision_stripe(user):
    if Seller.objects.filter(user=user).exists():
        _clear_stripe_error(user)
        return
    try:
        start_onboarding(
            user=user, display_name=user.display_name, contact_email=user.email
        )
    except Exception as exc:
        if Seller.objects.filter(user=user).exists():
            _clear_stripe_error(user)
            return
        user.stripe_provision_error = _error_text(exc)
        user.save(update_fields=["stripe_provision_error"])
        return
    _clear_stripe_error(user)


def _clear_stripe_error(user):
    if not user.stripe_provision_error:
        return
    user.stripe_provision_error = ""
    user.save(update_fields=["stripe_provision_error"])


def _provision_browser(user):
    if user.browser_profile_id:
        if user.browser_profile_status != "ready" or user.browser_profile_error:
            user.browser_profile_status = "ready"
            user.browser_profile_error = ""
            user.save(update_fields=["browser_profile_status", "browser_profile_error"])
        return
    user_id = str(user.pk)
    try:
        client = BrowserUseClient()
        profile = _matching_profile(client, user_id)
        if profile is None:
            profile = client.create_profile(name=user.display_name, user_id=user_id)
        user.browser_profile_id = profile.id
        user.browser_profile_status = "ready"
        user.browser_profile_error = ""
    except Exception as exc:
        user.browser_profile_status = "failed"
        user.browser_profile_error = _error_text(exc)
    user.save(
        update_fields=[
            "browser_profile_id",
            "browser_profile_status",
            "browser_profile_error",
        ]
    )


def _matching_profile(client, user_id):
    page = client.list_profiles(query=user_id)
    for profile in page.items:
        if profile.user_id == user_id:
            return profile
    return None


def _stripe_payload(user):
    seller = Seller.objects.filter(user=user).first()
    if seller is None:
        return {
            "status": "failed",
            "error": user.stripe_provision_error or "Stripe account has not been created.",
        }
    try:
        url = onboarding_link(seller.stripe_account_id, seller.pk)
    except Exception as exc:
        return {
            "seller_id": seller.pk,
            "stripe_account_id": seller.stripe_account_id,
            "transfers_status": seller.transfers_status,
            "error": _error_text(exc),
        }
    return {
        "seller_id": seller.pk,
        "stripe_account_id": seller.stripe_account_id,
        "transfers_status": seller.transfers_status,
        "onboarding_url": url,
    }


def _browser_payload(user):
    if user.browser_profile_status == "ready" and user.browser_profile_id:
        return {"status": "ready", "profile_id": user.browser_profile_id}
    return {
        "status": "failed",
        "error": user.browser_profile_error or "Browser profile has not been created.",
    }


def _error_text(exc):
    message = getattr(exc, "message", None) or str(exc)
    return message or exc.__class__.__name__
