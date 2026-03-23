# Phase 10: Local Dev Server - Research

**Researched:** 2026-03-23
**Domain:** Python subprocess lifecycle management, Next.js 16 stdout parsing, threading
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Server readiness detection: Parse `npm run dev` stdout for `Ready in Xms` or `Local: http://localhost:XXXX`
- Extract actual port from stdout — never assume port 3000
- Use `subprocess.Popen` (not `subprocess.run`) — long-running process
- Readiness timeout: 30 seconds; return error if no ready signal
- Polling approach: read stdout line-by-line in background thread; set `threading.Event` when pattern matches
- Pass `--port 0` to Next.js to let it pick a free port
- PID registry: module-level `_DEV_SERVERS: dict[str, DevServerInfo]`, thread-safe via `threading.Lock`
- DevServerInfo holds: pid, port, url, run_id, started_at
- Duplicate prevention: if run_id already has a running server (process alive), return existing URL
- Stale detection: verify liveness via `os.kill(pid, 0)` before returning "already running"
- Orphan cleanup: `atexit` handler sends SIGTERM to all tracked servers
- SIGTERM first, wait 5 seconds, then SIGKILL for survivors
- Also register signal handlers for SIGINT/SIGTERM on the MCP server process
- `waf_stop_dev_server` sends SIGTERM to specific server by run_id
- Cleanup is best-effort; tool response includes PID for reference
- Port detection: `npm run dev -- --port 0`, parse stdout for `http://localhost:XXXX` via regex
- Fallback if `--port 0` unsupported: scan ports 3000-3010 with `socket.bind()`
- `waf_start_dev_server(run_id)`: resolves project dir from run_id, returns URL or error
- `waf_stop_dev_server(run_id)`: stops server, returns confirmation or "not running"
- Responses use structured markdown consistent with `_status_formatter.py` (✓/✗ symbols)

### Claude's Discretion
- Exact stdout parsing regex for Next.js ready detection
- Whether to use `atexit` vs signal handler vs both for cleanup
- DevServerInfo dataclass structure
- Error message formatting

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LDEV-01 | Start local dev server (`npm run dev`) with auto-detected free port | `--port 0` confirmed working in Next.js 16.2.1; assigns ephemeral port (e.g., 59827) |
| LDEV-02 | Return localhost URL when server is ready (port detection from stdout) | `- Local: http://localhost:XXXX` pattern confirmed in Next.js 16 stdout |
| LDEV-03 | Track running servers by run_id; prevent duplicate starts | `os.kill(pid, 0)` liveness check pattern confirmed; module-level dict with Lock |
| LDEV-04 | Clean up orphan dev server processes on MCP server shutdown | `atexit` + SIGTERM/SIGKILL + `start_new_session=True` + `os.killpg()` pattern confirmed |
| TOOL-06 | `waf_start_dev_server` MCP tool: starts dev server, returns URL | Follows existing `@mcp.tool()` pattern in `mcp_server.py` |
| TOOL-07 | `waf_stop_dev_server` MCP tool: stops dev server, orphan cleanup | Same registration pattern; calls into `_dev_server.py` module |
</phase_requirements>

## Summary

Phase 10 introduces two MCP tools (`waf_start_dev_server`, `waf_stop_dev_server`) that manage the lifecycle of local Next.js dev server processes. The implementation requires careful subprocess management because `npm run dev` is a long-running process that spawns child processes (npm -> node -> next), meaning naive `proc.terminate()` only kills the npm wrapper and leaves orphaned node/next processes running.

The core technical challenge is threefold: (1) detecting server readiness from stdout in a non-blocking way, (2) tracking and deduplicating dev servers by run_id, and (3) ensuring all child processes are cleaned up on MCP server shutdown. Research confirms that `start_new_session=True` combined with `os.killpg()` is the correct pattern for killing the entire process tree. Next.js 16.2.1 (the version used in generated apps) outputs `- Local: http://localhost:XXXX` followed by `✓ Ready in Xms` as two distinct lines in its startup sequence.

