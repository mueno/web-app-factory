"""Unit tests for tools/deploy_providers module.

Covers:
- DeployProvider ABC (cannot be instantiated directly)
- DeployResult frozen dataclass
- Provider registry (get_provider factory)
- AWSProvider stub (NotImplementedError with v3.0 guidance)
- LocalOnlyProvider (npm run build + localhost URL + no-HTTP verify)

Requirements: DEPL-01, DEPL-04, DEPL-05
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# ABC + DeployResult
# ---------------------------------------------------------------------------


def test_abc_cannot_instantiate():
    """DeployProvider is abstract and cannot be instantiated directly."""
    from tools.deploy_providers.base import DeployProvider

    with pytest.raises(TypeError):
        DeployProvider()  # type: ignore[abstract]


def test_deploy_result_fields():
    """DeployResult is a frozen dataclass with required fields."""
    from tools.deploy_providers.base import DeployResult

    result = DeployResult(success=True, url="https://x.com", provider="test")
    assert result.success is True
    assert result.url == "https://x.com"
    assert result.provider == "test"
    assert isinstance(result.metadata, dict)


def test_deploy_result_frozen():
    """DeployResult raises FrozenInstanceError on attribute assignment."""
    from tools.deploy_providers.base import DeployResult

    result = DeployResult(success=True, url="https://x.com", provider="test")
    with pytest.raises(FrozenInstanceError):
        result.success = False  # type: ignore[misc]


def test_deploy_result_metadata_default():
    """DeployResult metadata defaults to empty dict."""
    from tools.deploy_providers.base import DeployResult

    result = DeployResult(success=False, url=None, provider="aws")
    assert result.metadata == {}


def test_deploy_result_with_metadata():
    """DeployResult accepts metadata dict."""
    from tools.deploy_providers.base import DeployResult

    meta = {"service_name": "my-app", "region": "us-central1"}
    result = DeployResult(success=True, url="https://x.run.app", provider="gcp", metadata=meta)
    assert result.metadata["service_name"] == "my-app"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_aws():
    """get_provider('aws') returns an AWSProvider instance."""
    from tools.deploy_providers.registry import get_provider
    from tools.deploy_providers.aws_provider import AWSProvider

    provider = get_provider("aws")
    assert isinstance(provider, AWSProvider)


def test_registry_local():
    """get_provider('local') returns a LocalOnlyProvider instance."""
    from tools.deploy_providers.registry import get_provider
    from tools.deploy_providers.local_provider import LocalOnlyProvider

    provider = get_provider("local")
    assert isinstance(provider, LocalOnlyProvider)


def test_registry_unknown():
    """get_provider with unknown target raises ValueError listing valid targets."""
    from tools.deploy_providers.registry import get_provider

    with pytest.raises(ValueError) as exc_info:
        get_provider("banana")

    error_msg = str(exc_info.value)
    assert "banana" in error_msg
    # Should list valid targets
    assert "aws" in error_msg
    assert "local" in error_msg


def test_registry_valid_targets_constant():
    """VALID_DEPLOY_TARGETS is a frozenset of expected targets."""
    from tools.deploy_providers.registry import VALID_DEPLOY_TARGETS

    assert isinstance(VALID_DEPLOY_TARGETS, frozenset)
    assert "aws" in VALID_DEPLOY_TARGETS
    assert "local" in VALID_DEPLOY_TARGETS
    assert "vercel" in VALID_DEPLOY_TARGETS
    assert "gcp" in VALID_DEPLOY_TARGETS


@pytest.mark.xfail(reason="VercelProvider not yet implemented — see Plan 09-02")
def test_registry_vercel():
    """get_provider('vercel') returns a VercelProvider instance."""
    from tools.deploy_providers.registry import get_provider
    from tools.deploy_providers.vercel_provider import VercelProvider

    provider = get_provider("vercel")
    assert isinstance(provider, VercelProvider)
    # VercelProvider must have all three base methods
    assert hasattr(provider, "deploy")
    assert hasattr(provider, "get_url")
    assert hasattr(provider, "verify")


@pytest.mark.xfail(reason="GCPProvider not yet implemented — see Plan 09-03")
def test_registry_gcp():
    """get_provider('gcp') returns a GCPProvider instance."""
    from tools.deploy_providers.registry import get_provider
    from tools.deploy_providers.gcp_provider import GCPProvider

    provider = get_provider("gcp")
    assert isinstance(provider, GCPProvider)
    assert hasattr(provider, "deploy")
    assert hasattr(provider, "get_url")
    assert hasattr(provider, "verify")


# ---------------------------------------------------------------------------
# AWSProvider
# ---------------------------------------------------------------------------


class TestAWSProvider:
    """AWSProvider is a stub that raises NotImplementedError with v3.0 guidance."""

    def test_deploy_raises(self):
        """AWSProvider.deploy() raises NotImplementedError containing 'v3.0'."""
        from tools.deploy_providers.aws_provider import AWSProvider

        provider = AWSProvider()
        with pytest.raises(NotImplementedError) as exc_info:
            provider.deploy(Path("/tmp/test"), {})

        assert "v3.0" in str(exc_info.value)

    def test_get_url_raises(self):
        """AWSProvider.get_url() raises NotImplementedError."""
        from tools.deploy_providers.aws_provider import AWSProvider
        from tools.deploy_providers.base import DeployResult

        provider = AWSProvider()
        result = DeployResult(success=False, url=None, provider="aws")
        with pytest.raises(NotImplementedError):
            provider.get_url(result)

    def test_verify_raises(self):
        """AWSProvider.verify() raises NotImplementedError."""
        from tools.deploy_providers.aws_provider import AWSProvider

        provider = AWSProvider()
        with pytest.raises(NotImplementedError):
            provider.verify("http://x")

    def test_guidance_message_content(self):
        """AWSProvider NotImplementedError message references CDK and v3.0 timeline."""
        from tools.deploy_providers.aws_provider import AWSProvider

        provider = AWSProvider()
        try:
            provider.deploy(Path("/tmp"), {})
        except NotImplementedError as exc:
            msg = str(exc)
            assert "v3.0" in msg
            assert "CDK" in msg or "cdk" in msg or "aws.amazon.com" in msg


# ---------------------------------------------------------------------------
# LocalOnlyProvider
# ---------------------------------------------------------------------------


class TestLocalOnlyProvider:
    """LocalOnlyProvider runs npm run build and returns localhost URL."""

    def test_deploy_success(self, tmp_path):
        """LocalOnlyProvider.deploy() calls subprocess with npm run build and returns localhost:3000."""
        from tools.deploy_providers.local_provider import LocalOnlyProvider

        # Create a fake package.json
        (tmp_path / "package.json").write_text('{"name": "test"}')

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            provider = LocalOnlyProvider()
            result = provider.deploy(tmp_path, {"nextjs_dir": str(tmp_path)})

        # Verify subprocess was called with npm run build (list args, no shell=True)
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd == ["npm", "run", "build"]
        # Must NOT use shell=True
        assert call_args.kwargs.get("shell") is not True

        assert result.success is True
        assert result.url == "http://localhost:3000"
        assert result.provider == "local"

    def test_deploy_missing_package_json(self, tmp_path):
        """LocalOnlyProvider.deploy() returns success=False when package.json not found."""
        from tools.deploy_providers.local_provider import LocalOnlyProvider

        # tmp_path has no package.json
        provider = LocalOnlyProvider()
        result = provider.deploy(tmp_path, {"nextjs_dir": str(tmp_path)})

        assert result.success is False
        assert result.url is None
        assert result.provider == "local"
        assert "package.json" in result.metadata.get("error", "")

    def test_deploy_build_failure(self, tmp_path):
        """LocalOnlyProvider.deploy() returns success=False when npm run build fails."""
        from tools.deploy_providers.local_provider import LocalOnlyProvider

        (tmp_path / "package.json").write_text('{"name": "test"}')

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: missing script build"

        with patch("subprocess.run", return_value=mock_result):
            provider = LocalOnlyProvider()
            result = provider.deploy(tmp_path, {"nextjs_dir": str(tmp_path)})

        assert result.success is False
        assert result.url is None
        assert result.provider == "local"

    def test_deploy_uses_project_dir_fallback(self, tmp_path):
        """LocalOnlyProvider.deploy() falls back to project_dir when nextjs_dir not in env."""
        from tools.deploy_providers.local_provider import LocalOnlyProvider

        (tmp_path / "package.json").write_text('{"name": "test"}')

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            provider = LocalOnlyProvider()
            # Pass empty env dict — should fall back to project_dir
            result = provider.deploy(tmp_path, {})

        assert result.success is True
        # Verify cwd was set to project_dir (or its string form)
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs.get("cwd") == str(tmp_path)

    def test_verify_skips_http(self):
        """LocalOnlyProvider.verify() returns True without making HTTP calls."""
        from tools.deploy_providers.local_provider import LocalOnlyProvider

        with patch("httpx.get") as mock_get, patch("httpx.Client") as mock_client:
            provider = LocalOnlyProvider()
            result = provider.verify("http://localhost:3000")

        # No HTTP call should have been made
        mock_get.assert_not_called()
        mock_client.assert_not_called()
        assert result is True

    def test_get_url_success(self):
        """LocalOnlyProvider.get_url() returns URL from successful DeployResult."""
        from tools.deploy_providers.local_provider import LocalOnlyProvider
        from tools.deploy_providers.base import DeployResult

        provider = LocalOnlyProvider()
        result = DeployResult(success=True, url="http://localhost:3000", provider="local")
        assert provider.get_url(result) == "http://localhost:3000"

    def test_get_url_no_url_raises(self):
        """LocalOnlyProvider.get_url() raises ValueError when url is None."""
        from tools.deploy_providers.local_provider import LocalOnlyProvider
        from tools.deploy_providers.base import DeployResult

        provider = LocalOnlyProvider()
        result = DeployResult(success=False, url=None, provider="local")
        with pytest.raises(ValueError):
            provider.get_url(result)

    def test_deploy_timeout(self, tmp_path):
        """LocalOnlyProvider.deploy() returns success=False on subprocess timeout."""
        import subprocess
        from tools.deploy_providers.local_provider import LocalOnlyProvider

        (tmp_path / "package.json").write_text('{"name": "test"}')

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["npm"], 300)):
            provider = LocalOnlyProvider()
            result = provider.deploy(tmp_path, {"nextjs_dir": str(tmp_path)})

        assert result.success is False
        assert "timed out" in result.metadata.get("error", "").lower()


# ---------------------------------------------------------------------------
# __init__.py re-exports
# ---------------------------------------------------------------------------


def test_init_exports_deploy_provider():
    """tools.deploy_providers re-exports DeployProvider."""
    from tools.deploy_providers import DeployProvider

    assert DeployProvider is not None


def test_init_exports_deploy_result():
    """tools.deploy_providers re-exports DeployResult."""
    from tools.deploy_providers import DeployResult

    assert DeployResult is not None


def test_init_exports_get_provider():
    """tools.deploy_providers re-exports get_provider."""
    from tools.deploy_providers import get_provider

    assert callable(get_provider)
