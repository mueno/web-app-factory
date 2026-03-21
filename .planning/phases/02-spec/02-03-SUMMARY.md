---
phase: 02-spec
plan: 03
subsystem: phase-executors
tags: [phase-1b, executor, tdd, prd, screen-spec, component-validation, SPEC-02]
dependency_graph:
  requires:
    - tools/phase_executors/spec_agent_runner.py (Plan 02-01)
    - agents/definitions.py SPEC_AGENT (Plan 02-01)
    - tests/conftest.py mock_agent_query fixture (Plan 02-01)
    - tools/phase_executors/phase_1a_executor.py (Plan 02-02 — Phase 1a output as context)
  provides:
    - tools/phase_executors/phase_1b_executor.py (Phase1bSpecExecutor registered for "1b")
    - tests/test_phase_1b_executor.py (19 tests covering SPEC-02)
  affects:
    - tools/contract_pipeline_runner.py (phase_1b_executor import added)
tech_stack:
  added:
    - re (stdlib) for Component Inventory extraction via regex
  patterns:
    - PhaseExecutor ABC subclass with @property phase_id and sub_steps
    - Module-level self-registration guard (get_executor("1b") is None before register())
    - Phase 1a context injection: full file content embedded in agent prompt (not path reference)
    - Cross-validation: set comparison of screen-spec.json components vs prd.md inventory
key_files:
  created:
    - tools/phase_executors/phase_1b_executor.py
    - tests/test_phase_1b_executor.py
  modified:
    - tools/contract_pipeline_runner.py (added phase_1b_executor import for self-registration)
decisions:
  - "Phase 1a context injected as full file content into prompt (not just file paths) — build agent needs actual competitor/tech data, not file references"
  - "Component cross-validation uses regex extraction of **BoldNames** from ## Component Inventory section — matches PRD writing conventions established in VALID_PRD_MD test fixture"
  - "Cross-validation failure returns PhaseResult(success=False) with descriptive error listing specific mismatched component names"
  - "Quality self-assessment failure logged as warning (non-blocking), consistent with Phase 1a pattern"
  - "File at 471 lines (attention range 401-600) — single-responsibility executor class, no split warranted"
metrics:
  duration: "~4 minutes"
  completed_date: "2026-03-21"
  tasks_completed: 1
  files_changed: 3
requirements_satisfied: [SPEC-02]
---

# Phase 2 Plan 03: Phase 1b Executor — PRD and Screen Specification Summary

Phase1bSpecExecutor calling the spec agent to produce prd.md with MoSCoW-labeled requirements, component inventory, and route structure, and screen-spec.json with cross-validated component names matching the PRD, with Phase 1a context embedded directly in the agent prompt.

## What Was Built

### tools/phase_executors/phase_1b_executor.py — Phase1bSpecExecutor

Concrete PhaseExecutor subclass for Phase 1b with:

- `phase_id = "1b"` — matches pipeline contract phase id
- `sub_steps = ["load_context", "write_prd", "derive_screen_spec", "cross_validate", "self_assess"]`
- `execute(ctx)` orchestrates 7 steps:
  1. Load Phase 1a context: read full content of idea-validation.md and tech-feasibility-memo.json
  2. Load quality criteria from YAML contract and build augmented system prompt
  3. Build user prompt with Phase 1a content embedded directly (not as path references)
  4. Call `run_spec_agent()` (from Plan 02-01's spec_agent_runner)
  5. Validate both deliverables exist on disk (`_validate_deliverables`)
  6. Cross-validate component names: extract from prd.md Component Inventory, compare to screen-spec.json (`_cross_validate_components`)
  7. Generate quality self-assessment JSON (CONT-04)
- Returns `PhaseResult(success=True, artifacts=[...])` with both file paths on success
- Returns `PhaseResult(success=False, error=...)` on empty agent result, missing files, or component mismatch

Helper methods:
- `_load_phase_1a_context(project_dir)` — reads idea-validation.md and tech-feasibility-memo.json, returns `dict[str, str]` with file contents
- `_build_user_prompt(ctx, phase_1a_context)` — embeds Phase 1a content directly in prompt, instructs prd.md-first ordering, exact component name matching
- `_validate_deliverables(project_dir)` — checks prd.md and screen-spec.json exist
- `_cross_validate_components(project_dir)` — extracts `**BoldName**` patterns from `## Component Inventory` section, compares to screen-spec.json components set
- `_extract_prd_component_names(prd_content)` — regex extraction of bold-formatted component names

Self-registration at module bottom: `if get_executor("1b") is None: register(Phase1bSpecExecutor())`

### tests/test_phase_1b_executor.py — 19 Tests

Full test coverage for SPEC-02:

| Test | What It Verifies |
|------|-----------------|
| test_phase_id_is_1b | phase_id property returns "1b" |
| test_sub_steps_returns_expected_list | sub_steps order and content |
| test_executor_self_registers_for_phase_1b | get_executor("1b") returns registered executor |
| test_execute_produces_prd_md | prd.md exists after execute() |
| test_execute_produces_screen_spec_json | screen-spec.json exists after execute() |
| test_prd_md_has_moscow_labels | Must/Should/Could/Won't all present |
| test_prd_md_has_component_inventory_section | ## Component Inventory section present |
| test_prd_md_has_route_structure_section | ## Route Structure section present |
| test_prd_md_has_responsive_breakpoint_info | mobile/tablet/desktop keywords present |
| test_screen_spec_is_valid_json_with_screens_list | valid JSON with non-empty screens list |
| test_each_screen_has_required_keys | route/layout/components/states/responsive all present |
| test_component_names_in_screen_spec_present_in_prd | cross-validation passes on valid data |
| test_execute_returns_failure_when_component_names_mismatch | PhaseResult(success=False) on UnknownWidgetXYZ |
| test_execute_returns_success_phase_result | PhaseResult(success=True) with artifacts list |
| test_execute_returns_artifacts_containing_deliverable_paths | prd.md and screen-spec.json in artifacts |
| test_execute_returns_failure_when_agent_returns_empty | PhaseResult(success=False) on empty result |
| test_quality_self_assessment_generated_after_execute | quality-self-assessment-1b.json written |
| test_phase_1a_idea_validation_content_injected_into_prompt | "CompetitorAlpha" in run_spec_agent prompt |
| test_phase_1a_tech_feasibility_rendering_strategy_injected_into_prompt | "ISR" in run_spec_agent prompt |

### tools/contract_pipeline_runner.py — Executor Import Added

Added after `import tools.phase_executors.phase_1a_executor`:

```python
import tools.phase_executors.phase_1b_executor  # noqa: F401
```

## Test Results

- 19 new tests in `tests/test_phase_1b_executor.py` — all passing
- Full suite: 146/146 passing (was 127 before this plan)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

All created/modified files verified on disk.
Commits f999fbe (RED) and 37be891 (GREEN) confirmed present.
Full test suite 146/146 passing.
