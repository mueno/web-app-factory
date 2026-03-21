---
phase: 03-build
plan: 02
subsystem: testing
tags: [gates, static-analysis, build, subprocess, regex, tdd]

# Dependency graph
requires:
  - phase: 03-build
    provides: GateResult dataclass and gate_policy.py normalize_gate_result helper

provides:
  - build_gate.py: runs npm run build + tsc --noEmit as subprocess calls, returns GateResult
  - static_analysis_gate.py: regex-scans layout.tsx/page.tsx for 'use client' and src/ for NEXT_PUBLIC_ secrets
  - 52 unit tests covering pass/fail/timeout/edge cases for both gates

affects: [03-03, contract-pipeline-runner gate dispatch wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD red-green: failing tests committed before implementation"
    - "Fail-fast gate: tsc not called if npm build fails"
    - "Exact-file scanning: GATE-05 scans ONLY layout.tsx and page.tsx (not error.tsx or components)"
    - "Regex-based secret detection: NEXT_PUBLIC_*KEY/*SECRET/*TOKEN pattern"

key-files:
  created:
    - tools/gates/build_gate.py
    - tools/gates/static_analysis_gate.py
    - tests/test_build_gate.py
    - tests/test_static_analysis_gate.py
  modified: []

key-decisions:
  - "Build gate uses fail-fast: tsc --noEmit is NOT called if npm run build fails (BILD-04)"
  - "NEXT_TELEMETRY_DISABLED=1 always injected into npm run build env to prevent telemetry hang"
  - "static_analysis_gate scans EXACTLY src/app/layout.tsx and src/app/page.tsx for 'use client' — not error.tsx, not components"
  - "Secret regex NEXT_PUBLIC_(?:.*KEY|.*SECRET|.*TOKEN) catches KEY/SECRET/TOKEN at any position after NEXT_PUBLIC_"
  - "Both gates return GateResult directly without going through normalize_gate_result (simpler, sufficient for these deterministic checks)"

patterns-established:
  - "Gate executor pattern: single exported function run_*_gate(project_dir, phase_id) -> GateResult"
  - "Timeout handling: subprocess.TimeoutExpired caught and returned as GateResult(passed=False) with descriptive message"
  - "Issue format: '{rel_path}:{lineno}: {description}' for all file-scan issues"

requirements-completed: [GATE-01, GATE-05, GATE-06]

# Metrics
duration: 12min
completed: 2026-03-21
---

# Phase 3 Plan 02: Build Gate and Static Analysis Gate Summary

**Build gate executor (npm build + tsc) and static analysis gate (use-client misplacement + NEXT_PUBLIC_ secret detection) with 52 unit tests via TDD**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-21T14:10:00Z
- **Completed:** 2026-03-21T14:22:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Build gate that runs npm run build (with NEXT_TELEMETRY_DISABLED=1) then tsc --noEmit, failing fast on first error
- Static analysis gate scanning exactly layout.tsx and page.tsx for misplaced 'use client' directives (not error.tsx, not components)
- Static analysis gate detecting NEXT_PUBLIC_ variables with secret-pattern suffixes (KEY/SECRET/TOKEN) in src/ and .env files
- 52 new unit tests (27 for build gate, 25 for static analysis gate), all passing; 14 pre-existing failures in test_phase_2a_executor.py remain unchanged (out of scope)

## Task Commits

Each task was committed atomically via TDD (RED then GREEN):

1. **Task 1: Build gate executor (RED)** - `76a6eac` (test)
2. **Task 1: Build gate executor (GREEN)** - `19a72fd` (feat)
3. **Task 2: Static analysis gate (RED)** - `df4163c` (test)
4. **Task 2: Static analysis gate (GREEN)** - `7405232` (feat)

_Note: TDD tasks have two commits each (test → feat)_

## Files Created/Modified

- `tools/gates/build_gate.py` - Build gate executor: runs npm run build + tsc --noEmit
- `tools/gates/static_analysis_gate.py` - Static analysis gate: use-client check + NEXT_PUBLIC_ secret scan
- `tests/test_build_gate.py` - 27 unit tests covering pass/fail/timeout/subprocess args
- `tests/test_static_analysis_gate.py` - 25 unit tests with real temp files (no mocking)

## Decisions Made

- **Fail-fast on npm build**: tsc --noEmit is not called if npm run build fails — reduces total gate time when there are build errors
- **GATE-05 exact-file scanning**: Only layout.tsx and page.tsx are scanned; error.tsx (correct for error boundaries) and component files are intentionally excluded
- **Direct GateResult construction**: Both gates construct GateResult directly rather than using normalize_gate_result, since these are deterministic subprocess/regex checks with no policy decisions needed
- **Timeout message wording**: "timeout" (not "timed out") used in issue messages for consistent test assertions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Minor: Initial timeout message used "timed out" but tests checked for "timeout". Fixed immediately in same GREEN iteration (not a separate deviation, part of normal TDD cycle).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both gate executors ready for dispatch wiring in Plan 03-03
- Build gate requires actual Next.js project directory with node_modules installed to run in production
- Static analysis gate works on any directory structure (no dependencies)
- Pre-existing 14 test failures in test_phase_2a_executor.py will need attention in Plan 03-03 or later

---
*Phase: 03-build*
*Completed: 2026-03-21*

## Self-Check: PASSED

- FOUND: tools/gates/build_gate.py
- FOUND: tools/gates/static_analysis_gate.py
- FOUND: tests/test_build_gate.py
- FOUND: tests/test_static_analysis_gate.py
- FOUND: .planning/phases/03-build/03-02-SUMMARY.md
- FOUND: commit 76a6eac (test: build gate RED)
- FOUND: commit 19a72fd (feat: build gate GREEN)
- FOUND: commit df4163c (test: static analysis gate RED)
- FOUND: commit 7405232 (feat: static analysis gate GREEN)
