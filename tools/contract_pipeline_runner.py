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
import re
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
from tools.gates.build_gate import run_build_gate
from tools.gates.static_analysis_gate import run_static_analysis_gate
from pipeline_runtime.governance_monitor import GovernanceMonitor

# Import executor modules to trigger self-registration via register() calls.
# Each module registers its executor at import time; the pipeline runner
# uses get_executor(phase_id) to look them up from the registry.
import tools.phase_executors.phase_1a_executor  # noqa: F401
import tools.phase_executors.phase_1b_executor  # noqa: F401
import tools.phase_executors.phase_2a_executor  # noqa: F401
import tools.phase_executors.phase_2b_executor  # noqa: F401
import tools.phase_executors.phase_3_executor  # noqa: F401 -- self-registers as phase "3"


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


def _read_deployment_url(project_dir: str) -> str:
    """Read the Vercel preview URL from docs/pipeline/deployment.json.

    Args:
        project_dir: Root directory of the generated project.

    Returns:
        The preview_url field from deployment.json.

    Raises:
        ValueError: If deployment.json is missing or preview_url field not found.
    """
    deployment_path = Path(project_dir) / "docs" / "pipeline" / "deployment.json"
    if not deployment_path.exists():
        raise ValueError(
            f"deployment.json not found at {deployment_path}. "
            "Run the deploy_preview sub-step first."
        )
    try:
        data = json.loads(deployment_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(
            f"Failed to read deployment.json: {type(exc).__name__}"
        ) from exc

    preview_url = data.get("preview_url")
    if not preview_url:
        raise ValueError(
            "preview_url field missing or empty in deployment.json"
        )
    return preview_url


def _run_gate_checks(
    contract_phase: dict[str, Any],
    project_dir: str,
    *,
    nextjs_dir: str | None = None,
) -> tuple[bool, list[str]]:
    """Run gate checks dispatched by gate type.

    Returns (passed, issues_list).

    Dispatches based on gate type:
    - "artifact": checks required_files existence (file presence gate)
    - "tool_invocation": checks required_output_markers in docs/pipeline/
    - "build": calls run_build_gate() — runs npm build + tsc --noEmit in nextjs_dir
    - "static_analysis": calls run_static_analysis_gate() — checks 'use client' + secrets in nextjs_dir
    - unknown types: fail-closed with a descriptive issue message (gate_policy)

    Args:
        contract_phase: Phase entry from the pipeline contract.
        project_dir: Pipeline root directory (used for artifact, tool_invocation,
            deployment-related gates, and as fallback for build/static_analysis).
        nextjs_dir: Optional Next.js project directory. When provided, build and
            static_analysis gates receive this directory instead of project_dir,
            ensuring npm/tsc run in the directory that contains package.json.
    """
    issues: list[str] = []
    phase_id = contract_phase.get("id", "unknown")

    for gate in contract_phase.get("gates", []):
        gate_type = gate.get("type", "")
        conditions = gate.get("conditions", {})

        if gate_type == "artifact":
            # Check required files exist
            for rel_path in conditions.get("required_files", []):
                full_path = Path(project_dir) / rel_path
                if not full_path.exists():
                    issues.append(f"Required file missing: {rel_path}")

        elif gate_type == "tool_invocation":
            # Check required output markers in files under docs/pipeline/.
            # Uses 2-layer matching: exact first, then case-insensitive
            # normalized fallback to absorb LLM heading variations.
            for marker in conditions.get("required_output_markers", []):
                found = False
                marker_lower = marker.lower()
                docs_dir = Path(project_dir) / "docs" / "pipeline"
                if docs_dir.exists():
                    for f in docs_dir.rglob("*"):
                        if f.is_file():
                            try:
                                content = f.read_text(encoding="utf-8", errors="replace")
                                if marker in content or marker_lower in content.lower():
                                    found = True
                                    break
                            except OSError:
                                pass
                if not found:
                    issues.append(f"Required output marker not found: {marker!r}")

        elif gate_type == "build":
            # Dispatch to build gate executor: runs npm build + tsc --noEmit.
            # Use nextjs_dir when provided (the generated Next.js project has
            # package.json there, not in the pipeline root).
            target_dir = nextjs_dir if nextjs_dir else project_dir
            gate_result = run_build_gate(target_dir, phase_id=phase_id)
            if not gate_result.passed:
                issues.extend(gate_result.issues)

        elif gate_type == "static_analysis":
            # Dispatch to static analysis gate: checks 'use client' placement + secrets.
            # Use nextjs_dir when provided (src/app/ lives in the Next.js project dir).
            target_dir = nextjs_dir if nextjs_dir else project_dir
            gate_result = run_static_analysis_gate(target_dir, phase_id=phase_id)
            if not gate_result.passed:
                issues.extend(gate_result.issues)

        elif gate_type == "lighthouse":
            from tools.gates.lighthouse_gate import run_lighthouse_gate
            try:
                deployment_url = _read_deployment_url(project_dir)
            except ValueError as exc:
                issues.append(str(exc))
                continue
            gate_result = run_lighthouse_gate(
                url=deployment_url,
                thresholds=conditions.get("thresholds"),
                phase_id=phase_id,
            )
            if not gate_result.passed:
                issues.extend(gate_result.issues)

        elif gate_type == "accessibility":
            from tools.gates.accessibility_gate import run_accessibility_gate
            try:
                deployment_url = _read_deployment_url(project_dir)
            except ValueError as exc:
                issues.append(str(exc))
                continue
            gate_result = run_accessibility_gate(url=deployment_url, phase_id=phase_id)
            if not gate_result.passed:
                issues.extend(gate_result.issues)

        elif gate_type == "security_headers":
            from tools.gates.security_headers_gate import run_security_headers_gate
            try:
                deployment_url = _read_deployment_url(project_dir)
            except ValueError as exc:
                issues.append(str(exc))
                continue
            gate_result = run_security_headers_gate(url=deployment_url, phase_id=phase_id)
            if not gate_result.passed:
                issues.extend(gate_result.issues)

        elif gate_type == "link_integrity":
            from tools.gates.link_integrity_gate import run_link_integrity_gate
            try:
                deployment_url = _read_deployment_url(project_dir)
            except ValueError as exc:
                issues.append(str(exc))
                continue
            gate_result = run_link_integrity_gate(url=deployment_url, phase_id=phase_id)
            if not gate_result.passed:
                issues.extend(gate_result.issues)

        elif gate_type == "deployment":
            from tools.gates.deployment_gate import run_deployment_gate
            try:
                deployment_url = _read_deployment_url(project_dir)
            except ValueError as exc:
                issues.append(str(exc))
                continue
            gate_result = run_deployment_gate(url=deployment_url, phase_id=phase_id)
            if not gate_result.passed:
                issues.extend(gate_result.issues)

        elif gate_type == "mcp_approval":
            from tools.gates.mcp_approval_gate import run_mcp_approval_gate
            gate_result = run_mcp_approval_gate(phase_id=phase_id, project_dir=project_dir)
            if not gate_result.passed:
                issues.extend(gate_result.issues)

        elif gate_type == "legal":
            from tools.gates.legal_gate import run_legal_gate
            # Use nextjs_dir when provided: legal files are written into the
            # Next.js project (src/app/privacy/page.tsx, src/app/terms/page.tsx),
            # not the pipeline root.
            legal_dir = nextjs_dir if nextjs_dir else project_dir
            gate_result = run_legal_gate(project_dir=legal_dir, phase_id=phase_id)
            if not gate_result.passed:
                issues.extend(gate_result.issues)

        else:
            # Unknown gate type: fail-closed per gate_policy (GATE-00 guard)
            issues.append(
                f"Unknown gate type: {gate_type!r} in phase {phase_id} — "
                f"gate check blocked (fail-closed policy)"
            )

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
    company_name: Optional[str] = None,
    contact_email: Optional[str] = None,
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
        company_name: Company name for legal document generation (optional).
            If provided, passed to Phase 3 executor via PhaseContext.extra.
        contact_email: Contact email for legal document generation (optional).
            If provided, passed to Phase 3 executor via PhaseContext.extra.

    Returns:
        Summary dict with keys: status, run_id, phases_executed, phases_skipped,
        error (if any).
    """
    project_dir = str(Path(project_dir).resolve())
    _contract_path = contract_path or str(_DEFAULT_CONTRACT_PATH)

    # Derive app name from idea slug (ASCII-only for npm compatibility)
    safe_chars = [c if (c.isascii() and c.isalnum()) or c in "-_" else "-" for c in idea[:40]]
    app_name = re.sub(r"-{2,}", "-", "".join(safe_chars)).strip("-").lower() or "web-app"

    # Derive the Next.js project directory.
    # project_dir is the pipeline root; create-next-app places the generated
    # app at project_dir.parent / app_name (same pattern as Phase 2a/2b).
    nextjs_dir = str(Path(project_dir).parent / app_name)

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

    # Instantiate GovernanceMonitor for this run (PIPE-05).
    # blocking=False because the contract runner calls execute() synchronously —
    # the monitor would trigger fast_phase_completion violations since phases
    # "complete" instantly from its perspective. Non-blocking still tracks and
    # logs all violations for audit.
    monitor = GovernanceMonitor(run_id=run_id, project_dir=project_dir, blocking=False)

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
        monitor.on_tool_use("mcp__factory__phase_reporter", {"phase": phase_id, "status": "start"})

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

        # Build context (company_name, contact_email, and nextjs_dir forwarded via extra)
        ctx = PhaseContext(
            run_id=run_id,
            phase_id=phase_id,
            project_dir=Path(project_dir),
            idea=idea,
            app_name=app_name,
            extra={
                "company_name": company_name,
                "contact_email": contact_email,
                "nextjs_dir": nextjs_dir,
            },
        )

        # Execute phase
        print(f"[pipeline] Executing phase {phase_id}...", file=sys.stderr)
        result: PhaseResult = executor.execute(ctx)
        phases_executed.append(phase_id)

        if not result.success:
            error_msg = result.error or f"Phase {phase_id} returned failure"
            print(f"[pipeline] Phase {phase_id} FAILED: {error_msg}", file=sys.stderr)
            monitor.on_tool_use("mcp__factory__phase_reporter", {"phase": phase_id, "status": "error"})
            mark_failed(run_id, project_dir, error_msg)
            return {
                "status": "failed",
                "run_id": run_id,
                "error": error_msg,
                "failed_phase": phase_id,
                "phases_executed": phases_executed,
                "phases_skipped": phases_skipped,
            }

        # Phase succeeded: track completion via GovernanceMonitor
        monitor.on_tool_use("mcp__factory__phase_reporter", {"phase": phase_id, "status": "complete"})

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
                gate_passed, gate_issues = _run_gate_checks(
                    contract_phase, project_dir, nextjs_dir=nextjs_dir
                )
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
                monitor.register_gate_pass(phase_id)

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
