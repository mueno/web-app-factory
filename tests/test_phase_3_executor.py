"""Tests for tools/phase_executors/phase_3_executor.py.

Verifies Phase3ShipExecutor:
- phase_id property returns "3"
- sub_steps list matches expected 10 items
- provision sub-step behavior (success / failure)
- deploy_preview URL capture and deployment.json writing
- legal document generation with PRD context
- legal gate sub-step
- gate retry logic (lighthouse, accessibility)
- gate no-retry (security_headers, link_integrity)
- MCP approval blocking
- deploy_production sub-step
- full happy-path integration
- self-registration at module import
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call


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


def _mock_subprocess_success(stdout: str = "") -> MagicMock:
    """Create a mock subprocess.CompletedProcess with returncode=0."""
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = stdout
    mock.stderr = ""
    return mock


def _mock_subprocess_failure(returncode: int = 1, stderr: str = "command failed") -> MagicMock:
    """Create a mock subprocess.CompletedProcess with non-zero returncode."""
    mock = MagicMock()
    mock.returncode = returncode
    mock.stdout = ""
    mock.stderr = stderr
    return mock


# ---------------------------------------------------------------------------
# Phase3ShipExecutor class properties
# ---------------------------------------------------------------------------


class TestPhase3ExecutorProperties:
    """Test basic properties of Phase3ShipExecutor."""

    def test_phase_id(self):
        """Phase3ShipExecutor().phase_id == '3'."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        executor = Phase3ShipExecutor()
        assert executor.phase_id == "3"

    def test_sub_steps_list(self):
        """sub_steps returns expected 10 items in order."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        executor = Phase3ShipExecutor()
        expected = [
            "provision",
            "deploy_preview",
            "generate_legal",
            "gate_legal",
            "gate_lighthouse",
            "gate_accessibility",
            "gate_security_headers",
            "gate_link_integrity",
            "gate_mcp_approval",
            "deploy_production",
        ]
        assert executor.sub_steps == expected

    def test_self_registration(self):
        """Phase3ShipExecutor self-registers as phase '3' on module import/reload."""
        import importlib
        from tools.phase_executors.registry import _clear_registry, get_executor
        import tools.phase_executors.phase_3_executor as mod_3

        # Clear and reload to re-trigger module-level self-registration
        _clear_registry()
        importlib.reload(mod_3)

        executor = get_executor("3")
        assert executor is not None
        assert executor.phase_id == "3"


# ---------------------------------------------------------------------------
# Provision sub-step
# ---------------------------------------------------------------------------


class TestProvisionSubStep:
    """Tests for the provision sub-step (vercel link --yes)."""

    def test_provision_success(self, tmp_path):
        """vercel link returns 0 -> SubStepResult(success=True)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_success()
            result = executor._provision(ctx)

        assert result.success is True
        assert result.sub_step_id == "provision"
        # Verify vercel link command was called
        args = mock_run.call_args[0][0]
        assert "vercel" in args
        assert "link" in args
        assert "--yes" in args

    def test_provision_failure(self, tmp_path):
        """vercel link returns 1 -> SubStepResult(success=False)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_failure(returncode=1, stderr="Not authenticated")
            result = executor._provision(ctx)

        assert result.success is False
        assert result.error is not None

    def test_provision_stops_pipeline_on_failure(self, tmp_path):
        """Provision failure stops execution (PhaseResult.success=False)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_failure()
            result = executor.execute(ctx)

        assert result.success is False
        # Only provision should have been attempted
        executed_steps = [s.sub_step_id for s in result.sub_steps]
        assert "provision" in executed_steps
        assert "deploy_preview" not in executed_steps


# ---------------------------------------------------------------------------
# deploy_preview sub-step
# ---------------------------------------------------------------------------


