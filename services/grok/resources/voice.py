"""Text to speech, speech to text, and custom voices."""

from __future__ import annotations

import mimetypes
import re

from services.grok.constants import (
    AUDIO_SAMPLE_RATES,
    DEFAULT_VOICE_ID,
    MAX_PAGINATION_PAGES,
    MAX_RESPONSE_BYTES,
    MAX_STT_UPLOAD_BYTES,
    MAX_TTS_CHARACTERS,
    MP3_BIT_RATES,
    TTS_CODECS,
)
from services.grok.errors import GrokApiError, GrokUsageError
from services.grok.resources.base import Resource
from services.grok.safety import (
    UNSET,
    optional_bool,
    optional_choice,
    optional_int,
    optional_language,
    optional_number,
    optional_text,
    read_file_with_limit,
    require_https_url,
    require_language,
    require_resource_id,
    require_text,
    safe_content_type,
    safe_filename,
    without_none,
)
from services.grok.transport import encode_multipart_form

_RAW_AUDIO_FORMATS = frozenset({"pcm", "mulaw", "alaw"})
_CONTAINER_AUDIO_FORMATS = frozenset(
    {"wav", "mp3", "ogg", "opus", "flac", "aac", "mp4", "m4a", "mkv"}
)
_VOICE_GENDERS = frozenset({"male", "female", "neutral"})
_VOICE_AGES = frozenset({"young", "middle-aged", "old"})
_VOICE_USE_CASES = frozenset(
    {
        "conversational",
        "narration",
        "characters",
        "educational",
        "advertisement",
        "social_media",
        "entertainment",
    }
)
_VOICE_TONES = frozenset(
    {"warm", "casual", "professional", "friendly", "authoritative", "expressive", "calm"}
)
_REPLACE_KEY = re.compile(r"^[A-Za-z0-9' ]{1,100}$")


