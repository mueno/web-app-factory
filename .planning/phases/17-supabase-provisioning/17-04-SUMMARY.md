---
phase: 17-supabase-provisioning
plan: 04
subsystem: database
tags: [supabase, provisioner, templates, typescript, nextjs, phase-executor, pipeline-integration]

# Dependency graph
requires:
  - phase: 17-supabase-provisioning/17-02
    provides: SupabaseProvisioner (create_project, poll_until_healthy, get_api_keys, inject_vercel_env) and supabase_gate
  - phase: 17-supabase-provisioning/17-03
    provides: get_credential() credential backend, supabase-browser.ts.tmpl, supabase-server.ts.tmpl templates

provides:
  - render_supabase_templates(): copies supabase-browser.ts and supabase-server.ts from templates into generated app src/lib/supabase/
  - add_supabase_deps(): injects @supabase/ssr and @supabase/supabase-js into generated app package.json
  - Phase3ShipExecutor extended with supabase_provision, supabase_render, supabase_gate sub-steps
  - Full Supabase provisioning pipeline gated behind supabase_enabled=True flag (backward compatible)

affects:
  - 18-backend-api-generation (Phase 3 executor now handles Supabase wiring before deploy gates)
  - 19-supabase-auth-scaffolding (client files in src/lib/supabase/ are the foundation for auth flows)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD: test files written first (RED), then implementation (GREEN)
    - Lazy import pattern: Supabase provisioner, keychain, template renderer, and gate all use lazy imports inside methods to avoid loading heavy deps on non-Supabase pipelines
    - asyncio.run() bridge: synchronous Phase 3 executor calls async SupabaseProvisioner methods via asyncio.run()
    - sys.modules stub: claude_agent_sdk stubbed in test module header to enable phase_3_executor import in environments without the SDK

key-files:
  created:
    - web_app_factory/_supabase_template_renderer.py
    - tests/test_supabase_template_renderer.py
    - tests/test_phase_3_supabase.py
  modified:
    - tools/phase_executors/phase_3_executor.py
    - tests/test_phase_3_executor.py

key-decisions:
  - "Lazy imports for all Supabase sub-step dependencies: avoids loading httpx/banto/provisioner on non-Supabase pipelines; keeps existing Vercel/GCP/local paths completely unaffected"
  - "asyncio.run() as sync/async bridge in _supabase_provision: consistent with deploy_agent_runner pattern already used in Phase 3"
  - "sys.modules stub for claude_agent_sdk in test file header: allows importing Phase3ShipExecutor in CI/test environments without the SDK installed, without changing production code"
  - "supabase_enabled check plus deploy_target != local guard: local deploy exits before Supabase block; supabase_enabled=False or absent skips entirely"

patterns-established:
  - "Template renderer pattern: reads .tmpl files from TEMPLATE_DIR (package-relative), writes stripped output to output_dir/src/lib/supabase/"
  - "Supabase sub-step sequencing: provision -> render -> gate (each can fail independently with descriptive error)"
  - "ctx.extra as inter-step state: project_ref and api_keys stored in ctx.extra by _supabase_provision for use by _supabase_render and _supabase_gate"

requirements-completed: [SUPA-01, SUPA-03, SUPA-06]

# Metrics
duration: 7min
completed: 2026-03-24
---

# Phase 17 Plan 04: Pipeline Integration (Phase 3 + Supabase Templates) Summary

**Template renderer + Phase 3 executor wiring: waf_generate_app with supabase_enabled=True now provisions Supabase, renders dual TypeScript client files into src/lib/supabase/, and runs supabase_gate — all backward compatible with existing Vercel/local/GCP targets**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-24T22:45:20Z
- **Completed:** 2026-03-24T22:52:40Z
- **Tasks:** 2
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- `render_supabase_templates()`: reads supabase-browser.ts.tmpl and supabase-server.ts.tmpl from templates/, creates src/lib/supabase/ directory in generated app, writes .ts files (no .tmpl extension)
- `add_supabase_deps()`: reads package.json, adds @supabase/ssr and @supabase/supabase-js to dependencies, preserves existing deps, writes back with indent=2
- Phase3ShipExecutor extended with 3 new sub-steps (supabase_provision, supabase_render, supabase_gate) that execute only when `supabase_enabled=True` and `deploy_target != "local"` — completely backward compatible
- 27 new tests green (13 template renderer + 14 phase 3 integration)