The new module `web_app_factory/_dev_server.py` follows established project patterns: module-level singleton dict with `threading.Lock` (identical to `_progress_store.py`), frozen dataclass for DevServerInfo (identical to `DeployResult` and `GateResult`), and `@mcp.tool()` registration in `mcp_server.py` (identical to existing tools).

**Primary recommendation:** Implement `_dev_server.py` as a single module with a `DevServerRegistry` class mirroring `ProgressStore` architecture, using `subprocess.Popen` with `start_new_session=True` and `os.killpg()` for process group cleanup.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `subprocess` | stdlib | Spawn and manage npm run dev | Already used throughout project; MCPI-04 audit enforced |
| `threading` | stdlib | Background stdout reader thread + Lock for registry | Used in `_progress_store.py`; same pattern |
| `os` (signal/kill) | stdlib | `os.kill(pid, 0)` liveness check; `os.killpg()` group kill | Standard POSIX process management |
| `signal` | stdlib | SIGTERM/SIGKILL constants; register SIGINT/SIGTERM handlers | Available: SIGTERM=15, SIGKILL=9, SIGINT=2 |
| `atexit` | stdlib | Register shutdown cleanup handler | Standard Python exit hook mechanism |
| `re` | stdlib | Parse `- Local: http://localhost:XXXX` and `Ready in Xms` from stdout | Pattern verified against Next.js 16.2.1 output |
| `dataclasses` | stdlib | `DevServerInfo` frozen dataclass | Project convention: frozen=True for all records |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `socket` | stdlib | Free port fallback scan | Only if `--port 0` fails (unlikely with Next.js 16) |
| `pathlib` | stdlib | `Path(project_dir) / "docs/pipeline/runs/{run_id}/state.json"` | Resolve project_dir from run_id |

**Installation:** No new dependencies. All stdlib.

## Architecture Patterns

### Recommended Project Structure
```
web_app_factory/
├── _dev_server.py       # New: dev server registry, start/stop logic
├── mcp_server.py        # Modified: add waf_start_dev_server, waf_stop_dev_server tools
└── (existing files unchanged)
```

### Pattern 1: DevServerRegistry (mirrors ProgressStore)
**What:** Module-level singleton with `threading.Lock` protecting a `dict[str, DevServerInfo]`
**When to use:** All access to running server state

```python
# Source: modeled on web_app_factory/_progress_store.py ProgressStore class
from __future__ import annotations

import atexit
import os
import re
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class DevServerInfo:
    run_id: str
    pid: int
    port: int
    url: str
    started_at: str
    project_dir: str


class DevServerRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._servers: dict[str, DevServerInfo] = {}

    def register(self, info: DevServerInfo) -> None:
        with self._lock:
            self._servers[info.run_id] = info

    def get(self, run_id: str) -> Optional[DevServerInfo]:
        with self._lock:
            return self._servers.get(run_id)

    def remove(self, run_id: str) -> Optional[DevServerInfo]:
        with self._lock:
            return self._servers.pop(run_id, None)

    def all_servers(self) -> list[DevServerInfo]:
        with self._lock:
            return list(self._servers.values())


_REGISTRY = DevServerRegistry()


def get_registry() -> DevServerRegistry:
    return _REGISTRY
```

### Pattern 2: Next.js 16 Readiness Detection

**What:** Background thread reads stdout line-by-line; sets `threading.Event` when ready
**When to use:** After `subprocess.Popen()` call, before returning URL to caller

**VERIFIED Next.js 16.2.1 stdout (actual output captured from generated app):**
```
▲ Next.js 16.2.1 (Turbopack)
- Local:         http://localhost:59827
- Network:       http://192.168.68.73:59827
✓ Ready in 197ms
- Experiments (use with caution):
  ✓ optimizeCss
  · optimizePackageImports
```

