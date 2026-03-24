---
phase: 12-environment-detection-distribution
plan: "01"
subsystem: env-checker
tags: [tdd, environment-detection, security, subprocess-safety]
dependency_graph:
  requires:
    - pipeline_runtime/startup_preflight.py
    - web_app_factory/_keychain.py
    - tools/deploy_providers/gcp_provider.py
  provides:
    - web_app_factory/_env_checker.py (check_env, install_tool, format_env_report)
  affects:
    - Phase 12 Plan 02: waf_check_env MCP tool (will import _env_checker)
tech_stack:
  added: []
  patterns:
    - TDD (RED/GREEN/REFACTOR)
    - allowlist security pattern for subprocess injection prevention
    - platform-aware install command table (darwin/linux)
    - module-level import patching for testability
key_files:
  created:
    - web_app_factory/_env_checker.py
    - tests/test_env_checker.py
  modified: []
decisions:
  - "Patch target is web_app_factory._env_checker.* (module binding), not pipeline_runtime.startup_preflight.* (source module) — required because _env_checker uses 'from X import f' style"
  - "Python status always 'present' when MCP server is running (per RESEARCH.md Pitfall 6) — simplifies logic and avoids false negatives"
  - "_INSTALL_ARGS keyed by (tool, platform) — missing key means auto-install unavailable, returns manual instructions"
  - "node on linux has no _INSTALL_ARGS entry — too many distro variants for single-command install"
metrics:
  duration_seconds: 259
  completed_date: "2026-03-24"
  tasks_completed: 1
  files_created: 2
  files_modified: 0
---

# Phase 12 Plan 01: Environment Checker Module Summary

TDD implementation of `_env_checker.py` providing structured ToolStatus-based environment detection with platform-aware install commands, Vercel auth scope warnings, and allowlist-validated subprocess installs.

## What Was Built

`web_app_factory/_env_checker.py` — the business logic layer for the `waf_check_env` MCP tool (Plan 02). Decoupled from MCP concerns for full test coverage.

### Functions Exported

**`check_env(deploy_target: str) -> list[dict]`**
- Always checks: node (>= 20.9.0), npm, python (always present)
- For `deploy_target='vercel'`: adds vercel CLI check + VERCEL_TOKEN auth detection
- For `deploy_target='gcp'`: adds gcloud CLI check + auth via `_check_gcloud_auth`
- For `deploy_target='local'`: node/npm/python only, no deploy-specific CLIs
- Returns ToolStatus dicts with keys: `tool`, `status`, `version_found`, `version_required`, `install_command`, `note`
- Status values: `present`, `outdated`, `missing`, `present_unauth`

**`install_tool(tool_to_install: str) -> str`**
- Validates against `_INSTALLABLE_TOOLS` frozenset `{'node', 'npm', 'vercel', 'gcloud'}` BEFORE any subprocess call
- Looks up `_INSTALL_ARGS[(tool, platform)]` for subprocess-safe list args
- Runs `subprocess.run(args, capture_output=True, text=True, timeout=120, check=False)` — no `shell=True`
- Returns manual instructions when no `_INSTALL_ARGS` entry exists (e.g., node on linux)

**`format_env_report(statuses, install_result=None) -> str`**
- Renders markdown table with columns: Tool, Status, Version Found, Required, Install Command
- Appends "Environment is ready" when all statuses are `present`
- Includes `waf_check_env` with `execute_install` instruction when tools are missing/outdated
- Appends per-tool notes (Vercel scope warning, gcloud auth issues) below table

### Internal Architecture

- `_INSTALL_COMMANDS`: `dict[(tool, platform), str]` — human-readable multi-line instructions
- `_INSTALL_ARGS`: `dict[(tool, platform), list[str]]` — subprocess-safe args for auto-installable tools
- `_INSTALLABLE_TOOLS`: `frozenset` allowlist for `install_tool` input validation
- `_build_tool_status()`: converts raw preflight check dicts to ToolStatus format
- `_check_gcloud()`: gcloud presence + version + auth wrapper
- `_check_vercel_auth()`: VERCEL_TOKEN env var → keychain fallback detection

## Test Coverage (18 tests)

| Class | Tests | Coverage |
|-------|-------|---------|
| TestCheckEnv | 6 | check_env for vercel/gcp/local targets; missing/outdated detection |
| TestVercelAuthStatus | 2 | Token present (org-scoped warning); no token (present_unauth) |
| TestInstallCommands | 3 | darwin/linux platform commands; npm references Node.js |
| TestInstallTool | 4 | Allowlist rejection; vercel install args; no shell=True; linux manual |
| TestFormatEnvReport | 3 | Markdown table; all-ok message; missing tool instructions |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock patch targets in tests**
- **Found during:** GREEN phase (first test run)
- **Issue:** Test patches targeted `pipeline_runtime.startup_preflight._check_nodejs` etc., but `_env_checker.py` imports these with `from X import f` style — patches must target the module where the name is bound (`web_app_factory._env_checker._check_nodejs`)
- **Fix:** Updated all 18 patch decorators in test file to target `web_app_factory._env_checker.*` module namespace
- **Files modified:** `tests/test_env_checker.py`
- **Commit:** 561f178 (included in GREEN commit)

None beyond the patch target fix — plan executed correctly after this correction.

## Self-Check: PASSED

Files created:
- `web_app_factory/_env_checker.py` — FOUND
- `tests/test_env_checker.py` — FOUND

Commits:
- `30a788e` — test(12-01): add failing tests (RED phase)
- `561f178` — feat(12-01): implement _env_checker (GREEN + fix)

Verification commands passed:
- `pytest tests/test_env_checker.py -x -q` — 18 passed
- `pytest tests/test_subprocess_audit.py -x -q` — 1 passed (no shell=True)
- `python -c "from web_app_factory._env_checker import check_env, install_tool, format_env_report"` — imports OK
