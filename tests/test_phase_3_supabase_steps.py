"""Tests for extracted Supabase sub-step functions in _phase_3_supabase_steps.py.

Verifies that the extracted standalone functions behave identically to the
original Phase3ShipExecutor methods they were extracted from.

Covers:
- supabase_provision: credentials check, provisioner called, ctx.extra updated
- supabase_provision: failure on missing credentials
- supabase_provision: failure on provisioner exception
- supabase_oauth_config: skips when no project_ref in ctx.extra
- supabase_oauth_config: skips when no OAuth env vars present
- supabase_oauth_config: calls configure_oauth_providers when creds present
- supabase_oauth_config: returns success=True with advisory on API failure
- supabase_oauth_config: never logs credential values
- supabase_render: calls render_supabase_templates and add_supabase_deps
- supabase_render: skips dep injection when package.json missing (warning)
- supabase_render: failure on renderer exception
- supabase_gate: calls run_supabase_gate with project_ref from ctx.extra
- supabase_gate: passes on gate success
- supabase_gate: fails on gate failure
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Stub claude_agent_sdk so the import chain resolves in test environments
# ---------------------------------------------------------------------------


def _make_claude_agent_sdk_stub() -> ModuleType:
    """Create a minimal stub for claude_agent_sdk."""
    stub = ModuleType("claude_agent_sdk")
    stub.query = MagicMock()  # type: ignore[attr-defined]

    class _ClaudeAgentOptions:
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    stub.ClaudeAgentOptions = _ClaudeAgentOptions  # type: ignore[attr-defined]

    types_stub = ModuleType("claude_agent_sdk.types")

    class _ResultMessage:
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


def _make_context(tmp_path: Path, extra: dict | None = None) -> object:
    """Create a PhaseContext for testing."""
    from tools.phase_executors.base import PhaseContext

    return PhaseContext(
        run_id="test-supa-steps-123",
        phase_id="3",
        project_dir=tmp_path,
        idea="A weight tracking web app",
        app_name="WeightSnap",
        extra=extra or {},
    )


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
    provisioner.configure_oauth_providers = AsyncMock(return_value=None)
    return provisioner


def _make_passing_gate_result() -> object:
    """Create a gate result with passed=True."""
    from tools.gates.gate_result import GateResult
    from datetime import datetime, timezone

    return GateResult(
        gate_type="supabase",
        phase_id="3",
        passed=True,
        status="PASS",
        severity="INFO",
        confidence=1.0,
        checked_at=datetime.now(timezone.utc).isoformat(),
        issues=[],
    )


def _make_failing_gate_result(issues: list[str] | None = None) -> object:
    """Create a gate result with passed=False."""
    from tools.gates.gate_result import GateResult
    from datetime import datetime, timezone

    return GateResult(
        gate_type="supabase",
        phase_id="3",
        passed=False,
        status="BLOCKED",
        severity="BLOCK",
        confidence=0.0,
        checked_at=datetime.now(timezone.utc).isoformat(),
        issues=issues or ["Supabase gate failed"],
    )


# ---------------------------------------------------------------------------
# supabase_provision tests
# ---------------------------------------------------------------------------


class TestSupabaseProvision:
    """Tests for the supabase_provision standalone function."""

    def test_missing_credentials_returns_failure(self, tmp_path: Path) -> None:
        """Returns SubStepResult(success=False) when credentials are missing."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_provision

        ctx = _make_context(tmp_path)

        with patch(
            "web_app_factory._keychain.get_credential",
            return_value=None,
        ):
            result = supabase_provision(ctx)

        assert result.success is False
        assert "credential" in result.error.lower() or "supabase" in result.error.lower()
        assert result.sub_step_id == "supabase_provision"

    def test_provisioner_called_with_credentials(self, tmp_path: Path) -> None:
        """SupabaseProvisioner.create_project is called when credentials present."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_provision

        ctx = _make_context(tmp_path)
        mock_provisioner = _make_mock_provisioner()

        with (
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
        ):
            result = supabase_provision(ctx)

        mock_provisioner.create_project.assert_called_once()
        assert result.success is True

    def test_ctx_extra_updated_with_project_ref(self, tmp_path: Path) -> None:
        """ctx.extra is updated with supabase_project_ref and supabase_api_keys."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_provision

        ctx = _make_context(tmp_path)
        mock_provisioner = _make_mock_provisioner()

        with (
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
        ):
            result = supabase_provision(ctx)

        assert ctx.extra.get("supabase_project_ref") == "abcxyz"
        assert "supabase_api_keys" in ctx.extra

    def test_provisioner_exception_returns_failure(self, tmp_path: Path) -> None:
        """Returns SubStepResult(success=False) when provisioner raises."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_provision

        ctx = _make_context(tmp_path)
        mock_provisioner = _make_mock_provisioner()
        mock_provisioner.create_project = AsyncMock(
            side_effect=RuntimeError("API error: quota exceeded")
        )

        with (
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
        ):
            result = supabase_provision(ctx)

        assert result.success is False
        assert result.error is not None


# ---------------------------------------------------------------------------
# supabase_oauth_config tests
# ---------------------------------------------------------------------------


class TestSupabaseOauthConfig:
    """Tests for the supabase_oauth_config standalone function."""

    def test_skips_when_no_project_ref(self, tmp_path: Path) -> None:
        """Returns success=True with skip note when project_ref absent."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_oauth_config

        ctx = _make_context(tmp_path, extra={})

        result = supabase_oauth_config(ctx)

        assert result.success is True
        assert result.sub_step_id == "supabase_oauth_config"
        assert "skipped" in result.notes.lower()

    def test_skips_when_no_oauth_env_vars(self, tmp_path: Path) -> None:
        """Returns success=True with advisory when no OAuth env vars present."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_oauth_config

        ctx = _make_context(tmp_path, extra={"supabase_project_ref": "abcxyz"})

        with patch.dict("os.environ", {}, clear=False):
            # Ensure OAuth env vars are absent
            for var in ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "APPLE_CLIENT_ID", "APPLE_CLIENT_SECRET"]:
                import os
                os.environ.pop(var, None)

            result = supabase_oauth_config(ctx)

        assert result.success is True
        assert "skipped" in result.notes.lower() or "advisory" in result.notes.lower()

    def test_calls_configure_oauth_when_creds_present(self, tmp_path: Path) -> None:
        """configure_oauth_providers called when Google/Apple creds present."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_oauth_config

        ctx = _make_context(tmp_path, extra={"supabase_project_ref": "abcxyz"})
        mock_provisioner = _make_mock_provisioner()

        with (
            patch.dict("os.environ", {
                "GOOGLE_CLIENT_ID": "gid",
                "GOOGLE_CLIENT_SECRET": "gsec",
            }),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
        ):
            result = supabase_oauth_config(ctx)

        mock_provisioner.configure_oauth_providers.assert_called_once()
        assert result.success is True
        assert result.notes == "OAuth providers configured"

    def test_returns_success_advisory_on_api_failure(self, tmp_path: Path) -> None:
        """Returns success=True with advisory note when configure_oauth_providers raises."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_oauth_config

        ctx = _make_context(tmp_path, extra={"supabase_project_ref": "abcxyz"})
        mock_provisioner = _make_mock_provisioner()
        mock_provisioner.configure_oauth_providers = AsyncMock(
            side_effect=RuntimeError("Network timeout")
        )

        with (
            patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "gid", "GOOGLE_CLIENT_SECRET": "gsec"}),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
        ):
            result = supabase_oauth_config(ctx)

        assert result.success is True
        assert "advisory" in result.notes.lower() or "failed" in result.notes.lower()

    def test_never_logs_credential_values(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Credential values (secrets) are never passed to logger."""
        import logging
        from tools.phase_executors._phase_3_supabase_steps import supabase_oauth_config

        ctx = _make_context(tmp_path, extra={"supabase_project_ref": "abcxyz"})
        mock_provisioner = _make_mock_provisioner()
        mock_provisioner.configure_oauth_providers = AsyncMock(
            side_effect=RuntimeError("API error")
        )

        with (
            caplog.at_level(logging.WARNING),
            patch.dict("os.environ", {
                "GOOGLE_CLIENT_ID": "super-secret-client-id",
                "GOOGLE_CLIENT_SECRET": "super-secret-client-secret",
            }),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "super-secret-token" if key else None,
            ),
            patch(
                "web_app_factory._supabase_provisioner.SupabaseProvisioner",
                return_value=mock_provisioner,
            ),
        ):
            supabase_oauth_config(ctx)

        # No log record should contain the secret values
        log_text = " ".join(r.message for r in caplog.records)
        assert "super-secret-client-id" not in log_text
        assert "super-secret-client-secret" not in log_text
        assert "super-secret-token" not in log_text


