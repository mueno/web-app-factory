# Phase 17: Supabase Provisioning - Research

**Researched:** 2026-03-25
**Domain:** Supabase Management API, credential security, static analysis gates
**Confidence:** HIGH (core API patterns verified against official docs; MEDIUM on migration endpoint access)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Credential Management — banto unified**
- `_keychain.py` to be refactored to banto (`SecureVault`) base — all credentials (Anthropic, Vercel, Supabase) retrieved via banto
- banto is **optional dependency** (optional). If not installed, fall back to env vars
- Supabase credentials stored as two banto providers:
  - `supabase-access-token` — Supabase Management API token
  - `supabase-org-id` — Supabase organization ID
- Existing Vercel/Anthropic credentials also mapped to banto providers

**Token-missing behavior**
- If Supabase token is unset when `waf_generate_app` runs, fail immediately
- `waf_check_env` shows a pre-check message (with `banto store` command or env var guidance)

### Claude's Discretion

- Re-run lifecycle for Supabase projects (create new vs. reuse)
- Migration SQL generation approach (direct SQL vs. Supabase CLI vs. Management API)
- `SupabaseProvisioner` internal architecture
- `supabase_gate.py` validation details
- Dual-client pattern (`supabase-browser.ts` / `supabase-server.ts`) template structure
- Default RLS policy patterns
- Security gate implementation (SECG-01, SECG-02)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SUPA-01 | `SupabaseProvisioner` creates a Supabase project via Management API and polls until `ACTIVE_HEALTHY` | Management API POST /v1/projects + GET /v1/projects/{ref}/health polling pattern verified |
| SUPA-02 | Generated migration SQL has RLS enabled on every table with `WITH CHECK (auth.uid() = user_id)` owner policy | Full RLS SQL patterns from official Supabase docs |
| SUPA-03 | `supabase_gate.py` verifies: project created, credentials injected into Vercel env, RLS enabled on all tables | Gate pattern from existing `static_analysis_gate.py` + `GateResult` dataclass |
| SUPA-04 | `waf_check_env` extended to detect `SUPABASE_ACCESS_TOKEN` and `SUPABASE_ORG_ID` presence | `_env_checker.py` + `ToolStatus` dict pattern fully mapped |
| SUPA-05 | Supabase credentials stored and retrieved via OS keychain (same as v2.0 pattern) | `_keychain.py` banto refactor + existing keyring pattern verified |
| SUPA-06 | Dual Supabase client pattern generated: `supabase-browser.ts` (anon key) and `supabase-server.ts` (service_role, server-only) | `@supabase/ssr` createBrowserClient/createServerClient pattern from official docs |
| SECG-01 | Env exposure gate extended to scan for `NEXT_PUBLIC_*SERVICE*ROLE*` patterns | Regex extension to existing `_NEXT_PUBLIC_SECRET_RE` in `static_analysis_gate.py` |
| SECG-02 | RLS gate scans every migration file — rejects if any `CREATE TABLE` lacks immediate `ENABLE ROW LEVEL SECURITY` | New `supabase_gate.py` file scanner using regex |

</phase_requirements>

---

## Summary

Phase 17 adds automated Supabase provisioning to the `waf_generate_app` pipeline. When a spec indicates Supabase as the database backend, the system must: (1) create a Supabase project via Management API and poll until healthy, (2) apply a migration that enables RLS on every table with `auth.uid() = user_id` policies, (3) retrieve API keys and inject them into Vercel as environment variables, and (4) generate dual Supabase client files in the Next.js output. Security gates ensure the service_role key is never exposed client-side and that every migration file includes `ENABLE ROW LEVEL SECURITY`.

The credential subsystem gets a significant upgrade: `_keychain.py` is refactored to use banto (`SecureVault`) as the primary backend when available, with `keyring` and `os.environ` as fallbacks. The banto provider names `supabase-access-token` and `supabase-org-id` are new; existing Vercel/Anthropic credentials are mapped to banto provider names as well. The key constraint is that banto is optional — CI/headless environments without it must still work via env vars.

