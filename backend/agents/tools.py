"""Tools Salt calls. Each one has a Grok Responses schema and a handler."""

from agents.willow.tool import handle_willow, willow_schema


class Tool:
    def __init__(self, name, schema, handler):
        self.name = name
        self.schema = schema
        self.handler = handler


TOOLS = {
    "willow": Tool("willow", willow_schema(), handle_willow),
}


def call_tool(name, user, arguments):
    """Run a specialist tool and return a result Salt can say back.

    Unknown names and invalid arguments are failed results. They are not
    exceptions, and a password in the arguments is left out of the result.
    """
    tool = TOOLS.get(name) if isinstance(name, str) else None
    if tool is None:
        shown = name if isinstance(name, str) and name else "that"
        return _result("", "failed", "", f"Unknown tool {shown}.")
    if not isinstance(arguments, dict):
        return _result("", "failed", "", "Tool arguments must be an object.")
    try:
        result = tool.handler(user, arguments)
    except Exception:
        return _result("", "failed", "", "That tool could not finish. Ask the seller to try again.")
    if not isinstance(result, dict):
        return _result("", "failed", "", "That tool could not finish. Ask the seller to try again.")
    return _clean(result, arguments)


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


def _result(marketplace, status, external_username, message):
    return {
        "marketplace": marketplace,
        "status": status,
        "external_username": external_username,
        "message": message,
    }
