"""YAML-driven pipeline runner for web-app-factory.

Loads the pipeline contract, dispatches phases through the executor registry
in PHASE_ORDER sequence, and blocks on gate failures.

Key behaviors (PIPE-01):
- Loads contracts/pipeline-contract.web.v1.yaml and validates against JSON schema
- Executes phases in PHASE_ORDER: 1a -> 1b -> 2a -> 2b -> 3
- Calls generate_quality_self_assessment after each phase success (CONT-04)
- Blocks on phase failure or gate failure (does not advance)
- Supports resume: skips phases already marked "completed" in state
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from tools.pipeline_state import (
    PHASE_ORDER,
    init_run,
    load_state,
    phase_complete,
    phase_start,
    mark_failed,
    mark_completed,
    get_resume_phase,
)
from tools.phase_executors.base import PhaseContext, PhaseResult
from tools.phase_executors.registry import get_executor
from tools.quality_self_assessment import generate_quality_self_assessment


# Default contract path relative to the project root
_DEFAULT_CONTRACT_PATH = (
    Path(__file__).resolve().parent.parent
    / "contracts"
    / "pipeline-contract.web.v1.yaml"
)

# JSON schema path
_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "contracts"
    / "pipeline-contract.schema.json"
)


def load_contract(contract_path: str) -> dict[str, Any]:
    """Load a YAML pipeline contract and validate against JSON schema.

    Args:
        contract_path: Path to the pipeline contract YAML file.

    Returns:
        Parsed contract dict.

    Raises:
        FileNotFoundError: If the contract file does not exist.
        yaml.YAMLError: If the YAML is malformed.
        jsonschema.ValidationError: If the contract violates the schema.
    """
    path = Path(contract_path)
    if not path.exists():
        raise FileNotFoundError(f"Contract not found: {contract_path}")

    with path.open(encoding="utf-8") as f:
        contract = yaml.safe_load(f)

    if not isinstance(contract, dict):
        raise ValueError(f"Contract must be a YAML mapping, got {type(contract).__name__}")

    # Validate against JSON schema
    try:
        import jsonschema  # type: ignore[import]

        if _SCHEMA_PATH.exists():
            schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
            jsonschema.validate(contract, schema)
    except ImportError:
        # jsonschema not available: skip validation (warn but don't fail)
        print(
            "warning: jsonschema not installed — contract schema validation skipped",
            file=sys.stderr,
        )
    # Note: jsonschema.ValidationError propagates naturally (no except here)

    return contract


def _get_contract_phase(contract: dict[str, Any], phase_id: str) -> dict[str, Any] | None:
    """Find a phase entry in the contract by id."""
    for phase in contract.get("phases", []):
        if phase.get("id") == phase_id:
            return phase
    return None


def _run_gate_checks(
    contract_phase: dict[str, Any],
    project_dir: str,
) -> tuple[bool, list[str]]:
    """Run artifact existence and content marker gate checks.

    Returns (passed, issues_list).
    Implements minimal gate checking: required_files existence + output_markers.
    """
    issues: list[str] = []

    for gate in contract_phase.get("gates", []):
        conditions = gate.get("conditions", {})

        # Check required files exist
        for rel_path in conditions.get("required_files", []):
            full_path = Path(project_dir) / rel_path
            if not full_path.exists():
                issues.append(f"Required file missing: {rel_path}")

        # Check required output markers in files
        for marker in conditions.get("required_output_markers", []):
            found = False
            # Search across all files in docs/pipeline/
            docs_dir = Path(project_dir) / "docs" / "pipeline"
            if docs_dir.exists():
                for f in docs_dir.rglob("*"):
                    if f.is_file():
                        try:
                            if marker in f.read_text(encoding="utf-8", errors="replace"):
                                found = True
                                break
                        except OSError:
                            pass
            if not found:
                issues.append(f"Required output marker not found: {marker!r}")

    return len(issues) == 0, issues


def run_pipeline(
    contract: dict[str, Any],
    project_dir: str,
    idea: str,
    *,
    resume_run_id: Optional[str] = None,
    dry_run: bool = False,
    skip_gates: bool = False,
    contract_path: Optional[str] = None,
) -> dict[str, Any]:
    """Execute the pipeline from contract definition.

    Args:
        contract: Parsed pipeline contract dict (from load_contract()).
        project_dir: Root directory for the project being built.
        idea: The app idea string (used for run init and executor context).
        resume_run_id: If set, load this run's state and skip completed phases.
        dry_run: If True, validate and report without executing phases.
        skip_gates: If True, skip gate checks (for testing/debugging).
        contract_path: Path to contract YAML file (for quality assessment).

    Returns:
        Summary dict with keys: status, run_id, phases_executed, phases_skipped,
        error (if any).
    """
    project_dir = str(Path(project_dir).resolve())
    _contract_path = contract_path or str(_DEFAULT_CONTRACT_PATH)

    # Derive app name from idea slug
    safe_chars = [c if c.isalnum() or c in "-_" else "-" for c in idea[:40]]
    app_name = "".join(safe_chars).strip("-") or "web-app"

    # Determine start state
    if resume_run_id:
        state = load_state(resume_run_id, project_dir)
        if state is None:
            return {
                "status": "failed",
                "run_id": resume_run_id,
                "error": f"Resume run not found: {resume_run_id}",
                "phases_executed": [],
                "phases_skipped": [],
            }
        run_id = resume_run_id
        resume_phase = get_resume_phase(run_id, project_dir)
    else:
        state = init_run(app_name, project_dir, idea)
        run_id = state.run_id
        resume_phase = PHASE_ORDER[0]

    if dry_run:
        return {
            "status": "dry-run",
            "run_id": run_id,
            "phases": [p.get("id") for p in contract.get("phases", [])],
            "phases_executed": [],
            "phases_skipped": [],
        }

    phases_executed: list[str] = []
    phases_skipped: list[str] = []
    pipeline_error: Optional[str] = None

    for phase_id in PHASE_ORDER:
        # Skip phases before the resume point
        if resume_phase is not None and PHASE_ORDER.index(phase_id) < PHASE_ORDER.index(resume_phase):
            phases_skipped.append(phase_id)
            continue

        # Skip phases already completed (resume within a phase range)
        if resume_run_id:
            current_state = load_state(run_id, project_dir)
            if current_state:
                phase_record = current_state.phases.get(phase_id, {})
                if phase_record.get("status") in {"completed", "skipped"}:
                    phases_skipped.append(phase_id)
                    continue

        # Record phase start
        phase_start(run_id, phase_id, project_dir)

        # Look up executor
        executor = get_executor(phase_id)
        if executor is None:
            # No executor registered: skip this phase (verify-only mode)
            print(
                f"Phase {phase_id}: no executor registered — skipping (stub mode)",
                file=sys.stderr,
            )
            phase_complete(run_id, phase_id, project_dir, notes="skipped — no executor registered")
            phases_skipped.append(phase_id)
            continue

        # Build context
        ctx = PhaseContext(
            run_id=run_id,
            phase_id=phase_id,
            project_dir=Path(project_dir),
            idea=idea,
            app_name=app_name,
        )

        # Execute phase
        print(f"[pipeline] Executing phase {phase_id}...", file=sys.stderr)
        result: PhaseResult = executor.execute(ctx)
        phases_executed.append(phase_id)

        if not result.success:
            error_msg = result.error or f"Phase {phase_id} returned failure"
            print(f"[pipeline] Phase {phase_id} FAILED: {error_msg}", file=sys.stderr)
            mark_failed(run_id, project_dir, error_msg)
            return {
                "status": "failed",
                "run_id": run_id,
                "error": error_msg,
                "failed_phase": phase_id,
                "phases_executed": phases_executed,
                "phases_skipped": phases_skipped,
            }

        # Phase succeeded: generate quality self-assessment (CONT-04)
        try:
            generate_quality_self_assessment(phase_id, project_dir, _contract_path)
        except Exception as exc:
            print(
                f"warning: quality self-assessment failed for {phase_id}: {exc}",
                file=sys.stderr,
            )

        # Run gate checks (unless skipped)
        if not skip_gates:
            contract_phase = _get_contract_phase(contract, phase_id)
            if contract_phase is not None:
                gate_passed, gate_issues = _run_gate_checks(contract_phase, project_dir)
                if not gate_passed:
                    gate_error = f"Gate failure for phase {phase_id}: {'; '.join(gate_issues)}"
                    print(f"[pipeline] {gate_error}", file=sys.stderr)
                    mark_failed(run_id, project_dir, gate_error)
                    return {
                        "status": "failed",
                        "run_id": run_id,
                        "error": gate_error,
                        "failed_phase": phase_id,
                        "gate_issues": gate_issues,
                        "phases_executed": phases_executed,
                        "phases_skipped": phases_skipped,
                    }

        # Record phase complete
        phase_complete(
            run_id,
            phase_id,
            project_dir,
            artifacts=[a for a in result.artifacts],
        )
        print(f"[pipeline] Phase {phase_id} complete.", file=sys.stderr)

    # All phases done
    mark_completed(run_id, project_dir)
    return {
        "status": "completed",
        "run_id": run_id,
        "phases_executed": phases_executed,
        "phases_skipped": phases_skipped,
    }
