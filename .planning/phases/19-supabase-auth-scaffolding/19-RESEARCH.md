# Phase 19: Supabase Auth Scaffolding - Research

**Researched:** 2026-03-25
**Domain:** Supabase Auth (SSR, OAuth, WebAuthn), Next.js App Router middleware, Python template generation
**Confidence:** MEDIUM (passkey/WebAuthn findings are HIGH-confidence on "not natively supported"; OAuth and SSR patterns are HIGH)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Passkey authentication as primary** — no email/password forms
- **Google OAuth + Apple Sign-In** as alternatives
- **@supabase/auth-ui-react** for UI components (see Critical Finding below)
- **Supabase Management API** for auto-enabling OAuth providers
- Google Cloud Console / Apple Developer Portal setup in README only (not automated)
- **Default-protect** all routes; `auth_required: false` endpoints remain public
- Unauthenticated access redirects to `/auth/login` with `returnTo` param
- `middleware.ts` calls session refresh on every request
- `signOut({ scope: 'global' })` for signout, redirect to `/`
- Refresh failure: silent redirect to login (no error message)
- Multi-tab/multi-device: rely on Supabase SSR standard cookie behavior
- Session check: Server Component only (no client-side check required)
- Auth page paths: `/auth/login`, `/auth/signup`, `/auth/signout` under `app/auth/`

### Claude's Discretion

- Passkey + @supabase/auth-ui-react integration pattern (WebAuthn support status)
- Protected route check location (Server Component vs Client Component)
- OAuth callback implementation (`/auth/callback` route structure)
- Management API provider configuration payloads
- SPEC_AGENT / BUILD_AGENT prompt additions (AUTH-06)
- **All technical decisions use 2026-03-25 best practices**

### Deferred Ideas (OUT OF SCOPE)

- Apple Developer Portal full automation (.p8 key auto-provisioning) — v4.0 ADV-01
- Email/password authentication — explicitly excluded
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUTH-01 | Generated apps include `@supabase/ssr` with `createBrowserClient` / `createServerClient` pattern | Already exists in Phase 17 templates; middleware.ts uses createServerClient with anon key |
| AUTH-02 | `middleware.ts` with session refresh generated for cookie-based auth | Standard `@supabase/ssr` pattern confirmed; use `getUser()` (not deprecated `updateSession`/`getSession`) |
| AUTH-03 | Sign-in / sign-up / sign-out pages generated under `app/auth/` | Custom OAuth buttons required (auth-ui-react is unmaintained); callback route at `/auth/callback` |
| AUTH-04 | Protected route pattern: server component checks session, redirects to login if absent | `supabase.auth.getUser()` in server component; redirect via Next.js `redirect()` |
| AUTH-05 | Google OAuth scaffold + README manual steps; Apple Sign-In at same depth | Management API PATCH endpoint confirmed for both providers; Apple requires 6-month key rotation |
| AUTH-06 | SPEC_AGENT and BUILD_AGENT system prompts updated to prefer Supabase Auth when Supabase DB used | definitions.py at 404 lines (borderline); add auth section to both agent prompts |
</phase_requirements>

---

## Summary

Phase 19 adds complete authentication scaffolding to generated apps. The core technology is `@supabase/ssr` (already in Phase 17 templates) with Next.js App Router middleware for session management. The user's decision to use passkeys as the primary auth method has a **critical constraint**: Supabase does not natively support WebAuthn/passkeys as of March 2026. The `@supabase/auth-ui-react` library is also unmaintained (archived October 2025). This forces a design change for the auth UI: custom-built OAuth buttons using `supabase.auth.signInWithOAuth()` directly, with passkey support deferred to third-party solutions or a future native implementation.

The SSR session management pattern is well-established: `middleware.ts` creates a server client, calls `supabase.auth.getUser()` on every request (NOT `getSession()` which is deprecated in server context), and syncs cookies between request and response. Protected routes use server component `getUser()` + Next.js `redirect()`. The OAuth flow uses `signInWithOAuth()` → Supabase → provider → `/auth/callback` → `exchangeCodeForSession()` → app.

