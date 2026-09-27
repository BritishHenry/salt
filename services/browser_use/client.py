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
    Profile,
    ProfilePage,
    Workspace,
    WorkspaceUpload,
    QueuedMessage,
    Run,
    Secret,
    Session,
)

_MAX_SECRET_BINDINGS = 10
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
        secret_bindings=None,
    ):
        """Start a browser agent on ``task``.

        Pass ``session_id`` to continue a conversation whose latest run has
        finished. A session that still has an active run raises
        :class:`SessionBusy`; use :meth:`send` to queue the next instruction.
        ``proxy_country_code=None`` disables the proxy. Leave it unset to
        accept the API default.

        ``secret_bindings`` are passwords the server may type during this run.
        They are not stored on the profile and cannot be queued onto a busy
        session. Sign in with :meth:`run` so the browser stops and its cookies
        stay on ``profile_id``.
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
            "secretBindings": _secret_bindings_body(secret_bindings),
        }
        for key, value in optional.items():
            if value is not None:
                body[key] = value
        if browser_settings:
            body["browserSettings"] = browser_settings
        payload = self._transport.request("POST", "/runs", json_body=body)
        return Run.from_api(payload)

    def create_workspace(self):
        """Create an empty workspace that can hold files for one run."""
        payload = self._transport.request("POST", "/workspaces", json_body={})
        if not isinstance(payload, dict):
            raise BrowserUseError("Browser Use did not return a workspace.")
        workspace_id = payload.get("id") or payload.get("workspaceId")
        if not isinstance(workspace_id, str) or not workspace_id:
            raise BrowserUseError("Browser Use did not return a workspace id.")
        return workspace_id

    def upload_workspace_file(self, workspace_id, *, filename, content, content_type):
        """Upload one file and return its id.

        The API returns a presigned URL. The bytes are PUT there without the API key.
        """
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise ValueError("content must be non-empty bytes")
        payload = self._transport.request(
            "POST",
            f"/workspaces/{quote(str(workspace_id))}/files/upload",
            json_body={
                "fileName": filename,
                "contentType": content_type,
                "sizeBytes": len(content),
            },
        )
        if not isinstance(payload, dict):
            raise BrowserUseError("Browser Use did not return an upload.")
        file_id = payload.get("fileId") or payload.get("id")
        upload_url = payload.get("uploadUrl") or payload.get("url")
        if not isinstance(file_id, str) or not file_id or not isinstance(upload_url, str):
            raise BrowserUseError("Browser Use did not return an upload URL.")
        self._transport.put_bytes(upload_url, bytes(content), content_type=content_type)
        return file_id

    def assign(self, task, *, session_id=None, interrupt=False, **run_options):
        """Pass a task to a browser agent and keep the conversation.

        A new ``session_id`` starts a conversation. An idle session gets
        another run. A busy session queues the text, and ``interrupt=True``
        asks the active run to stop so this instruction can start now.
        Options such as ``model`` apply only when a new run is created.
        ``secret_bindings`` cannot be queued; a busy session raises
        ``ValueError`` instead of sending the password as message text.
        """
        attached_file_ids = run_options.get("attached_file_ids")
        if run_options.get("secret_bindings") and session_id and interrupt:
            raise ValueError("secret_bindings cannot be queued; start a new run")
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
            if run_options.get("secret_bindings"):
                raise ValueError("secret_bindings cannot be queued; start a new run") from None
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

    def create_workspace(self, name=None):
        """Create an empty workspace for files uploaded before a run starts.

        Pass the returned id as ``workspace_id`` on :meth:`create_run`.
        """
        body = {}
        if name is not None:
            label = _profile_label(name, "name", 100)
            if label is not None:
                body["name"] = label
        payload = self._transport.request("POST", "/workspaces", json_body=body)
        return Workspace.from_api(payload)

    def upload_workspace_files(self, workspace_id, files):
        """Presign workspace uploads and PUT each file.

        ``files`` is a sequence of mappings with ``name``, ``data``, and
        ``content_type``. The returned ids are what ``attached_file_ids``
        expects on :meth:`create_run`. The presigned PUT does not send the
        API key.
        """
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise ValueError("workspace_id must be a non-empty string")
        prepared = _upload_items(files)
        payload = self._transport.request(
            "POST",
            f"/workspaces/{quote(workspace_id)}/files/upload",
            json_body={
                "files": [
                    {
                        "name": item["name"],
                        "size": len(item["data"]),
                        "contentType": item["content_type"],
                    }
                    for item in prepared
                ]
            },
        )
        returned = payload.get("files") if isinstance(payload, dict) else None
        if not isinstance(returned, list) or len(returned) != len(prepared):
            raise BrowserUseError("Browser Use did not return an upload for every file.")
        uploads = []
        for item, meta in zip(returned, prepared):
            upload = WorkspaceUpload.from_api(item)
            self._transport.put_bytes(upload.upload_url, meta["data"], meta["content_type"])
            uploads.append(upload)
        return tuple(uploads)

    def create_profile(self, name=None, user_id=None):
        """Create an empty browser profile and return it.

        Pass ``user_id`` so the profile can be found later with
        :meth:`list_profiles`. The profile has no logins until a run that
        loads it signs in and the browser is stopped.
        """
        body = {}
        name = None if name is None else _profile_label(name, "name", 100)
        user_id = None if user_id is None else _profile_label(user_id, "user_id", 255)
        if name is not None:
            body["name"] = name
        if user_id is not None:
            body["userId"] = user_id
        payload = self._transport.request("POST", "/profiles", json_body=body)
        return Profile.from_api(payload)

    def get_profile(self, profile_id):
        """Return a profile, including the domains it has cookies for."""
        payload = self._transport.request("GET", f"/profiles/{quote(profile_id)}")
        return Profile.from_api(payload)

    def list_profiles(self, query=None, page_size=None, page_number=None):
        """List profiles. ``query`` matches a profile name or ``user_id``."""
        payload = self._transport.request(
            "GET",
            "/profiles",
            query={
                "query": query,
                "pageSize": page_size,
                "pageNumber": page_number,
            },
        )
        return ProfilePage.from_api(payload)

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


def _profile_label(value, field, limit):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    label = value.strip()
    if not label:
        return None
    if len(label) > limit:
        raise ValueError(f"{field} must be at most {limit} characters")
    return label


_MAX_UPLOAD_BYTES = 52_428_800
_MAX_UPLOAD_FILES = 10


def _upload_items(files):
    if isinstance(files, (str, bytes)) or not isinstance(files, (list, tuple)):
        raise ValueError("files must be a list")
    if not 1 <= len(files) <= _MAX_UPLOAD_FILES:
        raise ValueError("files must contain 1 to 10 files")
    prepared = []
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("each file must include name, data, and content_type")
        name = item.get("name")
        data = item.get("data")
        content_type = item.get("content_type") or "application/octet-stream"
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 255:
            raise ValueError("file name must be 1 to 255 characters")
        if "/" in name or "\\" in name:
            raise ValueError("file name must not include a path")
        if not isinstance(data, (bytes, bytearray)) or len(data) < 1:
            raise ValueError("file data must be non-empty bytes")
        if len(data) > _MAX_UPLOAD_BYTES:
            raise ValueError("file data must be 50MB or smaller")
        if (
            not isinstance(content_type, str)
            or not content_type.strip()
            or len(content_type.strip()) > 255
        ):
            raise ValueError("content_type must be a mime type")
        prepared.append(
            {
                "name": name.strip(),
                "data": bytes(data),
                "content_type": content_type.strip(),
            }
        )
    return prepared


def _secret_bindings_body(bindings):
    if not bindings:
        return None
    bindings = tuple(bindings)
    if len(bindings) > _MAX_SECRET_BINDINGS:
        raise ValueError("secret_bindings accepts at most 10 secrets")
    encoded = []
    for binding in bindings:
        if not isinstance(binding, Secret):
            raise ValueError("secret_bindings entries must be Secret values")
        encoded.append(binding.to_api())
    return encoded
