from __future__ import annotations

from .config import GCS_BUCKET


def upload_bytes(data: bytes, object_name: str, content_type: str) -> str | None:
    """Upload to GCS only when GCS_BUCKET is configured; local mode remains dependency-light."""
    if not GCS_BUCKET:
        return None
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(object_name)
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{GCS_BUCKET}/{object_name}"
    except Exception:
        # Storage must never break a learning session. Runtime logs/cloud monitoring
        # can be used to investigate cloud upload failures.
        return None
