"""Client for handing work to Browser Use cloud agents.

Agents call :meth:`BrowserUseClient.assign` or :meth:`BrowserUseClient.conversation`
with a task. The cloud agent runs it in a hosted browser. Follow-up messages
continue the same session, queueing behind a busy run instead of starting a
second one.
"""

import os
import time
from urllib.parse import quote

from services.browser_use.errors import (
    BrowserUseConfigError,
    BrowserUseError,
    BrowserUseRunCancelled,
    BrowserUseRunFailed,
    BrowserUseTimeout,
    MessageNotDispatched,
    SessionBusy,
)
from services.browser_use.models import (
    MESSAGE_DONE_STATUSES,
    UNSET,
    Assignment,
    CloudBrowser,
    EventPage,
    QueuedMessage,
    Run,
    Session,
)
from services.browser_use.transport import DEFAULT_BASE_URL, UrllibTransport


class BrowserUseClient:
    """Talks to Browser Use API v4 using ``BROWSER_USE_API_KEY``.

    The key is sent as ``X-Browser-Use-API-Key`` with no Bearer prefix.
    Poll ``GET /runs/{id}/status`` until the run is terminal, then read the
    full run once. A local wait timeout does not cancel the cloud run.
    """

    def __init__(
        self,
        api_key=None,
        *,
        base_url=DEFAULT_BASE_URL,
        timeout=30,
        poll_interval=2,
        wait_timeout=600,
        transport=None,
        sleep=time.sleep,
        monotonic=time.monotonic,
    ):
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        if transport is None:
            key = api_key if api_key is not None else os.environ.get("BROWSER_USE_API_KEY", "")
            key = key.strip()
            if not key:
                raise BrowserUseConfigError(
                    "BROWSER_USE_API_KEY is not set. Add it to backend/.env."
                )
            transport = UrllibTransport(
                key,
                base_url=base_url,
                timeout=timeout,
                sleep=sleep,
            )
        self._transport = transport
        self._sleep = sleep
        self._monotonic = monotonic
        self.poll_interval = poll_interval
        self.wait_timeout = wait_timeout

    def create_run(
        self,
        task,
        *,
        model=None,
        session_id=None,
        workspace_id=None,
        output_schema=None,
        max_cost_usd=None,
        model_params=None,
        profile_id=None,
        proxy_country_code=UNSET,
        record=None,
        attached_file_ids=None,
    ):
        """Start a browser agent on ``task``.

        Pass ``session_id`` to continue a conversation whose latest run has
        finished. A session that still has an active run raises
        :class:`SessionBusy`; use :meth:`send` to queue the next instruction.
        ``proxy_country_code=None`` disables the proxy. Leave it unset to
        accept the API default.
        """
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")
        browser_settings = {}
        if profile_id is not None:
            browser_settings["profileId"] = profile_id
        if proxy_country_code is not UNSET:
            browser_settings["proxyCountryCode"] = proxy_country_code
        if record is not None:
            browser_settings["record"] = record
        body = {"task": task}
        optional = {
            "model": model,
            "sessionId": session_id,
            "workspaceId": workspace_id,
            "outputSchema": output_schema,
            "maxCostUsd": max_cost_usd,
            "modelParams": model_params,
            "attachedFileIds": attached_file_ids,
        }
        for key, value in optional.items():
            if value is not None:
                body[key] = value
        if browser_settings:
            body["browserSettings"] = browser_settings
        payload = self._transport.request("POST", "/runs", json_body=body)
        return Run.from_api(payload)

    def assign(self, task, *, session_id=None, interrupt=False, **run_options):
        """Pass a task to a browser agent and keep the conversation.

        A new ``session_id`` starts a conversation. An idle session gets
        another run. A busy session queues the text, and ``interrupt=True``
        asks the active run to stop so this instruction can start now.
        Options such as ``model`` apply only when a new run is created.
        """
        attached_file_ids = run_options.get("attached_file_ids")
        if session_id and interrupt:
            message = self.send(
                session_id,
                task,
                interrupt=True,
                attached_file_ids=attached_file_ids,
            )
            return Assignment(session_id=session_id, message=message)
        try:
            run = self.create_run(task, session_id=session_id, **run_options)
        except SessionBusy:
            if not session_id:
                raise
            message = self.send(session_id, task, attached_file_ids=attached_file_ids)
            return Assignment(session_id=session_id, message=message)
        return Assignment(session_id=run.session_id, run=run)

    def get_run(self, run_id):
        payload = self._transport.request("GET", f"/runs/{quote(run_id)}")
        return Run.from_api(payload)

    def get_status(self, run_id):
        payload = self._transport.request("GET", f"/runs/{quote(run_id)}/status")
        return payload["status"]

    def wait(
        self,
        run_id,
        *,
        timeout=UNSET,
        poll_interval=None,
        raise_on_error=True,
        session_id=None,
    ):
        """Poll run status until it finishes, then fetch the summary once.

        ``timeout=None`` waits until the run is terminal. The default is
        :attr:`wait_timeout`. Timing out raises :class:`BrowserUseTimeout`
        and leaves the cloud run running.
        """
        if timeout is UNSET:
            timeout = self.wait_timeout
        interval = self.poll_interval if poll_interval is None else poll_interval
        if interval <= 0:
            raise ValueError("poll_interval must be positive")
        deadline = None if timeout is None else self._monotonic() + timeout
        while True:
            status = self.get_status(run_id)
            if status in {"completed", "failed", "cancelled"}:
                run = self.get_run(run_id)
                return self._raise_for_run(run, raise_on_error)
            if deadline is not None and self._monotonic() >= deadline:
                raise BrowserUseTimeout(run_id, session_id=session_id)
            self._pause(interval, deadline, BrowserUseTimeout(run_id, session_id=session_id))

    def wait_assignment(self, assignment, **wait_options):
        """Wait for an :meth:`assign` result, including a message still queued."""
        if assignment.run is None and assignment.message is None:
            raise ValueError("assignment has neither a run nor a message")
        timeout = wait_options.get("timeout", UNSET)
        if timeout is UNSET:
            timeout = self.wait_timeout
        poll_interval = wait_options.get("poll_interval")
        raise_on_error = wait_options.get("raise_on_error", True)
        deadline = None if timeout is None else self._monotonic() + timeout
        run_id = assignment.run.id if assignment.run else None
        if assignment.message is not None:
            if assignment.message.run_id is None:
                remaining = None if deadline is None else max(0, deadline - self._monotonic())
                message = self.wait_for_dispatch(
                    assignment.session_id,
                    assignment.message.id,
                    timeout=remaining,
                    poll_interval=poll_interval,
                )
                run_id = message.run_id
            elif run_id is None:
                run_id = assignment.message.run_id
        remaining = None if deadline is None else max(0, deadline - self._monotonic())
        return self.wait(
            run_id,
            timeout=remaining,
            poll_interval=poll_interval,
            raise_on_error=raise_on_error,
            session_id=assignment.session_id,
        )

    def run(self, task, *, timeout=UNSET, **run_options):
        """Run one task to completion, then stop the browser it opened.

        A timeout leaves both the run and its browser active.
        """
        created = self.create_run(task, **run_options)
        try:
            finished = self.wait(
                created.id,
                timeout=timeout,
                raise_on_error=False,
                session_id=created.session_id,
            )
        except BrowserUseTimeout:
            raise
        except Exception as exc:
            if getattr(exc, "run_id", None) is None:
                exc.run_id = created.id
            if getattr(exc, "session_id", None) is None:
                exc.session_id = created.session_id
            self.release(created.session_id)
            raise
        self.release(created.session_id)
        return self._raise_for_run(finished, True)

    def cancel(self, run_id):
        """Cancel an in-flight run. A run that already finished is returned as-is."""
        payload = self._transport.request("POST", f"/runs/{quote(run_id)}/cancel")
        return Run.from_api(payload)

    def get_events(self, run_id, *, after=None, limit=None):
        query = {"after": after, "limit": limit}
        payload = self._transport.request("GET", f"/runs/{quote(run_id)}/events", query=query)
        return EventPage.from_api(payload)

    def iter_events(self, run_id, *, after=None, timeout=UNSET, poll_interval=None):
        """Yield run events in order.

        Status is read before each fetch so the last page is drained after the
        run becomes terminal. ``hasMore`` pages are fetched immediately.
        """
        if timeout is UNSET:
            timeout = self.wait_timeout
        interval = self.poll_interval if poll_interval is None else poll_interval
        if interval <= 0:
            raise ValueError("poll_interval must be positive")
        deadline = None if timeout is None else self._monotonic() + timeout
        cursor = after
        while True:
            status = self.get_status(run_id)
            requested = cursor
            page = self.get_events(run_id, after=cursor)
            yield from page.events
            advanced = page.next_after
            if advanced is None and page.events:
                advanced = page.events[-1].id
            if page.has_more:
                if advanced is None or advanced == requested:
                    raise BrowserUseError("Browser Use returned hasMore without a new cursor.")
                cursor = advanced
                continue
            if advanced is not None:
                cursor = advanced
            if status in {"completed", "failed", "cancelled"}:
                return
            if deadline is not None and self._monotonic() >= deadline:
                raise BrowserUseTimeout(run_id)
            self._pause(interval, deadline, BrowserUseTimeout(run_id))

    def get_session(self, session_id):
        payload = self._transport.request("GET", f"/sessions/{quote(session_id)}")
        return Session.from_api(payload)

    def send(self, session_id, text, *, interrupt=False, attached_file_ids=None):
        """Queue an instruction on a session.

        A busy session runs it as the next turn. An idle session starts it
        immediately. ``interrupt=True`` cancels the active run first.
        Keep the returned message id and poll :meth:`get_message`; do not
        send the text again to check on it.
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        body = {"text": text, "interrupt": interrupt}
        if attached_file_ids is not None:
            body["attachedFileIds"] = attached_file_ids
        payload = self._transport.request(
            "POST",
            f"/sessions/{quote(session_id)}/queue",
            json_body=body,
        )
        return QueuedMessage.from_api(payload)

    def get_message(self, session_id, message_id):
        payload = self._transport.request(
            "GET",
            f"/sessions/{quote(session_id)}/queue/{quote(str(message_id))}",
        )
        return QueuedMessage.from_api(payload)

    def list_messages(self, session_id):
        payload = self._transport.request("GET", f"/sessions/{quote(session_id)}/queue") or {}
        return tuple(QueuedMessage.from_api(item) for item in payload.get("queue", ()))

    def cancel_message(self, session_id, message_id):
        """Remove a message that is still pending. A claimed message returns 409."""
        payload = self._transport.request(
            "DELETE",
            f"/sessions/{quote(session_id)}/queue/{quote(str(message_id))}",
        )
        return QueuedMessage.from_api(payload)

    def wait_for_dispatch(self, session_id, message_id, *, timeout=UNSET, poll_interval=None):
        """Poll a queued message until it has a run id.

        Timing out leaves the message on the queue.
        """
        if timeout is UNSET:
            timeout = self.wait_timeout
        interval = self.poll_interval if poll_interval is None else poll_interval
        if interval <= 0:
            raise ValueError("poll_interval must be positive")
        deadline = None if timeout is None else self._monotonic() + timeout
        while True:
            message = self.get_message(session_id, message_id)
            if message.run_id:
                return message
            if message.status in MESSAGE_DONE_STATUSES:
                raise MessageNotDispatched(message)
            if deadline is not None and self._monotonic() >= deadline:
                raise BrowserUseTimeout(session_id=session_id, message_id=message_id)
            self._pause(
                interval,
                deadline,
                BrowserUseTimeout(session_id=session_id, message_id=message_id),
            )

    def list_browsers(self, *, agent_session_id=None, status=None):
        payload = self._transport.request(
            "GET",
            "/browsers",
            query={
                "agentSessionId": agent_session_id,
                "filterBy": status,
                "pageSize": 100,
            },
        ) or {}
        return tuple(CloudBrowser.from_api(item) for item in payload.get("items", ()))

    def get_browser(self, browser_id):
        payload = self._transport.request("GET", f"/browsers/{quote(browser_id)}")
        return CloudBrowser.from_api(payload)

    def stop_browser(self, browser_id):
        """Stop a managed browser. Closing CDP does not do this."""
        payload = self._transport.request(
            "PATCH",
            f"/browsers/{quote(browser_id)}",
            json_body={"action": "stop"},
        )
        return CloudBrowser.from_api(payload)

    def release(self, session_id):
        """Stop active browsers owned by a conversation.

        A finished run leaves its cloud browser running, so call this when
        the conversation is done.
        """
        stopped = []
        for browser in self.list_browsers(agent_session_id=session_id, status="active"):
            stopped.append(self.stop_browser(browser.id))
        return tuple(stopped)

    def conversation(self, task, **run_options):
        """Start a task and return a handle for follow-up messages."""
        from services.browser_use.conversation import Conversation

        run = self.create_run(task, **run_options)
        return Conversation(self, run)

    def _pause(self, interval, deadline, timeout_error):
        delay = interval
        if deadline is not None:
            delay = min(delay, deadline - self._monotonic())
        if delay <= 0:
            raise timeout_error
        self._sleep(delay)

    @staticmethod
    def _raise_for_run(run, raise_on_error):
        if not raise_on_error:
            return run
        if run.status == "failed":
            raise BrowserUseRunFailed(run)
        if run.status == "cancelled":
            raise BrowserUseRunCancelled(run)
        return run
