---
phase: 16-mcp-infrastructure-hardening
plan: 01
subsystem: infra
tags: [mcp, fastmcp, tool-annotations, refactor, tdd]

# Dependency graph
requires: []
provides:
  - "web_app_factory/_tool_impls.py with 7 async impl_* functions (shared business logic)"
  - "mcp_server.py refactored to thin stdio transport wrapper with ToolAnnotations on all 7 tools"
  - "test_tool_impls.py: CI guard for impl module structure and function existence"
  - "test_tool_annotations.py: CI guard for annotation completeness and safety values"
affects:
  - 16-02-PLAN (HTTP transport — will import from _tool_impls directly)
  - future-mcp-servers (pattern: transport wrappers delegate to impl layer)

# Tech tracking
tech-stack:
  added: [mcp.types.ToolAnnotations]
  patterns:
    - "Impl layer pattern: _tool_impls.py holds business logic; transports are thin wrappers"
    - "TDD with separate RED commit before GREEN implementation"
    - "Lazy imports inside function bodies (preserved from original pattern)"

key-files:
  created:
    - web_app_factory/_tool_impls.py
    - tests/test_tool_impls.py
    - tests/test_tool_annotations.py
  modified:
    - web_app_factory/mcp_server.py
    - tests/test_mcp_tools.py

key-decisions:
  - "Helper functions (_slugify, _format_disk_status, _scan_disk_runs) moved to _tool_impls.py — they are business logic, not transport-specific"
  - "waf_stop_dev_server: destructiveHint=True (terminates process); waf_get_status: readOnlyHint=True; waf_generate_app: openWorldHint=True (network calls to pipeline)"
  - "No module-level singletons in _tool_impls.py — _STORE/_EXECUTOR/_REGISTRY remain in their existing homes"
  - "test_mcp_tools.py mock paths updated from mcp_server._scan_disk_runs to _tool_impls._scan_disk_runs after function moved"

patterns-established:
  - "Impl layer: every transport server imports from _tool_impls.py, never reimplements logic"
  - "ToolAnnotations: readOnlyHint/destructiveHint/openWorldHint must all be non-None on all tools"
  - "TDD: RED commit (test_*) before GREEN commit (feat) for clear audit trail"

requirements-completed: [MCPH-01, MCPH-03]

# Metrics
duration: 20min
completed: 2026-03-24
---

# Phase 16 Plan 01: MCP Infrastructure Hardening — Impl Extraction Summary

**7 waf_* tool bodies extracted to shared `_tool_impls.py` layer; `mcp_server.py` slimmed to 267-line thin stdio wrapper with ToolAnnotations on all 7 tools**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-24T13:30:00Z
- **Completed:** 2026-03-24T13:50:00Z
- **Tasks:** 1 (TDD: RED + GREEN + auto-fix)
- **Files modified:** 5

## Accomplishments

- Created `web_app_factory/_tool_impls.py` with 7 async `impl_*` functions — the single source of truth for tool behavior across all transports
- Refactored `mcp_server.py` from 406 to 267 lines: pure thin wrappers delegating via `return await impl_*(...)` with zero business logic in tool bodies
- Added `ToolAnnotations` to all 7 stdio tools with all three required safety hints set (readOnly/destructive/openWorld) per safety classification table
- Created `tests/test_tool_impls.py` (4 tests) and `tests/test_tool_annotations.py` (6 tests) — total 33 tests passing

## Task Commits

Each task was committed atomically:

1. **RED: Failing tests for impl extraction and annotations** — `1e4b54a` (test)
2. **GREEN: Extract impl layer and add ToolAnnotations** — `ef3f918` (feat)

_Note: TDD task — RED commit before GREEN implementation_

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified

- `web_app_factory/_tool_impls.py` — New: 293-line shared impl layer with 7 async impl_* functions and helpers
- `web_app_factory/mcp_server.py` — Refactored: 406→267 lines, thin wrappers + ToolAnnotations on all 7 tools
- `tests/test_tool_impls.py` — New: 4 CI tests guarding _tool_impls structure
- `tests/test_tool_annotations.py` — New: 6 CI tests guarding annotation completeness and safety values
- `tests/test_mcp_tools.py` — Updated: 3 mock patches updated from `mcp_server` to `_tool_impls` module path

## Decisions Made

- Helper functions (`_slugify`, `_format_disk_status`, `_scan_disk_runs`) moved to `_tool_impls.py` — they contain business logic (path resolution, disk I/O), not transport concerns
- `waf_stop_dev_server` classified as destructive (sends SIGTERM/SIGKILL to process); `waf_get_status` and `waf_list_runs` classified as readOnly; `waf_generate_app` classified as openWorld (calls external pipeline services)
- `_tool_impls.py` has no module-level singletons — `_STORE`, `_EXECUTOR`, `_REGISTRY` remain in `_progress_store` and `_pipeline_bridge` to preserve existing singleton ownership

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `_scan_disk_runs` mock path in test_mcp_tools.py**
- **Found during:** Task 1 (GREEN verification)
- **Issue:** `tests/test_mcp_tools.py` patched `web_app_factory.mcp_server._scan_disk_runs` but the function moved to `web_app_factory._tool_impls` — 3 tests failed with `AttributeError: does not have attribute '_scan_disk_runs'`
- **Fix:** Updated 3 `patch()` calls from `web_app_factory.mcp_server._scan_disk_runs` to `web_app_factory._tool_impls._scan_disk_runs`
- **Files modified:** `tests/test_mcp_tools.py`
- **Verification:** All 23 original tests pass after fix
- **Committed in:** `ef3f918` (included in GREEN implementation commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug introduced by refactoring)
**Impact on plan:** Necessary correction — mock paths must match where functions actually live. No scope creep.

## Issues Encountered

None beyond the auto-fixed mock path issue above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `_tool_impls.py` is the shared business logic layer ready for HTTP transport import in Plan 02
- All 33 tests green (10 new + 23 existing)
- Both `mcp_server.py` (267 lines) and `_tool_impls.py` (293 lines) are code-health compliant (< 300/400 line thresholds)
- MCPH-01 (impl extraction) and MCPH-03 (partial: stdio annotations) requirements satisfied
- Plan 02 (HTTP server) can now import `from web_app_factory._tool_impls import impl_*` directly

---
*Phase: 16-mcp-infrastructure-hardening*
*Completed: 2026-03-24*
