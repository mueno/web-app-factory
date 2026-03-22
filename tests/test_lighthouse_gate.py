"""Tests for tools/gates/lighthouse_gate.py."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch, call

import pytest

from tools.gates.gate_result import GateResult


def _make_lighthouse_json(perf: float, a11y: float, seo: float) -> str:
    """Build a minimal Lighthouse JSON output string with given scores (0.0-1.0)."""
    return json.dumps(
        {
            "categories": {
                "performance": {"score": perf},
                "accessibility": {"score": a11y},
                "seo": {"score": seo},
            }
        }
    )


def _mock_successful_subprocess(perf: float, a11y: float, seo: float):
    """Return a mock CompletedProcess that writes Lighthouse JSON to the output path."""
    lh_json = _make_lighthouse_json(perf, a11y, seo)

    def side_effect(cmd, *args, **kwargs):
        # Find the --output-path argument and write the JSON there
        for arg in cmd:
            if arg.startswith("--output-path="):
                path = arg.split("=", 1)[1]
                with open(path, "w") as f:
                    f.write(lh_json)
                break
        return MagicMock(returncode=0, stdout="", stderr="")

    return side_effect


class TestLighthouseGatePass:
    """Tests where all scores pass their thresholds."""

    def test_all_scores_above_threshold_pass(self):
        """Scores 90/95/90 with defaults thresholds (85/90/85) -> passed=True."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert isinstance(result, GateResult)
        assert result.passed is True

    def test_pass_result_has_status_pass(self):
        """Passing gate returns status='PASS'."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert result.status == "PASS"

    def test_pass_result_has_severity_info(self):
        """Passing gate returns severity='INFO'."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert result.severity == "INFO"

    def test_pass_result_has_no_issues(self):
        """No issues when all scores pass."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert result.issues == []

    def test_gate_type_is_lighthouse(self):
        """gate_type field is 'lighthouse'."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert result.gate_type == "lighthouse"

    def test_phase_id_preserved(self):
        """phase_id passed to function appears in result."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com", phase_id="3")

        assert result.phase_id == "3"


class TestLighthouseGateFail:
    """Tests where one or more scores fail their thresholds."""

    def test_performance_below_threshold_fail(self):
        """Performance 50 with threshold 70 -> passed=False."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.50, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert result.passed is False

    def test_performance_below_threshold_has_issue(self):
        """Performance failure produces an issue mentioning 'performance'."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.50, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert any("performance" in issue.lower() for issue in result.issues)

    def test_all_below_threshold_fail_three_issues(self):
        """All 3 categories below threshold -> 3 issues."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.50, 0.50, 0.50)):
            result = run_lighthouse_gate("https://example.com")

        assert result.passed is False
        assert len(result.issues) == 3

    def test_fail_result_has_status_blocked(self):
        """Failing gate returns status='BLOCKED'."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.50, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert result.status == "BLOCKED"

    def test_fail_result_has_severity_block(self):
        """Failing gate returns severity='BLOCK'."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.50, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert result.severity == "BLOCK"


