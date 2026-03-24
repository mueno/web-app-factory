"""Tests for tools/gates/e2e_gate.py — E2E form flow gate executor.

Tests cover:
- Skip logic: no form components, missing screen-spec.json
- Playwright import guard
- Form/result route discovery heuristics
- Successful form submission flow (mocked playwright)
- Failure on empty result page
- Server cleanup on playwright exception
"""

from __future__ import annotations

import json
import os
import threading
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from tools.gates.gate_result import GateResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_screen_spec(screens: list) -> dict:
    """Build a minimal screen-spec.json-like dict."""
    return {"screens": screens}


def _make_screen(route: str, components: list[str]) -> dict:
    """Build a minimal screen dict with component names."""
    return {
        "route": route,
        "name": route.strip("/").replace("/", " ").title() or "Home",
        "components": [{"name": c} for c in components],
    }


def _spec_with_no_forms() -> dict:
    """Screen spec where no screen has form-like components."""
    return _make_screen_spec(
        [
            _make_screen("/", ["Header", "HeroSection", "Footer"]),
            _make_screen("/about", ["Header", "AboutContent", "Footer"]),
        ]
    )


def _spec_with_calculator() -> dict:
    """Screen spec with a CalculatorForm component."""
    return _make_screen_spec(
        [
            _make_screen("/", ["Header", "HeroSection", "Footer"]),
            _make_screen("/calculator", ["Header", "CalculatorForm", "Footer"]),
            _make_screen("/results", ["Header", "ResultsDisplay", "Footer"]),
        ]
    )


def _spec_with_search() -> dict:
    """Screen spec with a SearchInput component."""
    return _make_screen_spec(
        [
            _make_screen("/search", ["Header", "SearchInput", "SearchButton", "Footer"]),
            _make_screen("/search/results", ["Header", "ResultList", "Footer"]),
        ]
    )


def _write_spec(tmp_path: Path, spec: dict) -> str:
    """Write spec dict to docs/pipeline/screen-spec.json and return path."""
    spec_dir = tmp_path / "docs" / "pipeline"
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_file = spec_dir / "screen-spec.json"
    spec_file.write_text(json.dumps(spec), encoding="utf-8")
    return str(spec_file)


def _make_ready_stdout() -> BytesIO:
    """Return a BytesIO that yields a 'ready' line when read in chunks."""
    return BytesIO(b"starting server...\nReady in 300ms\n")


def _make_mock_process(stdout_data: bytes = b"Ready in 300ms\n") -> MagicMock:
    """Build a mock subprocess.Popen process."""
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.stdout = BytesIO(stdout_data)
    mock_proc.returncode = 0
    return mock_proc


