"""
Unit tests for web_app_factory._keychain module.

All tests mock keyring to avoid real OS keychain access in CI/CD.
"""
import logging
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestStoreAndRetrieve:
    """Test 1: Basic store and retrieve roundtrip via mocked keyring."""

    def test_store_and_retrieve(self):
        mock_storage: dict[str, str] = {}

        def mock_set(service, key, value):
            mock_storage[key] = value

        def mock_get(service, key):
            return mock_storage.get(key)

        with patch("keyring.set_password", side_effect=mock_set), patch(
            "keyring.get_password", side_effect=mock_get
        ):
            from web_app_factory._keychain import get_credential, store_credential

            result = store_credential("test_key", "test_value")
            assert result is True

            retrieved = get_credential("test_key")
            assert retrieved == "test_value"


class TestEnvVarFallback:
    """Test 2: Env-var fallback when keyring raises KeyringError."""

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("VERCEL_TOKEN", "env_vercel_token_value")

        with patch("keyring.get_password", side_effect=Exception("KeyringError: no backend")):
            from web_app_factory._keychain import get_credential

            result = get_credential("vercel_token")
            assert result == "env_vercel_token_value"


class TestKeyringUnavailableImport:
    """Test 3: When keyring module is not installed, store returns False and get falls back to env."""

    def test_keyring_unavailable_import(self, monkeypatch):
        monkeypatch.setenv("VERCEL_TOKEN", "fallback_value")

        with patch("web_app_factory._keychain._KEYRING_AVAILABLE", False):
            from web_app_factory._keychain import get_credential, store_credential

            store_result = store_credential("vercel_token", "some_secret")
            assert store_result is False

            get_result = get_credential("vercel_token")
            assert get_result == "fallback_value"


class TestNoCredentialInLogs:
    """Test 4: Credential values must never appear in any log output at any level."""

    def test_no_credential_in_logs(self, caplog):
        secret_value = "super_secret_value_12345"
        mock_storage: dict[str, str] = {}

        def mock_set(service, key, value):
            mock_storage[key] = value

        def mock_get(service, key):
            return mock_storage.get(key)

        with patch("keyring.set_password", side_effect=mock_set), patch(
            "keyring.get_password", side_effect=mock_get
        ):
            from web_app_factory._keychain import get_credential, store_credential

            with caplog.at_level(logging.DEBUG, logger="web_app_factory._keychain"):
                store_credential("some_key", secret_value)
                get_credential("some_key")

        for record in caplog.records:
            assert secret_value not in record.getMessage(), (
                f"Credential value found in log record at level {record.levelname}: "
                f"{record.getMessage()!r}"
            )


class TestDeleteCredential:
    """Test 5: delete_credential removes the key from keychain."""

    def test_delete_credential(self):
        mock_storage: dict[str, str] = {}

        def mock_set(service, key, value):
            mock_storage[key] = value

        def mock_get(service, key):
            return mock_storage.get(key)

        def mock_delete(service, key):
            mock_storage.pop(key, None)

        with patch("keyring.set_password", side_effect=mock_set), patch(
            "keyring.get_password", side_effect=mock_get
        ), patch("keyring.delete_password", side_effect=mock_delete):
            from web_app_factory._keychain import delete_credential, get_credential, store_credential

            store_credential("to_delete_key", "delete_value")
            assert mock_storage.get("to_delete_key") == "delete_value"

            result = delete_credential("to_delete_key")
            assert result is True
            assert "to_delete_key" not in mock_storage


class TestGetCredentialReturnsNone:
    """Test 6: When key is not in keychain and no env var is set, get_credential returns None."""

    def test_get_credential_returns_none(self, monkeypatch):
        # Ensure the env var is NOT set
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch("keyring.get_password", return_value=None):
            from web_app_factory._keychain import get_credential

            result = get_credential("anthropic_api_key")
            assert result is None
