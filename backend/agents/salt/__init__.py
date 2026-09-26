"""Chief of staff and primary chat interface.

Talks with the seller, understands requests, coordinates the other agents,
walks marketplace sign-in for Vinted, Depop, and eBay, asks for approvals,
and reports when a session needs the seller again before Maggie can publish.
"""

from agents.salt.agent import MODEL, REASONING_EFFORT, SaltAgent, SaltChatError, SaltEvent

__all__ = [
    "MODEL",
    "REASONING_EFFORT",
    "SaltAgent",
    "SaltChatError",
    "SaltEvent",
]
