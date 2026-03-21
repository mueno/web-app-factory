---
phase: 05-build-pipeline-fix
plan: 01
subsystem: build-pipeline
tags: [nextjs, governance, build-gate, phase-executor, tdd]

# Dependency graph
requires:
  - phase: 04-ship
    provides: full pipeline runner with gate dispatch and phase executor registry
  - phase: 03-build
    provides: Phase2bBuildExecutor, build_gate, static_analysis_gate, phase_2a_executor pattern
provides:
  - Fixed Phase 2b executor passing nextjs_dir (not pipeline root) to run_build_agent
  - _run_gate_checks accepting optional nextjs_dir parameter for build/static_analysis gates
  - run_pipeline computing nextjs_dir and forwarding to gate dispatch
  - GovernanceMonitor wired into live pipeline runner with blocking=False
affects: [phase-3-execution, build-gate, static-analysis-gate, governance-audit]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "nextjs_dir = ctx.project_dir.parent / ctx.app_name — consistent with Phase 2a pattern"
    - "GovernanceMonitor(run_id, project_dir, blocking=False) in run_pipeline before phase loop"
    - "_run_gate_checks nextjs_dir kwarg with fallback to project_dir for backward compat"

key-files:
  created: []
  modified:
    - tools/phase_executors/phase_2b_executor.py
    - tools/contract_pipeline_runner.py
    - tests/test_phase_2b_executor.py
    - tests/test_contract_runner.py

key-decisions:
  - "nextjs_dir = ctx.project_dir.parent / ctx.app_name — mirrors Phase 2a pattern for consistency"
  - "GovernanceMonitor.blocking=False in contract runner prevents fast_phase_completion violations since phases complete synchronously from monitor's perspective"
  - "_run_gate_checks falls back to project_dir when nextjs_dir is None — preserves backward compatibility for all non-build/non-static-analysis gate types"
  - "monitor.register_gate_pass called only when skip_gates=False and gate actually passes"
  - "Test helper _make_ctx uses pipeline-root/myapp split to distinguish pipeline root from Next.js project dir"

patterns-established:
  - "TDD RED→GREEN: Test helpers must create test data in the same directory the production code reads from"
  - "nextjs_dir kwarg pattern: keyword-only parameter with None default for optional override of target directory"

requirements-completed: [BILD-02, BILD-03, BILD-04, PIPE-05]

# Metrics
duration: 15min
completed: 2026-03-22
---

# Phase 5 Plan 01: Build Pipeline Directory Fix and GovernanceMonitor Wiring Summary

**Fixed Phase 2b build agent receiving pipeline root instead of Next.js project dir, wired GovernanceMonitor into live pipeline runner with phase lifecycle tracking**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-22
- **Completed:** 2026-03-22
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments

- Phase 2b executor now passes `ctx.project_dir.parent / ctx.app_name` to `run_build_agent`, `_validate_extra_npm_packages`, `generate_quality_self_assessment`, and the artifacts list — matching the Phase 2a directory pattern
- `_run_gate_checks` accepts optional `nextjs_dir` kwarg; build and static_analysis gates receive `nextjs_dir` when provided instead of the pipeline root, so npm/tsc run in the directory that has `package.json`
- `GovernanceMonitor` is now instantiated in `run_pipeline` with `blocking=False` and tracks phase start/complete/error events plus gate passes
- Full test suite green: 436 tests passing (50 pre-existing + 4 new failing tests in RED + all 54 green in GREEN)

## Task Commits

1. **Task 1: Write failing tests (TDD RED)** - `340fbae` (test)
2. **Task 2: Fix directory handoff + wire GovernanceMonitor (TDD GREEN)** - `802d3ec` (feat)

## Files Created/Modified

- `/Users/masa/Development/web-app-factory/tools/phase_executors/phase_2b_executor.py` - Added nextjs_dir computation and substituted all 4 uses of ctx.project_dir in execute()
- `/Users/masa/Development/web-app-factory/tools/contract_pipeline_runner.py` - Added GovernanceMonitor import, nextjs_dir param to _run_gate_checks, nextjs_dir computation in run_pipeline, monitor instantiation and lifecycle tracking
- `/Users/masa/Development/web-app-factory/tests/test_phase_2b_executor.py` - Updated _make_ctx to use pipeline-root/myapp split; renamed test to assert nextjs_dir; fixed package.json location in npm validation test
- `/Users/masa/Development/web-app-factory/tests/test_contract_runner.py` - Added TestNextjsDirGateDispatch (3 tests) and TestGovernanceIntegration (1 test)

## Decisions Made

- Used `blocking=False` for GovernanceMonitor in contract runner: phases complete synchronously from the monitor's perspective, which would trigger false `fast_phase_completion` violations with `blocking=True`
- `nextjs_dir` as keyword-only parameter with `None` default preserves backward compatibility — all existing callers unchanged, URL-dependent gates still use `project_dir`
- `monitor.register_gate_pass(phase_id)` called after gate checks pass but only when `skip_gates=False` — consistent with actual gate enforcement

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test helper wrote package.json to wrong directory**
- **Found during:** Task 2 (GREEN phase, running full test suite)
- **Issue:** `test_calls_validate_npm_packages_after_agent` created `package.json` in `ctx.project_dir` (pipeline root); after the fix, the executor reads from `nextjs_dir = ctx.project_dir.parent / ctx.app_name`, so `validate_npm_packages` was never called
- **Fix:** Changed the test to create `package.json` in `ctx.project_dir.parent / ctx.app_name` (the Next.js project dir)
- **Files modified:** tests/test_phase_2b_executor.py
- **Verification:** `uv run pytest tests/test_phase_2b_executor.py -q` — 24 passed
- **Committed in:** 802d3ec (Task 2 feat commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test data placement)
**Impact on plan:** Auto-fix necessary for test correctness. No scope creep.

## Issues Encountered

None beyond the test data fix above.

## Next Phase Readiness

- Phase 2b directory handoff is correct; build agent and build gate will now operate on the generated Next.js project directory
- GovernanceMonitor is live in the pipeline with audit logging support
- All 436 tests passing; no regressions

---
*Phase: 05-build-pipeline-fix*
*Completed: 2026-03-22*