```python
# Source: verified against Next.js 16.2.1 actual output (2026-03-23)
import re

_LOCAL_URL_RE = re.compile(r"-\s+Local:\s+(http://localhost:(\d+))")
_READY_RE = re.compile(r"(?:✓\s+)?Ready in \d+")

def _read_until_ready(
    proc: subprocess.Popen,
    ready_event: threading.Event,
    result_holder: list,  # mutable container for [url, port]
    timeout: float = 30.0,
) -> None:
    """Background thread: read stdout lines until ready signal or EOF."""
    try:
        for line in proc.stdout:
            m = _LOCAL_URL_RE.search(line)
            if m and not result_holder:
                result_holder.append(m.group(1))   # url
                result_holder.append(int(m.group(2)))  # port
            if _READY_RE.search(line) and result_holder:
                ready_event.set()
                break
    except (ValueError, OSError):
        pass  # Process closed stdout — already stopping
```

### Pattern 3: Process Spawning with Session Isolation

**What:** `start_new_session=True` creates a new process group, enabling `os.killpg()` for complete tree kill
**When to use:** Always — npm spawns node which spawns next; only killing npm leaves orphans

**VERIFIED behavior:** Without `start_new_session=True`, the child process shares our process group (PGID). With it, the child gets its own PGID equal to its PID.

```python
# Source: verified via Python subprocess testing (2026-03-23)
proc = subprocess.Popen(
    ["npm", "run", "dev", "--", "--port", "0"],
    cwd=project_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,   # merge stderr into stdout
    text=True,
    start_new_session=True,     # CRITICAL: new process group for full tree kill
)
```

### Pattern 4: Process Group Kill (SIGTERM → SIGKILL)

**What:** Two-phase termination to kill the entire npm/node/next process tree
**When to use:** `waf_stop_dev_server` and atexit cleanup

```python
# Source: verified POSIX process management pattern
import os, signal, time

def _terminate_server(proc: subprocess.Popen, timeout: float = 5.0) -> None:
    """Send SIGTERM to process group; escalate to SIGKILL after timeout."""
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return  # Already gone

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.2)

    # Escalate
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(timeout=2.0)
```

### Pattern 5: Liveness Check Before "Already Running" Response

**What:** `os.kill(pid, 0)` probes process existence without sending a real signal
**When to use:** Before returning existing URL from duplicate `waf_start_dev_server` call

```python
# Source: POSIX standard; verified on macOS Python 3.14
def _is_process_alive(pid: int) -> bool:
    """Return True if process with given PID is alive."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False  # No such process
    except PermissionError:
        return True   # Exists but we lack permission (treat as alive)
```

### Pattern 6: Resolving project_dir from run_id

**What:** Scan `output/*/docs/pipeline/runs/{run_id}/state.json` for the stored `project_dir`
**When to use:** `waf_start_dev_server(run_id)` needs to know where the app lives

**VERIFIED:** `state.json` contains `"project_dir": "/absolute/path/to/output/appname"`

```python
# Source: verified from output/airbnb/docs/pipeline/runs/.../state.json
import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent

def _resolve_project_dir(run_id: str) -> Optional[Path]:
    """Find project_dir for a run_id by scanning output/ state files."""
    output_dir = _PROJECT_ROOT / "output"
    if not output_dir.exists():
        return None
    for project_dir in output_dir.iterdir():
        if not project_dir.is_dir():
            continue
        state_file = project_dir / "docs" / "pipeline" / "runs" / run_id / "state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                return Path(data["project_dir"])
            except (KeyError, json.JSONDecodeError, OSError):
                continue
    return None
```

### Pattern 7: atexit + Signal Handler Registration

**What:** Belt-and-suspenders cleanup: `atexit` for normal exits, signal handlers for SIGTERM/SIGINT
**When to use:** Module initialization (one-time setup in `_dev_server.py`)

