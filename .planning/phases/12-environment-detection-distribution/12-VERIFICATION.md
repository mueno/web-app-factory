---
phase: 12-environment-detection-distribution
verified: 2026-03-24T06:30:00Z
status: passed
score: 15/15 must-haves verified
re_verification: false
---

# Phase 12: Environment Detection & Distribution Verification Report

**Phase Goal:** Environment detection, install guidance, and distribution packaging
**Verified:** 2026-03-24T06:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

All truths are drawn from the `must_haves` fields in the two PLAN files (12-01 and 12-02).

#### Plan 01 Truths (ENVS-01, ENVS-02, ENVS-03)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `check_env('vercel')` returns structured ToolStatus dicts for node, npm, python, vercel with status/version/install fields | VERIFIED | `_env_checker.py` lines 243-320; test `test_all_present` passes; all 6 keys confirmed in dict structure |
| 2 | `check_env('gcp')` includes gcloud check; `check_env('vercel')` does not include gcloud check | VERIFIED | Lines 315-316 add `_check_gcloud()` for gcp only; tests `test_gcloud_included_for_gcp` and `test_gcloud_skipped_for_vercel` both pass |
| 3 | Missing tool returns status='missing' with platform-aware install command for macOS or Linux | VERIFIED | `_build_tool_status()` lines 140-147; `_INSTALL_COMMANDS` dict keyed by `(tool, 'darwin'/'linux')`; `test_darwin_command` and `test_linux_command` pass |
| 4 | Outdated tool returns status='outdated' with version_found and version_required | VERIFIED | `_build_tool_status()` line 140 checks `"too old" in reason.lower()`; `test_node_outdated` verifies status='outdated' and version_found='v16.0.0' |
| 5 | Vercel auth check returns 'present_unauth' with scope warning when token is absent | VERIFIED | `_check_vercel_auth()` lines 219-236; `test_unauth_when_no_token` passes; note contains "VERCEL_TOKEN" |
| 6 | `install_tool` rejects unknown tool names via allowlist before any subprocess call | VERIFIED | `_INSTALLABLE_TOOLS` frozenset at line 99; allowlist guard at line 342 before any subprocess call; `test_unknown_tool_rejected` confirms mock_run.assert_not_called() |
| 7 | `install_tool('vercel')` runs subprocess with list args (no shell=True) | VERIFIED | `subprocess.run(install_args, ...)` at line 364 with no shell=True; `test_execute_installs` confirms `cmd == ["npm", "install", "-g", "vercel"]`; `test_no_shell_true` passes |
| 8 | `format_env_report` produces markdown table with per-tool status rows | VERIFIED | Lines 409-439 render `"| Tool | Status | Version Found | Required | Install Command |"` header; `test_produces_markdown_table` and `test_all_ok_message` pass |

#### Plan 02 Truths (TOOL-05)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 9 | `waf_check_env` is registered on the public MCP server with the `waf_` prefix | VERIFIED | `mcp_server.py` line 341: `async def waf_check_env(`; decorator `@mcp.tool()` at line 340; `test_mcp_server_tool_names.py` passes (3 tests) |
| 10 | `waf_check_env` returns a structured per-tool status report covering Node.js, npm, Python, and deploy-target-specific CLIs | VERIFIED | Tool calls `check_env(deploy_target)` via executor (line 375) then `format_env_report(statuses)` (line 390); unit tests confirm all tools appear in output |
| 11 | `waf_check_env` distinguishes missing, outdated, present, and present_unauth statuses | VERIFIED | All four status values defined and tested in `test_env_checker.py`; `format_env_report` maps them to display strings at lines 428-435 |
| 12 | `waf_check_env` with `execute_install=True` and valid `tool_to_install` runs the install | VERIFIED | Lines 379-388: guard checks `execute_install` then runs `install_tool` via executor; guard prevents execution without `tool_to_install` (line 380-385) |
| 13 | `waf_check_env` without `execute_install` returns only the report (no installs) | VERIFIED | Default `execute_install=False`; only `format_env_report(statuses)` returned (line 390) on non-install path |
| 14 | The public MCP server now exposes 7 tools total | VERIFIED | 7 `@mcp.tool()` decorators confirmed: waf_generate_app, waf_get_status, waf_approve_gate, waf_list_runs, waf_start_dev_server, waf_stop_dev_server, waf_check_env |
| 15 | `uv build` produces a distributable wheel without errors | VERIFIED | 12-02-SUMMARY.md records `uv build` success producing both `.whl` and `.tar.gz`; entry point import verified by `python -c "from web_app_factory.mcp_server import main; print('entry point OK')"` — clean |

**Score: 15/15 truths verified**

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `web_app_factory/_env_checker.py` | Environment check logic: check_env, install_tool, format_env_report | VERIFIED | 478 lines; all three functions exported; docstrings and type hints present |
| `tests/test_env_checker.py` | Unit tests covering ENVS-01/02/03 with mocked which/subprocess | VERIFIED | 418 lines (min_lines=100 easily met); 18 test methods across 5 test classes; all 18 pass |
| `web_app_factory/mcp_server.py` | waf_check_env MCP tool registration | VERIFIED | Line 341 defines `async def waf_check_env`; contains `"async def waf_check_env"` per PLAN artifact check |

