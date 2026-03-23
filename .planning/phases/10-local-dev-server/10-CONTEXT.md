# Phase 10: Local Dev Server - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Start, track, and stop local Next.js dev servers for generated apps. Two MCP tools (`waf_start_dev_server`, `waf_stop_dev_server`) plus internal lifecycle management (PID registry, orphan cleanup on shutdown). This phase does NOT change the pipeline execution flow — it provides post-generation local preview.

</domain>

<decisions>
## Implementation Decisions

### Server Readiness Detection
- Parse `npm run dev` stdout for the Next.js ready message: `Ready in Xms` or `Local: http://localhost:XXXX`
- Extract the actual port from stdout (Next.js auto-selects a free port via `--port 0` or detects conflicts)
- Use `subprocess.Popen` (not `subprocess.run`) — the dev server is a long-running process
- Readiness timeout: 30 seconds. If no ready signal in stdout within 30s, return error
- Polling approach: read stdout line-by-line in a background thread, set a `threading.Event` when ready pattern matches
- Do NOT assume port 3000 — always detect from stdout. Pass `--port 0` to let Next.js pick a free port

### PID Registry
- Module-level dict: `_DEV_SERVERS: dict[str, DevServerInfo]` where DevServerInfo holds pid, port, url, run_id, started_at
- Thread-safe via `threading.Lock` (same pattern as `_progress_store.py`)
- Duplicate prevention: if run_id already has a running server (process alive), return existing URL
- Stale detection: before returning "already running", verify process is still alive via `os.kill(pid, 0)`

### Orphan Cleanup Strategy
- Register `atexit` handler that sends SIGTERM to all tracked servers
- SIGTERM first, wait 5 seconds, then SIGKILL for any survivors
- Also register signal handlers for SIGINT/SIGTERM on the MCP server process itself
- `waf_stop_dev_server` sends SIGTERM to a specific server by run_id
- Cleanup is best-effort — if the MCP server crashes hard (SIGKILL), orphans may remain
- Users can always `kill` manually; the tool response includes the PID for reference

### Port Detection Strategy
- Start `npm run dev -- --port 0` to let Node.js pick a free port automatically
- Parse stdout for `http://localhost:XXXX` using regex
- If `--port 0` is not supported by the Next.js version, fall back to scanning ports 3000-3010 for a free one using `socket.bind()`
- Return the detected URL in the tool response

### Tool Behavior
- `waf_start_dev_server(run_id)`: Start dev server for a completed pipeline run. Resolves project dir from run_id. Returns URL when ready or error if timeout/not found.
- `waf_stop_dev_server(run_id)`: Stop the dev server for a run. Returns confirmation or "not running" message.
- Both tools return structured markdown consistent with the status formatter patterns (✓/✗ symbols).

### Claude's Discretion
- Exact stdout parsing regex for Next.js ready detection
- Whether to use `atexit` vs signal handler vs both for cleanup
- DevServerInfo dataclass structure
- Error message formatting

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. User trusts Claude to make reasonable defaults based on existing patterns.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `web_app_factory/_progress_store.py`: Thread-safe singleton pattern with `threading.Lock` — reuse for PID registry
- `web_app_factory/_pipeline_bridge.py`: `_ACTIVE_RUNS` dict pattern — similar to dev server tracking
- `web_app_factory/_status_formatter.py`: Markdown formatting with ✓/✗ symbols — reuse for tool responses
- `web_app_factory/_input_validator.py`: `validate_slug` — useful for run_id validation

### Established Patterns
- All subprocess calls use list args (no shell=True) — enforced by test_subprocess_audit.py
- Module-level singletons with `get_*()` accessor functions
- Frozen dataclasses for immutable records (DeployResult, GateResult, ProgressEvent)

### Integration Points
- `waf_start_dev_server` and `waf_stop_dev_server` register on `web_app_factory/mcp_server.py`
- Dev server module lives in `web_app_factory/_dev_server.py` (new file)
- `output/` directory contains generated apps — dev server resolves project path from here
- `waf_get_status` could optionally show dev server URL if running

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-local-dev-server*
*Context gathered: 2026-03-23*
