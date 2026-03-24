---
phase: 14-wire-interactive-gate-approval
plan: "01"
subsystem: gate-approval
tags: [mcp, gate, interactive, polling, settings]
dependency_graph:
  requires: []
  provides: [GATE_RESPONSES_DIR, _poll_mcp_gate_file, interactive-gate-routing]
  affects: [config/settings.py, tools/gates/mcp_approval_gate.py, web_app_factory/mcp_server.py]
tech_stack:
  added: []
  patterns: [file-based-polling, shared-path-constant, tdd-red-green]
key_files:
  created: []
  modified:
    - config/settings.py
    - tools/gates/mcp_approval_gate.py
    - web_app_factory/mcp_server.py
    - tests/test_mcp_approval_gate.py
decisions:
  - GATE_RESPONSES_DIR is the single source of truth for gate-response path, env-overridable via WEB_FACTORY_GATE_RESPONSES_DIR
  - _poll_mcp_gate_file timeout=0 means poll indefinitely, matching legacy approve_gate behavior
  - Gate file consumed (deleted) after read via unlink(missing_ok=True) to prevent double-processing
  - interactive/run_id params are keyword-only with defaults so all existing callers remain unchanged
metrics:
  duration: 155s
  completed_date: "2026-03-24"
  tasks_completed: 1
  files_modified: 4
---

# Phase 14 Plan 01: GATE_RESPONSES_DIR Shared Constant and Interactive Gate Polling Summary

**One-liner:** Introduced GATE_RESPONSES_DIR shared path constant and _poll_mcp_gate_file file-based polling to close BREAK-02 path mismatch between waf_approve_gate writer and mcp_approval_gate reader.

## Objective

Close the path mismatch (BREAK-02) between `waf_approve_gate` (writer) and `mcp_approval_gate` (reader) by introducing a single `GATE_RESPONSES_DIR` constant. Implement the `_poll_mcp_gate_file` function that blocks the worker thread until a gate decision file appears (or times out).

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| RED | Add failing tests for _poll_mcp_gate_file, interactive routing, path consistency | e18e39f | tests/test_mcp_approval_gate.py |
| GREEN | Implement GATE_RESPONSES_DIR, _poll_mcp_gate_file, interactive routing, mcp_server fix | e7e4c5c | config/settings.py, tools/gates/mcp_approval_gate.py, web_app_factory/mcp_server.py |

## Decisions Made

1. **GATE_RESPONSES_DIR as single source of truth** — Added to `config/settings.py` as an env-overridable constant. Both `waf_approve_gate` (writer) and `_poll_mcp_gate_file` (reader) import from this single location, eliminating the BREAK-02 path mismatch.

2. **timeout=0 means poll indefinitely** — Default behavior of `_poll_mcp_gate_file` with `timeout_seconds=0` means no timeout, matching the legacy `approve_gate` behavior that also blocks indefinitely.

3. **Gate file consumed after read** — `gate_file.unlink(missing_ok=True)` is called immediately after successful JSON parse to prevent double-processing in case the pipeline is restarted.

4. **Keyword-only params with defaults** — `interactive` and `run_id` added as keyword-only params with defaults (`False` and `""`) so all existing callers (`run_mcp_approval_gate("3", dir)`) remain unchanged.

5. **Invalid JSON continues polling** — `FileNotFoundError`, `json.JSONDecodeError`, and `OSError` are caught silently; polling continues until timeout, not crash.

## Test Coverage

| Test Class | Tests Added | Coverage |
|-----------|-------------|----------|
| TestPollMcpGateFile | 7 | approve/reject/timeout/invalid-JSON/file-delete/gate_type/phase_id |
| TestInteractiveModeRouting | 4 | delegate-to-poll/empty-run_id/legacy-path/signature-unchanged |
| TestGateResponsesPathConsistency | 4 | settings-export/default-path/mcp-approval-import/env-overridable |
| Pre-existing tests | 15 | All backward-compatible — no modifications required |

Total: 44 tests pass (up from 29 before this plan).

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

Files exist:
- [x] `config/settings.py` — GATE_RESPONSES_DIR added
- [x] `tools/gates/mcp_approval_gate.py` — _poll_mcp_gate_file + interactive routing
- [x] `web_app_factory/mcp_server.py` — uses GATE_RESPONSES_DIR
- [x] `tests/test_mcp_approval_gate.py` — 3 new test classes

Commits exist:
- [x] e18e39f — test(14-01): add failing tests for interactive gate polling
- [x] e7e4c5c — feat(14-01): add GATE_RESPONSES_DIR and interactive polling gate

## Self-Check: PASSED
