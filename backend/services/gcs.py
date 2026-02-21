from datetime import timedelta

from google.cloud import storage


def upload_file(
    bucket: str,
    object_path: str,
    file_bytes: bytes,
    content_type: str,
) -> str:
    """Upload bytes to GCS. Returns the GCS object path (not a signed URL)."""
    client = storage.Client()
    blob = client.bucket(bucket).blob(object_path)
    blob.upload_from_string(file_bytes, content_type=content_type)
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
    client = storage.Client()
    blob = client.bucket(bucket).blob(object_path)
    return blob.generate_signed_url(
        expiration=timedelta(days=expiry_days),
        method="GET",
        version="v4",
    )