def _make_mock_playwright(
    body_content: str = "Result: 42 widgets calculated",
    navigate_raises: Exception | None = None,
    wait_url_raises: Exception | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Build (sync_playwright mock, playwright context, page mock).

    Returns the three-level mock hierarchy so tests can inspect calls.
    """
    mock_page = MagicMock()
    mock_page.text_content.return_value = body_content

    if navigate_raises:
        mock_page.goto.side_effect = navigate_raises
    if wait_url_raises:
        mock_page.wait_for_url.side_effect = wait_url_raises

    # Make locator().all() return a single input mock
    mock_input = MagicMock()
    mock_locator = MagicMock()
    mock_locator.all.return_value = [mock_input]
    mock_locator.first = MagicMock()
    mock_page.locator.return_value = mock_locator

    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_pw_context = MagicMock()
    mock_pw_context.__enter__ = MagicMock(return_value=mock_pw_context)
    mock_pw_context.__exit__ = MagicMock(return_value=False)
    mock_pw_context.chromium.launch.return_value = mock_browser

    mock_sync_playwright = MagicMock(return_value=mock_pw_context)

    return mock_sync_playwright, mock_pw_context, mock_page


# ---------------------------------------------------------------------------
# TestE2eGateSkip
# ---------------------------------------------------------------------------


class TestE2eGateSkip:
    """E2E gate skip behaviour."""

    def test_skip_when_no_form_components(self, tmp_path):
        """Screen spec with no form-like components -> skipped=True."""
        from tools.gates.e2e_gate import run_e2e_gate

        spec_path = _write_spec(tmp_path, _spec_with_no_forms())

        result = run_e2e_gate(
            project_dir=str(tmp_path),
            spec_path=spec_path,
        )

        assert isinstance(result, GateResult)
        assert result.skipped is True
        assert result.skip_allowed is True

    def test_skip_when_screen_spec_missing(self, tmp_path):
        """Missing screen-spec.json -> skipped=True with descriptive issue."""
        from tools.gates.e2e_gate import run_e2e_gate

        missing_path = str(tmp_path / "nonexistent.json")

        result = run_e2e_gate(
            project_dir=str(tmp_path),
            spec_path=missing_path,
        )

        assert isinstance(result, GateResult)
        assert result.skipped is True
        assert result.skip_allowed is True
        assert len(result.issues) > 0

    def test_skip_when_no_result_route(self, tmp_path):
        """Form found but no result route -> skipped=True.

        The form screen is the last screen in the list (no next screen),
        and no screen has a result-keyword route, so no result route can
        be discovered.
        """
        from tools.gates.e2e_gate import run_e2e_gate

        spec = _make_screen_spec(
            [
                _make_screen("/home", ["Header", "HeroSection"]),
                _make_screen("/calculator", ["CalculatorForm"]),
                # calculator is last: no next screen, no result keyword routes
            ]
        )
        spec_path = _write_spec(tmp_path, spec)

        result = run_e2e_gate(
            project_dir=str(tmp_path),
            spec_path=spec_path,
        )

        assert result.skipped is True
        assert result.skip_allowed is True

    def test_gate_type_is_e2e_form_flow_on_skip(self, tmp_path):
        """gate_type='e2e_form_flow' even when skipped."""
        from tools.gates.e2e_gate import run_e2e_gate

        spec_path = _write_spec(tmp_path, _spec_with_no_forms())

        result = run_e2e_gate(
            project_dir=str(tmp_path),
            spec_path=spec_path,
        )

        assert result.gate_type == "e2e_form_flow"


# ---------------------------------------------------------------------------
# TestE2eGateType
# ---------------------------------------------------------------------------


class TestE2eGateType:
    """gate_type field is always 'e2e_form_flow'."""

    def test_gate_type_is_e2e_form_flow(self, tmp_path):
        """gate_type='e2e_form_flow' for all result shapes."""
        from tools.gates.e2e_gate import run_e2e_gate

        spec_path = _write_spec(tmp_path, _spec_with_no_forms())

        result = run_e2e_gate(
            project_dir=str(tmp_path),
            spec_path=spec_path,
        )

        assert result.gate_type == "e2e_form_flow"


# ---------------------------------------------------------------------------
# TestE2eGatePlaywrightMissing
# ---------------------------------------------------------------------------


class TestE2eGatePlaywrightMissing:
    """Playwright not installed -> descriptive failure."""

    def test_fails_when_playwright_missing(self, tmp_path):
        """When playwright import fails, returns passed=False."""
        spec_path = _write_spec(tmp_path, _spec_with_calculator())

        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            # Force re-import with playwright unavailable by patching the module-level attribute
            with patch("tools.gates.e2e_gate.sync_playwright", None):
                from tools.gates.e2e_gate import run_e2e_gate

                result = run_e2e_gate(
                    project_dir=str(tmp_path),
                    spec_path=spec_path,
                )

        assert isinstance(result, GateResult)
        assert result.passed is False
        assert result.gate_type == "e2e_form_flow"
        assert any("playwright" in issue.lower() for issue in result.issues)

    def test_playwright_missing_issue_mentions_playwright(self, tmp_path):
        """The issue message mentions 'playwright'."""
        spec_path = _write_spec(tmp_path, _spec_with_calculator())

        with patch("tools.gates.e2e_gate.sync_playwright", None):
            from tools.gates.e2e_gate import run_e2e_gate

            result = run_e2e_gate(
                project_dir=str(tmp_path),
                spec_path=spec_path,
            )

        assert len(result.issues) >= 1
        assert "playwright" in result.issues[0].lower()


# ---------------------------------------------------------------------------
# TestE2eGateRouteDiscovery
# ---------------------------------------------------------------------------


class TestE2eGateRouteDiscovery:
    """Form/result route discovery logic."""

    def test_discovers_form_route_from_component_names(self, tmp_path):
        """CalculatorForm component -> form route discovered."""
        from tools.gates.e2e_gate import _find_form_route

        spec = _spec_with_calculator()
        route = _find_form_route(spec)

        assert route == "/calculator"

    def test_discovers_result_route_heuristic(self, tmp_path):
        """'/results' route identified as result page."""
        from tools.gates.e2e_gate import _find_result_route

        spec = _spec_with_calculator()
        route = _find_result_route(spec, "/calculator")

        assert route is not None
        assert "result" in route.lower()

    def test_form_route_none_when_no_form_components(self, tmp_path):
        """No form-like components -> _find_form_route returns None."""
        from tools.gates.e2e_gate import _find_form_route

        spec = _spec_with_no_forms()
        route = _find_form_route(spec)

        assert route is None

    def test_search_input_is_form_component(self, tmp_path):
        """SearchInput component triggers form route detection."""
        from tools.gates.e2e_gate import _find_form_route

        spec = _spec_with_search()
        route = _find_form_route(spec)

        assert route is not None

    def test_result_route_next_screen_fallback(self, tmp_path):
        """When no result keyword in route, uses next screen in list."""
        from tools.gates.e2e_gate import _find_result_route

        # '/output' has no "result" keyword but should match "output" heuristic
        spec = _make_screen_spec(
            [
                _make_screen("/calc", ["CalculatorForm"]),
                _make_screen("/output", ["OutputDisplay"]),
            ]
        )
        route = _find_result_route(spec, "/calc")
        assert route is not None


# ---------------------------------------------------------------------------
# TestE2eGateSuccess
# ---------------------------------------------------------------------------


class TestE2eGateSuccess:
    """E2E gate passes on successful form flow."""

    def test_passed_true_on_successful_navigation(self, tmp_path):
        """Mocked playwright simulates successful form fill -> passed=True."""
        spec_path = _write_spec(tmp_path, _spec_with_calculator())
        mock_proc = _make_mock_process()
        mock_pw, _, _ = _make_mock_playwright(body_content="Result: 42 widgets calculated successfully. Your calculation is complete and the results are shown below.")

        with patch("tools.gates.e2e_gate.sync_playwright", mock_pw), \
             patch("tools.gates.e2e_gate.subprocess.Popen", return_value=mock_proc), \
             patch("tools.gates.e2e_gate.socket.socket") as mock_sock_cls, \
             patch("tools.gates.e2e_gate.os.killpg"), \
             patch("tools.gates.e2e_gate.os.getpgid", return_value=12345):

            mock_sock = MagicMock()
            mock_sock.getsockname.return_value = ("", 3001)
            mock_sock_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)

            from tools.gates.e2e_gate import run_e2e_gate

            result = run_e2e_gate(
                project_dir=str(tmp_path),
                spec_path=spec_path,
            )

        assert isinstance(result, GateResult)
        assert result.passed is True

    def test_gate_type_on_success(self, tmp_path):
        """gate_type='e2e_form_flow' on success."""
        spec_path = _write_spec(tmp_path, _spec_with_calculator())
        mock_proc = _make_mock_process()
        mock_pw, _, _ = _make_mock_playwright(body_content="Result: 42 widgets calculated. Your calculation is complete and results are shown on this page.")

        with patch("tools.gates.e2e_gate.sync_playwright", mock_pw), \
             patch("tools.gates.e2e_gate.subprocess.Popen", return_value=mock_proc), \
             patch("tools.gates.e2e_gate.socket.socket") as mock_sock_cls, \
             patch("tools.gates.e2e_gate.os.killpg"), \
             patch("tools.gates.e2e_gate.os.getpgid", return_value=12345):

            mock_sock = MagicMock()
            mock_sock.getsockname.return_value = ("", 3001)
            mock_sock_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)

            from tools.gates.e2e_gate import run_e2e_gate

            result = run_e2e_gate(
                project_dir=str(tmp_path),
                spec_path=spec_path,
            )

        assert result.gate_type == "e2e_form_flow"


# ---------------------------------------------------------------------------
# TestE2eGateFailure
# ---------------------------------------------------------------------------


class TestE2eGateFailure:
    """E2E gate fails on bad result page."""

    def test_passed_false_when_result_page_empty(self, tmp_path):
        """Result page body is empty -> passed=False."""
        spec_path = _write_spec(tmp_path, _spec_with_calculator())
        mock_proc = _make_mock_process()
        mock_pw, _, _ = _make_mock_playwright(body_content="   ")  # whitespace only

        with patch("tools.gates.e2e_gate.sync_playwright", mock_pw), \
             patch("tools.gates.e2e_gate.subprocess.Popen", return_value=mock_proc), \
             patch("tools.gates.e2e_gate.socket.socket") as mock_sock_cls, \
             patch("tools.gates.e2e_gate.os.killpg"), \
             patch("tools.gates.e2e_gate.os.getpgid", return_value=12345):

            mock_sock = MagicMock()
            mock_sock.getsockname.return_value = ("", 3001)
            mock_sock_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)

            from tools.gates.e2e_gate import run_e2e_gate

            result = run_e2e_gate(
                project_dir=str(tmp_path),
                spec_path=spec_path,
            )

        assert result.passed is False

    def test_passed_false_when_navigation_times_out(self, tmp_path):
        """wait_for_url raises TimeoutError -> passed=False."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        spec_path = _write_spec(tmp_path, _spec_with_calculator())
        mock_proc = _make_mock_process()
        mock_pw, _, _ = _make_mock_playwright(
            wait_url_raises=PlaywrightTimeoutError("Timed out waiting for URL"),
        )

        with patch("tools.gates.e2e_gate.sync_playwright", mock_pw), \
             patch("tools.gates.e2e_gate.subprocess.Popen", return_value=mock_proc), \
             patch("tools.gates.e2e_gate.socket.socket") as mock_sock_cls, \
             patch("tools.gates.e2e_gate.os.killpg"), \
             patch("tools.gates.e2e_gate.os.getpgid", return_value=12345):

            mock_sock = MagicMock()
            mock_sock.getsockname.return_value = ("", 3001)
            mock_sock_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)

            from tools.gates.e2e_gate import run_e2e_gate

            result = run_e2e_gate(
                project_dir=str(tmp_path),
                spec_path=spec_path,
            )

        assert result.passed is False


