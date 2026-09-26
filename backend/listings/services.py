import datetime
import json
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction

from listings.models import Item, ItemPhoto, Listing


class ListingError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


_ITEM_TEXT = {
    "title": 255,
    "description": None,
    "garment_type": 64,
    "brand": 255,
    "colour": 64,
    "colour_secondary": 64,
    "size_label": 64,
    "material": 255,
    "flaws": None,
    "source": 255,
    "storage_note": 255,
}

_ITEM_CHOICES = {
    "department": Item.Department.values,
    "category": Item.Category.values,
    "size_system": Item.SizeSystem.values,
    "condition": Item.Condition.values,
    "package_size": Item.PackageSize.values,
}

_ITEM_MEASUREMENTS = ("chest_cm", "waist_cm", "length_cm", "inseam_cm")
_ITEM_MONEY = ("cost_minor", "price_minor")

_ITEM_CREATE_FIELDS = (
    set(_ITEM_TEXT)
    | set(_ITEM_CHOICES)
    | set(_ITEM_MEASUREMENTS)
    | set(_ITEM_MONEY)
    | {"currency", "acquired_on"}
)
_ITEM_PATCH_FIELDS = _ITEM_CREATE_FIELDS | {"status"}

_LISTING_TEXT = {
    "title": 255,
    "description": None,
    "category_ref": 255,
}
_LISTING_MONEY = ("price_minor", "shipping_price_minor")
_LISTING_FIELDS = set(_LISTING_TEXT) | set(_LISTING_MONEY) | {"currency", "attributes"}
_LISTING_CREATE_FIELDS = _LISTING_FIELDS | {"marketplace"}
_LISTING_PATCH_FIELDS = _LISTING_FIELDS | {"status"}

_MARKETPLACES = ", ".join(Listing.Marketplace.values)


