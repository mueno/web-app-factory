"""Shared business logic for all 7 waf_* MCP tools.

This module is the single source of truth for tool behavior — both the
stdio MCP server (mcp_server.py) and the future HTTP server delegate
to these impl functions. A bug fix here propagates to all transports.

Design rules:
- All impl functions are async.
- All imports are lazy (inside function bodies) to avoid circular dependencies
  and to match the established pattern in the project.
- NO module-level singletons (_STORE, _EXECUTOR, _REGISTRY). Those remain in
  their existing homes (_progress_store, _pipeline_bridge).
- Helper functions (_slugify, _format_disk_status, _scan_disk_runs) live here
  because they are business logic, not transport-specific.
- _PROJECT_ROOT is computed once at module level — it is a path constant, not
  a singleton.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

# Path constant — not a singleton, safe at module level.
_PROJECT_ROOT = Path(__file__).parent.parent


# ── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(idea: str) -> str:
    """Convert idea text to a filesystem-safe slug for project directory."""
    slug = re.sub(r"[^a-z0-9]+", "-", idea.lower().strip())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:40] or "app"


def _format_disk_status(run_id: str) -> str:
    """Fall back to reading pipeline state from disk for completed runs."""
    try:
        from tools.pipeline_state import load_state  # noqa: PLC0415

        output_dir = _PROJECT_ROOT / "output"
        if output_dir.exists():
            for project_dir in output_dir.iterdir():
                if project_dir.is_dir():
                    state = load_state(run_id, str(project_dir))
                    if state is not None:
                        phases_info = []
                        for phase_id, record in state.phases.items():
                            if isinstance(record, dict):
                                status = record.get("status", "unknown")
                            else:
                                status = getattr(record, "status", "unknown")
                            phases_info.append(f"| Phase {phase_id} | {status.title()} |")

                        lines = [
                            f"## Pipeline Status: {run_id}",
                            "",
                            f"**Status:** {state.status.title()}",
                            "",
                            "| Phase | Status |",
                            "|-------|--------|",
                            *phases_info,
                        ]
                        return "\n".join(lines)
    except Exception:
        pass

    return f"Run `{run_id}` not found. Use `waf_list_runs()` to see available runs."


def _scan_disk_runs() -> list[dict]:
    """Scan output/ directories for historical pipeline runs."""
    runs = []
    output_dir = _PROJECT_ROOT / "output"
    if not output_dir.exists():
        return runs

    for project_dir in output_dir.iterdir():
        if not project_dir.is_dir():
            continue
        runs_dir = project_dir / "docs" / "pipeline" / "runs"
        if not runs_dir.exists():
            continue
        for run_dir in runs_dir.iterdir():
            state_file = run_dir / "state.json"
            if state_file.exists():
                try:
                    import json  # noqa: PLC0415

                    data = json.loads(state_file.read_text(encoding="utf-8"))
                    run_entry: dict = {
                        "run_id": data.get("run_id", run_dir.name),
                        "status": data.get("status", "unknown"),
                        "started_at": data.get("started_at"),
                    }
                    deploy_file = project_dir / "docs" / "pipeline" / "deployment.json"
                    if deploy_file.exists():
                        deploy_data = json.loads(deploy_file.read_text(encoding="utf-8"))
                        run_entry["url"] = deploy_data.get("url") or deploy_data.get("deploy_url")
                    runs.append(run_entry)
                except Exception:
                    pass

    return runs


# ── IMPL-01: impl_generate_app ───────────────────────────────────────────────

async def impl_generate_app(
    idea: str,
    mode: str = "auto",
    deploy_target: str = "vercel",
    company_name: str | None = None,
    contact_email: str | None = None,
    resume_run_id: str | None = None,
) -> str:
    """Generate a full-stack Next.js web application from an idea description.

    Creates an execution plan and starts the pipeline in the background.
    Returns the plan immediately with a run_id for tracking progress.
    """
    from web_app_factory._input_validator import validate_idea  # noqa: PLC0415
    from web_app_factory._pipeline_bridge import start_pipeline_async  # noqa: PLC0415
    from web_app_factory._status_formatter import format_plan_started  # noqa: PLC0415

    idea = validate_idea(idea)
    project_dir = str(_PROJECT_ROOT / "output" / _slugify(idea))

    run_id, plan = await start_pipeline_async(
        idea,
        project_dir,
        deploy_target=deploy_target,
        mode=mode,
        company_name=company_name,
        contact_email=contact_email,
        resume_run_id=resume_run_id,
    )

    return format_plan_started(run_id, plan)


# ── IMPL-02: impl_get_status ─────────────────────────────────────────────────

async def impl_get_status(run_id: str) -> str:
    """Get current progress of a pipeline run.

    Returns phase-by-phase status with progress indicators, elapsed time,
    and recent activity log entries.
    """
    from web_app_factory._progress_store import get_store  # noqa: PLC0415
    from web_app_factory._status_formatter import format_status  # noqa: PLC0415

    store = get_store()
    summary = store.get_run_summary(run_id)

    if summary is None:
        return _format_disk_status(run_id)

    events = store.get_events(run_id, since=-10)
    return format_status(run_id, summary, events)


# ── IMPL-03: impl_approve_gate ───────────────────────────────────────────────

async def impl_approve_gate(
    run_id: str,
    decision: str,
    feedback: str = "",
) -> str:
    """Approve or reject a pipeline gate in interactive mode.

    In interactive mode, the pipeline pauses at quality gates and waits
    for human approval. Use this to continue the pipeline.
    """
    if decision not in ("approve", "reject"):
        return f"Invalid decision: {decision!r}. Must be 'approve' or 'reject'."

    from web_app_factory._progress_store import get_store  # noqa: PLC0415

    store = get_store()
    run_mode = store.get_mode(run_id)
    if run_mode == "auto":
        return (
            f"Run `{run_id}` is in **auto** mode. "
            "Gates are approved automatically — manual approval is not applicable.\n\n"
            "To use manual gate approval, start the pipeline with `mode='interactive'`."
        )

    from config.settings import GATE_RESPONSES_DIR  # noqa: PLC0415

    gate_dir = GATE_RESPONSES_DIR
    gate_dir.mkdir(parents=True, exist_ok=True)
    gate_file = gate_dir / f"{run_id}.json"

    import json  # noqa: PLC0415

    gate_file.write_text(
        json.dumps({
            "run_id": run_id,
            "decision": decision,
            "feedback": feedback,
        }),
        encoding="utf-8",
    )

    if decision == "approve":
        return f"✓ Gate approved for run `{run_id}`. Pipeline will continue."
    return f"✗ Gate rejected for run `{run_id}`. Feedback: {feedback or '(none)'}"


# ── IMPL-04: impl_list_runs ──────────────────────────────────────────────────

async def impl_list_runs() -> str:
    """List all pipeline runs with their current status.

    Shows both active (in-memory) and historical (on-disk) runs.
    """
    from web_app_factory._progress_store import get_store  # noqa: PLC0415
    from web_app_factory._status_formatter import format_runs_table  # noqa: PLC0415

    store = get_store()
    runs = store.list_runs()

    disk_runs = _scan_disk_runs()

    seen_ids = {r["run_id"] for r in runs}
    for dr in disk_runs:
        if dr["run_id"] not in seen_ids:
            runs.append(dr)

    return format_runs_table(runs)


# ── IMPL-06: impl_start_dev_server ───────────────────────────────────────────

async def impl_start_dev_server(run_id: str) -> str:
    """Start a local dev server for a completed pipeline run.

    Spawns `npm run dev` for the generated Next.js app and waits up to
    30 seconds for the server to be ready.
    """
    from web_app_factory._dev_server import start_dev_server  # noqa: PLC0415

    return await asyncio.get_event_loop().run_in_executor(
        None, start_dev_server, run_id
    )


# ── IMPL-07: impl_stop_dev_server ────────────────────────────────────────────

async def impl_stop_dev_server(run_id: str) -> str:
    """Stop a running local dev server for a pipeline run.

    Sends SIGTERM to the process group of the dev server and waits for
    it to terminate. Escalates to SIGKILL after a short timeout.
    """
    from web_app_factory._dev_server import stop_dev_server  # noqa: PLC0415

    return stop_dev_server(run_id)


# ── IMPL-05: impl_check_env ──────────────────────────────────────────────────

async def impl_check_env(
    deploy_target: str = "vercel",
    execute_install: bool = False,
    tool_to_install: str | None = None,
) -> str:
    """Check environment readiness for the web-app-factory pipeline.

    Detects whether required tools are installed, up-to-date, and
    authenticated. Returns a structured markdown table with per-tool status.
    """
    from web_app_factory._env_checker import check_env, format_env_report, install_tool  # noqa: PLC0415

    statuses = await asyncio.get_event_loop().run_in_executor(None, check_env, deploy_target)

    install_result: str | None = None

    if execute_install:
        if tool_to_install is None:
            return (
                "Error: execute_install=True requires tool_to_install to be provided. "
                "Both parameters must be supplied together to prevent accidental installs. "
                "Example: waf_check_env(execute_install=True, tool_to_install='vercel')"
            )
        install_result = await asyncio.get_event_loop().run_in_executor(
            None, install_tool, tool_to_install
        )

    return format_env_report(statuses, install_result=install_result)