The critical open question is the Supabase migration API: the `POST /v1/projects/{ref}/database/migrations` endpoint is restricted to select customers. The preferred alternative is a direct PostgreSQL connection (using `asyncpg` or `psycopg2`) to the Supabase project's transaction pooler after provisioning. The db password must be generated at project-creation time and stored securely (in banto) since it cannot be retrieved later via the Management API.

**Primary recommendation:** `SupabaseProvisioner` uses httpx for Management API calls (already in project deps), generates a strong db_pass at runtime, stores it in banto, connects via asyncpg transaction pooler to apply migration SQL directly.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | >=0.28.0 (already in deps) | Supabase Management API calls, Vercel API calls | Already a project dependency; async-first HTTP client |
| `asyncpg` | Latest (new dep) | Execute migration SQL directly via Postgres connection | Required since database/migrations endpoint is restricted access; used by Supabase MCP server |
| `@supabase/ssr` | Latest | Next.js dual-client pattern (browser + server) | Official Supabase package for SSR; replaces legacy auth-helpers |
| `@supabase/supabase-js` | v2 | Base Supabase JS client (peer dep of @supabase/ssr) | Standard Supabase client |
| `banto` | 5.0.0 (local: `/Users/masa/Development/mcp/banto`) | Optional credential backend for SecureVault | Project-standard credential manager; `SecureVault.get_key(provider=...)` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `secrets` (stdlib) | Python stdlib | Generate cryptographically strong db_pass | Creating the Supabase project's database password |
| `keyring` | >=25.0.0 (already in deps) | Keychain fallback if banto unavailable | Non-macOS or banto not installed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncpg` | `psycopg2` | psycopg2 requires libpq native lib; asyncpg is pure Python wheels, better for CI |
| Direct Postgres | Supabase Management API migrations endpoint | Migration endpoint is restricted (select customers only) |
| `asyncpg` | `supabase-py` Python client | supabase-py doesn't support arbitrary DDL SQL; asyncpg is needed for CREATE TABLE + ENABLE ROW LEVEL SECURITY |

**Installation (new dependencies only):**
```bash
uv add asyncpg
npm install @supabase/supabase-js @supabase/ssr   # in generated Next.js apps
```

---

## Architecture Patterns

### SupabaseProvisioner Structure
```
web_app_factory/
├── _supabase_provisioner.py   # New: SupabaseProvisioner class
├── _keychain.py               # Refactor: banto backend + keyring fallback
├── _env_checker.py            # Extend: supabase checks in check_env()
└── _tool_impls.py             # No change needed (orchestrates via bridge)

tools/
├── gates/
│   ├── static_analysis_gate.py   # Extend: SECG-01 service_role pattern
│   └── supabase_gate.py          # New: SUPA-03, SECG-02
└── phase_executors/
    └── phase_3_executor.py       # Extend: optional Supabase provisioning step
```

### Generated App Output Structure
```
output/{app-name}/
└── nextjs/
    └── src/
        └── lib/
            └── supabase/
                ├── supabase-browser.ts   # createBrowserClient (anon key only)
                └── supabase-server.ts    # createServerClient (service_role, server-only)
```

### Pattern 1: Supabase Management API Create + Poll
**What:** POST to create project, then poll GET health until `ACTIVE_HEALTHY`
**When to use:** Always — project is not usable until health check passes

```python
# Source: https://supabase.com/docs/guides/integrations/supabase-for-platforms
import asyncio
import httpx
import secrets

MANAGEMENT_BASE = "https://api.supabase.com/v1"

