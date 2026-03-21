---
phase: 04-ship
plan: 03
subsystem: ship-executor
tags: [legal-gate, phase-3-executor, gate-dispatch, vercel, deploy-agent, tdd]

# Dependency graph
requires:
  - phase: 04-ship
    plan: 01
    provides: run_deploy_agent, run_mcp_approval_gate, run_deployment_gate, DEPLOY_AGENT definition
  - phase: 04-ship
    plan: 02
    provides: run_lighthouse_gate, run_accessibility_gate, run_security_headers_gate, run_link_integrity_gate
provides:
  - run_legal_gate function in tools/gates/legal_gate.py
  - Phase3ShipExecutor registered as phase "3" in executor registry
  - _run_gate_checks handles 11 gate types (4 existing + 7 new)
  - _read_deployment_url helper in contract_pipeline_runner.py
  - 54 new tests (40 Task 1 + 14 Task 2 net new)
affects:
  - contract_pipeline_runner.py (7 new gate dispatchers + Phase 3 import)
  - Full pipeline now end-to-end executable for phases 1a -> 1b -> 2a -> 2b -> 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD RED-GREEN cycle for legal gate and Phase 3 executor
    - Auto-fix retry cycle (fix -> npm build -> vercel redeploy -> re-gate)
    - Instance variable _preview_url tracks URL across 10 sequential sub-steps
    - Lazy gate imports inside elif branches (avoid heavy import at module level)
    - Self-registration guard at module level: if get_executor("3") is None: register()

key-files:
  created:
    - tools/gates/legal_gate.py
    - tools/phase_executors/phase_3_executor.py
    - tests/test_legal_gate.py
    - tests/test_phase_3_executor.py
  modified:
    - tools/contract_pipeline_runner.py
    - tests/test_contract_runner.py
    - tests/test_phase_3_executor.py (isolation fix for test_self_registration)

key-decisions:
  - "Legal gate scans for 6 placeholder patterns: YOUR_APP_NAME, YOUR_COMPANY, [COMPANY], [DATE], [APP_NAME], YOUR_EMAIL"
  - "Feature reference check is advisory-only (pass with advisory) so missing PRD cross-references don't block ship"
  - "gate_security_headers and gate_link_integrity run once (no retry) — headers are config-level fixes requiring redeploy"
  - "gate_lighthouse and gate_accessibility get max 3 retries with deploy-agent auto-fix cycle"
  - "test_self_registration uses importlib.reload() for deterministic registry isolation across the test suite"
  - "URL-dependent gates in _run_gate_checks fail-closed with descriptive error when deployment.json missing"

requirements-completed: [LEGL-01, LEGL-02, LEGL-03, GATE-02, GATE-03, GATE-04, GATE-07]

# Metrics
duration: 7min
completed: 2026-03-22
---

# Phase 04 Plan 03: Phase 3 Ship Executor, Legal Gate, Gate Dispatch Wiring Summary

