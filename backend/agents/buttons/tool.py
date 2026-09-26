"""The function schema Salt registers when she calls Buttons."""

from services.grok.builders import chat_function_tool

from agents.buttons.schema import ACTIONS, FIELD_ORDER

PARAMETERS = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action"],
    "properties": {
        "action": {
            "type": "string",
            "enum": list(ACTIONS),
            "description": (
                "read_photo starts a draft from the first photo. "
                "add_photo attaches another photo to that draft. "
                "confirm_field accepts one proposed value. "
                "apply_answer stores the seller's own value. "
                "confirm_item accepts every current proposal. "
                "deny_item archives the draft."
            ),
        },
        "item_id": {
            "type": "integer",
            "description": "Draft item id. Required for every action except read_photo.",
        },
        "image_url": {
            "type": "string",
            "description": "https URL or data:image URL of the photo. Omit when image_file_id is set.",
        },
        "image_file_id": {
            "type": "string",
            "description": "Grok Files API id for the photo. Omit when image_url is set.",
        },
        "field": {
            "type": "string",
            "enum": list(FIELD_ORDER),
            "description": "Item field to confirm or replace.",
        },
        "value": {
            "type": "string",
            "description": "Seller's value for field. Use unbranded when the garment has no brand.",
        },
    },
}

BUTTONS_TOOL = chat_function_tool(
    "buttons",
    PARAMETERS,
    description=(
        "Turn a seller's photo into a draft wardrobe item, then confirm, correct, "
        "or reject the details. Call read_photo with image_file_id or image_url. "
        "Call add_photo for another photo of the same item, including a label shot. "
        "Call confirm_field to accept one proposed field, apply_answer to store the "
        "seller's own value, confirm_item to accept every current proposal, or "
        "deny_item to archive the draft. Never send user_id. item_id is required "
        "after read_photo. When next_question asks for a label photo, call add_photo."
    ),
)
