"""Turn one garment photo into proposed item fields."""

import json

from services.grok.builders import (
    chat_json_schema_response_format,
    system_text_message,
    user_message_with_image,
)
from services.grok.constants import DEFAULT_TEXT_MODEL
from services.grok.errors import GrokError
from services.grok.parsing import extract_chat_message_text, parse_json_object

from agents.buttons.errors import ButtonsError
from agents.buttons.schema import (
    CHOICES,
    CONFIDENCE_LEVELS,
    EXTRACTION_SCHEMA,
    FIELD_ORDER,
    TEXT_LIMITS,
)

_INSTRUCTIONS = """You read a photo of a second-hand garment for a wardrobe inventory.
Return only details you can see. Use null when a detail is not visible.
Do not guess a brand, size, or condition.
Use the exact choice values from the schema.
confidence is high when the detail is clearly readable, medium when it is likely, and low when you are unsure.
evidence is a short note of where you saw it, such as "neck label" or "printed size tag".
"""


def extract_photo(grok, *, image_url=None, image_file_id=None):
    """Ask Grok to read a photo. Returns proposals keyed by item field."""
    try:
        response = grok.chat.create_chat_completion(
            model=DEFAULT_TEXT_MODEL,
            messages=[
                system_text_message(_INSTRUCTIONS),
                user_message_with_image(
                    "Read this garment photo and extract the item details.",
                    image_url=image_url,
                    image_file_id=image_file_id,
                ),
            ],
            response_format=chat_json_schema_response_format(
                "item_extraction",
                EXTRACTION_SCHEMA,
                strict=True,
            ),
            temperature=0,
        )
        payload = parse_json_object(extract_chat_message_text(response))
    except GrokError as exc:
        raise ButtonsError("I couldn't read that photo.") from exc
    except json.JSONDecodeError as exc:
        raise ButtonsError("I couldn't read that photo.") from exc
    return proposals_from_extraction(payload)


def proposals_from_extraction(payload):
    if not isinstance(payload, dict):
        raise ButtonsError("The photo reading was not an object.")
    proposals = {}
    for field in FIELD_ORDER:
        raw = payload.get(field)
        if raw is None:
            continue
        if not isinstance(raw, dict):
            raise ButtonsError(f"The reading for {field} was not an object.")
        value = raw.get("value")
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        confidence = raw.get("confidence")
        if confidence not in CONFIDENCE_LEVELS:
            raise ButtonsError(f"The confidence for {field} was not recognised.")
        evidence = raw.get("evidence", "")
        if evidence is None:
            evidence = ""
        if not isinstance(evidence, str):
            raise ButtonsError(f"The evidence for {field} must be text.")
        proposals[field] = {
            "value": clean_stored_value(field, value),
            "confidence": confidence,
            "evidence": evidence.strip()[:500],
        }
    return proposals


def clean_stored_value(field, value):
    """Validate a proposed or seller-supplied value. Brand 'unbranded' stays as that word."""
    if field not in FIELD_ORDER:
        raise ButtonsError(f"{field} is not a detail Buttons can record.")
    if field in CHOICES:
        return _choice_value(field, value)
    if not isinstance(value, str):
        raise ButtonsError(f"{field} must be text.")
    text = " ".join(value.split())
    if field == "brand" and text.lower() == "unbranded":
        return "unbranded"
    if not text:
        raise ButtonsError(f"{field} cannot be empty.")
    if len(text) > TEXT_LIMITS[field]:
        raise ButtonsError(f"{field} is too long.")
    return text


def column_value(field, value):
    """Value written onto the item. A confirmed unbranded brand is stored blank."""
    cleaned = clean_stored_value(field, value)
    if field == "brand" and cleaned == "unbranded":
        return ""
    return cleaned


def _choice_value(field, value):
    if not isinstance(value, str):
        raise ButtonsError(f"{field} must be one of the listed choices.")
    text = value.strip()
    choices = CHOICES[field]
    by_value = {choice.value: choice.value for choice in choices}
    by_label = {choice.label.lower(): choice.value for choice in choices}
    if text in by_value:
        return by_value[text]
    if text.lower() in by_label:
        return by_label[text.lower()]
    allowed = ", ".join(choice.value for choice in choices)
    raise ButtonsError(f"{field} must be one of: {allowed}.")
