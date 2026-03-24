---
phase: 17-supabase-provisioning
plan: "02"
subsystem: security
tags: [supabase, typescript, static-analysis, security-gate, templates, next-js]

requires:
  - phase: 16-mcp-infrastructure-hardening
    provides: gate pattern (static_analysis_gate.py) and GateResult dataclass

provides:
  - "supabase-browser.ts.tmpl: browser-side Supabase client using createBrowserClient + NEXT_PUBLIC_SUPABASE_ANON_KEY"
  - "supabase-server.ts.tmpl: server-side Supabase client using createServerClient + SUPABASE_SERVICE_ROLE_KEY (no NEXT_PUBLIC_)"
  - "SECG-01 gate: blocks NEXT_PUBLIC_*SERVICE*ROLE* and NEXT_PUBLIC_*SVC*ROLE* patterns"
  - "GATE-06 allowlist: NEXT_PUBLIC_SUPABASE_ANON_KEY no longer incorrectly blocked"

affects:
  - phase: 17 plan 03 (supabase provisioner uses these templates)
  - phase: 18 (backend API generation uses same gate)
  - phase: 19 (auth scaffolding generates Supabase client files)

tech-stack:
  added: ["@supabase/ssr (template dependency for generated apps)"]
  patterns:
    - "Dual Supabase client pattern: browser (anon key) vs server (service_role, server-only)"
    - "TDD: RED (failing tests committed) then GREEN (implementation)"
    - "Gate defense-in-depth: SECG-01 dedicated regex complements existing GATE-06"

key-files:
  created:
    - "web_app_factory/templates/supabase-browser.ts.tmpl"
    - "web_app_factory/templates/supabase-server.ts.tmpl"
    - "tests/test_supabase_templates.py"
  modified:
    - "tools/gates/static_analysis_gate.py"
    - "tests/test_static_analysis_gate.py"

key-decisions:
  - "NEXT_PUBLIC_SUPABASE_ANON_KEY allowlisted in GATE-06: the anon key is intentionally public (Supabase's design), blocking it was a false positive in the existing regex"
  - "SECG-01 regex uses two branches: SERVICE*ROLE and SVC*ROLE to catch common abbreviation variants"
  - "Server template uses async createClient() with cookie handling (Next.js 15 async cookies() API)"

patterns-established:
  - "Template naming: supabase-browser.ts.tmpl / supabase-server.ts.tmpl — browser vs server suffix signals key type"
  - "SECG-01 comment in server template documents the NEXT_PUBLIC_ restriction for future developers"
  - "Gate allowlist pattern: _NEXT_PUBLIC_ANON_KEY_ALLOWLIST_RE for known-safe NEXT_PUBLIC_ variables"

requirements-completed: [SUPA-06, SECG-01]

duration: 15min
completed: "2026-03-24"
---

# Phase 17 Plan 02: Supabase Client Templates and SECG-01 Gate Summary

**Dual Supabase TypeScript client templates (browser anon-key / server service_role) with SECG-01 gate blocking NEXT_PUBLIC_ service_role exposure**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-24T22:17:00Z
- **Completed:** 2026-03-24T22:32:08Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 5 (2 created templates, 1 extended gate, 2 test files)

## Accomplishments

