"""Tests for tools/contract_pipeline_runner.py."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


CONTRACT_PATH = str(
    Path(__file__).resolve().parent.parent / "contracts" / "pipeline-contract.web.v1.yaml"
)


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
