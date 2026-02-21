import asyncio
from datetime import timedelta
from typing import BinaryIO

from google.cloud import storage  # type: ignore[attr-defined]

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
    file_obj: BinaryIO,
    content_type: str,
) -> str:
    """Upload a file-like object to GCS (runs in thread pool to avoid blocking event loop).

    Accepts a BinaryIO so callers can pass FastAPI's SpooledTemporaryFile directly,
    avoiding buffering the full upload in Python memory.
    Returns the GCS object path (not a signed URL).
    """

    def _sync_upload() -> None:
        blob = _get_client().bucket(bucket).blob(object_path)
        blob.upload_from_file(file_obj, content_type=content_type)

    await asyncio.to_thread(_sync_upload)
    return object_path


async def generate_signed_url(
    bucket: str,
    object_path: str,
    expiry_days: int = 7,
) -> str:
    """Generate a v4 signed URL for reading a GCS object (runs in thread pool).

    The IAM signBlob round-trip is blocking; offload to a thread to avoid
    stalling the event loop. Requires the runtime service account to have the
    iam.serviceAccounts.signBlob permission. Uses Application Default
    Credentials (ADC) — run `gcloud auth application-default login`
    for local development.
    """

    def _sync_sign() -> str:
        blob = _get_client().bucket(bucket).blob(object_path)
        return blob.generate_signed_url(
            expiration=timedelta(days=expiry_days),
            method="GET",
            version="v4",
        )

    return await asyncio.to_thread(_sync_sign)