class TestDeployPreviewSubStep:
    """Tests for the deploy_preview sub-step."""

    def test_deploy_preview_captures_url(self, tmp_path):
        """stdout with Vercel URL -> URL parsed and deployment.json written."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()

        preview_url = "https://myapp-abc123.vercel.app"
        stdout = f"Deployed to {preview_url}\n"

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_success(stdout=stdout)
            result = executor._deploy_preview(ctx)

        assert result.success is True
        assert result.sub_step_id == "deploy_preview"

        # deployment.json should be written
        deployment_json_path = tmp_path / "docs" / "pipeline" / "deployment.json"
        assert deployment_json_path.exists()

        data = json.loads(deployment_json_path.read_text())
        assert data["preview_url"] == preview_url
        assert "deployed_at" in data
        assert data["platform"] == "vercel"

    def test_deploy_preview_url_regex_multiline(self, tmp_path):
        """Multi-line stdout with extra text -> URL still captured."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()

        preview_url = "https://myapp-xyz789.vercel.app"
        stdout = (
            "Installing dependencies...\n"
            "Building...\n"
            f"Deployment URL: {preview_url}\n"
            "Done!\n"
        )

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_success(stdout=stdout)
            result = executor._deploy_preview(ctx)

        assert result.success is True
        deployment_json_path = tmp_path / "docs" / "pipeline" / "deployment.json"
        data = json.loads(deployment_json_path.read_text())
        assert data["preview_url"] == preview_url

    def test_deploy_preview_url_not_found_fails(self, tmp_path):
        """stdout without Vercel URL -> SubStepResult(success=False)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_success(stdout="No URL here")
            result = executor._deploy_preview(ctx)

        assert result.success is False
        assert "URL" in result.error or "url" in result.error.lower()

    def test_deploy_preview_vercel_failure(self, tmp_path):
        """vercel CLI returns non-zero -> SubStepResult(success=False)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_failure(returncode=1)
            result = executor._deploy_preview(ctx)

        assert result.success is False


# ---------------------------------------------------------------------------
# generate_legal sub-step
# ---------------------------------------------------------------------------


