---
phase: 19-supabase-auth-scaffolding
verified: 2026-03-25T03:07:17Z
status: passed
score: 15/15 must-haves verified
re_verification: false
---

# Phase 19: Supabase Auth Scaffolding Verification Report

**Phase Goal:** Generated apps have complete passkey + Google/Apple OAuth authentication with cookie-based session management, protected routes, middleware session refresh, and auth page generation.
**Verified:** 2026-03-25T03:07:17Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                         | Status     | Evidence                                                                                               |
|----|-----------------------------------------------------------------------------------------------|------------|--------------------------------------------------------------------------------------------------------|
| 1  | Auth template files exist and contain correct Supabase SSR patterns                           | VERIFIED   | All 10 template files present under `web_app_factory/templates/auth/` + `auth-middleware.ts.tmpl`     |
| 2  | Middleware template uses `getUser()` with anon key (NOT getSession, NOT service_role)         | VERIFIED   | `getUser` at line 34, `NEXT_PUBLIC_SUPABASE_ANON_KEY` at line 9; zero forbidden pattern matches       |
| 3  | Login page uses `signInWithOAuth` for Google and Apple with returnTo support                  | VERIFIED   | `signInWithOAuth` + `provider: 'google'` + `provider: 'apple'` + `returnTo` all present              |
| 4  | Callback route exchanges PKCE code for session via `exchangeCodeForSession`                   | VERIFIED   | `exchangeCodeForSession` at line 32 + `returnTo.startsWith('/')` open-redirect guard at line 11       |
| 5  | Signout page uses `signOut({ scope: 'global' })` and redirects to `/`                        | VERIFIED   | `signOut({ scope: 'global' })` at line 25, `redirect('/')` at line 26                                 |
| 6  | Auth renderer copies templates into generated app directory structure                         | VERIFIED   | `render_auth_templates()` maps 10 templates to correct output paths, `TEMPLATE_DIR` at line 34        |
| 7  | `AUTH_SETUP.md.tmpl` covers Google Cloud Console, Apple Developer Portal, .p8 rotation, redirect URL allowlist | VERIFIED | All 4 sections present: Google Cloud Console, Apple Developer Portal, .p8 6-month rotation warning, `localhost:3000` allowlist |
| 8  | `SupabaseProvisioner` has `configure_oauth_providers` that PATCHes Supabase Management API   | VERIFIED   | Method at line 261; builds `external_google/apple_enabled/client_id/secret` payload; PATCHes `/config/auth` |
| 9  | `waf_check_env` reports missing Google/Apple OAuth credentials as advisories (not blocking)   | VERIFIED   | `_check_oauth_credentials()` at line 276, returns advisory status; wired into `check_env('supabase')` at line 454 |
| 10 | SPEC_AGENT prompt tells spec agent to prefer Supabase Auth when Supabase DB is in use        | VERIFIED   | Lines 36-39 of `agents/definitions.py` contain explicit Supabase Auth preference over NextAuth.js/Clerk |
| 11 | BUILD_AGENT prompt warns against `getSession()` and `auth-ui-react`, recommends `getUser()` and `signInWithOAuth` | VERIFIED | Lines 339-342: NEVER `@supabase/auth-ui-react`, NEVER `getSession()`, use `getUser()` + `signInWithOAuth` |
| 12 | Passkey WebAuthn templates exist with correct `@simplewebauthn` patterns                      | VERIFIED   | 4 passkey templates present; `generateRegistrationOptions`, `generateAuthenticationOptions`, `startRegistration`, `startAuthentication` all verified |
| 13 | Phase 2b generates auth pages and passkey deps when Supabase is enabled                       | VERIFIED   | `generate_auth_pages` at index 4 in `sub_steps`; detects Supabase via `NEXT_PUBLIC_SUPABASE_URL` in `.env.local`; calls `render_auth_templates` + `add_passkey_deps` |
| 14 | Phase 3 calls `configure_oauth_providers` after Supabase provisioning when OAuth creds present | VERIFIED  | `supabase_oauth_config` at position 2 in sub_steps list (after `supabase_provision`, before `supabase_render`); wired at line 243 |
| 15 | `phase_3_executor.py` line count reduced below 800 after Supabase step extraction            | VERIFIED   | `phase_3_executor.py` is 705 lines; `_phase_3_supabase_steps.py` is 265 lines (normal range)          |

