---
phase: 01-infrastructure
plan: "04"
subsystem: cli-pipeline-wiring
tags: [cli, preflight, pipeline-runner, tdd]
dependency_graph:
  requires: [01-02, 01-03]
  provides: [factory-cli, startup-preflight, contract-pipeline-runner]
  affects: [all-future-phases]
tech_stack:
  added: []
  patterns: [argparse-positional-or-named, dependency-injection-for-testability, phase-executor-registry-dispatch, resume-from-state]
key_files:
  created:
    - factory.py
    - pipeline_runtime/startup_preflight.py
    - tools/contract_pipeline_runner.py
    - tests/test_factory_cli.py
    - tests/test_startup_preflight.py
    - tests/test_contract_runner.py
  modified:
    - tests/test_contract_runner.py
decisions:
  - "Claude CLI checked via --version not -p (avoids known subprocess hang bug in issue 24481)"
  - "Registry isinstance check requires real PhaseExecutor subclasses in tests (not MagicMock)"
  - "run_pipeline uses resume_run_id + state inspection to skip completed phases (not just position)"
  - "skip_gates=True parameter added for unit test isolation (no filesystem artifacts needed)"
metrics:
  duration_seconds: 251
  completed_date: "2026-03-21"
  tasks_completed: 2
  files_created: 6
requirements_satisfied:
  - PIPE-01
  - PIPE-06
  - PIPE-07
---

# Phase 01 Plan 04: CLI Entry Point, Startup Preflight, and Pipeline Runner Summary

CLI wiring with argparse (positional + named idea), web-only startup preflight (Node.js ≥ 20.9, npm, Vercel CLI, Claude CLI via --version), and YAML-driven contract pipeline runner with phase ordering, gate blocking, and resume support.

## What Was Built

### factory.py (244 lines)
CLI entry point that:
- Accepts idea via positional arg or `--idea` flag
- Derives `--project-dir` from idea slug when not specified
- Runs startup preflight before pipeline execution
- Validates YAML contract against JSON schema (CONT-03)
- `--dry-run` mode lists phases without executing
- `--resume RUN_ID` resumes from saved state
- `--unsafe-no-gates` debug flag for skipping gate checks
- `--output-json` for structured output to file

### pipeline_runtime/startup_preflight.py (327 lines)
Web-adapted preflight checks:
- `_check_nodejs()`: validates node >= 20.9.0 with version tuple comparison
- `_check_npm()`: checks npm presence
- `_check_vercel_cli()`: checks vercel CLI presence
- `_check_python_version()`: validates Python >= 3.10
- `_check_claude_cli()`: checks `claude --version` (avoids known `claude -p` subprocess hang bug)
- `run_startup_preflight()`: aggregates all checks, writes `startup-preflight.json`
- All checks use dependency injection (which, run_subprocess) for full testability
- Lock file changed from `.ios-factory-run.lock` to `.web-factory-run.lock`

### tools/contract_pipeline_runner.py (307 lines)
YAML-driven pipeline runner:
- `load_contract()`: loads YAML + validates against JSON schema via jsonschema
- `run_pipeline()`: iterates PHASE_ORDER, dispatches to registered executors via registry
- Calls `generate_quality_self_assessment()` after each phase success (CONT-04)
- Gate checking: artifact existence + output marker validation
- Resume: loads state and skips phases with "completed" status
- Returns structured summary dict with status/run_id/phases_executed/phases_skipped

## Test Results

95 tests passing total (58 pre-existing + 37 new):
- `test_factory_cli.py`: 14 tests — argparse, defaults, flag combinations, project-dir derivation
- `test_startup_preflight.py`: 16 tests — all check functions + aggregation with DI mocks
- `test_contract_runner.py`: 7 tests — YAML loading, phase ordering, gate blocking, resume

## Verification

- `uv run python factory.py --help` shows all expected flags: --idea, --project-dir, --deploy-target, --framework, --dry-run, --resume, --unsafe-no-gates, --output-json
- `load_contract('contracts/pipeline-contract.web.v1.yaml')` loads 5 phases without error
- `uv run pytest tests/ -v` → 95 passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MagicMock fails PhaseExecutor isinstance check**
- **Found during:** Task 2 (test_contract_runner.py run_pipeline tests)
- **Issue:** The executor registry has `isinstance(executor, PhaseExecutor)` validation that rejects `MagicMock`. Tests couldn't use MagicMock for executor stubs.
- **Fix:** Replaced MagicMock-based executors with real `PhaseExecutor` subclasses: `StubExecutor` (simple pass/fail) and `TrackingExecutor` (appends to call_log). This is actually a better test design.
- **Files modified:** `tests/test_contract_runner.py`
- **Commit:** 335fe69 (included in implementation commit)

## Self-Check: PASSED

All created files exist. All commits verified:
- 9f0798f: test(01-04) — RED failing tests
- 335fe69: feat(01-04) — GREEN implementation
