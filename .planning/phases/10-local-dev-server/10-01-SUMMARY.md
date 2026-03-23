---
phase: 10-local-dev-server
plan: "01"
subsystem: infra
tags: [subprocess, threading, process-management, next.js, dev-server, pid-registry]

# Dependency graph
requires:
  - phase: 08-mcp-infrastructure-foundation
    provides: "module singleton pattern, progress store pattern, _input_validator for slug validation"
provides:
  - "DevServerRegistry: thread-safe in-memory PID registry with Lock"
  - "DevServerInfo: frozen dataclass for immutable server snapshots"
  - "start_dev_server(run_id): spawns npm run dev, detects readiness via threading.Event"
  - "stop_dev_server(run_id): sends SIGTERM to process group via os.killpg"
  - "_cleanup_all_servers: atexit + signal handler for orphan cleanup on MCP shutdown"
  - "_PROC_MAP: mutable Popen references separate from frozen registry"
affects:
  - "10-local-dev-server Plan 02 (waf_start_dev_server / waf_stop_dev_server MCP tool wiring)"
  - "mcp_server.py (tool registration in Plan 02)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thread-safe singleton registry mirroring _progress_store.py pattern"
    - "Background reader thread + threading.Event for async readiness detection"
    - "start_new_session=True on Popen for process group isolation"
    - "os.killpg for full npm/node/next process tree termination"
    - "_PROC_MAP separate from frozen dataclass registry (mutable vs immutable)"
    - "atexit + signal handlers dual cleanup strategy"

key-files:
  created:
    - web_app_factory/_dev_server.py
    - tests/test_dev_server.py
  modified: []

key-decisions:
  - "start_new_session=True on Popen: enables os.killpg to kill full npm/node/next process tree (not just npm)"
  - "Background reader thread with threading.Event: non-blocking readiness detection without polling loop"
  - "_PROC_MAP separate from DevServerInfo registry: Popen is mutable and cannot live in frozen dataclass"
  - "atexit + SIGTERM/SIGINT signal handlers: dual strategy covers graceful shutdown and signal termination"
  - "errors='replace' on Popen text=True: encoding safety for Windows npm output on non-UTF8 systems"

patterns-established:
  - "DevServerRegistry: mirrors ProgressStore singleton pattern — thread-safe dict + Lock + get_*() accessor"
  - "TDD approach: 21 failing tests committed first, then implementation — all tests pass green"

requirements-completed:
  - LDEV-01
  - LDEV-02
  - LDEV-03
  - LDEV-04

# Metrics
duration: 3min
completed: "2026-03-23"
---

# Phase 10 Plan 01: Dev Server Lifecycle Management Summary

**Thread-safe dev server registry with subprocess.Popen process group isolation, background threading.Event readiness detection, and atexit/SIGTERM cleanup for local Next.js app preview**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-23T13:21:42Z
- **Completed:** 2026-03-23T13:24:51Z
- **Tasks:** 2 (TDD RED + TDD GREEN)
- **Files modified:** 2

## Accomplishments
- Implemented `DevServerInfo` frozen dataclass and `DevServerRegistry` thread-safe singleton mirroring `_progress_store.py` pattern
- `start_dev_server` spawns `npm run dev -- --port 0` with `start_new_session=True`, background thread sets `threading.Event` when Next.js ready signal detected in stdout
- `stop_dev_server` sends `SIGTERM` to full process group via `os.killpg(pgid, SIGTERM)`, escalates to `SIGKILL` after 5s timeout
- Idempotent: returns cached URL for live servers; detects stale PIDs via `os.kill(pid, 0)` and auto-restarts
- `atexit.register(_cleanup_all_servers)` + `SIGTERM/SIGINT` signal handlers prevent orphaned Node.js processes on MCP shutdown
- 21 unit tests with mocked `Popen` covering all LDEV-01 through LDEV-04 requirements

## Task Commits

Each task was committed atomically:

1. **Task 1 (TDD RED): Failing tests for LDEV-01 through LDEV-04** - `3ab65ba` (test)
2. **Task 2 (TDD GREEN): _dev_server.py implementation** - `939e6c0` (feat)

_Note: TDD plan — RED commit first, then GREEN._

## Files Created/Modified
- `web_app_factory/_dev_server.py` — Dev server lifecycle module: registry, start, stop, cleanup (402 lines)
- `tests/test_dev_server.py` — 21 unit tests with mocked Popen for LDEV-01 through LDEV-04 (552 lines)

## Decisions Made
- `start_new_session=True` on `Popen` creates a new process group, enabling `os.killpg` to terminate the full npm/node/next tree, not just the npm wrapper process
- `_PROC_MAP` is a separate mutable `dict[str, subprocess.Popen]` because `DevServerInfo` is `frozen=True` and cannot hold mutable references
- Background reader thread approach (vs polling) reads stdout line-by-line without spinning; `threading.Event.wait(timeout)` blocks the caller cleanly
- `atexit + signal handlers` dual strategy: `atexit` covers normal exit and exceptions, signal handlers cover `kill` signals from parent process
- `errors='replace'` on `text=True` Popen: defensive encoding for npm output on non-UTF8 locales

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None - pre-existing `claude_agent_sdk` import failures in other test files are unrelated and existed before this plan.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `_dev_server.py` provides `start_dev_server` and `stop_dev_server` ready for MCP tool wiring
- Plan 02 registers `waf_start_dev_server` and `waf_stop_dev_server` on `mcp_server.py`
- No blockers — all LDEV-01 through LDEV-04 requirements met and tested

---
*Phase: 10-local-dev-server*
*Completed: 2026-03-23*
