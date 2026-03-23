"""Public MCP server for Web App Factory.

Entry point: ``web-app-factory-mcp`` (declared in pyproject.toml).
Transport: stdio (compatible with Claude Desktop and uvx invocation).

Tool namespace convention:
  ALL tools registered on this server MUST use the ``waf_`` prefix.
  This is enforced by tests/test_mcp_server_tool_names.py — any tool
  registered without the prefix will cause CI to fail.

Tools (TOOL-01 through TOOL-07):
  waf_generate_app      — Start pipeline, return execution plan + run_id
  waf_get_status        — Poll current progress of a pipeline run
  waf_approve_gate      — Approve or reject an interactive-mode gate
  waf_list_runs         — List all pipeline runs with status
  waf_start_dev_server  — Start a local dev server for a completed pipeline run
  waf_stop_dev_server   — Stop a running local dev server for a pipeline run
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

from fastmcp import FastMCP

# ── sys.path so internal modules are importable ──────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Public server — all tools must use waf_ prefix.
mcp = FastMCP(
    "web-app-factory",
    instructions=(
        "Web App Factory: generate full-stack Next.js apps from ideas. "
        "All tools prefixed waf_. Start with waf_generate_app."
    ),
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(idea: str) -> str:
    """Convert idea text to a filesystem-safe slug for project directory."""
    slug = re.sub(r"[^a-z0-9]+", "-", idea.lower().strip())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:40] or "app"


# ── TOOL-01: waf_generate_app ────────────────────────────────────────────────

@mcp.tool()
async def waf_generate_app(
    idea: str,
    mode: str = "auto",
    deploy_target: str = "vercel",
    company_name: str | None = None,
    contact_email: str | None = None,
) -> str:
    """Generate a full-stack Next.js web application from an idea description.

    Creates an execution plan and starts the pipeline in the background.
    Returns the plan immediately with a run_id for tracking progress.

    Args:
        idea: Description of the web app to build (e.g., "A recipe sharing app").
        mode: Execution mode — "auto" (default) or "dry_run" (validate only).
        deploy_target: Where to deploy — "vercel" (default), "gcp", "aws", "local".
        company_name: Company name for legal document generation (optional).
        contact_email: Contact email for legal documents (optional).

    Returns:
        Execution plan as formatted markdown with run_id for status polling.
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
    )

    return format_plan_started(run_id, plan)


# ── TOOL-02: waf_get_status ──────────────────────────────────────────────────

@mcp.tool()
async def waf_get_status(run_id: str) -> str:
    """Get current progress of a pipeline run.

    Returns phase-by-phase status with progress indicators, elapsed time,
    and recent activity log entries.

    Args:
        run_id: The run identifier returned by waf_generate_app.

    Returns:
        Formatted markdown with progress table and recent activity.
    """
    from web_app_factory._progress_store import get_store  # noqa: PLC0415
    from web_app_factory._status_formatter import format_status  # noqa: PLC0415

    store = get_store()
    summary = store.get_run_summary(run_id)

    if summary is None:
        # Try cold path: load from disk state.json for completed/old runs
        return _format_disk_status(run_id)

    events = store.get_events(run_id, since=-10)
    return format_status(run_id, summary, events)


def _format_disk_status(run_id: str) -> str:
    """Fall back to reading pipeline state from disk for completed runs."""
    try:
        from tools.pipeline_state import load_state  # noqa: PLC0415

        # Search output/ for runs matching this run_id
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


# ── TOOL-03: waf_approve_gate ────────────────────────────────────────────────

@mcp.tool()
async def waf_approve_gate(
    run_id: str,
    decision: str,
    feedback: str = "",
) -> str:
    """Approve or reject a pipeline gate in interactive mode.

    In interactive mode, the pipeline pauses at quality gates and waits
    for human approval. Use this tool to continue the pipeline.

    Args:
        run_id: The run identifier.
        decision: "approve" to continue or "reject" to stop the pipeline.
        feedback: Optional feedback text (used when rejecting).

    Returns:
        Confirmation message with next steps.
    """
    if decision not in ("approve", "reject"):
        return f"Invalid decision: {decision!r}. Must be 'approve' or 'reject'."

    # Write approval/rejection to the gate file the internal server polls
    gate_dir = _PROJECT_ROOT / "output" / ".gate-responses"
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
        return f"Gate approved for run `{run_id}`. Pipeline will continue."
    return f"Gate rejected for run `{run_id}`. Feedback: {feedback or '(none)'}"


# ── TOOL-04: waf_list_runs ───────────────────────────────────────────────────

@mcp.tool()
async def waf_list_runs() -> str:
    """List all pipeline runs with their current status.

    Shows both active (in-memory) and historical (on-disk) runs.

    Returns:
        Formatted table of all runs with status and timestamps.
    """
    from web_app_factory._progress_store import get_store  # noqa: PLC0415
    from web_app_factory._status_formatter import format_runs_table  # noqa: PLC0415

    store = get_store()
    runs = store.list_runs()

    # Also scan output/ for historical runs not in memory
    disk_runs = _scan_disk_runs()

    # Merge: in-memory runs take precedence
    seen_ids = {r["run_id"] for r in runs}
    for dr in disk_runs:
        if dr["run_id"] not in seen_ids:
            runs.append(dr)

    return format_runs_table(runs)


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
                    runs.append({
                        "run_id": data.get("run_id", run_dir.name),
                        "status": data.get("status", "unknown"),
                        "started_at": data.get("started_at"),
                    })
                except Exception:
                    pass

    return runs


# ── TOOL-06: waf_start_dev_server ────────────────────────────────────────────

@mcp.tool()
async def waf_start_dev_server(run_id: str) -> str:
    """Start a local dev server for a completed pipeline run.

    Spawns `npm run dev` for the generated Next.js app associated with
    the given run_id and waits up to 30 seconds for the server to be
    ready. Returns a localhost URL once the server is listening.

    Args:
        run_id: The run identifier returned by waf_generate_app.

    Returns:
        Markdown with the localhost URL, or an error message if the
        server could not be started within the timeout.
    """
    from web_app_factory._dev_server import start_dev_server  # noqa: PLC0415

    # start_dev_server blocks for up to 30s — run in executor to avoid
    # blocking the asyncio event loop.
    return await asyncio.get_event_loop().run_in_executor(
        None, start_dev_server, run_id
    )


# ── TOOL-07: waf_stop_dev_server ─────────────────────────────────────────────

@mcp.tool()
async def waf_stop_dev_server(run_id: str) -> str:
    """Stop a running local dev server for a pipeline run.

    Sends SIGTERM to the process group of the dev server associated with
    the given run_id and waits for it to terminate. Escalates to SIGKILL
    after a short timeout if the process does not exit gracefully.

    Args:
        run_id: The run identifier returned by waf_generate_app.

    Returns:
        Confirmation that the server was stopped, or a "not running"
        message if no server was found for the given run_id.
    """
    from web_app_factory._dev_server import stop_dev_server  # noqa: PLC0415

    return stop_dev_server(run_id)


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point for the ``web-app-factory-mcp`` console script."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
