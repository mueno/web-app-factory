"""E2E form flow gate executor.

Runs a Playwright-driven form submission flow against a locally started
Next.js application. The gate discovers the form page and result page from
screen-spec.json, starts ``next start`` on a free port, fills and submits
the form, and asserts the result page renders meaningful content.

Purpose: The FLOW-01 static analysis gate catches parameter name mismatches
at source level, but cannot detect runtime failures (JS errors, hydration
issues, navigation failures). The E2E gate catches what static analysis misses
by actually running the form flow in a real browser.

Exported function: run_e2e_gate
"""

from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tools.gates.gate_result import GateResult

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    # Allow import of this module even if playwright is not installed;
    # run_e2e_gate will fail gracefully at runtime with a descriptive issue.
    sync_playwright = None  # type: ignore[assignment]
    # Define a stub so references to PlaywrightTimeoutError don't NameError
    PlaywrightTimeoutError = Exception  # type: ignore[misc,assignment]


# Regex to detect next.js "ready" signal from stdout
_READY_RE = re.compile(r"(?:ready|Ready|started server)", re.IGNORECASE)

# Keywords that indicate a route is a result/output page
_RESULT_KEYWORDS = ("result", "output", "summary", "report")

# Component name substrings that indicate a form-like screen
_FORM_KEYWORDS = ("form", "input", "search", "calculator", "simulator", "builder", "creator", "editor")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_form_route(spec: dict) -> Optional[str]:
    """Return the route of the first screen with a form-like component.

    A screen is considered form-like if any component name contains one of
    the _FORM_KEYWORDS (case-insensitive).
    """
    for screen in spec.get("screens", []):
        for component in screen.get("components", []):
            name = component.get("name", "")
            if any(kw in name.lower() for kw in _FORM_KEYWORDS):
                return screen.get("route")
    return None


def _find_result_route(spec: dict, form_route: str) -> Optional[str]:
    """Return the route of the result page following the form page.

    Strategy (in order):
    1. Any screen whose route contains one of _RESULT_KEYWORDS.
    2. The screen immediately after the form screen in the screens list.
    """
    screens = spec.get("screens", [])

    # Strategy 1: keyword match in route
    for screen in screens:
        route = screen.get("route", "")
        if any(kw in route.lower() for kw in _RESULT_KEYWORDS):
            return route

    # Strategy 2: next screen in list
    for i, screen in enumerate(screens):
        if screen.get("route") == form_route and i + 1 < len(screens):
            return screens[i + 1].get("route")

    return None


def _find_free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_for_ready(proc: subprocess.Popen, timeout: float = 30.0) -> bool:  # type: ignore[type-arg]
    """Read proc.stdout until a ready-signal line is found or timeout expires.

    Returns True if the server became ready within the timeout, False otherwise.
    """
    ready_event = threading.Event()

    def _reader() -> None:
        try:
            for raw_line in proc.stdout:  # type: ignore[union-attr]
                line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
                if _READY_RE.search(line):
                    ready_event.set()
                    return
        except Exception:
            pass

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()
    return ready_event.wait(timeout=timeout)


