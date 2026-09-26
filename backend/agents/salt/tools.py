"""Tools Salt uses to hand work to the other agents.

The definitions are part of every chat request. Calls are not run yet:
Salt answers the seller directly until each specialist can take a job.
"""

from services.grok import responses_function_tool

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
        responses_function_tool(
            "willow",
            _REQUEST,
            description=(
                "Connect or refresh the seller's Vinted, Depop, or eBay session. "
                "Use when a marketplace login needs the seller or a stored session should be checked."
            ),
        ),
        responses_function_tool(
            "bobby",
            _REQUEST,
            description=(
                "Turn photos and item details into a listing: title, description, "
                "category, and attributes, adapted for Vinted, Depop, or eBay."
            ),
        ),
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
