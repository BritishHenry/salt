"""Tools Salt uses to hand work to the other agents.

The definitions are part of every chat request. Willow, Bobby, Jacob, Buttons,
Maggie, and Steve can be run through call_tool.
"""

from agents.tools import TOOLS


def specialist_tools():
    """Function tools for the specialists Salt can run."""
    return [
        TOOLS["willow"].schema,
        TOOLS["bobby"].schema,
        TOOLS["jacob"].schema,
        TOOLS["buttons"].schema,
        TOOLS["maggie"].schema,
        TOOLS["steve"].schema,
    ]
