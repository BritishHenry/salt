"""Hand tasks to Browser Use cloud agents and keep a conversation with them.

Set ``BROWSER_USE_API_KEY`` (see ``backend/.env.example``). The client uses
API v4: a session is the conversation, a run is one turn, and a follow-up
sent while a run is busy waits on that session's queue.

    from services.browser_use import BrowserUseClient

    browser = BrowserUseClient()
    with browser.conversation("Find the top Hacker News story") as chat:
        first = chat.wait()
        chat.send("Summarize that story in one sentence")
        second = chat.wait()
"""

from services.browser_use.client import BrowserUseClient
from services.browser_use.conversation import Conversation
from services.browser_use.errors import (
    BrowserUseAPIError,
    BrowserUseConfigError,
    BrowserUseError,
    BrowserUseRunCancelled,
    BrowserUseRunFailed,
    BrowserUseTimeout,
    MessageNotDispatched,
    QueueFull,
    SessionBusy,
)
from services.browser_use.models import (
    MODELS,
    Assignment,
    CloudBrowser,
    Profile,
    ProfilePage,
    QueuedMessage,
    Run,
    RunEvent,
    Secret,
    Session,
    Workspace,
    WorkspaceUpload,
)

__all__ = [
    "MODELS",
    "Assignment",
    "BrowserUseAPIError",
    "BrowserUseClient",
    "BrowserUseConfigError",
    "BrowserUseError",
    "BrowserUseRunCancelled",
    "BrowserUseRunFailed",
    "BrowserUseTimeout",
    "CloudBrowser",
    "Conversation",
    "MessageNotDispatched",
    "Profile",
    "ProfilePage",
    "QueueFull",
    "QueuedMessage",
    "Run",
    "RunEvent",
    "Secret",
    "Session",
    "SessionBusy",
    "Workspace",
    "WorkspaceUpload",
]
