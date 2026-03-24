---
phase: 13-pipeline-quality
plan: "01"
subsystem: phase-executors
tags: [pipeline, executor, tdd, checkpoint-resume, code-generation]
dependency_graph:
  requires: [phase-8-mcp-infrastructure]
  provides: [phase-2b-three-sub-step-executor, checkpoint-resume]
  affects: [contract-pipeline-runner, phase-2b-tests]
tech_stack:
  added: []
  patterns:
    - "Three-sub-step TDD executor with checkpoint-based resumption"
    - "Focused prompt isolation: shared components / pages / integration"
key_files:
  created: []
  modified:
    - tools/phase_executors/phase_2b_executor.py
    - tests/test_phase_2b_executor.py
decisions:
  - "Integration prompt omits PRD/screen-spec to prevent agent re-generating already-written files (Pitfall 2)"
  - "_start_index(ctx) gates each sub-step on start_idx <= N for clean resume skip logic"
  - "Existing TestPhase2bBuildExecutorAgentPrompt tests updated to check across all prompts (not assert len==1)"
metrics:
  duration_minutes: 6
  completed_date: "2026-03-24"
  tasks_completed: 2
  files_modified: 2
---

# Phase 13 Plan 01: Three-Sub-Step Phase 2b Executor Summary

**One-liner:** Phase 2b executor split into three checkpointed agent calls — shared components, pages, integration — with focused prompts and resume_point on failure.

## What Was Built

Split the Phase 2b build executor from a single monolithic `run_build_agent()` call into three sequential agent calls, each with a focused prompt and individual failure/resume capability.

### Sub-step decomposition

| Sub-step | Index | Prompt focus | On failure |
|----------|-------|-------------|-----------|
| `generate_shared_components` | 1 | PRD Component Inventory → `src/components/` only | `resume_point="generate_shared_components"` |
| `generate_pages` | 2 | screen-spec.json → routes in order, error.tsx (BILD-06), mobile-first (BILD-05) | `resume_point="generate_pages"` |
| `generate_integration` | 3 | `src/lib/types.ts` cross-page URLSearchParams only (no PRD/screen-spec) | `resume_point="generate_integration"` |

### Resume mechanism

`ctx.resume_sub_step` + `_start_index()` (already in `PhaseExecutor` base class) enables skipping completed sub-steps:
- `resume_sub_step="generate_pages"` → 2 agent calls (pages + integration)
- `resume_sub_step="generate_integration"` → 1 agent call (integration only)

### Prompt templates

Three module-level constants (`_SHARED_COMPONENTS_PROMPT_TEMPLATE`, `_PAGES_PROMPT_TEMPLATE`, `_INTEGRATION_PROMPT_TEMPLATE`) with format placeholders. Integration template explicitly excludes `{prd_content}` and `{screen_spec_content}` — prevents Pitfall 2 (agent re-generates already-written files when spec content is embedded).

## TDD Execution

**Task 1 (RED):** Added 3 new test classes and updated `test_sub_steps_contains_expected_steps`:
- `TestPhase2bSubStepCheckpoints` — resume_point set on each generation sub-step failure
- `TestPhase2bBuildExecutorResume` — skip logic via ctx.resume_sub_step
- `TestPhase2bSubStepPrompts` — prompt isolation (shared prompt has no page instruction, integration prompt has no PRD content)
- All 10 new/updated tests failed (RED confirmed)

**Task 2 (GREEN):** Implemented three-sub-step executor:
- 5-element `sub_steps` property
- Three `run_build_agent()` calls gated on `start_idx <= N`
- `PhaseResult.resume_point` set on each failure
- Also updated `TestPhase2bBuildExecutorAgentPrompt` tests to work with 3-call pattern (checks across all prompts instead of asserting exactly 1)
- All 27 Phase 2b tests pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing `TestPhase2bBuildExecutorAgentPrompt` tests assumed single agent call**
- **Found during:** Task 2 (GREEN) — tests failed because they asserted `len(captured_prompts) == 1` while executor now makes 3 calls
- **Issue:** `test_prompt_contains_prd_content`, `test_prompt_contains_screen_spec_content`, `test_prompt_instructs_error_tsx_per_route_segment`, `test_prompt_instructs_generation_order_shared_components_first`, `test_prompt_instructs_mobile_first_responsive`, `test_execute_uses_error_tsx_instruction_for_async_data_routes` all asserted exactly 1 prompt capture
- **Fix:** Updated tests to: (a) check content across all prompts using `" ".join(prompts)`, (b) check structural ordering by inspecting `prompts[0]` vs `prompts[1]` separately, (c) refactored to `_capture_all_prompts()` helper
- **Files modified:** `tests/test_phase_2b_executor.py`
- **Commit:** 66c5e59

## Verification

```
uv run pytest tests/test_phase_2b_executor.py -x -q
# → 27 passed

uv run pytest -q
# → 679 passed, 1 pre-existing failure (test_factory_cli.py::test_deploy_target_github_pages)
```

## Commits

| Hash | Message |
|------|---------|
| f8d48b3 | test(13-01): add failing tests for Phase 2b three-sub-step decomposition |
| 66c5e59 | feat(13-01): implement three-sub-step Phase 2b executor with checkpoint resume |

## Self-Check: PASSED

- tools/phase_executors/phase_2b_executor.py — FOUND
- tests/test_phase_2b_executor.py — FOUND
- Commit f8d48b3 (test RED) — FOUND
- Commit 66c5e59 (feat GREEN) — FOUND
- 27 Phase 2b tests pass — CONFIRMED
- 679 total tests pass (1 pre-existing failure only) — CONFIRMED
