import asyncio
from datetime import timedelta

from google.cloud import storage

# Singleton client — initialized once, reused across all calls.
# ADC (Application Default Credentials) are resolved at first use.
_gcs_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _gcs_client
    if _gcs_client is None:
        _gcs_client = storage.Client()
    return _gcs_client


async def upload_file(
    bucket: str,
    object_path: str,
    file_bytes: bytes,
    content_type: str,
) -> str:
    """Upload bytes to GCS (runs in thread pool to avoid blocking event loop).

    Returns the GCS object path (not a signed URL).
    """

    def _sync_upload() -> None:
        blob = _get_client().bucket(bucket).blob(object_path)
        blob.upload_from_string(file_bytes, content_type=content_type)

    await asyncio.to_thread(_sync_upload)
    return object_path


def generate_signed_url(
    bucket: str,
    object_path: str,
    expiry_days: int = 7,
) -> str:
    """Generate a v4 signed URL for reading a GCS object.

    Requires the runtime service account to have the
    iam.serviceAccounts.signBlob permission. Uses Application Default
    Credentials (ADC) — run `gcloud auth application-default login`
    for local development.
    """
    blob = _get_client().bucket(bucket).blob(object_path)
    return blob.generate_signed_url(
        expiration=timedelta(days=expiry_days),
        method="GET",
        version="v4",
    )