def parse_body(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as exc:
        raise ListingError("Request body must be JSON.") from exc
    if not isinstance(data, dict):
        raise ListingError("Request body must be a JSON object.")
    return data


def list_items(user):
    return (
        Item.objects.filter(user=user)
        .prefetch_related("photos", "listings")
        .order_by("-created_at", "-pk")
    )


def item_for_user(user, item_id):
    try:
        return (
            Item.objects.prefetch_related("photos", "listings")
            .get(pk=item_id, user=user)
        )
    except Item.DoesNotExist as exc:
        raise ListingError("Item not found.", status=404) from exc


def create_item(user, data):
    if "status" in data:
        raise ListingError("status cannot be set when creating an item.")
    item = Item(user=user, status=Item.Status.DRAFT)
    _apply_item_fields(item, data, allowed=_ITEM_CREATE_FIELDS)
    item.save()
    return item_for_user(user, item.pk)


def update_item(item, data):
    _apply_item_fields(item, data, allowed=_ITEM_PATCH_FIELDS)
    item.save()
    return item_for_user(item.user, item.pk)


def add_photo(item, upload):
    if upload is None or not getattr(upload, "size", 0):
        raise ListingError("image is required.")
    last = (
        item.photos.order_by("-position").values_list("position", flat=True).first()
    )
    position = 0 if last is None else last + 1
    if position > 32767:
        raise ListingError("This item has too many photos.")
    photo = ItemPhoto(item=item, position=position)
    photo.image = upload
    photo.save()
    return photo


def delete_photo(item, position):
    try:
        photo = item.photos.get(position=position)
    except ItemPhoto.DoesNotExist as exc:
        raise ListingError("Photo not found.", status=404) from exc
    photo.image.delete(save=False)
    photo.delete()


def create_listing(item, data):
    if "status" in data:
        raise ListingError("status cannot be set when creating a listing.")
    _reject_unknown(data, _LISTING_CREATE_FIELDS)
    if "marketplace" not in data:
        raise ListingError("marketplace is required.")
    marketplace = _marketplace(data["marketplace"])
    listing = Listing(item=item, marketplace=marketplace, status=Listing.Status.DRAFT)
    _apply_listing_fields(listing, data)
    try:
        with transaction.atomic():
            listing.save()
    except IntegrityError as exc:
        raise ListingError(
            "A listing for this marketplace already exists.", status=409
        ) from exc
    return listing


def listing_for_item(item, marketplace):
    cleaned = _marketplace(marketplace)
    try:
        return item.listings.get(marketplace=cleaned)
    except Listing.DoesNotExist as exc:
        raise ListingError("Listing not found.", status=404) from exc


def update_listing(listing, data):
    _reject_unknown(data, _LISTING_PATCH_FIELDS)
    if "status" in data:
        listing.status = _choice(
            data["status"], Listing.Status.values, "status", allow_blank=False
        )
    _apply_listing_fields(listing, data)
    listing.save()
    return listing


def item_payload(item, request):
    return {
        "id": item.pk,
        "title": item.title,
        "description": item.description,
        "department": item.department,
        "category": item.category,
        "garment_type": item.garment_type,
        "brand": item.brand,
        "colour": item.colour,
        "colour_secondary": item.colour_secondary,
        "size_label": item.size_label,
        "size_system": item.size_system,
        "condition": item.condition,
        "material": item.material,
        "flaws": item.flaws,
        "chest_cm": _decimal_out(item.chest_cm),
        "waist_cm": _decimal_out(item.waist_cm),
        "length_cm": _decimal_out(item.length_cm),
        "inseam_cm": _decimal_out(item.inseam_cm),
        "package_size": item.package_size,
        "cost_minor": item.cost_minor,
        "price_minor": item.price_minor,
        "currency": item.currency,
        "status": item.status,
        "source": item.source,
        "acquired_on": item.acquired_on.isoformat() if item.acquired_on else None,
        "storage_note": item.storage_note,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "photos": [photo_payload(photo, request) for photo in item.photos.all()],
        "listings": [
            listing_payload(listing)
            for listing in item.listings.order_by("marketplace")
        ],
    }


def photo_payload(photo, request):
    return {"position": photo.position, "url": _media_url(request, photo.image.url)}


def listing_payload(listing):
    return {
        "marketplace": listing.marketplace,
        "status": listing.status,
        "title": listing.title,
        "description": listing.description,
        "price_minor": listing.price_minor,
        "currency": listing.currency,
        "category_ref": listing.category_ref,
        "shipping_price_minor": listing.shipping_price_minor,
        "attributes": listing.attributes,
        "external_url": listing.external_url,
    }


def _apply_item_fields(item, data, *, allowed):
    _reject_unknown(data, allowed)
    for name, limit in _ITEM_TEXT.items():
        if name in data:
            setattr(item, name, _text(data[name], name, limit))
    for name, choices in _ITEM_CHOICES.items():
        if name in data:
            setattr(item, name, _choice(data[name], choices, name, allow_blank=True))
    for name in _ITEM_MEASUREMENTS:
        if name in data:
            setattr(item, name, _measurement(data[name], name))
    for name in _ITEM_MONEY:
        if name in data:
            setattr(item, name, _minor(data[name], name))
    if "currency" in data:
        item.currency = _currency(data["currency"])
    if "acquired_on" in data:
        item.acquired_on = _date(data["acquired_on"], "acquired_on")
    if "status" in data:
        item.status = _choice(
            data["status"], Item.Status.values, "status", allow_blank=False
        )


def _apply_listing_fields(listing, data):
    for name, limit in _LISTING_TEXT.items():
        if name in data:
            setattr(listing, name, _text(data[name], name, limit))
    for name in _LISTING_MONEY:
        if name in data:
            setattr(listing, name, _minor(data[name], name))
    if "currency" in data:
        listing.currency = _currency(data["currency"])
    if "attributes" in data:
        listing.attributes = _attributes(data["attributes"])


def _reject_unknown(data, allowed):
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise ListingError(f"Unknown field '{unknown[0]}'.")


def _text(value, field, max_length):
    if not isinstance(value, str):
        raise ListingError(f"{field} must be a string.")
    cleaned = value.strip()
    if max_length is not None and len(cleaned) > max_length:
        raise ListingError(f"{field} must be {max_length} characters or fewer.")
    return cleaned


def _choice(value, choices, field, *, allow_blank):
    if isinstance(value, str):
        value = value.strip()
    if value is None or value == "":
        if allow_blank:
            return ""
        raise ListingError(f"{field} is required.")
    if not isinstance(value, str) or value not in choices:
        raise ListingError(f"{field} must be one of: {', '.join(choices)}.")
    return value


def _minor(value, field):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ListingError(f"{field} must be a non-negative integer.")
    return value


def _measurement(value, field):
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, (list, dict)):
        raise ListingError(f"{field} must be a number.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ListingError(f"{field} must be a number.") from exc
    if not number.is_finite():
        raise ListingError(f"{field} must be a number.")
    quantized = number.quantize(Decimal("0.1"))
    if quantized != number:
        raise ListingError(f"{field} must have at most one decimal place.")
    if quantized < 0 or quantized >= Decimal("100000"):
        raise ListingError(f"{field} must be between 0 and 99999.9.")
    return quantized


def _currency(value):
    if not isinstance(value, str):
        raise ListingError("currency must be a 3-letter code.")
    code = value.strip().lower()
    if len(code) != 3 or not code.isalpha():
        raise ListingError("currency must be a 3-letter code.")
    return code


def _date(value, field):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) != 10:
        raise ListingError(f"{field} must be a date (YYYY-MM-DD).")
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ListingError(f"{field} must be a date (YYYY-MM-DD).") from exc


def _attributes(value):
    if not isinstance(value, dict):
        raise ListingError("attributes must be a JSON object.")
    return value


def _marketplace(value):
    if isinstance(value, str):
        value = value.strip().lower()
    if not isinstance(value, str) or value not in Listing.Marketplace.values:
        raise ListingError(f"marketplace must be one of: {_MARKETPLACES}.")
    return value


def _decimal_out(value):
    if value is None:
        return None
    return float(value)


def _media_url(request, url):
    if not url.startswith(("http://", "https://", "/")):
        url = "/" + url
    return request.build_absolute_uri(url)