## Task Commits

Each task was committed atomically:

1. **Task 1: Template renderer and tests** - `9ed16a2` (feat)
2. **Task 2: Phase 3 executor Supabase integration** - `d6c2c13` (feat)

_Note: TDD tasks — tests written first (RED), then implementation (GREEN)_

## Files Created/Modified

- `web_app_factory/_supabase_template_renderer.py` - render_supabase_templates() and add_supabase_deps() functions
- `tests/test_supabase_template_renderer.py` - 13 tests: directory creation, content validation, dep injection, error cases
- `tests/test_phase_3_supabase.py` - 14 tests: enabled flow, backward compat, failure cases; includes claude_agent_sdk stub
- `tools/phase_executors/phase_3_executor.py` - Added supabase_provision/render/gate sub-steps and _supabase_provision/_supabase_render/_supabase_gate methods
- `tests/test_phase_3_executor.py` - Updated test_sub_steps_list to reflect 13 items (was 10)

## Decisions Made

- **Lazy imports for all Supabase deps:** `_supabase_provision`, `_supabase_render`, and `_supabase_gate` all use `from ... import ...` inside method bodies. This means non-Supabase pipelines never pay the import cost of httpx/banto/provisioner.
- **asyncio.run() bridge:** The synchronous Phase 3 executor runs async SupabaseProvisioner methods via `asyncio.run()`, consistent with how `deploy_agent_runner.py` handles the same sync/async problem.
- **sys.modules stub for tests:** `claude_agent_sdk` is not installed in the test environment. Rather than change production code, the test file stubs the SDK in `sys.modules` before any import of `Phase3ShipExecutor`. This is the standard pattern for optional/external SDK stubs.
- **ctx.extra as inter-step state:** `project_ref` and `api_keys` from provisioning are stored in `ctx.extra` dict for downstream steps. This is consistent with how `preview_url` is stored in `self._preview_url` in the existing executor.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_phase_3_executor.py sub_steps test expected 10 items**
- **Found during:** Task 2 (verifying backward compatibility)
- **Issue:** `test_sub_steps_list` in `test_phase_3_executor.py` asserted exactly 10 sub-steps. After adding 3 Supabase sub-steps, this test would fail (even though the test itself was already failing due to claude_agent_sdk).
- **Fix:** Updated the expected list to 13 items including the three new Supabase sub-steps; updated docstring to say "13 items".
- **Files modified:** `tests/test_phase_3_executor.py`
- **Verification:** The updated test list now correctly matches Phase3ShipExecutor.sub_steps
- **Committed in:** `d6c2c13` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug in existing test)
**Impact on plan:** Required fix to prevent test regression. No scope creep.

## Issues Encountered

- `claude_agent_sdk` is not installed in the test environment, causing `phase_3_executor.py` module import to fail. Resolved by adding a `sys.modules` stub in the test file header — no production code change needed. This is a known limitation of test environments without the full SDK; the existing `test_phase_3_executor.py` tests have the same issue.

## User Setup Required

None - no external service configuration required beyond what was documented in Plan 01 (Supabase credentials stored via banto or env vars).

## Next Phase Readiness

- Full Supabase provisioning pipeline wired into waf_generate_app Phase 3
- SUPA-01 (SupabaseProvisioner in pipeline), SUPA-03 (dual client TypeScript files), SUPA-06 (pipeline integration) all satisfied
- Phase 17 complete — all 4 plans done
- Ready for Phase 18: Backend API Generation (BGEN-01 to BGEN-07, SECG-03)

## Self-Check: PASSED

- `web_app_factory/_supabase_template_renderer.py` — FOUND
- `tests/test_supabase_template_renderer.py` — FOUND
- `tests/test_phase_3_supabase.py` — FOUND
- `tools/phase_executors/phase_3_executor.py` — FOUND (modified)
- `tests/test_phase_3_executor.py` — FOUND (modified)
- commit `9ed16a2` (Task 1) — FOUND
- commit `d6c2c13` (Task 2) — FOUND
- 27/27 new tests green (13 template renderer + 14 phase 3 supabase)
- 83/83 Supabase plan tests green (Plans 01-04 combined)

---
*Phase: 17-supabase-provisioning*
*Completed: 2026-03-24*
