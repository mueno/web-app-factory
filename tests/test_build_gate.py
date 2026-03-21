"""Tests for tools/gates/build_gate.py."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from tools.gates.gate_result import GateResult


class TestRunBuildGatePass:
    """Tests for successful build gate execution."""

    def test_returns_gate_result_passed_true_when_both_commands_succeed(self):
        """Both npm run build and tsc --noEmit exit 0 → passed=True."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="Build succeeded\n", stderr="")

        with patch("subprocess.run", return_value=mock_success):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert isinstance(result, GateResult)
        assert result.passed is True

    def test_returns_status_pass_when_both_commands_succeed(self):
        """Passed result has status='PASS'."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert result.status == "PASS"

    def test_returns_severity_info_when_both_commands_succeed(self):
        """Passed result has severity='INFO'."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert result.severity == "INFO"

    def test_returns_confidence_1_when_both_commands_succeed(self):
        """Passed result has confidence=1.0."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert result.confidence == 1.0

    def test_gate_type_is_build(self):
        """gate_type field is 'build'."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert result.gate_type == "build"

    def test_phase_id_is_preserved(self):
        """phase_id passed to function is reflected in result."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert result.phase_id == "2a"

    def test_checked_at_is_non_empty_string(self):
        """checked_at field is populated."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert isinstance(result.checked_at, str)
        assert len(result.checked_at) > 0

    def test_no_issues_when_both_commands_succeed(self):
        """No issues in result when both commands pass."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert result.issues == []


class TestRunBuildGateNpmFail:
    """Tests for npm run build failure path."""

    def test_returns_passed_false_when_npm_build_fails(self):
        """npm run build non-zero exit → passed=False."""
        from tools.gates.build_gate import run_build_gate

        mock_fail = MagicMock(returncode=1, stdout="", stderr="Error: Build failed\n")

        with patch("subprocess.run", return_value=mock_fail):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert result.passed is False

    def test_issues_contain_npm_stderr_when_build_fails(self):
        """stderr content from npm build appears in issues."""
        from tools.gates.build_gate import run_build_gate

        mock_fail = MagicMock(returncode=1, stdout="", stderr="Error: Module not found\n")

        with patch("subprocess.run", return_value=mock_fail):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert any("Module not found" in issue for issue in result.issues)

    def test_tsc_not_called_when_npm_build_fails(self):
        """tsc is NOT called if npm run build fails (fail-fast)."""
        from tools.gates.build_gate import run_build_gate

        mock_fail = MagicMock(returncode=1, stdout="", stderr="Build error")

        with patch("subprocess.run", return_value=mock_fail) as mock_run:
            run_build_gate("/fake/project", phase_id="2a")

        # Only one subprocess.run call (for npm build) when it fails
        assert mock_run.call_count == 1

    def test_gate_type_is_build_on_npm_fail(self):
        """gate_type remains 'build' on failure."""
        from tools.gates.build_gate import run_build_gate

        mock_fail = MagicMock(returncode=1, stdout="", stderr="fail")

        with patch("subprocess.run", return_value=mock_fail):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert result.gate_type == "build"


class TestRunBuildGateTscFail:
    """Tests for tsc --noEmit failure path."""

    def test_returns_passed_false_when_tsc_fails(self):
        """tsc --noEmit non-zero exit → passed=False."""
        from tools.gates.build_gate import run_build_gate

        mock_npm_ok = MagicMock(returncode=0, stdout="Build OK", stderr="")
        mock_tsc_fail = MagicMock(returncode=1, stdout="", stderr="TS2345: Type error\n")

        with patch("subprocess.run", side_effect=[mock_npm_ok, mock_tsc_fail]):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert result.passed is False

    def test_issues_contain_tsc_stderr_when_tsc_fails(self):
        """stderr from tsc appears in issues."""
        from tools.gates.build_gate import run_build_gate

        mock_npm_ok = MagicMock(returncode=0, stdout="Build OK", stderr="")
        mock_tsc_fail = MagicMock(returncode=1, stdout="", stderr="TS2345: Argument type error\n")

        with patch("subprocess.run", side_effect=[mock_npm_ok, mock_tsc_fail]):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert any("TS2345" in issue for issue in result.issues)

    def test_two_subprocess_calls_when_npm_passes(self):
        """Both npm and tsc are called when npm succeeds."""
        from tools.gates.build_gate import run_build_gate

        mock_npm_ok = MagicMock(returncode=0, stdout="Build OK", stderr="")
        mock_tsc_fail = MagicMock(returncode=1, stdout="", stderr="TS error")

        with patch("subprocess.run", side_effect=[mock_npm_ok, mock_tsc_fail]) as mock_run:
            run_build_gate("/fake/project", phase_id="2a")

        assert mock_run.call_count == 2


class TestRunBuildGateSubprocessArgs:
    """Tests that subprocess.run is called with correct arguments."""

    def test_npm_run_build_command_used(self):
        """subprocess.run is called with ['npm', 'run', 'build']."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success) as mock_run:
            run_build_gate("/fake/project", phase_id="2a")

        first_call = mock_run.call_args_list[0]
        cmd = first_call[0][0] if first_call[0] else first_call[1].get("args", first_call[0][0])
        assert cmd == ["npm", "run", "build"]

    def test_tsc_no_emit_command_used(self):
        """subprocess.run second call uses ['npx', 'tsc', '--noEmit']."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success) as mock_run:
            run_build_gate("/fake/project", phase_id="2a")

        second_call = mock_run.call_args_list[1]
        cmd = second_call[0][0] if second_call[0] else second_call[1].get("args", second_call[0][0])
        assert cmd == ["npx", "tsc", "--noEmit"]

    def test_next_telemetry_disabled_in_npm_env(self):
        """NEXT_TELEMETRY_DISABLED=1 is passed in env for npm run build."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success) as mock_run:
            run_build_gate("/fake/project", phase_id="2a")

        first_call = mock_run.call_args_list[0]
        kwargs = first_call[1] if first_call[1] else {}
        env = kwargs.get("env", {})
        assert env.get("NEXT_TELEMETRY_DISABLED") == "1"

    def test_timeout_120_for_npm_build(self):
        """timeout=120 is used for npm run build."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success) as mock_run:
            run_build_gate("/fake/project", phase_id="2a")

        first_call = mock_run.call_args_list[0]
        kwargs = first_call[1] if first_call[1] else {}
        assert kwargs.get("timeout") == 120

    def test_timeout_120_for_tsc(self):
        """timeout=120 is used for tsc --noEmit."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success) as mock_run:
            run_build_gate("/fake/project", phase_id="2a")

        second_call = mock_run.call_args_list[1]
        kwargs = second_call[1] if second_call[1] else {}
        assert kwargs.get("timeout") == 120

    def test_capture_output_true_for_npm_build(self):
        """capture_output=True is used for npm run build."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success) as mock_run:
            run_build_gate("/fake/project", phase_id="2a")

        first_call = mock_run.call_args_list[0]
        kwargs = first_call[1] if first_call[1] else {}
        assert kwargs.get("capture_output") is True

    def test_text_true_for_npm_build(self):
        """text=True is used for npm run build."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success) as mock_run:
            run_build_gate("/fake/project", phase_id="2a")

        first_call = mock_run.call_args_list[0]
        kwargs = first_call[1] if first_call[1] else {}
        assert kwargs.get("text") is True

    def test_cwd_set_to_project_dir(self):
        """cwd is set to project_dir for npm run build."""
        from tools.gates.build_gate import run_build_gate

        mock_success = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_success) as mock_run:
            run_build_gate("/fake/project", phase_id="2a")

        first_call = mock_run.call_args_list[0]
        kwargs = first_call[1] if first_call[1] else {}
        assert kwargs.get("cwd") == "/fake/project"