For Google and Apple OAuth, the Supabase Management API `PATCH /v1/projects/{ref}/config/auth` endpoint accepts `external_google_enabled`, `external_google_client_id`, `external_google_secret` (and Apple equivalents). This integrates cleanly into the existing `SupabaseProvisioner` pattern from Phase 17. Apple requires a `.p8` private key with 6-month rotation — the scaffold generates code + README guidance, not full automation.

**Primary recommendation:** Build custom auth page templates (no auth-ui-react), use `supabase.auth.signInWithOAuth()` for Google/Apple buttons, defer passkey to third-party (`@simplewebauthn/browser` + `@simplewebauthn/server`) scaffolding as a separate optional sub-step, or scope passkeys out of this phase entirely given the complexity and lack of native Supabase support.

---

## Critical Finding: @supabase/auth-ui-react is Unmaintained

| Finding | Detail | Confidence |
|---------|--------|------------|
| `@supabase/auth-ui-react` status | **Archived/unmaintained since Feb 7, 2024** — Supabase team explicitly states no capacity to maintain | HIGH |
| Passkey support in auth-ui-react | **None** — no WebAuthn components exist | HIGH |
| Native Supabase passkey support | **Not available as of March 2026** — planned but not shipped | HIGH |
| Supabase maintainer quote (Jan 2026) | "this is being planned, could be available quite soon even" | MEDIUM (single source) |

**Impact on locked decisions:** The user decision to use `@supabase/auth-ui-react` is based on outdated information. The library is archived and has no passkey support. The planner MUST choose one of these paths:

1. **Build custom OAuth buttons** (recommended): `signInWithOAuth()` called from a `"use client"` component, skip passkeys entirely in this phase
2. **Use third-party passkey library**: `@simplewebauthn/browser` + `@simplewebauthn/server` with custom server endpoints (significant complexity, requires Supabase custom JWT hooks)
3. **Defer passkeys to a separate phase**: Implement only Google/Apple OAuth now, add passkey ticket to backlog

The research strongly supports option 1 + 3: implement OAuth (Google + Apple) with custom components, add passkeys to the backlog as a separate phase when Supabase native support ships.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@supabase/ssr` | `^0.5.x` | SSR client creation, cookie handling | Official Supabase package for Next.js App Router; already in Phase 17 |
| `@supabase/supabase-js` | `^2.x` | Base Supabase client | Required transitive dep of @supabase/ssr |

### Auth-Specific Additions
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@simplewebauthn/browser` | `^9.x` | WebAuthn browser-side passkey API | Only if passkey scope is confirmed; significant extra work |
| `@simplewebauthn/server` | `^9.x` | WebAuthn server-side verification | Paired with browser package |

### DO NOT Use
| Library | Reason |
|---------|--------|
| `@supabase/auth-ui-react` | Archived since Feb 7, 2024 — no maintenance, no passkey support |
| `@supabase/auth-helpers-nextjs` | Deprecated — replaced by `@supabase/ssr` |
| `supabase.auth.getSession()` in server code | Not guaranteed to revalidate token; use `getUser()` or `getClaims()` |

### Installation (auth pages only):
```bash
# @supabase/ssr is already installed from Phase 17
# No additional npm packages needed for Google/Apple OAuth
npm install @supabase/ssr @supabase/supabase-js
```

---

## Architecture Patterns

### Auth Client Architecture

The existing Phase 17 templates already establish the dual-client pattern. Auth for generated apps needs a **third client variant**: a middleware client that reads/writes cookies for session refresh.

