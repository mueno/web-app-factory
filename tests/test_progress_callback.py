"""Tests for the on_progress callback added to run_pipeline().

Covers:
- test_callback_receives_events: callback receives all expected event types in order.
- test_no_callback_works: calling run_pipeline without on_progress succeeds (backward compat).
- test_callback_exception_ignored: a raising callback never breaks the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------

CONTRACT_PATH = str(
    Path(__file__).resolve().parent.parent / "contracts" / "pipeline-contract.web.v1.yaml"
)


def _make_stub_executor(phase_id: str, success: bool = True):
    """Create a minimal PhaseExecutor stub."""
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


def _run_single_phase_pipeline(
    tmp_path: Path,
    phase_id: str = "1a",
    on_progress=None,
    skip_gates: bool = True,
):
    """Run the pipeline with a single stub executor for one phase.

    Registers executors for all phases so the pipeline can complete.
    Returns the result dict.
    """
    from tools.contract_pipeline_runner import load_contract, run_pipeline
    from tools.phase_executors.registry import _clear_registry, register

    _clear_registry()

    # Register stub executors for all 5 phases so run_pipeline runs to completion.
    for pid in ["1a", "1b", "2a", "2b", "3"]:
        register(_make_stub_executor(pid, success=True))

    contract = load_contract(CONTRACT_PATH)
    result = run_pipeline(
        contract=contract,
        project_dir=str(tmp_path),
        idea="progress callback test",
        skip_gates=skip_gates,
        on_progress=on_progress,
    )

    _clear_registry()
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProgressCallback:
    def test_callback_receives_events(self, tmp_path):
        """on_progress callback receives phase_start, phase_execute_done,
        gate_start, gate_result, phase_complete events in the expected order.

        We run with skip_gates=False and mock _run_gate_checks to return
        (True, []) so we get gate events without touching the real gate logic.
        """
        from tools.phase_executors.registry import _clear_registry, register
        from tools.contract_pipeline_runner import load_contract, run_pipeline

        received: list[tuple] = []

        def on_progress(event_type, phase_id, message, detail):
            received.append((event_type, phase_id))

        _clear_registry()
        for pid in ["1a", "1b", "2a", "2b", "3"]:
            register(_make_stub_executor(pid, success=True))

        contract = load_contract(CONTRACT_PATH)

        # Patch gate checks to pass and quality self-assessment to no-op
        with patch(
            "tools.contract_pipeline_runner._run_gate_checks",
            return_value=(True, []),
        ), patch(
            "tools.contract_pipeline_runner.generate_quality_self_assessment"
        ):
            result = run_pipeline(
                contract=contract,
                project_dir=str(tmp_path),
                idea="progress callback test",
                skip_gates=False,
                on_progress=on_progress,
            )

        _clear_registry()

        assert result["status"] == "completed"

        # Build the ordered list of events actually received
        event_types = [e for e, _ in received]

        # For every phase we expect this sequence of event types
        expected_sequence = [
            "phase_start",
            "phase_execute_done",
            "gate_start",
            "gate_result",
            "phase_complete",
        ]
        all_phases = ["1a", "1b", "2a", "2b", "3"]

        # Verify that each phase emits all 5 events
        for phase in all_phases:
            phase_events = [e for e, pid in received if pid == phase]
            for expected_event in expected_sequence:
                assert expected_event in phase_events, (
                    f"Expected event {expected_event!r} for phase {phase!r} "
                    f"but got: {phase_events}"
                )

        # Verify phase_start always precedes phase_complete for each phase
        for phase in all_phases:
            start_idx = next(
                i for i, (e, pid) in enumerate(received) if e == "phase_start" and pid == phase
            )
            complete_idx = next(
                i for i, (e, pid) in enumerate(received) if e == "phase_complete" and pid == phase
            )
            assert start_idx < complete_idx, (
                f"phase_start must precede phase_complete for phase {phase}"
            )

    def test_no_callback_works(self, tmp_path):
        """Calling run_pipeline without on_progress completes without error (backward compat)."""
        result = _run_single_phase_pipeline(tmp_path, on_progress=None, skip_gates=True)
        assert result["status"] == "completed"

    def test_callback_exception_ignored(self, tmp_path):
        """A callback that raises must not break the pipeline."""

        def raising_callback(event_type, phase_id, message, detail):
            raise RuntimeError("Simulated callback failure")

        result = _run_single_phase_pipeline(
            tmp_path, on_progress=raising_callback, skip_gates=True
        )
        assert result["status"] == "completed"