```python
# Source: Python docs atexit + signal modules
import atexit, signal

def _cleanup_all_servers() -> None:
    """atexit handler: terminate all tracked dev servers."""
    for info in get_registry().all_servers():
        try:
            proc_ref = _PROC_MAP.get(info.run_id)
            if proc_ref is not None:
                _terminate_server(proc_ref, timeout=5.0)
        except Exception:
            pass  # Best-effort

atexit.register(_cleanup_all_servers)

def _signal_handler(signum, frame):
    _cleanup_all_servers()
    # Re-raise to allow default handling
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)

signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)
```

**NOTE:** `_PROC_MAP: dict[str, subprocess.Popen]` must be a separate module-level dict alongside `_REGISTRY` because `DevServerInfo` is a frozen dataclass (cannot hold mutable Popen reference). The Popen object is not serializable and should not be in the frozen record.

### Pattern 8: MCP Tool Registration

**What:** `@mcp.tool()` on async functions in `mcp_server.py`
**When to use:** Both `waf_start_dev_server` and `waf_stop_dev_server`

```python
# Source: existing web_app_factory/mcp_server.py pattern
@mcp.tool()
async def waf_start_dev_server(run_id: str) -> str:
    """Start a local dev server for a completed pipeline run.

    Args:
        run_id: The run identifier from waf_generate_app.

    Returns:
        Formatted markdown with localhost URL when ready, or error message.
    """
    from web_app_factory._dev_server import start_dev_server  # noqa: PLC0415
    return await asyncio.get_event_loop().run_in_executor(
        None, start_dev_server, run_id
    )


@mcp.tool()
async def waf_stop_dev_server(run_id: str) -> str:
    """Stop a running local dev server for a pipeline run.

    Args:
        run_id: The run identifier of the running server to stop.

    Returns:
        Confirmation or "not running" message.
    """
    from web_app_factory._dev_server import stop_dev_server  # noqa: PLC0415
    return stop_dev_server(run_id)
```

**IMPORTANT:** `start_dev_server` blocks for up to 30 seconds waiting for ready signal. It must run in an executor to avoid blocking the asyncio event loop.

### Anti-Patterns to Avoid

- **`proc.terminate()` without `start_new_session=True`:** Kills only the npm wrapper; leaves node/next child processes as orphans. Use `os.killpg()` instead.
- **`shell=True` in Popen:** Violates MCPI-04 security rule; caught by `test_subprocess_audit.py` CI test.
- **Assuming port 3000:** Next.js with `--port 0` selects an ephemeral port. Always parse stdout.
- **Calling `communicate()` on the Popen process:** `communicate()` waits for process termination. Dev server never terminates normally; use background thread to read stdout instead.
- **Storing `subprocess.Popen` in frozen dataclass:** Popen is mutable; use a separate `_PROC_MAP` dict alongside the frozen `DevServerInfo` registry.
- **Not merging stderr into stdout:** Next.js outputs all startup messages to stdout, but merging with `stderr=subprocess.STDOUT` ensures no output is missed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Free port selection | `socket.bind()` loop over port range | `npm run dev -- --port 0` | Node.js native; atomic; no TOCTOU race |
| Process tree kill | Walking `/proc` to find children | `os.killpg()` with `start_new_session=True` | Single syscall; works on macOS/Linux |
| Stdout non-blocking read | `fcntl` O_NONBLOCK + polling | Background `threading.Thread` reading line-by-line | Simpler; proven pattern in codebase |
| Process liveness | `/proc/{pid}/status` parsing | `os.kill(pid, 0)` | POSIX standard; one line |

**Key insight:** Node.js process management must account for the npm wrapper spawning child processes. The entire process group must be targeted for termination, not just the process we spawned.

## Common Pitfalls