class VoiceResource(Resource):
    def synthesize_speech_audio_from_text(
        self,
        text,
        *,
        language,
        voice_id=DEFAULT_VOICE_ID,
        codec=None,
        sample_rate=None,
        bit_rate=None,
        speed=None,
        text_normalization=None,
        optimize_streaming_latency=None,
        replace=None,
        timeout_seconds=None,
    ):
        """POST /v1/tts. Returns audio bytes in the requested codec (mp3 by default)."""
        body = _speech_body(
            text=text,
            language=language,
            voice_id=voice_id,
            codec=codec,
            sample_rate=sample_rate,
            bit_rate=bit_rate,
            speed=speed,
            text_normalization=text_normalization,
            optimize_streaming_latency=optimize_streaming_latency,
            replace=replace,
            with_timestamps=False,
        )
        result = self._http.send(
            "POST",
            "/v1/tts",
            json_body=body,
            parse_json=False,
            timeout_seconds=timeout_seconds or 180,
            max_response_bytes=MAX_RESPONSE_BYTES,
        )
        if result.content_type == "application/json":
            raise GrokApiError(
                "Speech synthesis returned JSON instead of audio. "
                "Use synthesize_speech_with_character_timestamps when you need timings.",
                status_code=result.status_code,
            )
        return result.body

    def synthesize_speech_with_character_timestamps(
        self,
        text,
        *,
        language,
        voice_id=DEFAULT_VOICE_ID,
        codec=None,
        sample_rate=None,
        bit_rate=None,
        speed=None,
        text_normalization=None,
        replace=None,
        timeout_seconds=None,
    ):
        """POST /v1/tts with with_timestamps=true. Returns JSON, including base64 audio."""
        body = _speech_body(
            text=text,
            language=language,
            voice_id=voice_id,
            codec=codec,
            sample_rate=sample_rate,
            bit_rate=bit_rate,
            speed=speed,
            text_normalization=text_normalization,
            replace=replace,
            with_timestamps=True,
        )
        return self._json("POST", "/v1/tts", body=body, timeout_seconds=timeout_seconds or 180)

    def list_built_in_voices(self, *, timeout_seconds=None):
        """GET /v1/tts/voices."""
        return self._json("GET", "/v1/tts/voices", timeout_seconds=timeout_seconds)

    def retrieve_built_in_voice(self, voice_id, *, timeout_seconds=None):
        """GET /v1/tts/voices/{voice_id}."""
        return self._json(
            "GET",
            f"/v1/tts/voices/{require_resource_id(voice_id, 'voice_id')}",
            timeout_seconds=timeout_seconds,
        )

    def text_to_speech_websocket_connection(
        self,
        *,
        language,
        voice_id=DEFAULT_VOICE_ID,
        codec="mp3",
        sample_rate=24000,
        bit_rate=128000,
        speed=None,
        text_normalization=False,
        with_timestamps=False,
        optimize_streaming_latency=0,
    ):
        """Connection details for wss://api.x.ai/v1/tts. The API key is only in headers.

        Send text_to_speech_delta_message and text_to_speech_done_message after connecting.
        This client does not open the socket.
        """
        query = {
            "language": require_language(language),
            "voice": require_resource_id(voice_id, "voice_id"),
            "codec": optional_choice(codec, "codec", TTS_CODECS),
            "sample_rate": optional_choice(sample_rate, "sample_rate", AUDIO_SAMPLE_RATES),
            "bit_rate": optional_choice(bit_rate, "bit_rate", MP3_BIT_RATES) if codec == "mp3" else None,
            "speed": optional_number(speed, "speed", minimum=0.5, maximum=2),
            "text_normalization": bool(text_normalization),
            "with_timestamps": bool(with_timestamps),
            "optimize_streaming_latency": optional_choice(
                optimize_streaming_latency, "optimize_streaming_latency", {0, 1}
            ),
        }
        return self._http.websocket_connection("/v1/tts", query)

    def transcribe_audio_file(
        self,
        path,
        *,
        language=None,
        audio_format=None,
        sample_rate=None,
        format_text=None,
        multichannel=None,
        channels=None,
        diarize=None,
        keyterms=None,
        filler_words=None,
        vad_threshold=None,
        timeout_seconds=None,
    ):
        """POST /v1/stt with a local audio file. Maximum size is 500 MB."""
        data, filename = read_file_with_limit(path, MAX_STT_UPLOAD_BYTES, "path")
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return self._transcribe(
            fields=_transcription_fields(
                language=language,
                audio_format=audio_format,
                sample_rate=sample_rate,
                format_text=format_text,
                multichannel=multichannel,
                channels=channels,
                diarize=diarize,
                keyterms=keyterms,
                filler_words=filler_words,
                vad_threshold=vad_threshold,
            ),
            file_part=("file", filename, safe_content_type(content_type), data),
            timeout_seconds=timeout_seconds,
        )

    def transcribe_audio_bytes(
        self,
        data,
        *,
        filename,
        content_type=None,
        language=None,
        audio_format=None,
        sample_rate=None,
        format_text=None,
        multichannel=None,
        channels=None,
        diarize=None,
        keyterms=None,
        filler_words=None,
        vad_threshold=None,
        timeout_seconds=None,
    ):
        """POST /v1/stt with audio bytes already in memory."""
        if not isinstance(data, (bytes, bytearray)):
            raise GrokUsageError("data must be bytes.")
        if len(data) > MAX_STT_UPLOAD_BYTES:
            raise GrokUsageError(
                f"Speech-to-text audio must be at most {MAX_STT_UPLOAD_BYTES} bytes."
            )
        return self._transcribe(
            fields=_transcription_fields(
                language=language,
                audio_format=audio_format,
                sample_rate=sample_rate,
                format_text=format_text,
                multichannel=multichannel,
                channels=channels,
                diarize=diarize,
                keyterms=keyterms,
                filler_words=filler_words,
                vad_threshold=vad_threshold,
            ),
            file_part=(
                "file",
                safe_filename(filename),
                safe_content_type(content_type),
                bytes(data),
            ),
            timeout_seconds=timeout_seconds,
        )

    def transcribe_audio_from_url(
        self,
        url,
        *,
        language=None,
        format_text=None,
        multichannel=None,
        diarize=None,
        keyterms=None,
        filler_words=None,
        vad_threshold=None,
        timeout_seconds=None,
    ):
        """POST /v1/stt asking xAI to fetch an https audio URL."""
        fields = _transcription_fields(
            language=language,
            audio_format=None,
            sample_rate=None,
            format_text=format_text,
            multichannel=multichannel,
            channels=None,
            diarize=diarize,
            keyterms=keyterms,
            filler_words=filler_words,
            vad_threshold=vad_threshold,
        )
        fields.append(("url", require_https_url(url, "url")))
        return self._transcribe(fields=fields, file_part=None, timeout_seconds=timeout_seconds)

    def speech_to_text_websocket_connection(
        self,
        *,
        sample_rate=16000,
        encoding="pcm",
        interim_results=False,
        endpointing=None,
        language=None,
        multichannel=False,
        channels=None,
        diarize=False,
        keyterms=None,
        filler_words=False,
        smart_turn=None,
        smart_turn_timeout=None,
        vad_threshold=None,
    ):
        """Connection details for wss://api.x.ai/v1/stt. Send raw audio frames after connecting."""
        if encoding not in {"pcm", "mulaw", "alaw"}:
            raise GrokUsageError("encoding must be 'pcm', 'mulaw', or 'alaw'.")
        if multichannel and (channels is None or channels < 2):
            raise GrokUsageError("multichannel transcription requires channels between 2 and 8.")
        query = without_none(
            {
                "sample_rate": optional_choice(sample_rate, "sample_rate", AUDIO_SAMPLE_RATES),
                "encoding": encoding,
                "interim_results": bool(interim_results),
                "endpointing": optional_int(endpointing, "endpointing", minimum=0, maximum=5000),
                "language": optional_language(language),
                "multichannel": bool(multichannel),
                "channels": optional_int(channels, "channels", minimum=1, maximum=8),
                "diarize": bool(diarize),
                "keyterm": _keyterms(keyterms),
                "filler_words": bool(filler_words),
                "smart_turn": optional_number(smart_turn, "smart_turn", minimum=0, maximum=1),
                "smart_turn_timeout": optional_int(
                    smart_turn_timeout, "smart_turn_timeout", minimum=1, maximum=5000
                ),
                "vad_threshold": optional_number(vad_threshold, "vad_threshold", minimum=0, maximum=1),
            }
        )
        return self._http.websocket_connection("/v1/stt", query)

    def create_custom_voice_from_audio_file(
        self,
        path,
        *,
        name=None,
        description=None,
        gender=None,
        accent=None,
        age=None,
        language=None,
        use_case=None,
        tone=None,
        timeout_seconds=None,
    ):
        """POST /v1/custom-voices. Reference audio can be at most 120 seconds."""
        data, filename = read_file_with_limit(path, MAX_STT_UPLOAD_BYTES, "path")
        fields = _custom_voice_fields(
            name=name,
            description=description,
            gender=gender,
            accent=accent,
            age=age,
            language=language,
            use_case=use_case,
            tone=tone,
        )
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        raw, form_type = encode_multipart_form(
            fields,
            [("file", filename, safe_content_type(content_type), data)],
        )
        result = self._http.send(
            "POST",
            "/v1/custom-voices",
            raw_body=raw,
            content_type=form_type,
            timeout_seconds=timeout_seconds or 180,
            max_request_bytes=MAX_STT_UPLOAD_BYTES + 1_000_000,
            parse_json=True,
        )
        return result.json_body or {}

    def list_custom_voices_page(self, *, limit=None, pagination_token=None, timeout_seconds=None):
        """GET /v1/custom-voices."""
        query = without_none(
            {
                "limit": optional_int(limit, "limit", minimum=1, maximum=1000),
                "pagination_token": optional_text(pagination_token, "pagination_token", max_length=2000)
                if pagination_token is not None
                else None,
            }
        )
        return self._json("GET", "/v1/custom-voices", query=query, timeout_seconds=timeout_seconds)

    def list_all_custom_voices(
        self,
        *,
        limit=100,
        max_pages=MAX_PAGINATION_PAGES,
        timeout_seconds=None,
    ):
        def fetch(token):
            return self.list_custom_voices_page(
                limit=limit,
                pagination_token=token,
                timeout_seconds=timeout_seconds,
            )

        return self._collect_token_pages(fetch, items_key="voices", max_pages=max_pages)

    def retrieve_custom_voice(self, voice_id, *, timeout_seconds=None):
        """GET /v1/custom-voices/{voice_id}."""
        return self._json(
            "GET",
            f"/v1/custom-voices/{require_resource_id(voice_id, 'voice_id')}",
            timeout_seconds=timeout_seconds,
        )

    def update_custom_voice_metadata(
        self,
        voice_id,
        *,
        name=UNSET,
        description=UNSET,
        gender=UNSET,
        accent=UNSET,
        age=UNSET,
        language=UNSET,
        use_case=UNSET,
        tone=UNSET,
        timeout_seconds=None,
    ):
        """PATCH /v1/custom-voices/{voice_id}. Omitted fields stay unchanged. None clears a field."""
        body = {}
        if name is not UNSET:
            body["name"] = None if name is None else optional_text(name, "name", max_length=200)
        if description is not UNSET:
            body["description"] = (
                None if description is None else optional_text(description, "description", max_length=2000)
            )
        if gender is not UNSET:
            body["gender"] = None if gender is None else optional_choice(gender, "gender", _VOICE_GENDERS)
        if accent is not UNSET:
            body["accent"] = None if accent is None else optional_text(accent, "accent", max_length=100)
        if age is not UNSET:
            body["age"] = None if age is None else optional_choice(age, "age", _VOICE_AGES)
        if language is not UNSET:
            body["language"] = None if language is None else optional_language(language)
        if use_case is not UNSET:
            body["use_case"] = (
                None if use_case is None else optional_choice(use_case, "use_case", _VOICE_USE_CASES)
            )
        if tone is not UNSET:
            body["tone"] = None if tone is None else optional_choice(tone, "tone", _VOICE_TONES)
        if not body:
            raise GrokUsageError("Provide at least one custom voice field to update.")
        return self._json(
            "PATCH",
            f"/v1/custom-voices/{require_resource_id(voice_id, 'voice_id')}",
            body=body,
            timeout_seconds=timeout_seconds,
        )

    def delete_custom_voice(self, voice_id, *, timeout_seconds=None):
        """DELETE /v1/custom-voices/{voice_id}."""
        return self._json(
            "DELETE",
            f"/v1/custom-voices/{require_resource_id(voice_id, 'voice_id')}",
            timeout_seconds=timeout_seconds,
        )

    def download_custom_voice_reference_audio(self, voice_id, *, timeout_seconds=None):
        """GET /v1/custom-voices/{voice_id}/audio."""
        return self._bytes(
            "GET",
            f"/v1/custom-voices/{require_resource_id(voice_id, 'voice_id')}/audio",
            timeout_seconds=timeout_seconds,
            max_response_bytes=MAX_RESPONSE_BYTES,
        )

    def _transcribe(self, *, fields, file_part, timeout_seconds):
        files = [file_part] if file_part is not None else []
        raw, form_type = encode_multipart_form(fields, files)
        result = self._http.send(
            "POST",
            "/v1/stt",
            raw_body=raw,
            content_type=form_type,
            timeout_seconds=timeout_seconds or 600,
            max_request_bytes=MAX_STT_UPLOAD_BYTES + 1_000_000,
            parse_json=True,
        )
        return result.json_body or {}


