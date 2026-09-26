"""Entry point for the Grok client.

Typical use from Django, after settings has put the repository root on the path:

    from services.grok import GrokClient

    grok = GrokClient.from_environment()
    answer = grok.ask("What should this jacket be listed for?", instructions="You price second-hand clothes.")

The inference key is read from XAI_API_KEY. Collection management reads
XAI_MANAGEMENT_API_KEY and is not called with the inference key.

Responses are not stored on xAI unless you opt in. Use
start_server_stored_conversation when you want multi-turn state kept for 30 days,
and delete_stored_responses when you are finished with it.
"""

from __future__ import annotations

import os
from pathlib import Path

from services.grok.builders import json_object_text_format, json_schema_text_format
from services.grok.constants import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TEXT_MODEL,
    DEFAULT_VOICE_ID,
    INFERENCE_BASE_URL,
    INFERENCE_HOSTS,
    MANAGEMENT_BASE_URL,
    MANAGEMENT_HOSTS,
)
from services.grok.errors import GrokApiError, GrokConfigurationError, GrokError, GrokNotFoundError
from services.grok.parsing import extract_output_text, extract_text_delta, parse_json_object
from services.grok.resources.account import AccountResource
from services.grok.resources.batches import BatchesResource
from services.grok.resources.chat import ChatResource
from services.grok.resources.collections import CollectionsResource
from services.grok.resources.documents import DocumentsResource
from services.grok.resources.embeddings import EmbeddingsResource
from services.grok.resources.files import FilesResource
from services.grok.resources.images import ImagesResource
from services.grok.resources.legacy import LegacyResource
from services.grok.resources.models import ModelsResource
from services.grok.resources.realtime import RealtimeResource
from services.grok.resources.responses import ResponsesResource
from services.grok.resources.skills import SkillsResource
from services.grok.resources.tokenize import TokenizeResource
from services.grok.resources.videos import VideosResource
from services.grok.resources.voice import VoiceResource
from services.grok.transport import HttpTransport