| Client | File | Key | Use |
|--------|------|-----|-----|
| Browser client | `src/lib/supabase/browser.ts` | anon key (`NEXT_PUBLIC_`) | Client components, OAuth trigger |
| Server client | `src/lib/supabase/server.ts` | service_role key (no `NEXT_PUBLIC_`) | Server components, API routes, data access |
| Middleware client | embedded in `middleware.ts` | anon key (`NEXT_PUBLIC_`) | Session refresh only — never used for data |

**IMPORTANT:** The middleware client uses the **anon key** (same as browser client), NOT the service_role key. It only refreshes sessions, not accesses data.

### Recommended Project Structure (auth files only)

```
src/
├── app/
│   └── auth/
│       ├── login/
│       │   └── page.tsx          # OAuth buttons (Google + Apple) — "use client"
│       ├── signup/
│       │   └── page.tsx          # Same as login for OAuth (no separate signup flow)
│       ├── signout/
│       │   └── page.tsx          # Server component: calls signOut + redirect
│       └── callback/
│           └── route.ts          # exchangeCodeForSession handler
├── lib/
│   └── supabase/
│       ├── browser.ts            # createBrowserClient (existing from Phase 17)
│       └── server.ts             # createServerClient with service_role (existing from Phase 17)
└── middleware.ts                 # Session refresh on every request (NEW)

web_app_factory/templates/
├── supabase-browser.ts.tmpl      # Already exists
├── supabase-server.ts.tmpl       # Already exists
├── auth-middleware.ts.tmpl       # NEW — middleware with session refresh
├── auth/
│   ├── login-page.tsx.tmpl       # NEW — OAuth sign-in page
│   ├── signup-page.tsx.tmpl      # NEW — OAuth sign-up page (or redirect to login)
│   ├── signout-page.tsx.tmpl     # NEW — sign-out server action
│   └── callback-route.ts.tmpl   # NEW — PKCE code exchange
```

### Pattern 1: Middleware Session Refresh (AUTH-02)

The middleware client uses `createServerClient` with the **anon key** (not service_role), creates cookies getter/setter from `NextRequest`/`NextResponse`, and calls `supabase.auth.getUser()` to refresh the session on every non-static request.

```typescript
// Source: Supabase SSR docs + vercel/nextjs-subscription-payments pattern
// File: middleware.ts (at project root or src/middleware.ts)
import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function middleware(request: NextRequest): Promise<NextResponse> {
  let supabaseResponse = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,  // anon key — NOT service_role
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          )
          supabaseResponse = NextResponse.next({ request })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  // IMPORTANT: Never trust getSession() in server code — use getUser()
  const { data: { user } } = await supabase.auth.getUser()

  // Default-protect: redirect to login if no session on protected routes
  if (!user && !request.nextUrl.pathname.startsWith('/auth')) {
    const url = request.nextUrl.clone()
    url.pathname = '/auth/login'
    url.searchParams.set('returnTo', request.nextUrl.pathname)
    return NextResponse.redirect(url)
  }

  return supabaseResponse
}

export const config = {
  matcher: [
    // Skip static assets and Next.js internals
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
```

**Note on getClaims() vs getUser():** The newer `getClaims()` does local JWT validation (faster, no server round-trip). `getUser()` validates with the Supabase server (detects logout server-side). For the default-protect pattern, `getUser()` is required because it detects revoked sessions. `getClaims()` is safe for performance-critical cases where logout detection latency is acceptable.

### Pattern 2: Protected Route (AUTH-04)

Server component that calls `getUser()` and redirects if no session.

```typescript
// Source: Supabase SSR official pattern
// File: any protected page.tsx
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'

export default async function ProtectedPage(): Promise<React.ReactElement> {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect('/auth/login')
  }

  return <div>Protected content for {user.email}</div>
}
```

**Note:** With the middleware default-protect pattern, protected page checks are a safety net only. The middleware already redirects. The server component check is a second defense layer.

### Pattern 3: OAuth Sign-In Page (AUTH-03, AUTH-05)