def _speech_body(
    *,
    text,
    language,
    voice_id,
    codec,
    sample_rate,
    bit_rate,
    speed,
    text_normalization,
    replace,
    with_timestamps,
    optimize_streaming_latency=None,
):
    output_format = None
    if any(value is not None for value in (codec, sample_rate, bit_rate)):
        chosen_codec = codec or "mp3"
        output_format = without_none(
            {
                "codec": optional_choice(chosen_codec, "codec", TTS_CODECS),
                "sample_rate": optional_choice(sample_rate, "sample_rate", AUDIO_SAMPLE_RATES),
                "bit_rate": optional_choice(bit_rate, "bit_rate", MP3_BIT_RATES)
                if chosen_codec == "mp3"
                else None,
            }
        )
        if chosen_codec != "mp3" and bit_rate is not None:
            raise GrokUsageError("bit_rate applies only to the mp3 codec.")
    body = without_none(
        {
            "text": require_text(text, "text", max_length=MAX_TTS_CHARACTERS),
            "language": require_language(language),
            "voice_id": require_resource_id(voice_id, "voice_id"),
            "output_format": output_format,
            "speed": optional_number(speed, "speed", minimum=0.5, maximum=2),
            "text_normalization": optional_bool(text_normalization, "text_normalization"),
            "optimize_streaming_latency": _latency(optimize_streaming_latency),
            "replace": _replace_map(replace),
        }
    )
    if with_timestamps:
        body["with_timestamps"] = True
    return body


