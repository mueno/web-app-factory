"""Dev server lifecycle management for generated Next.js applications.

Provides start_dev_server and stop_dev_server for managing local preview
servers. Used by waf_start_dev_server and waf_stop_dev_server MCP tools.

Key design decisions:
- subprocess.Popen with start_new_session=True for process group isolation
- Background thread reads stdout, sets threading.Event on ready signal
- os.killpg(pgid, SIGTERM) terminates full npm/node/next process tree
- _PROC_MAP is separate from frozen DevServerInfo registry (Popen is mutable)
- atexit handler + signal handlers for orphan cleanup on MCP shutdown
"""
from __future__ import annotations

import atexit
import json
import os
import re
import signal
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Module constants ──────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent

# Timeout waiting for Next.js ready signal (seconds)
_READINESS_TIMEOUT = 30.0

# Next.js stdout patterns
_LOCAL_URL_RE = re.compile(r"-\s+Local:\s+(http://localhost:(\d+))")
_READY_RE = re.compile(r"(?:✓\s+)?Ready in \d+")

# ── Data types ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DevServerInfo:
    """Immutable snapshot of a running dev server."""

    run_id: str
    pid: int
    port: int
    url: str
    started_at: str      # ISO 8601
    project_dir: str


# ── Registry ──────────────────────────────────────────────────────────────────


class DevServerRegistry:
    """Thread-safe in-memory registry of running dev servers.

    Mirrors the ProgressStore pattern from _progress_store.py.
    DevServerInfo is frozen; mutable Popen objects live in _PROC_MAP.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._registry: dict[str, DevServerInfo] = {}

    def get(self, run_id: str) -> Optional[DevServerInfo]:
        with self._lock:
            return self._registry.get(run_id)

    def set(self, info: DevServerInfo) -> None:
        with self._lock:
            self._registry[info.run_id] = info

    def remove(self, run_id: str) -> None:
        with self._lock:
            self._registry.pop(run_id, None)

    def all_run_ids(self) -> list[str]:
        with self._lock:
            return list(self._registry.keys())


# ── Module-level singletons ───────────────────────────────────────────────────

_REGISTRY = DevServerRegistry()

# Mutable Popen references — separate from frozen DevServerInfo
_PROC_MAP: dict[str, subprocess.Popen] = {}  # type: ignore[type-arg]

_PROC_MAP_LOCK = threading.Lock()


def get_registry() -> DevServerRegistry:
    """Return the module-level DevServerRegistry singleton."""
    return _REGISTRY


# ── Project dir resolution ────────────────────────────────────────────────────


def _resolve_project_dir(run_id: str) -> Optional[Path]:
    """Scan output/*/docs/pipeline/runs/{run_id}/state.json for project_dir.

    Returns the resolved Path or None if not found.
    """
    output_root = _PROJECT_ROOT / "output"
    if not output_root.exists():
        return None

    pattern = output_root / "*" / "docs" / "pipeline" / "runs" / run_id / "state.json"
    matches = list(output_root.glob(
        f"*/docs/pipeline/runs/{run_id}/state.json"
    ))
    if not matches:
        return None

    state_path = matches[0]
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        project_dir_str = state.get("project_dir")
        if project_dir_str:
            return Path(project_dir_str)
    except (json.JSONDecodeError, OSError):
        pass

    return None


# ── Readiness reader thread ───────────────────────────────────────────────────


def _reader_thread(
    proc: subprocess.Popen,  # type: ignore[type-arg]
    ready_event: threading.Event,
    url_holder: list[str],
    timeout: float,
) -> None:
    """Background thread: read proc.stdout line-by-line, set ready_event when ready.

    Captures URL from "- Local: http://localhost:XXXX" line.
    Sets event when BOTH URL captured AND "Ready in Xms" matched.
    """
    url_found = False
    ready_found = False
    url: str = ""

    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            line = line.rstrip()

            url_match = _LOCAL_URL_RE.search(line)
            if url_match:
                url = url_match.group(1)
                url_holder.append(url)
                url_found = True

            if _READY_RE.search(line):
                ready_found = True

            if url_found and ready_found:
                ready_event.set()
                return

            # If process exited, stop reading
            if proc.poll() is not None:
                break
    except Exception:
        pass

    # If we reach here without setting event, mark as done so timeout path
    # can distinguish "process exited" from "still waiting"
    # (ready_event remains unset → caller sees timeout or exit)


# ── Core public API ───────────────────────────────────────────────────────────