class SupabaseProvisioner:
    def __init__(self, access_token: str, org_id: str) -> None:
        self._token = access_token   # never logged
        self._org_id = org_id

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json"}

    async def create_project(self, name: str) -> dict:
        """Create project and return project dict with ref."""
        db_pass = secrets.token_urlsafe(32)   # store in banto immediately
        payload = {
            "name": name,
            "organization_slug": self._org_id,
            "db_pass": db_pass,
            "region_selection": {"type": "smartGroup", "code": "americas"},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{MANAGEMENT_BASE}/projects",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
        proj = resp.json()
        proj["_db_pass"] = db_pass   # ephemeral, never serialized to disk
        return proj

    async def poll_until_healthy(
        self, ref: str, *, timeout_s: int = 300, interval_s: int = 5
    ) -> None:
        """Poll GET /v1/projects/{ref}/health until ACTIVE_HEALTHY."""
        url = f"{MANAGEMENT_BASE}/projects/{ref}/health"
        deadline = asyncio.get_event_loop().time() + timeout_s
        async with httpx.AsyncClient(timeout=15.0) as client:
            while asyncio.get_event_loop().time() < deadline:
                resp = await client.get(url, headers=self._headers())
                if resp.status_code == 200:
                    health = resp.json()
                    # health is a list of {name, status} objects
                    all_healthy = all(
                        svc.get("status") == "ACTIVE_HEALTHY"
                        for svc in health
                    )
                    if all_healthy:
                        return
                await asyncio.sleep(interval_s)
        raise TimeoutError(f"Supabase project {ref} did not reach ACTIVE_HEALTHY in {timeout_s}s")
```

### Pattern 2: Apply Migration SQL via Direct Postgres Connection
**What:** Use asyncpg to connect to Supabase transaction pooler and execute DDL SQL
**When to use:** After project is ACTIVE_HEALTHY; the Management API migrations endpoint is restricted

```python
# Source: asyncpg docs + Supabase connection string format
import asyncpg

async def apply_migration(ref: str, db_pass: str, sql: str) -> None:
    """Execute migration SQL via Supabase transaction pooler."""
    # Supabase pooler connection string (transaction mode, port 6543)
    # region is not known upfront — use direct connection instead
    dsn = (
        f"postgresql://postgres:{db_pass}"
        f"@db.{ref}.supabase.co:5432/postgres"
    )
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(sql)
    finally:
        await conn.close()
```

### Pattern 3: RLS Migration SQL Generation
**What:** Generate migration SQL that enables RLS + creates owner policies on every table
**When to use:** For every `CREATE TABLE` in the generated migration

```sql
-- Source: https://supabase.com/docs/guides/database/postgres/row-level-security
-- Generated for table "todos" with user_id FK column:

CREATE TABLE public.todos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES auth.users NOT NULL,
    title text NOT NULL,
    created_at timestamptz DEFAULT now()
);

ALTER TABLE public.todos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can SELECT their own todos"
ON public.todos FOR SELECT TO authenticated
USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can INSERT their own todos"
ON public.todos FOR INSERT TO authenticated
WITH CHECK ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can UPDATE their own todos"
ON public.todos FOR UPDATE TO authenticated
USING ((SELECT auth.uid()) = user_id)
WITH CHECK ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can DELETE their own todos"
ON public.todos FOR DELETE TO authenticated
USING ((SELECT auth.uid()) = user_id);

