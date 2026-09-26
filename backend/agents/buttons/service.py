"""Apply a Buttons tool call to a seller's draft item."""

from django.core.files.base import ContentFile
from django.db import transaction

from services.grok.errors import GrokError

from listings.models import Item, ItemPhoto

from agents.buttons.errors import ButtonsError
from agents.buttons.extract import column_value, extract_photo
from agents.buttons.photos import load_photo_bytes
from agents.buttons.schema import (
    ACTIONS,
    ASK_PROMPTS,
    CHOICES,
    FIELD_LABELS,
    FIELD_ORDER,
    LABEL_PHOTO_FIELDS,
    REQUIRED_FIELDS,
    choice_options,
)


def handle(user, arguments, *, grok):
    """Run one Buttons action for the authenticated seller."""
    if not isinstance(arguments, dict):
        raise ButtonsError("Tool arguments must be an object.")
    action = arguments.get("action")
    if action not in ACTIONS:
        raise ButtonsError("action must be a Buttons action.")
    if action == "read_photo":
        return _read_photo(user, arguments, grok)
    item = _owned_item(user, arguments)
    if action == "add_photo":
        return _add_photo(item, arguments, grok)
    if action == "confirm_field":
        return _confirm_field(item, arguments)
    if action == "apply_answer":
        return _apply_answer(item, arguments)
    if action == "confirm_item":
        return _confirm_item(item)
    return _deny_item(item)


def _read_photo(user, arguments, grok):
    if arguments.get("item_id") not in (None, ""):
        raise ButtonsError("read_photo starts a new item. Omit item_id.")
    image_url, image_file_id = _photo_reference(arguments)
    data, proposals = _read_image(grok, image_url=image_url, image_file_id=image_file_id)
    with transaction.atomic():
        item = Item.objects.create(
            user=user,
            source="buttons",
            status=Item.Status.DRAFT,
            proposals=proposals,
            confirmed_fields=[],
        )
        _store_photo(item, data)
    item.refresh_from_db()
    return present(item)


def _add_photo(item, arguments, grok):
    _require_draft(item)
    image_url, image_file_id = _photo_reference(arguments)
    data, incoming = _read_image(grok, image_url=image_url, image_file_id=image_file_id)
    with transaction.atomic():
        _store_photo(item, data)
        confirmed = set(item.confirmed_fields or [])
        proposals = dict(item.proposals or {})
        for field, row in incoming.items():
            if field in confirmed:
                continue
            proposals[field] = row
        item.proposals = proposals
        item.save(update_fields=["proposals", "updated_at"])
    item.refresh_from_db()
    return present(item)


def _confirm_field(item, arguments):
    _require_draft(item)
    field = _require_field(arguments)
    proposals = dict(item.proposals or {})
    if field not in proposals:
        raise ButtonsError(f"There is no proposed {field} to confirm.")
    row = proposals.pop(field)
    _write_confirmed(item, field, row["value"])
    item.proposals = proposals
    _save_confirmation(item, field)
    return present(item)


def _apply_answer(item, arguments):
    _require_draft(item)
    field = _require_field(arguments)
    if "value" not in arguments or arguments.get("value") is None:
        raise ButtonsError("value is required.")
    proposals = dict(item.proposals or {})
    proposals.pop(field, None)
    _write_confirmed(item, field, arguments.get("value"))
    item.proposals = proposals
    _save_confirmation(item, field)
    return present(item)


def _confirm_item(item):
    _require_draft(item)
    proposals = dict(item.proposals or {})
    written = []
    for field in list(proposals):
        if field in set(item.confirmed_fields or []):
            proposals.pop(field)
            continue
        row = proposals.pop(field)
        _write_confirmed(item, field, row["value"])
        written.append(field)
    item.proposals = proposals
    item.save(update_fields=["proposals", "confirmed_fields", *written, "updated_at"])
    return present(item)


def _deny_item(item):
    if item.status == Item.Status.ARCHIVED:
        return present(item)
    _require_draft(item)
    item.status = Item.Status.ARCHIVED
    item.proposals = {}
    item.save(update_fields=["status", "proposals", "updated_at"])
    return present(item)


def present(item):
    confirmed_names = list(item.confirmed_fields or [])
    confirmed = set(confirmed_names)
    proposals = item.proposals or {}
    proposed = []
    for field in FIELD_ORDER:
        row = proposals.get(field)
        if row is None or field in confirmed:
            continue
        proposed.append(
            {
                "field": field,
                "value": row["value"],
                "confidence": row["confidence"],
                "evidence": row["evidence"],
            }
        )
    question = _next_question(item)
    return {
        "item_id": item.pk,
        "status": _intake_status(item),
        "proposed": proposed,
        "confirmed": {field: _confirmed_display(item, field) for field in confirmed_names},
        "missing_required": _missing_required(item),
        "next_question": question,
        "summary": _summary(item, question),
    }