# ---------------------------------------------------------------------------
# TestE2eGateServerCleanup
# ---------------------------------------------------------------------------


class TestE2eGateServerCleanup:
    """Server process is always cleaned up."""

    def test_server_cleanup_on_failure(self, tmp_path):
        """Server process is terminated even when playwright raises an exception."""
        spec_path = _write_spec(tmp_path, _spec_with_calculator())
        mock_proc = _make_mock_process()
        mock_pw, _, _ = _make_mock_playwright(
            navigate_raises=Exception("Playwright internal error"),
        )

        kill_calls = []

        def fake_killpg(pgid, sig):
            kill_calls.append((pgid, sig))

        with patch("tools.gates.e2e_gate.sync_playwright", mock_pw), \
             patch("tools.gates.e2e_gate.subprocess.Popen", return_value=mock_proc), \
             patch("tools.gates.e2e_gate.socket.socket") as mock_sock_cls, \
             patch("tools.gates.e2e_gate.os.killpg", side_effect=fake_killpg), \
             patch("tools.gates.e2e_gate.os.getpgid", return_value=12345):

            mock_sock = MagicMock()
            mock_sock.getsockname.return_value = ("", 3001)
            mock_sock_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
            mock_sock_cls.return_value.__exit__ = MagicMock(return_value=False)

            from tools.gates.e2e_gate import run_e2e_gate

            result = run_e2e_gate(
                project_dir=str(tmp_path),
                spec_path=spec_path,
            )

        # Server cleanup must have been called
        assert len(kill_calls) >= 1
        assert result.passed is False


