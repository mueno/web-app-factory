"""Tests for tools/gates/mcp_approval_gate.py.

Covers:
- run_mcp_approval_gate(phase_id, project_dir) returns GateResult with gate_type="mcp_approval"
- approve_gate returns APPROVED string -> passed=True
- approve_gate returns REJECTED string -> passed=False
- exception in approve_gate -> passed=False with issue in result
- _poll_mcp_gate_file: approve/reject/timeout/invalid-JSON/missing-run-id
- TestInteractiveModeRouting: interactive=True delegates to _poll_mcp_gate_file
- TestGateResponsesPathConsistency: GATE_RESPONSES_DIR matches waf_approve_gate writer path
"""

from __future__ import annotations

import json
import time
from pathlib import Path
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


# ──────────────────────────────────────────────────────────────────────────────
# New tests for Phase 14-01: interactive polling via _poll_mcp_gate_file
# ──────────────────────────────────────────────────────────────────────────────


class TestPollMcpGateFile:
    """Unit tests for _poll_mcp_gate_file file-based polling logic."""

    def test_approve_returns_passed_true(self, tmp_path: Path):
        """Gate file with decision='approve' -> passed=True, status='PASS'."""
        from tools.gates.mcp_approval_gate import _poll_mcp_gate_file

        gate_file = tmp_path / "run-abc.json"
        gate_file.write_text(
            json.dumps({"run_id": "run-abc", "decision": "approve", "feedback": ""}),
            encoding="utf-8",
        )

        with patch("tools.gates.mcp_approval_gate.GATE_RESPONSES_DIR", tmp_path):
            result = _poll_mcp_gate_file("3", "run-abc")

        assert result.passed is True
        assert result.status == "PASS"

    def test_reject_returns_passed_false(self, tmp_path: Path):
        """Gate file with decision='reject' -> passed=False with feedback in issues."""
        from tools.gates.mcp_approval_gate import _poll_mcp_gate_file

        gate_file = tmp_path / "run-xyz.json"
        gate_file.write_text(
            json.dumps(
                {"run_id": "run-xyz", "decision": "reject", "feedback": "Needs work"}
            ),
            encoding="utf-8",
        )

        with patch("tools.gates.mcp_approval_gate.GATE_RESPONSES_DIR", tmp_path):
            result = _poll_mcp_gate_file("3", "run-xyz")

        assert result.passed is False
        assert any("Needs work" in issue for issue in result.issues)

    def test_gate_file_deleted_after_consume(self, tmp_path: Path):
        """Gate file is removed after being read (no double-read)."""
        from tools.gates.mcp_approval_gate import _poll_mcp_gate_file

        gate_file = tmp_path / "run-del.json"
        gate_file.write_text(
            json.dumps({"run_id": "run-del", "decision": "approve", "feedback": ""}),
            encoding="utf-8",
        )

        with patch("tools.gates.mcp_approval_gate.GATE_RESPONSES_DIR", tmp_path):
            _poll_mcp_gate_file("3", "run-del")

        assert not gate_file.exists(), "Gate file should be deleted after consumption"

    def test_timeout_returns_blocked(self, tmp_path: Path):
        """_poll_mcp_gate_file times out when no gate file appears."""
        from tools.gates.mcp_approval_gate import _poll_mcp_gate_file

        with patch("tools.gates.mcp_approval_gate.GATE_RESPONSES_DIR", tmp_path):
            result = _poll_mcp_gate_file(
                "3", "run-timeout", poll_interval=0.05, timeout_seconds=0.1
            )

        assert result.passed is False
        assert result.status == "BLOCKED"
        assert any("timeout" in issue.lower() or "Timeout" in issue for issue in result.issues)

    def test_invalid_json_continues_polling_then_times_out(self, tmp_path: Path):
        """Invalid JSON in gate file does not crash — polling continues until timeout."""
        from tools.gates.mcp_approval_gate import _poll_mcp_gate_file

        gate_file = tmp_path / "run-badjson.json"
        gate_file.write_text("not valid json", encoding="utf-8")

        with patch("tools.gates.mcp_approval_gate.GATE_RESPONSES_DIR", tmp_path):
            result = _poll_mcp_gate_file(
                "3", "run-badjson", poll_interval=0.05, timeout_seconds=0.2
            )

        # Should time out, not crash
        assert result.passed is False
        assert result.status == "BLOCKED"

    def test_approve_gate_type_is_mcp_approval(self, tmp_path: Path):
        """Approved poll result has gate_type='mcp_approval'."""
        from tools.gates.mcp_approval_gate import _poll_mcp_gate_file

        gate_file = tmp_path / "run-gtype.json"
        gate_file.write_text(
            json.dumps({"run_id": "run-gtype", "decision": "approve", "feedback": ""}),
            encoding="utf-8",
        )

        with patch("tools.gates.mcp_approval_gate.GATE_RESPONSES_DIR", tmp_path):
            result = _poll_mcp_gate_file("3", "run-gtype")

        assert result.gate_type == "mcp_approval"

    def test_phase_id_preserved_on_approve(self, tmp_path: Path):
        """phase_id is propagated correctly into the poll result."""
        from tools.gates.mcp_approval_gate import _poll_mcp_gate_file

        gate_file = tmp_path / "run-ph.json"
        gate_file.write_text(
            json.dumps({"run_id": "run-ph", "decision": "approve", "feedback": ""}),
            encoding="utf-8",
        )

        with patch("tools.gates.mcp_approval_gate.GATE_RESPONSES_DIR", tmp_path):
            result = _poll_mcp_gate_file("5", "run-ph")

        assert result.phase_id == "5"