def _next_question(item):
    if item.status == Item.Status.ARCHIVED:
        return None
    missing = _missing_required(item)
    if not missing:
        return None
    if item.photos.count() < 2:
        low = _first_low_label_field(item)
        if low is not None:
            return {
                "field": low,
                "prompt": (
                    "I couldn't read the brand and size confidently. "
                    "Can you upload a photo of the label?"
                ),
                "choices": None,
                "asks_for_photo": True,
            }
    field = missing[0]
    proposal = (item.proposals or {}).get(field)
    if proposal:
        prompt = (
            f"I think the {FIELD_LABELS[field]} is "
            f"{_display(field, proposal['value'])}. Should I keep that?"
        )
    else:
        prompt = ASK_PROMPTS[field]
    return {
        "field": field,
        "prompt": prompt,
        "choices": choice_options(field),
        "asks_for_photo": False,
    }


def _first_low_label_field(item):
    confirmed = set(item.confirmed_fields or [])
    proposals = item.proposals or {}
    for field in LABEL_PHOTO_FIELDS:
        if field in confirmed:
            continue
        proposal = proposals.get(field)
        if proposal is not None and proposal.get("confidence") == "low":
            return field
    return None


def _summary(item, question):
    if item.status == Item.Status.ARCHIVED:
        return "I've archived that draft."
    status = _intake_status(item)
    if status == "ready":
        return "Those details are confirmed. This item is ready for pricing and listing."
    if question and question.get("asks_for_photo"):
        return "I need a photo of the label before I can trust the brand and size."
    if status == "needs_confirmation":
        return "I read a few details from the photo. Please confirm them before I save them on the item."
    if question:
        return question["prompt"]
    return "I still need a few details."


def _intake_status(item):
    if item.status == Item.Status.ARCHIVED:
        return "archived"
    if not _missing_required(item):
        return "ready"
    if _pending_proposals(item):
        return "needs_confirmation"
    return "needs_details"


def _missing_required(item):
    confirmed = set(item.confirmed_fields or [])
    return [field for field in REQUIRED_FIELDS if field not in confirmed]


def _pending_proposals(item):
    missing = _missing_required(item)
    if not missing:
        return False
    if item.photos.count() < 2 and _first_low_label_field(item) is not None:
        return False
    return missing[0] in (item.proposals or {})


def _write_confirmed(item, field, value):
    setattr(item, field, column_value(field, value))
    confirmed = list(item.confirmed_fields or [])
    if field not in confirmed:
        confirmed.append(field)
    item.confirmed_fields = confirmed


def _save_confirmation(item, field):
    item.save(update_fields=["proposals", "confirmed_fields", field, "updated_at"])


def _confirmed_display(item, field):
    value = getattr(item, field)
    if field == "brand" and value == "":
        return "unbranded"
    return value


def _display(field, value):
    if field == "brand" and value in ("", "unbranded"):
        return "unbranded"
    choices = CHOICES.get(field)
    if choices is not None:
        return dict(choices.choices).get(value, value)
    return value


def _store_photo(item, data):
    position = _next_position(item)
    photo = ItemPhoto(item=item, position=position)
    photo.image.save(f"photo-{position}.jpg", ContentFile(data), save=True)
    return photo


def _next_position(item):
    current = item.photos.order_by("-position").first()
    if current is None:
        return 0
    return current.position + 1


def _owned_item(user, arguments):
    item_id = _require_item_id(arguments)
    try:
        item = Item.objects.get(pk=item_id)
    except Item.DoesNotExist as exc:
        raise ButtonsError("That item does not exist.") from exc
    if item.user_id != user.pk:
        raise ButtonsError("That item belongs to someone else.")
    return item


def _require_draft(item):
    if item.status != Item.Status.DRAFT:
        raise ButtonsError("That item is not an open draft.")


def _require_field(arguments):
    field = arguments.get("field")
    if field not in FIELD_ORDER:
        raise ButtonsError("field must be a detail Buttons can record.")
    return field


def _require_item_id(arguments):
    raw = arguments.get("item_id")
    if isinstance(raw, bool) or raw in (None, ""):
        raise ButtonsError("item_id is required.")
    if isinstance(raw, str) and raw.isdigit():
        raw = int(raw)
    if not isinstance(raw, int) or raw < 1:
        raise ButtonsError("item_id must be an integer.")
    return raw


def _read_image(grok, *, image_url, image_file_id):
    try:
        data = load_photo_bytes(grok, image_url=image_url, image_file_id=image_file_id)
        proposals = extract_photo(grok, image_url=image_url, image_file_id=image_file_id)
    except GrokError as exc:
        raise ButtonsError("I couldn't read that photo.") from exc
    return data, proposals


def _photo_reference(arguments):
    image_url = _blank_to_none(arguments.get("image_url"))
    image_file_id = _blank_to_none(arguments.get("image_file_id"))
    if (image_url is None) == (image_file_id is None):
        raise ButtonsError("Provide an image_url or an image_file_id.")
    return image_url, image_file_id


def _blank_to_none(value):
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value
