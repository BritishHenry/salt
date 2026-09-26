"""Fields Buttons can read from a photo, and the JSON schema she asks Grok to fill."""

from listings.models import Item

CONFIDENCE_LEVELS = ("high", "medium", "low")

# Order is the order Salt asks the seller about required gaps.
REQUIRED_FIELDS = (
    "category",
    "brand",
    "colour",
    "size_label",
    "size_system",
    "condition",
)

LABEL_PHOTO_FIELDS = ("brand", "size_label", "size_system")

TEXT_LIMITS = {
    "title": 255,
    "garment_type": 64,
    "brand": 255,
    "colour": 64,
    "colour_secondary": 64,
    "size_label": 64,
    "material": 255,
    "flaws": 4000,
}

CHOICES = {
    "department": Item.Department,
    "category": Item.Category,
    "size_system": Item.SizeSystem,
    "condition": Item.Condition,
}

FIELD_LABELS = {
    "title": "title",
    "department": "department",
    "category": "category",
    "garment_type": "garment type",
    "brand": "brand",
    "colour": "colour",
    "colour_secondary": "second colour",
    "size_label": "size",
    "size_system": "size system",
    "condition": "condition",
    "material": "material",
    "flaws": "flaws",
}

FIELD_ORDER = (
    "title",
    "department",
    "category",
    "garment_type",
    "brand",
    "colour",
    "colour_secondary",
    "size_label",
    "size_system",
    "condition",
    "material",
    "flaws",
)

ASK_PROMPTS = {
    "category": "Which category should I use?",
    "brand": "What brand is it? Say unbranded if there isn't one.",
    "colour": "What colour is it?",
    "size_label": "What size is printed on the label?",
    "size_system": "Which size system is that?",
    "condition": "What condition is it in?",
}

ACTIONS = (
    "read_photo",
    "add_photo",
    "confirm_field",
    "apply_answer",
    "confirm_item",
    "deny_item",
)


def _nullable_text():
    return {"anyOf": [{"type": "string"}, {"type": "null"}]}


def _nullable_choice(values):
    return {
        "anyOf": [
            {"type": "string", "enum": list(values)},
            {"type": "null"},
        ]
    }


def _reading(value_schema):
    return {
        "anyOf": [
            {"type": "null"},
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["value", "confidence", "evidence"],
                "properties": {
                    "value": value_schema,
                    "confidence": {"type": "string", "enum": list(CONFIDENCE_LEVELS)},
                    "evidence": {"type": "string"},
                },
            },
        ]
    }


def _value_schema(field):
    choices = CHOICES.get(field)
    if choices is not None:
        return _nullable_choice(choices.values)
    return _nullable_text()


EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(FIELD_ORDER),
    "properties": {field: _reading(_value_schema(field)) for field in FIELD_ORDER},
}


def choice_options(field):
    choices = CHOICES.get(field)
    if choices is None:
        return None
    return [{"value": value, "label": label} for value, label in choices.choices]
