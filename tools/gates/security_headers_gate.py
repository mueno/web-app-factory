"""Security headers gate executor.

Sends an HTTP GET request to the deployed URL and verifies that all
required security headers are present in the response.

Required headers (blocking): Content-Security-Policy, X-Frame-Options,
X-Content-Type-Options, Referrer-Policy.

Advisory header (non-blocking): Strict-Transport-Security (Vercel injects
this automatically, so its absence does not block the gate).

Exported function: run_security_headers_gate
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from tools.gates.gate_result import GateResult


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_REQUIRED_HEADERS: list = [
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
]

_ADVISORY_HEADERS: list = [
    "Strict-Transport-Security",
]


def run_security_headers_gate(url: str, phase_id: str = "3") -> GateResult:
    """Verify security headers are present in the HTTP response.

    Sends a GET request to the URL and checks for required security
    headers. Missing required headers are reported as blocking issues.
    Missing advisory headers are reported as non-blocking advisories.

    Args:
        url: Full URL of the deployed application.
        phase_id: Pipeline phase identifier (default "3").

    Returns:
        GateResult with gate_type="security_headers". passed=True only
        when all required headers are present.
    """
    checked_at = _now_iso()

    try:
        response = httpx.get(url, timeout=30, follow_redirects=True)
    except httpx.RequestError as exc:
        return GateResult(
            gate_type="security_headers",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=[f"Request failed: {exc}"],
        )

    # httpx.Headers provides case-insensitive access
    resp_headers = response.headers

    issues: list = []
    advisories: list = []

    # Check required headers (blocking)
    for header in _REQUIRED_HEADERS:
        if header.lower() not in resp_headers:
            issues.append(f"Missing required security header: {header}")

    # Check advisory headers (non-blocking)
    for header in _ADVISORY_HEADERS:
        if header.lower() not in resp_headers:
            advisories.append(
                f"Missing advisory security header: {header} "
                f"(Vercel typically provides this automatically)"
            )

    passed = len(issues) == 0

    return GateResult(
        gate_type="security_headers",
        phase_id=phase_id,
        passed=passed,
        status="PASS" if passed else "BLOCKED",
        severity="INFO" if passed else "BLOCK",
        confidence=1.0 if passed else 0.0,
        checked_at=checked_at,
        issues=issues,
        advisories=advisories,
    )
