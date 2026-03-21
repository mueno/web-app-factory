"""Build gate executor.

Runs `npm run build` and `npx tsc --noEmit` as subprocess calls.
Both must exit 0 for the gate to pass.

Exported function: run_build_gate
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone

from tools.gates.gate_result import GateResult


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_build_gate(project_dir: str, phase_id: str = "2a") -> GateResult:
    """Run build gate checks: npm run build and tsc --noEmit.

    Args:
        project_dir: Absolute path to the generated Next.js project directory.
        phase_id: Pipeline phase identifier (default "2a").

    Returns:
        GateResult with passed=True only when both commands exit 0.
    """
    checked_at = _now_iso()

    # Step 1: Run npm run build
    try:
        npm_result = subprocess.run(
            ["npm", "run", "build"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1"},
        )
    except subprocess.TimeoutExpired:
        return GateResult(
            gate_type="build",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=["npm run build timeout after 120 seconds"],
        )

    if npm_result.returncode != 0:
        stderr = (npm_result.stderr or "").strip()
        issues = [stderr] if stderr else ["npm run build exited with non-zero status"]
        return GateResult(
            gate_type="build",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=issues,
        )

    # Step 2: Run tsc --noEmit
    try:
        tsc_result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return GateResult(
            gate_type="build",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=["npx tsc --noEmit timeout after 120 seconds"],
        )

    if tsc_result.returncode != 0:
        stderr = (tsc_result.stderr or "").strip()
        issues = [stderr] if stderr else ["tsc --noEmit exited with non-zero status"]
        return GateResult(
            gate_type="build",
            phase_id=phase_id,
            passed=False,
            status="BLOCKED",
            severity="BLOCK",
            confidence=0.0,
            checked_at=checked_at,
            issues=issues,
        )

    # Both commands passed
    return GateResult(
        gate_type="build",
        phase_id=phase_id,
        passed=True,
        status="PASS",
        severity="INFO",
        confidence=1.0,
        checked_at=checked_at,
        issues=[],
    )
