---
phase: 19-supabase-auth-scaffolding
plan: "02"
subsystem: auth
tags: [supabase, oauth, google, apple, agent-prompts, env-checker, provisioner]

# Dependency graph
requires:
  - phase: 17-supabase-provisioning
    provides: SupabaseProvisioner class and _env_checker patterns used for extension
  - phase: 18-backend-api-generation
    provides: agents/definitions.py BUILD_AGENT prompt extended with auth section
provides:
  - SupabaseProvisioner.configure_oauth_providers() — PATCHes Management API for Google/Apple OAuth
  - _check_oauth_credentials() advisory env checker for 4 OAuth env vars
  - SPEC_AGENT prompt: prefers Supabase Auth over NextAuth.js/Clerk when Supabase DB is in use
  - BUILD_AGENT prompt: getUser() over getSession(), auth-ui-react warning, signInWithOAuth pattern
affects: [phase-19-03, phase-20-ios-backend, any phase using SupabaseProvisioner or agents/definitions.py]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "configure_oauth_providers skips PATCH when all args None — no unnecessary API calls"
    - "OAuth advisory vs blocking: OAuth credentials are optional (can add later), never blocking"
    - "Agent prompts: conditional guidance tied to environment signal (NEXT_PUBLIC_SUPABASE_URL present)"

key-files:
  created:
    - tests/test_agent_definitions.py
  modified:
    - web_app_factory/_supabase_provisioner.py
    - web_app_factory/_env_checker.py
    - agents/definitions.py
    - tests/test_supabase_provisioner.py
    - tests/test_env_checker.py

key-decisions:
  - "OAuth advisories are not blocking — users can configure Google/Apple OAuth after initial deployment"
  - "configure_oauth_providers skips API call entirely when all params None — no empty PATCH"
  - "Credential VALUES never logged — only key names logged (security contract from 10-security-core.md)"
  - "SPEC_AGENT: Supabase Auth preference expressed as conditional on Supabase DB being in use"
  - "BUILD_AGENT: @supabase/auth-ui-react explicitly warned as archived Feb 2024 — prevents agents from using it"
  - "getSession() in server code explicitly banned in BUILD_AGENT — NEVER pattern with reason"

patterns-established:
  - "Pattern: advisory env check — status=missing but not blocking; note contains 'Advisory:' prefix"
  - "Pattern: OAuth provider configuration via Management API PATCH /v1/projects/{ref}/config/auth"
  - "Pattern: agent prompt auth section tied to env var signal (NEXT_PUBLIC_SUPABASE_URL)"

requirements-completed: [AUTH-05, AUTH-06]

# Metrics
duration: 3min
completed: 2026-03-25
---

# Phase 19 Plan 02: Supabase Auth Scaffolding — OAuth Provider Configuration Summary

**Supabase Management API OAuth auto-configuration via configure_oauth_providers(), Google/Apple advisory env checks, and Supabase Auth preference guidance injected into SPEC_AGENT and BUILD_AGENT prompts**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-25T02:41:58Z
- **Completed:** 2026-03-25T02:45:10Z
- **Tasks:** 2
- **Files modified:** 5 (3 source + 2 test, 1 new test file)

## Accomplishments

- Added `SupabaseProvisioner.configure_oauth_providers()` — async method that PATCHes `/v1/projects/{ref}/config/auth` with external Google/Apple OAuth fields; skips API call entirely when all params are None; credential values never logged
- Added `_check_oauth_credentials()` to env checker — advisory checks for 4 OAuth env vars (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, APPLE_CLIENT_ID, APPLE_CLIENT_SECRET) appended to `check_env('supabase')` output; status is "missing" but advisory (not blocking)
- Updated SPEC_AGENT prompt with Supabase Auth preference over NextAuth.js/Clerk when Supabase DB is in use
- Updated BUILD_AGENT prompt with dedicated auth section: getUser() over getSession(), @supabase/auth-ui-react ban (archived Feb 2024), signInWithOAuth pattern, protected route pattern, signOut with global scope

## Task Commits

Each task was committed atomically with TDD (RED then GREEN):

1. **Task 1 RED: configure_oauth_providers + OAuth env check failing tests** — `5480aa7` (test)
2. **Task 1 GREEN: configure_oauth_providers + _check_oauth_credentials implementation** — `19ede30` (feat)
3. **Task 2 RED: agent definitions failing tests** — `c9deea4` (test)
4. **Task 2 GREEN: SPEC_AGENT + BUILD_AGENT auth prompt updates** — `d3c9fc2` (feat)

## Files Created/Modified

- `/Users/masa/Development/web-app-factory/web_app_factory/_supabase_provisioner.py` — Added `configure_oauth_providers()` async method (259 → 309 lines)
- `/Users/masa/Development/web-app-factory/web_app_factory/_env_checker.py` — Added `_check_oauth_credentials()` and hooked into `check_env('supabase')` (539 → 616 lines, warning range but acceptable)
- `/Users/masa/Development/web-app-factory/agents/definitions.py` — Updated SPEC_AGENT stack context auth line; added BUILD_AGENT authentication section (404 → 418 lines)
- `/Users/masa/Development/web-app-factory/tests/test_supabase_provisioner.py` — Added `TestConfigureOAuthProviders` (6 tests)
- `/Users/masa/Development/web-app-factory/tests/test_env_checker.py` — Added `TestOAuthCredentials` (5 tests)
- `/Users/masa/Development/web-app-factory/tests/test_agent_definitions.py` — Created new file with `TestSpecAgentAuthPrompt` (3 tests) and `TestBuildAgentAuthPrompt` (7 tests)

## Decisions Made

- OAuth advisories not blocking: Google/Apple OAuth is optional. Users can deploy Supabase apps without OAuth configured and add it later. Blocking on OAuth credentials would prevent basic deployments unnecessarily.
- configure_oauth_providers skips PATCH entirely when all params None: avoids making an empty PATCH that could reset auth configuration.
- _env_checker.py at 616 lines (warning range): plan analysis acknowledged this range as acceptable given the function responsibility scope; split would add more complexity than benefit.
- BUILD_AGENT auth section tied to NEXT_PUBLIC_SUPABASE_URL: makes the guidance conditional, so it only applies when Supabase is actually in use, rather than being guidance for all generated apps.

## Deviations from Plan

None — plan executed exactly as written. _env_checker.py reached 616 lines vs ~589 estimated, but this is within the "warning range" that the plan explicitly noted as acceptable.

## Issues Encountered

None.

## Next Phase Readiness

- configure_oauth_providers is ready to be called from phase_3_executor.py when Google/Apple OAuth credentials are present in banto/env
- OAuth advisory checks will appear in waf_check_env output for supabase target, guiding users to configure OAuth
- Agent prompts now steer spec/build agents toward Supabase Auth patterns, preventing NextAuth.js/Clerk generation on Supabase stack
- Phase 19-03 (Auth scaffolding — scaffold files and route handlers) can proceed

---
*Phase: 19-supabase-auth-scaffolding*
*Completed: 2026-03-25*
