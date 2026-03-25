---
phase: 19-supabase-auth-scaffolding
plan: "01"
subsystem: auth
tags: [supabase, nextjs, middleware, oauth, google-auth, apple-signin, typescript, templates, python]

# Dependency graph
requires:
  - phase: 17-supabase-provisioning
    provides: "@supabase/ssr createBrowserClient/createServerClient templates and TEMPLATE_DIR pattern"
  - phase: 18-backend-api-generation
    provides: "backend templates directory structure and template renderer pattern"
provides:
  - "auth-middleware.ts.tmpl: Next.js middleware with getUser() session refresh and default-protect redirect"
  - "auth/login-page.tsx.tmpl: OAuth sign-in page with Google + Apple buttons using signInWithOAuth()"
  - "auth/signup-page.tsx.tmpl: OAuth-only create-account page"
  - "auth/signout-page.tsx.tmpl: Server action with signOut({ scope: 'global' }) + redirect('/')"
  - "auth/callback-route.ts.tmpl: PKCE code exchange with exchangeCodeForSession + open-redirect prevention"
  - "auth/AUTH_SETUP.md.tmpl: Step-by-step README for Google Cloud Console, Apple Developer Portal, .p8 rotation, redirect URL allowlist"
  - "_supabase_auth_renderer.py: render_auth_templates() copies 6 templates into generated app"
affects:
  - "19-02 (OAuth provisioner + agent prompts depend on these templates existing)"
  - "phase_3_executor (will call render_auth_templates after Supabase provisioning)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Auth template renderer pattern: TEMPLATE_DIR-based module mapping 6 templates to output paths"
    - "getUser() over getSession() in all server-context code (middleware, callback route)"
    - "anon key in middleware, service_role only in server components doing data access"
    - "returnTo parameter roundtrip: middleware redirect -> login page -> callback route"
    - "Open redirect prevention: validate returnTo.startsWith('/') in callback route"
    - "Global scope signout: signOut({ scope: 'global' }) signs out all devices"

key-files:
  created:
    - web_app_factory/templates/auth-middleware.ts.tmpl
    - web_app_factory/templates/auth/login-page.tsx.tmpl
    - web_app_factory/templates/auth/signup-page.tsx.tmpl
    - web_app_factory/templates/auth/signout-page.tsx.tmpl
    - web_app_factory/templates/auth/callback-route.ts.tmpl
    - web_app_factory/templates/auth/AUTH_SETUP.md.tmpl
    - web_app_factory/_supabase_auth_renderer.py
    - tests/test_auth_templates.py
    - tests/test_supabase_auth_renderer.py
  modified: []

key-decisions:
  - "Custom OAuth buttons (not @supabase/auth-ui-react): auth-ui-react is archived since Feb 2024 with no passkey support"
  - "getUser() not getSession() in all server context: getUser() validates with Supabase server, detects revoked sessions"
  - "Anon key in middleware not service_role: middleware only refreshes sessions, never accesses privileged data (SECG-01)"
  - "returnTo validation: callback route validates returnTo.startsWith('/') to prevent open redirect attacks"
  - "AUTH_SETUP.md at project root (not src/): developer-facing README, not a source file"
  - "Separate renderer module (not extending _supabase_template_renderer.py): keeps each module focused on one set of templates"

patterns-established:
  - "Auth template TDD: tests validate required patterns (getUser, signInWithOAuth) and forbidden patterns (getSession, service_role, auth-ui-react)"
  - "Template renderer atomic validation: all templates checked for existence before any output is written"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05]

# Metrics
duration: 4min
completed: 2026-03-25
---

# Phase 19 Plan 01: Supabase Auth Scaffolding Templates Summary

**Cookie-based auth scaffolding with custom Google/Apple OAuth buttons, PKCE callback, global signout, and step-by-step README for manual Google Cloud Console and Apple Developer Portal setup**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-25T02:35:07Z
- **Completed:** 2026-03-25T02:39:00Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Created 6 auth template files following 2026-03 Supabase SSR best practices: `getUser()` in all server contexts, anon key in middleware, custom OAuth buttons (not archived auth-ui-react), PKCE callback with open-redirect prevention, global scope signout
- Created `_supabase_auth_renderer.py` module following the established `_supabase_template_renderer.py` pattern: 6-template mapping, atomic pre-validation, mkdir-p directory creation, returns absolute paths
- Created 64 tests (47 template content tests + 17 renderer behavior tests) with full RED → GREEN TDD cycle

## Task Commits

Each task was committed atomically:

1. **Task 1: Auth TypeScript templates and AUTH_SETUP.md README** - `f9536e4` (feat)
2. **Task 2: Auth template renderer module** - `5a2cf9d` (feat)

## Files Created/Modified

