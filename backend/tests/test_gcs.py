import sys
from importlib import import_module
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(name="gcs_service")
def gcs_service_fixture():
    """
    Fixture that patches google dependencies in sys.modules,
    imports backend.services.gcs, and yields it.
    """
    mock_storage_pkg = MagicMock()
    mock_google_auth_pkg = MagicMock()
    mock_requests_pkg = MagicMock()
    mock_google_pkg = MagicMock()

    # Create the mock structure
    # We mock google.cloud.storage as a package that contains Client
    mock_storage_pkg.Client = MagicMock()

    # We mock google.auth as a package
    mock_google_auth_pkg.default = MagicMock()

    # We mock google.auth.transport.requests
    mock_requests_pkg.Request = MagicMock()

    modules_to_patch = {
        "google": mock_google_pkg,
        "google.cloud": MagicMock(),
        "google.cloud.storage": mock_storage_pkg,
        "google.auth": mock_google_auth_pkg,
        "google.auth.transport.requests": mock_requests_pkg,
    }

    # Use patch.dict to safely modify sys.modules temporarily
    with patch.dict(sys.modules, modules_to_patch):
        # Remove backend.services.gcs from sys.modules if it exists
        # to ensure it gets re-imported using our mocks
        original_gcs = sys.modules.pop("backend.services.gcs", None)

        try:
            # Import the module under test
            # We use import_module instead of import statement to avoid top-level imports in test file
            gcs_module = import_module("backend.services.gcs")

            # Since we popped it, it should be a fresh module using our mocks
            yield gcs_module

        finally:
            # Cleanup: remove our mocked version
            sys.modules.pop("backend.services.gcs", None)

            # Restore original if it existed
            if original_gcs:
                sys.modules["backend.services.gcs"] = original_gcs


@pytest.mark.asyncio
async def test_upload_file(gcs_service):
    """Test uploading a file to GCS."""
    bucket_name = "test-bucket"
    object_path = "test/path/video.mp4"
    content_type = "video/mp4"
    file_obj = MagicMock()

    # Access mocks through the imported module
    # The module imports: from google.cloud import storage
    mock_storage = gcs_service.storage

    # Configure the mock chain: client.bucket().blob().upload_from_file()
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_storage.Client.return_value = mock_client
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    # Patch _get_client inside the imported module instance
    # We need to patch it on the *module object* we got from the fixture
    with patch.object(gcs_service, "_get_client", return_value=mock_client):
        result = await gcs_service.upload_file(bucket_name, object_path, file_obj, content_type)

    assert result == object_path

    # Verify calls
    mock_client.bucket.assert_called_once_with(bucket_name)
    mock_bucket.blob.assert_called_once_with(object_path)
    mock_blob.upload_from_file.assert_called_once_with(file_obj, content_type=content_type)


@pytest.mark.asyncio
async def test_generate_signed_upload_url_success(gcs_service):
    """Test generating a signed upload URL successfully."""
    bucket_name = "test-bucket"
    object_path = "test/path/video.mp4"
    content_type = "video/mp4"
    expiry = 15
    expected_url = "https://storage.googleapis.com/signed-url"

    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.generate_signed_url.return_value = expected_url

    with patch.object(gcs_service, "_get_client", return_value=mock_client), \
         patch.object(gcs_service, "_get_signing_credentials", return_value=("sa@example.com", "access-token")):

        url = await gcs_service.generate_signed_upload_url(
            bucket_name, object_path, content_type, expiry
        )

    assert url == expected_url
    mock_blob.generate_signed_url.assert_called_once()
    _, kwargs = mock_blob.generate_signed_url.call_args
    assert kwargs["method"] == "PUT"
    assert kwargs["content_type"] == content_type
    assert kwargs["service_account_email"] == "sa@example.com"
    assert kwargs["access_token"] == "access-token"


@pytest.mark.asyncio
async def test_generate_signed_url_success(gcs_service):
    """Test generating a signed download URL successfully."""
    bucket_name = "test-bucket"
    object_path = "test/path/video.mp4"
    expected_url = "https://storage.googleapis.com/signed-read-url"

    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.generate_signed_url.return_value = expected_url

    with patch.object(gcs_service, "_get_client", return_value=mock_client), \
         patch.object(gcs_service, "_get_signing_credentials", return_value=("sa@example.com", "access-token")):

        url = await gcs_service.generate_signed_url(bucket_name, object_path)

    assert url == expected_url
    mock_blob.generate_signed_url.assert_called_once()
    _, kwargs = mock_blob.generate_signed_url.call_args
    assert kwargs["method"] == "GET"


@pytest.mark.asyncio
async def test_generate_signed_url_failure(gcs_service):
    """Test handling of signing failure."""
    bucket_name = "test-bucket"
    object_path = "test/path/video.mp4"

    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.generate_signed_url.side_effect = Exception("Signing failed")

    with patch.object(gcs_service, "_get_client", return_value=mock_client), \
         patch.object(gcs_service, "_get_signing_credentials", return_value=("sa@example.com", "access-token")):

        url = await gcs_service.generate_signed_url(bucket_name, object_path)

    assert url is None
