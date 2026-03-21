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
