"""Safety and coverage tests for the internal Grok client. No network calls."""

from __future__ import annotations

import io
import json
import os
import socket
import tempfile
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from services.grok import (
    GrokApiError,
    GrokAuthenticationError,
    GrokClient,
    GrokConfigurationError,
    GrokNotFoundError,
    GrokSafetyError,
    GrokTimeoutError,
    GrokTransportError,
    GrokUsageError,
    audio_reference,
    chat_function_tool,
    file_search_tool,
    image_reference,
    responses_function_tool,
    user_message_with_image,
    web_search_tool,
)
from services.grok.constants import INFERENCE_HOSTS, MANAGEMENT_HOSTS
from services.grok.resources.videos import video_keyframe
from services.grok.transport import HttpTransport, encode_multipart_form

INFERENCE_KEY = "inference-key-12345678"
MANAGEMENT_KEY = "management-key-12345678"

EMPTY = {
    "data": [{"index": 1, "embedding": [0.2]}, {"index": 0, "embedding": [0.1]}],
    "models": [{"id": "grok-4.6"}],
    "batches": [],
    "voices": [],
    "collections": [],
    "documents": [],
    "matches": [],
    "batch_request_metadata": [],
    "results": [],
    "output": [
        {
            "type": "message",
            "content": [{"type": "output_text", "text": "Hello"}],
        }
    ],
    "id": "resp_test",
    "request_id": "req_test",
    "status": "done",
    "deleted": True,
    "text": "transcribed",
    "token_ids": [1, 2, 3],
    "value": "xai-realtime-client-secret-test",
    "expires_at": 1750000000,
    "has_more": False,
    "object": "list",
}


class Headers(dict):
    def get(self, key, default=None):
        for existing, value in super().items():
            if str(existing).lower() == str(key).lower():
                return value
        return default


class FakeResponse:
    def __init__(self, status, body, headers=None):
        if isinstance(body, str):
            body = body.encode()
        self.status = status
        self.code = status
        self.headers = Headers(headers or {"Content-Type": "application/json"})
        self._buffer = io.BytesIO(body)
        self.closed = False

    def read(self, n=-1):
        return self._buffer.read(n)

    def readline(self):
        return self._buffer.readline()

    def close(self):
        self.closed = True

    def getcode(self):
        return self.status

    def getheader(self, name, default=None):
        return self.headers.get(name, default)


class FakeUrlopen:
    def __init__(self, script=None):
        self.script = list(script or [])
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return default_response(request)


def default_response(request):
    path = urlparse(request.full_url).path
    data = request.data or b""
    if path == "/v1/tts" and b"with_timestamps" not in data:
        return FakeResponse(200, b"MP3DATA", {"Content-Type": "audio/mpeg"})
    if path.endswith("/content") or path.endswith("/audio"):
        return FakeResponse(200, b"BYTES", {"Content-Type": "application/octet-stream"})
    if b'"stream": true' in data:
        payload = (
            'data: {"type": "response.output_text.delta", "delta": "Hi"}\n'
            "data: [DONE]\n"
        )
        return FakeResponse(200, payload, {"Content-Type": "text/event-stream"})
    return FakeResponse(200, json.dumps(EMPTY), {"Content-Type": "application/json"})


def http_error(status, body, headers=None):
    return urllib.error.HTTPError(
        url="https://api.x.ai/v1/responses",
        code=status,
        msg="error",
        hdrs=Headers(headers or {"Content-Type": "application/json"}),
        fp=io.BytesIO(body if isinstance(body, bytes) else body.encode()),
    )


def transport(fake, *, api_key=INFERENCE_KEY, base_url="https://api.x.ai", hosts=INFERENCE_HOSTS, **kwargs):
    return HttpTransport(
        api_key,
        base_url=base_url,
        allowed_hosts=hosts,
        urlopen=fake,
        sleep=lambda seconds: None,
        random_unit_interval=lambda: 0,
        max_retries=kwargs.pop("max_retries", 2),
        **kwargs,
    )