All artifacts pass all three levels: exists, substantive, wired.

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `web_app_factory/_env_checker.py` | `pipeline_runtime/startup_preflight.py` | `from pipeline_runtime.startup_preflight import _check_nodejs, _check_npm, _check_vercel_cli, _check_python_version` | WIRED | Lines 19-24 in `_env_checker.py`; functions used at lines 260, 263, 266, 279 |
| `web_app_factory/_env_checker.py` | `tools/deploy_providers/gcp_provider.py` | `from tools.deploy_providers.gcp_provider import _check_gcloud_auth` | WIRED | Lazy import at line 200 inside `_check_gcloud()`; called at line 202 with result used at lines 203-205 |
| `web_app_factory/mcp_server.py` | `web_app_factory/_env_checker.py` | lazy import in tool handler body | WIRED | Line 372: `from web_app_factory._env_checker import check_env, format_env_report, install_tool`; all three used in tool body (lines 375, 386, 390) |

All 3 key links verified as WIRED.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ENVS-01 | 12-01 | Auto-detect Node.js, npm, Python, Vercel CLI, gcloud CLI presence and version | SATISFIED | `check_env()` performs all detections per deploy_target; 6 test cases cover all tool/target combinations |
| ENVS-02 | 12-01 | Provide install commands for each missing tool (platform-aware: macOS/Linux) | SATISFIED | `_INSTALL_COMMANDS` dict keyed by `(tool, 'darwin'/'linux')`; Vercel scope warning implemented; `test_darwin_command` and `test_linux_command` verify platform awareness |
| ENVS-03 | 12-01 | Optionally execute install with user permission (not silently) | SATISFIED | `install_tool()` requires explicit allowlist match; `waf_check_env` requires `execute_install=True` AND `tool_to_install` to run install; allowlist guard prevents injection |
| TOOL-05 | 12-02 | `waf_check_env` detects Node.js, Python, CLI tools and reports missing/outdated with install instructions | SATISFIED | Tool registered on MCP server; returns structured markdown report; 36-test suite passes end-to-end |

**No orphaned requirements.** REQUIREMENTS.md traceability table maps all four IDs (ENVS-01, ENVS-02, ENVS-03, TOOL-05) to Phase 12 with status "Complete".

---

## Anti-Patterns Found

No blocking anti-patterns detected.

| File | Check | Result |
|------|-------|--------|
| `_env_checker.py` | TODO/FIXME/PLACEHOLDER | None found |
| `_env_checker.py` | shell=True | Not present (only in comments/docstrings explaining its absence) |
| `_env_checker.py` | Empty return stub | None found |
| `mcp_server.py` | TODO/FIXME/PLACEHOLDER | None found |
| `mcp_server.py` | shell=True | Not present |
| `test_env_checker.py` | All 18 tests pass | Confirmed: 18 passed in 0.05s |
| `test_subprocess_audit.py` | No shell=True in production code | Confirmed: 1 passed |
| `test_mcp_server_tool_names.py` | waf_ prefix and 7-tool count | Confirmed: 3 passed |

Full Phase 12 suite: **36 tests passed** in 0.43s.

File line counts are within code health thresholds (`.claude/rules/25-code-health.md`):
- `_env_checker.py`: 478 lines — in the "warning" zone (401-600) but acceptable for a self-contained module
- `mcp_server.py`: 401 lines — at the boundary; single responsibility maintained

---

## Human Verification Required

### 1. Live environment detection on a real machine

**Test:** Run `waf_check_env(deploy_target="vercel")` via Claude Desktop or `claude mcp` after installing the server.
**Expected:** Returns markdown table showing actual tool presence/absence for the host machine (not mocked).
**Why human:** Tests use mocked subprocess; live behavior depends on actual installed tools.

### 2. Actual `install_tool('vercel')` on macOS

**Test:** Run `waf_check_env(execute_install=True, tool_to_install="vercel")` on a machine where Vercel CLI is absent.
**Expected:** `npm install -g vercel` runs, Vercel CLI is installed, re-run of `waf_check_env` shows status='present'.
**Why human:** Cannot verify subprocess side effects programmatically in this environment.

### 3. Distribution install via uvx

**Test:** On a clean Python environment: `uvx web-app-factory` (or `claude mcp add web-app-factory -- uvx web-app-factory`).
**Expected:** Server starts, tools are callable via MCP protocol, `waf_check_env` returns a report.
**Why human:** PyPI publishing and clean-environment install require manual verification steps (documented in 12-VALIDATION.md per Plan 02).

---

## Gaps Summary

No gaps. All must-haves are verified. The phase goal — "Environment detection, install guidance, and distribution packaging" — is achieved:

- **Detection:** `_env_checker.py` implements structured ToolStatus detection for node, npm, python, vercel, and gcloud across multiple deploy targets.
- **Install guidance:** Platform-aware (macOS/Linux) install commands are provided for all tools; allowlist-validated subprocess installs are available for auto-installable tools.
- **Distribution packaging:** `uv build` produces a wheel and sdist; the entry point resolves cleanly; all 36 Phase 12 tests pass.

---

*Verified: 2026-03-24T06:30:00Z*
*Verifier: Claude (gsd-verifier)*
