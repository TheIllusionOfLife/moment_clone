from unittest import mock
import os
from backend.core.settings import Settings

def test_cors_origins_default_is_secure():
    # Ensure no environment variables interfere
    with mock.patch.dict(os.environ, {}, clear=True):
        # Instantiate settings without environment variables override and ignore .env file
        # This should default to an empty list (secure)
        settings = Settings(_env_file=None)

        # Check that the default is NOT the insecure localhost values
        # The vulnerability is that it defaults to localhost:3000, localhost:3001
        assert "http://localhost:3000" not in settings.cors_origins_list
        assert "http://localhost:3001" not in settings.cors_origins_list
        # Ideally, it should be empty if no env var is set
        assert settings.cors_origins_list == []

def test_cors_origins_can_be_configured():
    # Verify that we can still configure CORS origins via arguments (simulating env vars)
    # We also ignore .env here to isolate the test
    settings = Settings(CORS_ORIGINS="http://example.com,http://test.com", _env_file=None)

    assert "http://example.com" in settings.cors_origins_list
    assert "http://test.com" in settings.cors_origins_list
    assert len(settings.cors_origins_list) == 2
