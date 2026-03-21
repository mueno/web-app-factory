"""Tests for tools/contract_pipeline_runner.py."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


CONTRACT_PATH = str(
    Path(__file__).resolve().parent.parent / "contracts" / "pipeline-contract.web.v1.yaml"
)


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
    def _make_failing_executor(self, phase_id: str):
        """Create a mock executor that returns failure."""
        from tools.phase_executors.base import PhaseResult
        executor = MagicMock()
        executor.phase_id = phase_id
        executor.execute.return_value = PhaseResult(
            phase_id=phase_id,
            success=False,
            error="Stub executor failure",
        )
        return executor

    def _make_passing_executor(self, phase_id: str):
        """Create a mock executor that returns success."""
        from tools.phase_executors.base import PhaseResult
        executor = MagicMock()
        executor.phase_id = phase_id
        executor.execute.return_value = PhaseResult(
            phase_id=phase_id,
            success=True,
        )
        return executor

    def test_stops_at_first_failing_phase(self, tmp_path):
        from tools.contract_pipeline_runner import load_contract, run_pipeline
        from tools.phase_executors.registry import _clear_registry, register

        _clear_registry()
        failing_1a = self._make_failing_executor("1a")
        register(failing_1a)
        passing_1b = self._make_passing_executor("1b")
        register(passing_1b)

        contract = load_contract(CONTRACT_PATH)
        result = run_pipeline(
            contract=contract,
            project_dir=str(tmp_path),
            idea="test idea",
            skip_gates=True,  # skip gate checks in unit test
        )

        assert result["status"] == "failed"
        # 1b should never have been called
        passing_1b.execute.assert_not_called()

        _clear_registry()

    def test_executes_phases_in_order(self, tmp_path):
        from tools.contract_pipeline_runner import load_contract, run_pipeline
        from tools.phase_executors.registry import _clear_registry, register

        _clear_registry()
        called_order = []

        for pid in ["1a", "1b", "2a", "2b", "3"]:
            executor = self._make_passing_executor(pid)
            # Capture call order via side_effect
            from tools.phase_executors.base import PhaseResult
            pid_capture = pid  # closure capture
            def make_side_effect(p):
                def side_effect(ctx):
                    called_order.append(p)
                    return PhaseResult(phase_id=p, success=True)
                return side_effect
            executor.execute.side_effect = make_side_effect(pid)
            register(executor)

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
        executor_1a = self._make_passing_executor("1a")
        executor_1b = self._make_failing_executor("1b")  # Stop at 1b
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
        executor_1a.execute.assert_not_called()
        # 1b should have been called (and failed)
        executor_1b.execute.assert_called_once()

        _clear_registry()