class GrokClient:
    """Verbose client for the xAI Grok HTTPS API."""

    def __init__(
        self,
        api_key=None,
        *,
        management_api_key=None,
        base_url=INFERENCE_BASE_URL,
        management_base_url=MANAGEMENT_BASE_URL,
        timeout_seconds=DEFAULT_HTTP_TIMEOUT_SECONDS,
        max_retries=DEFAULT_MAX_RETRIES,
        allow_non_default_host=False,
        default_text_model=DEFAULT_TEXT_MODEL,
        transport=None,
        management_transport=None,
        urlopen=None,
        sleep=None,
        random_unit_interval=None,
    ):
        if transport is None:
            if not api_key:
                raise GrokConfigurationError(
                    "XAI_API_KEY is missing. Set it in backend/.env or pass api_key."
                )
            transport = HttpTransport(
                api_key,
                base_url=base_url,
                allowed_hosts=INFERENCE_HOSTS,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                allow_non_default_host=allow_non_default_host,
                urlopen=urlopen,
                sleep=sleep,
                random_unit_interval=random_unit_interval,
            )
        if management_transport is None and management_api_key:
            management_transport = HttpTransport(
                management_api_key,
                base_url=management_base_url,
                allowed_hosts=MANAGEMENT_HOSTS,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                allow_non_default_host=allow_non_default_host,
                urlopen=urlopen,
                sleep=sleep,
                random_unit_interval=random_unit_interval,
            )
        self._transport = transport
        self.default_text_model = default_text_model
        self.responses = ResponsesResource(transport)
        self.chat = ChatResource(transport)
        self.images = ImagesResource(transport)
        self.videos = VideosResource(transport)
        self.files = FilesResource(transport)
        self.models = ModelsResource(transport)
        self.embeddings = EmbeddingsResource(transport)
        self.documents = DocumentsResource(transport)
        self.skills = SkillsResource(transport)
        self.account = AccountResource(transport)
        self.tokenize = TokenizeResource(transport)
        self.legacy = LegacyResource(transport)
        self.voice = VoiceResource(transport)
        self.realtime = RealtimeResource(transport)
        self.batches = BatchesResource(transport)
        self._collections = (
            CollectionsResource(management_transport) if management_transport is not None else None
        )

    def __repr__(self):
        return f"GrokClient(base_url={self._transport.base_url!r}, api_key='***')"

    @classmethod
    def from_environment(
        cls,
        *,
        load_project_env_file=True,
        timeout_seconds=DEFAULT_HTTP_TIMEOUT_SECONDS,
        max_retries=DEFAULT_MAX_RETRIES,
        default_text_model=DEFAULT_TEXT_MODEL,
    ):
        """Build a client from XAI_API_KEY and, when present, XAI_MANAGEMENT_API_KEY."""
        if load_project_env_file:
            _load_project_env_file()
        management_key = os.environ.get("XAI_MANAGEMENT_API_KEY", "").strip() or None
        base_url = os.environ.get("XAI_API_BASE_URL", "").strip() or INFERENCE_BASE_URL
        management_base_url = (
            os.environ.get("XAI_MANAGEMENT_API_BASE_URL", "").strip() or MANAGEMENT_BASE_URL
        )
        allow_non_default_host = os.environ.get("XAI_ALLOW_NON_DEFAULT_HOST", "").strip() == "1"
        return cls(
            api_key=os.environ.get("XAI_API_KEY", ""),
            management_api_key=management_key,
            base_url=base_url,
            management_base_url=management_base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            allow_non_default_host=allow_non_default_host,
            default_text_model=default_text_model,
        )

    @property
    def collections(self):
        if self._collections is None:
            raise GrokConfigurationError(
                "Set XAI_MANAGEMENT_API_KEY to use collections. "
                "The inference API key is not sent to the management API."
            )
        return self._collections

    def ask(
        self,
        prompt,
        *,
        instructions=None,
        model=None,
        temperature=None,
        max_output_tokens=None,
        previous_response_id=None,
        store_response_on_xai_servers=False,
        tools=None,
        tool_choice=None,
        reasoning_effort=None,
        safety_identifier=None,
        text_format=None,
        timeout_seconds=None,
    ):
        """Send one prompt and return the assistant text.

        The response is not stored on xAI unless store_response_on_xai_servers is true.
        """
        body = self.responses.create_model_response(
            model=model or self.default_text_model,
            input=prompt,
            instructions=instructions,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
            store_response_on_xai_servers=store_response_on_xai_servers,
            tools=tools,
            tool_choice=tool_choice,
            reasoning_effort=reasoning_effort,
            safety_identifier=safety_identifier,
            text=text_format,
            timeout_seconds=timeout_seconds,
        )
        return extract_output_text(body)

    def ask_for_json_object(
        self,
        prompt,
        *,
        instructions=None,
        schema=None,
        schema_name="response",
        model=None,
        temperature=None,
        timeout_seconds=None,
    ):
        """Ask for one JSON object. Pass schema to constrain the shape."""
        if schema is None:
            text_format = json_object_text_format()
        else:
            text_format = json_schema_text_format(schema_name, schema)
        raw = self.ask(
            prompt,
            instructions=instructions,
            model=model,
            temperature=temperature,
            text_format=text_format,
            timeout_seconds=timeout_seconds,
        )
        return parse_json_object(raw)

    def stream_text(
        self,
        prompt,
        *,
        instructions=None,
        model=None,
        temperature=None,
        max_output_tokens=None,
        tools=None,
        reasoning_effort=None,
        timeout_seconds=None,
    ):
        """Yield assistant text as it arrives. Nothing is stored on xAI."""
        events = self.responses.stream_model_response_events(
            model=model or self.default_text_model,
            input=prompt,
            instructions=instructions,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            tools=tools,
            reasoning_effort=reasoning_effort,
            store_response_on_xai_servers=False,
            timeout_seconds=timeout_seconds,
        )
        with events as stream:
            for event in stream:
                delta = extract_text_delta(event)
                if delta:
                    yield delta

    def start_server_stored_conversation(self, **kwargs):
        """Start a multi-turn conversation stored on xAI for up to 30 days."""
        return ServerStoredConversation(self, **kwargs)

    def generate_image_from_text_prompt(self, prompt, **kwargs):
        return self.images.generate_image_from_text_prompt(prompt, **kwargs)

    def edit_image_with_prompt(self, prompt, **kwargs):
        return self.images.edit_image_with_prompt(prompt, **kwargs)

    def generate_video_from_text_prompt(self, prompt, **kwargs):
        return self.videos.generate_video_from_text_prompt(prompt, **kwargs)

    def wait_until_video_generation_finishes(self, request_id, **kwargs):
        return self.videos.wait_until_video_generation_finishes(request_id, **kwargs)

    def embed_texts(self, texts, **kwargs):
        """Return embedding vectors in the same order as texts."""
        body = self.embeddings.create_embedding_vectors(texts, **kwargs)
        data = body.get("data") or []
        if not isinstance(data, list):
            raise GrokApiError("The embeddings response did not include data.")
        ordered = sorted(
            data,
            key=lambda item: item.get("index", 0) if isinstance(item, dict) else 0,
        )
        return [item.get("embedding") if isinstance(item, dict) else None for item in ordered]

    def upload_file_from_path(self, path, **kwargs):
        return self.files.upload_file_from_path(path, **kwargs)

    def transcribe_audio_file(self, path, **kwargs):
        return self.voice.transcribe_audio_file(path, **kwargs)

    def speak(self, text, *, language="en", voice_id=DEFAULT_VOICE_ID, **kwargs):
        """Synthesize speech and return audio bytes."""
        return self.voice.synthesize_speech_audio_from_text(
            text,
            language=language,
            voice_id=voice_id,
            **kwargs,
        )

    def search_collection_documents(self, query, collection_ids, **kwargs):
        return self.documents.search_collection_documents(query, collection_ids, **kwargs)

    def count_tokens_in_text(self, text, *, model=None, timeout_seconds=None):
        return self.tokenize.count_tokens_in_text(
            text,
            model=model or self.default_text_model,
            timeout_seconds=timeout_seconds,
        )

    def list_all_models(self, **kwargs):
        return self.models.list_all_models(**kwargs)