class TestRunBuildGateTimeout:
    """Tests for subprocess.TimeoutExpired handling."""

    def test_timeout_on_npm_build_returns_passed_false(self):
        """subprocess.TimeoutExpired during npm build → passed=False."""
        from tools.gates.build_gate import run_build_gate

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["npm", "run", "build"], timeout=120),
        ):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert result.passed is False

    def test_timeout_on_npm_build_has_timeout_message_in_issues(self):
        """Timeout produces descriptive message in issues."""
        from tools.gates.build_gate import run_build_gate

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["npm", "run", "build"], timeout=120),
        ):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert any("timeout" in issue.lower() for issue in result.issues)

    def test_timeout_on_tsc_returns_passed_false(self):
        """subprocess.TimeoutExpired during tsc → passed=False."""
        from tools.gates.build_gate import run_build_gate

        mock_npm_ok = MagicMock(returncode=0, stdout="Build OK", stderr="")

        with patch(
            "subprocess.run",
            side_effect=[
                mock_npm_ok,
                subprocess.TimeoutExpired(cmd=["npx", "tsc", "--noEmit"], timeout=120),
            ],
        ):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert result.passed is False

    def test_timeout_on_tsc_has_timeout_message_in_issues(self):
        """Timeout on tsc produces descriptive message in issues."""
        from tools.gates.build_gate import run_build_gate

        mock_npm_ok = MagicMock(returncode=0, stdout="Build OK", stderr="")

        with patch(
            "subprocess.run",
            side_effect=[
                mock_npm_ok,
                subprocess.TimeoutExpired(cmd=["npx", "tsc", "--noEmit"], timeout=120),
            ],
        ):
            result = run_build_gate("/fake/project", phase_id="2a")

        assert any("timeout" in issue.lower() for issue in result.issues)
