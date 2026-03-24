---
phase: 15-declare-playwright-dependency
plan: 01
subsystem: testing
tags: [playwright, dependency-management, e2e, uv, pyproject]

# Dependency graph
requires:
  - phase: 13-pipeline-quality
    provides: E2E gate implementation (tools/gates/e2e_gate.py) with playwright import guard

provides:
  - playwright>=1.50.0 declared as direct dependency in pyproject.toml
  - uv.lock regenerated with playwright v1.58.0 resolved
  - E2E gate BLOCKED message updated to guide on browser binary install (not Python package install)
affects:
  - fresh uvx installations (playwright now auto-installed)
  - users encountering the E2E gate BLOCKED state

# Tech tracking
tech-stack:
  added: [playwright>=1.50.0 (now a declared direct dependency, was optional/implicit)]
  patterns: [direct dependency declaration for tools used in pipeline gates]

key-files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
    - tools/gates/e2e_gate.py

key-decisions:
  - "playwright added to [project.dependencies], not [project.optional-dependencies] or [dependency-groups] — uvx only installs direct dependencies"
  - "BLOCKED message updated to reflect two-step separation: Python package auto-installed by uvx; browser binaries require explicit 'playwright install chromium'"
  - "try/except import block in e2e_gate.py kept unchanged — safety fallback per prior user decision"

patterns-established:
  - "Pipeline gate dependencies belong in [project.dependencies] so uvx installs them on first run"

requirements-completed: [QUAL-02]

# Metrics
duration: 5min
completed: 2026-03-24
---

# Phase 15 Plan 01: Declare Playwright Dependency Summary

**playwright>=1.50.0 added to pyproject.toml direct dependencies; E2E gate BLOCKED message updated from pip-install to browser-binary-only guidance; uvx now auto-installs playwright on fresh install**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-24T09:11:52Z
- **Completed:** 2026-03-24T09:16:30Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- playwright>=1.50.0 added to `[project.dependencies]` in pyproject.toml (resolves as v1.58.0 in lockfile)
- uv.lock regenerated; playwright, greenlet, and pyee added to resolved packages
- E2E gate BLOCKED message changed from `"pip install playwright && playwright install chromium"` to `"playwright browser binaries not found — run: playwright install chromium"`
- All 21 e2e_gate tests pass unchanged; full suite has 703 passing, 1 pre-existing failure (test_deploy_target_github_pages)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add playwright to direct dependencies and regenerate lockfile** - `c33e9c1` (feat)
2. **Task 2: Update E2E gate BLOCKED message and verify all tests pass** - `6f799d2` (fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `pyproject.toml` - Added `"playwright>=1.50.0"` to `[project.dependencies]` (alphabetical between mcp and pyyaml)
- `uv.lock` - Regenerated; playwright v1.58.0, greenlet v3.3.2, pyee v13.0.1 added
- `tools/gates/e2e_gate.py` - Updated BLOCKED message to guide on browser binary installation only

## Decisions Made

- `playwright` goes in `[project.dependencies]`, not optional-dependencies or dependency-groups — uvx only installs direct dependencies (QUAL-02 requirement)
- The updated BLOCKED message reflects the two-step reality: Python package is auto-installed; browser binaries require a separate user command
- The try/except import block (safety fallback) remains unchanged per earlier user decision

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. Users still need to run `playwright install chromium` once for browser binaries, but the Python package is now auto-installed by uvx.

## Next Phase Readiness

Phase 15 is complete. QUAL-02 is closed: `uvx web-app-factory` installs playwright automatically; the only remaining user action for E2E gate functionality is `playwright install chromium`.

---
*Phase: 15-declare-playwright-dependency*
*Completed: 2026-03-24*