### Pitfall 1: npm Spawns Child Processes
**What goes wrong:** `proc.terminate()` kills only npm (the shell/wrapper). The actual `next dev` node process becomes an orphan, keeping the port bound.
**Why it happens:** `npm run dev` internally spawns `node_modules/.bin/next dev`. These are separate processes.
**How to avoid:** Always use `subprocess.Popen(..., start_new_session=True)` and terminate with `os.killpg(os.getpgid(proc.pid), signal.SIGTERM)`.
**Warning signs:** Port remains bound after calling `waf_stop_dev_server`; `ps aux | grep next` shows lingering processes.

### Pitfall 2: stdout Buffering
**What goes wrong:** Readline on subprocess stdout blocks indefinitely because Node.js buffers output when not writing to a TTY.
**Why it happens:** Python line-by-line reading depends on newlines being flushed; node processes may buffer output.
**How to avoid:** Next.js 16 with Turbopack outputs to stdout without buffering (verified). Do not rely on `bufsize=0` for text mode. Use `text=True` with default buffering.
**Warning signs:** Readiness event never fires despite server being up; `curl localhost:XXXX` succeeds but Python never got the output.

### Pitfall 3: Stale PID Registry After MCP Server Restart
**What goes wrong:** `_DEV_SERVERS` is in-memory only. After MCP server restart, the registry is empty but old dev servers may still be running from a previous session.
**Why it happens:** Module-level state does not persist across processes.
**How to avoid:** This is known and acceptable per user decision ("Cleanup is best-effort"). The tool response includes PID; users can `kill` manually. Do not attempt persistence.
**Warning signs:** User calls `waf_start_dev_server` for a run_id that already has a dev server running from a prior session; a duplicate server starts on a different port.

### Pitfall 4: Threading.Event Timeout vs Process Death
**What goes wrong:** The background stdout-reader thread never fires the ready event if the process crashes early (bad package.json, missing node_modules, etc.).
**Why it happens:** `proc.stdout` reaches EOF on process exit, causing the `for line in proc.stdout` loop to terminate without setting the event.
**How to avoid:** After `ready_event.wait(timeout=30)`, also check `proc.poll()` to distinguish "timed out" from "process exited with error". Include exit code in error message.
**Warning signs:** Timeout after exactly 30 seconds for apps missing `node_modules`.