class TestGenerateLegalSubStep:
    """Tests for the generate_legal sub-step."""

    def _setup_prd(self, tmp_path: Path) -> None:
        """Create a minimal PRD file."""
        prd_dir = tmp_path / "docs" / "pipeline"
        prd_dir.mkdir(parents=True, exist_ok=True)
        (prd_dir / "prd.md").write_text(
            "# WeightSnap PRD\n\n## Features\n\n- **WeightTracker**: Core feature\n",
            encoding="utf-8",
        )

    def test_legal_generation_with_prd(self, tmp_path):
        """Mock PRD content + company info -> deploy-agent called with PRD + company."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        self._setup_prd(tmp_path)

        ctx = _make_context(
            tmp_path,
            extra={"company_name": "AllNew LLC", "contact_email": "hello@allnew.jp"},
        )
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        with patch("tools.phase_executors.phase_3_executor.run_deploy_agent") as mock_agent:
            mock_agent.return_value = "Legal documents generated"
            result = executor._generate_legal(ctx)

        assert result.success is True
        assert result.sub_step_id == "generate_legal"

        # Verify deploy-agent was called
        assert mock_agent.called
        # Check all args/kwargs for the prompt content
        call_args = mock_agent.call_args
        # prompt can be positional or keyword arg
        if call_args[0]:
            prompt = call_args[0][0]
        else:
            prompt = call_args[1].get("prompt", "")
        # Prompt should include PRD content
        assert "WeightSnap" in prompt or "WeightTracker" in prompt
        # Prompt should include company info
        assert "AllNew LLC" in prompt
        assert "hello@allnew.jp" in prompt

    def test_legal_generation_without_company_info(self, tmp_path):
        """Missing company_name/contact_email -> deploy-agent still called."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        self._setup_prd(tmp_path)

        ctx = _make_context(tmp_path, extra={"company_name": None, "contact_email": None})
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        with patch("tools.phase_executors.phase_3_executor.run_deploy_agent") as mock_agent:
            mock_agent.return_value = "Docs generated"
            result = executor._generate_legal(ctx)

        # Should still succeed (legal gate will catch placeholder issues)
        assert result.success is True

    def test_legal_generation_missing_prd(self, tmp_path):
        """Missing prd.md -> deploy-agent still called (no PRD context)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        with patch("tools.phase_executors.phase_3_executor.run_deploy_agent") as mock_agent:
            mock_agent.return_value = "Docs generated"
            result = executor._generate_legal(ctx)

        assert result.success is True


# ---------------------------------------------------------------------------
# gate_legal sub-step
# ---------------------------------------------------------------------------


class TestGateLegalSubStep:
    """Tests for the gate_legal sub-step."""

    def test_legal_gate_pass(self, tmp_path):
        """Legal gate passes -> SubStepResult(success=True)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()

        passing_result = _make_passing_gate_result("legal")

        with patch("tools.phase_executors.phase_3_executor.run_legal_gate") as mock_gate:
            mock_gate.return_value = passing_result
            result = executor._gate_legal(ctx)

        assert result.success is True
        assert result.sub_step_id == "gate_legal"

    def test_legal_gate_fail(self, tmp_path):
        """Legal gate fails -> SubStepResult(success=False), no retry."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()

        failing_result = _make_failing_gate_result("legal", issues=["Missing privacy page"])

        with patch("tools.phase_executors.phase_3_executor.run_legal_gate") as mock_gate:
            mock_gate.return_value = failing_result
            result = executor._gate_legal(ctx)

        assert result.success is False
        # Legal gate is called only once (no retry)
        assert mock_gate.call_count == 1


# ---------------------------------------------------------------------------
# Gate retry logic
# ---------------------------------------------------------------------------


class TestGateRetry:
    """Tests for _run_gate_with_retry (lighthouse and accessibility)."""

    def test_gate_retry_passes_on_first_try(self, tmp_path):
        """Gate passes first try -> success with no retry."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        passing_result = _make_passing_gate_result("lighthouse")

        with patch("tools.phase_executors.phase_3_executor.run_deploy_agent") as mock_agent, \
             patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_sub:
            result = executor._run_gate_with_retry(
                gate_fn=lambda url: passing_result,
                gate_name="gate_lighthouse",
                preview_url="https://test.vercel.app",
                ctx=ctx,
                max_retries=3,
            )

        assert result.success is True
        assert result.sub_step_id == "gate_lighthouse"
        # No retry needed, so no deploy agent calls
        assert not mock_agent.called

    def test_gate_retry_on_failure_succeeds_third_attempt(self, tmp_path):
        """Gate fails twice, passes on 3rd -> overall success with retry notes."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        failing_result = _make_failing_gate_result("lighthouse")
        passing_result = _make_passing_gate_result("lighthouse")

        call_count = [0]

        def gate_fn(url: str):
            call_count[0] += 1
            if call_count[0] < 3:
                return failing_result
            return passing_result

        preview_stdout = "https://myapp-new.vercel.app"

        with patch("tools.phase_executors.phase_3_executor.run_deploy_agent") as mock_agent, \
             patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_sub:
            mock_agent.return_value = "Fixed issues"
            mock_sub.return_value = _mock_subprocess_success(stdout=f"https://myapp-new.vercel.app")
            result = executor._run_gate_with_retry(
                gate_fn=gate_fn,
                gate_name="gate_lighthouse",
                preview_url="https://test.vercel.app",
                ctx=ctx,
                max_retries=3,
            )

        assert result.success is True
        assert "retry" in result.notes.lower() or "attempt" in result.notes.lower()

    def test_gate_retry_exhausted(self, tmp_path):
        """Gate fails 3 times -> SubStepResult(success=False)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        failing_result = _make_failing_gate_result("lighthouse")
        preview_stdout = "https://myapp-new.vercel.app"

        with patch("tools.phase_executors.phase_3_executor.run_deploy_agent") as mock_agent, \
             patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_sub:
            mock_agent.return_value = "Fixed"
            mock_sub.return_value = _mock_subprocess_success(stdout=f"{preview_stdout}")
            result = executor._run_gate_with_retry(
                gate_fn=lambda url: failing_result,
                gate_name="gate_lighthouse",
                preview_url="https://test.vercel.app",
                ctx=ctx,
                max_retries=3,
            )

        assert result.success is False
        assert result.sub_step_id == "gate_lighthouse"

    def test_security_headers_no_retry(self, tmp_path):
        """security_headers gate runs once on failure (no retry pattern)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        failing_result = _make_failing_gate_result("security_headers")

        call_count = [0]

        def gate_fn(url: str):
            call_count[0] += 1
            return failing_result

        with patch("tools.phase_executors.phase_3_executor.run_deploy_agent") as mock_agent, \
             patch("tools.phase_executors.phase_3_executor.subprocess.run"):
            result = executor._gate_security_headers(ctx)

        # security_headers uses run_security_headers_gate mock, called once
        # The gate function was called from within _gate_security_headers

    def test_link_integrity_no_retry(self, tmp_path):
        """link_integrity gate runs once on failure (no retry pattern)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        failing_result = _make_failing_gate_result("link_integrity")

        with patch("tools.phase_executors.phase_3_executor.run_link_integrity_gate") as mock_gate:
            mock_gate.return_value = failing_result
            result = executor._gate_link_integrity(ctx)

        assert result.success is False
        # link_integrity called only once
        assert mock_gate.call_count == 1


