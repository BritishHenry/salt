from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts.auth import user_from_request
from agents.jacob.pricing import PricingError, price_item
from listings.services import (
    ListingError,
    add_photo,
    create_item,
    create_listing,
    delete_photo,
    item_for_user,
    item_payload,
    list_items,
    listing_for_item,
    listing_payload,
    parse_body,
    photo_payload,
    update_item,
    update_listing,
)


def _json_error(exc):
    return JsonResponse({"error": exc.message}, status=exc.status)


def _authenticated(request):
    user = user_from_request(request)
    if user is None:
        return None, JsonResponse({"error": "Authentication required."}, status=401)
    return user, None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def items(request):
    user, error = _authenticated(request)
    if error is not None:
        return error
    if request.method == "GET":
        payload = [item_payload(item, request) for item in list_items(user)]
        return JsonResponse({"items": payload})
    try:
        item = create_item(user, parse_body(request))
    except ListingError as exc:
        return _json_error(exc)
    return JsonResponse(item_payload(item, request), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def item_detail(request, item_id):
    user, error = _authenticated(request)
    if error is not None:
        return error
    try:
        item = item_for_user(user, item_id)
        if request.method == "PATCH":
            item = update_item(item, parse_body(request))
    except ListingError as exc:
        return _json_error(exc)
    return JsonResponse(item_payload(item, request))


@csrf_exempt
@require_http_methods(["POST"])
def item_photos(request, item_id):
    user, error = _authenticated(request)
    if error is not None:
        return error
    try:
        item = item_for_user(user, item_id)
        photo = add_photo(item, request.FILES.get("image"))
    except ListingError as exc:
        return _json_error(exc)
    return JsonResponse(photo_payload(photo, request), status=201)


@csrf_exempt
@require_http_methods(["DELETE"])
def item_photo(request, item_id, position):
    user, error = _authenticated(request)
    if error is not None:
        return error
    try:
        item = item_for_user(user, item_id)
        delete_photo(item, position)
    except ListingError as exc:
        return _json_error(exc)
    return HttpResponse(status=204)


@csrf_exempt
@require_http_methods(["POST"])
def item_listings(request, item_id):
    user, error = _authenticated(request)
    if error is not None:
        return error
    try:
        item = item_for_user(user, item_id)
        listing = create_listing(item, parse_body(request))
    except ListingError as exc:
        return _json_error(exc)
    return JsonResponse(listing_payload(listing), status=201)


@csrf_exempt
@require_http_methods(["PATCH"])
def item_listing(request, item_id, marketplace):
    user, error = _authenticated(request)
    if error is not None:
        return error
    try:
        item = item_for_user(user, item_id)
        listing = listing_for_item(item, marketplace)
        listing = update_listing(listing, parse_body(request))
    except ListingError as exc:
        return _json_error(exc)
    return JsonResponse(listing_payload(listing))


def _quote_payload(quote):
    return {
        "id": quote.pk,
        "item_id": quote.item_id,
        "status": quote.status,
        "price_minor": quote.price_minor,
        "currency": quote.currency,
        "rationale": quote.rationale,
        "error": quote.error,
        "comps": [
            {
                "marketplace": comp.marketplace,
                "title": comp.title,
                "price_minor": comp.price_minor,
                "currency": comp.currency,
                "condition": comp.condition,
                "size": comp.size,
                "url": comp.url,
                "sold": comp.sold,
                "similarity": comp.similarity,
                "reason": comp.reason,
            }
            for comp in quote.comps.all()
        ],
    }


@csrf_exempt
@require_http_methods(["POST"])
def price_item_view(request, item_id):
    """Price one of the caller's items and return Jacob's quote."""
    user, error = _authenticated(request)
    if error is not None:
        return error
    try:
        item = item_for_user(user, item_id)
        quote = price_item(item)
    except ListingError as exc:
        return _json_error(exc)
    except PricingError as exc:
        return JsonResponse({"error": exc.message}, status=exc.status)
    item.refresh_from_db()
    return JsonResponse(
        {
            "quote": _quote_payload(quote),
            "item": {
                "id": item.pk,
                "price_minor": item.price_minor,
                "currency": item.currency,
            },
        }
    )
