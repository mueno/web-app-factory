"""Status and plan formatters for MCP tool responses.

Renders pipeline progress data as structured markdown that the LLM
displays to the user. Follows GSD ui-brand patterns:
  - Status symbols: ✓ ◆ ○ ✗
  - Progress bar: ████░░
  - Phase table with status indicators
  - Recent activity log
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web_app_factory._plan_generator import ExecutionPlan

# ── Status symbols (GSD convention) ──────────────────────────────────────────
_SYMBOLS: dict[str, str] = {
    "completed": "✓",
    "running": "◆",
    "pending": "○",
    "failed": "✗",
    "skipped": "—",
}

_COMPLEXITY_MARKS: dict[str, str] = {
    "light": "○",
    "medium": "◆",
    "heavy": "●",
}


def format_plan_started(run_id: str, plan: ExecutionPlan) -> str:
    """Format the initial response when a pipeline starts.

    Returned by waf_generate_app — shows the execution plan and run_id.
    """
    lines = [
        f"## Execution Plan: {_slug_from_run_id(run_id)}",
        "",
        f"**Run ID:** `{run_id}`",
        f"**Deploy Target:** {plan.deploy_target}",
        "",
        "| # | Phase | What it produces | Gates | Complexity |",
        "|---|-------|-----------------|-------|------------|",
    ]

    for i, phase in enumerate(plan.phases, 1):
        deliverables = ", ".join(phase.deliverables[:3])
        if len(phase.deliverables) > 3:
            deliverables += f" (+{len(phase.deliverables) - 3})"
        gates = ", ".join(phase.gate_types) if phase.gate_types else "—"
        mark = _COMPLEXITY_MARKS.get(phase.complexity, "○")
        lines.append(
            f"| {i} | {phase.name} | {deliverables} | {gates} | {mark} {phase.complexity.title()} |"
        )

    lines.extend([
        "",
        f'Pipeline started. Use `waf_get_status("{run_id}")` to track progress.',
    ])

    return "\n".join(lines)


def format_status(
    run_id: str,
    summary: dict[str, Any],
    events: list[Any],
) -> str:
    """Format current pipeline status with progress table and recent activity.

    Returned by waf_get_status.
    """
    status = summary.get("status", "unknown")
    completed = summary.get("completed_count", 0)
    total = summary.get("total_phases", 0)
    started_at = summary.get("started_at")
    plan = summary.get("plan")

    elapsed = _elapsed_str(started_at) if started_at else "—"
    bar = _progress_bar(completed, total)

    status_label = status.title()
    if status == "running":
        status_label = "Running"
    elif status == "completed":
        status_label = "Complete"
    elif status == "failed":
        status_label = "Failed"

    lines = [
        f"## Pipeline Progress: {_slug_from_run_id(run_id)}",
        "",
        f"**Status:** {status_label} | **Elapsed:** {elapsed}",
        f"**Progress:** {bar} {completed}/{total} phases",
        "",
    ]

    # Phase table
    lines.extend([
        "| Phase | Status | Details |",
        "|-------|--------|---------|",
    ])

    phase_statuses = summary.get("phase_statuses", {})

    if plan and hasattr(plan, "phases"):
        for phase in plan.phases:
            phase_status = phase_statuses.get(phase.phase_id, "pending")
            symbol = _SYMBOLS.get(phase_status, "○")
            detail = _phase_detail(phase_status, phase)
            lines.append(f"| {phase.name} | {symbol} {phase_status.title()} | {detail} |")
    else:
        for phase_id, phase_status in phase_statuses.items():
            symbol = _SYMBOLS.get(phase_status, "○")
            lines.append(f"| Phase {phase_id} | {symbol} {phase_status.title()} | — |")

    # Recent activity
    if events:
        lines.extend(["", "### Recent Activity"])
        for ev in events[-8:]:
            ts = ev.timestamp[11:19] if len(ev.timestamp) > 19 else ev.timestamp
            lines.append(f"- {ts} — {ev.message}")

    return "\n".join(lines)


def format_runs_table(runs: list[dict[str, Any]]) -> str:
    """Format a table of all pipeline runs.

    Returned by waf_list_runs.
    """
    if not runs:
        return "No pipeline runs found."

    lines = [
        "## Pipeline Runs",
        "",
        "| Run ID | Status | Started |",
        "|--------|--------|---------|",
    ]

    for run in runs:
        run_id = run.get("run_id", "—")
        status = run.get("status", "unknown")
        symbol = _SYMBOLS.get(status, "○")
        started = run.get("started_at", "—")
        if isinstance(started, str) and len(started) > 19:
            started = started[:19].replace("T", " ")
        lines.append(f"| `{run_id}` | {symbol} {status.title()} | {started} |")

    return "\n".join(lines)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _progress_bar(completed: int, total: int, width: int = 10) -> str:
    """Render a text progress bar: ████████░░"""
    if total <= 0:
        return "░" * width
    filled = min(round(completed / total * width), width)
    return "█" * filled + "░" * (width - filled)


def _elapsed_str(started_at: str) -> str:
    """Compute human-readable elapsed time from ISO timestamp."""
    try:
        start = datetime.fromisoformat(started_at)
        now = datetime.now(tz=timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        delta = now - start
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return "0s"
        minutes, seconds = divmod(total_seconds, 60)
        if minutes > 0:
            return f"{minutes}m {seconds:02d}s"
        return f"{seconds}s"
    except (ValueError, TypeError):
        return "—"


def _slug_from_run_id(run_id: str) -> str:
    """Extract the slug portion from a run_id like '20260323-143000-recipe-app'."""
    parts = run_id.split("-", 2)
    return parts[2] if len(parts) > 2 else run_id


def _phase_detail(status: str, phase: Any) -> str:
    """Generate a brief detail string for a phase row."""
    if status == "completed":
        count = len(phase.deliverables) if hasattr(phase, "deliverables") else 0
        return f"{count} deliverables" if count else "Done"
    if status == "running":
        return "In progress..."
    if status == "failed":
        return "Check logs"
    return "Waiting"
