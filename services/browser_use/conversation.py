"""A live conversation with one Browser Use cloud agent."""

from services.browser_use.errors import BrowserUseTimeout
from services.browser_use.models import UNSET


class Conversation:
    """One cloud session an agent can task, watch, and reply to.

    Use it as a context manager. Leaving the block stops the cloud browser
    after a finished, failed, or cancelled run. A :class:`BrowserUseTimeout`
    leaves the browser up so the run can keep going::

        browser = BrowserUseClient()
        with browser.conversation("Find navy coats on Vinted under £20") as chat:
            first = chat.wait()
            chat.send("Open the cheapest listing and copy the seller name")
            second = chat.wait()
    """

    def __init__(self, client, run):
        self.client = client
        self.session_id = run.session_id
        self.workspace_id = run.workspace_id
        self.latest_run_id = run.id
        self._pending = None
        self._closed = False

    def send(self, text, *, interrupt=False, attached_file_ids=None):
        """Tell the browser agent something else.

        The message waits on the session queue when a run is in progress.
        """
        message = self.client.send(
            self.session_id,
            text,
            interrupt=interrupt,
            attached_file_ids=attached_file_ids,
        )
        self._pending = message
        if message.run_id:
            self.latest_run_id = message.run_id
        return message

    def wait(self, *, timeout=UNSET, poll_interval=None, raise_on_error=True):
        """Wait for the latest instruction to finish.

        A message that has not been dispatched yet is polled first. The
        timeout covers that wait and the run together.
        """
        if timeout is UNSET:
            timeout = self.client.wait_timeout
        deadline = None if timeout is None else self.client._monotonic() + timeout
        if self._pending is not None and self._pending.run_id is None:
            remaining = None if deadline is None else max(0, deadline - self.client._monotonic())
            message = self.client.wait_for_dispatch(
                self.session_id,
                self._pending.id,
                timeout=remaining,
                poll_interval=poll_interval,
            )
            self._pending = message
            self.latest_run_id = message.run_id
        remaining = None if deadline is None else max(0, deadline - self.client._monotonic())
        run = self.client.wait(
            self.latest_run_id,
            timeout=remaining,
            poll_interval=poll_interval,
            raise_on_error=raise_on_error,
            session_id=self.session_id,
        )
        self._pending = None
        return run

    def events(self, *, after=None, timeout=UNSET, poll_interval=None):
        """Stream events from the latest run."""
        return self.client.iter_events(
            self.latest_run_id,
            after=after,
            timeout=timeout,
            poll_interval=poll_interval,
        )

    def live_url(self):
        """Return the live view URL for this conversation's active browser."""
        browsers = self.client.list_browsers(agent_session_id=self.session_id, status="active")
        for browser in browsers:
            if browser.live_url:
                return browser.live_url
        return None

    def cancel(self):
        """Cancel the latest run."""
        return self.client.cancel(self.latest_run_id)

    def close(self):
        """Stop cloud browsers owned by this conversation."""
        if self._closed:
            return ()
        self._closed = True
        return self.client.release(self.session_id)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not BrowserUseTimeout:
            self.close()
        return False