CREATE INDEX ON public.todos (user_id);
```

### Pattern 4: Inject Credentials into Vercel via REST API
**What:** POST to Vercel's env endpoint to set Supabase env vars on the project
**When to use:** After Supabase project keys are retrieved

```python
# Source: https://vercel.com/docs/rest-api/projects/create-one-or-more-environment-variables
async def inject_vercel_env(
    vercel_token: str,
    vercel_project_id: str,
    supabase_url: str,
    anon_key: str,
    service_role_key: str,
) -> None:
    """Inject Supabase env vars into Vercel project via REST API."""
    url = f"https://api.vercel.com/v10/projects/{vercel_project_id}/env"
    headers = {"Authorization": f"Bearer {vercel_token}"}
    vars_to_set = [
        # NEXT_PUBLIC_ — safe to expose, anon key only
        {"key": "NEXT_PUBLIC_SUPABASE_URL",
         "value": supabase_url,
         "type": "plain",
         "target": ["production", "preview", "development"]},
        {"key": "NEXT_PUBLIC_SUPABASE_ANON_KEY",
         "value": anon_key,
         "type": "plain",
         "target": ["production", "preview", "development"]},
        # NO NEXT_PUBLIC_ prefix — server-only (SECG-01 enforces this)
        {"key": "SUPABASE_SERVICE_ROLE_KEY",
         "value": service_role_key,
         "type": "sensitive",
         "target": ["production", "preview"]},
    ]
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            url,
            headers=headers,
            json=vars_to_set,
            params={"upsert": "true"},
        )
        resp.raise_for_status()
```

### Pattern 5: Dual Supabase Client TypeScript Templates
**What:** Two separate files — browser uses anon key only, server uses service_role
**When to use:** Always generated when Supabase is the database target

```typescript
// supabase-browser.ts
// Source: https://supabase.com/docs/guides/auth/server-side/creating-a-client
import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}
```

```typescript
// supabase-server.ts — MUST NOT use NEXT_PUBLIC_*SERVICE*ROLE* (SECG-01)
// Source: https://supabase.com/docs/guides/auth/server-side/creating-a-client
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createClient() {
  const cookieStore = await cookies()
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,  // no NEXT_PUBLIC_ prefix
    {
      cookies: {
        getAll() { return cookieStore.getAll() },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch { /* Server Component context — OK */ }
        },
      },
    }
  )
}
```

### Pattern 6: banto SecureVault Integration in _keychain.py
**What:** Wrap `_keychain.py` to try banto first, fall back to keyring, then env var
**When to use:** All credential lookups in the project

```python
# Source: /Users/masa/Development/mcp/banto/banto/vault.py
# banto provider names for Supabase:
#   "supabase-access-token"  -> SUPABASE_ACCESS_TOKEN
#   "supabase-org-id"        -> SUPABASE_ORG_ID
# Existing mappings:
#   "anthropic"              -> ANTHROPIC_API_KEY
#   "vercel"                 -> VERCEL_TOKEN

try:
    from banto.vault import SecureVault
    from banto.keychain import KeyNotFoundError
    _BANTO_AVAILABLE = True
except ImportError:
    _BANTO_AVAILABLE = False

_BANTO_PROVIDER_MAP: dict[str, str] = {
    "anthropic_api_key": "anthropic",
    "vercel_token": "vercel",
    "supabase_access_token": "supabase-access-token",
    "supabase_org_id": "supabase-org-id",
}

def get_credential(key: str) -> Optional[str]:
    # Priority 1: banto SecureVault
    if _BANTO_AVAILABLE:
        provider = _BANTO_PROVIDER_MAP.get(key, key)
        try:
            vault = SecureVault()
            return vault.get_key(provider=provider)
        except Exception:
            pass   # fall through to keyring
    # Priority 2: keyring (existing logic)
    # Priority 3: env var fallback (existing _ENV_FALLBACKS)
```

### Pattern 7: supabase_gate.py — SECG-02 Migration Scanner

```python
# Source: existing static_analysis_gate.py pattern (re-use _should_skip, GateResult)
import re
from pathlib import Path
from tools.gates.gate_result import GateResult

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:public\.)?(\w+)",
    re.IGNORECASE,
)
_ENABLE_RLS_RE = re.compile(
    r"ALTER\s+TABLE\s+(?:public\.)?(\w+)\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
    re.IGNORECASE,
)

def _check_rls_coverage(migration_sql: str) -> list[str]:
    """Return list of tables missing ENABLE ROW LEVEL SECURITY."""
    tables_created = {m.group(1).lower()
                      for m in _CREATE_TABLE_RE.finditer(migration_sql)}
    tables_rls = {m.group(1).lower()
                  for m in _ENABLE_RLS_RE.finditer(migration_sql)}
    return sorted(tables_created - tables_rls)
