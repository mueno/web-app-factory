"""Tests for Supabase integration in tools/phase_executors/phase_3_executor.py.

Verifies:
- When supabase_enabled=True, Phase3ShipExecutor calls SupabaseProvisioner flow
- Supabase sub-steps appear in PhaseResult.sub_steps
- When supabase_enabled=False or absent, all Supabase sub-steps are skipped
- When deploy_target="local", Supabase sub-steps are skipped
- Supabase provisioning failure returns PhaseResult(success=False)
- render_supabase_templates is called after successful provisioning
- supabase_gate is called with project_ref and credentials after provisioning
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out claude_agent_sdk so the phase_3_executor module can be imported
# in test environments where the SDK is not installed.
# ---------------------------------------------------------------------------

def _make_claude_agent_sdk_stub() -> ModuleType:
    """Create a minimal stub for claude_agent_sdk and its submodules."""
    stub = ModuleType("claude_agent_sdk")
    stub.query = MagicMock()  # type: ignore[attr-defined]

    class _ClaudeAgentOptions:  # noqa: D101
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    stub.ClaudeAgentOptions = _ClaudeAgentOptions  # type: ignore[attr-defined]

    types_stub = ModuleType("claude_agent_sdk.types")

    class _ResultMessage:  # noqa: D101
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    types_stub.ResultMessage = _ResultMessage  # type: ignore[attr-defined]
    sys.modules.setdefault("claude_agent_sdk", stub)
    sys.modules.setdefault("claude_agent_sdk.types", types_stub)
    return stub


_make_claude_agent_sdk_stub()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_passing_gate_result(gate_type: str = "test") -> object:
    """Create a GateResult-like object with passed=True."""
    from tools.gates.gate_result import GateResult
    from datetime import datetime, timezone

    return GateResult(
        gate_type=gate_type,
        phase_id="3",
        passed=True,
        status="PASS",
        severity="INFO",
        confidence=1.0,
        checked_at=datetime.now(timezone.utc).isoformat(),
        issues=[],
    )


def _make_failing_gate_result(gate_type: str = "test", issues: list | None = None) -> object:
    """Create a GateResult-like object with passed=False."""
    from tools.gates.gate_result import GateResult
    from datetime import datetime, timezone

    return GateResult(
        gate_type=gate_type,
        phase_id="3",
        passed=False,
        status="BLOCKED",
        severity="BLOCK",
        confidence=0.0,
        checked_at=datetime.now(timezone.utc).isoformat(),
        issues=issues or [f"{gate_type} gate failed"],
    )


def _make_context(tmp_path: Path, extra: dict | None = None) -> object:
    """Create a PhaseContext for testing."""
    from tools.phase_executors.base import PhaseContext

    return PhaseContext(
        run_id="test-run-123",
        phase_id="3",
        project_dir=tmp_path,
        idea="A weight tracking web app",
        app_name="WeightSnap",
        extra=extra or {},
    )


def _make_deploy_result(success: bool = True, url: str = "https://preview.example.com") -> object:
    """Create a DeployResult-like object."""
    mock = MagicMock()
    mock.success = success
    mock.url = url
    mock.metadata = {"step": "deploy_preview", "error": "deploy failed"} if not success else {}
    return mock


def _patch_full_pipeline(tmp_path: Path) -> list:
    """Return patch context managers for all non-Supabase Phase 3 gates."""
    passing_gate = _make_passing_gate_result("legal")
    return [
        patch(
            "tools.phase_executors.phase_3_executor.get_provider",
            return_value=_make_mock_provider(tmp_path),
        ),
        patch(
            "tools.phase_executors.phase_3_executor.run_legal_gate",
            return_value=_make_passing_gate_result("legal"),
        ),
        patch(
            "tools.phase_executors.phase_3_executor.run_lighthouse_gate",
            return_value=_make_passing_gate_result("lighthouse"),
        ),
        patch(
            "tools.phase_executors.phase_3_executor.run_accessibility_gate",
            return_value=_make_passing_gate_result("accessibility"),
        ),
        patch(
            "tools.phase_executors.phase_3_executor.run_security_headers_gate",
            return_value=_make_passing_gate_result("security_headers"),
        ),
        patch(
            "tools.phase_executors.phase_3_executor.run_link_integrity_gate",
            return_value=_make_passing_gate_result("link_integrity"),
        ),
        patch(
            "tools.phase_executors.phase_3_executor.run_mcp_approval_gate",
            return_value=_make_passing_gate_result("mcp_approval"),
        ),
        patch(
            "tools.phase_executors.phase_3_executor.run_deploy_agent",
            return_value="legal docs generated",
        ),
    ]


def _make_mock_provider(tmp_path: Path) -> MagicMock:
    """Create a mock DeployProvider that succeeds."""
    provider = MagicMock()
    deploy_result = _make_deploy_result(success=True, url="https://preview.vercel.app")
    provider.deploy.return_value = deploy_result
    provider.get_url.return_value = "https://preview.vercel.app"
    return provider


def _make_mock_provisioner() -> MagicMock:
    """Create a mock SupabaseProvisioner with successful async methods."""
    provisioner = MagicMock()
    provisioner.create_project = AsyncMock(
        return_value={"id": "proj-123", "ref": "abcxyz", "_db_pass": "secret"}
    )
    provisioner.poll_until_healthy = AsyncMock(return_value=None)
    provisioner.get_api_keys = AsyncMock(
        return_value={"anon": "anon-key-value", "service_role": "service-role-value"}
    )
    provisioner.inject_vercel_env = AsyncMock(return_value=None)
    return provisioner


# ---------------------------------------------------------------------------
# sub_steps includes Supabase entries
# ---------------------------------------------------------------------------


class TestSupabaseSubStepsProperty:
    """Test that sub_steps includes Supabase entries."""

    def test_sub_steps_include_supabase_provision(self) -> None:
        """sub_steps includes 'supabase_provision'."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        assert "supabase_provision" in executor.sub_steps

    def test_sub_steps_include_supabase_render(self) -> None:
        """sub_steps includes 'supabase_render'."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        assert "supabase_render" in executor.sub_steps

    def test_sub_steps_include_supabase_gate(self) -> None:
        """sub_steps includes 'supabase_gate'."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        assert "supabase_gate" in executor.sub_steps

    def test_supabase_steps_ordered_after_deploy_preview(self) -> None:
        """Supabase sub-steps appear after 'deploy_preview' in sub_steps list."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        steps = executor.sub_steps
        deploy_preview_idx = steps.index("deploy_preview")
        supabase_provision_idx = steps.index("supabase_provision")
        assert supabase_provision_idx > deploy_preview_idx


# ---------------------------------------------------------------------------
# Supabase-enabled: full flow
# ---------------------------------------------------------------------------


class TestSupabaseEnabledFlow:
    """Tests for supabase_enabled=True with vercel deploy target."""

    def test_supabase_provisioner_called_when_enabled(self, tmp_path: Path) -> None:
        """SupabaseProvisioner.create_project is called when supabase_enabled=True."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        ctx = _make_context(
            tmp_path,
            extra={
                "deploy_target": "vercel",
                "supabase_enabled": True,
                "nextjs_dir": str(tmp_path),
            },
        )

        mock_provisioner = _make_mock_provisioner()

        with (
            patch(
                "tools.phase_executors.phase_3_executor.get_provider",
                return_value=_make_mock_provider(tmp_path),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_legal_gate",
                return_value=_make_passing_gate_result("legal"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_lighthouse_gate",
                return_value=_make_passing_gate_result("lighthouse"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_accessibility_gate",
                return_value=_make_passing_gate_result("accessibility"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_security_headers_gate",
                return_value=_make_passing_gate_result("security_headers"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_link_integrity_gate",
                return_value=_make_passing_gate_result("link_integrity"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_mcp_approval_gate",
                return_value=_make_passing_gate_result("mcp_approval"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_deploy_agent",
                return_value="legal docs generated",
            ),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
            patch(
                "web_app_factory._supabase_template_renderer.render_supabase_templates",
                return_value=["/mock/browser.ts", "/mock/server.ts"],
            ),
            patch(
                "web_app_factory._supabase_template_renderer.add_supabase_deps",
                return_value=None,
            ),
            patch(
                "tools.gates.supabase_gate.run_supabase_gate",
                return_value=_make_passing_gate_result("supabase"),
            ),
        ):
            result = executor.execute(ctx)

        # Provisioner should have been constructed and create_project called
        mock_provisioner.create_project.assert_called_once()

    def test_supabase_substeps_in_result(self, tmp_path: Path) -> None:
        """PhaseResult.sub_steps includes supabase_provision, supabase_render, supabase_gate."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        ctx = _make_context(
            tmp_path,
            extra={
                "deploy_target": "vercel",
                "supabase_enabled": True,
                "nextjs_dir": str(tmp_path),
            },
        )

        mock_provisioner = _make_mock_provisioner()

        with (
            patch(
                "tools.phase_executors.phase_3_executor.get_provider",
                return_value=_make_mock_provider(tmp_path),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_legal_gate",
                return_value=_make_passing_gate_result("legal"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_lighthouse_gate",
                return_value=_make_passing_gate_result("lighthouse"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_accessibility_gate",
                return_value=_make_passing_gate_result("accessibility"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_security_headers_gate",
                return_value=_make_passing_gate_result("security_headers"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_link_integrity_gate",
                return_value=_make_passing_gate_result("link_integrity"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_mcp_approval_gate",
                return_value=_make_passing_gate_result("mcp_approval"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_deploy_agent",
                return_value="legal docs generated",
            ),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
            patch(
                "web_app_factory._supabase_template_renderer.render_supabase_templates",
                return_value=["/mock/browser.ts", "/mock/server.ts"],
            ),
            patch(
                "web_app_factory._supabase_template_renderer.add_supabase_deps",
                return_value=None,
            ),
            patch(
                "tools.gates.supabase_gate.run_supabase_gate",
                return_value=_make_passing_gate_result("supabase"),
            ),
        ):
            result = executor.execute(ctx)

        sub_step_ids = [s.sub_step_id for s in result.sub_steps]
        assert "supabase_provision" in sub_step_ids
        assert "supabase_render" in sub_step_ids
        assert "supabase_gate" in sub_step_ids

    def test_render_templates_called_after_provisioning(self, tmp_path: Path) -> None:
        """render_supabase_templates is called after successful provisioning."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        ctx = _make_context(
            tmp_path,
            extra={
                "deploy_target": "vercel",
                "supabase_enabled": True,
                "nextjs_dir": str(tmp_path),
            },
        )

        mock_provisioner = _make_mock_provisioner()
        mock_render = MagicMock(return_value=["/mock/browser.ts", "/mock/server.ts"])

        with (
            patch(
                "tools.phase_executors.phase_3_executor.get_provider",
                return_value=_make_mock_provider(tmp_path),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_legal_gate",
                return_value=_make_passing_gate_result("legal"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_lighthouse_gate",
                return_value=_make_passing_gate_result("lighthouse"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_accessibility_gate",
                return_value=_make_passing_gate_result("accessibility"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_security_headers_gate",
                return_value=_make_passing_gate_result("security_headers"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_link_integrity_gate",
                return_value=_make_passing_gate_result("link_integrity"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_mcp_approval_gate",
                return_value=_make_passing_gate_result("mcp_approval"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_deploy_agent",
                return_value="legal docs generated",
            ),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
            patch(
                "web_app_factory._supabase_template_renderer.render_supabase_templates",
                mock_render,
            ),
            patch(
                "web_app_factory._supabase_template_renderer.add_supabase_deps",
                return_value=None,
            ),
            patch(
                "tools.gates.supabase_gate.run_supabase_gate",
                return_value=_make_passing_gate_result("supabase"),
            ),
        ):
            result = executor.execute(ctx)

        mock_render.assert_called_once()

    def test_supabase_gate_called_with_project_ref(self, tmp_path: Path) -> None:
        """run_supabase_gate is called with project_ref from provisioner."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        ctx = _make_context(
            tmp_path,
            extra={
                "deploy_target": "vercel",
                "supabase_enabled": True,
                "nextjs_dir": str(tmp_path),
            },
        )

        mock_provisioner = _make_mock_provisioner()
        # create_project returns ref="abcxyz"
        mock_gate = MagicMock(return_value=_make_passing_gate_result("supabase"))

        with (
            patch(
                "tools.phase_executors.phase_3_executor.get_provider",
                return_value=_make_mock_provider(tmp_path),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_legal_gate",
                return_value=_make_passing_gate_result("legal"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_lighthouse_gate",
                return_value=_make_passing_gate_result("lighthouse"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_accessibility_gate",
                return_value=_make_passing_gate_result("accessibility"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_security_headers_gate",
                return_value=_make_passing_gate_result("security_headers"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_link_integrity_gate",
                return_value=_make_passing_gate_result("link_integrity"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_mcp_approval_gate",
                return_value=_make_passing_gate_result("mcp_approval"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_deploy_agent",
                return_value="legal docs generated",
            ),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
            patch(
                "web_app_factory._supabase_template_renderer.render_supabase_templates",
                return_value=["/mock/browser.ts", "/mock/server.ts"],
            ),
            patch(
                "web_app_factory._supabase_template_renderer.add_supabase_deps",
                return_value=None,
            ),
            patch(
                "tools.gates.supabase_gate.run_supabase_gate",
                mock_gate,
            ),
        ):
            result = executor.execute(ctx)

        # Gate should be called with project_ref="abcxyz"
        mock_gate.assert_called_once()
        call_kwargs = mock_gate.call_args[1]
        assert call_kwargs.get("project_ref") == "abcxyz"


# ---------------------------------------------------------------------------
# Backward compatibility: supabase_enabled=False
# ---------------------------------------------------------------------------


class TestSupabaseDisabledBackwardCompat:
    """Tests ensuring non-Supabase pipelines are completely unaffected."""

    def test_supabase_skipped_when_not_enabled(self, tmp_path: Path) -> None:
        """No Supabase sub-steps executed when supabase_enabled=False."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        ctx = _make_context(
            tmp_path,
            extra={
                "deploy_target": "vercel",
                "supabase_enabled": False,
                "nextjs_dir": str(tmp_path),
            },
        )

        mock_provisioner_cls = MagicMock()

        with (
            patch(
                "tools.phase_executors.phase_3_executor.get_provider",
                return_value=_make_mock_provider(tmp_path),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_legal_gate",
                return_value=_make_passing_gate_result("legal"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_lighthouse_gate",
                return_value=_make_passing_gate_result("lighthouse"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_accessibility_gate",
                return_value=_make_passing_gate_result("accessibility"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_security_headers_gate",
                return_value=_make_passing_gate_result("security_headers"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_link_integrity_gate",
                return_value=_make_passing_gate_result("link_integrity"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_mcp_approval_gate",
                return_value=_make_passing_gate_result("mcp_approval"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_deploy_agent",
                return_value="legal docs generated",
            ),
        ):
            result = executor.execute(ctx)

        # Supabase sub-steps must NOT be present
        sub_step_ids = [s.sub_step_id for s in result.sub_steps]
        assert "supabase_provision" not in sub_step_ids
        assert "supabase_render" not in sub_step_ids
        assert "supabase_gate" not in sub_step_ids

    def test_supabase_skipped_when_flag_absent(self, tmp_path: Path) -> None:
        """No Supabase sub-steps when supabase_enabled key is entirely absent from extra."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        ctx = _make_context(
            tmp_path,
            extra={
                "deploy_target": "vercel",
                # supabase_enabled is NOT set
                "nextjs_dir": str(tmp_path),
            },
        )

        with (
            patch(
                "tools.phase_executors.phase_3_executor.get_provider",
                return_value=_make_mock_provider(tmp_path),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_legal_gate",
                return_value=_make_passing_gate_result("legal"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_lighthouse_gate",
                return_value=_make_passing_gate_result("lighthouse"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_accessibility_gate",
                return_value=_make_passing_gate_result("accessibility"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_security_headers_gate",
                return_value=_make_passing_gate_result("security_headers"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_link_integrity_gate",
                return_value=_make_passing_gate_result("link_integrity"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_mcp_approval_gate",
                return_value=_make_passing_gate_result("mcp_approval"),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_deploy_agent",
                return_value="legal docs generated",
            ),
        ):
            result = executor.execute(ctx)

        sub_step_ids = [s.sub_step_id for s in result.sub_steps]
        assert "supabase_provision" not in sub_step_ids

    def test_supabase_skipped_for_local_deploy_target(self, tmp_path: Path) -> None:
        """No Supabase sub-steps when deploy_target='local' (even if supabase_enabled=True)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        ctx = _make_context(
            tmp_path,
            extra={
                "deploy_target": "local",
                "supabase_enabled": True,
                "nextjs_dir": str(tmp_path),
            },
        )

        with patch(
            "tools.phase_executors.phase_3_executor.get_provider",
            return_value=_make_mock_provider(tmp_path),
        ):
            result = executor.execute(ctx)

        # Local deploy exits early before Supabase steps
        sub_step_ids = [s.sub_step_id for s in result.sub_steps]
        assert "supabase_provision" not in sub_step_ids
        assert "supabase_render" not in sub_step_ids
        assert "supabase_gate" not in sub_step_ids
        assert result.success is True


# ---------------------------------------------------------------------------
# Failure cases
# ---------------------------------------------------------------------------


class TestSupabaseFailureCases:
    """Tests for Supabase sub-step failure behavior."""

    def test_missing_credentials_returns_failure(self, tmp_path: Path) -> None:
        """PhaseResult.success=False when Supabase credentials are missing."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        ctx = _make_context(
            tmp_path,
            extra={
                "deploy_target": "vercel",
                "supabase_enabled": True,
                "nextjs_dir": str(tmp_path),
            },
        )

        with (
            patch(
                "tools.phase_executors.phase_3_executor.get_provider",
                return_value=_make_mock_provider(tmp_path),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_deploy_agent",
                return_value="legal docs generated",
            ),
            # Credentials return None (missing)
            patch(
                "web_app_factory._keychain.get_credential",
                return_value=None,
            ),
        ):
            result = executor.execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "credential" in result.error.lower() or "supabase" in result.error.lower()

    def test_provisioner_exception_returns_failure(self, tmp_path: Path) -> None:
        """PhaseResult.success=False when SupabaseProvisioner.create_project raises."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        ctx = _make_context(
            tmp_path,
            extra={
                "deploy_target": "vercel",
                "supabase_enabled": True,
                "nextjs_dir": str(tmp_path),
            },
        )

        mock_provisioner = _make_mock_provisioner()
        mock_provisioner.create_project = AsyncMock(
            side_effect=RuntimeError("API error: quota exceeded")
        )

        with (
            patch(
                "tools.phase_executors.phase_3_executor.get_provider",
                return_value=_make_mock_provider(tmp_path),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_deploy_agent",
                return_value="legal docs generated",
            ),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
        ):
            result = executor.execute(ctx)

        assert result.success is False
        assert result.error is not None

    def test_supabase_gate_failure_returns_phase_failure(self, tmp_path: Path) -> None:
        """PhaseResult.success=False when supabase_gate fails."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor

        executor = Phase3ShipExecutor()
        ctx = _make_context(
            tmp_path,
            extra={
                "deploy_target": "vercel",
                "supabase_enabled": True,
                "nextjs_dir": str(tmp_path),
            },
        )

        mock_provisioner = _make_mock_provisioner()

        with (
            patch(
                "tools.phase_executors.phase_3_executor.get_provider",
                return_value=_make_mock_provider(tmp_path),
            ),
            patch(
                "tools.phase_executors.phase_3_executor.run_deploy_agent",
                return_value="legal docs generated",
            ),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
            patch(
                "web_app_factory._supabase_template_renderer.render_supabase_templates",
                return_value=["/mock/browser.ts", "/mock/server.ts"],
            ),
            patch(
                "web_app_factory._supabase_template_renderer.add_supabase_deps",
                return_value=None,
            ),
            patch(
                "tools.gates.supabase_gate.run_supabase_gate",
                return_value=_make_failing_gate_result(
                    "supabase", issues=["Missing RLS on table 'posts'"]
                ),
            ),
        ):
            result = executor.execute(ctx)

        assert result.success is False
        assert result.error is not None
