"""The function schema Salt registers when she calls Buttons."""

from services.grok import responses_function_tool
from services.grok.errors import GrokError

from agents.buttons.errors import ButtonsError
from agents.buttons.schema import ACTIONS, FIELD_ORDER
from agents.buttons.service import handle as apply_buttons

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

BUTTONS_DESCRIPTION = (
    "Turn a seller's photo into a draft wardrobe item, then confirm, correct, "
    "or reject the details. Call read_photo with image_file_id or image_url. "
    "Call add_photo for another photo of the same item, including a label shot. "
    "Call confirm_field to accept one proposed field, apply_answer to store the "
    "seller's own value, confirm_item to accept every current proposal, or "
    "deny_item to archive the draft. Never send user_id. item_id is required "
    "after read_photo. When next_question asks for a label photo, call add_photo."
)


def buttons_schema():
    return responses_function_tool(
        "buttons",
        PARAMETERS,
        description=BUTTONS_DESCRIPTION,
    )


def handle_buttons(user, arguments, *, grok=None, browser=None):
    """Run one Buttons action. A refused photo or item comes back as a failed result."""
    if grok is None:
        from services.grok import GrokClient

        grok = GrokClient.from_environment()
    try:
        return apply_buttons(user, arguments, grok=grok)
    except (ButtonsError, GrokError) as exc:
        item_id = arguments.get("item_id") if isinstance(arguments, dict) else None
        if type(item_id) is not int:
            item_id = None
        return {
            "status": "failed",
            "item_id": item_id,
            "message": str(exc),
        }


def present_buttons(result, arguments):
    """Return the intake summary, or a failed result Salt can say back."""
    if isinstance(result, dict) and "summary" in result:
        return result
    password = arguments.get("password") if isinstance(arguments, dict) else None
    message = _plain(result.get("message") if isinstance(result, dict) else "", password)
    if not message:
        message = "That tool could not finish. Ask the seller to try again."
    item_id = result.get("item_id") if isinstance(result, dict) else None
    if type(item_id) is not int:
        item_id = None
    return {
        "status": "failed",
        "item_id": item_id,
        "message": message,
        "summary": message,
        "proposed": [],
        "confirmed": {},
        "missing_required": [],
        "next_question": None,
    }


def _plain(value, password):
    if not isinstance(value, str):
        return ""
    if isinstance(password, str) and len(password) >= 4 and password in value:
        value = value.replace(password, "")
    return " ".join(value.split())
