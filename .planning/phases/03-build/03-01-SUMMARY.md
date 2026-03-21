---
phase: 03-build
plan: "01"
subsystem: build-agent
tags: [build-agent, next.js, typescript, phase-executor, tdd]
dependency_graph:
  requires: [02-03]
  provides: [build_agent_runner, phase_2a_executor, BUILD_AGENT_system_prompt]
  affects: [contract_pipeline_runner, phase_3_gates]
tech_stack:
  added: []
  patterns:
    - "build agent runner with Bash tools (parallel to spec_agent_runner with WebSearch)"
    - "two-step scaffold: deterministic subprocess + agent customization"
    - "self-registration guard for executor reload safety"
key_files:
  created:
    - tools/phase_executors/build_agent_runner.py
    - tools/phase_executors/phase_2a_executor.py
    - tests/test_phase_2a_executor.py
  modified:
    - agents/definitions.py
    - tests/conftest.py
decisions:
  - "Bash tool in allowed_tools (not WebSearch) — build agent writes files and runs shell commands"
  - "cwd=project_dir sandboxes build agent to generated project directory"
  - "max_turns=50 for build agent vs 25 for spec agent — code generation needs more iterations"
  - "--disable-git flag (not --no-git) is the correct create-next-app flag"
  - "Patch path for generate_quality_self_assessment must be module-local (tools.phase_executors.phase_2a_executor.generate_quality_self_assessment)"
  - "iOS zoom term removed from BUILD_AGENT system prompt — rephrased to mobile browser auto-zoom to avoid iOS term"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-21"
  tasks_completed: 2
  files_created: 3
  files_modified: 2
  tests_added: 31
  tests_total: 229
---

# Phase 3 Plan 01: Build Agent Runner and Phase 2a Scaffold Executor Summary

**One-liner:** Build agent runner with Bash/cwd sandboxing and Phase 2a two-step scaffold (create-next-app subprocess + agent customization) with TypeScript strict-mode rules in BUILD_AGENT system prompt.

## What Was Built

### Task 1: Build Agent Runner and BUILD_AGENT System Prompt

**`tools/phase_executors/build_agent_runner.py`** — parallel module to `spec_agent_runner.py`:
- Exports `run_build_agent(prompt, system_prompt, project_dir, max_turns=50) -> str`
- `allowed_tools=["Read", "Write", "Bash"]` — build agent writes files and runs shell commands
- `cwd=project_dir` — sandboxes the agent to the generated project directory
- `max_turns=50` — higher than spec agent's 25 for multi-turn code generation
- `permission_mode="bypassPermissions"` — same pattern as spec agent
- Re-exports `load_phase_quality_criteria` and `build_phase_system_prompt` from spec_agent_runner

**`agents/definitions.py`** — BUILD_AGENT stub replaced with real system prompt (~130 lines):
- Next.js App Router server/client boundary rules
- Explicit rule: NEVER put `"use client"` in `layout.tsx` or `page.tsx`
- Explicit rule: `error.tsx` MUST start with `"use client"` (React error boundary)
- Generate `error.tsx` per route segment with async data (BILD-06)
- TypeScript strict-mode generation rules:
  - `noImplicitAny`: every variable/parameter/return must have explicit type
  - All component props typed with TypeScript interfaces (BILD-03/04)
  - All exported functions with explicit return types
  - NEVER use `@ts-ignore`, `@ts-expect-error`, or `as any` casts
- Mobile-first responsive design with Tailwind CSS v4 (BILD-05)
- npm package validation instruction (BILD-07)
- Anti-gate-gaming instruction (same pattern as SPEC_AGENT)

**`tests/conftest.py`** — added `mock_build_agent_query` fixture:
- Patches `tools.phase_executors.build_agent_runner.query`
- Returns canned ResultMessage for Phase 3+ executor tests

### Task 2: Phase 2a Scaffold Executor

**`tools/phase_executors/phase_2a_executor.py`** — `Phase2aScaffoldExecutor`:
- `phase_id = "2a"`
- `sub_steps = ["scaffold", "customize", "self_assess"]`
- Two-step scaffold approach:
  - **Step 1 (deterministic):** `npx create-next-app@latest {app_name} --typescript --tailwind --app --src-dir --disable-git --use-npm --yes` with `timeout=180`
  - **Step 2 (agent):** `run_build_agent()` customizes scaffold — replaces boilerplate page.tsx, configures `next.config.ts`, adds `error.tsx` with `"use client"`, adds `not-found.tsx` (server component)
  - **Step 3:** `generate_quality_self_assessment()`
- Self-registration guard: `if get_executor("2a") is None: register(Phase2aScaffoldExecutor())`
- Failure path: subprocess non-zero exit → `PhaseResult(success=False, error=stderr)`
- Artifacts: `[str(project_dir / app_name)]`

## Test Coverage

**31 new tests in `tests/test_phase_2a_executor.py`:**
- `TestBuildAgentSystemPrompt` (12 tests): system prompt content verification
- `TestRunBuildAgent` (6 tests): allowed_tools, cwd, max_turns, return value
- `TestPhase2aScaffoldExecutor` (13 tests): phase_id, self-registration, subprocess flags, success/failure paths, quality self-assessment, artifacts

**Full suite: 229 tests passing** (146 prior + 31 new + 2 conftest changes)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock patch path for generate_quality_self_assessment**
- **Found during:** Task 2 GREEN phase
- **Issue:** Tests were patching `tools.quality_self_assessment.generate_quality_self_assessment` but the executor uses `from tools.quality_self_assessment import generate_quality_self_assessment` which binds the name in the executor module. The patch had no effect.
- **Fix:** Changed patch path to `tools.phase_executors.phase_2a_executor.generate_quality_self_assessment` (module-local binding)
- **Files modified:** `tests/test_phase_2a_executor.py`
- **Commit:** 42f885c

**2. [Rule 2 - Bug] Fixed iOS term in BUILD_AGENT system prompt**
- **Found during:** Task 1 GREEN phase
- **Issue:** "prevent iOS zoom on input focus" in the system prompt contained "iOS" which triggered the `test_no_ios_swift_xcode_references` test (per the plan: zero iOS/Swift/Xcode references)
- **Fix:** Rephrased to "prevent mobile browser auto-zoom on input focus"
- **Files modified:** `agents/definitions.py`
- **Commit:** 9336681

## Self-Check

Checking created files exist:

- FOUND: tools/phase_executors/build_agent_runner.py
- FOUND: tools/phase_executors/phase_2a_executor.py
- FOUND: tests/test_phase_2a_executor.py
- FOUND: 60b0d57 (TDD RED commit)
- FOUND: 9336681 (Task 1 GREEN commit)
- FOUND: 42f885c (Task 2 GREEN commit)

## Self-Check: PASSED