**Score:** 15/15 truths verified

---

### Required Artifacts

| Artifact                                                              | Expected                                               | Status     | Details                                      |
|-----------------------------------------------------------------------|--------------------------------------------------------|------------|----------------------------------------------|
| `web_app_factory/templates/auth-middleware.ts.tmpl`                  | Next.js middleware with session refresh + redirect      | VERIFIED   | 44 lines; `createServerClient`, `getUser`    |
| `web_app_factory/templates/auth/login-page.tsx.tmpl`                 | OAuth sign-in with Google + Apple buttons               | VERIFIED   | `signInWithOAuth` + `PasskeyButtons` import  |
| `web_app_factory/templates/auth/signup-page.tsx.tmpl`                | Create-account page                                     | VERIFIED   | Mirrors login with "Create an account" heading + `PasskeyButtons` |
| `web_app_factory/templates/auth/signout-page.tsx.tmpl`               | Global signout server action                            | VERIFIED   | `signOut({ scope: 'global' })` + `redirect('/')` |
| `web_app_factory/templates/auth/callback-route.ts.tmpl`              | PKCE code exchange handler                              | VERIFIED   | `exchangeCodeForSession` + open-redirect prevention |
| `web_app_factory/templates/auth/AUTH_SETUP.md.tmpl`                  | README for manual OAuth setup steps                     | VERIFIED   | Google Cloud Console, Apple Dev Portal, .p8 rotation, redirect allowlist |
| `web_app_factory/templates/auth/passkey-register-api.ts.tmpl`        | WebAuthn registration ceremony endpoint                 | VERIFIED   | `generateRegistrationOptions`, `verifyRegistrationResponse` |
| `web_app_factory/templates/auth/passkey-auth-api.ts.tmpl`            | WebAuthn authentication ceremony endpoint               | VERIFIED   | `generateAuthenticationOptions`, `verifyAuthenticationResponse`, `allowCredentials` |
| `web_app_factory/templates/auth/passkey-client.tsx.tmpl`             | Client-side passkey UI component                        | VERIFIED   | `'use client'`, `startRegistration`, `startAuthentication` |
| `web_app_factory/templates/auth/passkey-hooks.ts.tmpl`               | Supabase JWT bridge for passkey sessions                | VERIFIED   | `generateLink`, `SUPABASE_SERVICE_ROLE_KEY`, `verifyOtp` |
| `web_app_factory/_supabase_auth_renderer.py`                         | Auth template rendering function                        | VERIFIED   | `render_auth_templates()` maps 10 templates; `TEMPLATE_DIR` resolution |
| `web_app_factory/_supabase_provisioner.py`                           | `configure_oauth_providers` async method                | VERIFIED   | 309 lines; PATCHes `/config/auth` with external OAuth fields |
| `web_app_factory/_env_checker.py`                                    | OAuth credential advisory checks                        | VERIFIED   | `_check_oauth_credentials()` + wired into `check_env('supabase')` |
| `agents/definitions.py`                                              | Auth instructions in SPEC_AGENT and BUILD_AGENT         | VERIFIED   | 418 lines; Supabase Auth preference + `getUser` + `auth-ui-react` ban |
| `tools/phase_executors/_phase_3_supabase_steps.py`                   | Extracted Supabase sub-steps with `supabase_oauth_config` | VERIFIED | 265 lines; all 4 Supabase sub-step functions present |
| `tools/phase_executors/phase_2b_executor.py`                         | `generate_auth_pages` sub-step                          | VERIFIED   | 766 lines; `generate_auth_pages` at index 4 in sub_steps |
| `tools/phase_executors/phase_3_executor.py`                          | Delegates to `_phase_3_supabase_steps`                  | VERIFIED   | 705 lines; imports and delegates all 4 Supabase sub-steps |
| `web_app_factory/_supabase_template_renderer.py`                     | `add_passkey_deps()` function                           | VERIFIED   | `@simplewebauthn/browser ^9.0.0` and `@simplewebauthn/server ^9.0.0` |

