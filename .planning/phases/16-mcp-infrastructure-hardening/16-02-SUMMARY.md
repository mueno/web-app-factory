---
phase: 16-mcp-infrastructure-hardening
plan: 02
subsystem: infra
tags: [mcp, fastmcp, http-transport, openai-apps, tdd, ci]

# Dependency graph
requires:
  - "16-01 (web_app_factory/_tool_impls.py shared impl layer)"
provides:
  - "web_app_factory/openai_mcp_server.py: HTTP transport wrapper with 7 annotated waf_* tools"
  - "pyproject.toml: web-app-factory-mcp-http console script entry point"
  - "tests/test_openai_mcp_server.py: 11 smoke tests for HTTP server structure, tool parity, annotation parity, entry point"
  - "tests/test_mcp_server_tool_names.py: extended CI coverage with 3 new invariants for HTTP server"
affects:
  - Phase 21 (OpenAI Apps Distribution — HTTP transport is the delivery mechanism)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "HTTP transport: mcp.run(transport='http') — FastMCP binds to 0.0.0.0:8000, endpoint /mcp"
    - "Dual transport: stdio (mcp_server.py) + HTTP (openai_mcp_server.py) share _tool_impls.py, never cross-import"
    - "TDD: RED commit (test) before GREEN commit (feat) for audit trail"

key-files:
  created:
    - web_app_factory/openai_mcp_server.py
    - tests/test_openai_mcp_server.py
  modified:
    - pyproject.toml
    - tests/test_mcp_server_tool_names.py

key-decisions:
  - "HTTP server is a separate FastMCP instance — never imports mcp_server.py and vice versa; both import _tool_impls.py only"
  - "Annotation values copied exactly from mcp_server.py (same safety classification per tool)"
  - "Pre-existing test failure (test_deploy_target_github_pages in test_factory_cli.py) out of scope — unrelated to MCP infrastructure"

requirements-completed: [MCPH-02, MCPH-03, MCPH-04]

# Metrics
duration: 15min
completed: 2026-03-24
---

# Phase 16 Plan 02: MCP Infrastructure Hardening — HTTP Transport Summary

**HTTP transport MCP server created with all 7 waf_* annotated tools over HTTP; CI extended to cover both stdio and HTTP servers for waf_ prefix enforcement**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-24T13:45:00Z
- **Completed:** 2026-03-24T13:58:00Z
- **Tasks:** 2 (Task 1: TDD RED+GREEN; Task 2: CI extension)
- **Files modified:** 4

## Accomplishments

- Created `web_app_factory/openai_mcp_server.py` (274 lines): HTTP transport wrapper with all 7 waf_* tools delegating to `_tool_impls.py`, identical `ToolAnnotations` values as the stdio server
- Added `web-app-factory-mcp-http` console script to `pyproject.toml` pointing to `openai_mcp_server:main`
- Created `tests/test_openai_mcp_server.py` (11 tests): module importability, mcp/main attributes, tool count, name parity with stdio, annotation completeness, annotation parity, entry point resolution
- Extended `tests/test_mcp_server_tool_names.py`: added `http_mcp` fixture and 3 new tests — `test_http_tools_have_waf_prefix`, `test_no_tool_name_collision_http_internal`, `test_http_stdio_tool_parity`
- Total: 47 plan-relevant tests passing (11 new + 36 pre-existing)

## Task Commits

1. **RED: Failing tests for HTTP server** — `ac11dcb` (test)
2. **GREEN: HTTP server implementation + pyproject.toml entry point** — `61b8e6f` (feat)
3. **CI: Extend waf_ prefix assertion to HTTP server** — `6c79993` (feat)

## Files Created/Modified

- `web_app_factory/openai_mcp_server.py` — New: 274-line HTTP transport thin wrapper, 7 annotated waf_* tools, main() calls mcp.run(transport="http")
- `pyproject.toml` — Modified: added `web-app-factory-mcp-http = "web_app_factory.openai_mcp_server:main"`
- `tests/test_openai_mcp_server.py` — New: 11 tests covering HTTP server structure, tool parity, annotation parity, entry point
- `tests/test_mcp_server_tool_names.py` — Extended: 3 new tests + http_mcp fixture + updated docstring

## Decisions Made

- HTTP server (`openai_mcp_server.py`) creates its own `FastMCP` instance and never imports from `mcp_server.py`. Both files import exclusively from `_tool_impls.py`. This avoids circular imports and keeps each transport fully independent.
- Annotation values on the HTTP server are identical to the stdio server (verified by `test_http_annotation_values_match_stdio`).

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Pre-existing test failure `tests/test_factory_cli.py::TestFactoryCLIFlags::test_deploy_target_github_pages` — present before Plan 02 changes; out of scope per SCOPE BOUNDARY rule (not caused by current task's changes). Logged in deferred-items.

## User Setup Required

None — no external service configuration required to use the HTTP server. ChatGPT connection requires standard MCP HTTP configuration pointing to `http://your-host:8000/mcp`.

## Phase 16 Completion

All 4 requirements satisfied across Plans 01 + 02:
- MCPH-01: Impl extraction to `_tool_impls.py` (Plan 01)
- MCPH-02: HTTP transport entry point serving all 7 waf_* tools (Plan 02)
- MCPH-03: Both stdio AND HTTP servers have all tools annotated with ToolAnnotations (Plan 01 + Plan 02)
- MCPH-04: CI assertion extended to cover both stdio and HTTP tool registrations (Plan 02)

---
*Phase: 16-mcp-infrastructure-hardening*
*Completed: 2026-03-24*