class TestInteractiveModeRouting:
    """Verify that run_mcp_approval_gate routes correctly for interactive mode."""

    def test_interactive_true_with_run_id_delegates_to_poll(self, tmp_path: Path):
        """interactive=True with valid run_id calls _poll_mcp_gate_file."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        expected_result = GateResult(
            gate_type="mcp_approval",
            phase_id="3",
            passed=True,
            status="PASS",
            severity="INFO",
            confidence=1.0,
            checked_at="2026-01-01T00:00:00+00:00",
        )

        with patch(
            "tools.gates.mcp_approval_gate._poll_mcp_gate_file",
            return_value=expected_result,
        ) as mock_poll:
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR, interactive=True, run_id="run-123")

        mock_poll.assert_called_once_with("3", "run-123")
        assert result.passed is True

    def test_interactive_true_with_empty_run_id_returns_error(self):
        """interactive=True with empty run_id returns passed=False with descriptive error."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR, interactive=True, run_id="")

        assert result.passed is False
        assert result.status == "BLOCKED"
        assert any("run_id" in issue.lower() for issue in result.issues)

    def test_interactive_false_uses_legacy_path(self):
        """interactive=False (default) falls through to legacy approve_gate path."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="APPROVED: legacy path works.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert result.passed is True

    def test_existing_signature_unchanged(self):
        """Existing positional call run_mcp_approval_gate('3', dir) still works."""
        from tools.gates.mcp_approval_gate import run_mcp_approval_gate

        mock_coroutine = AsyncMock(return_value="APPROVED: backward compat.")

        with patch("tools.gates.mcp_approval_gate.approve_gate", mock_coroutine):
            result = run_mcp_approval_gate("3", FAKE_PROJECT_DIR)

        assert isinstance(result, GateResult)


class TestGateResponsesPathConsistency:
    """Verify that writer (waf_approve_gate) and reader (mcp_approval_gate) share the same path."""

    def test_gate_responses_dir_in_settings(self):
        """GATE_RESPONSES_DIR is exported from config.settings."""
        from config.settings import GATE_RESPONSES_DIR

        assert GATE_RESPONSES_DIR is not None

    def test_gate_responses_dir_matches_expected_default(self):
        """Default GATE_RESPONSES_DIR equals PROJECT_ROOT/output/.gate-responses."""
        from config.settings import GATE_RESPONSES_DIR, PROJECT_ROOT

        expected = PROJECT_ROOT / "output" / ".gate-responses"
        assert GATE_RESPONSES_DIR == expected

    def test_gate_responses_dir_imported_by_mcp_approval_gate(self):
        """mcp_approval_gate module can import GATE_RESPONSES_DIR from config.settings."""
        from tools.gates.mcp_approval_gate import GATE_RESPONSES_DIR as reader_dir
        from config.settings import GATE_RESPONSES_DIR as settings_dir

        assert reader_dir == settings_dir

    def test_gate_responses_dir_is_env_overridable(self, monkeypatch, tmp_path):
        """GATE_RESPONSES_DIR can be overridden via WEB_FACTORY_GATE_RESPONSES_DIR env var."""
        import importlib
        import config.settings as settings_module

        monkeypatch.setenv("WEB_FACTORY_GATE_RESPONSES_DIR", str(tmp_path))
        importlib.reload(settings_module)

        try:
            assert settings_module.GATE_RESPONSES_DIR == tmp_path
        finally:
            # Reload to restore original state
            monkeypatch.delenv("WEB_FACTORY_GATE_RESPONSES_DIR", raising=False)
            importlib.reload(settings_module)
