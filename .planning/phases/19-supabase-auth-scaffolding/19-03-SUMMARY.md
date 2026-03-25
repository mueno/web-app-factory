---
phase: 19-supabase-auth-scaffolding
plan: "03"
subsystem: executor-pipeline
tags: [code-health, tdd, supabase, oauth, auth-pages, executor-split]
dependency_graph:
  requires: ["19-01", "19-02", "17-04"]
  provides: ["_phase_3_supabase_steps.py", "generate_auth_pages sub-step", "supabase_oauth_config sub-step"]
  affects: ["phase_2b_executor.py", "phase_3_executor.py"]
tech_stack:
  added: []
  patterns: ["lazy imports", "asyncio.run() bridge", "ctx.extra inter-step state", "code-health Pattern A split", "TDD RED/GREEN/REFACTOR"]
key_files:
  created:
    - tools/phase_executors/_phase_3_supabase_steps.py
    - tests/test_phase_3_supabase_steps.py
  modified:
    - tools/phase_executors/phase_3_executor.py
    - tools/phase_executors/phase_2b_executor.py
    - tests/test_phase_2b_executor.py
    - tests/test_phase_3_supabase.py
decisions:
  - "phase_3_executor.py split using Pattern A (registry + individual files) from code-health rules"
  - "Supabase enablement detected via NEXT_PUBLIC_SUPABASE_URL presence in .env.local (deterministic, no spec parsing)"
  - "supabase_oauth_config is non-blocking: API failure returns success=True with advisory note"
  - "asyncio.run() bridge used consistently for async provisioner calls from sync executor"
metrics:
  duration_minutes: 90
  tasks_completed: 3
  files_created: 2
  files_modified: 4
  completed_date: "2026-03-25"
---

# Phase 19 Plan 03: Supabase Sub-step Extraction and OAuth Wiring Summary

**One-liner:** Code-health split of 850-line phase_3_executor.py into extracted _phase_3_supabase_steps.py module, plus TDD wiring of generate_auth_pages (Phase 2b) and supabase_oauth_config (Phase 3).

## What Was Built

### Task 1: Code Health Split — Extract Supabase Sub-steps

`phase_3_executor.py` was at 850 lines (DANGER zone per `25-code-health.md`). All Supabase sub-step logic was extracted to a new `_phase_3_supabase_steps.py` module:

- **`supabase_provision(ctx)`** — provisions Supabase project via Management API; stores `supabase_project_ref` and `supabase_api_keys` in `ctx.extra`
- **`supabase_oauth_config(ctx)`** — NEW: configures Google/Apple OAuth via `configure_oauth_providers`; non-blocking advisory on failure
- **`supabase_render(ctx)`** — renders Supabase client templates and injects npm deps
- **`supabase_gate(ctx)`** — runs Supabase validation gate with project_ref from `ctx.extra`

Result: `phase_3_executor.py` reduced from 850 → 705 lines. `_phase_3_supabase_steps.py` at 265 lines (well within normal range).

15 unit tests in `tests/test_phase_3_supabase_steps.py` cover each extracted function independently.

### Task 2 (TDD): generate_auth_pages in Phase 2b

Added `generate_auth_pages` as the 5th sub-step in `Phase2bBuildExecutor` (index 4, after `generate_api_routes`, before `generate_integration`):

- **Enablement detection**: checks `NEXT_PUBLIC_SUPABASE_URL` presence in `nextjs_dir/.env.local` — deterministic, no spec parsing required
- **When enabled**: lazily imports and calls `render_auth_templates(nextjs_dir)` then `add_passkey_deps(nextjs_dir / "package.json")`
- **When disabled**: records `success=True` with skip note — non-breaking for non-Supabase pipelines
- **On failure**: records `success=False` and propagates phase failure

10 new tests in `TestPhase2bAuthPagesSubStep` + updated 3 existing tests that checked exact sub-step list length (6 → 7).

### Task 3 (TDD): supabase_oauth_config Integration Tests

Added `TestSupabaseOauthConfigInPhase3` class with 7 integration tests in `tests/test_phase_3_supabase.py`:

- Ordering assertions (oauth_config after provision, before render)
- Call behavior with full OAuth credentials
- Skip behavior with no credentials (advisory, not error)
- Non-blocking behavior on API failure (success=True)
- Substep result presence in phase output

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 8abb7d5 | feat(19-03): extract Supabase sub-steps to _phase_3_supabase_steps.py |
| Task 2 | 76b16b6 | feat(19-03): add generate_auth_pages sub-step to Phase 2b executor |
| Task 3 | c29d3bc | feat(19-03): wire supabase_oauth_config into Phase 3 and add integration tests |

## Test Results

- `tests/test_phase_3_supabase_steps.py`: 15/15 passed
- `tests/test_phase_3_supabase.py`: 21/21 passed (14 pre-existing + 7 new)
- `tests/test_phase_2b_executor.py`: 45/45 passed
- Full suite: 1070 passed, 2 pre-existing failures (unrelated to this plan)

## File Sizes After Plan

```
tools/phase_executors/phase_2b_executor.py   766 lines  (WARNING range, within target)
tools/phase_executors/phase_3_executor.py    705 lines  (WARNING range, down from 850)
tools/phase_executors/_phase_3_supabase_steps.py  265 lines  (normal range)
```

## Decisions Made

1. **Code-health split pattern**: Used Pattern A (registry + individual files) from `.claude/rules/25-code-health.md`. Standalone functions accept `(ctx: PhaseContext)` and return `SubStepResult` — no class needed.

2. **Supabase enablement in Phase 2b**: Detect via `NEXT_PUBLIC_SUPABASE_URL` in `.env.local` rather than spec parsing. This file is created by `load_spec` and is available at the time `generate_auth_pages` runs.

3. **supabase_oauth_config is non-blocking**: API failures return `success=True` with advisory note. Users can configure OAuth providers later via Supabase Dashboard. Consistent with Phase 17-04 advisory pattern.

4. **asyncio.run() bridge**: Used consistently for async provisioner calls from sync executor context. This is the established pattern from Phase 17-04.

5. **Lazy imports everywhere**: All Supabase-specific imports are inside function bodies so non-Supabase pipelines never import httpx/provisioner modules.

## Deviations from Plan

None — plan executed exactly as written.

## Pre-existing Test Failures (Out of Scope)

Two pre-existing test failures unrelated to this plan:
- `tests/test_phase_3_executor.py::TestPhase3ExecutorProperties::test_sub_steps_list` — stale test hardcoding old sub_steps list from before Supabase steps were added
- `tests/test_factory_cli.py::TestFactoryCLIFlags::test_deploy_target_github_pages` — CLI doesn't support `github-pages` deploy target

Both failures exist on `git stash` (before any of this plan's changes). Logged in deferred-items.

## Self-Check: PASSED
