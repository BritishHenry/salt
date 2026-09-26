import os

from django.core.exceptions import ImproperlyConfigured
from supabase import create_client

LISTINGS_BUCKET = "listings"


def client():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise ImproperlyConfigured(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in backend/.env."
        )
    return create_client(url, key)


def upload_listing_image(path, data, content_type):
    """Upload image bytes to the public listings bucket and return its URL."""
    storage = client().storage.from_(LISTINGS_BUCKET)
    storage.upload(
        path,
        data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return storage.get_public_url(path)