### Pitfall 5: signal Handler in Non-Main Thread
**What goes wrong:** `signal.signal()` raises `ValueError: signal only works in main thread of the main interpreter`.
**Why it happens:** Signal handlers can only be set from the main thread. The MCP server runs signal-sensitive startup from the main thread, but if `_dev_server.py` is imported lazily from a worker thread, signal registration fails.
**How to avoid:** Register signal handlers at module import time (when the module is first imported by the MCP server's main thread). Use `try/except ValueError` to gracefully skip if called from a non-main thread.
**Warning signs:** `ValueError` exception during import or startup.

## Code Examples

Verified patterns from official sources and project codebase:

### Start Dev Server (complete flow)
```python
# Source: verified against Next.js 16.2.1 actual output + Python subprocess docs
import subprocess, threading, re, os, signal, time
from pathlib import Path

_LOCAL_URL_RE = re.compile(r"-\s+Local:\s+(http://localhost:(\d+))")
_READY_RE = re.compile(r"(?:✓\s+)?Ready in \d+")
_READINESS_TIMEOUT = 30.0

def start_dev_server(run_id: str) -> str:
    """Start dev server for run_id. Returns markdown with URL or error."""
    registry = get_registry()

    # Duplicate check
    existing = registry.get(run_id)
    if existing is not None and _is_process_alive(existing.pid):
        return f"✓ Dev server already running\n\n**URL:** {existing.url}\n**PID:** {existing.pid}"

    # Remove stale entry
    if existing is not None:
        registry.remove(run_id)
        _PROC_MAP.pop(run_id, None)

    # Resolve project directory
    project_dir = _resolve_project_dir(run_id)
    if project_dir is None:
        return f"✗ Run `{run_id}` not found. Use `waf_list_runs()` to see available runs."

    # Start process
    proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", "0"],
        cwd=str(project_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )

    # Background readiness detection
    ready_event = threading.Event()
    result_holder = []  # [url, port]

    reader_thread = threading.Thread(
        target=_read_until_ready,
        args=(proc, ready_event, result_holder),
        daemon=True,
    )
    reader_thread.start()

    # Wait for ready signal
    fired = ready_event.wait(timeout=_READINESS_TIMEOUT)

    if not fired:
        # Check if process died
        exit_code = proc.poll()
        if exit_code is not None:
            return f"✗ Dev server exited with code {exit_code}. Check node_modules is installed."
        # Timeout
        proc.terminate()
        return f"✗ Dev server did not become ready within {_READINESS_TIMEOUT:.0f}s."

    url, port = result_holder[0], result_holder[1]
    info = DevServerInfo(
        run_id=run_id,
        pid=proc.pid,
        port=port,
        url=url,
        started_at=datetime.now(tz=timezone.utc).isoformat(),
        project_dir=str(project_dir),
    )
    registry.register(info)
    _PROC_MAP[run_id] = proc

    return f"✓ Dev server started\n\n**URL:** {url}\n**PID:** {proc.pid}\n**Run ID:** `{run_id}`"
```

### Stop Dev Server
```python
# Source: POSIX process management pattern
def stop_dev_server(run_id: str) -> str:
    """Stop dev server for run_id. Returns confirmation markdown."""
    registry = get_registry()
    info = registry.remove(run_id)
    proc = _PROC_MAP.pop(run_id, None)

    if info is None:
        return f"Dev server for `{run_id}` is not running."

    if proc is not None:
        _terminate_server(proc, timeout=5.0)
        return f"✓ Dev server stopped\n\n**Run ID:** `{run_id}`\n**Was running on:** {info.url}"

    # info exists but proc reference lost (e.g., after module reload)
    # Try killing by PID directly
    try:
        os.kill(info.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    return f"✓ Dev server process {info.pid} terminated\n\n**Run ID:** `{run_id}`"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `proc.terminate()` for npm | `os.killpg()` with `start_new_session=True` | Node.js ecosystem growth | Required for npm process tree |
| Port 3000 assumption | `--port 0` with stdout parsing | Next.js added multi-server support | Port 3000 often occupied in dev |
| `subprocess.run()` for long-running | `subprocess.Popen()` with background thread | Long-running processes always needed this | `run()` waits for completion |

**Verified Next.js version in generated apps:** 16.2.1 (from `output/airbnb/package.json`)
**`--port 0` confirmed working:** Yes — assigns ephemeral port (verified: 59827 in test)
**Exact ready signal lines:**
1. `- Local:         http://localhost:XXXX` (port detection)
2. `✓ Ready in XXXms` (readiness confirmation)

## Open Questions

1. **Non-main thread signal registration**
   - What we know: MCP server's main thread imports modules at startup
   - What's unclear: Whether FastMCP's asyncio machinery ever imports `_dev_server` from a non-main thread
   - Recommendation: Wrap signal registration in `threading.current_thread() is threading.main_thread()` check; log warning if skipping

2. **Stdout encoding for non-ASCII project paths**
   - What we know: `text=True` uses locale encoding; Next.js outputs ASCII-only startup messages
   - What's unclear: Whether non-ASCII project directory paths in stdout could cause decode errors
   - Recommendation: Use `text=True, errors='replace'` or verify `encoding='utf-8'` is safe on macOS

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (confirmed in pyproject.toml) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `python3 -m pytest tests/test_dev_server.py -q` |
| Full suite command | `python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LDEV-01 | `start_dev_server` spawns `npm run dev --port 0` with `start_new_session=True` | unit (mock Popen) | `pytest tests/test_dev_server.py::TestStartDevServer::test_spawns_npm_with_port_zero -x` | ❌ Wave 0 |
| LDEV-02 | Returns `http://localhost:XXXX` URL parsed from stdout | unit (mock Popen stdout) | `pytest tests/test_dev_server.py::TestStartDevServer::test_detects_url_from_stdout -x` | ❌ Wave 0 |
| LDEV-03 | Duplicate call returns existing URL without new Popen | unit | `pytest tests/test_dev_server.py::TestStartDevServer::test_duplicate_returns_existing -x` | ❌ Wave 0 |
| LDEV-03 | Stale (dead) PID triggers new server start | unit (`os.kill` mocked) | `pytest tests/test_dev_server.py::TestStartDevServer::test_stale_pid_restarts -x` | ❌ Wave 0 |
| LDEV-04 | `stop_dev_server` calls `os.killpg` with SIGTERM | unit (mock `os.killpg`) | `pytest tests/test_dev_server.py::TestStopDevServer::test_sigterm_on_stop -x` | ❌ Wave 0 |
| LDEV-04 | atexit handler terminates all registered servers | unit | `pytest tests/test_dev_server.py::TestCleanup::test_atexit_cleans_all -x` | ❌ Wave 0 |
| TOOL-06 | `waf_start_dev_server` registered in mcp_server with `waf_` prefix | static (existing test) | `pytest tests/test_mcp_server_tool_names.py -x` | ✅ (will auto-catch after registration) |
| TOOL-07 | `waf_stop_dev_server` registered in mcp_server with `waf_` prefix | static (existing test) | `pytest tests/test_mcp_server_tool_names.py -x` | ✅ (will auto-catch after registration) |
| LDEV-02 | Readiness timeout after 30s returns error | unit | `pytest tests/test_dev_server.py::TestStartDevServer::test_timeout_returns_error -x` | ❌ Wave 0 |
| LDEV-04 | No `shell=True` in new module | static (existing test) | `pytest tests/test_subprocess_audit.py -x` | ✅ (auto-scans `web_app_factory/`) |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_dev_server.py tests/test_mcp_server_tool_names.py tests/test_subprocess_audit.py -q`
- **Per wave merge:** `python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_dev_server.py` — covers LDEV-01 through LDEV-04 (unit tests with mocked Popen)
- [ ] `web_app_factory/_dev_server.py` — the implementation module itself

*(Existing infrastructure: pytest installed, conftest.py present, subprocess audit test already covers new code automatically)*

## Sources

### Primary (HIGH confidence)
- Direct code inspection — `web_app_factory/_progress_store.py` (threading.Lock singleton pattern)
- Direct code inspection — `web_app_factory/_pipeline_bridge.py` (ThreadPoolExecutor, module-level dict)
- Direct code inspection — `web_app_factory/mcp_server.py` (@mcp.tool() registration pattern)
- Direct code inspection — `tools/deploy_providers/base.py` (frozen dataclass convention)
- Live test — Next.js 16.2.1 actual stdout captured from `output/airbnb/` app (2026-03-23)
- Live test — `--port 0` behavior verified: assigns ephemeral port 59827
- Live test — `start_new_session=True` + `os.killpg()` verified functional on macOS

### Secondary (MEDIUM confidence)
- Python stdlib documentation — `subprocess.Popen`, `os.killpg`, `os.kill(pid, 0)`, `atexit`, `threading.Event`
- Python stdlib documentation — `signal.signal` main-thread restriction (verified in Python 3.14 behavior docs)

### Tertiary (LOW confidence)
- None — all critical findings verified from primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib; project already uses these modules
- Architecture: HIGH — directly mirrors existing `_progress_store.py` and `deploy_providers/base.py` patterns
- Next.js stdout patterns: HIGH — captured from actual Next.js 16.2.1 run on the generated app
- Process management: HIGH — verified `start_new_session=True` + `os.killpg()` on macOS
- Pitfalls: HIGH — most derived from verified code behavior, not speculation

**Research date:** 2026-03-23
**Valid until:** 2026-06-23 (Next.js output format stable; stdlib patterns permanent)