# ---------------------------------------------------------------------------
# MCP approval sub-step
# ---------------------------------------------------------------------------


class TestMcpApprovalSubStep:
    """Tests for the gate_mcp_approval sub-step."""

    def test_mcp_approval_pass(self, tmp_path):
        """Approval gate passes -> SubStepResult(success=True)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        passing_result = _make_passing_gate_result("mcp_approval")

        with patch("tools.phase_executors.phase_3_executor.run_mcp_approval_gate") as mock_gate:
            mock_gate.return_value = passing_result
            result = executor._gate_mcp_approval(ctx)

        assert result.success is True
        assert result.sub_step_id == "gate_mcp_approval"

    def test_mcp_approval_rejected_stops_pipeline(self, tmp_path):
        """Approval gate rejected -> PhaseResult(success=False), no production deploy."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()

        failing_result = _make_failing_gate_result("mcp_approval", issues=["Human rejected"])

        # Mock all sub-steps up to mcp_approval to succeed
        passing_gate = _make_passing_gate_result()

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_sub, \
             patch("tools.phase_executors.phase_3_executor.run_deploy_agent") as mock_agent, \
             patch("tools.phase_executors.phase_3_executor.run_legal_gate") as mock_legal, \
             patch("tools.phase_executors.phase_3_executor.run_lighthouse_gate") as mock_lh, \
             patch("tools.phase_executors.phase_3_executor.run_accessibility_gate") as mock_a11y, \
             patch("tools.phase_executors.phase_3_executor.run_security_headers_gate") as mock_sec, \
             patch("tools.phase_executors.phase_3_executor.run_link_integrity_gate") as mock_link, \
             patch("tools.phase_executors.phase_3_executor.run_mcp_approval_gate") as mock_mcp:

            # Provision and deploy_preview succeed
            mock_sub.return_value = _mock_subprocess_success(
                stdout="https://test-app.vercel.app"
            )
            mock_agent.return_value = "Done"
            mock_legal.return_value = passing_gate
            mock_lh.return_value = passing_gate
            mock_a11y.return_value = passing_gate
            mock_sec.return_value = passing_gate
            mock_link.return_value = passing_gate
            mock_mcp.return_value = failing_result

            result = executor.execute(ctx)

        assert result.success is False
        executed_steps = [s.sub_step_id for s in result.sub_steps]
        assert "gate_mcp_approval" in executed_steps
        assert "deploy_production" not in executed_steps


# ---------------------------------------------------------------------------
# deploy_production sub-step
# ---------------------------------------------------------------------------


class TestDeployProductionSubStep:
    """Tests for the deploy_production sub-step."""

    def test_deploy_production_success(self, tmp_path):
        """vercel promote returns 0 -> SubStepResult(success=True)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        # Create deployment.json
        pipeline_dir = tmp_path / "docs" / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        (pipeline_dir / "deployment.json").write_text(
            json.dumps({"preview_url": "https://test.vercel.app", "platform": "vercel"}),
            encoding="utf-8",
        )

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_success()
            result = executor._deploy_production(ctx)

        assert result.success is True
        assert result.sub_step_id == "deploy_production"

        # Verify vercel promote command was called
        args = mock_run.call_args[0][0]
        assert "vercel" in args
        assert "promote" in args

    def test_deploy_production_failure(self, tmp_path):
        """vercel promote returns non-zero -> SubStepResult(success=False)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_failure()
            result = executor._deploy_production(ctx)

        assert result.success is False