def _latency(value):
    if value is None:
        return None
    if value not in {0, 1, "0", "1"}:
        raise GrokUsageError("optimize_streaming_latency must be 0 or 1.")
    return str(value)


def _replace_map(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise GrokUsageError("replace must be an object of written phrases to spoken phrases.")
    if len(value) > 200:
        raise GrokUsageError("replace accepts at most 200 entries.")
    cleaned = {}
    for key, spoken in value.items():
        if not isinstance(key, str) or not _REPLACE_KEY.fullmatch(key):
            raise GrokUsageError(
                "replace keys may contain only letters, digits, apostrophes, and spaces."
            )
        cleaned[key] = require_text(spoken, "replace value", max_length=128)
    return cleaned


def _transcription_fields(
    *,
    language,
    audio_format,
    sample_rate,
    format_text,
    multichannel,
    channels,
    diarize,
    keyterms,
    filler_words,
    vad_threshold,
):
    if audio_format is not None and audio_format not in _RAW_AUDIO_FORMATS | _CONTAINER_AUDIO_FORMATS:
        raise GrokUsageError("audio_format is not a supported speech-to-text format.")
    if audio_format in _RAW_AUDIO_FORMATS and sample_rate is None:
        raise GrokUsageError("sample_rate is required for raw pcm, mulaw, and alaw audio.")
    if format_text and not language:
        raise GrokUsageError("format_text requires language so numbers and units can be written out.")
    fields = []
    if language is not None:
        fields.append(("language", optional_language(language)))
    if audio_format is not None:
        fields.append(("audio_format", audio_format))
    if sample_rate is not None:
        fields.append(
            ("sample_rate", str(optional_choice(sample_rate, "sample_rate", AUDIO_SAMPLE_RATES)))
        )
    if format_text is not None:
        fields.append(("format", "true" if format_text else "false"))
    if multichannel is not None:
        fields.append(("multichannel", "true" if multichannel else "false"))
    if channels is not None:
        fields.append(("channels", str(optional_int(channels, "channels", minimum=2, maximum=8))))
    if diarize is not None:
        fields.append(("diarize", "true" if diarize else "false"))
    for term in _keyterms(keyterms) or []:
        fields.append(("keyterm", term))
    if filler_words is not None:
        fields.append(("filler_words", "true" if filler_words else "false"))
    if vad_threshold is not None:
        fields.append(
            ("vad_threshold", str(optional_number(vad_threshold, "vad_threshold", minimum=0, maximum=1)))
        )
    return fields


def _keyterms(values):
    if values is None:
        return None
    if not isinstance(values, list) or len(values) > 100:
        raise GrokUsageError("keyterms accepts at most 100 phrases.")
    return [require_text(item, "keyterms", max_length=50) for item in values]


def _custom_voice_fields(*, name, description, gender, accent, age, language, use_case, tone):
    pairs = without_none(
        {
            "name": optional_text(name, "name", max_length=200),
            "description": optional_text(description, "description", max_length=2000),
            "gender": optional_choice(gender, "gender", _VOICE_GENDERS),
            "accent": optional_text(accent, "accent", max_length=100),
            "age": optional_choice(age, "age", _VOICE_AGES),
            "language": optional_language(language),
            "use_case": optional_choice(use_case, "use_case", _VOICE_USE_CASES),
            "tone": optional_choice(tone, "tone", _VOICE_TONES),
        }
    )
    return list(pairs.items())
