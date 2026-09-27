"""Chief of staff and primary chat interface.

Talks with the seller, understands requests, and calls the other agents.
Willow signs in to an existing Vinted, Depop, or eBay account. Salt does not.
She asks for approvals and reports when a session needs the seller again
before Maggie can publish.
"""

from agents.salt.agent import MODEL, REASONING_EFFORT, SaltAgent, SaltChatError, SaltEvent

__all__ = [
    "MODEL",
    "REASONING_EFFORT",
    "SaltAgent",
    "SaltChatError",
    "SaltEvent",
]