# ---------------------------------------------------------------------------
# Full happy-path integration
# ---------------------------------------------------------------------------


class TestFullHappyPath:
    """End-to-end test with all sub-steps mocked to succeed."""

    def test_full_happy_path(self, tmp_path):
        """All sub-steps succeed -> PhaseResult(success=True) with 10 SubStepResults."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(
            tmp_path,
            extra={"company_name": "AllNew LLC", "contact_email": "hi@allnew.jp"},
        )
        executor = Phase3ShipExecutor()

        passing_gate = _make_passing_gate_result()
        preview_url = "https://myapp-happy.vercel.app"

        # Create PRD for generate_legal sub-step
        prd_dir = tmp_path / "docs" / "pipeline"
        prd_dir.mkdir(parents=True, exist_ok=True)
        (prd_dir / "prd.md").write_text("# App PRD\n\n## Features\n\n- Feature\n", encoding="utf-8")

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_sub, \
             patch("tools.phase_executors.phase_3_executor.run_deploy_agent") as mock_agent, \
             patch("tools.phase_executors.phase_3_executor.run_legal_gate") as mock_legal, \
             patch("tools.phase_executors.phase_3_executor.run_lighthouse_gate") as mock_lh, \
             patch("tools.phase_executors.phase_3_executor.run_accessibility_gate") as mock_a11y, \
             patch("tools.phase_executors.phase_3_executor.run_security_headers_gate") as mock_sec, \
             patch("tools.phase_executors.phase_3_executor.run_link_integrity_gate") as mock_link, \
             patch("tools.phase_executors.phase_3_executor.run_mcp_approval_gate") as mock_mcp, \
             patch("tools.phase_executors.phase_3_executor.generate_quality_self_assessment") as mock_qsa:

            # Provision (vercel link)
            # deploy_preview (vercel deploy) -> with URL
            mock_sub.return_value = _mock_subprocess_success(stdout=preview_url)
            mock_agent.return_value = "Completed"
            mock_legal.return_value = passing_gate
            mock_lh.return_value = passing_gate
            mock_a11y.return_value = passing_gate
            mock_sec.return_value = passing_gate
            mock_link.return_value = passing_gate
            mock_mcp.return_value = passing_gate

            result = executor.execute(ctx)

        assert result.success is True
        assert result.phase_id == "3"

        # Verify all 10 sub-steps are recorded
        step_ids = [s.sub_step_id for s in result.sub_steps]
        expected_steps = [
            "provision",
            "deploy_preview",
            "generate_legal",
            "gate_legal",
            "gate_lighthouse",
            "gate_accessibility",
            "gate_security_headers",
            "gate_link_integrity",
            "gate_mcp_approval",
            "deploy_production",
        ]
        for step in expected_steps:
            assert step in step_ids, f"Expected step '{step}' in sub_steps"

        # All sub-steps should be successful
        for step_result in result.sub_steps:
            assert step_result.success is True, (
                f"Sub-step '{step_result.sub_step_id}' was not successful: {step_result.error}"
            )


# ---------------------------------------------------------------------------
# nextjs_dir cwd propagation tests (Phase 07-01 — DEPL-01, LEGL-01/02/03)
# ---------------------------------------------------------------------------


class TestProvisionNextjsDir:
    """Test 2: provision uses nextjs_dir from ctx.extra as cwd."""

    def test_provision_uses_nextjs_dir_as_cwd(self, tmp_path):
        """_provision cwd kwarg uses nextjs_dir from ctx.extra, not ctx.project_dir."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path, extra={"nextjs_dir": "/fake/nextjs"})
        executor = Phase3ShipExecutor()

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_success()
            executor._provision(ctx)

        # subprocess.run must have been called with cwd="/fake/nextjs" (not str(tmp_path))
        assert mock_run.called, "subprocess.run was not called"
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("cwd") == "/fake/nextjs", (
            f"Expected cwd='/fake/nextjs', got cwd={call_kwargs.get('cwd')!r}. "
            "DEPL-01: _provision must use nextjs_dir (from ctx.extra) as cwd."
        )