def client_with(fake):
    inference = transport(fake)
    management = transport(
        fake,
        api_key=MANAGEMENT_KEY,
        base_url="https://management-api.x.ai",
        hosts=MANAGEMENT_HOSTS,
    )
    return GrokClient(transport=inference, management_transport=management)


def request_json(request):
    return json.loads(request.data.decode())


class GrokClientTests(unittest.TestCase):
    def test_ask_does_not_store_the_response_and_hides_the_key(self):
        fake = FakeUrlopen()
        client = client_with(fake)
        self.assertEqual(client.ask("Price this jacket"), "Hello")
        body = request_json(fake.requests[0])
        self.assertIs(body["store"], False)
        self.assertEqual(body["model"], "grok-4.6")
        self.assertEqual(body["input"], "Price this jacket")
        self.assertNotIn(INFERENCE_KEY, fake.requests[0].full_url)
        self.assertNotIn(INFERENCE_KEY, repr(client))
        self.assertIn("Bearer " + INFERENCE_KEY, fake.requests[0].get_header("Authorization"))

    def test_background_response_must_be_stored(self):
        client = client_with(FakeUrlopen())
        with self.assertRaises(GrokUsageError):
            client.responses.create_model_response(
                model="grok-4.6",
                input="hello",
                background=True,
            )

    def test_stream_text_yields_deltas_without_storing(self):
        fake = FakeUrlopen()
        client = client_with(fake)
        self.assertEqual(list(client.stream_text("hello")), ["Hi"])
        body = request_json(fake.requests[0])
        self.assertIs(body["stream"], True)
        self.assertIs(body["store"], False)

    def test_json_object_answer_parses_fenced_json(self):
        payload = dict(EMPTY)
        payload["output"] = [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '```json\n{"price": 12}\n```'}],
            }
        ]
        fake = FakeUrlopen()
        fake.script = [FakeResponse(200, json.dumps(payload))]
        client = client_with(fake)
        self.assertEqual(client.ask_for_json_object("price it"), {"price": 12})
        self.assertEqual(request_json(fake.requests[0])["text"]["format"]["type"], "json_object")

    def test_server_stored_conversation_keeps_ids_and_can_delete_them(self):
        fake = FakeUrlopen()
        client = client_with(fake)
        conversation = client.start_server_stored_conversation(instructions="Be brief.")
        self.assertEqual(conversation.send_user_message("first"), "Hello")
        self.assertEqual(conversation.send_user_message("second"), "Hello")
        first = request_json(fake.requests[0])
        second = request_json(fake.requests[1])
        self.assertIs(first["store"], True)
        self.assertEqual(first["instructions"], "Be brief.")
        self.assertEqual(second["previous_response_id"], "resp_test")
        self.assertNotIn("instructions", second)
        conversation.delete_stored_responses()
        delete_paths = [urlparse(request.full_url).path for request in fake.requests[2:]]
        self.assertEqual(delete_paths, ["/v1/responses/resp_test", "/v1/responses/resp_test"])
        self.assertEqual(conversation.response_ids, [])

    def test_error_body_does_not_reveal_the_api_key(self):
        fake = FakeUrlopen(
            [
                http_error(
                    401,
                    json.dumps({"error": {"message": f"rejected {INFERENCE_KEY}", "code": "nope"}}),
                )
            ]
        )
        client = client_with(fake)
        with self.assertRaises(GrokAuthenticationError) as caught:
            client.ask("hello")
        self.assertNotIn(INFERENCE_KEY, str(caught.exception))
        self.assertIn("***", str(caught.exception))
        self.assertEqual(caught.exception.error_code, "nope")

    def test_post_is_not_retried_on_server_error_but_is_retried_on_rate_limit(self):
        post_failure = FakeUrlopen([http_error(500, '{"error":"nope"}')])
        client = client_with(post_failure)
        with self.assertRaises(GrokApiError):
            client.ask("hello")
        self.assertEqual(len(post_failure.requests), 1)

        post_limit = FakeUrlopen(
            [http_error(429, '{"error":"slow"}', {"Retry-After": "0"}), default_response_later()]
        )
        # default_response_later is a response object, not a callable. Build it after the request exists.
        post_limit.script[1] = FakeResponse(200, json.dumps(EMPTY))
        client = client_with(post_limit)
        self.assertEqual(client.ask("hello"), "Hello")
        self.assertEqual(len(post_limit.requests), 2)

    def test_get_retries_transient_failures_and_connection_errors(self):
        fake = FakeUrlopen(
            [
                http_error(503, '{"error":"unavailable"}'),
                urllib.error.URLError("connection reset"),
                FakeResponse(200, json.dumps(EMPTY)),
            ]
        )
        client = client_with(fake)
        body = client.list_all_models()
        self.assertEqual(body["models"][0]["id"], "grok-4.6")
        self.assertEqual(len(fake.requests), 3)

    def test_post_connection_failure_is_not_retried(self):
        fake = FakeUrlopen([urllib.error.URLError("connection reset"), FakeResponse(200, b"{}")])
        client = client_with(fake)
        with self.assertRaises(GrokTransportError):
            client.ask("hello")
        self.assertEqual(len(fake.requests), 1)

    def test_timeout_on_get_retries_then_succeeds(self):
        fake = FakeUrlopen([socket.timeout("slow"), FakeResponse(200, json.dumps(EMPTY))])
        client = client_with(fake)
        self.assertIn("models", client.models.list_all_models())
        self.assertEqual(len(fake.requests), 2)

    def test_oversized_response_is_discarded(self):
        fake = FakeUrlopen()
        http = transport(fake, max_response_bytes=8)
        with self.assertRaises(GrokSafetyError):
            http.send("GET", "/v1/models")

    def test_resource_ids_cannot_change_the_path(self):
        client = client_with(FakeUrlopen())
        with self.assertRaises(GrokUsageError):
            client.files.retrieve_file_metadata("../secrets")
        with self.assertRaises(GrokUsageError):
            client.files.retrieve_file_metadata("file id")

    def test_api_key_cannot_be_placed_in_the_url_or_sent_to_another_host(self):
        http = transport(FakeUrlopen())
        with self.assertRaises(GrokSafetyError):
            http.send("GET", "/v1/models", query={"echo": INFERENCE_KEY})
        with self.assertRaises(GrokSafetyError):
            GrokClient(api_key=INFERENCE_KEY, base_url="https://evil.example")
        with self.assertRaises(GrokSafetyError):
            GrokClient(api_key=INFERENCE_KEY, base_url="https://api.x.ai.evil.example")
        with self.assertRaises(GrokSafetyError):
            GrokClient(api_key=INFERENCE_KEY, base_url="http://api.x.ai")

    def test_redirects_are_refused(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "https://example.com/steal")
                self.end_headers()

            def log_message(self, fmt, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            grok = GrokClient(
                api_key=INFERENCE_KEY,
                base_url=f"http://127.0.0.1:{port}",
                allow_non_default_host=True,
                max_retries=0,
                timeout_seconds=5,
            )
            with self.assertRaises(GrokSafetyError):
                grok.list_all_models()
        finally:
            server.shutdown()
            server.server_close()

    def test_collections_use_the_management_key_only(self):
        missing = GrokClient(transport=transport(FakeUrlopen()))
        with self.assertRaises(GrokConfigurationError):
            missing.collections.list_all_collections()

        fake = FakeUrlopen()
        grok = client_with(fake)
        grok.collections.create_collection("Jackets")
        request = fake.requests[-1]
        self.assertEqual(urlparse(request.full_url).netloc, "management-api.x.ai")
        self.assertIn(MANAGEMENT_KEY, request.get_header("Authorization"))
        self.assertNotIn(INFERENCE_KEY, request.get_header("Authorization"))

    def test_pagination_stops_on_a_repeated_token_and_on_the_page_cap(self):
        repeated = FakeUrlopen(
            [
                FakeResponse(200, json.dumps({"data": [{"id": "a"}], "pagination_token": "same"})),
                FakeResponse(200, json.dumps({"data": [{"id": "b"}], "pagination_token": "same"})),
            ]
        )
        grok = client_with(repeated)
        with self.assertRaises(GrokSafetyError):
            grok.files.list_all_files(max_pages=5)
        self.assertEqual(len(repeated.requests), 2)

        counter = {"n": 0}

        def endless(request, timeout=None):
            counter["n"] += 1
            body = {"data": [{"id": counter["n"]}], "pagination_token": f"page-{counter['n']}"}
            return FakeResponse(200, json.dumps(body))

        capped = FakeUrlopen()
        capped.script = []
        original = capped.__call__

        def capped_open(request, timeout=None):
            capped.requests.append(request)
            return endless(request, timeout=timeout)

        http = transport(capped_open)
        from services.grok.resources.files import FilesResource

        with self.assertRaises(GrokSafetyError):
            FilesResource(http).list_all_files(max_pages=2)
        self.assertEqual(counter["n"], 2)

    def test_multipart_filenames_cannot_inject_headers(self):
        with self.assertRaises(GrokSafetyError):
            encode_multipart_form([], [("file", 'evil"\r\nX-Injected: 1', "text/plain", b"hi")])
        fake = FakeUrlopen()
        grok = client_with(fake)
        grok.files.upload_file_bytes(b"jacket", filename="../../jacket\r\n.png", content_type="image/png")
        disposition = fake.requests[-1].data.split(b"\r\n")
        filename_lines = [line for line in disposition if line.startswith(b"Content-Disposition:")]
        self.assertEqual(len(filename_lines), 1)
        self.assertIn(b'filename="jacket.png"', filename_lines[0])
        self.assertNotIn(b"X-Injected", fake.requests[-1].data)

    def test_video_polling_stops_when_generation_fails(self):
        failed = {
            "status": "failed",
            "response": {"error": {"message": "moderation rejected the clip"}},
        }
        fake = FakeUrlopen([FakeResponse(200, json.dumps(failed))])
        grok = client_with(fake)
        with self.assertRaises(GrokApiError) as caught:
            grok.wait_until_video_generation_finishes("req_video")
        self.assertIn("moderation rejected", str(caught.exception))

    def test_deferred_chat_waits_through_pending(self):
        fake = FakeUrlopen(
            [
                FakeResponse(202, json.dumps({"request_id": "req_test"})),
                FakeResponse(200, json.dumps({"choices": [{"message": {"content": "303"}}]})),
            ]
        )
        grok = client_with(fake)
        body = grok.chat.wait_for_deferred_chat_completion("req_test", poll_interval_seconds=0.2)
        self.assertEqual(body["choices"][0]["message"]["content"], "303")
        self.assertEqual(len(fake.requests), 2)

    def test_embedding_order_and_token_count(self):
        fake = FakeUrlopen()
        grok = client_with(fake)
        self.assertEqual(grok.embed_texts(["a", "b"]), [[0.1], [0.2]])
        self.assertEqual(grok.count_tokens_in_text("hello"), 3)

    def test_builders_reject_ambiguous_media_and_search_options(self):
        with self.assertRaises(GrokUsageError):
            image_reference()
        with self.assertRaises(GrokUsageError):
            image_reference(file_id="file_1", url="https://example.com/a.png")
        with self.assertRaises(GrokUsageError):
            web_search_tool(allowed_domains=["a.com"], excluded_domains=["b.com"])
        with self.assertRaises(GrokUsageError):
            audio_reference(voice_id="ara", url="https://example.com/a.wav")
        with self.assertRaises(GrokUsageError):
            video_keyframe(image_url="https://example.com/a.png", timestamp_seconds=0)
        tool = responses_function_tool("list_price", {"type": "object"})
        self.assertEqual(tool["type"], "function")
        self.assertEqual(tool["name"], "list_price")
        chat_tool = chat_function_tool("list_price", {"type": "object"})
        self.assertEqual(chat_tool["function"]["name"], "list_price")
        self.assertEqual(
            file_search_tool(["collection_123"])["vector_store_ids"],
            ["collection_123"],
        )
        message = user_message_with_image("look", image_url="https://example.com/jacket.png")
        self.assertEqual(message["content"][1]["image_url"]["url"], "https://example.com/jacket.png")

    def test_ephemeral_secret_and_websocket_keep_the_key_out_of_urls(self):
        fake = FakeUrlopen()
        grok = client_with(fake)
        secret = grok.realtime.create_ephemeral_realtime_client_secret(expires_after_seconds=300)
        self.assertNotIn("xai-realtime-client-secret-test", repr(secret))
        self.assertTrue(secret.authorization_header_value.startswith("Bearer "))
        connection = grok.voice.text_to_speech_websocket_connection(language="en")
        self.assertTrue(connection.url.startswith("wss://api.x.ai/v1/tts?"))
        self.assertNotIn(INFERENCE_KEY, connection.url)
        self.assertNotIn(INFERENCE_KEY, repr(connection))
        self.assertEqual(connection.headers["Authorization"], "Bearer " + INFERENCE_KEY)
        realtime = grok.realtime.realtime_websocket_connection()
        self.assertTrue(realtime.url.startswith("wss://api.x.ai/v1/realtime?"))
        self.assertNotIn(INFERENCE_KEY, realtime.url)

    def test_every_documented_endpoint_is_called_with_the_right_method_and_path(self):
        fake = FakeUrlopen()
        grok = client_with(fake)
        with tempfile.TemporaryDirectory() as directory:
            audio_path = Path(directory) / "clip.mp3"
            image_path = Path(directory) / "jacket.png"
            skill_path = Path(directory) / "skill.zip"
            audio_path.write_bytes(b"audio")
            image_path.write_bytes(b"image")
            skill_path.write_bytes(b"zip")
            calls = catalog(grok, audio_path, image_path, skill_path)
            for method_name, expected_method, expected_path in calls:
                with self.subTest(method=method_name):
                    before = len(fake.requests)
                    method_name()
                    self.assertGreater(len(fake.requests), before)
                    request = fake.requests[-1]
                    self.assertEqual(request.get_method(), expected_method)
                    path = urlparse(request.full_url).path
                    self.assertEqual(path, expected_path)
                    host = urlparse(request.full_url).netloc
                    if expected_path.startswith("/v1/collections"):
                        self.assertEqual(host, "management-api.x.ai")
                        self.assertIn(MANAGEMENT_KEY, request.get_header("Authorization"))
                    else:
                        self.assertEqual(host, "api.x.ai")
                        self.assertIn(INFERENCE_KEY, request.get_header("Authorization"))
                    self.assertNotIn(INFERENCE_KEY, request.full_url)
                    self.assertNotIn(MANAGEMENT_KEY, request.full_url)


def default_response_later():
    return FakeResponse(200, json.dumps(EMPTY))


def catalog(grok, audio_path, image_path, skill_path):
    file_id = "file_123"
    response_id = "resp_123"
    batch_id = "batch_123"
    collection_id = "collection_123"
    voice_id = "eve"
    custom_voice_id = "nlbqfwie"
    skill_id = "skill_123"
    model_id = "grok-4.6"
    request_id = "req_123"
    call_id = "call_123"
    return [
        (lambda: grok.responses.create_model_response(model=model_id, input="hi"), "POST", "/v1/responses"),
        (
            lambda: list(grok.responses.stream_model_response_events(model=model_id, input="hi")),
            "POST",
            "/v1/responses",
        ),
        (
            lambda: grok.responses.compact_response_input(model=model_id, input="hi"),
            "POST",
            "/v1/responses/compact",
        ),
        (
            lambda: grok.responses.retrieve_stored_model_response(response_id),
            "GET",
            f"/v1/responses/{response_id}",
        ),
        (
            lambda: grok.responses.delete_stored_model_response(response_id),
            "DELETE",
            f"/v1/responses/{response_id}",
        ),
        (
            lambda: grok.responses.list_stored_response_input_items(response_id),
            "GET",
            f"/v1/responses/{response_id}/input_items",
        ),
        (
            lambda: grok.chat.create_chat_completion(
                model=model_id, messages=[{"role": "user", "content": "hi"}]
            ),
            "POST",
            "/v1/chat/completions",
        ),
        (
            lambda: list(
                grok.chat.stream_chat_completion(
                    model=model_id, messages=[{"role": "user", "content": "hi"}]
                )
            ),
            "POST",
            "/v1/chat/completions",
        ),
        (
            lambda: grok.chat.fetch_deferred_chat_completion(request_id),
            "GET",
            f"/v1/chat/deferred-completion/{request_id}",
        ),
        (lambda: grok.images.generate_image_from_text_prompt("a jacket"), "POST", "/v1/images/generations"),
        (
            lambda: grok.images.edit_image_with_prompt("brighter", image_url="https://example.com/jacket.png"),
            "POST",
            "/v1/images/edits",
        ),
        (lambda: grok.videos.generate_video_from_text_prompt("spin"), "POST", "/v1/videos/generations"),
        (
            lambda: grok.videos.edit_video_with_prompt("slower", video_url="https://example.com/clip.mp4"),
            "POST",
            "/v1/videos/edits",
        ),
        (
            lambda: grok.videos.extend_video_with_prompt("continue", video_file_id=file_id),
            "POST",
            "/v1/videos/extensions",
        ),
        (lambda: grok.videos.fetch_video_generation_result(request_id), "GET", f"/v1/videos/{request_id}"),
        (lambda: grok.files.list_files_page(), "GET", "/v1/files"),
        (
            lambda: grok.files.upload_file_from_path(image_path, content_type="image/png"),
            "POST",
            "/v1/files",
        ),
        (lambda: grok.files.retrieve_file_metadata(file_id), "GET", f"/v1/files/{file_id}"),
        (lambda: grok.files.delete_file(file_id), "DELETE", f"/v1/files/{file_id}"),
        (lambda: grok.files.download_file_bytes(file_id), "GET", f"/v1/files/{file_id}/content"),
        (
            lambda: grok.files.create_unauthenticated_public_url_for_file(file_id),
            "POST",
            f"/v1/files/{file_id}/public-url",
        ),
        (
            lambda: grok.files.revoke_public_file_url(file_id),
            "POST",
            f"/v1/files/{file_id}/public-url/revoke",
        ),
        (lambda: grok.models.list_all_models(), "GET", "/v1/models"),
        (lambda: grok.models.retrieve_model(model_id), "GET", f"/v1/models/{model_id}"),
        (lambda: grok.models.list_language_models(), "GET", "/v1/language-models"),
        (
            lambda: grok.models.retrieve_language_model(model_id),
            "GET",
            f"/v1/language-models/{model_id}",
        ),
        (lambda: grok.models.list_image_generation_models(), "GET", "/v1/image-generation-models"),
        (
            lambda: grok.models.retrieve_image_generation_model(model_id),
            "GET",
            f"/v1/image-generation-models/{model_id}",
        ),
        (lambda: grok.models.list_video_generation_models(), "GET", "/v1/video-generation-models"),
        (
            lambda: grok.models.retrieve_video_generation_model(model_id),
            "GET",
            f"/v1/video-generation-models/{model_id}",
        ),
        (lambda: grok.models.list_embedding_models(), "GET", "/v1/embedding-models"),
        (
            lambda: grok.models.retrieve_embedding_model(model_id),
            "GET",
            f"/v1/embedding-models/{model_id}",
        ),
        (lambda: grok.embeddings.create_embedding_vectors("jacket"), "POST", "/v1/embeddings"),
        (
            lambda: grok.documents.search_collection_documents("wool", [collection_id]),
            "POST",
            "/v1/documents/search",
        ),
        (lambda: grok.skills.list_skills_page(), "GET", "/v1/skills"),
        (lambda: grok.skills.upload_skill_from_path(skill_path), "POST", "/v1/skills"),
        (lambda: grok.skills.retrieve_skill(skill_id), "GET", f"/v1/skills/{skill_id}"),
        (lambda: grok.skills.delete_skill(skill_id), "DELETE", f"/v1/skills/{skill_id}"),
        (lambda: grok.skills.download_skill_content(skill_id), "GET", f"/v1/skills/{skill_id}/content"),
        (lambda: grok.account.get_api_key_information(), "GET", "/v1/api-key"),
        (lambda: grok.account.get_authenticated_caller(), "GET", "/v1/me"),
        (lambda: grok.tokenize.tokenize_text("hello", model=model_id), "POST", "/v1/tokenize-text"),
        (
            lambda: grok.legacy.create_legacy_anthropic_text_completion(
                model=model_id, prompt="hi", max_tokens_to_sample=16
            ),
            "POST",
            "/v1/complete",
        ),
        (
            lambda: grok.legacy.create_legacy_prompt_completion(model=model_id, prompt="hi"),
            "POST",
            "/v1/completions",
        ),
        (
            lambda: grok.legacy.create_anthropic_compatible_message(
                model=model_id,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=16,
            ),
            "POST",
            "/v1/messages",
        ),
        (lambda: grok.voice.synthesize_speech_audio_from_text("hi", language="en"), "POST", "/v1/tts"),
        (
            lambda: grok.voice.synthesize_speech_with_character_timestamps("hi", language="en"),
            "POST",
            "/v1/tts",
        ),
        (lambda: grok.voice.list_built_in_voices(), "GET", "/v1/tts/voices"),
        (lambda: grok.voice.retrieve_built_in_voice(voice_id), "GET", f"/v1/tts/voices/{voice_id}"),
        (lambda: grok.voice.transcribe_audio_file(audio_path), "POST", "/v1/stt"),
        (
            lambda: grok.voice.transcribe_audio_from_url("https://example.com/clip.mp3"),
            "POST",
            "/v1/stt",
        ),
        (
            lambda: grok.voice.create_custom_voice_from_audio_file(audio_path, name="Salt"),
            "POST",
            "/v1/custom-voices",
        ),
        (lambda: grok.voice.list_custom_voices_page(), "GET", "/v1/custom-voices"),
        (
            lambda: grok.voice.retrieve_custom_voice(custom_voice_id),
            "GET",
            f"/v1/custom-voices/{custom_voice_id}",
        ),
        (
            lambda: grok.voice.update_custom_voice_metadata(custom_voice_id, tone="calm"),
            "PATCH",
            f"/v1/custom-voices/{custom_voice_id}",
        ),
        (
            lambda: grok.voice.delete_custom_voice(custom_voice_id),
            "DELETE",
            f"/v1/custom-voices/{custom_voice_id}",
        ),
        (
            lambda: grok.voice.download_custom_voice_reference_audio(custom_voice_id),
            "GET",
            f"/v1/custom-voices/{custom_voice_id}/audio",
        ),
        (lambda: grok.batches.create_batch("pricing"), "POST", "/v1/batches"),
        (lambda: grok.batches.list_batches_page(), "GET", "/v1/batches"),
        (lambda: grok.batches.retrieve_batch(batch_id), "GET", f"/v1/batches/{batch_id}"),
        (
            lambda: grok.batches.list_batch_requests_page(batch_id),
            "GET",
            f"/v1/batches/{batch_id}/requests",
        ),
        (
            lambda: grok.batches.add_chat_completion_requests_to_batch(
                batch_id,
                [
                    {
                        "batch_request_id": "price-1",
                        "model": model_id,
                        "messages": [{"role": "user", "content": "hi"}],
                    }
                ],
            ),
            "POST",
            f"/v1/batches/{batch_id}/requests",
        ),
        (
            lambda: grok.batches.list_batch_results_page(batch_id),
            "GET",
            f"/v1/batches/{batch_id}/results",
        ),
        (lambda: grok.batches.cancel_batch(batch_id), "POST", f"/v1/batches/{batch_id}:cancel"),
        (
            lambda: grok.realtime.create_ephemeral_realtime_client_secret(),
            "POST",
            "/v1/realtime/client_secrets",
        ),
        (
            lambda: grok.realtime.refer_realtime_phone_call(call_id, "sip:agent@example.com"),
            "POST",
            f"/v1/realtime/calls/{call_id}/refer",
        ),
        (
            lambda: grok.realtime.hang_up_realtime_phone_call(call_id),
            "POST",
            f"/v1/realtime/calls/{call_id}/hangup",
        ),
        (
            lambda: grok.realtime.create_phone_number(origin="xai_provisioned", name="Salt line"),
            "POST",
            "/v2/phone-numbers",
        ),
        (
            lambda: grok.collections.create_collection("Jackets"),
            "POST",
            "/v1/collections",
        ),
        (lambda: grok.collections.list_collections_page(), "GET", "/v1/collections"),
        (
            lambda: grok.collections.retrieve_collection(collection_id),
            "GET",
            f"/v1/collections/{collection_id}",
        ),
        (
            lambda: grok.collections.update_collection(collection_id, collection_description="coats"),
            "PUT",
            f"/v1/collections/{collection_id}",
        ),
        (
            lambda: grok.collections.add_file_to_collection(collection_id, file_id, fields={"kind": "coat"}),
            "POST",
            f"/v1/collections/{collection_id}/documents/{file_id}",
        ),
        (
            lambda: grok.collections.list_collection_documents_page(collection_id),
            "GET",
            f"/v1/collections/{collection_id}/documents",
        ),
        (
            lambda: grok.collections.retrieve_collection_document(collection_id, file_id),
            "GET",
            f"/v1/collections/{collection_id}/documents/{file_id}",
        ),
        (
            lambda: grok.collections.reindex_collection_document(collection_id, file_id),
            "PATCH",
            f"/v1/collections/{collection_id}/documents/{file_id}",
        ),
        (
            lambda: grok.collections.remove_file_from_collection(collection_id, file_id),
            "DELETE",
            f"/v1/collections/{collection_id}/documents/{file_id}",
        ),
        (
            lambda: grok.collections.batch_get_collection_documents(collection_id, [file_id]),
            "GET",
            f"/v1/collections/{collection_id}/documents:batchGet",
        ),
        (
            lambda: grok.collections.delete_collection(collection_id),
            "DELETE",
            f"/v1/collections/{collection_id}",
        ),
    ]


class EnvironmentTests(unittest.TestCase):
    def test_missing_key_names_the_env_variable(self):
        previous = os.environ.pop("XAI_API_KEY", None)
        try:
            with self.assertRaises(GrokConfigurationError) as caught:
                GrokClient.from_environment(load_project_env_file=False)
            self.assertIn("XAI_API_KEY", str(caught.exception))
        finally:
            if previous is not None:
                os.environ["XAI_API_KEY"] = previous

    def test_not_found_responses_can_be_ignored_by_callers(self):
        fake = FakeUrlopen([http_error(404, '{"error":"missing"}')])
        grok = client_with(fake)
        with self.assertRaises(GrokNotFoundError):
            grok.responses.delete_stored_model_response("resp_missing")


class DjangoPathTests(unittest.TestCase):
    def test_settings_put_the_repository_root_on_the_path(self):
        os.environ.setdefault(
            "DATABASE_URL",
            "postgresql://user:pass@localhost:5432/salt",
        )
        import sys

        backend = str(Path(__file__).resolve().parents[3] / "backend")
        if backend not in sys.path:
            sys.path.insert(0, backend)
        import config.settings as settings

        self.assertIn(str(settings.REPO_ROOT), sys.path)
        self.assertTrue((settings.REPO_ROOT / "services" / "grok" / "client.py").is_file())


if __name__ == "__main__":
    unittest.main()
