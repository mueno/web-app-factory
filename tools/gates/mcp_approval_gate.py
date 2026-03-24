"""MCP approval gate executor.

Supports two modes:

1. **Legacy mode** (``interactive=False``, default):
   Calls the ``approve_gate`` function from ``factory_mcp_server`` directly
   (function import, not via MCP transport) to obtain human sign-off before
   production deployment.

2. **Interactive mode** (``interactive=True``):
   Polls a gate-response JSON file written by ``waf_approve_gate`` MCP tool.
   The file is placed at ``GATE_RESPONSES_DIR / "{run_id}.json"`` by the MCP
   server when the human approves or rejects via Claude Desktop.

Per Phase 4 RESEARCH.md Open Question 3: calling the function directly in
legacy mode avoids the overhead of MCP transport and stdin/stdout handshaking
in the gate context.

Exported function: run_mcp_approval_gate
Internal function: _poll_mcp_gate_file (exposed for unit testing)
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from config.settings import GATE_RESPONSES_DIR
from tools.gates.gate_result import GateResult

# Import approve_gate function directly — function import, not MCP transport.
from tools.factory_mcp_server import approve_gate


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _poll_mcp_gate_file(
    phase_id: str,
    run_id: str,
    *,
    poll_interval: float = 2.0,
    timeout_seconds: float = 0,
) -> GateResult:
    """Poll for a gate-response JSON file written by waf_approve_gate.

    Blocks the calling thread until:
    - A gate file appears and contains a valid ``decision`` field, OR
    - ``timeout_seconds`` elapses (returns BLOCKED result).

    A ``timeout_seconds`` of 0 (default) means poll indefinitely.

    On a successful read the file is deleted (consumed) to prevent
    double-processing.

    Args:
        phase_id: Pipeline phase identifier forwarded to GateResult.
        run_id: Pipeline run identifier; the gate file is named ``{run_id}.json``.
        poll_interval: Seconds to sleep between file-existence checks.
        timeout_seconds: Maximum total wait time in seconds. 0 = no limit.

    Returns:
        GateResult with passed=True on approval, passed=False on rejection or timeout.
    """
    checked_at = _now_iso()
    gate_file: Path = GATE_RESPONSES_DIR / f"{run_id}.json"
    deadline = time.monotonic() + timeout_seconds if timeout_seconds > 0 else None

    while True:
        # Check timeout before attempting file read
        if deadline is not None and time.monotonic() >= deadline:
            return GateResult(
                gate_type="mcp_approval",
                phase_id=phase_id,
                passed=False,
                status="BLOCKED",
                severity="BLOCK",
                confidence=0.0,
                checked_at=checked_at,
                issues=[
                    f"Timeout waiting for gate approval (run_id={run_id}, "
                    f"timeout={timeout_seconds}s)"
                ],
            )

        try:
            raw = gate_file.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            # File not yet available or malformed — wait and retry
            time.sleep(poll_interval)
            continue

        # File was read — consume it immediately to prevent double-processing
        gate_file.unlink(missing_ok=True)

        decision = data.get("decision", "")
        feedback = data.get("feedback", "")

        if decision == "approve":
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

        # Any non-approve decision (reject, unknown) -> BLOCKED
        issue_text = f"Human approval denied: decision={decision!r}"
        if feedback:
            issue_text += f", feedback: {feedback[:200]}"
        return GateResult(
            gate_type="mcp_approval",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=[issue_text],
        )


def run_mcp_approval_gate(
    phase_id: str,
    project_dir: str,
    *,
    interactive: bool = False,
    run_id: str = "",
) -> GateResult:
    """Run MCP human approval gate: call approve_gate and parse result.

    Supports two execution modes:

    **Legacy mode** (``interactive=False``, default):
    Calls the ``approve_gate`` async function synchronously via asyncio.run().
    The function prints to stderr and blocks until the human responds via the
    file-polling mechanism. This gate should only be called after all quality
    gates have passed.

    **Interactive mode** (``interactive=True``):
    Delegates to ``_poll_mcp_gate_file`` which polls for a gate-response JSON
    file written by ``waf_approve_gate``. Requires ``run_id`` to be non-empty.

    Args:
        phase_id: Pipeline phase identifier (e.g., "3").
        project_dir: Path to the generated project directory (for context).
        interactive: If True, use file-based polling instead of approve_gate.
        run_id: Required when interactive=True. Run identifier for polling.

    Returns:
        GateResult with passed=True only when the gate is approved.
        Any other response (rejected, timeout) or exception returns passed=False.
    """
    checked_at = _now_iso()

    # ── Interactive file-based polling path ──────────────────────────────────
    if interactive:
        if not run_id:
            return GateResult(
                gate_type="mcp_approval",
                phase_id=phase_id,
                passed=False,
                status="BLOCKED",
                severity="BLOCK",
                confidence=0.0,
                checked_at=checked_at,
                issues=[
                    "Interactive mode requires run_id to be provided. "
                    "Ensure the pipeline was started with mode='interactive' "
                    "and pass the run_id from waf_generate_app."
                ],
            )
        return _poll_mcp_gate_file(phase_id, run_id)

    # ── Legacy path: asyncio.run(approve_gate(...)) ──────────────────────────
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
