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


# ---------------------------------------------------------------------------
# Banto integration tests
# ---------------------------------------------------------------------------


class TestBantoFirstLookup:
    """Test 7: banto is consulted first when _BANTO_AVAILABLE is True."""

    def test_banto_returns_value_before_keyring(self, monkeypatch):
        """get_credential returns banto value without consulting keyring."""
        mock_vault = MagicMock()
        mock_vault.get_key.return_value = "banto_secret_value"

        with (
            patch("web_app_factory._keychain._BANTO_AVAILABLE", True),
            patch("web_app_factory._keychain.SecureVault", return_value=mock_vault),
            patch("keyring.get_password") as mock_keyring,
        ):
            from web_app_factory._keychain import get_credential

            result = get_credential("supabase_access_token")

        assert result == "banto_secret_value"
        mock_keyring.assert_not_called()

    def test_banto_key_not_found_falls_back_to_keyring(self, monkeypatch):
        """When banto raises KeyNotFoundError, falls back to keyring."""
        # Use a generic exception to simulate KeyNotFoundError; the module
        # treats all banto exceptions as fallback triggers.
        mock_vault = MagicMock()
        mock_vault.get_key.side_effect = LookupError("not found")

        with (
            patch("web_app_factory._keychain._BANTO_AVAILABLE", True),
            patch("web_app_factory._keychain.SecureVault", return_value=mock_vault),
            patch("keyring.get_password", return_value="keyring_value"),
        ):
            from web_app_factory._keychain import get_credential

            result = get_credential("supabase_access_token")

        assert result == "keyring_value"

    def test_banto_exception_falls_back_to_env_var(self, monkeypatch):
        """When banto raises generic exception, falls back to env var."""
        mock_vault = MagicMock()
        mock_vault.get_key.side_effect = RuntimeError("banto unavailable")

        monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "env_supabase_value")

        with (
            patch("web_app_factory._keychain._BANTO_AVAILABLE", True),
            patch("web_app_factory._keychain.SecureVault", return_value=mock_vault),
            patch("web_app_factory._keychain._KEYRING_AVAILABLE", False),
        ):
            from web_app_factory._keychain import get_credential

            result = get_credential("supabase_access_token")

        assert result == "env_supabase_value"

    def test_banto_unavailable_skips_to_keyring(self, monkeypatch):
        """When _BANTO_AVAILABLE is False, banto is never called; keyring is consulted."""
        monkeypatch.delenv("VERCEL_TOKEN", raising=False)

        with (
            patch("web_app_factory._keychain._BANTO_AVAILABLE", False),
            patch("keyring.get_password", return_value="keyring_only_value"),
        ):
            from web_app_factory._keychain import get_credential

            result = get_credential("vercel_token")

        assert result == "keyring_only_value"

    def test_vercel_token_backward_compat(self):
        """get_credential('vercel_token') still works with banto provider name 'vercel'."""
        mock_vault = MagicMock()
        mock_vault.get_key.return_value = "banto_vercel_token"

        with (
            patch("web_app_factory._keychain._BANTO_AVAILABLE", True),
            patch("web_app_factory._keychain.SecureVault", return_value=mock_vault),
        ):
            from web_app_factory._keychain import get_credential

            result = get_credential("vercel_token")

        assert result == "banto_vercel_token"
        # Verify the correct banto provider name was used
        mock_vault.get_key.assert_called_once_with(provider="vercel")

    def test_banto_provider_map_contents(self):
        """_BANTO_PROVIDER_MAP maps all 6 expected credential keys to correct banto provider names."""
        from web_app_factory._keychain import _BANTO_PROVIDER_MAP

        assert _BANTO_PROVIDER_MAP["supabase_access_token"] == "supabase-access-token"
        assert _BANTO_PROVIDER_MAP["supabase_org_id"] == "supabase-org-id"
        assert _BANTO_PROVIDER_MAP["anthropic_api_key"] == "anthropic"
        assert _BANTO_PROVIDER_MAP["vercel_token"] == "vercel"
        assert _BANTO_PROVIDER_MAP["vercel_org_id"] == "vercel-org-id"
        assert _BANTO_PROVIDER_MAP["vercel_project_id"] == "vercel-project-id"

    def test_supabase_env_fallbacks_present(self, monkeypatch):
        """_ENV_FALLBACKS includes supabase_access_token and supabase_org_id."""
        from web_app_factory._keychain import _ENV_FALLBACKS

        assert "supabase_access_token" in _ENV_FALLBACKS
        assert _ENV_FALLBACKS["supabase_access_token"] == "SUPABASE_ACCESS_TOKEN"
        assert "supabase_org_id" in _ENV_FALLBACKS
        assert _ENV_FALLBACKS["supabase_org_id"] == "SUPABASE_ORG_ID"

    def test_no_credential_in_logs_banto_path(self, caplog):
        """Credential values from banto never appear in logs."""
        secret_value = "ultra_secret_banto_value_xyz"
        mock_vault = MagicMock()
        mock_vault.get_key.return_value = secret_value

        with (
            patch("web_app_factory._keychain._BANTO_AVAILABLE", True),
            patch("web_app_factory._keychain.SecureVault", return_value=mock_vault),
        ):
            from web_app_factory._keychain import get_credential

            with caplog.at_level(logging.DEBUG, logger="web_app_factory._keychain"):
                result = get_credential("supabase_access_token")

        assert result == secret_value
        for record in caplog.records:
            assert secret_value not in record.getMessage(), (
                f"Credential value found in log at level {record.levelname}: "
                f"{record.getMessage()!r}"
            )