- Created `supabase-browser.ts.tmpl` with `createBrowserClient` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` — safe for client bundle
- Created `supabase-server.ts.tmpl` with `createServerClient`, `SUPABASE_SERVICE_ROLE_KEY` (no `NEXT_PUBLIC_` prefix), and async cookie handling
- Extended `static_analysis_gate.py` with SECG-01: `_check_service_role_exposure()` blocks `NEXT_PUBLIC_*SERVICE*ROLE*` and `NEXT_PUBLIC_*SVC*ROLE*` variants
- Fixed pre-existing bug: `NEXT_PUBLIC_SUPABASE_ANON_KEY` was incorrectly blocked by GATE-06 (allowlisted it)
- 76 total tests pass (25 template + 51 gate including 11 new SECG-01 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Supabase template tests** - `d55f5d0` (test)
2. **Task 1 GREEN: Dual Supabase client templates** - `a7d9619` (feat)
3. **Task 2 RED: SECG-01 gate tests** - `9ea0b57` (test)
4. **Task 2 GREEN: SECG-01 gate implementation** - `c9c7f14` (feat)

_Note: TDD tasks have separate test (RED) and implementation (GREEN) commits_

## Files Created/Modified

- `web_app_factory/templates/supabase-browser.ts.tmpl` — Browser Supabase client (anon key, createBrowserClient)
- `web_app_factory/templates/supabase-server.ts.tmpl` — Server Supabase client (service_role, createServerClient, async cookies)
- `tests/test_supabase_templates.py` — 25 tests verifying template content and security constraints
- `tools/gates/static_analysis_gate.py` — Added `_NEXT_PUBLIC_SERVICE_ROLE_RE`, `_check_service_role_exposure()`, GATE-06 anon key allowlist
- `tests/test_static_analysis_gate.py` — 11 new SECG-01 tests (total: 51)

## Decisions Made

- **Anon key allowlist:** `NEXT_PUBLIC_SUPABASE_ANON_KEY` is allowlisted in GATE-06. Supabase's architecture intentionally exposes the anon key to the browser — it's how Row Level Security enforces per-user access at the database layer. Blocking it would create false positives in every generated app using Supabase.
- **SVC variant in SECG-01:** The regex uses two branches (`SERVICE*ROLE` and `SVC*ROLE`) to catch the common `SVC` abbreviation. Without this, `NEXT_PUBLIC_SVC_ROLE` would bypass the check.
- **Async createClient in server template:** Next.js 15 requires `await cookies()` — the server template uses `async function createClient()` to match the current API.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed GATE-06 false positive: NEXT_PUBLIC_SUPABASE_ANON_KEY incorrectly blocked**
- **Found during:** Task 2 (writing SECG-01 tests for pass/block behavior)
- **Issue:** The plan specifies "Gate PASSES when file contains NEXT_PUBLIC_SUPABASE_ANON_KEY (anon key is safe)". Testing revealed the existing `_NEXT_PUBLIC_SECRET_RE` blocks all `NEXT_PUBLIC_*KEY` patterns including `ANON_KEY`. This is a false positive — the anon key is Supabase's designed public key for browser use.
- **Fix:** Added `_NEXT_PUBLIC_ANON_KEY_ALLOWLIST_RE` and skip logic in `_check_next_public_secrets()` to allowlist `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- **Files modified:** `tools/gates/static_analysis_gate.py`
- **Verification:** `test_passes_next_public_supabase_anon_key` passes; existing GATE-06 tests unaffected
- **Committed in:** `c9c7f14` (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Auto-fix was necessary for correctness — plan explicitly required anon key to pass. No scope creep.

## Issues Encountered

- `NEXT_PUBLIC_SVC_ROLE` test initially failed because the SECG-01 regex only matched `SERVICE` not the abbreviation `SVC`. Fixed by adding a second regex branch. (This was part of the implementation, not a separate issue.)

## User Setup Required

None - no external service configuration required for this plan. Templates are static files; gate extension is backend Python.

## Next Phase Readiness

- Templates ready for use by `SupabaseProvisioner` (Plan 03) when generating app files
- SECG-01 gate active — any future generated code that accidentally exposes service_role via NEXT_PUBLIC_ will be blocked
- Plan 03 can import templates from `web_app_factory/templates/` using Path-based loading

---
*Phase: 17-supabase-provisioning*
*Completed: 2026-03-24*

## Self-Check: PASSED

- [x] `web_app_factory/templates/supabase-browser.ts.tmpl` — FOUND
- [x] `web_app_factory/templates/supabase-server.ts.tmpl` — FOUND
- [x] `tests/test_supabase_templates.py` — FOUND
- [x] `17-02-SUMMARY.md` — FOUND
- [x] Commit `d55f5d0` (test: failing template tests) — FOUND
- [x] Commit `a7d9619` (feat: dual templates) — FOUND
- [x] Commit `9ea0b57` (test: failing SECG-01 tests) — FOUND
- [x] Commit `c9c7f14` (feat: SECG-01 gate) — FOUND
- [x] 76 tests pass (test_supabase_templates.py + test_static_analysis_gate.py)