class ServerStoredConversation:
    """Multi-turn chat that stores each response on xAI so the next turn can be short.

    Call delete_stored_responses when the conversation is finished.
    """

    def __init__(
        self,
        client,
        *,
        model=None,
        instructions=None,
        tools=None,
        tool_choice=None,
        reasoning_effort=None,
        safety_identifier=None,
    ):
        self._client = client
        self.model = model or client.default_text_model
        self.instructions = instructions
        self.tools = tools
        self.tool_choice = tool_choice
        self.reasoning_effort = reasoning_effort
        self.safety_identifier = safety_identifier
        self.response_ids = []

    def send_user_message(self, prompt, *, model=None):
        previous = self.response_ids[-1] if self.response_ids else None
        body = self._client.responses.create_model_response(
            model=model or self.model,
            input=prompt,
            instructions=None if previous else self.instructions,
            previous_response_id=previous,
            store_response_on_xai_servers=True,
            tools=self.tools,
            tool_choice=self.tool_choice,
            reasoning_effort=self.reasoning_effort,
            safety_identifier=self.safety_identifier,
        )
        response_id = body.get("id")
        if not isinstance(response_id, str) or not response_id:
            raise GrokApiError(
                "Stored response did not include an id, so the conversation cannot continue safely."
            )
        self.response_ids.append(response_id)
        return extract_output_text(body)

    def delete_stored_responses(self):
        """Delete every stored response id from this conversation."""
        remaining = []
        last_error = None
        for response_id in self.response_ids:
            try:
                self._client.responses.delete_stored_model_response(response_id)
            except GrokNotFoundError:
                continue
            except GrokError as exc:
                remaining.append(response_id)
                last_error = exc
        self.response_ids = remaining
        if last_error is not None:
            raise last_error


def _load_project_env_file():
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path(__file__).resolve().parents[2] / "backend" / ".env"
    load_dotenv(env_path)
