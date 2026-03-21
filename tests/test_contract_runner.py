"""Tests for tools/contract_pipeline_runner.py."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


CONTRACT_PATH = str(
    Path(__file__).resolve().parent.parent / "contracts" / "pipeline-contract.web.v1.yaml"
)


# ---------------------------------------------------------------------------
# Executor registration tests (Task 2)
# ---------------------------------------------------------------------------

class TestExecutorRegistration:
    """Verify that importing contract_pipeline_runner triggers 2a and 2b registration."""

    def setup_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def test_executor_registration_2a(self):
        """After importing contract_pipeline_runner, get_executor('2a') is not None.

        Reload both the executor module and the runner to re-trigger module-level
        self-registration after _clear_registry().
        """
        import importlib
        import tools.phase_executors.phase_2a_executor as mod_2a
        import tools.contract_pipeline_runner  # noqa: F401
        importlib.reload(mod_2a)
        importlib.reload(tools.contract_pipeline_runner)
        from tools.phase_executors.registry import get_executor
        assert get_executor("2a") is not None

    def test_executor_registration_2b(self):
        """After importing contract_pipeline_runner, get_executor('2b') is not None.

        Reload both the executor module and the runner to re-trigger module-level
        self-registration after _clear_registry().
        """
        import importlib
        import tools.phase_executors.phase_2b_executor as mod_2b
        import tools.contract_pipeline_runner  # noqa: F401
        importlib.reload(mod_2b)
        importlib.reload(tools.contract_pipeline_runner)
        from tools.phase_executors.registry import get_executor
        assert get_executor("2b") is not None


# ---------------------------------------------------------------------------
# Gate dispatch tests (Task 2)
# ---------------------------------------------------------------------------

class TestGateDispatch:
    """Verify _run_gate_checks dispatches to gate executors by gate type."""

    def _make_build_gate_phase(self) -> dict:
        """Create a contract_phase dict with a 'build' gate."""
        return {
            "id": "2a",
            "gates": [
                {
                    "type": "build",
                    "conditions": {
                        "commands": ["npm run build"],
                    },
                }
            ],
        }

    def _make_static_analysis_gate_phase(self) -> dict:
        """Create a contract_phase dict with a 'static_analysis' gate."""
        return {
            "id": "2b",
            "gates": [
                {
                    "type": "static_analysis",
                    "conditions": {},
                }
            ],
        }

    def _make_artifact_gate_phase(self, tmp_path: Path) -> dict:
        """Create a contract_phase dict with an 'artifact' gate and a real file."""
        required_file = "docs/pipeline/prd.md"
        (tmp_path / "docs" / "pipeline").mkdir(parents=True)
        (tmp_path / required_file).write_text("# PRD", encoding="utf-8")
        return {
            "id": "1b",
            "gates": [
                {
                    "type": "artifact",
                    "conditions": {
                        "required_files": [required_file],
                    },
                }
            ],
        }

    def _make_tool_invocation_gate_phase(self, tmp_path: Path) -> dict:
        """Create a contract_phase dict with a 'tool_invocation' gate and a real marker."""
        docs_dir = tmp_path / "docs" / "pipeline"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "output.md").write_text("go_no_go: Go", encoding="utf-8")
        return {
            "id": "1a",
            "gates": [
                {
                    "type": "tool_invocation",
                    "conditions": {
                        "required_output_markers": ["go_no_go: Go"],
                    },
                }
            ],
        }

    def test_gate_dispatch_build(self, tmp_path):
        """_run_gate_checks dispatches gate_type='build' to run_build_gate."""
        from tools.gates.gate_result import GateResult
        from datetime import datetime, timezone

        passed_result = GateResult(
            gate_type="build",
            phase_id="2a",
            passed=True,
            status="PASS",
            severity="INFO",
            confidence=1.0,
            checked_at=datetime.now(timezone.utc).isoformat(),
            issues=[],
        )

        contract_phase = self._make_build_gate_phase()

        with patch("tools.contract_pipeline_runner.run_build_gate", return_value=passed_result) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert mock_gate.called
        mock_gate.assert_called_once_with(str(tmp_path), phase_id="2a")
        assert passed is True
        assert issues == []

    def test_gate_dispatch_build_failure(self, tmp_path):
        """_run_gate_checks propagates run_build_gate issues on failure."""
        from tools.gates.gate_result import GateResult
        from datetime import datetime, timezone

        failed_result = GateResult(
            gate_type="build",
            phase_id="2a",
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=datetime.now(timezone.utc).isoformat(),
            issues=["npm run build exited with code 1"],
        )

        contract_phase = self._make_build_gate_phase()

        with patch("tools.contract_pipeline_runner.run_build_gate", return_value=failed_result):
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is False
        assert "npm run build exited with code 1" in issues

    def test_gate_dispatch_static_analysis(self, tmp_path):
        """_run_gate_checks dispatches gate_type='static_analysis' to run_static_analysis_gate."""
        from tools.gates.gate_result import GateResult
        from datetime import datetime, timezone

        passed_result = GateResult(
            gate_type="static_analysis",
            phase_id="2b",
            passed=True,
            status="PASS",
            severity="INFO",
            confidence=1.0,
            checked_at=datetime.now(timezone.utc).isoformat(),
            issues=[],
        )

        contract_phase = self._make_static_analysis_gate_phase()

        with patch(
            "tools.contract_pipeline_runner.run_static_analysis_gate",
            return_value=passed_result
        ) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert mock_gate.called
        mock_gate.assert_called_once_with(str(tmp_path), phase_id="2b")
        assert passed is True
        assert issues == []

    def test_gate_dispatch_static_analysis_failure(self, tmp_path):
        """_run_gate_checks propagates run_static_analysis_gate issues on failure."""
        from tools.gates.gate_result import GateResult
        from datetime import datetime, timezone

        failed_result = GateResult(
            gate_type="static_analysis",
            phase_id="2b",
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=datetime.now(timezone.utc).isoformat(),
            issues=["src/app/layout.tsx:1: 'use client' directive found in server component file"],
        )

        contract_phase = self._make_static_analysis_gate_phase()

        with patch(
            "tools.contract_pipeline_runner.run_static_analysis_gate",
            return_value=failed_result
        ):
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is False
        assert any("use client" in issue for issue in issues)

    def test_gate_dispatch_unknown_type(self, tmp_path):
        """_run_gate_checks returns failure with descriptive message for unknown gate type."""
        contract_phase = {
            "id": "1a",
            "gates": [
                {
                    "type": "unknown_gate_xyz",
                    "conditions": {},
                }
            ],
        }

        from tools.contract_pipeline_runner import _run_gate_checks
        passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is False
        assert len(issues) > 0
        # Should describe the unknown gate type
        assert any("unknown_gate_xyz" in issue.lower() or "unknown" in issue.lower() for issue in issues)

    def test_gate_dispatch_artifact_regression(self, tmp_path):
        """Existing artifact gate (required_files) behavior still works correctly."""
        contract_phase = self._make_artifact_gate_phase(tmp_path)

        from tools.contract_pipeline_runner import _run_gate_checks
        passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is True
        assert issues == []

    def test_gate_dispatch_artifact_regression_missing_file(self, tmp_path):
        """Artifact gate fails correctly when required file is missing."""
        contract_phase = {
            "id": "1b",
            "gates": [
                {
                    "type": "artifact",
                    "conditions": {
                        "required_files": ["docs/pipeline/nonexistent.md"],
                    },
                }
            ],
        }

        from tools.contract_pipeline_runner import _run_gate_checks
        passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is False
        assert any("nonexistent.md" in issue for issue in issues)

    def test_gate_dispatch_tool_invocation_regression(self, tmp_path):
        """Existing tool_invocation gate (required_output_markers) behavior still works."""
        contract_phase = self._make_tool_invocation_gate_phase(tmp_path)

        from tools.contract_pipeline_runner import _run_gate_checks
        passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is True
        assert issues == []

    def test_gate_dispatch_tool_invocation_regression_missing_marker(self, tmp_path):
        """Tool invocation gate fails when marker is missing from docs/pipeline/."""
        (tmp_path / "docs" / "pipeline").mkdir(parents=True)
        contract_phase = {
            "id": "1a",
            "gates": [
                {
                    "type": "tool_invocation",
                    "conditions": {
                        "required_output_markers": ["go_no_go: Go"],
                    },
                }
            ],
        }

        from tools.contract_pipeline_runner import _run_gate_checks
        passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is False
        assert any("go_no_go" in issue for issue in issues)


def _make_stub_executor(phase_id: str, success: bool):
    """Create a real PhaseExecutor subclass stub for the given phase."""
    from tools.phase_executors.base import PhaseExecutor, PhaseContext, PhaseResult

    class StubExecutor(PhaseExecutor):
        @property
        def phase_id(self) -> str:
            return phase_id

        @property
        def sub_steps(self) -> list:
            return []

        def execute(self, ctx: PhaseContext) -> PhaseResult:
            return PhaseResult(
                phase_id=phase_id,
                success=success,
                error=None if success else "Stub executor failure",
            )

    return StubExecutor()


def _make_tracking_executor(phase_id: str, call_log: list, success: bool = True):
    """Create a PhaseExecutor stub that appends phase_id to call_log on execute."""
    from tools.phase_executors.base import PhaseExecutor, PhaseContext, PhaseResult

    class TrackingExecutor(PhaseExecutor):
        @property
        def phase_id(self) -> str:
            return phase_id

        @property
        def sub_steps(self) -> list:
            return []

        def execute(self, ctx: PhaseContext) -> PhaseResult:
            call_log.append(phase_id)
            return PhaseResult(phase_id=phase_id, success=success)

    return TrackingExecutor()


class TestLoadContract:
    def test_loads_yaml_with_5_phases(self):
        from tools.contract_pipeline_runner import load_contract
        contract = load_contract(CONTRACT_PATH)
        assert "phases" in contract
        assert len(contract["phases"]) == 5

    def test_loaded_contract_has_phase_ids(self):
        from tools.contract_pipeline_runner import load_contract
        contract = load_contract(CONTRACT_PATH)
        phase_ids = [p["id"] for p in contract["phases"]]
        assert "1a" in phase_ids
        assert "1b" in phase_ids
        assert "2a" in phase_ids
        assert "2b" in phase_ids
        assert "3" in phase_ids

    def test_validates_against_json_schema(self):
        """load_contract should not raise on a valid contract."""
        from tools.contract_pipeline_runner import load_contract
        # Should not raise ValidationError
        contract = load_contract(CONTRACT_PATH)
        assert contract is not None

    def test_raises_on_missing_file(self):
        from tools.contract_pipeline_runner import load_contract
        with pytest.raises(Exception):
            load_contract("/nonexistent/path/contract.yaml")


class TestRunPipeline:
    def test_stops_at_first_failing_phase(self, tmp_path):
        from tools.contract_pipeline_runner import load_contract, run_pipeline
        from tools.phase_executors.registry import _clear_registry, register

        _clear_registry()
        failing_1a = _make_stub_executor("1a", success=False)
        register(failing_1a)

        called_order: list[str] = []
        passing_1b = _make_tracking_executor("1b", called_order, success=True)
        register(passing_1b)

        contract = load_contract(CONTRACT_PATH)
        result = run_pipeline(
            contract=contract,
            project_dir=str(tmp_path),
            idea="test idea",
            skip_gates=True,
        )

        assert result["status"] == "failed"
        # 1b should never have been called
        assert "1b" not in called_order

        _clear_registry()

    def test_executes_phases_in_order(self, tmp_path):
        from tools.contract_pipeline_runner import load_contract, run_pipeline
        from tools.phase_executors.registry import _clear_registry, register

        _clear_registry()
        called_order: list[str] = []

        for pid in ["1a", "1b", "2a", "2b", "3"]:
            register(_make_tracking_executor(pid, called_order, success=True))

        contract = load_contract(CONTRACT_PATH)
        result = run_pipeline(
            contract=contract,
            project_dir=str(tmp_path),
            idea="test idea",
            skip_gates=True,
        )

        assert called_order == ["1a", "1b", "2a", "2b", "3"]
        _clear_registry()

    def test_resume_skips_completed_phases(self, tmp_path):
        from tools.contract_pipeline_runner import load_contract, run_pipeline
        from tools.phase_executors.registry import _clear_registry, register
        import tools.pipeline_state as ps

        # Pre-populate state with 1a completed
        state = ps.init_run("test-app", str(tmp_path), "test idea")
        ps.phase_start(state.run_id, "1a", str(tmp_path))
        ps.phase_complete(state.run_id, "1a", str(tmp_path))

        _clear_registry()
        called_order: list[str] = []
        executor_1a = _make_tracking_executor("1a", called_order, success=True)
        executor_1b = _make_tracking_executor("1b", called_order, success=False)  # Stop at 1b
        register(executor_1a)
        register(executor_1b)

        contract = load_contract(CONTRACT_PATH)
        result = run_pipeline(
            contract=contract,
            project_dir=str(tmp_path),
            idea="test idea",
            resume_run_id=state.run_id,
            skip_gates=True,
        )

        # 1a was already complete, should not re-execute it
        assert "1a" not in called_order
        # 1b should have been called (and failed)
        assert "1b" in called_order

        _clear_registry()


# ---------------------------------------------------------------------------
# New gate dispatch tests (Task 2 — Phase 04-03)
# ---------------------------------------------------------------------------


def _make_passing_gate_result(gate_type: str = "test") -> object:
    """Create a GateResult with passed=True for testing."""
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


def _make_failing_gate_result(gate_type: str = "test") -> object:
    """Create a GateResult with passed=False for testing."""
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
        issues=[f"{gate_type} check failed"],
    )


def _make_deployment_json(tmp_path: Path, preview_url: str = "https://test.vercel.app") -> None:
    """Create docs/pipeline/deployment.json with the given preview_url."""
    import json
    pipeline_dir = tmp_path / "docs" / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    (pipeline_dir / "deployment.json").write_text(
        json.dumps({"preview_url": preview_url, "platform": "vercel"}),
        encoding="utf-8",
    )


class TestReadDeploymentUrl:
    """Tests for the _read_deployment_url helper."""

    def test_read_deployment_url_success(self, tmp_path):
        """deployment.json exists with URL -> returns URL string."""
        expected_url = "https://myapp-abc.vercel.app"
        _make_deployment_json(tmp_path, preview_url=expected_url)

        from tools.contract_pipeline_runner import _read_deployment_url
        url = _read_deployment_url(str(tmp_path))

        assert url == expected_url

    def test_read_deployment_url_missing_file(self, tmp_path):
        """deployment.json missing -> ValueError raised."""
        from tools.contract_pipeline_runner import _read_deployment_url

        with pytest.raises(ValueError, match="deployment.json not found"):
            _read_deployment_url(str(tmp_path))

    def test_read_deployment_url_missing_field(self, tmp_path):
        """deployment.json exists but preview_url field empty -> ValueError."""
        import json
        pipeline_dir = tmp_path / "docs" / "pipeline"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        (pipeline_dir / "deployment.json").write_text(
            json.dumps({"platform": "vercel"}),  # no preview_url
            encoding="utf-8",
        )

        from tools.contract_pipeline_runner import _read_deployment_url

        with pytest.raises(ValueError, match="preview_url"):
            _read_deployment_url(str(tmp_path))


class TestNewGateDispatch:
    """Test that _run_gate_checks dispatches to the 7 new gate types."""

    def test_gate_dispatch_lighthouse(self, tmp_path):
        """_run_gate_checks dispatches gate_type='lighthouse' to run_lighthouse_gate."""
        _make_deployment_json(tmp_path)

        contract_phase = {
            "id": "3",
            "gates": [{"type": "lighthouse", "conditions": {}}],
        }
        passing_result = _make_passing_gate_result("lighthouse")

        with patch("tools.contract_pipeline_runner._run_gate_checks.__module__") if False else \
             patch("tools.gates.lighthouse_gate.run_lighthouse_gate", return_value=passing_result):
            # Import inside context to pick up new dispatch logic
            from tools.contract_pipeline_runner import _run_gate_checks
            with patch("tools.contract_pipeline_runner.run_lighthouse_gate",
                       return_value=passing_result, create=True):
                pass  # won't hit this — we need lazy import patching

        # Re-approach: patch the module path for lazy import
        with patch("tools.gates.lighthouse_gate.run_lighthouse_gate", return_value=passing_result) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is True
        assert issues == []

    def test_gate_dispatch_lighthouse_calls_with_url(self, tmp_path):
        """Lighthouse gate is called with URL from deployment.json."""
        expected_url = "https://lh-test.vercel.app"
        _make_deployment_json(tmp_path, preview_url=expected_url)

        contract_phase = {
            "id": "3",
            "gates": [{"type": "lighthouse", "conditions": {}}],
        }
        passing_result = _make_passing_gate_result("lighthouse")

        with patch("tools.gates.lighthouse_gate.run_lighthouse_gate", return_value=passing_result) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        mock_gate.assert_called_once_with(
            url=expected_url,
            thresholds=None,
            phase_id="3",
        )

    def test_gate_dispatch_accessibility(self, tmp_path):
        """_run_gate_checks dispatches gate_type='accessibility' to run_accessibility_gate."""
        expected_url = "https://a11y-test.vercel.app"
        _make_deployment_json(tmp_path, preview_url=expected_url)

        contract_phase = {
            "id": "3",
            "gates": [{"type": "accessibility", "conditions": {}}],
        }
        passing_result = _make_passing_gate_result("accessibility")

        with patch("tools.gates.accessibility_gate.run_accessibility_gate", return_value=passing_result) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is True
        mock_gate.assert_called_once_with(url=expected_url, phase_id="3")

    def test_gate_dispatch_security_headers(self, tmp_path):
        """_run_gate_checks dispatches gate_type='security_headers' to run_security_headers_gate."""
        expected_url = "https://sec-test.vercel.app"
        _make_deployment_json(tmp_path, preview_url=expected_url)

        contract_phase = {
            "id": "3",
            "gates": [{"type": "security_headers", "conditions": {}}],
        }
        passing_result = _make_passing_gate_result("security_headers")

        with patch("tools.gates.security_headers_gate.run_security_headers_gate", return_value=passing_result) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is True
        mock_gate.assert_called_once_with(url=expected_url, phase_id="3")

    def test_gate_dispatch_link_integrity(self, tmp_path):
        """_run_gate_checks dispatches gate_type='link_integrity' to run_link_integrity_gate."""
        expected_url = "https://link-test.vercel.app"
        _make_deployment_json(tmp_path, preview_url=expected_url)

        contract_phase = {
            "id": "3",
            "gates": [{"type": "link_integrity", "conditions": {}}],
        }
        passing_result = _make_passing_gate_result("link_integrity")

        with patch("tools.gates.link_integrity_gate.run_link_integrity_gate", return_value=passing_result) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is True
        mock_gate.assert_called_once_with(url=expected_url, phase_id="3")

    def test_gate_dispatch_deployment(self, tmp_path):
        """_run_gate_checks dispatches gate_type='deployment' to run_deployment_gate."""
        expected_url = "https://depl-test.vercel.app"
        _make_deployment_json(tmp_path, preview_url=expected_url)

        contract_phase = {
            "id": "3",
            "gates": [{"type": "deployment", "conditions": {}}],
        }
        passing_result = _make_passing_gate_result("deployment")

        with patch("tools.gates.deployment_gate.run_deployment_gate", return_value=passing_result) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is True
        mock_gate.assert_called_once_with(url=expected_url, phase_id="3")

    def test_gate_dispatch_mcp_approval(self, tmp_path):
        """_run_gate_checks dispatches gate_type='mcp_approval' to run_mcp_approval_gate."""
        contract_phase = {
            "id": "3",
            "gates": [{"type": "mcp_approval", "conditions": {}}],
        }
        passing_result = _make_passing_gate_result("mcp_approval")

        with patch("tools.gates.mcp_approval_gate.run_mcp_approval_gate", return_value=passing_result) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is True
        mock_gate.assert_called_once_with(phase_id="3", project_dir=str(tmp_path))

    def test_gate_dispatch_legal(self, tmp_path):
        """_run_gate_checks dispatches gate_type='legal' to run_legal_gate."""
        contract_phase = {
            "id": "3",
            "gates": [{"type": "legal", "conditions": {}}],
        }
        passing_result = _make_passing_gate_result("legal")

        with patch("tools.gates.legal_gate.run_legal_gate", return_value=passing_result) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is True
        mock_gate.assert_called_once_with(project_dir=str(tmp_path), phase_id="3")

    def test_gate_dispatch_lighthouse_failure_propagates(self, tmp_path):
        """Lighthouse gate failure issues are propagated to _run_gate_checks."""
        _make_deployment_json(tmp_path)

        contract_phase = {
            "id": "3",
            "gates": [{"type": "lighthouse", "conditions": {}}],
        }
        failing_result = _make_failing_gate_result("lighthouse")

        with patch("tools.gates.lighthouse_gate.run_lighthouse_gate", return_value=failing_result):
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is False
        assert len(issues) >= 1
        assert any("lighthouse" in issue.lower() for issue in issues)

    def test_gate_dispatch_missing_deployment_json(self, tmp_path):
        """URL-dependent gates fail with descriptive error when deployment.json missing."""
        contract_phase = {
            "id": "3",
            "gates": [{"type": "lighthouse", "conditions": {}}],
        }

        from tools.contract_pipeline_runner import _run_gate_checks
        passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is False
        assert len(issues) >= 1
        assert any("deployment.json" in issue or "deployment" in issue.lower() for issue in issues)


# ---------------------------------------------------------------------------
# nextjs_dir gate dispatch tests (Phase 05-01 — BILD-02/03/04)
# ---------------------------------------------------------------------------


class TestNextjsDirGateDispatch:
    """Verify _run_gate_checks passes nextjs_dir to build and static_analysis gates."""

    def _make_build_gate_phase(self) -> dict:
        """Create a contract_phase dict with a 'build' gate."""
        return {
            "id": "2a",
            "gates": [
                {
                    "type": "build",
                    "conditions": {"commands": ["npm run build"]},
                }
            ],
        }

    def _make_static_analysis_gate_phase(self) -> dict:
        """Create a contract_phase dict with a 'static_analysis' gate."""
        return {
            "id": "2b",
            "gates": [
                {
                    "type": "static_analysis",
                    "conditions": {},
                }
            ],
        }

    def _make_passing_build_gate_result(self) -> object:
        from tools.gates.gate_result import GateResult
        from datetime import datetime, timezone
        return GateResult(
            gate_type="build",
            phase_id="2a",
            passed=True,
            status="PASS",
            severity="INFO",
            confidence=1.0,
            checked_at=datetime.now(timezone.utc).isoformat(),
            issues=[],
        )

    def _make_passing_static_analysis_result(self) -> object:
        from tools.gates.gate_result import GateResult
        from datetime import datetime, timezone
        return GateResult(
            gate_type="static_analysis",
            phase_id="2b",
            passed=True,
            status="PASS",
            severity="INFO",
            confidence=1.0,
            checked_at=datetime.now(timezone.utc).isoformat(),
            issues=[],
        )

    def test_build_gate_receives_nextjs_dir(self, tmp_path):
        """_run_gate_checks passes nextjs_dir (not project_dir) to build gate when nextjs_dir provided.

        BILD-03: The build gate must receive the Next.js project directory so that
        npm run build and tsc --noEmit run inside the directory that has package.json.
        """
        contract_phase = self._make_build_gate_phase()
        nextjs_dir = str(tmp_path / "nextjs-app")
        pipeline_dir = str(tmp_path / "pipeline-root")
        passed_result = self._make_passing_build_gate_result()

        with patch("tools.contract_pipeline_runner.run_build_gate", return_value=passed_result) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, pipeline_dir, nextjs_dir=nextjs_dir)

        # Gate should have been called with nextjs_dir, NOT pipeline_dir
        mock_gate.assert_called_once_with(nextjs_dir, phase_id="2a")
        assert passed is True

    def test_static_analysis_gate_receives_nextjs_dir(self, tmp_path):
        """_run_gate_checks passes nextjs_dir (not project_dir) to static_analysis gate.

        BILD-04: The static analysis gate must receive the Next.js project directory
        so that src/app/layout.tsx and page.tsx are scanned in the generated project.
        """
        contract_phase = self._make_static_analysis_gate_phase()
        nextjs_dir = str(tmp_path / "nextjs-app")
        pipeline_dir = str(tmp_path / "pipeline-root")
        passed_result = self._make_passing_static_analysis_result()

        with patch(
            "tools.contract_pipeline_runner.run_static_analysis_gate",
            return_value=passed_result,
        ) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, pipeline_dir, nextjs_dir=nextjs_dir)

        # Gate should have been called with nextjs_dir, NOT pipeline_dir
        mock_gate.assert_called_once_with(nextjs_dir, phase_id="2b")
        assert passed is True

    def test_build_gate_falls_back_to_project_dir_when_no_nextjs_dir(self, tmp_path):
        """_run_gate_checks falls back to project_dir when nextjs_dir is not provided.

        Backward-compatibility: when called without nextjs_dir, behavior is unchanged.
        """
        contract_phase = self._make_build_gate_phase()
        pipeline_dir = str(tmp_path)
        passed_result = self._make_passing_build_gate_result()

        with patch("tools.contract_pipeline_runner.run_build_gate", return_value=passed_result) as mock_gate:
            from tools.contract_pipeline_runner import _run_gate_checks
            passed, issues = _run_gate_checks(contract_phase, pipeline_dir)

        mock_gate.assert_called_once_with(pipeline_dir, phase_id="2a")
        assert passed is True


# ---------------------------------------------------------------------------
# GovernanceMonitor integration tests (Phase 05-01 — PIPE-05)
# ---------------------------------------------------------------------------


class TestGovernanceIntegration:
    """Verify GovernanceMonitor is instantiated in run_pipeline."""

    def setup_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def teardown_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def test_governance_monitor_instantiated_in_run_pipeline(self, tmp_path):
        """run_pipeline() instantiates GovernanceMonitor with blocking=False.

        PIPE-05: GovernanceMonitor must be wired into the live pipeline runner so
        that phase-skip enforcement and phase lifecycle tracking are active.
        """
        from tools.contract_pipeline_runner import load_contract, run_pipeline
        from tools.phase_executors.registry import register

        # Register a stub for "1a" only — all other phases skip (no executor)
        register(_make_stub_executor("1a", success=True))

        contract = load_contract(CONTRACT_PATH)

        with patch(
            "tools.contract_pipeline_runner.GovernanceMonitor"
        ) as MockGovernanceMonitor:
            mock_monitor_instance = MagicMock()
            MockGovernanceMonitor.return_value = mock_monitor_instance

            result = run_pipeline(
                contract=contract,
                project_dir=str(tmp_path),
                idea="test governance integration",
                skip_gates=True,
            )

        # GovernanceMonitor must have been instantiated
        assert MockGovernanceMonitor.called, (
            "GovernanceMonitor was not instantiated in run_pipeline(). "
            "PIPE-05 requires GovernanceMonitor to be wired into the live pipeline."
        )

        # Must be instantiated with blocking=False
        call_kwargs = MockGovernanceMonitor.call_args
        assert call_kwargs is not None
        _, kwargs = call_kwargs
        assert kwargs.get("blocking") is False, (
            f"GovernanceMonitor must be called with blocking=False, got: {kwargs!r}"
        )


class TestPhase3ContractAlignment:
    """Regression tests for Phase 3 contract alignment (CONT-04).

    Prevents path drift and duplicate mcp_approval gate from being re-introduced.
    """

    _CONTRACT_PATH = Path(__file__).parent.parent / "contracts" / "pipeline-contract.web.v1.yaml"

    def _load_phase_3(self) -> dict:
        """Load the live YAML contract and return the Phase 3 config."""
        import yaml

        contract = yaml.safe_load(self._CONTRACT_PATH.read_text(encoding="utf-8"))
        phase_3 = next(
            (p for p in contract["phases"] if str(p["id"]) == "3"),
            None,
        )
        assert phase_3 is not None, "Phase '3' not found in contract YAML"
        return phase_3

    def test_phase3_no_mcp_approval_gate_in_yaml(self) -> None:
        """Phase 3 gates in the live YAML do NOT include type 'mcp_approval'.

        The Phase3ShipExecutor already calls run_mcp_approval_gate() internally
        (sub-step 9). Having a second mcp_approval gate in the YAML causes
        _run_gate_checks() to dispatch a duplicate human-approval request.
        """
        phase_3 = self._load_phase_3()
        gate_types = [g["type"] for g in phase_3.get("gates", [])]
        assert "mcp_approval" not in gate_types, (
            f"Phase 3 gates must NOT contain 'mcp_approval' — the executor already "
            f"handles it internally. Current gate types: {gate_types}"
        )


class TestExecutorRegistrationPhase3:
    """Verify Phase 3 executor self-registers via contract_pipeline_runner import."""

    def setup_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def test_executor_registration_phase_3(self):
        """After importing contract_pipeline_runner, get_executor('3') is not None."""
        import importlib
        import tools.phase_executors.phase_3_executor as mod_3
        import tools.contract_pipeline_runner  # noqa: F401
        importlib.reload(mod_3)
        importlib.reload(tools.contract_pipeline_runner)
        from tools.phase_executors.registry import get_executor
        executor = get_executor("3")
        assert executor is not None
        assert executor.phase_id == "3"

    def teardown_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()
