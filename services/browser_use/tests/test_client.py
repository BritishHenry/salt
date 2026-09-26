"""Client tests against a scripted transport. No live Browser Use calls."""

import io
import json
import sys
import unittest
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.browser_use import BrowserUseClient
from services.browser_use.errors import (
    BrowserUseAPIError,
    BrowserUseConfigError,
    BrowserUseRunFailed,
    BrowserUseTimeout,
    MessageNotDispatched,
    QueueFull,
    SessionBusy,
)
from services.browser_use.transport import UrllibTransport


class Clock:
    def __init__(self):
        self.now = 0
        self.slept = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, *, json_body=None, query=None):
        self.calls.append(
            {"method": method, "path": path, "json": json_body, "query": query}
        )
        if not self.responses:
            raise AssertionError(f"unexpected {method} {path}")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def client(responses, clock=None):
    clock = clock or Clock()
    transport = FakeTransport(responses)
    browser = BrowserUseClient(transport=transport, sleep=clock.sleep, monotonic=clock.monotonic)
    return browser, transport, clock


RUN_ID = "11111111-1111-1111-1111-111111111111"
SESSION_ID = "22222222-2222-2222-2222-222222222222"
WORKSPACE_ID = "33333333-3333-3333-3333-333333333333"
BROWSER_ID = "44444444-4444-4444-4444-444444444444"


def created_run(**extra):
    payload = {
        "id": RUN_ID,
        "status": "queued",
        "model": "gpt-5.6-luna",
        "sessionId": SESSION_ID,
        "workspaceId": WORKSPACE_ID,
        "eventsUrl": f"/runs/{RUN_ID}/events",
    }
    payload.update(extra)
    return payload


def summary(status="completed", **extra):
    payload = {
        "id": RUN_ID,
        "status": status,
        "model": "gpt-5.6-luna",
        "sessionId": SESSION_ID,
        "workspaceId": WORKSPACE_ID,
        "task": "Find the top story",
        "title": "Top story",
        "result": "A story",
        "error": None,
        "output": {"title": "A story"},
        "totalInputTokens": 10,
        "totalOutputTokens": 4,
        "totalCostUsd": "0.01",
        "createdAt": "2026-09-26T00:00:00Z",
        "updatedAt": "2026-09-26T00:01:00Z",
    }
    payload.update(extra)
    return payload


def message(status="pending", run_id=None, message_id=7, text="Next"):
    return {
        "id": message_id,
        "sessionId": SESSION_ID,
        "runId": run_id,
        "mode": "queue",
        "status": status,
        "text": text,
        "createdAt": "2026-09-26T00:00:00Z",
    }


class CreateRunTests(unittest.TestCase):
    def test_sends_only_the_task_by_default(self):
        browser, transport, _clock = client([created_run()])
        run = browser.create_run("Find the top Hacker News story")
        self.assertEqual(transport.calls[0]["json"], {"task": "Find the top Hacker News story"})
        self.assertEqual(run.id, RUN_ID)
        self.assertEqual(run.session_id, SESSION_ID)

    def test_includes_follow_up_fields_and_explicit_null_proxy(self):
        browser, transport, _clock = client([created_run()])
        browser.create_run(
            "Continue",
            model="grok-4.5",
            session_id=SESSION_ID,
            output_schema={"type": "object"},
            proxy_country_code=None,
            record=True,
        )
        self.assertEqual(
            transport.calls[0]["json"],
            {
                "task": "Continue",
                "model": "grok-4.5",
                "sessionId": SESSION_ID,
                "outputSchema": {"type": "object"},
                "browserSettings": {"proxyCountryCode": None, "record": True},
            },
        )

    def test_rejects_a_blank_task(self):
        browser, _transport, _clock = client([])
        with self.assertRaises(ValueError):
            browser.create_run("  ")

    def test_missing_api_key(self):
        with self.assertRaises(BrowserUseConfigError):
            BrowserUseClient(api_key="  ")


