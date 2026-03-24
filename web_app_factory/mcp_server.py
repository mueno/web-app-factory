"""Public MCP server for Web App Factory.

Entry point: ``web-app-factory-mcp`` (declared in pyproject.toml).
Transport: stdio (compatible with Claude Desktop and uvx invocation).

Tool namespace convention:
  ALL tools registered on this server MUST use the ``waf_`` prefix.
  This is enforced by tests/test_mcp_server_tool_names.py — any tool
  registered without the prefix will cause CI to fail.

Tools (TOOL-01 through TOOL-07, TOOL-05):
  waf_generate_app      — Start pipeline, return execution plan + run_id
  waf_get_status        — Poll current progress of a pipeline run
  waf_approve_gate      — Approve or reject an interactive-mode gate
  waf_list_runs         — List all pipeline runs with status
  waf_start_dev_server  — Start a local dev server for a completed pipeline run
  waf_stop_dev_server   — Stop a running local dev server for a pipeline run
  waf_check_env         -- Check environment readiness and optionally install missing tools

Business logic is in _tool_impls.py — this file is a thin transport wrapper only.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from web_app_factory._tool_impls import (
    impl_approve_gate,
    impl_check_env,
    impl_generate_app,
    impl_get_status,
    impl_list_runs,
    impl_start_dev_server,
    impl_stop_dev_server,
)

# ── sys.path so internal modules are importable ───────────────────────────────
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


# ── TOOL-01: waf_generate_app ────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    openWorldHint=True,
))
async def waf_generate_app(
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

    Args:
        idea: Description of the web app to build (e.g., "A recipe sharing app").
        mode: Execution mode — "auto" (default), "interactive" (pause at gates),
              or "dry_run" (validate only).
        deploy_target: Where to deploy — "vercel" (default), "gcp", "aws", "local".
        company_name: Company name for legal document generation (optional).
        contact_email: Contact email for legal documents (optional).
        resume_run_id: If set, resume this previous run instead of starting fresh.

    Returns:
        Execution plan as formatted markdown with run_id for status polling.
    """
    return await impl_generate_app(
        idea,
        mode=mode,
        deploy_target=deploy_target,
        company_name=company_name,
        contact_email=contact_email,
        resume_run_id=resume_run_id,
    )


# ── TOOL-02: waf_get_status ──────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    openWorldHint=False,
))
async def waf_get_status(run_id: str) -> str:
    """Get current progress of a pipeline run.

    Returns phase-by-phase status with progress indicators, elapsed time,
    and recent activity log entries.

    Args:
        run_id: The run identifier returned by waf_generate_app.

    Returns:
        Formatted markdown with progress table and recent activity.
    """
    return await impl_get_status(run_id)


# ── TOOL-03: waf_approve_gate ────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    openWorldHint=False,
))
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
    return await impl_approve_gate(run_id, decision, feedback=feedback)


# ── TOOL-04: waf_list_runs ───────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    openWorldHint=False,
))
async def waf_list_runs() -> str:
    """List all pipeline runs with their current status.

    Shows both active (in-memory) and historical (on-disk) runs.

    Returns:
        Formatted table of all runs with status and timestamps.
    """
    return await impl_list_runs()


# ── TOOL-06: waf_start_dev_server ────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    openWorldHint=False,
))
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
    return await impl_start_dev_server(run_id)


# ── TOOL-07: waf_stop_dev_server ─────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    openWorldHint=False,
))
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
    return await impl_stop_dev_server(run_id)


# ── TOOL-05: waf_check_env ───────────────────────────────────────────────────

@mcp.tool(annotations=ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    openWorldHint=False,
))
async def waf_check_env(
    deploy_target: str = "vercel",
    execute_install: bool = False,
    tool_to_install: str | None = None,
) -> str:
    """Check environment readiness for the web-app-factory pipeline.

    Detects whether required tools (Node.js, npm, Python, and deploy-target-specific
    CLIs) are installed, up-to-date, and authenticated. Returns a structured markdown
    table with per-tool status.

    Args:
        deploy_target: Target platform to check. One of "vercel" (default), "gcp",
                       "local". Determines which deploy-target-specific CLIs are
                       checked (e.g. "vercel" checks the Vercel CLI + token;
                       "gcp" checks gcloud CLI + auth).
        execute_install: Set to True to run an automated install after checking.
                         Requires ``tool_to_install`` to be provided as well.
                         Both parameters must be supplied together to prevent
                         accidental silent installs.
        tool_to_install: Logical name of the tool to install (e.g. "node", "npm",
                         "vercel", "gcloud"). Only valid when ``execute_install``
                         is True. The tool must be in the install allowlist —
                         unknown tool names are rejected before any subprocess call.

    Returns:
        Formatted markdown report with a per-tool status table (Tool, Status,
        Version Found, Required, Install Command) plus a summary line and any
        per-tool notes. If ``execute_install=True`` and ``tool_to_install`` is
        provided, the install result is appended at the end of the report.
    """
    return await impl_check_env(
        deploy_target,
        execute_install=execute_install,
        tool_to_install=tool_to_install,
    )


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point for the ``web-app-factory-mcp`` console script."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
