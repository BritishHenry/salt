"""Asynchronous video generation, editing, and extension."""

from __future__ import annotations

from services.grok.builders import audio_reference, image_reference, video_reference
from services.grok.constants import VIDEO_ASPECT_RATIOS, VIDEO_RESOLUTIONS
from services.grok.errors import GrokUsageError
from services.grok.parsing import video_failure_message
from services.grok.resources.base import Resource
from services.grok.safety import (
    merge_additional_fields,
    optional_choice,
    optional_dict,
    optional_identifier,
    optional_int,
    optional_number,
    require_model_name,
    require_resource_id,
    require_text,
    without_none,
)


class VideosResource(Resource):
    def generate_video_from_text_prompt(
        self,
        prompt,
        *,
        model=None,
        image_url=None,
        image_file_id=None,
        reference_images=None,
        reference_audios=None,
        keyframes=None,
        duration_seconds=None,
        aspect_ratio=None,
        resolution=None,
        output=None,
        storage_options=None,
        user=None,
        additional_fields=None,
        timeout_seconds=None,
    ):
        """POST /v1/videos/generations. Returns a request id to poll."""
        image = None
        if image_url is not None or image_file_id is not None:
            image = image_reference(file_id=image_file_id, url=image_url)
        body = _video_body(
            prompt=prompt,
            model=model,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            output=output,
            storage_options=storage_options,
            user=user,
            additional_fields=additional_fields,
        )
        body.update(
            without_none(
                {
                    "image": image,
                    "reference_images": reference_images,
                    "reference_audios": reference_audios,
                    "keyframes": keyframes,
                }
            )
        )
        return self._json("POST", "/v1/videos/generations", body=body, timeout_seconds=timeout_seconds)

    def edit_video_with_prompt(
        self,
        prompt,
        *,
        video_url=None,
        video_file_id=None,
        model=None,
        output=None,
        storage_options=None,
        user=None,
        additional_fields=None,
        timeout_seconds=None,
    ):
        """POST /v1/videos/edits. Returns a request id to poll."""
        body = _video_body(
            prompt=prompt,
            model=model,
            output=output,
            storage_options=storage_options,
            user=user,
            additional_fields=additional_fields,
        )
        body["video"] = video_reference(file_id=video_file_id, url=video_url)
        return self._json("POST", "/v1/videos/edits", body=body, timeout_seconds=timeout_seconds)

    def extend_video_with_prompt(
        self,
        prompt,
        *,
        video_url=None,
        video_file_id=None,
        model=None,
        duration_seconds=None,
        output=None,
        storage_options=None,
        additional_fields=None,
        timeout_seconds=None,
    ):
        """POST /v1/videos/extensions. Returns a request id to poll."""
        body = _video_body(
            prompt=prompt,
            model=model,
            duration_seconds=duration_seconds,
            output=output,
            storage_options=storage_options,
            additional_fields=additional_fields,
        )
        body["video"] = video_reference(file_id=video_file_id, url=video_url)
        return self._json("POST", "/v1/videos/extensions", body=body, timeout_seconds=timeout_seconds)

    def fetch_video_generation_result(self, request_id, *, timeout_seconds=None):
        """GET /v1/videos/{request_id}. pending is true while status is pending."""
        return self._deferred(
            "GET",
            f"/v1/videos/{require_resource_id(request_id, 'request_id')}",
            timeout_seconds=timeout_seconds,
        )

    def wait_until_video_generation_finishes(
        self,
        request_id,
        *,
        poll_interval_seconds=2.0,
        timeout_seconds=600.0,
        sleep=None,
        monotonic=None,
    ):
        """Poll until a video generation is done, failed, or the timeout elapses."""
        return self._wait_until_ready(
            lambda: self.fetch_video_generation_result(request_id),
            request_id=request_id,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
            sleep=sleep,
            monotonic=monotonic,
            operation_name="Video generation",
            failed_message=video_failure_message,
        )


def reference_audio(*, voice_id=None, url=None):
    """Alias kept next to the video methods for call sites that build clips inline."""
    return audio_reference(voice_id=voice_id, url=url)


def video_keyframe(*, image_url=None, image_file_id=None, timestamp_seconds):
    timestamp = optional_number(
        timestamp_seconds, "timestamp_seconds", minimum=0, maximum=120
    )
    if timestamp is None or timestamp <= 0:
        raise GrokUsageError("timestamp_seconds must be greater than 0 and inside the clip.")
    return {
        "image": image_reference(file_id=image_file_id, url=image_url),
        "timestamp_s": timestamp,
    }


def _video_body(
    *,
    prompt,
    model=None,
    duration_seconds=None,
    aspect_ratio=None,
    resolution=None,
    output=None,
    storage_options=None,
    user=None,
    additional_fields=None,
):
    body = without_none(
        {
            "prompt": require_text(prompt, "prompt", max_length=20_000),
            "model": require_model_name(model) if model is not None else None,
            "duration": optional_int(duration_seconds, "duration_seconds", minimum=1, maximum=120),
            "aspect_ratio": optional_choice(aspect_ratio, "aspect_ratio", VIDEO_ASPECT_RATIOS),
            "resolution": optional_choice(resolution, "resolution", VIDEO_RESOLUTIONS),
            "output": optional_dict(output, "output"),
            "storage_options": optional_dict(storage_options, "storage_options"),
            "user": optional_identifier(user, "user"),
        }
    )
    return merge_additional_fields(body, additional_fields)
