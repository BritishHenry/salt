import json

import stripe
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from accounts.auth import user_from_request
from payments.models import BalanceTransfer, ProcessedStripeEvent, Seller
from payments.services import (
    PaymentError,
    authorize_sale,
    record_sale,
    start_onboarding,
    sync_seller,
    transfer_sale,
)
from payments.stripe_api import (
    StripeCallError,
    express_login_link,
    onboarding_link,
    refresh_transfers_status,
    unsigned_seller,
)


def _user(request):
    return user_from_request(request)


def _seller(user):
    try:
        return user.seller
    except Seller.DoesNotExist:
        return None


def _body(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as exc:
        raise PaymentError("Request body must be JSON.") from exc
    if not isinstance(data, dict):
        raise PaymentError("Request body must be a JSON object.")
    return data


def _json_error(exc):
    return JsonResponse({"error": exc.message}, status=exc.status)


def _seller_payload(seller, url=None):
    payload = {
        "seller_id": seller.pk,
        "stripe_account_id": seller.stripe_account_id,
        "display_name": seller.display_name,
        "contact_email": seller.contact_email,
        "transfers_status": seller.transfers_status,
    }
    if url:
        payload["onboarding_url"] = url
    return payload


@csrf_exempt
@require_POST
def connect(request):
    user = _user(request)
    if user is None:
        return JsonResponse({"error": "Authentication required."}, status=401)
    try:
        data = _body(request)
        seller, url = start_onboarding(
            user=user,
            display_name=data.get("display_name", ""),
            contact_email=data.get("contact_email", ""),
        )
    except (PaymentError, StripeCallError) as exc:
        return _json_error(exc)
    return JsonResponse(_seller_payload(seller, url), status=201)


@csrf_exempt
@require_GET
def connect_status(request):
    user = _user(request)
    if user is None:
        return JsonResponse({"error": "Authentication required."}, status=401)
    seller = _seller(user)
    if seller is None:
        return JsonResponse({"error": "Seller has not started Stripe onboarding."}, status=404)
    try:
        sync_seller(seller)
    except StripeCallError as exc:
        return _json_error(exc)
    return JsonResponse(_seller_payload(seller))


@csrf_exempt
@require_POST
def connect_login_link(request):
    user = _user(request)
    if user is None:
        return JsonResponse({"error": "Authentication required."}, status=401)
    seller = _seller(user)
    if seller is None:
        return JsonResponse({"error": "Seller has not started Stripe onboarding."}, status=404)
    try:
        url = express_login_link(seller.stripe_account_id)
    except StripeCallError as exc:
        return _json_error(exc)
    return JsonResponse({"url": url})


@require_GET
def connect_return(request):
    return JsonResponse(
        {
            "status": "submitted",
            "detail": "Stripe has the onboarding submission. Transfers stay inactive until stripe_transfers is active.",
        }
    )


@require_GET
def connect_refresh(request):
    try:
        seller_id = unsigned_seller(request.GET.get("seller", ""))
        seller = Seller.objects.get(pk=seller_id)
        url = onboarding_link(seller.stripe_account_id, seller.pk)
    except (Seller.DoesNotExist, StripeCallError):
        return JsonResponse({"error": "Could not refresh onboarding."}, status=400)
    return HttpResponseRedirect(url)


@csrf_exempt
@require_POST
def sales(request):
    user = _user(request)
    if user is None:
        return JsonResponse({"error": "Authentication required."}, status=401)
    seller = _seller(user)
    if seller is None:
        return JsonResponse({"error": "Seller has not started Stripe onboarding."}, status=404)
    try:
        data = _body(request)
        sale = record_sale(
            seller=seller,
            marketplace=data.get("marketplace", ""),
            external_sale_id=data.get("external_sale_id", ""),
            amount_minor=data.get("amount_minor"),
        )
    except PaymentError as exc:
        return _json_error(exc)
    return JsonResponse(_sale_payload(sale), status=201)


@csrf_exempt
@require_POST
def sale_authorize(request, sale_id):
    user = _user(request)
    if user is None:
        return JsonResponse({"error": "Authentication required."}, status=401)
    seller = _seller(user)
    if seller is None:
        return JsonResponse({"error": "Seller has not started Stripe onboarding."}, status=404)
    try:
        authorization = authorize_sale(seller=seller, sale_id=sale_id, user=user)
    except PaymentError as exc:
        return _json_error(exc)
    return JsonResponse(
        {
            "sale_id": authorization.sale_id,
            "authorization_id": authorization.pk,
            "statement": authorization.statement,
        }
    )


@csrf_exempt
@require_POST
def sale_transfer(request, sale_id):
    user = _user(request)
    if user is None:
        return JsonResponse({"error": "Authentication required."}, status=401)
    seller = _seller(user)
    if seller is None:
        return JsonResponse({"error": "Seller has not started Stripe onboarding."}, status=404)
    try:
        seller = sync_seller(seller)
        transfer = transfer_sale(seller=seller, sale_id=sale_id)
    except (PaymentError, StripeCallError) as exc:
        return _json_error(exc)
    return JsonResponse(
        {
            "sale_id": transfer.sale_id,
            "stripe_transfer_id": transfer.stripe_transfer_id,
            "status": transfer.status,
        }
    )


def _sale_payload(sale):
    return {
        "sale_id": sale.pk,
        "marketplace": sale.marketplace,
        "external_sale_id": sale.external_sale_id,
        "amount_minor": sale.amount_minor,
        "currency": sale.currency,
    }


@csrf_exempt
@require_POST
def webhook(request):
    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret:
        return HttpResponse(status=500)
    try:
        event = stripe.Webhook.construct_event(
            request.body,
            request.headers.get("Stripe-Signature", ""),
            secret,
        )
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponse(status=400)

    event_id = event["id"]
    if ProcessedStripeEvent.objects.filter(event_id=event_id).exists():
        return HttpResponse(status=200)
    _apply_event(event)
    ProcessedStripeEvent.objects.create(event_id=event_id)
    return HttpResponse(status=200)


def _apply_event(event):
    event_type = event["type"]
    obj = event["data"]["object"]
    if event_type.startswith("transfer."):
        transfer_id = obj.get("id")
        if transfer_id:
            BalanceTransfer.objects.filter(stripe_transfer_id=transfer_id).update(
                status="reversed" if obj.get("reversed") else "created"
            )
        return

    account_id = obj.get("id") if str(obj.get("id", "")).startswith("acct_") else None
    if account_id is None:
        related = event.get("related_object") or {}
        if str(related.get("id", "")).startswith("acct_"):
            account_id = related["id"]
    if not account_id:
        return
    seller = Seller.objects.filter(stripe_account_id=account_id).first()
    if seller is None:
        return
    try:
        seller.transfers_status = refresh_transfers_status(account_id)
    except StripeCallError:
        return
    seller.save(update_fields=["transfers_status", "updated_at"])