class WaitTests(unittest.TestCase):
    def test_polls_status_then_fetches_the_summary_once(self):
        browser, transport, clock = client(
            [
                {"status": "running"},
                {"status": "completed"},
                summary(),
            ]
        )
        run = browser.wait(RUN_ID, timeout=30, session_id=SESSION_ID)
        self.assertEqual(run.result, "A story")
        self.assertEqual(run.output, {"title": "A story"})
        self.assertEqual(
            [call["path"] for call in transport.calls],
            [f"/runs/{RUN_ID}/status", f"/runs/{RUN_ID}/status", f"/runs/{RUN_ID}"],
        )
        self.assertEqual(clock.slept, [2])

    def test_timeout_does_not_cancel_the_run(self):
        browser, transport, _clock = client([{"status": "running"}])
        with self.assertRaises(BrowserUseTimeout) as caught:
            browser.wait(RUN_ID, timeout=0, session_id=SESSION_ID)
        self.assertEqual(caught.exception.run_id, RUN_ID)
        self.assertEqual(caught.exception.session_id, SESSION_ID)
        self.assertEqual([call["path"] for call in transport.calls], [f"/runs/{RUN_ID}/status"])

    def test_failed_run_raises_with_the_summary(self):
        browser, _transport, _clock = client(
            [{"status": "failed"}, summary(status="failed", result=None, error="blocked")]
        )
        with self.assertRaises(BrowserUseRunFailed) as caught:
            browser.wait(RUN_ID, timeout=5)
        self.assertEqual(caught.exception.run.error, "blocked")

    def test_one_shot_run_stops_the_browser_after_completion(self):
        browser, transport, _clock = client(
            [
                created_run(),
                {"status": "completed"},
                summary(),
                {"items": [{"id": BROWSER_ID, "status": "active", "agentSessionId": SESSION_ID}]},
                {"id": BROWSER_ID, "status": "stopped"},
            ]
        )
        run = browser.run("Find the top story")
        self.assertEqual(run.status, "completed")
        self.assertEqual(transport.calls[-1]["method"], "PATCH")
        self.assertEqual(transport.calls[-1]["path"], f"/browsers/{BROWSER_ID}")
        self.assertEqual(transport.calls[-1]["json"], {"action": "stop"})

    def test_one_shot_timeout_leaves_the_browser_running(self):
        browser, transport, _clock = client([created_run(), {"status": "running"}])
        with self.assertRaises(BrowserUseTimeout):
            browser.run("Find the top story", timeout=0)
        self.assertEqual([call["method"] for call in transport.calls], ["POST", "GET"])


class ConversationTests(unittest.TestCase):
    def test_busy_session_queues_the_follow_up(self):
        browser, transport, clock = client(
            [
                SessionBusy(409, "The session already has an active run."),
                message(),
                message(status="dispatching"),
                message(status="consumed", run_id=RUN_ID),
                {"status": "completed"},
                summary(task="Now summarize"),
            ]
        )
        assignment = browser.assign("Now summarize", session_id=SESSION_ID)
        self.assertIsNone(assignment.run)
        self.assertEqual(assignment.message.id, 7)
        self.assertEqual(transport.calls[1]["json"], {"text": "Now summarize", "interrupt": False})
        finished = browser.wait_assignment(assignment, timeout=30)
        self.assertEqual(finished.result, "A story")
        self.assertEqual(clock.slept, [2])
        self.assertNotIn("POST", [call["method"] for call in transport.calls[2:]])

    def test_interrupt_queues_without_creating_a_run(self):
        browser, transport, _clock = client([message(text="Stop and do this")])
        browser.assign("Stop and do this", session_id=SESSION_ID, interrupt=True)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0]["path"], f"/sessions/{SESSION_ID}/queue")
        self.assertTrue(transport.calls[0]["json"]["interrupt"])

    def test_message_that_fails_to_dispatch(self):
        browser, _transport, _clock = client([message(status="superseded")])
        with self.assertRaises(MessageNotDispatched):
            browser.wait_for_dispatch(SESSION_ID, 7, timeout=5)

    def test_dispatch_timeout_keeps_the_message_id(self):
        browser, transport, _clock = client([message()])
        with self.assertRaises(BrowserUseTimeout) as caught:
            browser.wait_for_dispatch(SESSION_ID, 7, timeout=0)
        self.assertEqual(caught.exception.message_id, 7)
        self.assertEqual(len(transport.calls), 1)

    def test_context_releases_the_browser_unless_the_wait_times_out(self):
        browser, transport, _clock = client(
            [
                created_run(),
                {"status": "completed"},
                summary(),
                {"items": [{"id": BROWSER_ID, "status": "active"}]},
                {"id": BROWSER_ID, "status": "stopped"},
            ]
        )
        with browser.conversation("Find the top story") as chat:
            chat.wait(timeout=5)
        self.assertEqual(transport.calls[-1]["json"], {"action": "stop"})

        browser, transport, _clock = client([created_run(), {"status": "running"}])
        with self.assertRaises(BrowserUseTimeout):
            with browser.conversation("Find the top story") as chat:
                chat.wait(timeout=0)
        self.assertNotIn("PATCH", [call["method"] for call in transport.calls])

    def test_send_then_wait_follows_the_queued_message(self):
        browser, transport, _clock = client(
            [
                created_run(),
                message(text="Open the cheapest"),
                message(status="consumed", run_id=RUN_ID, text="Open the cheapest"),
                {"status": "completed"},
                summary(result="Ada"),
            ]
        )
        chat = browser.conversation("Find coats")
        chat.send("Open the cheapest")
        result = chat.wait(timeout=5)
        self.assertEqual(result.result, "Ada")
        self.assertEqual(transport.calls[1]["path"], f"/sessions/{SESSION_ID}/queue")


