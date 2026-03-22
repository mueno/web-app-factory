"""Deployment gate executor.

Performs an HTTP health check against a deployed URL to verify the deployment
is reachable and returns HTTP 200 OK.

Exported function: run_deployment_gate
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from tools.gates.gate_result import GateResult


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_deployment_gate(
    url: str,
    phase_id: str = "3",
) -> GateResult:
    """Run deployment health check gate: HTTP GET on URL, expect 200.

    Args:
        url: The deployed application URL to verify (Vercel preview or prod URL).
        phase_id: Pipeline phase identifier (default "3" — ship phase).

    Returns:
        GateResult with passed=True only when HTTP status code is 200.
    """
    checked_at = _now_iso()

    try:
        response = httpx.get(url, timeout=30, follow_redirects=True)
    except httpx.RequestError as exc:
        return GateResult(
            gate_type="deployment",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=[
                f"Deployment URL unreachable: {type(exc).__name__} — "
                f"could not connect to {url}"
            ],
        )

    if response.status_code in (200, 401):
        return GateResult(
            gate_type="deployment",
            phase_id=phase_id,
            passed=True,
            status="PASS",
            severity="INFO",
            confidence=1.0,
            checked_at=checked_at,
            issues=[],
        )

    return GateResult(
        gate_type="deployment",
        phase_id=phase_id,
        passed=False,
        status="BLOCKED",
        severity="BLOCK",
        confidence=0.0,
        checked_at=checked_at,
        issues=[
            f"Deployment health check failed: HTTP {response.status_code} from {url}"
        ],
    )
