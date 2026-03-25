"""Tests for backend_spec gate dispatch in contract_pipeline_runner._run_gate_checks.

Covers:
- _run_gate_checks handles gate_type "backend_spec" by calling run_backend_spec_gate
- backend_spec gate receives nextjs_dir when provided (same pattern as build/static_analysis)
- backend_spec gate failures are added to issues list
- Unknown gate types still fail-closed (regression check)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_contract_phase(gate_type: str, *, phase_id: str = "2b") -> dict:
    """Minimal contract phase dict with one gate."""
    return {
        "id": phase_id,
        "name": f"Phase {phase_id}",
        "gates": [
            {"type": gate_type, "conditions": {}},
        ],
    }


def _make_passed_gate_result() -> "GateResult":
    """Create a GateResult that represents a passing gate."""
    from tools.gates.gate_result import GateResult
    return GateResult(
        gate_type="backend_spec",
        phase_id="2b",
        passed=True,
        status="PASS",
        severity="INFO",
        confidence=1.0,
        checked_at="2026-01-01T00:00:00+00:00",
        issues=[],
        advisories=[],
    )


def _make_failed_gate_result(issues: list[str]) -> "GateResult":
    """Create a GateResult that represents a failing gate."""
    from tools.gates.gate_result import GateResult
    return GateResult(
        gate_type="backend_spec",
        phase_id="2b",
        passed=False,
        status="BLOCKED",
        severity="BLOCK",
        confidence=0.0,
        checked_at="2026-01-01T00:00:00+00:00",
        issues=issues,
        advisories=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBackendSpecGateDispatch:
    """_run_gate_checks dispatches 'backend_spec' type to run_backend_spec_gate."""

    def test_backend_spec_gate_dispatched(self, tmp_path):
        """_run_gate_checks calls run_backend_spec_gate when gate_type='backend_spec'."""
        from tools.contract_pipeline_runner import _run_gate_checks

        contract_phase = _make_contract_phase("backend_spec")
        mock_gate_result = _make_passed_gate_result()

        with patch(
            "tools.gates.backend_spec_gate.run_backend_spec_gate",
            return_value=mock_gate_result,
        ) as mock_gate:
            passed, issues = _run_gate_checks(
                contract_phase, str(tmp_path)
            )

        assert mock_gate.called
        assert passed is True
        assert issues == []

    def test_backend_spec_gate_uses_nextjs_dir(self, tmp_path):
        """backend_spec gate receives nextjs_dir when provided (same as build gate pattern)."""
        from tools.contract_pipeline_runner import _run_gate_checks

        contract_phase = _make_contract_phase("backend_spec")
        mock_gate_result = _make_passed_gate_result()
        nextjs_dir = str(tmp_path / "myapp")

        with patch(
            "tools.gates.backend_spec_gate.run_backend_spec_gate",
            return_value=mock_gate_result,
        ) as mock_gate:
            passed, issues = _run_gate_checks(
                contract_phase, str(tmp_path), nextjs_dir=nextjs_dir
            )

        # Verify run_backend_spec_gate was called with nextjs_dir as project_dir
        mock_gate.assert_called_once()
        call_args = mock_gate.call_args
        first_positional_arg = call_args[0][0] if call_args[0] else call_args[1].get("project_dir")
        assert first_positional_arg == nextjs_dir

    def test_backend_spec_gate_uses_project_dir_when_no_nextjs_dir(self, tmp_path):
        """backend_spec gate uses project_dir as fallback when nextjs_dir is None."""
        from tools.contract_pipeline_runner import _run_gate_checks

        contract_phase = _make_contract_phase("backend_spec")
        mock_gate_result = _make_passed_gate_result()

        with patch(
            "tools.gates.backend_spec_gate.run_backend_spec_gate",
            return_value=mock_gate_result,
        ) as mock_gate:
            passed, issues = _run_gate_checks(
                contract_phase, str(tmp_path), nextjs_dir=None
            )

        mock_gate.assert_called_once()
        call_args = mock_gate.call_args
        first_positional_arg = call_args[0][0] if call_args[0] else call_args[1].get("project_dir")
        assert first_positional_arg == str(tmp_path)

    def test_backend_spec_gate_failures_block(self, tmp_path):
        """GateResult(passed=False) from backend_spec gate causes _run_gate_checks to return issues."""
        from tools.contract_pipeline_runner import _run_gate_checks

        contract_phase = _make_contract_phase("backend_spec")
        failure_issues = [
            "src/app/api/todos/route.ts: missing Zod import",
            "src/app/api/health/route.ts is missing",
        ]
        mock_gate_result = _make_failed_gate_result(failure_issues)

        with patch(
            "tools.gates.backend_spec_gate.run_backend_spec_gate",
            return_value=mock_gate_result,
        ):
            passed, issues = _run_gate_checks(
                contract_phase, str(tmp_path)
            )

        assert passed is False
        assert issues == failure_issues

    def test_backend_spec_gate_failure_issues_added_to_list(self, tmp_path):
        """Issues from a failed backend_spec gate are added to the issues list."""
        from tools.contract_pipeline_runner import _run_gate_checks

        contract_phase = _make_contract_phase("backend_spec")
        failure_issues = ["route.ts: missing Zod import"]
        mock_gate_result = _make_failed_gate_result(failure_issues)

        with patch(
            "tools.gates.backend_spec_gate.run_backend_spec_gate",
            return_value=mock_gate_result,
        ):
            passed, issues = _run_gate_checks(
                contract_phase, str(tmp_path)
            )

        assert "route.ts: missing Zod import" in issues


class TestUnknownGateTypeRegressionCheck:
    """Unknown gate types must still fail-closed (regression guard)."""

    def test_unknown_gate_type_fails_closed(self, tmp_path):
        """An unknown gate type returns passed=False with a descriptive issue."""
        from tools.contract_pipeline_runner import _run_gate_checks

        contract_phase = _make_contract_phase("totally_unknown_gate_type_xyz")

        passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is False
        assert len(issues) > 0
        # Issue should mention the unknown gate type
        combined = " ".join(issues)
        assert "totally_unknown_gate_type_xyz" in combined or "Unknown gate type" in combined
