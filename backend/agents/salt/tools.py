"""Tools Salt uses to hand work to the other agents.

The definitions are part of every chat request. Willow and Bobby can be run
through call_tool. The other specialists are still descriptions only, and this
chat turn answers the seller directly.
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
        responses_function_tool(
            "maggie",
            _REQUEST,
            description=(
                "Publish an approved listing, check its status, apply an update, "
                "or remove the other marketplace listings when an item sells."
            ),
        ),
        responses_function_tool(
            "steve",
            _REQUEST,
            description=(
                "Answer a buyer from verified item details, or haggle within the "
                "seller's limits. Unusual requests come back to Salt."
            ),
        ),
    ]
