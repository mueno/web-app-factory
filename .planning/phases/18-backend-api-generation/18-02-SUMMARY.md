---
phase: 18-backend-api-generation
plan: "02"
subsystem: phase-executors
tags: [backend-spec, phase-1b, spec-agent, tdd, bgen-01]
dependency_graph:
  requires: []
  provides: [backend-spec-generation, cross-validation-backend]
  affects: [phase_1b_executor, spec_agent_prompt, phase_1b_tests]
tech_stack:
  added: []
  patterns: [optional-sub-step-with-skip-flag, cross-validation-pattern, tdd-red-green]
key_files:
  created: []
  modified:
    - tools/phase_executors/phase_1b_executor.py
    - agents/definitions.py
    - tests/test_phase_1b_executor.py
decisions:
  - "_BACKEND_SPEC_PATH = Path('docs') / 'pipeline' / 'backend-spec.json' — matches research schema"
  - "backend-spec sub-steps are OPTIONAL: absence of backend-spec.json results in skipped=True, not failure"
  - "Cross-validation uses used_by_screens endpoint arrays checked against screen-spec.json route values"
  - "Existing test_sub_steps_returns_expected_list updated to include 2 new sub-steps (derive_backend_spec, cross_validate_backend)"
metrics:
  duration: "6 minutes"
  completed: "2026-03-25"
  tasks_completed: 1
  files_modified: 3
---

# Phase 18 Plan 02: Extend Phase 1b with Backend-Spec Generation Summary

**One-liner:** Phase 1b extended with optional backend-spec.json generation — entities, relationships, CRUD endpoints — with cross-validation against screen-spec.json routes.

## What Was Built

Extended `Phase1bSpecExecutor` in `tools/phase_executors/phase_1b_executor.py` to:

1. Expose `_BACKEND_SPEC_PATH = Path("docs") / "pipeline" / "backend-spec.json"` as a module-level constant.
2. Expand `sub_steps` from 4 entries to 6: `derive_backend_spec` and `cross_validate_backend` appended after existing `cross_validate`.
3. Add `_validate_backend_spec()` — validates backend-spec.json is valid JSON with `entities` and `endpoints` top-level keys.
4. Add `_cross_validate_backend_spec()` — extracts `used_by_screens` from all endpoints, checks each against `screen-spec.json` route values, returns orphaned paths on failure.
5. Update `execute()` with Steps 7-8 handling the optional backend-spec (file absent = skipped successfully, file present = validated and cross-validated).
6. Update `_build_user_prompt()` with Task 3 instructing the agent to derive backend-spec.json with CRUD auto-expansion and mandatory `/api/health` endpoint.

Updated `SPEC_AGENT` system prompt in `agents/definitions.py` with a `## Backend Specification` section describing the schema, CRUD auto-expansion rule, health endpoint requirement, and `used_by_screens` constraint.

## Test Coverage

8 new tests added to `tests/test_phase_1b_executor.py` (26 total, all green):

- `test_sub_steps_include_backend_spec` — `derive_backend_spec` and `cross_validate_backend` in sub_steps
- `test_backend_spec_path_constant` — `_BACKEND_SPEC_PATH` value check
- `test_backend_spec_cross_validation_passes` — valid used_by_screens references pass
- `test_backend_spec_cross_validation_fails_bad_screen_ref` — orphaned `/nonexistent-screen` fails
- `test_backend_spec_skipped_when_not_produced` — Phase 1b succeeds when backend-spec.json absent
- `test_spec_agent_prompt_includes_backend_instructions` — SPEC_AGENT prompt contains `backend-spec`
- `test_backend_spec_user_prompt_includes_crud_instruction` — CRUD in user prompt
- `test_backend_spec_user_prompt_mentions_health_endpoint` — `/api/health` in user prompt

Also updated `test_sub_steps_returns_expected_list` to reflect the expanded 6-entry sub_steps list.

## Decisions Made

- backend-spec sub-steps are **optional**: file absence is a graceful skip (not failure). This enables static apps with no backend to pass Phase 1b without changes.
- Cross-validation uses the string values of `used_by_screens` matched against `screen-spec.json[screens][*][route]` — exact string comparison.
- `relationships` key is optional in backend-spec.json (not all apps have inter-entity relationships). Only `entities` and `endpoints` are required for validation to pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing test test_sub_steps_returns_expected_list broken by extension**
- **Found during:** GREEN phase
- **Issue:** The existing test asserted sub_steps == 4-entry list; new implementation expands to 6 entries.
- **Fix:** Updated the test to assert the new 6-entry list.
- **Files modified:** tests/test_phase_1b_executor.py
- **Commit:** 91f25b1

### Code Health Note

`phase_1b_executor.py` is at 643 lines — in the "warning" range (601-800). This is expected given the plan called for significant new methods in this file. The plan explicitly targeted this file with multiple sub-step additions. Recommended future split: extract `_validate_backend_spec` and `_cross_validate_backend_spec` into a `backend_spec_validator.py` helper module once Phase 18 is complete.

## Verification

```
uv run pytest tests/test_phase_1b_executor.py -x -q
# 26 passed in 0.35s

uv run python -c "from agents.definitions import SPEC_AGENT; assert 'backend-spec' in SPEC_AGENT.system_prompt.lower(); print('OK')"
# OK - SPEC_AGENT prompt contains backend-spec
```

## Commits

- `f15ff34`: test(18-02): add failing tests for backend-spec Phase 1b extension (RED phase)
- `91f25b1`: feat(18-02): extend Phase 1b executor with backend-spec generation (BGEN-01) (GREEN phase)

## Self-Check: PASSED