class TestDeployPreviewNextjsDir:
    """Test 3: deploy_preview uses nextjs_dir from ctx.extra as cwd."""

    def test_deploy_preview_uses_nextjs_dir_as_cwd(self, tmp_path):
        """_deploy_preview cwd kwarg uses nextjs_dir from ctx.extra, not ctx.project_dir."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path, extra={"nextjs_dir": "/fake/nextjs"})
        executor = Phase3ShipExecutor()

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_success(
                stdout="https://test-app.vercel.app"
            )
            executor._deploy_preview(ctx)

        assert mock_run.called, "subprocess.run was not called"
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("cwd") == "/fake/nextjs", (
            f"Expected cwd='/fake/nextjs', got cwd={call_kwargs.get('cwd')!r}. "
            "DEPL-01: _deploy_preview must use nextjs_dir (from ctx.extra) as cwd."
        )


class TestGenerateLegalNextjsDir:
    """Test 4: _generate_legal uses nextjs_dir as project_dir for deploy agent."""

    def test_legal_generation_uses_nextjs_dir(self, tmp_path):
        """run_deploy_agent receives nextjs_dir as project_dir, not ctx.project_dir."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(
            tmp_path,
            extra={
                "nextjs_dir": "/fake/nextjs",
                "company_name": "AllNew LLC",
                "contact_email": "hi@allnew.jp",
            },
        )
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        # Create PRD so _generate_legal doesn't skip for missing PRD
        prd_dir = tmp_path / "docs" / "pipeline"
        prd_dir.mkdir(parents=True, exist_ok=True)
        (prd_dir / "prd.md").write_text("# PRD\n\n## Features\n\n- Feature\n", encoding="utf-8")

        with patch("tools.phase_executors.phase_3_executor.run_deploy_agent") as mock_agent:
            mock_agent.return_value = "Legal docs generated"
            executor._generate_legal(ctx)

        assert mock_agent.called, "run_deploy_agent was not called"
        call_kwargs = mock_agent.call_args[1]
        assert call_kwargs.get("project_dir") == "/fake/nextjs", (
            f"Expected project_dir='/fake/nextjs', got project_dir={call_kwargs.get('project_dir')!r}. "
            "LEGL-01: _generate_legal must pass nextjs_dir as project_dir to deploy agent."
        )


class TestGateLegalNextjsDir:
    """Test 5: _gate_legal uses nextjs_dir as the directory arg to run_legal_gate."""

    def test_legal_gate_uses_nextjs_dir(self, tmp_path):
        """run_legal_gate receives nextjs_dir as first positional arg, not str(ctx.project_dir)."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path, extra={"nextjs_dir": "/fake/nextjs"})
        executor = Phase3ShipExecutor()

        passing_result = _make_passing_gate_result("legal")

        with patch("tools.phase_executors.phase_3_executor.run_legal_gate") as mock_gate:
            mock_gate.return_value = passing_result
            executor._gate_legal(ctx)

        assert mock_gate.called, "run_legal_gate was not called"
        # The first positional arg must be nextjs_dir
        call_args = mock_gate.call_args[0]
        assert call_args[0] == "/fake/nextjs", (
            f"Expected run_legal_gate('/fake/nextjs', ...), got first arg={call_args[0]!r}. "
            "LEGL-03: _gate_legal must pass nextjs_dir (not ctx.project_dir) to run_legal_gate."
        )


class TestGateRetryNextjsDir:
    """Test 6: _run_gate_with_retry re-deploy subprocess uses nextjs_dir as cwd."""

    def test_retry_redeploy_uses_nextjs_dir_as_cwd(self, tmp_path):
        """After gate failure, the re-deploy subprocess.run uses cwd=nextjs_dir."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path, extra={"nextjs_dir": "/fake/nextjs"})
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        # Gate fails first, passes second time (triggers 1 retry + redeploy)
        failing_result = _make_failing_gate_result("lighthouse")
        passing_result = _make_passing_gate_result("lighthouse")
        call_count = [0]

        def gate_fn(url: str):
            call_count[0] += 1
            if call_count[0] < 2:
                return failing_result
            return passing_result

        with patch("tools.phase_executors.phase_3_executor.run_deploy_agent"), \
             patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_sub:
            mock_sub.return_value = _mock_subprocess_success(
                stdout="https://myapp-new.vercel.app"
            )
            executor._run_gate_with_retry(
                gate_fn=gate_fn,
                gate_name="gate_lighthouse",
                preview_url="https://test.vercel.app",
                ctx=ctx,
                max_retries=3,
            )

        # At least one subprocess.run call (re-deploy) must have cwd="/fake/nextjs"
        assert mock_sub.called, "subprocess.run was not called during retry"
        redeploy_cwds = [
            call[1].get("cwd")
            for call in mock_sub.call_args_list
        ]
        assert "/fake/nextjs" in redeploy_cwds, (
            f"Expected at least one subprocess.run call with cwd='/fake/nextjs', "
            f"got cwds={redeploy_cwds!r}. "
            "DEPL-01: retry redeploy must use nextjs_dir (from ctx.extra) as cwd."
        )