---

### Key Link Verification

| From                                           | To                                              | Via                                          | Status     | Details                                                         |
|------------------------------------------------|-------------------------------------------------|----------------------------------------------|------------|-----------------------------------------------------------------|
| `web_app_factory/_supabase_auth_renderer.py`   | `web_app_factory/templates/`                    | `TEMPLATE_DIR = Path(__file__).parent / "templates"` | WIRED | Line 34 confirmed; `_AUTH_TEMPLATE_MAPPINGS` uses relative paths |
| `web_app_factory/templates/auth-middleware.ts.tmpl` | `@supabase/ssr`                            | `createServerClient` import                   | WIRED      | Line 1: `import { createServerClient } from '@supabase/ssr'`   |
| `web_app_factory/_supabase_provisioner.py`     | Supabase Management API                         | `httpx.AsyncClient PATCH /config/auth`        | WIRED      | `url = f"{_SUPABASE_API_BASE}/projects/{ref}/config/auth"` at line 303 |
| `web_app_factory/_env_checker.py`              | `check_env` function                            | `_check_oauth_credentials()` appended to results | WIRED   | `statuses.extend(_check_oauth_credentials())` at line 454 for `deploy_target == "supabase"` |
| `tools/phase_executors/phase_2b_executor.py`   | `web_app_factory/_supabase_auth_renderer.py`    | lazy import of `render_auth_templates`        | WIRED      | Lines 528-535: lazy import + call inside `if supabase_enabled` |
| `tools/phase_executors/phase_2b_executor.py`   | `web_app_factory/_supabase_template_renderer.py` | lazy import of `add_passkey_deps`            | WIRED      | Line 531: `from web_app_factory._supabase_template_renderer import add_passkey_deps` |
| `tools/phase_executors/_phase_3_supabase_steps.py` | `web_app_factory/_supabase_provisioner.py`  | lazy import of `SupabaseProvisioner.configure_oauth_providers` | WIRED | Line 147: lazy import inside `supabase_oauth_config` |
| `tools/phase_executors/phase_3_executor.py`    | `tools/phase_executors/_phase_3_supabase_steps.py` | import delegation                         | WIRED      | Lines 58-62: `from tools.phase_executors._phase_3_supabase_steps import ...` |
| `web_app_factory/templates/auth/passkey-client.tsx.tmpl` | `@simplewebauthn/browser`             | `import { startRegistration, startAuthentication }` | WIRED | Line 20 confirmed |
| `web_app_factory/templates/auth/passkey-register-api.ts.tmpl` | `@simplewebauthn/server`        | `import { generateRegistrationOptions, verifyRegistrationResponse }` | WIRED | Lines 26-28 confirmed |

---

### Requirements Coverage