def run_e2e_gate(
    project_dir: str,
    spec_path: str,
    phase_id: str = "2b",
) -> GateResult:
    """Run E2E form submission flow gate.

    Starts ``next start`` in project_dir, navigates to the form page
    discovered from spec_path, fills and submits the form, and asserts
    the result page renders meaningful content.

    Args:
        project_dir: Absolute path to the Next.js project directory.
        spec_path: Absolute path to screen-spec.json.
        phase_id: Pipeline phase identifier (default "2b").

    Returns:
        GateResult with gate_type="e2e_form_flow".
        - skipped=True + skip_allowed=True when no form components exist or
          spec is missing/malformed.
        - passed=False when playwright is not installed or the form flow fails.
        - passed=True when form submission successfully navigates to result page
          with non-trivial content.
    """
    checked_at = _now_iso()

    # Guard: playwright not installed
    if sync_playwright is None:
        return GateResult(
            gate_type="e2e_form_flow",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=["playwright browser binaries not found — run: playwright install chromium"],
        )

    # Load screen-spec.json
    spec_file = Path(spec_path)
    if not spec_file.exists():
        return GateResult(
            gate_type="e2e_form_flow",
            phase_id=phase_id,
            passed=False,
            skipped=True,
            skip_allowed=True,
            status="SKIPPED",
            severity="INFO",
            confidence=1.0,
            checked_at=checked_at,
            issues=[f"screen-spec.json not found at {spec_path} — E2E form flow gate skipped"],
        )

    try:
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return GateResult(
            gate_type="e2e_form_flow",
            phase_id=phase_id,
            passed=False,
            skipped=True,
            skip_allowed=True,
            status="SKIPPED",
            severity="INFO",
            confidence=1.0,
            checked_at=checked_at,
            issues=[f"Failed to parse screen-spec.json: {type(exc).__name__} — E2E form flow gate skipped"],
        )

    # Discover form/result route pair
    form_route = _find_form_route(spec)
    if form_route is None:
        return GateResult(
            gate_type="e2e_form_flow",
            phase_id=phase_id,
            passed=False,
            skipped=True,
            skip_allowed=True,
            status="SKIPPED",
            severity="INFO",
            confidence=1.0,
            checked_at=checked_at,
            issues=["No form-like components found in screen-spec.json — E2E form flow gate skipped"],
        )

    result_route = _find_result_route(spec, form_route)
    if result_route is None:
        return GateResult(
            gate_type="e2e_form_flow",
            phase_id=phase_id,
            passed=False,
            skipped=True,
            skip_allowed=True,
            status="SKIPPED",
            severity="INFO",
            confidence=1.0,
            checked_at=checked_at,
            issues=["Form page found but no result route identified — E2E form flow gate skipped"],
        )

    # Start next start server
    port = _find_free_port()
    env = {**os.environ, "PORT": str(port)}

    proc = subprocess.Popen(
        ["npm", "run", "start"],
        cwd=project_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    try:
        ready = _wait_for_ready(proc, timeout=30.0)
        if not ready:
            return GateResult(
                gate_type="e2e_form_flow",
                phase_id=phase_id,
                passed=False,
                status="BLOCKED",
                severity="BLOCK",
                confidence=0.0,
                checked_at=checked_at,
                issues=["next start did not become ready in 30s — E2E form flow gate failed"],
            )

        return _run_playwright_flow(
            port=port,
            form_route=form_route,
            result_route=result_route,
            phase_id=phase_id,
            checked_at=checked_at,
        )

    finally:
        # Always terminate the server process group
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception:
            pass


def _run_playwright_flow(
    port: int,
    form_route: str,
    result_route: str,
    phase_id: str,
    checked_at: str,
) -> GateResult:
    """Run the Playwright form fill + navigation flow.

    This is extracted from run_e2e_gate to allow the server cleanup
    ``finally`` block to always execute regardless of Playwright errors.
    """
    base_url = f"http://localhost:{port}"

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(
                    f"{base_url}{form_route}",
                    wait_until="networkidle",
                    timeout=30000,
                )

                # Fill visible input fields with appropriate test data
                inputs = page.locator("input:visible").all()
                for inp in inputs:
                    input_type = inp.get_attribute("type") or "text"
                    if input_type == "email":
                        inp.fill("test@example.com")
                    elif input_type == "number":
                        inp.fill("100")
                    else:
                        inp.fill("test")

                # Click the submit button
                page.locator(
                    "button[type='submit'], button:has-text('Submit'), "
                    "button:has-text('Calculate'), button:has-text('Search'), "
                    "button:has-text('Go')"
                ).first.click()

                # Wait for navigation to result page
                try:
                    page.wait_for_url(f"**{result_route}**", timeout=10000)
                except PlaywrightTimeoutError:
                    return GateResult(
                        gate_type="e2e_form_flow",
                        phase_id=phase_id,
                        passed=False,
                        status="BLOCKED",
                        severity="BLOCK",
                        confidence=0.0,
                        checked_at=checked_at,
                        issues=[
                            f"E2E: form submission did not navigate to result page "
                            f"'{result_route}' within 10s — check form action and router.push"
                        ],
                    )

                # Assert result page has meaningful content
                content = page.text_content("body")
                if content and len(content.strip()) > 50:
                    return GateResult(
                        gate_type="e2e_form_flow",
                        phase_id=phase_id,
                        passed=True,
                        status="PASS",
                        severity="INFO",
                        confidence=1.0,
                        checked_at=checked_at,
                        issues=[],
                        extra={
                            "form_route": form_route,
                            "result_route": result_route,
                            "result_content_length": len(content.strip()),
                        },
                    )
                else:
                    return GateResult(
                        gate_type="e2e_form_flow",
                        phase_id=phase_id,
                        passed=False,
                        status="BLOCKED",
                        severity="BLOCK",
                        confidence=0.0,
                        checked_at=checked_at,
                        issues=[
                            f"E2E: result page '{result_route}' rendered empty or near-empty content "
                            f"(content length: {len((content or '').strip())} chars) — "
                            f"check that result page reads searchParams and renders results"
                        ],
                    )

            finally:
                browser.close()

    except Exception as exc:
        return GateResult(
            gate_type="e2e_form_flow",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=[f"E2E gate error: {type(exc).__name__} — {exc}"],
        )
