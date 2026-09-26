"""Image generation and editing."""

from __future__ import annotations

from services.grok.builders import image_reference
from services.grok.constants import (
    DEFAULT_IMAGE_MODEL,
    IMAGE_ASPECT_RATIOS,
    IMAGE_RESOLUTIONS,
)
from services.grok.errors import GrokUsageError
from services.grok.resources.base import Resource
from services.grok.safety import (
    merge_additional_fields,
    optional_choice,
    optional_dict,
    optional_identifier,
    optional_int,
    optional_text,
    require_model_name,
    require_text,
    without_none,
)


class ImagesResource(Resource):
    def generate_image_from_text_prompt(
        self,
        prompt,
        *,
        model=DEFAULT_IMAGE_MODEL,
        aspect_ratio=None,
        resolution=None,
        number_of_images=None,
        response_format=None,
        storage_options=None,
        user=None,
        additional_fields=None,
        timeout_seconds=None,
    ):
        """POST /v1/images/generations."""
        body = _image_body(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            number_of_images=number_of_images,
            response_format=response_format,
            storage_options=storage_options,
            user=user,
            additional_fields=additional_fields,
        )
        return self._json("POST", "/v1/images/generations", body=body, timeout_seconds=timeout_seconds)

    def edit_image_with_prompt(
        self,
        prompt,
        *,
        image_url=None,
        image_file_id=None,
        images=None,
        model=DEFAULT_IMAGE_MODEL,
        aspect_ratio=None,
        resolution=None,
        number_of_images=None,
        response_format=None,
        storage_options=None,
        user=None,
        additional_fields=None,
        timeout_seconds=None,
    ):
        """POST /v1/images/edits.

        Pass one image with image_url or image_file_id, or several references
        in images. Each reference is an object from image_reference().
        """
        single = image_url is not None or image_file_id is not None
        if single == (images is not None):
            raise GrokUsageError("Provide one image or a list of images, not both.")
        if single:
            image = image_reference(file_id=image_file_id, url=image_url)
            extra = {"image": image}
        else:
            if not isinstance(images, list) or not images:
                raise GrokUsageError("images must be a non-empty list of image references.")
            extra = {"images": images}
        body = _image_body(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            number_of_images=number_of_images,
            response_format=response_format,
            storage_options=storage_options,
            user=user,
            additional_fields=additional_fields,
        )
        body.update(extra)
        return self._json("POST", "/v1/images/edits", body=body, timeout_seconds=timeout_seconds)


def _image_body(
    *,
    prompt,
    model,
    aspect_ratio,
    resolution,
    number_of_images,
    response_format,
    storage_options,
    user,
    additional_fields,
):
    if response_format is not None and response_format not in {"url", "b64_json"}:
        raise GrokUsageError("response_format must be 'url' or 'b64_json'.")
    body = without_none(
        {
            "prompt": require_text(prompt, "prompt", max_length=20_000),
            "model": require_model_name(model) if model is not None else None,
            "aspect_ratio": optional_choice(aspect_ratio, "aspect_ratio", IMAGE_ASPECT_RATIOS),
            "resolution": optional_choice(resolution, "resolution", IMAGE_RESOLUTIONS),
            "n": optional_int(number_of_images, "number_of_images", minimum=1, maximum=10),
            "response_format": response_format,
            "storage_options": optional_dict(storage_options, "storage_options"),
            "user": optional_identifier(user, "user"),
        }
    )
    return merge_additional_fields(body, additional_fields)