| Requirement | Source Plan | Description                                                                 | Status    | Evidence                                                                                         |
|-------------|-------------|-----------------------------------------------------------------------------|-----------|--------------------------------------------------------------------------------------------------|
| AUTH-01     | 19-01       | Generated apps include `@supabase/ssr` with `createBrowserClient` / `createServerClient` pattern | SATISFIED | `auth-middleware.ts.tmpl` imports `createServerClient from '@supabase/ssr'`; login template imports `createBrowserClient` |
| AUTH-02     | 19-01       | `middleware.ts` with `updateSession()` generated for cookie-based auth in Next.js App Router | SATISFIED | `auth-middleware.ts.tmpl` renders to `src/middleware.ts`; uses cookie getAll/setAll pattern with `createServerClient` + `getUser()` for session refresh |
| AUTH-03     | 19-01, 19-04 | Sign-in / sign-up / sign-out pages generated under `app/auth/`            | SATISFIED | `login-page.tsx.tmpl` → `src/app/auth/login/page.tsx`, `signup-page.tsx.tmpl` → `src/app/auth/signup/page.tsx`, `signout-page.tsx.tmpl` → `src/app/auth/signout/page.tsx`; passkey templates also generated |
| AUTH-04     | 19-01       | Protected route pattern generated — server component checks session, redirects to login if absent | SATISFIED | Middleware redirects to `/auth/login?returnTo=...` for non-`/auth` paths when `getUser()` returns null; `BUILD_AGENT` contains protected route pattern guidance |
| AUTH-05     | 19-01, 19-02 | Google OAuth scaffold generated with code + README manual steps (not automated provisioning) | SATISFIED | OAuth templates (login, callback, signout) + `AUTH_SETUP.md.tmpl` covers step-by-step Google + Apple setup; `configure_oauth_providers` provides optional API-based provisioning |
| AUTH-06     | 19-02       | `SPEC_AGENT` and `BUILD_AGENT` system prompts updated to prefer Supabase Auth when Supabase DB is in use | SATISFIED | `definitions.py` lines 36-39 (SPEC_AGENT), lines 335-345 (BUILD_AGENT); explicit Supabase Auth preference, `getUser()` guidance, `auth-ui-react` ban |

All 6 requirements satisfied. No orphaned requirements found.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | None found |

No TODOs, FIXMEs, placeholders, empty implementations, or console-log-only handlers found in any of the phase 19 key files.

---

### Human Verification Required

#### 1. End-to-End OAuth Sign-in Flow

**Test:** Deploy a generated app with Supabase configured. Click "Sign in with Google" on the login page.
**Expected:** Browser redirects to Google OAuth consent, back to `/auth/callback?returnTo=/`, Supabase session cookie set, user redirected to `/`.
**Why human:** Live OAuth redirect flow requires real credentials and a running Supabase project — cannot verify programmatically.

#### 2. Passkey Registration and Authentication

**Test:** Open the generated login page. Click "Register Passkey", complete the browser WebAuthn UI (Touch ID / Face ID). Then click "Sign in with Passkey" with the registered credential.
**Expected:** Registration stores credential in `passkey_credentials` table. Authentication verifies credential, creates Supabase session via `generateLink` + `verifyOtp`, and redirects the user.
**Why human:** WebAuthn ceremonies require actual browser + OS authenticator interaction. The `passkey_credentials` table schema must also be manually verified in Supabase dashboard.

#### 3. Middleware Protected Route Redirect

**Test:** Access a protected route (e.g., `/dashboard`) in a generated app without being signed in.
**Expected:** Redirected to `/auth/login?returnTo=/dashboard`. After sign-in, redirected back to `/dashboard`.
**Why human:** Requires a running Next.js dev server to verify the middleware intercept behavior.

---

### Gaps Summary

None. All 15 must-have truths verified. All 6 requirements satisfied. All key links confirmed wired. 248 tests pass across all 9 test files created or modified in this phase.

---

## Test Suite Results

```
tests/test_auth_templates.py          47 passed
tests/test_supabase_auth_renderer.py  30 passed
tests/test_supabase_provisioner.py    (includes 6 new OAuth tests)
tests/test_env_checker.py             (includes 5 new OAuth advisory tests)
tests/test_agent_definitions.py       10 passed (new file)
tests/test_phase_2b_executor.py       45 passed
tests/test_phase_3_supabase.py        21 passed
tests/test_phase_3_supabase_steps.py  15 passed
tests/test_passkey_templates.py       31 passed

Total (phase-related): 248 passed in 0.90s
```

---

_Verified: 2026-03-25T03:07:17Z_
_Verifier: Claude (gsd-verifier)_
