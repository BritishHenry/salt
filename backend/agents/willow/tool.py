"""Willow as a function tool Salt can call."""

from services.grok import responses_function_tool

from agents.willow.service import check_session, connect_marketplace
from agents.willow.sites import SITES

WILLOW_DESCRIPTION = (
    "Connect or check the seller's Vinted, Depop, or eBay session. "
    "For connect, pass the password the seller just typed. It is encrypted "
    "before the browser runs and can be typed only on that marketplace. "
    "Never invent a password and never repeat it. Omit the password to reuse "
    "the encrypted one already stored. For check, omit the password. "
    "needs_login means that marketplace needs the seller again before Maggie can publish."
)

WILLOW_PARAMETERS = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["connect", "check"],
            "description": "connect signs in. check only looks at the saved session.",
        },
        "marketplace": {
            "type": "string",
            "enum": ["vinted", "depop", "ebay"],
            "description": "The marketplace to connect or check.",
        },
        "password": {
            "type": "string",
            "description": (
                "The seller just typed this. Do not invent it, and do not repeat it back. "
                "Willow encrypts it and does not keep the plaintext. "
                "Omit it when an encrypted password is already stored."
            ),
        },
    },
    "required": ["action", "marketplace"],
    "additionalProperties": False,
}


def willow_schema():
    return responses_function_tool(
        "willow",
        WILLOW_PARAMETERS,
        description=WILLOW_DESCRIPTION,
    )


def handle_willow(user, arguments, *, grok=None, browser=None):
    """Run one Willow action. Invalid arguments come back as a failed result."""
    action = arguments.get("action")
    marketplace = arguments.get("marketplace")
    if action not in {"connect", "check"}:
        return _failed(_slug(marketplace), "action must be connect or check.")
    if marketplace not in SITES:
        return _failed("", "marketplace must be vinted, depop, or ebay.")
    password = arguments.get("password")
    if "password" in arguments and not isinstance(password, str):
        return _failed(marketplace, "password must be a string.")
    if action == "check":
        return check_session(user, marketplace, client=browser)
    return connect_marketplace(user, marketplace, password or "", client=browser)


def _slug(marketplace):
    if isinstance(marketplace, str) and marketplace in SITES:
        return marketplace
    return ""


def _failed(marketplace, message):
    return {
        "marketplace": marketplace,
        "status": "failed",
        "external_username": "",
        "message": message,
    }
