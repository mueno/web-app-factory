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
# VercelProvider
# ---------------------------------------------------------------------------


class TestVercelProvider:
    """VercelProvider implements deploy/get_url/verify using Vercel CLI subprocess logic."""

    def test_deploy_success(self, tmp_path):
        """deploy() calls provision, deploy_preview, and promote in sequence; returns DeployResult."""
        from tools.deploy_providers.vercel_provider import VercelProvider

        preview_url = "https://myapp-abc123.vercel.app"
        (tmp_path / "docs" / "pipeline").mkdir(parents=True, exist_ok=True)

        mock_success = MagicMock()
        mock_success.returncode = 0
        mock_success.stdout = f"Deployed to {preview_url}"
        mock_success.stderr = ""

        with patch("subprocess.run", return_value=mock_success) as mock_run:
            provider = VercelProvider()
            result = provider.deploy(tmp_path, {"nextjs_dir": str(tmp_path)})

        # All 3 subprocess.run calls: provision, deploy_preview, promote
        assert mock_run.call_count == 3
        assert result.success is True
        assert result.url == preview_url
        assert result.provider == "vercel"

    def test_provision_failure(self, tmp_path):
        """When vercel link returns non-zero, deploy() returns DeployResult(success=False)."""
        from tools.deploy_providers.vercel_provider import VercelProvider

        mock_failure = MagicMock()
        mock_failure.returncode = 1
        mock_failure.stdout = ""
        mock_failure.stderr = "Not authenticated to Vercel CLI"

        with patch("subprocess.run", return_value=mock_failure):
            provider = VercelProvider()
            result = provider.deploy(tmp_path, {"nextjs_dir": str(tmp_path)})

        assert result.success is False
        assert result.url is None
        assert result.provider == "vercel"
        assert "provision" in result.metadata.get("step", "")

    def test_preview_url_extraction(self, tmp_path):
        """deploy() captures Vercel preview URL from multi-line stdout via regex."""
        from tools.deploy_providers.vercel_provider import VercelProvider

        preview_url = "https://test-app-xyz789.vercel.app"
        stdout_with_noise = (
            "Installing dependencies...\n"
            "Building...\n"
            f"Deployment URL: {preview_url}\n"
            "Done!\n"
        )

        mock_provision = MagicMock()
        mock_provision.returncode = 0
        mock_provision.stdout = ""
        mock_provision.stderr = ""

        mock_deploy = MagicMock()
        mock_deploy.returncode = 0
        mock_deploy.stdout = stdout_with_noise
        mock_deploy.stderr = ""

        mock_promote = MagicMock()
        mock_promote.returncode = 0
        mock_promote.stdout = ""
        mock_promote.stderr = ""

        with patch("subprocess.run", side_effect=[mock_provision, mock_deploy, mock_promote]):
            provider = VercelProvider()
            result = provider.deploy(tmp_path, {"nextjs_dir": str(tmp_path)})

        assert result.success is True
        assert result.url == preview_url

    def test_verify_delegates_to_gate(self):
        """verify() delegates to run_deployment_gate and returns gate_result.passed."""
        from tools.deploy_providers.vercel_provider import VercelProvider
        from tools.gates.gate_result import GateResult
        from datetime import datetime, timezone

        passing_gate = GateResult(
            gate_type="deployment",
            phase_id="3",
            passed=True,
            status="PASS",
            severity="INFO",
            confidence=1.0,
            checked_at=datetime.now(timezone.utc).isoformat(),
            issues=[],
        )

        with patch(
            "tools.deploy_providers.vercel_provider.run_deployment_gate",
            return_value=passing_gate,
        ) as mock_gate:
            provider = VercelProvider()
            result = provider.verify("https://test.vercel.app")

        mock_gate.assert_called_once_with("https://test.vercel.app")
        assert result is True

    def test_get_url_returns_url(self):
        """get_url() returns url from a successful DeployResult."""
        from tools.deploy_providers.vercel_provider import VercelProvider
        from tools.deploy_providers.base import DeployResult

        provider = VercelProvider()
        deploy_result = DeployResult(
            success=True,
            url="https://myapp.vercel.app",
            provider="vercel",
        )
        assert provider.get_url(deploy_result) == "https://myapp.vercel.app"

    def test_get_url_raises_when_no_url(self):
        """get_url() raises ValueError when url is None (deploy failed)."""
        from tools.deploy_providers.vercel_provider import VercelProvider
        from tools.deploy_providers.base import DeployResult

        provider = VercelProvider()
        deploy_result = DeployResult(
            success=False,
            url=None,
            provider="vercel",
        )
        with pytest.raises(ValueError):
            provider.get_url(deploy_result)

    def test_deployment_json_written_on_success(self, tmp_path):
        """deploy() writes deployment.json with preview_url and platform='vercel'."""
        from tools.deploy_providers.vercel_provider import VercelProvider
        import json

        preview_url = "https://myapp-dep.vercel.app"

        mock_success = MagicMock()
        mock_success.returncode = 0
        mock_success.stdout = f"Preview: {preview_url}"
        mock_success.stderr = ""

        with patch("subprocess.run", return_value=mock_success):
            provider = VercelProvider()
            provider.deploy(tmp_path, {"nextjs_dir": str(tmp_path)})

        deployment_json_path = tmp_path / "docs" / "pipeline" / "deployment.json"
        assert deployment_json_path.exists()
        data = json.loads(deployment_json_path.read_text())
        assert data["preview_url"] == preview_url
        assert data["platform"] == "vercel"
        assert "deployed_at" in data

    def test_verify_returns_false_on_gate_failure(self):
        """verify() returns False when run_deployment_gate fails."""
        from tools.deploy_providers.vercel_provider import VercelProvider
        from tools.gates.gate_result import GateResult
        from datetime import datetime, timezone

        failing_gate = GateResult(
            gate_type="deployment",
            phase_id="3",
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=datetime.now(timezone.utc).isoformat(),
            issues=["HTTP 503 from URL"],
        )

        with patch(
            "tools.deploy_providers.vercel_provider.run_deployment_gate",
            return_value=failing_gate,
        ):
            provider = VercelProvider()
            result = provider.verify("https://test.vercel.app")

        assert result is False


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


