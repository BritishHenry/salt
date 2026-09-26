"""Tools Salt uses to hand work to the other agents.

The definitions are part of every chat request. Willow, Bobby, Maggie, and Steve
can be run through call_tool. Jacob is still a description only, and this chat
turn answers the seller directly.
"""

from services.grok import responses_function_tool

from agents.tools import TOOLS

_REQUEST = {
    "type": "object",
    "properties": {
        "request": {
            "type": "string",
            "description": "What the seller needs this agent to do, in one plain request.",
        }
    },
    "required": ["request"],
    "additionalProperties": False,
}


def specialist_tools():
    """Function tools for Willow, Bobby, Jacob, Maggie, and Steve."""
    return [
        TOOLS["willow"].schema,
        TOOLS["bobby"].schema,
        responses_function_tool(
            "jacob",
            _REQUEST,
            description=(
                "Recommend one list price from comparable listings on Vinted, Depop, "
                "and eBay, including condition and size."
            ),
        ),
        TOOLS["maggie"].schema,
        TOOLS["steve"].schema,
    ]
