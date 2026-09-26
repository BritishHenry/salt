"""Chief of staff and primary chat interface.

Talks with the seller, understands requests, coordinates the other agents,
asks for approvals, and reports progress or problems.
"""

from agents.salt.agent import MODEL, REASONING_EFFORT, SaltAgent, SaltChatError, SaltEvent

__all__ = [
    "MODEL",
    "REASONING_EFFORT",
    "SaltAgent",
    "SaltChatError",
    "SaltEvent",
]
