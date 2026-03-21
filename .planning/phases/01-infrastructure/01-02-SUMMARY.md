---
phase: 01-infrastructure
plan: 02
subsystem: infra
tags: [pipeline-state, governance, gate-result, phase-executor, state-persistence, resume-logic]

# Dependency graph
requires:
  - phase: 01-infrastructure/01-01
    provides: pyproject.toml, YAML contract, JSON schema, and test infrastructure

provides:
  - PHASE_ORDER=['1a','1b','2a','2b','3'] web phase constants in pipeline_state.py
  - State persistence: init_run, phase_start, phase_complete write state.json + activity-log.jsonl
  - Resume logic: get_resume_phase returns next incomplete phase after interruption
  - GovernanceMonitor with blocking phase-order enforcement via GovernanceViolationError
  - GateResult frozen dataclass with backward-compatible dict access
  - PhaseExecutor ABC with PhaseContext, PhaseResult, SubStepResult dataclasses
  - Phase executor registry for dynamic dispatch (empty, populated in Phase 2+)

affects:
  - 01-infrastructure/01-03 (MCP server depends on pipeline_state for phase_reporter)
  - 01-infrastructure/01-04 (CLI factory.py calls init_run + phase lifecycle)
  - phase-02 (web phase executors implement PhaseExecutor ABC and register in registry)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PHASE_ORDER constant is single source of truth for phase ID enumeration"
    - "State persistence via state.json + activity-log.jsonl in docs/pipeline/runs/{run_id}/"
    - "GovernanceMonitor.blocking=False pattern for test isolation (avoids fast_phase_completion)"
    - "GateResult frozen dataclass with dict-bridge for backward compatibility"
    - "PhaseExecutor ABC + registry pattern: executors self-register at module load"

key-files:
  created:
    - tools/pipeline_state.py
    - pipeline_runtime/governance_monitor.py
    - tools/gates/gate_result.py
    - tools/gates/gate_policy.py
    - tools/phase_executors/base.py
    - tools/phase_executors/registry.py
    - tests/test_pipeline_state.py
    - tests/test_governance_monitor.py
  modified: []

key-decisions:
  - "get_resume_phase returns None (not PHASE_ORDER[-1]) when all phases complete — web pipeline terminates cleanly"
  - "Removed iOS-specific imports from base.py (_ExecuteModeExecutor class stripped, has runtime/quality/logger deps not yet available)"
  - "registry.py auto-registration block removed (no web executors yet); blank slate for Phase 2"
  - "Test isolation via blocking=False on GovernanceMonitor to prevent fast_phase_completion from interfering with unit tests"

patterns-established:
  - "TDD RED→GREEN cycle: test imports fail → write production code → all tests green"
  - "State file path convention: docs/pipeline/runs/{run_id}/state.json"
  - "Activity log convention: docs/pipeline/activity-log.jsonl (cross-run, append-only)"

requirements-completed:
  - PIPE-01
  - PIPE-02
  - PIPE-03
  - PIPE-05

# Metrics
duration: 7min
completed: 2026-03-21
---

# Phase 1 Plan 2: Pipeline Backbone Summary

**Pipeline state persistence (state.json + activity-log.jsonl), governance enforcement (GovernanceViolationError on out-of-order phases), GateResult dataclass, and PhaseExecutor ABC — adapted from ios-app-factory for 5 web phases**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-21T12:20:36Z
- **Completed:** 2026-03-21T12:27:30Z
- **Tasks:** 2 (TDD)
- **Files modified:** 8

## Accomplishments

- 6 production files from ios-app-factory copied/adapted with PHASE_ORDER updated to web phases
- 25 tests covering state persistence, resume logic, governance enforcement, and GateResult semantics — all green
- GovernanceMonitor correctly blocks out-of-order phase execution with GovernanceViolationError
- get_resume_phase returns None (not last phase) when all phases complete — key behavioral change from ios-app-factory

## Task Commits

Each task was committed atomically:

1. **Task 1 (TDD RED): Add failing tests** - `3c67972` (test)
2. **Task 1+2 (TDD GREEN): Production files + test fixes** - `832459f` (feat)

_Note: TDD tasks had RED commit followed by GREEN commit; test fixes for fast_phase_completion folded into GREEN commit_

## Files Created/Modified

