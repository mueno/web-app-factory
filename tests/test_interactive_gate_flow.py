"""Integration test: full interactive gate approve/reject flow.

Tests the END-TO-END path from run_pipeline() through _run_gate_checks()
through _poll_mcp_gate_file() to file consumption — WITHOUT mocking the
gate module itself.

What IS mocked:
- Phase executors (return success immediately)
- pipeline_state functions (no-op — we don't need real state files)
- Quality self-assessment (no-op — not under test)
- GATE_RESPONSES_DIR (patched to tmp_path so each test uses a fresh dir)

What is NOT mocked:
- _poll_mcp_gate_file (real file polling)
- run_mcp_approval_gate routing (real interactive path)
- _run_gate_checks dispatch (real mcp_approval branch)
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Minimal contract: one phase with a single mcp_approval gate
INTERACTIVE_CONTRACT = {
    "version": "1.0",
    "name": "test-interactive",
    "phases": [
        {
            "id": "1a",
            "name": "test-phase",
            "deliverables": [],
            "gates": [{"type": "mcp_approval", "conditions": {}}],
        }
    ],
}


def _make_stub_executor_class(phase_id: str):
    """Return a PhaseExecutor subclass stub that succeeds immediately."""
    from tools.phase_executors.base import PhaseExecutor, PhaseContext, PhaseResult

    class StubExecutor(PhaseExecutor):
        @property
        def phase_id(self) -> str:
            return phase_id

        @property
        def sub_steps(self) -> list:
            return []

        def execute(self, ctx: PhaseContext) -> PhaseResult:
            return PhaseResult(phase_id=phase_id, success=True)

    return StubExecutor()


def _write_gate_file_after_delay(
    gate_dir: Path,
    run_id: str,
    decision: str,
    delay: float = 0.3,
    feedback: str = "",
) -> threading.Thread:
    """Start a background thread that writes a gate-response file after `delay` seconds.

    Returns the thread (already started).
    """
    def _writer():
        time.sleep(delay)
        gate_dir.mkdir(parents=True, exist_ok=True)
        gate_file = gate_dir / f"{run_id}.json"
        gate_file.write_text(
            json.dumps({"run_id": run_id, "decision": decision, "feedback": feedback}),
            encoding="utf-8",
        )

    t = threading.Thread(target=_writer, daemon=True)
    t.start()
    return t


class TestInteractiveGateFlow:
    """End-to-end tests: bridge -> runner -> _poll_mcp_gate_file -> file -> resume."""

    def _setup(self):
        """Import run_pipeline (triggers module-level executor registrations) THEN clear registry."""
        from tools.contract_pipeline_runner import run_pipeline  # noqa: F401
        from tools.phase_executors.registry import _clear_registry, register
        _clear_registry()
        return run_pipeline, register

    def _no_op_pipeline_state_patches(self):
        """Return a list of context managers that no-op all pipeline_state calls."""
        return [
            patch("tools.contract_pipeline_runner.init_run", return_value=MagicMock(
                run_id="test-run-integration-01", phases={}
            )),
            patch("tools.contract_pipeline_runner.phase_start"),
            patch("tools.contract_pipeline_runner.phase_complete"),
            patch("tools.contract_pipeline_runner.mark_failed"),
            patch("tools.contract_pipeline_runner.mark_completed"),
            patch("tools.contract_pipeline_runner.generate_quality_self_assessment"),
        ]

    def test_approve_flow_completes_pipeline(self, tmp_path):
        """Approve file written while pipeline polls -> pipeline completes with status='completed'.

        Flow:
        1. run_pipeline starts with interactive_mode=True
        2. Phase 1a executes (stub executor: immediate success)
        3. _run_gate_checks encounters mcp_approval gate
        4. gate_waiting event emitted
        5. _poll_mcp_gate_file starts polling (poll_interval=0.1s for speed)
        6. Background thread writes {run_id}.json with decision='approve' after 0.3s
        7. _poll_mcp_gate_file reads file, returns GateResult(passed=True)
        8. run_pipeline returns {"status": "completed"}
        """
        run_pipeline, register = self._setup()
        register(_make_stub_executor_class("1a"))

        gate_dir = tmp_path / ".gate-responses"
        run_id_holder: list[str] = []

        # We need to know the run_id before writing the file.
        # We intercept init_run to capture run_id, then also patch GATE_RESPONSES_DIR.
        mock_state = MagicMock()
        mock_state.run_id = "test-interactive-approve"
        mock_state.phases = {}

        # Patch GATE_RESPONSES_DIR in both modules that reference it
        patches = [
            patch("tools.contract_pipeline_runner.init_run", return_value=mock_state),
            patch("tools.contract_pipeline_runner.phase_start"),
            patch("tools.contract_pipeline_runner.phase_complete"),
            patch("tools.contract_pipeline_runner.mark_failed"),
            patch("tools.contract_pipeline_runner.mark_completed"),
            patch("tools.contract_pipeline_runner.generate_quality_self_assessment"),
            patch("tools.gates.mcp_approval_gate.GATE_RESPONSES_DIR", gate_dir),
            patch("tools.gates.mcp_approval_gate._poll_mcp_gate_file",
                  wraps=_wrap_poll_with_fast_interval(gate_dir)),
        ]

        run_id = mock_state.run_id

        # Start background thread that writes the approve file
        writer_thread = _write_gate_file_after_delay(
            gate_dir, run_id, "approve", delay=0.3
        )

        # Apply all patches and run pipeline
        ctx_managers = [p.__enter__() for p in patches]
        try:
            result = run_pipeline(
                contract=INTERACTIVE_CONTRACT,
                project_dir=str(tmp_path),
                idea="approve flow test",
                interactive_mode=True,
            )
        finally:
            for i, p in enumerate(reversed(patches)):
                p.__exit__(None, None, None)

        writer_thread.join(timeout=5.0)
        assert result["status"] == "completed", (
            f"Expected status='completed' after approve, got {result!r}"
        )

    def test_reject_flow_fails_pipeline(self, tmp_path):
        """Reject file written while pipeline polls -> pipeline fails with status='failed'."""
        run_pipeline, register = self._setup()
        register(_make_stub_executor_class("1a"))

        gate_dir = tmp_path / ".gate-responses"
        mock_state = MagicMock()
        mock_state.run_id = "test-interactive-reject"
        mock_state.phases = {}

        patches = [
            patch("tools.contract_pipeline_runner.init_run", return_value=mock_state),
            patch("tools.contract_pipeline_runner.phase_start"),
            patch("tools.contract_pipeline_runner.phase_complete"),
            patch("tools.contract_pipeline_runner.mark_failed"),
            patch("tools.contract_pipeline_runner.mark_completed"),
            patch("tools.contract_pipeline_runner.generate_quality_self_assessment"),
            patch("tools.gates.mcp_approval_gate.GATE_RESPONSES_DIR", gate_dir),
            patch("tools.gates.mcp_approval_gate._poll_mcp_gate_file",
                  wraps=_wrap_poll_with_fast_interval(gate_dir)),
        ]

        run_id = mock_state.run_id
        writer_thread = _write_gate_file_after_delay(
            gate_dir, run_id, "reject", delay=0.3, feedback="Not ready for production"
        )

        ctx_managers = [p.__enter__() for p in patches]
        try:
            result = run_pipeline(
                contract=INTERACTIVE_CONTRACT,
                project_dir=str(tmp_path),
                idea="reject flow test",
                interactive_mode=True,
            )
        finally:
            for i, p in enumerate(reversed(patches)):
                p.__exit__(None, None, None)

        writer_thread.join(timeout=5.0)
        assert result["status"] == "failed", (
            f"Expected status='failed' after reject, got {result!r}"
        )
        assert "gate_issues" in result, (
            f"Expected 'gate_issues' in result: {result!r}"
        )

    def test_auto_mode_does_not_read_gate_files(self, tmp_path):
        """Pipeline with interactive_mode=False (auto) does NOT use file polling.

        The legacy approve_gate path is used instead. Gate files are not written
        or read. The pipeline completes without any gate file in the gate dir.
        """
        run_pipeline, register = self._setup()
        register(_make_stub_executor_class("1a"))

        gate_dir = tmp_path / ".gate-responses"
        mock_state = MagicMock()
        mock_state.run_id = "test-auto-mode"
        mock_state.phases = {}

        # Mock the legacy approve_gate path to return approval
        from unittest.mock import AsyncMock

        patches = [
            patch("tools.contract_pipeline_runner.init_run", return_value=mock_state),
            patch("tools.contract_pipeline_runner.phase_start"),
            patch("tools.contract_pipeline_runner.phase_complete"),
            patch("tools.contract_pipeline_runner.mark_failed"),
            patch("tools.contract_pipeline_runner.mark_completed"),
            patch("tools.contract_pipeline_runner.generate_quality_self_assessment"),
            patch("tools.gates.mcp_approval_gate.GATE_RESPONSES_DIR", gate_dir),
            patch(
                "tools.gates.mcp_approval_gate.approve_gate",
                new=AsyncMock(return_value="APPROVED: auto approval"),
            ),
        ]

        ctx_managers = [p.__enter__() for p in patches]
        try:
            result = run_pipeline(
                contract=INTERACTIVE_CONTRACT,
                project_dir=str(tmp_path),
                idea="auto mode test",
                # interactive_mode omitted -> defaults to False -> legacy path
            )
        finally:
            for i, p in enumerate(reversed(patches)):
                p.__exit__(None, None, None)

        # Auto mode should complete (legacy approve_gate returns APPROVED)
        assert result["status"] == "completed", (
            f"Expected status='completed' for auto mode, got {result!r}"
        )
        # No gate file should be in the gate dir
        if gate_dir.exists():
            gate_files = list(gate_dir.glob("*.json"))
            assert len(gate_files) == 0, (
                f"Auto mode should not create gate files, found: {gate_files!r}"
            )


def _wrap_poll_with_fast_interval(gate_dir: Path):
    """Return a wrapper for _poll_mcp_gate_file that uses fast poll_interval=0.1s."""
    from tools.gates.mcp_approval_gate import _poll_mcp_gate_file

    def wrapper(phase_id: str, run_id: str, **kwargs):
        # Override to fast poll_interval and short timeout (5s max for tests)
        return _poll_mcp_gate_file(
            phase_id,
            run_id,
            poll_interval=0.1,
            timeout_seconds=5.0,
        )

    return wrapper
