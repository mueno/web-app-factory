---
phase: 04-ship
plan: 02
subsystem: testing
tags: [lighthouse, axe-core, httpx, playwright, accessibility, security-headers, link-integrity]

# Dependency graph
requires:
  - phase: 03-build
    provides: GateResult pattern from build_gate.py, gate_result.py dataclass
provides:
  - run_lighthouse_gate function in tools/gates/lighthouse_gate.py
  - run_security_headers_gate function in tools/gates/security_headers_gate.py
  - run_accessibility_gate function in tools/gates/accessibility_gate.py
  - run_link_integrity_gate function in tools/gates/link_integrity_gate.py
  - 68 new tests covering all 4 gate functions
affects:
  - phase 04 plan 03 (phase_3_executor.py will dispatch to these 4 gates)
  - _run_gate_checks in contract_pipeline_runner.py needs new elif branches

# Tech tracking
tech-stack:
  added:
    - playwright (Python, optional runtime dependency — accessibility gate)
    - axe-playwright-python (optional runtime dependency — accessibility gate)
  patterns:
    - TDD RED-GREEN cycle for all new gate functions
    - Module-level optional import with graceful fallback for missing playwright/axe
    - BFS crawl with visited set and depth + count limits

key-files:
  created:
    - tools/gates/lighthouse_gate.py
    - tools/gates/security_headers_gate.py
    - tools/gates/accessibility_gate.py
    - tools/gates/link_integrity_gate.py
    - tests/test_lighthouse_gate.py
    - tests/test_security_headers_gate.py
    - tests/test_accessibility_gate.py
    - tests/test_link_integrity_gate.py
  modified: []

key-decisions:
  - "Lighthouse gate uses --runs=3 for median score mitigating non-determinism (from RESEARCH.md Pitfall 2)"
  - "Security headers gate treats HSTS as advisory-only (Vercel provides it); 4 headers are blocking"
  - "Accessibility gate uses module-level optional import with graceful fallback when playwright/axe not installed"
  - "Link integrity gate: depth 3 / max 50 URLs prevents runaway crawl; per-URL exception handling allows other URLs to continue"
  - "Lighthouse gate writes JSON to tempfile (mkstemp) with cleanup in finally block (TOCTOU-safe)"

patterns-established:
  - "Gate function signature: run_*_gate(url, phase_id='3') -> GateResult with gate_type matching function name"
  - "Optional heavy dependencies (playwright) imported at module level with try/except fallback"
  - "BFS crawler with deque, visited set, (url, depth) tuples for link integrity checking"

requirements-completed: [GATE-02, GATE-03, GATE-04, GATE-07]

# Metrics
duration: 6min
completed: 2026-03-22
---

# Phase 04 Plan 02: Quality Gates Summary

**Four quality gate functions: Lighthouse JSON score parsing with --runs=3 median, httpx security header verification, axe-core critical violation filtering via playwright, and BFS link integrity crawler — all returning GateResult with 68 tests and zero regressions**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-21T15:33:54Z
- **Completed:** 2026-03-21T15:39:23Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Lighthouse gate parses subprocess JSON output, uses --runs=3 for median scores, compares perf/a11y/seo to configurable thresholds (85/90/85 default)
- Security headers gate checks 4 required headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy) via httpx with HSTS as advisory-only
- Accessibility gate runs axe-core via playwright, filters to critical-impact violations only, stores total/critical counts in extra
- Link integrity gate BFS-crawls internal links (depth 3, max 50 URLs), reports 404s as blocking issues, handles per-URL errors gracefully

## Task Commits

Each task was committed atomically:

1. **Task 1: Lighthouse gate and security headers gate** - `965df89` (feat)
2. **Task 2: Accessibility gate and link integrity gate** - `e6f43b5` (feat)

## Files Created/Modified

- `tools/gates/lighthouse_gate.py` - npx lighthouse subprocess, --runs=3, JSON parse, threshold comparison
- `tools/gates/security_headers_gate.py` - httpx GET, 4 required headers check, HSTS advisory
- `tools/gates/accessibility_gate.py` - playwright + axe-core, critical violation filter, optional import with fallback
- `tools/gates/link_integrity_gate.py` - BFS httpx crawler, depth/count limits, 404 detection
- `tests/test_lighthouse_gate.py` - 37 tests: pass/fail/custom-threshold/extra/subprocess-args/errors
- `tests/test_security_headers_gate.py` - 17 tests: pass/fail/case-insensitive/HSTS-advisory/request-error
- `tests/test_accessibility_gate.py` - 11 tests: pass/non-critical-ignored/fail/extra-counts/browser-failure
- `tests/test_link_integrity_gate.py` - 14 tests: pass/404-fail/redirect-ok/external-ignored/depth/max-urls/extra/request-error

## Decisions Made

- Lighthouse `--runs=3` flag: Lighthouse CLI performs 3 runs and reports median scores when this flag is given, reducing non-determinism per RESEARCH.md recommendation
- HSTS advisory (not blocking): Vercel auto-injects HSTS, so its absence in tests is expected; blocking on it would create false failures in CI
- playwright optional import at module level: Allows the module to be imported cleanly even when playwright is not installed (e.g., in CI environments that only run the pipeline unit tests), with a clear runtime error message when the gate is actually invoked
- BFS link crawler with explicit limits: depth 3 and max 50 URLs prevent infinite crawl on large apps; per-URL exception handling ensures one timeout doesn't abort the entire crawl

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Minor: Initial implementation placed playwright imports inside the function body, which prevented `patch("tools.gates.accessibility_gate.sync_playwright")` from working in tests. Fixed by moving imports to module level with try/except fallback. This is covered by the module-level optional import pattern now established.

## User Setup Required

None - no external service configuration required (playwright/axe are optional runtime dependencies, not test-time dependencies).

## Next Phase Readiness

- All 4 gate functions ready for dispatch from `_run_gate_checks()` in `contract_pipeline_runner.py`
- Phase 3 executor (`phase_3_executor.py`) can import and call all 4 functions
- Note: playwright and axe-playwright-python must be installed in the production environment before `run_accessibility_gate` can run against real URLs
- 378 total tests passing (68 new + 310 existing, zero regressions)

---
*Phase: 04-ship*
*Completed: 2026-03-22*
