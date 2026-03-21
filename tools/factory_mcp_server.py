from __future__ import annotations

#!/usr/bin/env python3
"""
Factory MCP Server — Standalone MCP server for web-app-factory.

Provides approve_gate and phase_reporter tools.
Started as a subprocess; communicates via stdin/stdout.
"""

import asyncio
import json
import os
import re
import sys
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:
    class FastMCP:  # pragma: no cover - exercised when MCP SDK is unavailable
        """Minimal fallback used by unit tests importing tool functions directly."""

        def __init__(self, _name: str) -> None:
            self._name = _name

        def tool(self, *_args: Any, **_kwargs: Any):
            def _decorator(func):
                return func

            return _decorator

        def run(self) -> None:
            raise RuntimeError("mcp.server.fastmcp is not installed")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import APPROVAL_TMP_DIR

mcp = FastMCP("factory")

# ── approve_gate ──────────────────────────────────────────────

APPROVAL_TIMEOUT_SECONDS = int(os.environ.get("WEB_FACTORY_APPROVAL_TIMEOUT_SEC", "0"))


def _new_gate_paths() -> tuple[Path, Path]:
    token = f"{os.getpid()}-{uuid.uuid4().hex}"
    request = APPROVAL_TMP_DIR / f"factory_approve_request_{token}.json"
    response = APPROVAL_TMP_DIR / f"factory_approve_response_{token}"
    return request, response


@mcp.tool()
async def approve_gate(phase: str, summary: str, artifacts: str, next_action: str) -> str:
    """Human approval gate. Called after phase completion to get approve/reject/feedback."""
    request_path, response_path = _new_gate_paths()
    APPROVAL_TMP_DIR.mkdir(parents=True, exist_ok=True)

    separator = "=" * 60
    print(f"\n{separator}", file=sys.stderr)
    print(f"  Approval Gate: {phase}", file=sys.stderr)
    print(f"{separator}", file=sys.stderr)
    print(f"\nSummary: {summary}", file=sys.stderr)
    print(f"\nArtifacts:\n{artifacts}", file=sys.stderr)
    print(f"\nNext action: {next_action}", file=sys.stderr)
    print(f"\n{separator}", file=sys.stderr)

    # Write request to file
    response_path.unlink(missing_ok=True)
    request_path.write_text(
        json.dumps(
            {
                "phase": phase,
                "summary": summary,
                "artifacts": artifacts,
                "next_action": next_action,
                "response_path": str(response_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        "\nAwaiting response: write yes/no/feedback to the response file below",
        file=sys.stderr,
    )
    print(f"  request:  {request_path}", file=sys.stderr)
    print(f"  response: {response_path}", file=sys.stderr)

    # File-based polling (2-second interval)
    started = time.monotonic()
    while True:
        if response_path.exists():
            response = response_path.read_text(encoding="utf-8").strip()
            if response:
                response_path.unlink(missing_ok=True)
                request_path.unlink(missing_ok=True)
                break
        if APPROVAL_TIMEOUT_SECONDS > 0 and (time.monotonic() - started) >= APPROVAL_TIMEOUT_SECONDS:
            request_path.unlink(missing_ok=True)
            response_path.unlink(missing_ok=True)
            return (
                f"REJECTED: {phase} timed out waiting for approval "
                f"({APPROVAL_TIMEOUT_SECONDS}s)."
            )
        await asyncio.sleep(2)

    if response.lower() == "yes":
        return f"APPROVED: {phase} approved. Proceed with {next_action}."
    elif response.lower() == "no":
        return f"REJECTED: {phase} rejected by user. Stop the pipeline."
    else:
        return f"FEEDBACK: {response}\n\nApply this feedback to {phase} and call approve_gate again."


# ── phase_reporter ────────────────────────────────────────────

REPORTS_DIR = Path(__file__).parent.parent / "output" / "reports"


@mcp.tool()
async def phase_reporter(
    phase: str,
    status: str,
    message: str,
    run_id: str = "",
    project_dir: str = "",
    artifacts: list[str] | None = None,
) -> str:
    """Log pipeline phase progress.

    status: start, complete, error, info
    run_id: unique ID per pipeline run (writes to global log if empty)
    project_dir: project directory (used as bridge to update state.json / activity-log.jsonl)
    artifacts: list of artifact paths on phase completion
    """

    emoji = {"start": "🚀", "complete": "✅", "error": "❌", "info": "ℹ️"}.get(
        status, "📝"
    )
    print(f"[{emoji}] [{phase}] {status}: {message}", file=sys.stderr)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Individual log if run_id provided, else global log
    if run_id:
        log_path = REPORTS_DIR / f"pipeline-{run_id}.jsonl"
    else:
        log_path = REPORTS_DIR / "pipeline.jsonl"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "status": status,
        "message": message,
    }
    if run_id:
        entry["run_id"] = run_id
    if artifacts:
        entry["artifacts"] = artifacts

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── Bridge: pipeline_state → state.json / activity-log.jsonl ──
    if run_id and project_dir:
        phase_id = _normalize_phase_id_mcp(phase)
        try:
            from tools.pipeline_state import phase_complete as ps_complete
            from tools.pipeline_state import phase_start as ps_start

            if status == "start":
                ps_start(run_id, phase_id, project_dir)
            elif status == "complete":
                ps_complete(run_id, phase_id, project_dir, artifacts, message or "")
            print(
                f"  [bridge] pipeline_state updated: {phase_id} {status}",
                file=sys.stderr,
            )
        except Exception as exc:
            import traceback

            print(
                f"  [bridge] pipeline_state error: {exc}", file=sys.stderr
            )
            print(traceback.format_exc(), file=sys.stderr)
            # Fallback: write directly to activity-log.jsonl
            _fallback_activity_log(
                project_dir, run_id, phase_id, status, message, artifacts
            )

    return f"{emoji} {phase}: {status} - {message}"


_PHASE_ID_RE = re.compile(
    r"(?<![0-9A-Za-z])([1-9][0-9]?[ab]?\+?)(?![0-9A-Za-z])", re.IGNORECASE
)


def _normalize_phase_id_mcp(phase: str) -> str:
    """Normalize phase strings like 'Phase 1a: Idea Validation' -> '1a'."""
    normalized = unicodedata.normalize("NFKC", phase)
    match = _PHASE_ID_RE.search(normalized)
    return match.group(1).lower() if match else phase


def _fallback_activity_log(
    project_dir: str,
    run_id: str,
    phase_id: str,
    status: str,
    message: str,
    artifacts: list[str] | None,
) -> None:
    """Fallback: write directly to activity-log.jsonl when bridge fails."""
    try:
        log_path = Path(project_dir) / "docs" / "pipeline" / "activity-log.jsonl"
        event = f"phase_{status}" if status in ("start", "complete") else status
        fallback_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "event": event,
            "phase": phase_id,
            "message": message,
        }
        if artifacts:
            fallback_entry["artifacts"] = artifacts
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(fallback_entry, ensure_ascii=False) + "\n")
        print(
            f"  [bridge] fallback write to activity-log.jsonl OK",
            file=sys.stderr,
        )
    except Exception as exc2:
        print(
            f"  [bridge] fallback write also failed: {exc2}",
            file=sys.stderr,
        )


# ── main ──────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