# ---------------------------------------------------------------------------
# supabase_render tests
# ---------------------------------------------------------------------------


class TestSupabaseRender:
    """Tests for the supabase_render standalone function."""

    def test_render_templates_called(self, tmp_path: Path) -> None:
        """render_supabase_templates is called with nextjs_dir."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_render

        ctx = _make_context(tmp_path, extra={"nextjs_dir": str(tmp_path)})
        mock_render = MagicMock(return_value=["/mock/browser.ts", "/mock/server.ts"])

        with (
            patch(
                "web_app_factory._supabase_template_renderer.render_supabase_templates",
                mock_render,
            ),
            patch(
                "web_app_factory._supabase_template_renderer.add_supabase_deps",
                return_value=None,
            ),
        ):
            result = supabase_render(ctx)

        mock_render.assert_called_once()
        assert result.success is True

    def test_skips_dep_injection_when_no_package_json(self, tmp_path: Path) -> None:
        """Logs warning and skips add_supabase_deps when package.json absent."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_render

        ctx = _make_context(tmp_path, extra={"nextjs_dir": str(tmp_path)})
        # No package.json in tmp_path
        mock_add_deps = MagicMock()

        with (
            patch(
                "web_app_factory._supabase_template_renderer.render_supabase_templates",
                return_value=["/mock/browser.ts"],
            ),
            patch(
                "web_app_factory._supabase_template_renderer.add_supabase_deps",
                mock_add_deps,
            ),
        ):
            result = supabase_render(ctx)

        # add_supabase_deps should NOT be called (no package.json)
        mock_add_deps.assert_not_called()
        assert result.success is True

    def test_failure_on_renderer_exception(self, tmp_path: Path) -> None:
        """Returns SubStepResult(success=False) when render_supabase_templates raises."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_render

        ctx = _make_context(tmp_path, extra={"nextjs_dir": str(tmp_path)})

        with patch(
            "web_app_factory._supabase_template_renderer.render_supabase_templates",
            side_effect=FileNotFoundError("Template not found"),
        ):
            result = supabase_render(ctx)

        assert result.success is False
        assert result.error is not None


# ---------------------------------------------------------------------------
# supabase_gate tests
# ---------------------------------------------------------------------------


class TestSupabaseGate:
    """Tests for the supabase_gate standalone function."""

    def test_gate_called_with_project_ref_from_ctx(self, tmp_path: Path) -> None:
        """run_supabase_gate is called with project_ref from ctx.extra."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_gate

        ctx = _make_context(tmp_path, extra={"supabase_project_ref": "test-ref-abc"})
        mock_gate = MagicMock(return_value=_make_passing_gate_result())

        with (
            patch(
                "tools.gates.supabase_gate.run_supabase_gate",
                mock_gate,
            ),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
        ):
            result = supabase_gate(ctx)

        mock_gate.assert_called_once()
        call_kwargs = mock_gate.call_args[1]
        assert call_kwargs.get("project_ref") == "test-ref-abc"

    def test_passes_on_gate_success(self, tmp_path: Path) -> None:
        """Returns SubStepResult(success=True) when gate passes."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_gate

        ctx = _make_context(tmp_path, extra={"supabase_project_ref": "abcxyz"})

        with (
            patch(
                "tools.gates.supabase_gate.run_supabase_gate",
                return_value=_make_passing_gate_result(),
            ),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
        ):
            result = supabase_gate(ctx)

        assert result.success is True
        assert result.sub_step_id == "supabase_gate"

    def test_fails_on_gate_failure(self, tmp_path: Path) -> None:
        """Returns SubStepResult(success=False) when gate fails."""
        from tools.phase_executors._phase_3_supabase_steps import supabase_gate

        ctx = _make_context(tmp_path, extra={"supabase_project_ref": "abcxyz"})

        with (
            patch(
                "tools.gates.supabase_gate.run_supabase_gate",
                return_value=_make_failing_gate_result(["Missing RLS on table 'posts'"]),
            ),
            patch(
                "web_app_factory._keychain.get_credential",
                side_effect=lambda key: "mock-token" if key else None,
            ),
        ):
            result = supabase_gate(ctx)

        assert result.success is False
        assert result.error is not None
        assert "posts" in result.error