class TestLighthouseGateCustomThresholds:
    """Tests with custom threshold values."""

    def test_custom_thresholds_pass(self):
        """Custom threshold {'performance': 50} with score 60 -> pass."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.60, 0.95, 0.90)):
            result = run_lighthouse_gate(
                "https://example.com",
                thresholds={"performance": 50, "accessibility": 90, "seo": 85},
            )

        assert result.passed is True

    def test_custom_high_threshold_fail(self):
        """Score 90 fails if threshold is 95."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)):
            result = run_lighthouse_gate(
                "https://example.com",
                thresholds={"performance": 95, "accessibility": 90, "seo": 85},
            )

        assert result.passed is False

    def test_default_thresholds_are_70_90_85(self):
        """Default thresholds are performance=70, accessibility=90, seo=85."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        # Score exactly at threshold should pass
        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.70, 0.90, 0.85)):
            result = run_lighthouse_gate("https://example.com")

        assert result.passed is True


class TestLighthouseGateTolerance:
    """Tests for score tolerance (advisory instead of hard block)."""

    def test_score_within_tolerance_passes(self):
        """Score 69 with threshold 70 and tolerance 2 -> passed=True (advisory)."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        # 69 is within 2 points of 70 -> should pass with advisory
        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.69, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert result.passed is True
        assert len(result.advisories) > 0
        assert any("tolerance" in a.lower() for a in result.advisories)

    def test_score_below_tolerance_fails(self):
        """Score 65 with threshold 70 and tolerance 2 -> passed=False (hard block)."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        # 65 is 5 points below 70 -> exceeds tolerance -> hard block
        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.65, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert result.passed is False
        assert any("below threshold" in issue for issue in result.issues)

    def test_score_at_threshold_passes_no_advisory(self):
        """Score exactly at threshold -> passed=True, no advisory."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.70, 0.90, 0.85)):
            result = run_lighthouse_gate("https://example.com")

        assert result.passed is True
        assert result.advisories == []

    def test_tolerance_stored_in_extra(self):
        """tolerance value is stored in extra for auditability."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.83, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert "tolerance" in result.extra


class TestLighthouseGateExtra:
    """Tests for extra data stored in GateResult."""

    def test_scores_stored_in_extra(self):
        """actual scores are stored in extra['scores']."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.88)):
            result = run_lighthouse_gate("https://example.com")

        assert "scores" in result.extra
        scores = result.extra["scores"]
        assert "performance" in scores
        assert "accessibility" in scores
        assert "seo" in scores

    def test_scores_are_percentages(self):
        """Scores stored in extra are multiplied to percentage values."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.88)):
            result = run_lighthouse_gate("https://example.com")

        scores = result.extra["scores"]
        assert scores["performance"] == pytest.approx(90.0)
        assert scores["accessibility"] == pytest.approx(95.0)
        assert scores["seo"] == pytest.approx(88.0)


class TestLighthouseGateSubprocessArgs:
    """Tests that subprocess.run is called with correct arguments."""

    def test_runs_flag_present(self):
        """--runs=3 appears in the subprocess command."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)) as mock_run:
            run_lighthouse_gate("https://example.com")

        call_args = mock_run.call_args_list[0]
        cmd = call_args[0][0]
        assert "--runs=3" in cmd

    def test_headless_chrome_flags_present(self):
        """--headless --no-sandbox chrome flags appear in subprocess command."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)) as mock_run:
            run_lighthouse_gate("https://example.com")

        call_args = mock_run.call_args_list[0]
        cmd = call_args[0][0]
        chrome_flag_arg = " ".join(cmd)
        assert "--headless" in chrome_flag_arg

    def test_output_json_flag_present(self):
        """--output=json appears in subprocess command."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)) as mock_run:
            run_lighthouse_gate("https://example.com")

        call_args = mock_run.call_args_list[0]
        cmd = call_args[0][0]
        assert "--output=json" in cmd

    def test_url_appears_in_command(self):
        """The URL is passed to the subprocess command."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        test_url = "https://myapp.vercel.app"
        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)) as mock_run:
            run_lighthouse_gate(test_url)

        call_args = mock_run.call_args_list[0]
        cmd = call_args[0][0]
        assert test_url in cmd


class TestLighthouseGateErrors:
    """Tests for error conditions."""

    def test_subprocess_timeout_returns_passed_false(self):
        """TimeoutExpired -> passed=False."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["npx", "lighthouse"], timeout=180),
        ):
            result = run_lighthouse_gate("https://example.com")

        assert result.passed is False

    def test_subprocess_timeout_has_issue(self):
        """TimeoutExpired -> issues list is non-empty."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["npx", "lighthouse"], timeout=180),
        ):
            result = run_lighthouse_gate("https://example.com")

        assert len(result.issues) > 0
        assert any("timeout" in issue.lower() for issue in result.issues)

    def test_subprocess_nonzero_exit_returns_passed_false(self):
        """Non-zero returncode -> passed=False."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="Error")):
            result = run_lighthouse_gate("https://example.com")

        assert result.passed is False

    def test_subprocess_nonzero_exit_has_issue(self):
        """Non-zero returncode -> issues list is non-empty."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="Error output")):
            result = run_lighthouse_gate("https://example.com")

        assert len(result.issues) > 0

    def test_checked_at_is_populated(self):
        """checked_at field is non-empty on success."""
        from tools.gates.lighthouse_gate import run_lighthouse_gate

        with patch("subprocess.run", side_effect=_mock_successful_subprocess(0.90, 0.95, 0.90)):
            result = run_lighthouse_gate("https://example.com")

        assert isinstance(result.checked_at, str)
        assert len(result.checked_at) > 0
