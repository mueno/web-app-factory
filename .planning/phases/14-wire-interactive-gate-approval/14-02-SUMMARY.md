---
phase: 14-wire-interactive-gate-approval
plan: "02"
subsystem: pipeline-bridge
tags: [interactive, gate, bridge, tdd, integration-test]
dependency_graph:
  requires: [14-01]
  provides: [interactive_mode-wiring, gate_waiting-event, approve-reject-e2e]
  affects:
    - web_app_factory/_pipeline_bridge.py
    - tools/contract_pipeline_runner.py
    - tests/test_pipeline_bridge.py
    - tests/test_contract_runner.py
    - tests/test_interactive_gate_flow.py
tech_stack:
  added: []
  patterns: [tdd-red-green, threading-integration-test, kwarg-forwarding]
key_files:
  created:
    - tests/test_interactive_gate_flow.py
  modified:
    - web_app_factory/_pipeline_bridge.py
    - tools/contract_pipeline_runner.py
    - tests/test_pipeline_bridge.py
    - tests/test_contract_runner.py
decisions:
  - interactive_mode forwarded unconditionally in pipeline_kwargs (not conditional like company_name) — always has a bool value
  - _run_gate_checks always passes interactive=interactive_mode and run_id=run_id to run_mcp_approval_gate (even when False/"") — simpler call site
  - gate_waiting event emitted BEFORE entering poll loop so waf_get_status shows paused state immediately
  - Integration tests use wraps= on _poll_mcp_gate_file to override poll_interval=0.1s without changing real logic
  - _setup() helper pattern: import run_pipeline THEN call _clear_registry() — necessary because module-level executor imports fire on first import, not on setup_method call
metrics:
  duration: 416s
  completed_date: "2026-03-24"
  tasks_completed: 2
  files_modified: 5
---

# Phase 14 Plan 02: Interactive Mode Wiring Summary

**One-liner:** Wired interactive_mode through _pipeline_bridge -> run_pipeline -> _run_gate_checks -> run_mcp_approval_gate, closing BREAK-01 (mode='interactive' silently dropped), and proved the full approve/reject flow with a threading-based integration test.

## Objective

Close BREAK-01 by forwarding `interactive_mode` from the MCP bridge through the pipeline runner to `run_mcp_approval_gate`. Emit a `gate_waiting` progress event so `waf_get_status` shows the pipeline is paused. Prove the full flow (bridge -> runner -> gate -> file -> resume) with integration tests.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| RED | Add failing tests for interactive_mode forwarding (bridge + runner) | abfb282 | tests/test_pipeline_bridge.py, tests/test_contract_runner.py |
| GREEN | Wire interactive_mode through bridge and runner; emit gate_waiting event | 5cdd826 | web_app_factory/_pipeline_bridge.py, tools/contract_pipeline_runner.py, tests/test_contract_runner.py |
| Task 2 | Integration tests: approve/reject/auto-mode end-to-end flow | 4a34dfd | tests/test_interactive_gate_flow.py |

## Decisions Made

1. **interactive_mode forwarded unconditionally** — Unlike `company_name` (forwarded only if truthy), `interactive_mode` is always included in `pipeline_kwargs` as `(mode == "interactive")`. This avoids a None/missing default issue and makes the calling convention explicit.

2. **_run_gate_checks always passes interactive/run_id** — Even when `interactive_mode=False` and `run_id=""`, the call to `run_mcp_approval_gate` always includes both kwargs. The function signature uses defaults so this is backward compatible. Existing tests were updated to expect the new call signature.

3. **gate_waiting emitted before poll** — The `gate_waiting` progress event is emitted before entering `_poll_mcp_gate_file` so that a call to `waf_get_status` during the poll window will show the pipeline is paused waiting for human approval.

4. **_setup() pattern for test isolation** — The `TestInteractiveGate._setup()` helper imports `run_pipeline` (triggering module-level executor registrations) THEN calls `_clear_registry()`. This is necessary because `tools.contract_pipeline_runner` registers executors on first import; `setup_method` runs before the import, so the registry is empty when cleared but then gets populated by the import. The pattern follows `TestRunPipeline`.

5. **Integration tests use wraps= with fast poll_interval** — `_poll_mcp_gate_file` is patched with `wraps=_wrap_poll_with_fast_interval(gate_dir)` which calls the real function but overrides `poll_interval=0.1s` and `timeout_seconds=5.0`. This keeps tests fast (<1s total) without changing production behavior.

## Test Coverage

| Test Class | Tests Added | Coverage |
|-----------|-------------|----------|
| TestInteractiveModeForwarded | 2 | bridge forwards interactive_mode=True/False in pipeline_kwargs |
| TestInteractiveGate | 4 | interactive=True forwarded to gate; backward compat; rejection fails; gate_waiting emitted |
| TestInteractiveGateFlow | 3 | E2E: approve file -> completed; reject file -> failed; auto mode uses legacy path |

Total: 85 tests pass (up from 76 before this plan, +9 new tests).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated TestNewGateDispatch.test_gate_dispatch_mcp_approval assertion**
- **Found during:** Task 1 GREEN phase regression check
- **Issue:** Existing test used `assert_called_once_with(phase_id="3", project_dir=...)` but new code always passes `interactive=False, run_id=""` kwargs. Test was asserting old call signature.
- **Fix:** Updated assertion to `assert_called_once_with(phase_id="3", project_dir=..., interactive=False, run_id="")`.
- **Files modified:** tests/test_contract_runner.py
- **Commit:** 5cdd826

### Out-of-scope Pre-existing Failure

`tests/test_factory_cli.py::TestFactoryCLIFlags::test_deploy_target_github_pages` was already failing before this plan (confirmed via git stash). It tests that `github-pages` is a valid deploy target, but the CLI only accepts `vercel, gcp, aws, local`. Deferred to `deferred-items.md`.

## Self-Check

Files exist:
- [x] `web_app_factory/_pipeline_bridge.py` — interactive_mode forwarded in pipeline_kwargs
- [x] `tools/contract_pipeline_runner.py` — interactive_mode param in run_pipeline and _run_gate_checks; gate_waiting event
- [x] `tests/test_pipeline_bridge.py` — TestInteractiveModeForwarded class
- [x] `tests/test_contract_runner.py` — TestInteractiveGate class
- [x] `tests/test_interactive_gate_flow.py` — End-to-end integration test

Commits exist:
- [x] abfb282 — test(14-02): add failing tests for interactive_mode wiring
- [x] 5cdd826 — feat(14-02): wire interactive_mode through bridge -> runner -> gate
- [x] 4a34dfd — test(14-02): add integration tests for full interactive gate approve/reject flow

## Self-Check: PASSED