```typescript
// Source: Supabase signInWithOAuth docs + Next.js server actions
// File: app/auth/login/page.tsx — "use client"
'use client'

import { createClient } from '@/lib/supabase/browser'
import { useSearchParams } from 'next/navigation'

export default function LoginPage(): React.ReactElement {
  const searchParams = useSearchParams()
  const returnTo = searchParams.get('returnTo') || '/'

  const handleGoogleSignIn = async () => {
    const supabase = createClient()
    const origin = window.location.origin
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${origin}/auth/callback?returnTo=${encodeURIComponent(returnTo)}`,
      },
    })
  }

  const handleAppleSignIn = async () => {
    const supabase = createClient()
    const origin = window.location.origin
    await supabase.auth.signInWithOAuth({
      provider: 'apple',
      options: {
        redirectTo: `${origin}/auth/callback?returnTo=${encodeURIComponent(returnTo)}`,
      },
    })
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex flex-col gap-4 p-8">
        <button onClick={handleGoogleSignIn}
          className="flex items-center gap-2 rounded-lg border px-6 py-3 hover:bg-gray-50">
          Sign in with Google
        </button>
        <button onClick={handleAppleSignIn}
          className="flex items-center gap-2 rounded-lg bg-black px-6 py-3 text-white hover:bg-gray-800">
          Sign in with Apple
        </button>
      </div>
    </div>
  )
}
```

### Pattern 4: OAuth Callback Route (AUTH-03)

```typescript
// Source: Supabase PKCE callback pattern
// File: app/auth/callback/route.ts
import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function GET(request: Request): Promise<NextResponse> {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const returnTo = searchParams.get('returnTo') || '/'

  if (code) {
    const cookieStore = await cookies()
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll() { return cookieStore.getAll() },
          setAll(cookiesToSet) {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          },
        },
      }
    )
    const { error } = await supabase.auth.exchangeCodeForSession(code)
    if (!error) {
      return NextResponse.redirect(`${origin}${returnTo}`)
    }
  }

  // Auth code exchange failed — redirect to login silently (per locked decision)
  return NextResponse.redirect(`${origin}/auth/login`)
}
```

### Pattern 5: Sign-Out (AUTH-03)

```typescript
// Source: Supabase docs — scope:'global' per locked decision
// File: app/auth/signout/page.tsx — Server Component with Form Action
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'

async function signOut(): Promise<never> {
  'use server'
  const supabase = await createClient()
  await supabase.auth.signOut({ scope: 'global' })
  redirect('/')
}

export default function SignOutPage(): React.ReactElement {
  return (
    <form action={signOut}>
      <button type="submit" className="rounded-lg bg-red-600 px-6 py-3 text-white">
        Sign Out
      </button>
    </form>
  )
}
```

### Pattern 6: Management API OAuth Provider Setup (AUTH-05)

```python
# Source: Supabase Management API docs
# Extends SupabaseProvisioner pattern from Phase 17

async def configure_oauth_providers(
    self,
    ref: str,
    google_client_id: str | None,
    google_secret: str | None,
    apple_client_id: str | None,
    apple_secret: str | None,
) -> None:
    """Enable Google/Apple OAuth on Supabase project via Management API."""
    payload: dict[str, Any] = {}

    if google_client_id and google_secret:
        payload["external_google_enabled"] = True
        payload["external_google_client_id"] = google_client_id
        payload["external_google_secret"] = google_secret

    if apple_client_id and apple_secret:
        payload["external_apple_enabled"] = True
        payload["external_apple_client_id"] = apple_client_id
        payload["external_apple_secret"] = apple_secret

    if not payload:
        logger.info("No OAuth credentials provided — skipping provider configuration")
        return

    url = f"{_SUPABASE_API_BASE}/projects/{ref}/config/auth"
    async with httpx.AsyncClient() as client:
        response = await client.patch(url, json=payload, headers=self._headers())
        response.raise_for_status()

    # Log only keys configured, never values
    logger.info("OAuth providers configured: %r", list(payload.keys()))
