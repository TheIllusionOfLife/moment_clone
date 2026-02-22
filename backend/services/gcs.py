import asyncio
from datetime import timedelta
from typing import BinaryIO

import google.auth  # type: ignore[import-untyped]
import google.auth.transport.requests  # type: ignore[import-untyped]
from google.cloud import storage  # type: ignore[attr-defined]

# Singleton client — initialized once, reused across all calls.
# ADC (Application Default Credentials) are resolved at first use.
_gcs_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _gcs_client
    if _gcs_client is None:
        _gcs_client = storage.Client()
    return _gcs_client


def _get_signing_credentials() -> tuple[str, str]:
    """Return (service_account_email, access_token) for signed URL generation.

    On Cloud Run the runtime credentials are Compute Engine credentials that
    don't carry a private key, so we can't sign locally.  Instead we pass the
    SA email + a fresh access token to generate_signed_url(), which makes the
    SDK delegate signing to the IAM signBlob API.

    For local development with a service-account key file (GOOGLE_APPLICATION_CREDENTIALS)
    google.auth.default() returns ServiceAccountCredentials, which DO have a private
    key — but generate_signed_url() ignores the extra kwargs when a signer is already
    present, so the same code path works everywhere.
    """
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    sa_email: str = getattr(credentials, "service_account_email", "")
    token: str = getattr(credentials, "token", "")
    return sa_email, token


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
        sa_email, access_token = _get_signing_credentials()
        blob = _get_client().bucket(bucket).blob(object_path)
        kwargs: dict = dict(
            expiration=timedelta(days=expiry_days),
            method="GET",
            version="v4",
        )
        if sa_email and access_token:
            kwargs["service_account_email"] = sa_email
            kwargs["access_token"] = access_token
        return blob.generate_signed_url(**kwargs)

    return await asyncio.to_thread(_sync_sign)