- `tools/pipeline_state.py` - State persistence with PHASE_ORDER=['1a','1b','2a','2b','3']
- `pipeline_runtime/governance_monitor.py` - Phase ordering enforcement, write-without-phase detection
- `tools/gates/gate_result.py` - Frozen GateResult dataclass with dict bridge
- `tools/gates/gate_policy.py` - normalize_gate_result, SPC recording helpers
- `tools/phase_executors/base.py` - PhaseExecutor ABC, PhaseContext, PhaseResult, SubStepResult
- `tools/phase_executors/registry.py` - Empty executor registry (web executors added Phase 2+)
- `tests/test_pipeline_state.py` - 15 tests: PHASE_ORDER, init_run, lifecycle, activity log, resume
- `tests/test_governance_monitor.py` - 10 tests: violation error, phase order, write-without-phase, GateResult

## Decisions Made

- `get_resume_phase` returns `None` (not `PHASE_ORDER[-1]`) when all phases complete — the ios-app-factory version returned the last phase ID, which would cause a "resume from ship" loop; web pipeline should terminate
- `_ExecuteModeExecutor` removed from `base.py` — it imports `tools.phase_executors.runtime`, `tools.phase_logger`, and `tools.quality.quality_self_assessment` which don't exist yet; only PhaseExecutor ABC is needed now
- Registry auto-registration imports removed — ios-app-factory's registry imported iOS phase executors at module load; web-app-factory starts empty and fills as Phase 2 executors are added
- Tests use `blocking=False` on GovernanceMonitor to prevent `fast_phase_completion` from triggering (phases complete in <5s with <2 tool calls in unit test context)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed get_resume_phase return value for all-complete case**
- **Found during:** Task 2 (writing tests)
- **Issue:** ios-app-factory returns `PHASE_ORDER[-1]` when all phases complete; this would cause web pipeline to attempt resuming from "3" (Ship) unnecessarily
- **Fix:** Changed return to `None` when all phases are in terminal status — test `test_get_resume_phase_all_complete_returns_none` validates this
- **Files modified:** tools/pipeline_state.py
- **Verification:** Test passes
- **Committed in:** 832459f (Task 1+2 commit)

**2. [Rule 3 - Blocking] Removed _ExecuteModeExecutor from base.py**
- **Found during:** Task 1 (import verification)
- **Issue:** `_ExecuteModeExecutor` references `tools.phase_executors.runtime`, `tools.phase_logger`, `tools.quality.quality_self_assessment` — none exist in web-app-factory yet; would cause ImportError
- **Fix:** Stripped _ExecuteModeExecutor class; kept only PhaseExecutor ABC, PhaseContext, PhaseResult, SubStepResult
- **Files modified:** tools/phase_executors/base.py
- **Verification:** `uv run python -c "from tools.phase_executors.base import PhaseExecutor, PhaseContext, PhaseResult"` succeeds
- **Committed in:** 832459f (Task 1+2 commit)

**3. [Rule 3 - Blocking] Removed iOS executor imports from registry.py**
- **Found during:** Task 1 (copy/adapt)
- **Issue:** ios-app-factory's registry.py imports `phase_2a_scaffold`, `all_phases`, `phase_2c_ui_designer`, `phase_2d_comparison`, and `phase_1b_task_decomposed` — all iOS-specific, none exist in web-app-factory
- **Fix:** Replaced auto-registration block with a comment placeholder; registry starts empty
- **Files modified:** tools/phase_executors/registry.py
- **Verification:** `from tools.phase_executors.registry import get_executor` succeeds
- **Committed in:** 832459f (Task 1+2 commit)

**4. [Rule 1 - Bug] Fixed test_governance_monitor for fast_phase_completion behavior**
- **Found during:** Task 2 (first GREEN run)
- **Issue:** Two governance tests failed because GovernanceMonitor raises `fast_phase_completion` (blocking) when a phase completes in <5s with <2 tool calls — expected in real pipelines but fires in unit tests
- **Fix:** Tests now use `blocking=False` for setup, then re-enable `blocking=True` for the specific violation being tested
- **Files modified:** tests/test_governance_monitor.py
- **Verification:** All 25 tests pass
- **Committed in:** 832459f (Task 1+2 commit)

---

**Total deviations:** 4 auto-fixed (2 blocking import issues, 1 logic bug, 1 test bug)
**Impact on plan:** All fixes necessary for importability and correct behavior. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Pipeline backbone is complete and importable
- Plan 03 (MCP server) can now import GovernanceMonitor and pipeline_state
- Plan 04 (CLI) can call init_run, phase_start, phase_complete, get_resume_phase
- Phase executor registry ready to receive web executors in Phase 2
- All 43 tests pass (18 from Plan 01 + 25 new)

---
*Phase: 01-infrastructure*
*Completed: 2026-03-21*
