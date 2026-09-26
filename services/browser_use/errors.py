"""Errors raised by the Browser Use cloud client."""


class BrowserUseError(Exception):
    """Base error for the Browser Use client."""


class BrowserUseConfigError(BrowserUseError):
    """The client is missing configuration it needs to call the API."""


class BrowserUseAPIError(BrowserUseError):
    """The Browser Use API rejected a request."""

    def __init__(self, status, detail, *, body=None):
        self.status = status
        self.detail = detail
        self.body = body
        super().__init__(f"Browser Use API {status}: {detail}")


class SessionBusy(BrowserUseAPIError):
    """The session already has an active run, so another run cannot start."""


class QueueFull(BrowserUseAPIError):
    """The session queue already holds its limit of pending messages."""


class BrowserUseTimeout(BrowserUseError):
    """The local wait ended before the cloud run did.

    The cloud run is still active. A wait timeout does not cancel it.
    """

    def __init__(self, run_id=None, *, session_id=None, message_id=None):
        self.run_id = run_id
        self.session_id = session_id
        self.message_id = message_id
        if message_id is not None and run_id is None:
            message = (
                f"Timed out waiting for message {message_id} to start. "
                "It is still queued; keep its id and poll it rather than sending it again."
            )
        else:
            message = (
                f"Timed out waiting for run {run_id}. "
                "The cloud run is still active; reconcile it before starting the same work again."
            )
        super().__init__(message)


class BrowserUseRunFailed(BrowserUseError):
    """The browser agent finished the run with status failed."""

    def __init__(self, run):
        self.run = run
        super().__init__(run.error or f"Run {run.id} failed.")


class BrowserUseRunCancelled(BrowserUseError):
    """The run ended because it was cancelled."""

    def __init__(self, run):
        self.run = run
        super().__init__(f"Run {run.id} was cancelled.")


class MessageNotDispatched(BrowserUseError):
    """A queued message ended without becoming a run."""

    def __init__(self, message):
        self.message = message
        super().__init__(
            f"Queued message {message.id} ended with status {message.status} and no run."
        )
