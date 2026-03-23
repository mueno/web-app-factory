---
phase: 08-mcp-infrastructure-foundation
plan: 02
subsystem: infra
tags: [async, threadpool, subprocess-security, input-validation, shell-injection, path-traversal, tdd]

# Dependency graph
requires:
  - "08-01: web_app_factory package skeleton with FastMCP server"
provides:
  - "ThreadPoolExecutor bridge: start_pipeline_async() returns run_id immediately"
  - "Input validation: validate_slug, validate_idea, validate_project_dir, safe_shell_arg"
  - "Static CI audit: no shell=True in web_app_factory/ or tools/ production code"
affects:
  - "09-mcp-generate-tool"
  - "10-mcp-status-list-tools"
  - "11-mcp-cloud-deployment"
  - "12-mcp-project-cleanup"
  - "13-pipeline-quality"

# Tech tracking
tech-stack:
  added:
    - "concurrent.futures.ThreadPoolExecutor (max_workers=3, thread_name_prefix=waf-pipeline)"
    - "asyncio.run_in_executor pattern for non-blocking pipeline execution"
    - "shlex.quote for safe_shell_arg implementation"
    - "pathlib.Path.relative_to() for path traversal prevention"
  patterns:
    - "run_id generated BEFORE executor submission (Pitfall 5: avoids queue-full blocking)"
    - "_run_pipeline_sync() wrapper isolates import boundary for test patching"
    - "_ACTIVE_RUNS dict tracks all in-flight pipeline futures"
    - "Static subprocess audit catches shell=True regressions in CI"

key-files:
  created:
    - "web_app_factory/_pipeline_bridge.py"
    - "web_app_factory/_input_validator.py"
    - "tests/test_pipeline_bridge.py"
    - "tests/test_input_validator.py"
    - "tests/test_subprocess_audit.py"
  modified: []

key-decisions:
  - "Use _run_pipeline_sync() as a thin wrapper around run_pipeline import — this single boundary enables test patching without complex import machinery"
  - "Generate run_id synchronously BEFORE loop.run_in_executor() call — prevents subtle blocking if thread pool queue is momentarily full (research Pitfall 5)"
  - "Regex + explicit shell metacharacter set for slug validation — defense in depth: both pattern and explicit character rejection"
  - "Static audit test (test_subprocess_audit.py) scans production files only, skipping test_ files — catches future regressions in CI without false positives"

patterns-established:
  - "Pattern: async bridge — start_pipeline_async returns run_id immediately; pipeline runs in ThreadPoolExecutor thread"
  - "Pattern: _run_pipeline_sync wrapper — isolates import boundary for testing without patching internal module state"
  - "Pattern: subprocess audit CI test — static regex scan prevents shell=True regressions from being merged"

requirements-completed:
  - MCPI-03
  - MCPI-04

# Metrics
duration: 3min
completed: 2026-03-23
---

# Phase 8 Plan 02: Async Pipeline Bridge and Input Validation Summary

**ThreadPoolExecutor bridge returning run_id immediately + shell injection / path traversal prevention via validate_slug, validate_idea, validate_project_dir, and a static CI audit blocking any future shell=True regression**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-23T07:13:34Z
- **Completed:** 2026-03-23T07:17:07Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Created `web_app_factory/_pipeline_bridge.py` with `start_pipeline_async()` that returns a run_id string in under 1 second while the pipeline runs in a background ThreadPoolExecutor thread; `_ACTIVE_RUNS` dict tracks all in-flight futures
- Created `web_app_factory/_input_validator.py` with four security functions: `validate_slug` (rejects shell metacharacters, path traversal, null bytes, >50 chars), `validate_idea` (strips whitespace, rejects empty/null bytes/>500 chars), `validate_project_dir` (enforces Path.relative_to(output_base) boundary), `safe_shell_arg` (shlex.quote wrapper)
- Established static CI audit via `tests/test_subprocess_audit.py` that scans all production Python files in `web_app_factory/` and `tools/` for `shell=True` and `os.system()` — any future regression fails CI immediately
- All 510 tests pass (459 existing + 51 new, including 36 from this plan)

## Task Commits

Each task was committed atomically (TDD: RED + GREEN per task):

1. **Task 1: Async pipeline bridge (RED)** — `d6a460a` (test)
2. **Task 1: Async pipeline bridge (GREEN)** — `b5021fd` (feat)
3. **Task 2: Input validation and static audit (RED)** — `80a702e` (test)
4. **Task 2: Input validation and static audit (GREEN)** — `23fd6a1` (feat)

## Files Created/Modified

- `web_app_factory/_pipeline_bridge.py` — Async bridge: `start_pipeline_async()`, `_EXECUTOR` (ThreadPoolExecutor, 3 workers), `_ACTIVE_RUNS` dict, `_generate_run_id()` (YYYYMMDD-HHMMSS-slug), `_run_pipeline_sync()` (import isolation wrapper)
- `web_app_factory/_input_validator.py` — Security validators: `validate_slug`, `validate_idea`, `validate_project_dir`, `safe_shell_arg`
- `tests/test_pipeline_bridge.py` — 4 tests: run_id immediacy, background execution, format, tracking
- `tests/test_input_validator.py` — 28 tests: slug, idea, project_dir, safe_shell_arg validation paths
- `tests/test_subprocess_audit.py` — 1 static audit test scanning production code for shell injection risks

## Decisions Made

- Used `_run_pipeline_sync()` as an import isolation wrapper — patching `web_app_factory._pipeline_bridge._run_pipeline_sync` in tests avoids the complexity of patching deeply nested import paths inside the `tools` package
- Run_id is generated BEFORE `loop.run_in_executor()` call per research Pitfall 5 — if the thread pool queue is momentarily saturated, the executor submission could block briefly; generating the run_id first guarantees it is returned to the caller with zero delay
- Regex + explicit `_SHELL_META_CHARS` frozenset for slug validation — double defense: the character set rejects metacharacters (`;|&\`$...`) before the regex check, providing clear error messages identifying which characters are problematic

## Deviations from Plan

None — plan executed exactly as written. All four test classes and the static audit test passed on first implementation.

## Issues Encountered

- None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `start_pipeline_async()` is ready for Phase 9 (`waf_generate_app` tool) to call
- Input validators ready for Phase 9 tool handlers to use for request parameter validation
- Static audit CI guard in place — any future `shell=True` addition will fail tests before merge

---
*Phase: 08-mcp-infrastructure-foundation*
*Completed: 2026-03-23*
