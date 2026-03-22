"""Tests for tools/gates/accessibility_gate.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from tools.gates.gate_result import GateResult


def _make_violation(impact: str, description: str = "Some violation") -> dict:
    """Build a minimal axe violation dict."""
    return {
        "id": f"violation-{impact}",
        "impact": impact,
        "description": description,
        "help": f"Help text for {description}",
    }


def _make_axe_result(violations: list) -> MagicMock:
    """Build a mock axe result with the given violations.

    The real axe-playwright-python result stores violations at
    ``result.response["violations"]``, so we mock ``response`` as a
    dict-like object.
    """
    mock_result = MagicMock()
    mock_result.response = {"violations": violations}
    return mock_result


class TestAccessibilityGatePass:
    """Tests where accessibility gate passes."""

    def test_zero_critical_pass(self):
        """No critical violations -> passed=True."""
        from tools.gates.accessibility_gate import run_accessibility_gate

        axe_result = _make_axe_result([])

        with patch("tools.gates.accessibility_gate.sync_playwright") as mock_pw_ctx:
            mock_page = MagicMock()
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.chromium.launch.return_value = mock_browser
            mock_pw_ctx.return_value = mock_context

            with patch("tools.gates.accessibility_gate.Axe") as mock_axe_cls:
                mock_axe = MagicMock()
                mock_axe.run.return_value = axe_result
                mock_axe_cls.return_value = mock_axe

                result = run_accessibility_gate("https://example.com")

        assert isinstance(result, GateResult)
        assert result.passed is True

    def test_non_critical_violations_ignored(self):
        """Only 'minor' and 'moderate' violations -> passed=True (only critical blocked)."""
        from tools.gates.accessibility_gate import run_accessibility_gate

        violations = [
            _make_violation("minor", "Color contrast issue"),
            _make_violation("moderate", "Missing aria-label"),
        ]
        axe_result = _make_axe_result(violations)

        with patch("tools.gates.accessibility_gate.sync_playwright") as mock_pw_ctx:
            mock_page = MagicMock()
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.chromium.launch.return_value = mock_browser
            mock_pw_ctx.return_value = mock_context

            with patch("tools.gates.accessibility_gate.Axe") as mock_axe_cls:
                mock_axe = MagicMock()
                mock_axe.run.return_value = axe_result
                mock_axe_cls.return_value = mock_axe

                result = run_accessibility_gate("https://example.com")

        assert result.passed is True
        assert result.issues == []

    def test_gate_type_is_accessibility(self):
        """gate_type field is 'accessibility'."""
        from tools.gates.accessibility_gate import run_accessibility_gate

        axe_result = _make_axe_result([])

        with patch("tools.gates.accessibility_gate.sync_playwright") as mock_pw_ctx:
            mock_page = MagicMock()
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.chromium.launch.return_value = mock_browser
            mock_pw_ctx.return_value = mock_context

            with patch("tools.gates.accessibility_gate.Axe") as mock_axe_cls:
                mock_axe = MagicMock()
                mock_axe.run.return_value = axe_result
                mock_axe_cls.return_value = mock_axe

                result = run_accessibility_gate("https://example.com")

        assert result.gate_type == "accessibility"

    def test_phase_id_preserved(self):
        """phase_id passed to function appears in result."""
        from tools.gates.accessibility_gate import run_accessibility_gate

        axe_result = _make_axe_result([])

        with patch("tools.gates.accessibility_gate.sync_playwright") as mock_pw_ctx:
            mock_page = MagicMock()
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.chromium.launch.return_value = mock_browser
            mock_pw_ctx.return_value = mock_context

            with patch("tools.gates.accessibility_gate.Axe") as mock_axe_cls:
                mock_axe = MagicMock()
                mock_axe.run.return_value = axe_result
                mock_axe_cls.return_value = mock_axe

                result = run_accessibility_gate("https://example.com", phase_id="3")

        assert result.phase_id == "3"

    def test_checked_at_is_populated(self):
        """checked_at field is non-empty."""
        from tools.gates.accessibility_gate import run_accessibility_gate

        axe_result = _make_axe_result([])

        with patch("tools.gates.accessibility_gate.sync_playwright") as mock_pw_ctx:
            mock_page = MagicMock()
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.chromium.launch.return_value = mock_browser
            mock_pw_ctx.return_value = mock_context

            with patch("tools.gates.accessibility_gate.Axe") as mock_axe_cls:
                mock_axe = MagicMock()
                mock_axe.run.return_value = axe_result
                mock_axe_cls.return_value = mock_axe

                result = run_accessibility_gate("https://example.com")

        assert isinstance(result.checked_at, str)
        assert len(result.checked_at) > 0


class TestAccessibilityGateFail:
    """Tests where critical violations are found."""

    def test_critical_violations_fail(self):
        """2 critical violations -> passed=False."""
        from tools.gates.accessibility_gate import run_accessibility_gate

        violations = [
            _make_violation("critical", "Missing alt text"),
            _make_violation("critical", "Insufficient color contrast"),
        ]
        axe_result = _make_axe_result(violations)

        with patch("tools.gates.accessibility_gate.sync_playwright") as mock_pw_ctx:
            mock_page = MagicMock()
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.chromium.launch.return_value = mock_browser
            mock_pw_ctx.return_value = mock_context

            with patch("tools.gates.accessibility_gate.Axe") as mock_axe_cls:
                mock_axe = MagicMock()
                mock_axe.run.return_value = axe_result
                mock_axe_cls.return_value = mock_axe

                result = run_accessibility_gate("https://example.com")

        assert result.passed is False

    def test_critical_violations_produce_issues(self):
        """Critical violations appear as issues in result."""
        from tools.gates.accessibility_gate import run_accessibility_gate

        violations = [
            _make_violation("critical", "Missing alt text"),
            _make_violation("critical", "Insufficient color contrast"),
        ]
        axe_result = _make_axe_result(violations)

        with patch("tools.gates.accessibility_gate.sync_playwright") as mock_pw_ctx:
            mock_page = MagicMock()
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.chromium.launch.return_value = mock_browser
            mock_pw_ctx.return_value = mock_context

            with patch("tools.gates.accessibility_gate.Axe") as mock_axe_cls:
                mock_axe = MagicMock()
                mock_axe.run.return_value = axe_result
                mock_axe_cls.return_value = mock_axe

                result = run_accessibility_gate("https://example.com")

        assert len(result.issues) == 2

    def test_fail_result_status_is_blocked(self):
        """Critical violations -> status='BLOCKED'."""
        from tools.gates.accessibility_gate import run_accessibility_gate

        violations = [_make_violation("critical", "Missing alt text")]
        axe_result = _make_axe_result(violations)

        with patch("tools.gates.accessibility_gate.sync_playwright") as mock_pw_ctx:
            mock_page = MagicMock()
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.chromium.launch.return_value = mock_browser
            mock_pw_ctx.return_value = mock_context

            with patch("tools.gates.accessibility_gate.Axe") as mock_axe_cls:
                mock_axe = MagicMock()
                mock_axe.run.return_value = axe_result
                mock_axe_cls.return_value = mock_axe

                result = run_accessibility_gate("https://example.com")

        assert result.status == "BLOCKED"


class TestAccessibilityGateExtra:
    """Tests for extra data in GateResult."""

    def test_extra_contains_violation_counts(self):
        """extra dict has total_violations and critical_violations keys."""
        from tools.gates.accessibility_gate import run_accessibility_gate

        violations = [
            _make_violation("critical", "Missing alt text"),
            _make_violation("moderate", "Color contrast"),
            _make_violation("minor", "Label issue"),
        ]
        axe_result = _make_axe_result(violations)

        with patch("tools.gates.accessibility_gate.sync_playwright") as mock_pw_ctx:
            mock_page = MagicMock()
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.chromium.launch.return_value = mock_browser
            mock_pw_ctx.return_value = mock_context

            with patch("tools.gates.accessibility_gate.Axe") as mock_axe_cls:
                mock_axe = MagicMock()
                mock_axe.run.return_value = axe_result
                mock_axe_cls.return_value = mock_axe

                result = run_accessibility_gate("https://example.com")

        assert "total_violations" in result.extra
        assert "critical_violations" in result.extra
        assert result.extra["total_violations"] == 3
        assert result.extra["critical_violations"] == 1


class TestAccessibilityGateBrowserFailure:
    """Tests for browser/playwright error handling."""

    def test_browser_launch_failure_returns_passed_false(self):
        """Playwright exception during setup -> passed=False."""
        from tools.gates.accessibility_gate import run_accessibility_gate

        with patch("tools.gates.accessibility_gate.sync_playwright") as mock_pw_ctx:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(side_effect=Exception("Browser failed to launch"))
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_pw_ctx.return_value = mock_context

            result = run_accessibility_gate("https://example.com")

        assert result.passed is False

    def test_browser_launch_failure_has_issue(self):
        """Playwright exception produces an issue."""
        from tools.gates.accessibility_gate import run_accessibility_gate

        with patch("tools.gates.accessibility_gate.sync_playwright") as mock_pw_ctx:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(side_effect=Exception("Browser failed to launch"))
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_pw_ctx.return_value = mock_context

            result = run_accessibility_gate("https://example.com")

        assert len(result.issues) > 0
