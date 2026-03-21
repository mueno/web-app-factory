---
phase: 02-spec
plan: 02
subsystem: phase-executors
tags: [phase-1a, executor, tdd, npm-validation, SPEC-01, SPEC-03]
dependency_graph:
  requires:
    - tools/phase_executors/spec_agent_runner.py (Plan 02-01)
    - agents/definitions.py SPEC_AGENT (Plan 02-01)
    - tests/conftest.py mock_agent_query fixture (Plan 02-01)
  provides:
    - tools/phase_executors/phase_1a_executor.py (Phase1aSpecExecutor registered for "1a")
    - validate_npm_packages() module-level function
    - tests/test_phase_1a_executor.py (18 tests)
  affects:
    - tools/contract_pipeline_runner.py (phase_1a_executor import added)
    - tools/phase_executors/phase_1b_executor.py (Plan 02-03 — next executor)
tech_stack:
  added:
    - httpx.AsyncClient for npm registry lookups (asyncio.run() sync/async bridge)
    - importlib.reload() + get_executor() guard for test-safe self-registration
  patterns:
    - PhaseExecutor ABC subclass with @property phase_id and sub_steps
    - Module-level self-registration guard (get_executor("1a") is None before register())
    - asyncio.run() for sync/async bridge in validate_npm_packages()
    - project_dir_with_deliverables fixture pre-populates disk files for mocked agent tests
key_files:
  created:
    - tools/phase_executors/phase_1a_executor.py
    - tests/test_phase_1a_executor.py
  modified:
    - tools/contract_pipeline_runner.py (added phase_1a_executor import for self-registration)
decisions:
  - "Phase1aSpecExecutor uses PhaseExecutor ABC inheritance (not duck-typing) to satisfy registry isinstance check"
  - "Self-registration guard: get_executor('1a') is None check prevents duplicate ValueError on importlib.reload() in tests"
  - "validate_npm_packages() is module-level (not a method) since it is Phase 1a specific and may be called independently"
  - "Executor does not write files itself — agent writes them; executor validates existence via _validate_deliverables()"
  - "Quality self-assessment failure is logged as warning, not propagated as PhaseResult failure (non-blocking)"
metrics:
  duration: "~4 minutes"
  completed_date: "2026-03-21"
  tasks_completed: 1
  files_changed: 3
requirements_satisfied: [SPEC-01, SPEC-03]
---

# Phase 2 Plan 02: Phase 1a Executor — Idea Validation and Tech Feasibility Summary

Phase1aSpecExecutor calling the spec agent to produce idea-validation.md with Go/No-Go decision and tech-feasibility-memo.json with npm-validated packages, self-registered in the executor registry via a reload-safe guard.

## What Was Built

### tools/phase_executors/phase_1a_executor.py — Phase1aSpecExecutor

Concrete PhaseExecutor subclass for Phase 1a with:

- `phase_id = "1a"` — matches pipeline contract phase id
- `sub_steps = ["research", "analyze", "write_validation", "write_feasibility", "self_assess"]`
- `execute(ctx)` orchestrates 6 steps:
  1. Load quality criteria from YAML contract and build augmented system prompt
  2. Build user prompt instructing the agent to research competitors, write both files
  3. Call `run_spec_agent()` (from Plan 02-01's spec_agent_runner)
  4. Validate both deliverables exist on disk (`_validate_deliverables`)
  5. Validate npm packages in feasibility memo against registry.npmjs.org (`_validate_npm_packages_in_memo`)
  6. Generate quality self-assessment JSON (CONT-04, `generate_quality_self_assessment`)
- Returns `PhaseResult(success=True, artifacts=[...])` with both file paths on success
- Returns `PhaseResult(success=False, error=...)` when agent returns empty or files not written

`validate_npm_packages(packages: list[str]) -> dict[str, bool]` — module-level function using `httpx.AsyncClient` with `asyncio.run()` bridge. Checks each package against `https://registry.npmjs.org/{pkg}/latest`.

Self-registration at module bottom: `if get_executor("1a") is None: register(Phase1aSpecExecutor())` — the guard prevents `ValueError: Duplicate executor registration` when `importlib.reload()` is called in tests after `_clear_registry()`.

### tests/test_phase_1a_executor.py — 18 Tests

Full test coverage for SPEC-01 and SPEC-03:

| Test | What It Verifies |
|------|-----------------|
| test_phase_id_is_1a | phase_id property returns "1a" |
| test_sub_steps_returns_expected_list | sub_steps order and content |
| test_executor_self_registers_for_phase_1a | get_executor("1a") returns registered executor |
| test_execute_produces_idea_validation_md | File exists after execute() |
| test_execute_produces_tech_feasibility_memo_json | File exists after execute() |
| test_idea_validation_md_has_required_sections | ## Competitors, ## Target User, ## Differentiation, ## Risks |
| test_idea_validation_md_has_parseable_go_no_go | regex `go_no_go:\s*(Go\|No-Go)` matches |
| test_tech_feasibility_memo_is_valid_json_with_rendering_strategy | JSON with rendering_strategy key |
| test_tech_feasibility_memo_has_packages_list | JSON with packages list |
| test_execute_returns_success_phase_result | PhaseResult(success=True, artifacts=[...]) |
| test_execute_returns_artifacts_containing_deliverable_paths | Both file paths in artifacts |
| test_execute_calls_npm_validation_for_packages | validate_npm_packages called once |
| test_validate_npm_packages_returns_dict | Return type is dict |
| test_validate_npm_packages_returns_true_for_existing_packages | 200 response → True |
| test_validate_npm_packages_returns_false_for_missing_packages | 404 response → False |
| test_execute_returns_failure_when_agent_returns_empty | PhaseResult(success=False) on empty result + no files |
| test_execute_returns_failure_when_deliverables_missing_after_agent_run | PhaseResult(success=False) when files absent |
| test_quality_self_assessment_generated_after_execute | quality-self-assessment-1a.json written |

### tools/contract_pipeline_runner.py — Executor Import Added

Added after `from tools.phase_executors.registry import get_executor`:

```python
# Import executor modules to trigger self-registration via register() calls.
import tools.phase_executors.phase_1a_executor  # noqa: F401
```

## Test Results

- 18 new tests in `tests/test_phase_1a_executor.py` — all passing
- Full suite: 127/127 passing (was 109 before this plan)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Phase1aSpecExecutor must subclass PhaseExecutor ABC**
- **Found during:** Task 1 GREEN phase — first test run
- **Issue:** Initial implementation used duck-typing (no ABC inheritance). Registry's `isinstance(executor, PhaseExecutor)` check raised `TypeError: Expected PhaseExecutor instance, got Phase1aSpecExecutor`
- **Fix:** Changed class definition to `class Phase1aSpecExecutor(PhaseExecutor)`, added `PhaseExecutor` to imports, converted `phase_id` and `sub_steps` class attributes to `@property` methods per ABC contract
- **Files modified:** `tools/phase_executors/phase_1a_executor.py`
- **Commit:** 75f4bb9 (included in GREEN commit)

**2. [Rule 1 - Bug] Module reload in tests caused duplicate registration ValueError**
- **Found during:** Task 1 GREEN phase — second test run
- **Issue:** Test helper `_import_executor()` called `importlib.reload()` after first import, re-running the module-level `register()` call and hitting `ValueError: Duplicate executor registration for phase '1a'`
- **Fix:** Added guard at module bottom: `if get_executor("1a") is None: register(Phase1aSpecExecutor())`. This allows reload to re-register after `_clear_registry()` clears the registry, while preventing double-registration on first load.
- **Files modified:** `tools/phase_executors/phase_1a_executor.py`, `tests/test_phase_1a_executor.py`
- **Commit:** 75f4bb9 (included in GREEN commit)

## Self-Check: PASSED

All created/modified files verified on disk. Commits d0f4f2e (RED) and 75f4bb9 (GREEN) confirmed present.
Full test suite 127/127 passing.
