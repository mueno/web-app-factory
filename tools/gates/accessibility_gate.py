"""Accessibility gate executor.

Runs axe-core accessibility checks against a deployed URL using
axe-playwright-python (sync_playwright). Filters violations to
critical impact only and fails when any critical violation is found.

Per RESEARCH.md Pitfall 4: use sync_playwright (not async) to avoid
event loop conflicts with the Python pipeline.

Exported function: run_accessibility_gate
"""

from __future__ import annotations

from datetime import datetime, timezone

from tools.gates.gate_result import GateResult

try:
    from playwright.sync_api import sync_playwright
    from axe_playwright_python.sync_playwright import Axe
except ImportError:
    # Allow import of this module even if playwright/axe are not installed;
    # run_accessibility_gate will fail gracefully at runtime with a descriptive
    # issue when the libraries are missing.
    sync_playwright = None  # type: ignore[assignment]
    Axe = None  # type: ignore[assignment]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_accessibility_gate(url: str, phase_id: str = "3") -> GateResult:
    """Run axe-core accessibility gate against a deployed URL.

    Launches a headless Chromium browser via Playwright, navigates to
    the URL, runs axe-core, and checks for critical violations.

    Args:
        url: Full URL of the deployed application.
        phase_id: Pipeline phase identifier (default "3").

    Returns:
        GateResult with gate_type="accessibility". passed=True only when
        zero critical violations are found.
        extra["total_violations"] is all violation count.
        extra["critical_violations"] is critical-only count.
    """
    checked_at = _now_iso()

    if sync_playwright is None or Axe is None:
        return GateResult(
            gate_type="accessibility",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=["playwright and axe-playwright-python are required but not installed"],
            extra={"total_violations": 0, "critical_violations": 0},
        )

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=30000)

                axe = Axe()
                axe_result = axe.run(page)

                all_violations: list = list(axe_result.violations)
                critical_violations = [v for v in all_violations if v.get("impact") == "critical"]

                issues: list = []
                for violation in critical_violations:
                    description = violation.get("description", violation.get("help", violation.get("id", "Unknown")))
                    issues.append(f"Critical accessibility violation: {description}")

                passed = len(critical_violations) == 0

                return GateResult(
                    gate_type="accessibility",
                    phase_id=phase_id,
                    passed=passed,
                    status="PASS" if passed else "BLOCKED",
                    severity="INFO" if passed else "BLOCK",
                    confidence=1.0 if passed else 0.0,
                    checked_at=checked_at,
                    issues=issues,
                    extra={
                        "total_violations": len(all_violations),
                        "critical_violations": len(critical_violations),
                    },
                )
            finally:
                browser.close()

    except Exception as exc:
        return GateResult(
            gate_type="accessibility",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=[f"Accessibility gate error: {exc}"],
            extra={
                "total_violations": 0,
                "critical_violations": 0,
            },
        )