```

### Anti-Patterns to Avoid

- **Using `getSession()` in server code**: Not guaranteed to revalidate; use `getUser()` instead
- **Service_role key in middleware**: Middleware uses anon key; service_role only for server components doing data access
- **`@supabase/auth-ui-react`**: Archived; custom buttons are the only viable path
- **Client component session check for protection**: Server component must do the redirect (locked decision: `auth_required` check is server-side only)
- **Hardcoding OAuth redirect URIs**: Must use `window.location.origin` (client) or `request.headers.get('origin')` (server action) for local dev compatibility
- **Skipping `returnTo` parameter**: The locked decision requires `returnTo` on login redirect so users land back on their intended page post-auth

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth 2.0 + PKCE flow | Custom auth server | `supabase.auth.signInWithOAuth()` | Token exchange, PKCE verifier, state param — 50+ edge cases |
| Cookie-based session storage | Custom session serialization | `@supabase/ssr` `createServerClient` cookie handlers | Token refresh, expiry, secure attributes |
| JWT validation | Custom RS256 verify | `supabase.auth.getUser()` / `getClaims()` | Key rotation, clock skew |
| WebAuthn registration ceremony | Custom WebAuthn | `@simplewebauthn/server` | Challenge generation, credential storage, attestation |
| WebAuthn authentication ceremony | Custom credential verification | `@simplewebauthn/browser` + `@simplewebauthn/server` | Authenticator state, counter validation |

**Key insight:** Auth is deceptively complex — the 95% happy path looks simple, but edge cases (token refresh races, logout propagation, PKCE replay attacks) require library-level handling.

---

## Common Pitfalls

### Pitfall 1: getSession() in Server Context
**What goes wrong:** `supabase.auth.getSession()` in server components, middleware, or route handlers returns the session from cookies without server-side validation. A user who signed out on another device can still access protected routes.
**Why it happens:** `getSession()` used to be the recommended pattern; docs are inconsistent.
**How to avoid:** Always use `supabase.auth.getUser()` in server context. `getUser()` calls the Supabase auth server to validate the token.
**Warning signs:** Any import of `getSession` in server-context files.

### Pitfall 2: Service Role Key in Middleware
**What goes wrong:** Using `SUPABASE_SERVICE_ROLE_KEY` in `middleware.ts` means the service role key is bundled into the Edge Runtime — which may log or leak it. Also violates SECG-01.
**Why it happens:** Developer copies the server.ts pattern into middleware.
**How to avoid:** Middleware always uses `NEXT_PUBLIC_SUPABASE_ANON_KEY`. The middleware only refreshes sessions, never accesses privileged data.

### Pitfall 3: OAuth Callback Route Missing from Middleware Exclusion
**What goes wrong:** If `middleware.ts` redirects unauthenticated requests to `/auth/login` but also intercepts `/auth/callback`, the OAuth callback will redirect in a loop.
**Why it happens:** The default-protect middleware catches `/auth/callback` before the session is established.
**How to avoid:** The middleware must exclude `/auth/*` paths from the redirect logic (already shown in Pattern 1 above: `!request.nextUrl.pathname.startsWith('/auth')`).

### Pitfall 4: Redirect URL Not Added to Supabase Allow List
**What goes wrong:** `signInWithOAuth()` callback redirects are rejected by Supabase with "Redirect URL not in allowed list" error.
**Why it happens:** Supabase Dashboard → Authentication → URL Configuration requires explicit redirect URL entries.
**How to avoid:** The generated README must instruct users to add `http://localhost:3000/**` and `https://<your-vercel-domain>/**` to the Supabase redirect allow list. The `waf_check_env` guidance should mention this.

### Pitfall 5: Apple Sign-In Secret Key Rotation
**What goes wrong:** Apple requires generating a new `.p8` secret key every 6 months. If not rotated, Apple OAuth silently fails.
**Why it happens:** The key is a JWT signed with the `.p8` private key; Apple invalidates it after 6 months.
**How to avoid:** README must include prominent 6-month rotation reminder. The scaffolded code should include a comment with the key generation date.

### Pitfall 6: auth-ui-react Passkey Expectation
**What goes wrong:** Attempting to use `@supabase/auth-ui-react` passkey components that don't exist.
**Why it happens:** User decision assumed the library supports passkeys; it does not and the library is archived.
**How to avoid:** Use custom OAuth buttons. Passkeys require a separate implementation strategy (third-party or future native Supabase support).

### Pitfall 7: Missing /auth/confirm for Magic Links and OTP
**What goes wrong:** If using email confirmation (even just for OAuth email delivery), the `?token_hash&type=signup` callback fails if there's no `/auth/confirm` route.
**Why it happens:** Supabase sends email confirmations with a token hash flow distinct from the OAuth PKCE code flow.
**How to avoid:** For pure OAuth-only apps (Google + Apple), this is not needed. Document this pitfall if email features are added later.

### Pitfall 8: definitions.py File Size
**What goes wrong:** `agents/definitions.py` is currently at 404 lines. Adding substantial auth instructions to both SPEC_AGENT and BUILD_AGENT prompts may push it into the 401-600 "warning" range and above the 600 "must split" threshold.
**Why it happens:** Monolithic agent definitions file accumulates all prompt content.
**How to avoid:** Keep auth additions concise (10-20 lines per agent), or plan to extract agent prompts into separate files per `.claude/rules/25-code-health.md`.

---

## State of the Art (2026-03-25)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@supabase/auth-helpers-nextjs` | `@supabase/ssr` | 2023-2024 | auth-helpers deprecated; SSR package is the standard |
| `@supabase/auth-ui-react` | Custom components or Radix/shadcn | Feb 2024 (archived) | No maintained pre-built auth UI exists |
| `supabase.auth.getSession()` in middleware | `supabase.auth.getUser()` or `getClaims()` | 2024 | getSession not guaranteed to revalidate in server context |
| `updateSession()` helper pattern | Direct `getUser()` in middleware body | 2024-2025 | The updateSession helper was from auth-helpers; SSR uses getUser directly |
| Email/password as primary auth | OAuth + Passkeys (when available) | Industry trend 2024-2025 | Better UX, no password storage risk |

**Deprecated/outdated:**
- `@supabase/auth-helpers-nextjs`: Deprecated — use `@supabase/ssr`
- `@supabase/auth-ui-react`: Archived — build custom components
- `supabase.auth.getSession()` in server code: Unreliable — use `getUser()`
- `updateSession()` helper: auth-helpers pattern — use direct `getUser()` call

---

## Management API Auth Configuration

The `PATCH /v1/projects/{ref}/config/auth` endpoint accepts these fields for OAuth provider setup:

```json
{
  "external_google_enabled": true,
  "external_google_client_id": "<GOOGLE_CLIENT_ID>",
  "external_google_secret": "<GOOGLE_CLIENT_SECRET>",
  "external_apple_enabled": true,
  "external_apple_client_id": "<APPLE_SERVICES_ID>",
  "external_apple_secret": "<APPLE_GENERATED_SECRET>"
}
```

**Integration point:** Add `configure_oauth_providers()` method to `SupabaseProvisioner` in `_supabase_provisioner.py`. Called from `phase_3_executor.py` after `supabase_provision` sub-step, conditional on `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `APPLE_CLIENT_ID` / `APPLE_CLIENT_SECRET` being present in environment (via `_env_checker.py` check).

**Apple secret generation:** Apple doesn't store the client secret — it's a JWT signed with the `.p8` private key. The `external_apple_secret` value is this generated JWT, which the user must create following the README steps. Supabase accepts it directly.

---

## ENV Checker Additions (AUTH-05)

Add new check function to `web_app_factory/_env_checker.py`:

```python
def _check_oauth_credentials() -> list[dict[str, Any]]:
    """Check for optional Google/Apple OAuth credentials."""
    # Returns ToolStatus list with status "present" or "missing"
    # Missing OAuth creds are ADVISORY (not blocking) — users can add later
    # Keys: google_client_id, google_client_secret, apple_client_id, apple_client_secret
```

Current `_env_checker.py` is at 539 lines — adding ~50 lines puts it at ~589 (within warning range 401-600). This is acceptable.

---

## SPEC_AGENT / BUILD_AGENT Updates (AUTH-06)

### SPEC_AGENT addition (~15 lines)

Add to the `## Your Stack Context` section:

```
- **Auth**: Supabase Auth (when Supabase DB is in use) via @supabase/ssr
  - Prefer Supabase Auth over NextAuth.js, Clerk, or other auth providers when the app uses Supabase as its database
  - When backend-spec.json includes `auth_required: true` endpoints, assume Supabase Auth is active
```

### BUILD_AGENT addition (~20 lines)

Add a new `## Authentication (when Supabase DB is in use)` section:

```
When the project uses Supabase (NEXT_PUBLIC_SUPABASE_URL is present):
- Use src/lib/supabase/browser.ts for client-side auth (createBrowserClient, anon key)
- Use src/lib/supabase/server.ts for server-side auth (createServerClient, service_role key)
- NEVER use @supabase/auth-ui-react — it is unmaintained (archived Feb 2024)
- NEVER use supabase.auth.getSession() in server code — use getUser() instead
- Protected routes: call supabase.auth.getUser() in server component, redirect('/auth/login') if null
- OAuth signIn: use signInWithOAuth({ provider, options: { redirectTo: origin + '/auth/callback' } })
```

**File size check:** `agents/definitions.py` is at 404 lines. Adding ~35 total lines brings it to ~439 — still in the "normal" range (≤600 warning threshold).

---

## Open Questions

1. **Passkey scope for this phase**
   - What we know: Supabase has no native WebAuthn support as of March 2026; `@supabase/auth-ui-react` is archived with no passkey support; `@simplewebauthn` works but requires custom server endpoints and Supabase custom JWT hooks
   - What's unclear: Whether the user wants to accept the complexity of `@simplewebauthn` integration, or defer passkeys entirely
   - Recommendation: **Plan should propose implementing Google + Apple OAuth only, add passkey as a separate backlog ticket.** If the user insists on passkeys in this phase, the planner should scope it as a separate sub-step using `@simplewebauthn/browser@9.x` + `@simplewebauthn/server@9.x`.

2. **middleware.ts placement: project root vs `src/`**
   - What we know: Next.js App Router supports both `middleware.ts` at root and `src/middleware.ts`; existing templates use `src/app/` structure
   - What's unclear: Which location the project_skeleton_generator places files
   - Recommendation: Use `src/middleware.ts` to keep all source in `src/`

3. **returnTo parameter security**
   - What we know: The `returnTo` parameter is user-controlled and could be used for open redirect attacks
   - What's unclear: Whether to validate the returnTo path is internal (starts with `/`) in the callback route
   - Recommendation: Validate in the callback route: `returnTo.startsWith('/') ? returnTo : '/'`

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `cd /Users/masa/Development/web-app-factory && uv run pytest tests/test_supabase_templates.py tests/test_supabase_provisioner.py -q` |
| Full suite command | `cd /Users/masa/Development/web-app-factory && uv run pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | `@supabase/ssr` createBrowserClient/createServerClient templates exist | unit | `uv run pytest tests/test_supabase_templates.py -q` | ✅ (Phase 17) |
| AUTH-02 | `auth-middleware.ts.tmpl` exists and contains `getUser()` + cookie sync | unit | `uv run pytest tests/test_auth_middleware_template.py -q` | ❌ Wave 0 |
| AUTH-03 | `auth/login`, `auth/signup`, `auth/signout`, `auth/callback` templates exist with correct patterns | unit | `uv run pytest tests/test_auth_page_templates.py -q` | ❌ Wave 0 |
| AUTH-04 | Protected route pattern uses `getUser()` NOT `getSession()` | unit | `uv run pytest tests/test_auth_page_templates.py -q` | ❌ Wave 0 |
| AUTH-05 | SupabaseProvisioner gains `configure_oauth_providers()` method; env checker has OAuth credential check | unit | `uv run pytest tests/test_supabase_provisioner.py tests/test_env_checker.py -q` | Partial (extend existing) |
| AUTH-06 | SPEC_AGENT and BUILD_AGENT prompts contain Supabase Auth preference instructions | unit | `uv run pytest tests/test_agent_definitions.py -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_supabase_templates.py tests/test_supabase_provisioner.py -q`
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_auth_middleware_template.py` — covers AUTH-02: middleware template content validation
- [ ] `tests/test_auth_page_templates.py` — covers AUTH-03, AUTH-04: login/signup/signout/callback template validation
- [ ] `tests/test_agent_definitions.py` — covers AUTH-06: SPEC_AGENT + BUILD_AGENT prompt content checks

*(Extend existing: `tests/test_supabase_provisioner.py` for new `configure_oauth_providers()` method; `tests/test_env_checker.py` for OAuth credential checks)*

---

## Sources

### Primary (HIGH confidence)
- Supabase Discussion #8677 — passkey support status (not natively available as of March 2026, "being planned")
- https://github.com/supabase-community/auth-ui — archived Oct 23, 2025; unmaintained since Feb 7, 2024
- https://supabase.com/docs/guides/auth/social-login/auth-google — Management API PATCH endpoint for Google OAuth
- https://supabase.com/docs/guides/auth/social-login/auth-apple — Management API PATCH endpoint for Apple Sign-In + 6-month key rotation requirement
- https://supabase.com/docs/guides/auth/server-side/nextjs — SSR auth setup, getUser() over getSession() requirement
- https://github.com/vercel/nextjs-subscription-payments utils/supabase/middleware.ts — updateSession/getUser pattern
- Existing codebase: `_supabase_provisioner.py`, `agents/definitions.py`, template files (direct read)

### Secondary (MEDIUM confidence)
- Supabase maintainer quote Jan 2026 from Discussion #8677: "this is being planned, could be available quite soon"
- https://supabase.com/docs/guides/auth/server-side/creating-a-client — getClaims() vs getUser() tradeoffs
- https://supabase.com/docs/guides/auth/server-side/advanced-guide — PKCE flow, Cache-Control headers
- WebSearch: signInWithOAuth PKCE callback pattern consensus from multiple 2025 sources

### Tertiary (LOW confidence)
- Passkey implementation via @simplewebauthn: blog sources only, not verified against current package versions
- `getClaims()` as a performance optimization: mentioned in Supabase issues but not in official middleware examples yet

---

## Metadata

**Confidence breakdown:**
- Standard stack (SSR, OAuth patterns): HIGH — confirmed via official Supabase docs
- Auth-ui-react status: HIGH — archived status confirmed via GitHub + multiple sources
- Passkey native support: HIGH (not available) — confirmed via Discussion #8677 maintainer comment
- Architecture patterns (middleware, callback, protected routes): HIGH — confirmed via Vercel example repo and Supabase docs
- Management API payload structure: HIGH — confirmed via official docs for both Google and Apple
- Passkey via simplewebauthn complexity: MEDIUM — blog examples, not official docs
- getClaims() vs getUser() nuance: MEDIUM — Supabase issues, not stable docs yet

**Research date:** 2026-03-25
**Valid until:** 2026-06-25 (stable domain; check passkey native support status before then — Supabase may ship it)