```

### Pattern 8: SECG-01 Extension to static_analysis_gate.py

The existing `_NEXT_PUBLIC_SECRET_RE` pattern already catches `NEXT_PUBLIC_*KEY|*SECRET|*TOKEN`. SECG-01 requires also catching `NEXT_PUBLIC_*SERVICE*ROLE*`. The cleanest approach is to add a second pattern for the service_role-specific case:

```python
# Source: existing static_analysis_gate.py
# Add to existing _NEXT_PUBLIC_SECRET_RE or as a separate pattern:
_NEXT_PUBLIC_SERVICE_ROLE_RE = re.compile(
    r"NEXT_PUBLIC_\w*SERVICE\w*ROLE\w*",
    re.IGNORECASE,
)
```

Since `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY` also matches the existing `*KEY` pattern, SECG-01 may already be partially covered by the existing gate. However, to be explicit and to pass if someone spells it differently (e.g., `NEXT_PUBLIC_SVC_ROLE`), add the dedicated pattern.

### Anti-Patterns to Avoid
- **Storing db_pass in output files or logs:** The database password must only exist in banto/keychain — it cannot be recovered from the Management API later
- **Using NEXT_PUBLIC_ prefix for service_role key:** This bypasses RLS and is a critical security flaw (SECG-01)
- **Creating RLS policies without a user_id column or FK to auth.users:** Policies referencing `auth.uid() = user_id` will not error but will always return 0 rows if the column doesn't exist; spec generation must ensure `user_id uuid REFERENCES auth.users` is present
- **Enabling RLS without creating any policies:** Empty RLS = zero rows visible to everyone; the gate must verify policies exist, not just ENABLE ROW LEVEL SECURITY
- **Not wrapping auth.uid() in SELECT:** `auth.uid() = user_id` without `(SELECT auth.uid())` triggers a function call per row; always use `(SELECT auth.uid())`
- **Polling without timeout:** The health endpoint poll must have a hard timeout (300s recommended) to avoid infinite hangs
- **Re-running without idempotency:** Create-vs-reuse logic needed for re-runs to avoid orphaned Supabase projects

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client for Management API | Custom urllib wrapper | `httpx` (already in deps) | Already used project-wide; async support built in |
| Postgres connection for migrations | subprocess + psql CLI | `asyncpg` | Pure Python, no native lib, consistent error handling |
| Secret generation for db_pass | `random` or `uuid` | `secrets.token_urlsafe(32)` | Cryptographically secure by spec; `random` is not |
| RLS policy SQL templates | Custom per-table logic | Fixed 4-policy pattern (SELECT/INSERT/UPDATE/DELETE) | Standard owner pattern; deviations create security holes |
| `@supabase/ssr` client setup | Manual fetch wrappers | `createBrowserClient`/`createServerClient` | Handles cookie-based session, token refresh, SSR edge cases |

**Key insight:** The Supabase JavaScript client abstracts away cookie coordination between server and browser components. Rolling a custom solution misses token refresh logic and causes auth state desync in SSR.

---

## Common Pitfalls

### Pitfall 1: Migration API Restricted Access
**What goes wrong:** `POST /v1/projects/{ref}/database/migrations` returns 403 for non-partner accounts
**Why it happens:** Supabase restricts this endpoint to select customers
**How to avoid:** Use direct asyncpg connection to Supabase's Postgres endpoint (port 5432, direct connection) after project reaches ACTIVE_HEALTHY
**Warning signs:** 403 response from migrations endpoint during integration testing

### Pitfall 2: db_pass Unrecoverable After Project Creation
**What goes wrong:** The Management API does not expose the db_pass after creation; losing it means no direct DB access
**Why it happens:** Supabase stores only a hash of the password
**How to avoid:** Store `db_pass` in banto immediately after calling `create_project()`, before any other operation; use `banto store supabase-db-pass-{ref}` or a derived key
**Warning signs:** Provisioner fails midway through migration step with no way to reconnect

### Pitfall 3: Vercel Env Vars Not in Production Scope
**What goes wrong:** Env vars injected with only `["preview"]` target are missing in production deploys
**Why it happens:** Vercel's target array must include `"production"` explicitly
**How to avoid:** Always set `target: ["production", "preview", "development"]` for NEXT_PUBLIC_ vars; `["production", "preview"]` for server-only keys
**Warning signs:** Deployed app can't connect to Supabase in production

### Pitfall 4: RLS Without Index on user_id
**What goes wrong:** Queries run full table scans when RLS policy references `user_id`
**Why it happens:** Postgres can't use an index for `user_id = auth.uid()` without an explicit index
**How to avoid:** Always append `CREATE INDEX ON public.{table} (user_id);` in every migration
**Warning signs:** Slow query warnings after RLS enabled; EXPLAIN ANALYZE shows Seq Scan

### Pitfall 5: Empty Table Match on Health Poll
**What goes wrong:** Health response may return an empty list `[]` briefly after project creation
**Why it happens:** Services haven't registered yet with the health endpoint
**How to avoid:** Handle `len(health) == 0` as "not yet healthy" in the poll loop; don't treat empty list as all-healthy
**Warning signs:** Poll exits immediately claiming healthy but subsequent API calls fail

### Pitfall 6: banto Not Available in CI
**What goes wrong:** `from banto.vault import SecureVault` raises ImportError in CI
**Why it happens:** banto is optional; CI uses env vars instead
**How to avoid:** Follow existing keyring pattern — `try: import banto; _BANTO_AVAILABLE = True; except ImportError: _BANTO_AVAILABLE = False`
**Warning signs:** Tests for keychain logic fail in CI with ImportError

### Pitfall 7: Supabase Project Name Collision
**What goes wrong:** If `waf_generate_app` is run twice with the same idea, a second Supabase project is created with the same name (Supabase allows duplicate names)
**Why it happens:** No project lookup before creation
**How to avoid:** In Claude's Discretion (create vs. reuse). Research recommendation: on re-run, look up existing project by slug/name via `GET /v1/projects`, reuse if found and already ACTIVE_HEALTHY; only create new if none found. Store `supabase_project_ref` in the pipeline state JSON.
**Warning signs:** Multiple Supabase projects accumulate after repeated test runs

---

## Code Examples

### Getting API Keys After Project Creation

```python
# Source: https://supabase.com/docs/guides/api/api-keys
# GET /v1/projects/{ref}/api-keys returns list of key objects
async def get_api_keys(ref: str, token: str) -> dict[str, str]:
    """Retrieve anon and service_role keys for a project."""
    url = f"https://api.supabase.com/v1/projects/{ref}/api-keys"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
    keys = resp.json()
    result: dict[str, str] = {}
    for key_obj in keys:
        name = key_obj.get("name", "")
        value = key_obj.get("api_key", "")
        if name == "anon":
            result["anon_key"] = value
        elif name == "service_role":
            result["service_role_key"] = value
    return result
    # Note: project URL is https://{ref}.supabase.co
