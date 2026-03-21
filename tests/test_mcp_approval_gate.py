"""Tests for tools/gates/mcp_approval_gate.py.

Covers:
- run_mcp_approval_gate(phase_id, project_dir) returns GateResult with gate_type="mcp_approval"
- approve_gate returns APPROVED string -> passed=True
- approve_gate returns REJECTED string -> passed=False
- exception in approve_gate -> passed=False with issue in result
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from tools.gates.gate_result import GateResult


FAKE_PROJECT_DIR = "/tmp/fake_project"


class TestRunMcpApprovalGateApproved:
    """Tests for approve_gate returning approval."""

    def test_returns_gate_result_instance(self):
        """run_mcp_approval_gate must return a GateResult."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="APPROVED: phase 3 approved. Proceed with production deploy.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert isinstance(result, GateResult)

    def test_passed_true_when_approved(self):
        """approve_gate returning APPROVED -> passed=True."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="APPROVED: phase 3 approved.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.passed is True

    def test_status_pass_when_approved(self):
        """Approved result has status='PASS'."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="APPROVED: approved.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.status == "PASS"

    def test_confidence_1_when_approved(self):
        """Approved result has confidence=1.0."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="APPROVED: approved.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.confidence == 1.0

    def test_no_issues_when_approved(self):
        """Approved result has empty issues list."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="APPROVED: approved.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.issues == []

    def test_gate_type_is_mcp_approval(self):
        """gate_type must be 'mcp_approval'."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="APPROVED: approved.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.gate_type == "mcp_approval"

    def test_phase_id_preserved_when_approved(self):
        """phase_id is passed through to result."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="APPROVED: approved.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.phase_id == "3"

    def test_checked_at_is_populated(self):
        """checked_at must be a non-empty string."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="APPROVED: approved.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert isinstance(result.checked_at, str) and len(result.checked_at) > 0


class TestRunMcpApprovalGateRejected:
    """Tests for approve_gate returning rejection."""

    def test_passed_false_when_rejected(self):
        """approve_gate returning REJECTED -> passed=False."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="REJECTED: phase 3 rejected by user.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.passed is False

    def test_issue_present_when_rejected(self):
        """Rejected result must have at least one issue."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="REJECTED: rejected by user.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert len(result.issues) > 0

    def test_gate_type_is_mcp_approval_when_rejected(self):
        """gate_type remains 'mcp_approval' on rejection."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="REJECTED: rejected.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.gate_type == "mcp_approval"

    def test_passed_false_on_feedback_response(self):
        """FEEDBACK response (not APPROVED) -> passed=False."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(
            return_value="FEEDBACK: Please improve accessibility scores and resubmit."
        )

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.passed is False


class TestRunMcpApprovalGateException:
    """Tests for exception handling in approve_gate."""

    def test_passed_false_on_exception(self):
        """Exception in approve_gate -> passed=False."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(side_effect=RuntimeError("MCP server unavailable"))

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.passed is False

    def test_issue_present_on_exception(self):
        """Exception -> descriptive issue in result."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(side_effect=RuntimeError("Connection refused"))

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert len(result.issues) > 0

    def test_gate_type_is_mcp_approval_on_exception(self):
        """gate_type remains 'mcp_approval' on exception."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(side_effect=Exception("Unexpected error"))

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.gate_type == "mcp_approval"