class EventTests(unittest.TestCase):
    def test_drains_extra_pages_then_stops_on_terminal_status(self):
        browser, transport, clock = client(
            [
                {"status": "running"},
                {
                    "events": [
                        {"id": 1, "runId": RUN_ID, "ts": "t", "type": "step", "data": {"n": 1}}
                    ],
                    "nextAfter": 1,
                    "hasMore": True,
                },
                {"status": "completed"},
                {
                    "events": [
                        {"id": 2, "runId": RUN_ID, "ts": "t", "type": "done", "data": {}}
                    ],
                    "nextAfter": 2,
                    "hasMore": False,
                },
            ]
        )
        events = list(browser.iter_events(RUN_ID, timeout=10))
        self.assertEqual([event.type for event in events], ["step", "done"])
        self.assertEqual(transport.calls[1]["query"]["after"], None)
        self.assertEqual(transport.calls[3]["query"]["after"], 1)
        self.assertEqual(clock.slept, [])


class TransportTests(unittest.TestCase):
    def test_sends_the_api_key_without_bearer_and_retries_retry_after(self):
        seen = []

        def opener(request, timeout=None):
            seen.append(request)
            if len(seen) == 1:
                headers = Message()
                headers["Retry-After"] = "3"
                raise HTTPError(
                    request.full_url,
                    429,
                    "Too Many Requests",
                    headers,
                    io.BytesIO(b'{"retry_after_seconds": 3}'),
                )
            return _response(b'{"id":"run"}')

        clock = Clock()
        transport = UrllibTransport("bu_test_key", sleep=clock.sleep, opener=opener)
        payload = transport.request("POST", "/runs", json_body={"task": "Look"})
        self.assertEqual(payload, {"id": "run"})
        self.assertEqual(seen[0].get_header("X-browser-use-api-key"), "bu_test_key")
        self.assertIsNone(seen[0].get_header("Authorization"))
        self.assertEqual(clock.slept, [3])
        self.assertEqual(json.loads(seen[0].data.decode()), {"task": "Look"})

    def test_full_queue_is_not_retried(self):
        calls = []

        def opener(request, timeout=None):
            calls.append(request)
            raise HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                Message(),
                io.BytesIO(b'{"detail":"The session message queue is full."}'),
            )

        transport = UrllibTransport("bu_test_key", opener=opener)
        with self.assertRaises(QueueFull):
            transport.request(
                "POST",
                f"/sessions/{SESSION_ID}/queue",
                json_body={"text": "Again", "interrupt": False},
            )
        self.assertEqual(len(calls), 1)

    def test_busy_session_maps_to_session_busy(self):
        def opener(request, timeout=None):
            raise HTTPError(
                request.full_url,
                409,
                "Conflict",
                Message(),
                io.BytesIO(b'{"detail":"The session already has an active run."}'),
            )

        transport = UrllibTransport("bu_test_key", opener=opener)
        with self.assertRaises(SessionBusy):
            transport.request("POST", "/runs", json_body={"task": "Again", "sessionId": SESSION_ID})

    def test_other_errors_keep_the_status(self):
        def opener(request, timeout=None):
            raise HTTPError(
                request.full_url,
                402,
                "Payment Required",
                Message(),
                io.BytesIO(b'{"detail":"Insufficient credits"}'),
            )

        transport = UrllibTransport("bu_test_key", opener=opener)
        with self.assertRaises(BrowserUseAPIError) as caught:
            transport.request("POST", "/runs", json_body={"task": "Look"})
        self.assertEqual(caught.exception.status, 402)
        self.assertIn("Insufficient credits", str(caught.exception))


def _response(body):
    class Response:
        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    return Response()


if __name__ == "__main__":
    unittest.main()