# ---------------------------------------------------------------------------
# TestE2eGateDispatch (Task 2 — integration with contract runner)
# ---------------------------------------------------------------------------


class TestE2eGateDispatch:
    """Integration tests: contract runner dispatches e2e_form_flow gate."""

    def test_contract_runner_dispatches_e2e_form_flow(self, tmp_path):
        """_run_gate_checks calls run_e2e_gate for e2e_form_flow gate type."""
        contract_phase = {
            "id": "2b",
            "gates": [{"type": "e2e_form_flow", "conditions": {"timeout_seconds": 30}}],
        }

        mock_gate_result = GateResult(
            gate_type="e2e_form_flow",
            phase_id="2b",
            passed=True,
            skipped=False,
        )

        with patch("tools.gates.e2e_gate.run_e2e_gate", return_value=mock_gate_result) as mock_run:
            from tools.contract_pipeline_runner import _run_gate_checks

            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        mock_run.assert_called_once()
        assert passed is True
        assert issues == []

    def test_flow01_and_e2e_independent_e2e_fails(self, tmp_path):
        """static_analysis passes, e2e fails -> e2e issues appear."""
        contract_phase = {
            "id": "2b",
            "gates": [
                {"type": "static_analysis", "conditions": {}},
                {"type": "e2e_form_flow", "conditions": {}},
            ],
        }

        passing_static = GateResult(gate_type="static_analysis", phase_id="2b", passed=True)
        failing_e2e = GateResult(
            gate_type="e2e_form_flow",
            phase_id="2b",
            passed=False,
            issues=["E2E: form did not navigate to result page"],
        )

        with patch("tools.contract_pipeline_runner.run_static_analysis_gate", return_value=passing_static), \
             patch("tools.gates.e2e_gate.run_e2e_gate", return_value=failing_e2e):

            from tools.contract_pipeline_runner import _run_gate_checks

            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is False
        assert any("E2E" in issue for issue in issues)

    def test_flow01_and_e2e_independent_static_fails(self, tmp_path):
        """static_analysis fails, e2e passes -> static issues appear."""
        contract_phase = {
            "id": "2b",
            "gates": [
                {"type": "static_analysis", "conditions": {}},
                {"type": "e2e_form_flow", "conditions": {}},
            ],
        }

        failing_static = GateResult(
            gate_type="static_analysis",
            phase_id="2b",
            passed=False,
            issues=["FLOW-01: use client in layout.tsx"],
        )
        passing_e2e = GateResult(gate_type="e2e_form_flow", phase_id="2b", passed=True)

        with patch("tools.contract_pipeline_runner.run_static_analysis_gate", return_value=failing_static), \
             patch("tools.gates.e2e_gate.run_e2e_gate", return_value=passing_e2e):

            from tools.contract_pipeline_runner import _run_gate_checks

            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is False
        assert any("FLOW-01" in issue for issue in issues)

    def test_e2e_skipped_does_not_block(self, tmp_path):
        """Skipped E2E gate (no forms) does not contribute issues."""
        contract_phase = {
            "id": "2b",
            "gates": [{"type": "e2e_form_flow", "conditions": {}}],
        }

        skipped_result = GateResult(
            gate_type="e2e_form_flow",
            phase_id="2b",
            passed=False,
            skipped=True,
            skip_allowed=True,
            issues=["No form-like components found in screen-spec.json — E2E form flow gate skipped"],
        )

        with patch("tools.gates.e2e_gate.run_e2e_gate", return_value=skipped_result):
            from tools.contract_pipeline_runner import _run_gate_checks

            passed, issues = _run_gate_checks(contract_phase, str(tmp_path))

        assert passed is True
        assert issues == []