# ---------------------------------------------------------------------------
# GCPProvider
# ---------------------------------------------------------------------------


class TestGCPProvider:
    """GCPProvider: auth preflight + Cloud Run deploy + URL extraction."""

    # ------------------------------------------------------------------
    # Preflight checks
    # ------------------------------------------------------------------

    def test_gcp_preflight_no_gcloud(self):
        """When gcloud --version raises FileNotFoundError, deploy() returns failure with 'gcloud CLI not found'."""
        from tools.deploy_providers.gcp_provider import GCPProvider

        with patch("subprocess.run", side_effect=FileNotFoundError):
            provider = GCPProvider()
            result = provider.deploy(Path("/tmp/test"), {})

        assert result.success is False
        assert result.provider == "gcp"
        assert "gcloud CLI not found" in result.metadata.get("error", "")

    def test_gcp_preflight_auth_failure(self):
        """When gcloud auth print-access-token exits non-zero, deploy() returns failure with 'gcloud auth login'."""
        import subprocess
        from tools.deploy_providers.gcp_provider import GCPProvider

        gcloud_version_ok = MagicMock(returncode=0, stdout="Google Cloud SDK 456.0.0")
        auth_fail = MagicMock(returncode=1, stdout="", stderr="ERROR: (gcloud) no access token")

        def mock_run(cmd, **kwargs):
            if "--version" in cmd:
                return gcloud_version_ok
            if "print-access-token" in cmd:
                return auth_fail
            return MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", side_effect=mock_run):
            provider = GCPProvider()
            result = provider.deploy(Path("/tmp/test"), {})

        assert result.success is False
        assert "gcloud auth login" in result.metadata.get("error", "")

    def test_gcp_preflight_no_project(self):
        """When gcloud config get-value project returns '(unset)', deploy() returns failure with 'gcloud config set project'."""
        from tools.deploy_providers.gcp_provider import GCPProvider

        gcloud_version_ok = MagicMock(returncode=0, stdout="Google Cloud SDK 456.0.0")
        auth_ok = MagicMock(returncode=0, stdout="ya29.token")
        no_project = MagicMock(returncode=0, stdout="(unset)")

        def mock_run(cmd, **kwargs):
            if "--version" in cmd:
                return gcloud_version_ok
            if "print-access-token" in cmd:
                return auth_ok
            if "get-value" in cmd and "project" in cmd:
                return no_project
            return MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", side_effect=mock_run):
            provider = GCPProvider()
            result = provider.deploy(Path("/tmp/test"), {})

        assert result.success is False
        assert "gcloud config set project" in result.metadata.get("error", "")

    # ------------------------------------------------------------------
    # Deploy success
    # ------------------------------------------------------------------

    def test_gcp_deploy_success(self):
        """When all checks pass and stderr contains Service URL, deploy() returns success."""
        from tools.deploy_providers.gcp_provider import GCPProvider

        auth_ok = MagicMock(returncode=0, stdout="ya29.token")
        project_ok = MagicMock(returncode=0, stdout="my-project-123")
        region_ok = MagicMock(returncode=0, stdout="us-central1")
        deploy_ok = MagicMock(
            returncode=0,
            stdout="",
            stderr="Service URL: https://my-app-abc123-uc.a.run.app",
        )

        def mock_run(cmd, **kwargs):
            if "--version" in cmd:
                return MagicMock(returncode=0, stdout="Google Cloud SDK 456.0.0")
            if "print-access-token" in cmd:
                return auth_ok
            if "get-value" in cmd and "project" in cmd:
                return project_ok
            if "get-value" in cmd and "run/region" in " ".join(cmd):
                return region_ok
            if "run" in cmd and "deploy" in cmd:
                return deploy_ok
            return MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", side_effect=mock_run):
            provider = GCPProvider()
            result = provider.deploy(Path("/tmp/test"), {"app_name": "my-app", "nextjs_dir": "/tmp/test"})

        assert result.success is True
        assert result.url == "https://my-app-abc123-uc.a.run.app"
        assert result.provider == "gcp"

    # ------------------------------------------------------------------
    # Error conditions
    # ------------------------------------------------------------------

    def test_gcp_deploy_timeout(self):
        """When gcloud run deploy raises TimeoutExpired, deploy() returns failure with timeout error."""
        import subprocess
        from tools.deploy_providers.gcp_provider import GCPProvider

        def mock_run(cmd, **kwargs):
            if "--version" in cmd:
                return MagicMock(returncode=0, stdout="Google Cloud SDK 456.0.0")
            if "print-access-token" in cmd:
                return MagicMock(returncode=0, stdout="ya29.token")
            if "get-value" in cmd and "project" in cmd:
                return MagicMock(returncode=0, stdout="my-project-123")
            if "get-value" in cmd and "run/region" in " ".join(cmd):
                return MagicMock(returncode=0, stdout="us-central1")
            if "deploy" in cmd:
                raise subprocess.TimeoutExpired(cmd, 600)
            return MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", side_effect=mock_run):
            provider = GCPProvider()
            result = provider.deploy(Path("/tmp/test"), {"nextjs_dir": "/tmp/test"})

        assert result.success is False
        assert "timed out" in result.metadata.get("error", "").lower() or "timeout" in result.metadata.get("error", "").lower()

    def test_gcp_deploy_no_url_in_output(self):
        """When gcloud succeeds but stderr has no Service URL pattern, deploy() returns failure."""
        from tools.deploy_providers.gcp_provider import GCPProvider

        def mock_run(cmd, **kwargs):
            if "--version" in cmd:
                return MagicMock(returncode=0, stdout="Google Cloud SDK 456.0.0")
            if "print-access-token" in cmd:
                return MagicMock(returncode=0, stdout="ya29.token")
            if "get-value" in cmd and "project" in cmd:
                return MagicMock(returncode=0, stdout="my-project-123")
            if "get-value" in cmd and "run/region" in " ".join(cmd):
                return MagicMock(returncode=0, stdout="us-central1")
            if "deploy" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="Deploying service... done")
            return MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", side_effect=mock_run):
            provider = GCPProvider()
            result = provider.deploy(Path("/tmp/test"), {"nextjs_dir": "/tmp/test"})

        assert result.success is False
        assert result.url is None

    # ------------------------------------------------------------------
    # URL extraction
    # ------------------------------------------------------------------

    def test_gcp_url_extraction_regex(self):
        """_GCP_URL_RE matches 'Service URL: https://...' in various stderr formats."""
        from tools.deploy_providers.gcp_provider import _GCP_URL_RE

        # Standard format
        m = _GCP_URL_RE.search("Service URL: https://my-service-abc123-uc.a.run.app")
        assert m is not None
        assert m.group(1) == "https://my-service-abc123-uc.a.run.app"

        # With surrounding text
        m2 = _GCP_URL_RE.search(
            "Deploying container to Cloud Run service [my-service] ...\n"
            "Service URL: https://my-service-xyz-ew.a.run.app\n"
            "Done."
        )
        assert m2 is not None
        assert m2.group(1) == "https://my-service-xyz-ew.a.run.app"

        # No match
        m3 = _GCP_URL_RE.search("Deploying... done.")
        assert m3 is None

    # ------------------------------------------------------------------
    # verify() delegation
    # ------------------------------------------------------------------

    def test_gcp_verify_delegates(self):
        """GCPProvider.verify() calls run_deployment_gate() and returns .passed."""
        from tools.deploy_providers.gcp_provider import GCPProvider
        from tools.gates.gate_result import GateResult
        from datetime import datetime, timezone

        fake_gate_result = GateResult(
            gate_type="deployment",
            phase_id="3",
            passed=True,
            status="PASS",
            severity="INFO",
            confidence=1.0,
            checked_at=datetime.now(timezone.utc).isoformat(),
            issues=[],
        )

        with patch(
            "tools.deploy_providers.gcp_provider.run_deployment_gate",
            return_value=fake_gate_result,
        ) as mock_gate:
            provider = GCPProvider()
            result = provider.verify("https://my-service-abc123-uc.a.run.app")

        mock_gate.assert_called_once_with("https://my-service-abc123-uc.a.run.app")
        assert result is True

    # ------------------------------------------------------------------
    # Region default
    # ------------------------------------------------------------------

    def test_gcp_region_default(self):
        """When gcloud config get-value run/region returns empty, deploy cmd includes --region us-central1."""
        from tools.deploy_providers.gcp_provider import GCPProvider

        captured_cmds: list = []

        def mock_run(cmd, **kwargs):
            captured_cmds.append(cmd)
            if "--version" in cmd:
                return MagicMock(returncode=0, stdout="Google Cloud SDK 456.0.0")
            if "print-access-token" in cmd:
                return MagicMock(returncode=0, stdout="ya29.token")
            if "get-value" in cmd and "project" in cmd and "run/region" not in " ".join(cmd):
                return MagicMock(returncode=0, stdout="my-project-123")
            if "get-value" in cmd and "run/region" in " ".join(cmd):
                # Empty region → default to us-central1
                return MagicMock(returncode=0, stdout="")
            if "deploy" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="Service URL: https://my-app-abc123-uc.a.run.app")
            return MagicMock(returncode=0, stdout="")

        with patch("subprocess.run", side_effect=mock_run):
            provider = GCPProvider()
            provider.deploy(Path("/tmp/test"), {"nextjs_dir": "/tmp/test"})

        # Find the deploy command
        deploy_cmd = next((c for c in captured_cmds if "deploy" in c), None)
        assert deploy_cmd is not None
        assert "--region" in deploy_cmd
        region_idx = deploy_cmd.index("--region")
        assert deploy_cmd[region_idx + 1] == "us-central1"