def start_dev_server(run_id: str) -> str:
    """Start a Next.js dev server for the given run_id.

    Returns a formatted markdown string with the server URL on success,
    or an error message if the run_id is not found / server fails to start.

    Idempotent: if a live server is already tracked for this run_id, returns
    the existing URL without spawning a new process.
    """
    # ── Check for existing live server ───────────────────────────────────────
    existing = _REGISTRY.get(run_id)
    if existing is not None:
        try:
            os.kill(existing.pid, 0)
            # Process is alive — return cached URL
            return (
                f"✓ Dev server already running\n\n"
                f"**URL:** {existing.url}\n"
                f"**PID:** {existing.pid}\n"
                f"**Run ID:** `{run_id}`"
            )
        except ProcessLookupError:
            # Stale PID — remove and restart
            _REGISTRY.remove(run_id)
            with _PROC_MAP_LOCK:
                _PROC_MAP.pop(run_id, None)
        except OSError:
            # Permission denied or other — treat as alive to be safe
            return (
                f"✓ Dev server already running\n\n"
                f"**URL:** {existing.url}\n"
                f"**PID:** {existing.pid}\n"
                f"**Run ID:** `{run_id}`"
            )

    # ── Resolve project directory ─────────────────────────────────────────────
    project_dir = _resolve_project_dir(run_id)
    if project_dir is None:
        return (
            f"✗ Dev server error\n\n"
            f"Run ID `{run_id}` not found. "
            f"Run `waf_generate_app` first, or check the run_id."
        )

    # ── Spawn dev server process ──────────────────────────────────────────────
    cmd = ["npm", "run", "dev", "--", "--port", "0"]
    proc = subprocess.Popen(
        cmd,
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        start_new_session=True,
    )

    with _PROC_MAP_LOCK:
        _PROC_MAP[run_id] = proc

    # ── Wait for readiness ────────────────────────────────────────────────────
    ready_event = threading.Event()
    url_holder: list[str] = []

    thread = threading.Thread(
        target=_reader_thread,
        args=(proc, ready_event, url_holder, _READINESS_TIMEOUT),
        daemon=True,
    )
    thread.start()

    # Check for quick process exit (crash before reading begins)
    def _poll_for_exit(event: threading.Event) -> None:
        """Poll process for early exit and set event to unblock wait."""
        while not event.is_set():
            if proc.poll() is not None:
                event.set()
                return
            threading.Event().wait(0.05)

    exit_poller = threading.Thread(target=_poll_for_exit, args=(ready_event,), daemon=True)
    exit_poller.start()

    fired = ready_event.wait(timeout=_READINESS_TIMEOUT)
    thread.join(timeout=1.0)

    # ── Evaluate outcome ──────────────────────────────────────────────────────
    if not url_holder:
        # Either timeout or process exited without signaling readiness
        exit_code = proc.poll()
        if exit_code is not None:
            _cleanup_proc(run_id, proc)
            return (
                f"✗ Dev server failed to start\n\n"
                f"Process exited with code {exit_code}. "
                f"Check that `npm install` has been run in the project directory."
            )
        # Timeout — terminate the stuck process
        _cleanup_proc(run_id, proc)
        return (
            f"✗ Dev server timeout\n\n"
            f"No ready signal detected within {int(_READINESS_TIMEOUT)}s. "
            f"The process was terminated."
        )

    url = url_holder[0]
    # Parse port from URL
    port_match = re.search(r":(\d+)$", url)
    port = int(port_match.group(1)) if port_match else 0
    started_at = datetime.now(timezone.utc).isoformat()

    # Register server info
    info = DevServerInfo(
        run_id=run_id,
        pid=proc.pid,
        port=port,
        url=url,
        started_at=started_at,
        project_dir=str(project_dir),
    )
    _REGISTRY.set(info)

    return (
        f"✓ Dev server started\n\n"
        f"**URL:** {url}\n"
        f"**PID:** {proc.pid}\n"
        f"**Run ID:** `{run_id}`"
    )


def _cleanup_proc(run_id: str, proc: subprocess.Popen) -> None:  # type: ignore[type-arg]
    """Terminate a process and remove it from tracking maps."""
    _terminate_server(run_id, proc)
    _REGISTRY.remove(run_id)
    with _PROC_MAP_LOCK:
        _PROC_MAP.pop(run_id, None)


def stop_dev_server(run_id: str) -> str:
    """Stop the dev server for the given run_id.

    Sends SIGTERM to the process group (os.killpg). Escalates to SIGKILL
    after 5 seconds if the process has not exited.

    Returns a formatted confirmation or 'not running' message.
    """
    info = _REGISTRY.get(run_id)
    if info is None:
        return f"✗ Dev server for `{run_id}` is not running"

    with _PROC_MAP_LOCK:
        proc = _PROC_MAP.get(run_id)

    _terminate_server(run_id, proc)
    _REGISTRY.remove(run_id)
    with _PROC_MAP_LOCK:
        _PROC_MAP.pop(run_id, None)

    return (
        f"✓ Dev server stopped\n\n"
        f"**Run ID:** `{run_id}`\n"
        f"**PID:** {info.pid}"
    )


def _terminate_server(run_id: str, proc: Optional[subprocess.Popen]) -> None:  # type: ignore[type-arg]
    """Send SIGTERM to process group; escalate to SIGKILL after 5s."""
    if proc is None:
        return

    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        # Process already gone
        return

    # Wait up to 5s for graceful exit
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        # Escalate to SIGKILL
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass


# ── Cleanup handlers ──────────────────────────────────────────────────────────


def _cleanup_all_servers() -> None:
    """Terminate all tracked dev servers. Called by atexit handler.

    Best-effort: if MCP server crashes hard (SIGKILL), orphans may remain.
    Users can kill manually using the PID reported in the tool response.
    """
    run_ids = _REGISTRY.all_run_ids()
    for run_id in run_ids:
        with _PROC_MAP_LOCK:
            proc = _PROC_MAP.get(run_id)
        _terminate_server(run_id, proc)


def _signal_handler(signum: int, frame: object) -> None:
    """Signal handler for SIGTERM/SIGINT: clean up servers and re-raise."""
    _cleanup_all_servers()
    # Re-raise the signal with default handler
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


# ── Register cleanup ──────────────────────────────────────────────────────────

atexit.register(_cleanup_all_servers)

# Register signal handlers only when running in the main thread
# (avoids ValueError: signal only works in main thread)
try:
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
except ValueError:
    # Not main thread — skip signal registration
    pass