```

### _env_checker.py Supabase Check (ToolStatus pattern)

```python
# Source: existing _env_checker.py ToolStatus pattern
def _check_supabase_credentials() -> list[dict]:
    """Check for SUPABASE_ACCESS_TOKEN and SUPABASE_ORG_ID.

    Returns two ToolStatus dicts — one per required credential.
    """
    from web_app_factory._keychain import get_credential  # noqa: PLC0415
    statuses = []

    for logical_key, env_var, display_name in [
        ("supabase_access_token", "SUPABASE_ACCESS_TOKEN", "supabase-access-token"),
        ("supabase_org_id", "SUPABASE_ORG_ID", "supabase-org-id"),
    ]:
        value = get_credential(logical_key)
        if value:
            status, note = "present", None
        else:
            status = "missing"
            note = (
                f"{env_var} not set. "
                f"Run: banto store {display_name}  "
                f"OR  export {env_var}=<your-value>"
            )
        statuses.append({
            "tool": display_name,
            "status": status,
            "version_found": None,
            "version_required": None,
            "install_command": None,
            "note": note,
        })
    return statuses
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `anon`/`service_role` JWT keys | `publishable`/`secret` non-JWT keys | 2024-2025 | New keys rotate independently; old keys still work |
| `@supabase/auth-helpers` | `@supabase/ssr` | 2023-2024 | Unified SSR package; auth-helpers deprecated |
| `createClientComponentClient` / `createServerComponentClient` | `createBrowserClient` / `createServerClient` | 2024 | Simpler API; cookie handling explicit |
| RLS policy without `TO authenticated` | Policies with `TO authenticated` | Best practice since ~2023 | Prevents evaluating policies for anon users |