**Phase3ShipExecutor orchestrating 10 sub-steps (provision -> deploy_preview -> generate_legal -> gate_legal -> gate_lighthouse -> gate_accessibility -> gate_security_headers -> gate_link_integrity -> gate_mcp_approval -> deploy_production) with legal quality gate, auto-fix retry for lighthouse/accessibility, and 7 new gate dispatchers wired into contract_pipeline_runner**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-22T17:03:06Z
- **Completed:** 2026-03-22T17:10:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `legal_gate.py`: `run_legal_gate()` validates presence of `src/app/privacy/page.tsx` and `src/app/terms/page.tsx`, scans for 6 placeholder patterns (fail), and checks PRD feature cross-references (advisory-only)
- `phase_3_executor.py`: `Phase3ShipExecutor` with 10 sequential sub-steps; auto-registers as phase "3" at module import time; retry cycle for lighthouse/accessibility (max 3 attempts: fix -> npm build -> vercel redeploy -> re-gate)
- `contract_pipeline_runner.py`: `_read_deployment_url()` helper reads preview URL from `deployment.json`; 7 new elif branches in `_run_gate_checks` dispatch `lighthouse`, `accessibility`, `security_headers`, `link_integrity`, `deployment`, `mcp_approval`, `legal` gate types; Phase 3 executor self-registration triggered via module import
- Full test suite: 432 tests passing (54 new tests, 378 pre-existing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Legal quality gate + Phase 3 Ship Executor** - `e21a3b8` (feat)
2. **Task 2: Gate dispatch wiring in contract_pipeline_runner + executor import** - `9bd5e92` (feat)

## Files Created/Modified

- `tools/gates/legal_gate.py` — run_legal_gate() with file presence, placeholder scan, and feature advisory checks (165 lines)
- `tools/phase_executors/phase_3_executor.py` — Phase3ShipExecutor with 10 sub-steps and retry logic (733 lines)
- `tools/contract_pipeline_runner.py` — Phase 3 import, _read_deployment_url helper, 7 new gate dispatchers (460 lines total, +112 lines)
- `tests/test_legal_gate.py` — 14 tests: file presence, placeholder variants, feature advisory, phase_id, no-PRD edge case
- `tests/test_phase_3_executor.py` — 26 tests: properties, provision, deploy_preview, generate_legal, gate_legal, retry logic, mcp_approval, deploy_production, full happy path
- `tests/test_contract_runner.py` — 14 new tests: ReadDeploymentUrl (3), NewGateDispatch (10), ExecutorRegistrationPhase3 (1)

## Decisions Made

- Legal gate feature reference is advisory-only: downstream apps may not reference PRD feature names verbatim in legal boilerplate, so blocking here would cause unnecessary friction; the gate still ensures placeholder removal (which IS blocking)
- `gate_security_headers` and `gate_link_integrity` run without retry: headers require `next.config.ts` changes + full redeploy (structural), and 404 links require new pages to be created (also structural) — the deploy-agent fix cycle applies to performance/accessibility which are more correctable
- `test_self_registration` uses `importlib.reload()` after `_clear_registry()` rather than direct import: ensures the module-level guard `if get_executor("3") is None: register(...)` runs fresh in an isolated test order
- URL-dependent gates in `_run_gate_checks` use `continue` after `issues.append(str(exc))` when `deployment.json` is missing: this adds a descriptive error and moves to the next gate rather than crashing the entire gate check loop

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_self_registration test isolation failure**
- **Found during:** Task 2 full test suite run
- **Issue:** `test_self_registration` passed when run alone but failed in full suite because a prior test's `_clear_registry()` left the registry empty, and the module was already imported (self-registration `if get_executor("3") is None` guard was False on first import, never re-runs)
- **Fix:** Changed test to use `importlib.reload()` after `_clear_registry()` to re-trigger module-level self-registration deterministically
- **Files modified:** `tests/test_phase_3_executor.py`
- **Commit:** `9bd5e92`

**2. [Rule 1 - Bug] test_legal_generation_with_prd: call_args positional access**
- **Found during:** Task 1 test run
- **Issue:** Test accessed `mock_agent.call_args[0][0]` (positional args) but `run_deploy_agent` is called with keyword args only (`prompt=`, `system_prompt=`, `project_dir=`)
- **Fix:** Changed test to check both positional and keyword args for the prompt content
- **Files modified:** `tests/test_phase_3_executor.py`
- **Commit:** `e21a3b8`

### Code Health Note

`phase_3_executor.py` is 733 lines (within 601-800 "warning" range). The file has single responsibility (Phase 3 Ship orchestration) with 10 sub-steps each requiring substantial implementation. Refactoring would require splitting the sub-step methods into a separate module, which would add complexity without improving clarity. File is borderline but justified by the inherent complexity of the orchestrated workflow.

## Self-Check

All task commits verified:
- `e21a3b8` (feat): legal gate + Phase 3 Ship executor
- `9bd5e92` (feat): gate dispatch wiring + Phase 3 executor import

Files verified:
- `tools/gates/legal_gate.py` - exists, 165 lines
- `tools/phase_executors/phase_3_executor.py` - exists, 733 lines
- `tools/contract_pipeline_runner.py` - modified, contains "lighthouse" dispatch
- `tests/test_legal_gate.py` - exists, 14 tests passing
- `tests/test_phase_3_executor.py` - exists, 26 tests passing
- `tests/test_contract_runner.py` - modified, 32 tests passing total

## Self-Check: PASSED

All 432 tests passing. Phase 3 executor registered for phase "3". Gate dispatch handles all 11 gate types (4 existing + 7 new). Legal gate validates file presence, placeholders, and feature references.
