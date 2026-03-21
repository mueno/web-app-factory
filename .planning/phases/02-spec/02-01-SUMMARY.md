---
phase: 02-spec
plan: 01
subsystem: agents
tags: [spec-agent, claude-sdk, tdd, SPEC-04]
dependency_graph:
  requires: []
  provides:
    - SPEC_AGENT system prompt (web-specific, no iOS references)
    - tools/phase_executors/spec_agent_runner.py (run_spec_agent, load_phase_quality_criteria, build_phase_system_prompt)
    - tests/conftest.py mock_agent_query fixture
  affects:
    - tools/phase_executors/phase_1a_executor.py (Plan 02-02)
    - tools/phase_executors/phase_1b_executor.py (Plan 02-03)
tech_stack:
  added:
    - claude_agent_sdk query() with ClaudeAgentOptions
    - asyncio.run() sync/async bridge pattern
    - PyYAML safe_load for contract quality criteria extraction
  patterns:
    - TDD red-green cycle with ResultMessage mock fixture
    - Quality criteria injection into agent system prompt
    - Anti-gate-gaming instruction appended to every phase prompt
key_files:
  created:
    - tools/phase_executors/spec_agent_runner.py
    - tests/test_phase_spec_agent.py
  modified:
    - agents/definitions.py (SPEC_AGENT stub → real web-specific prompt)
    - tests/conftest.py (added mock_agent_query fixture)
decisions:
  - "mock_agent_query passes all required ResultMessage constructor positional args (subtype, duration_ms, duration_api_ms, is_error, num_turns, session_id)"
  - "run_spec_agent allowed_tools restricted to WebSearch/Read/Write — no shell execution"
  - "asyncio.run() used for sync/async bridge (not nest_asyncio) per existing ios-app-factory pattern"
metrics:
  duration: "~10 minutes"
  completed_date: "2026-03-21"
  tasks_completed: 1
  files_changed: 4
requirements_satisfied: [SPEC-04]
---

# Phase 2 Plan 01: Spec Agent Definition and Runner Utility Summary

Real web-specific SPEC_AGENT system prompt with zero iOS references, shared async-to-sync agent runner with quality-criteria injection, and mock fixture enabling downstream executor tests without hitting the real Claude API.

## What Was Built

### agents/definitions.py — Real SPEC_AGENT System Prompt

Replaced the `"System prompt to be defined in Phase 2"` stub with a substantive ~90-line system prompt covering:
- Web stack context (Next.js App Router, Tailwind CSS v4, Vercel, NextAuth.js/Clerk)
- Competitor research instructions requiring WebSearch tool usage (no hallucinated names)
- Phase 1a deliverable format: idea-validation.md sections, tech-feasibility-memo.json structure
- Phase 1b ordering rule: write prd.md FIRST, derive screen-spec.json from it
- Anti-gate-gaming instruction: produce substantive output, not minimum-viable gate passers
- SPEC-04 compliance: zero iOS/Swift/Xcode/App Store/HealthKit/UIKit references

### tools/phase_executors/spec_agent_runner.py — Shared Runner Utility

Three exported functions:
- `load_phase_quality_criteria(phase_id, contract_path) -> list[str]`: reads YAML contract, extracts all quality_criteria strings for the given phase across all deliverables
- `build_phase_system_prompt(base_prompt, quality_criteria) -> str`: appends `## Quality Criteria` section with anti-gate-gaming instruction
- `run_spec_agent(prompt, system_prompt, project_dir, max_turns=25) -> str`: wraps `claude_agent_sdk.query()` in `asyncio.run()`, returns `ResultMessage.result` text or empty string

### tests/conftest.py — mock_agent_query Fixture

Added `mock_agent_query` fixture that patches `tools.phase_executors.spec_agent_runner.query` to return an async generator yielding a `ResultMessage` with `result="mocked agent output"`. Correctly passes all 6 required positional arguments to `ResultMessage.__init__`.

## Test Results

- 14 new tests in `tests/test_phase_spec_agent.py` — all passing
- Full suite: 109/109 passing (was 95 before this plan)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ResultMessage requires 6 positional constructor arguments**
- **Found during:** Task 1 GREEN phase — mock_agent_query fixture setup error
- **Issue:** `ResultMessage(result="mocked agent output")` raised `TypeError: missing 6 required positional arguments` because the dataclass has `subtype`, `duration_ms`, `duration_api_ms`, `is_error`, `num_turns`, and `session_id` as required fields before `result`
- **Fix:** Passed all required positional args in the fixture: `subtype="result"`, `duration_ms=100`, `duration_api_ms=100`, `is_error=False`, `num_turns=1`, `session_id="test-session-id"`
- **Files modified:** `tests/conftest.py`
- **Commit:** 835a051 (included in GREEN commit)

## Self-Check: PASSED

All created files verified on disk. Commits a4a7ad8 (RED) and 835a051 (GREEN) confirmed present.
Full test suite 109/109 passing.