**Deprecated/outdated:**
- `@supabase/auth-helpers-nextjs`: replaced by `@supabase/ssr`; do not use in generated templates
- `supabase.auth.getSession()` on server: replaced by `supabase.auth.getClaims()`; getSession is not safe in server context

---

## Open Questions

1. **db_pass storage key naming for multiple apps**
   - What we know: banto uses `provider` string as the lookup key; must be unique per project
   - What's unclear: If multiple apps each have a Supabase project, they need distinct banto keys (e.g., `supabase-db-pass-{ref}`)
   - Recommendation: Store as `supabase-db-{ref}` where `ref` is the Supabase project ref (returned in creation response); this is deterministic and unique

2. **Project create vs. reuse on re-runs (Claude's Discretion)**
   - What we know: Supabase Management API has `GET /v1/projects` to list all projects; projects have `name` and `ref` fields; duplicate names are allowed
   - What's unclear: Whether to match by name or by stored ref in pipeline state
   - Recommendation: Store `supabase_project_ref` in `docs/pipeline/supabase-provision.json` after first creation; on re-run, if this file exists and the project is still ACTIVE_HEALTHY, skip creation step

3. **asyncpg SSL requirements for Supabase**
   - What we know: Supabase uses SSL by default; connection string may require `?sslmode=require`
   - What's unclear: Whether asyncpg's `connect()` auto-negotiates SSL or requires explicit flag
   - Recommendation: Pass `ssl="require"` to `asyncpg.connect()` to avoid connection errors; test against a real Supabase project

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/test_keychain.py tests/test_env_checker.py tests/test_static_analysis_gate.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SUPA-01 | `SupabaseProvisioner.create_project()` calls correct endpoint; poll exits on ACTIVE_HEALTHY | unit (mocked httpx) | `pytest tests/test_supabase_provisioner.py -x` | Wave 0 |
| SUPA-02 | Migration SQL for a 2-table schema includes ENABLE ROW LEVEL SECURITY + 4 policies per table | unit | `pytest tests/test_supabase_migration_generator.py -x` | Wave 0 |
| SUPA-03 | `supabase_gate.py` returns `passed=False` when a table lacks RLS; `passed=True` when all tables have RLS | unit | `pytest tests/test_supabase_gate.py -x` | Wave 0 |
| SUPA-04 | `check_env("supabase")` returns missing ToolStatus when credentials absent; present when set | unit | `pytest tests/test_env_checker.py -x -k supabase` | Wave 0 (extend existing file) |
| SUPA-05 | `get_credential("supabase_access_token")` tries banto first, falls back to env var when banto absent | unit (mock banto) | `pytest tests/test_keychain.py -x -k banto` | Wave 0 (extend existing file) |
| SUPA-06 | Generated `supabase-browser.ts` uses NEXT_PUBLIC_SUPABASE_ANON_KEY; `supabase-server.ts` uses SUPABASE_SERVICE_ROLE_KEY (no NEXT_PUBLIC) | unit (template render) | `pytest tests/test_supabase_templates.py -x` | Wave 0 |
| SECG-01 | Static analysis gate returns BLOCKED when `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY` appears in any .ts/.env file | unit | `pytest tests/test_static_analysis_gate.py -x -k service_role` | Wave 0 (extend existing file) |
| SECG-02 | `supabase_gate.py` scan returns failed table list when CREATE TABLE lacks ENABLE ROW LEVEL SECURITY | unit | `pytest tests/test_supabase_gate.py -x -k rls` | Wave 0 (in same file as SUPA-03) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_supabase_provisioner.py tests/test_supabase_gate.py tests/test_keychain.py tests/test_env_checker.py tests/test_static_analysis_gate.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_supabase_provisioner.py` — covers SUPA-01 (create_project, poll_until_healthy with mocked httpx)
- [ ] `tests/test_supabase_migration_generator.py` — covers SUPA-02 (SQL generation with RLS policies)
- [ ] `tests/test_supabase_gate.py` — covers SUPA-03 + SECG-02 (file scan, missing RLS detection)
- [ ] `tests/test_supabase_templates.py` — covers SUPA-06 (browser/server template rendering)
- [ ] `asyncpg` dependency: `uv add asyncpg` — if not already in pyproject.toml

---

## Sources

### Primary (HIGH confidence)
- `https://supabase.com/docs/guides/integrations/supabase-for-platforms` — Full Management API workflow: create project, poll health, apply migrations, API keys
- `https://supabase.com/docs/guides/database/postgres/row-level-security` — All RLS SQL patterns with auth.uid()
- `https://supabase.com/docs/guides/auth/server-side/creating-a-client` — createBrowserClient/createServerClient patterns for Next.js App Router
- `https://supabase.com/docs/guides/api/api-keys` — anon vs service_role key security, NEXT_PUBLIC_ prefix rules
- `https://vercel.com/docs/rest-api/projects/create-one-or-more-environment-variables` — Full Vercel env var injection API spec
- `/Users/masa/Development/web-app-factory/web_app_factory/_keychain.py` — existing credential management patterns to extend
- `/Users/masa/Development/web-app-factory/web_app_factory/_env_checker.py` — ToolStatus dict pattern, check_env extension point
- `/Users/masa/Development/web-app-factory/tools/gates/static_analysis_gate.py` — existing gate implementation patterns, GateResult usage
- `/Users/masa/Development/mcp/banto/banto/vault.py` — SecureVault.get_key(provider=...) API

### Secondary (MEDIUM confidence)
- `https://supabase.com/docs/reference/api/v1-get-services-health` — Health endpoint response format (ACTIVE_HEALTHY status string verified)
- `https://github.com/alexander-zuev/supabase-mcp-server` — Confirmed asyncpg direct connection approach for SQL execution
- `https://supabase.com/docs/guides/database/connecting-to-postgres` — Connection string formats (direct: port 5432, pooler: port 6543)

### Tertiary (LOW confidence)
- Supabase Management API `database/migrations` endpoint: documented as restricted to select customers. The specific restriction criteria (free vs. paid tier) were not confirmed from official docs — treat as HIGH risk for availability.
- `GET /v1/projects/{ref}/api-keys` response field names (`api_key`, `name`): confirmed from general docs context; exact field names should be verified against a live response before implementation.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — httpx already in deps; asyncpg confirmed by community use; @supabase/ssr is official package
- Architecture: HIGH — follows established patterns in codebase (_keychain, _env_checker, gate files)
- Migration approach: MEDIUM — asyncpg direct connection confirmed as alternative; db_pass persistence strategy recommended but untested
- Pitfalls: HIGH — most verified from official docs or direct codebase inspection

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (Supabase API evolves rapidly; recheck API key naming conventions)