- `web_app_factory/templates/auth-middleware.ts.tmpl` - Next.js middleware: createServerClient + getUser() + default-protect redirect with returnTo
- `web_app_factory/templates/auth/login-page.tsx.tmpl` - 'use client' OAuth buttons: Google + Apple via signInWithOAuth()
- `web_app_factory/templates/auth/signup-page.tsx.tmpl` - OAuth-only create-account page (same flow as login)
- `web_app_factory/templates/auth/signout-page.tsx.tmpl` - Server action: signOut({ scope: 'global' }) + redirect('/')
- `web_app_factory/templates/auth/callback-route.ts.tmpl` - PKCE handler: exchangeCodeForSession + returnTo open-redirect prevention
- `web_app_factory/templates/auth/AUTH_SETUP.md.tmpl` - Step-by-step README: Google Cloud Console, Apple Developer Portal, .p8 6-month rotation, Supabase redirect URL allowlist
- `web_app_factory/_supabase_auth_renderer.py` - render_auth_templates(): renders 6 templates into correct generated app paths
- `tests/test_auth_templates.py` - 47 tests: required patterns + forbidden patterns (getSession, service_role in middleware, auth-ui-react)
- `tests/test_supabase_auth_renderer.py` - 17 tests: output paths, return value, content integrity, directory creation, error handling

## Decisions Made

- **Custom OAuth buttons over auth-ui-react**: `@supabase/auth-ui-react` is archived (Feb 2024) and has no passkey support. Custom `signInWithOAuth()` buttons are the only maintained path.
- **getUser() exclusively in server context**: `getSession()` is not guaranteed to validate against Supabase server — it reads cookies without revalidation. `getUser()` detects revoked sessions correctly.
- **Anon key in middleware**: Middleware only refreshes sessions; it never accesses privileged data. Using service_role key in middleware would risk exposing it in Edge Runtime and violates SECG-01.
- **returnTo open-redirect prevention**: Callback route validates `returnTo.startsWith('/')` before redirecting, preventing external URL injection.
- **AUTH_SETUP.md at project root**: It's a developer-facing README, not source code. Placing it at `output_dir/AUTH_SETUP.md` keeps it at the project root alongside package.json.
- **Separate renderer module**: `_supabase_auth_renderer.py` is a separate module from `_supabase_template_renderer.py` — each stays focused on its own template set (browser/server clients vs auth pages).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed false-positive test assertions for middleware template**
- **Found during:** Task 1 TDD GREEN phase
- **Issue:** Two middleware tests failed because the comment in the template contained "getSession" and "service_role" as warning strings (e.g., `// NOT service_role`), which caused the "does not contain" checks to fail
- **Fix:** Rewrote comment text to avoid mentioning the forbidden strings while preserving the intent
- **Files modified:** `web_app_factory/templates/auth-middleware.ts.tmpl`
- **Verification:** Both tests now pass; template still clearly communicates the security constraint via different wording
- **Committed in:** `f9536e4` (part of Task 1 feat commit)

**2. [Rule 1 - Bug] Fixed inverted test assertion in login template SSR import test**
- **Found during:** Task 1 TDD GREEN phase
- **Issue:** The test `test_login_template_imports_from_supabase_ssr` had inverted logic: `assert "@supabase/ssr" not in content or "supabase/browser" in content` — this failed when the template correctly imported `createBrowserClient from '@supabase/ssr'` directly
- **Fix:** Rewrote test to assert `auth-helpers-nextjs` is absent (the real forbidden import) and verify at least one of the valid import patterns is present
- **Files modified:** `tests/test_auth_templates.py`
- **Verification:** Test now correctly validates that the deprecated auth-helpers package is not used
- **Committed in:** `f9536e4` (part of Task 1 feat commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — Bug fixes in tests/templates)
**Impact on plan:** Both fixes were necessary for test correctness. No scope creep.

## Issues Encountered

None — plan executed with straightforward TDD cycles after fixing the two minor comment/assertion issues noted above.

## User Setup Required

None — templates and renderer are code artifacts. External service configuration (Google Cloud Console, Apple Developer Portal) is documented in `AUTH_SETUP.md.tmpl` which gets rendered into each generated app.

## Next Phase Readiness

- Auth template files are ready for use by the phase executor (Phase 19 Plans 02+)
- `render_auth_templates()` can be called from `phase_3_executor.py` after Supabase provisioning
- AUTH_SETUP.md covers the manual OAuth setup steps that cannot be automated
- No blockers for Phase 19 Plan 02 (OAuth provisioner + agent prompt updates)

## Self-Check: PASSED

All created files exist on disk. Both task commits verified in git log.

---
*Phase: 19-supabase-auth-scaffolding*
*Completed: 2026-03-25*