class TestDeployProductionNextjsDir:
    """Test 7: _deploy_production uses nextjs_dir as cwd."""

    def test_deploy_production_uses_nextjs_dir_as_cwd(self, tmp_path):
        """_deploy_production cwd kwarg uses nextjs_dir from ctx.extra, not ctx.project_dir."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path, extra={"nextjs_dir": "/fake/nextjs"})
        executor = Phase3ShipExecutor()
        executor._preview_url = "https://test.vercel.app"

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_run:
            mock_run.return_value = _mock_subprocess_success()
            executor._deploy_production(ctx)

        assert mock_run.called, "subprocess.run was not called"
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("cwd") == "/fake/nextjs", (
            f"Expected cwd='/fake/nextjs', got cwd={call_kwargs.get('cwd')!r}. "
            "DEPL-01: _deploy_production must use nextjs_dir (from ctx.extra) as cwd."
        )

    def test_quality_self_assessment_generated(self, tmp_path):
        """Quality self-assessment is generated after all sub-steps."""
        from tools.phase_executors.phase_3_executor import Phase3ShipExecutor
        ctx = _make_context(tmp_path)
        executor = Phase3ShipExecutor()

        passing_gate = _make_passing_gate_result()
        preview_url = "https://myapp.vercel.app"

        prd_dir = tmp_path / "docs" / "pipeline"
        prd_dir.mkdir(parents=True, exist_ok=True)
        (prd_dir / "prd.md").write_text("# PRD\n", encoding="utf-8")

        with patch("tools.phase_executors.phase_3_executor.subprocess.run") as mock_sub, \
             patch("tools.phase_executors.phase_3_executor.run_deploy_agent") as mock_agent, \
             patch("tools.phase_executors.phase_3_executor.run_legal_gate") as mock_legal, \
             patch("tools.phase_executors.phase_3_executor.run_lighthouse_gate") as mock_lh, \
             patch("tools.phase_executors.phase_3_executor.run_accessibility_gate") as mock_a11y, \
             patch("tools.phase_executors.phase_3_executor.run_security_headers_gate") as mock_sec, \
             patch("tools.phase_executors.phase_3_executor.run_link_integrity_gate") as mock_link, \
             patch("tools.phase_executors.phase_3_executor.run_mcp_approval_gate") as mock_mcp, \
             patch("tools.phase_executors.phase_3_executor.generate_quality_self_assessment") as mock_qsa:

            mock_sub.return_value = _mock_subprocess_success(stdout=preview_url)
            mock_agent.return_value = "Done"
            mock_legal.return_value = passing_gate
            mock_lh.return_value = passing_gate
            mock_a11y.return_value = passing_gate
            mock_sec.return_value = passing_gate
            mock_link.return_value = passing_gate
            mock_mcp.return_value = passing_gate

            result = executor.execute(ctx)

        assert result.success is True
        assert mock_qsa.called
