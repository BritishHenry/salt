"""Tools Salt calls. Each one has a Grok Responses schema, a handler, and a presenter."""

from agents.bobby.tool import bobby_schema, handle_bobby, present_bobby
from agents.steve.tool import handle_steve, present_steve, steve_schema
from agents.willow.tool import handle_willow, willow_schema


class Tool:
    def __init__(self, name, schema, handler, present):
        self.name = name
        self.schema = schema
        self.handler = handler
        self.present = present


def call_tool(name, user, arguments, *, grok=None, browser=None):
    """Run a specialist tool and return a result Salt can say back.

    Unknown names and invalid arguments are failed results. They are not
    exceptions, and a password in the arguments is left out of the result.
    grok and browser are the clients a handler may use. Tests pass fakes.
    """
    tool = TOOLS.get(name) if isinstance(name, str) else None
    if tool is None:
        shown = name if isinstance(name, str) and name else "that"
        return _result("", "failed", "", f"Unknown tool {shown}.")
    if not isinstance(arguments, dict):
        return tool.present(
            {"status": "failed", "message": "Tool arguments must be an object."},
            {},
        )
    try:
        result = tool.handler(user, arguments, grok=grok, browser=browser)
    except Exception:
        return tool.present(_crashed(arguments), arguments)
    if not isinstance(result, dict):
        return tool.present(_crashed(arguments), arguments)
    return tool.present(result, arguments)


def _clean(result, arguments):
    password = arguments.get("password")
    status = result.get("status")
    if status not in {"connected", "needs_login", "failed"}:
        status = "failed"
    message = _text(result.get("message"), password)
    if not message:
        message = "That tool could not finish. Ask the seller to try again."
    return _result(
        _text(result.get("marketplace"), password),
        status,
        _text(result.get("external_username"), password),
        message,
    )


def _text(value, password):
    if not isinstance(value, str):
        return ""
    if isinstance(password, str) and len(password) >= 4 and password in value:
        value = value.replace(password, "")
    return " ".join(value.split())


def _crashed(arguments):
    payload = {
        "status": "failed",
        "message": "That tool could not finish. Ask the seller to try again.",
    }
    item_id = arguments.get("item_id") if isinstance(arguments, dict) else None
    if type(item_id) is int and item_id >= 1:
        payload["item_id"] = item_id
    return payload


def _result(marketplace, status, external_username, message):
    return {
        "marketplace": marketplace,
        "status": status,
        "external_username": external_username,
        "message": message,
    }


TOOLS = {
    "willow": Tool("willow", willow_schema(), handle_willow, _clean),
    "bobby": Tool("bobby", bobby_schema(), handle_bobby, present_bobby),
    "steve": Tool("steve", steve_schema(), handle_steve, present_steve),
}
