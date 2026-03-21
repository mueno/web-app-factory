"""MCP approval gate executor.

Calls the ``approve_gate`` function from ``factory_mcp_server`` directly
(function import, not via MCP transport) to obtain human sign-off before
production deployment.

Per Phase 4 RESEARCH.md Open Question 3: calling the function directly avoids
the overhead of MCP transport and stdin/stdout handshaking in the gate context.

Exported function: run_mcp_approval_gate
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from tools.gates.gate_result import GateResult

# Import approve_gate function directly — function import, not MCP transport.
from tools.factory_mcp_server import approve_gate


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_mcp_approval_gate(
    phase_id: str,
    project_dir: str,
) -> GateResult:
    """Run MCP human approval gate: call approve_gate and parse result.

    Calls the ``approve_gate`` async function synchronously via asyncio.run().
    The function prints to stderr and blocks until the human responds via the
    file-polling mechanism. This gate should only be called after all quality
    gates have passed.

    Args:
        phase_id: Pipeline phase identifier (e.g., "3").
        project_dir: Path to the generated project directory (for context).

    Returns:
        GateResult with passed=True only when approve_gate returns "APPROVED:..."
        string. Any other response (REJECTED, FEEDBACK, timeout) or exception
        returns passed=False.
    """
    checked_at = _now_iso()

    try:
        response = asyncio.run(
            approve_gate(
                phase=phase_id,
                summary=f"Phase {phase_id} quality gates passed. Awaiting production deploy approval.",
                artifacts=project_dir,
                next_action="production deployment via `vercel --prod`",
            )
        )
    except Exception as exc:
        return GateResult(
            gate_type="mcp_approval",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=[
                f"MCP approval gate failed with exception: {type(exc).__name__}"
            ],
        )

    # Parse approve_gate response — "APPROVED:..." means success
    if response.startswith("APPROVED:"):
        return GateResult(
            gate_type="mcp_approval",
            phase_id=phase_id,
            passed=True,
            status="PASS",
            severity="INFO",
            confidence=1.0,
            checked_at=checked_at,
            issues=[],
        )

    # REJECTED, FEEDBACK, timeout, or any other response -> blocked
    return GateResult(
        gate_type="mcp_approval",
        phase_id=phase_id,
        passed=False,
        status="BLOCKED",
        severity="BLOCK",
        confidence=0.0,
        checked_at=checked_at,
        issues=[f"Human approval denied: {response[:200]}"],
    )
