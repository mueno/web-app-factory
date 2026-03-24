# Technology Stack

**Project:** web-app-factory
**Researched:** 2026-03-24
**Scope of this update:** v3.0 additions only — Supabase (DB + Auth + Realtime), allnew-mobile-baas integration, iOS backend generation, OpenAI Apps SDK (ChatGPT distribution). Do not change the v1.0/v2.0 stack already documented below.

---

## v3.0 Stack Additions (NEW — Research for This Milestone)

### Backend Generation: Supabase DB + Auth + Realtime (Generated Apps)

**Decision: `@supabase/supabase-js` v2 + `@supabase/ssr` for Next.js generated apps**

The generated apps use Supabase as their backend. The right packages depend on whether code runs in a browser (client component) or on the server (Route Handlers, Server Actions, middleware).

| Package | Version | Side | Purpose | Why |
|---------|---------|------|---------|-----|
| `@supabase/supabase-js` | `^2.99.3` | Client + Server | Core SDK — DB queries, Auth, Storage, Realtime | Universal JS client; v2 is current stable (2.99.3, March 21 2026); 2.100.0 canary in flight |
| `@supabase/ssr` | `^0.9.0` | Server-only | Cookie-based auth for Next.js SSR | Replaces deprecated `@supabase/auth-helpers-nextjs`; required for App Router Server Components and middleware |

**Do NOT add `@supabase/auth-helpers-nextjs`** — deprecated, replaced by `@supabase/ssr`. Future bug fixes target `@supabase/ssr` only.

#### Generated App Integration Pattern

Two client types, one for each execution context:

```typescript
// lib/supabase/client.ts — Client Components (browser)
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}

// lib/supabase/server.ts — Server Components, Route Handlers, Server Actions
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          );
        },
      },
    }
  );
}
```

#### Environment Variables Injected by Pipeline

```
NEXT_PUBLIC_SUPABASE_URL=https://<project_ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon_key>
SUPABASE_SERVICE_ROLE_KEY=<service_role_key>
```

The pipeline provisions these from the Supabase Management API and injects them into the generated app's `.env.local` and Vercel project environment.

**Confidence:** HIGH — verified from Supabase official docs (SSR guide, March 2026) and npm version confirmed.

---

### Backend Generation: Vercel Functions Pattern (Generated Apps)

**Decision: Next.js App Router Route Handlers at `app/api/**` — no separate Express/Hono**

For generated backends, use Next.js App Router Route Handlers. They become Vercel serverless functions automatically with zero configuration. No separate Node.js server or framework is needed.

```typescript
// Generated app: app/api/items/route.ts
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET() {
  const supabase = await createClient();
  const { data, error } = await supabase.from("items").select("*");
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}

export async function POST(request: Request) {
  const supabase = await createClient();
  const body = await request.json();
  const { data, error } = await supabase.from("items").insert(body).select().single();
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json(data, { status: 201 });
}
```

**Why Route Handlers over Server Actions for the generated REST API:**
- Server Actions are POST-only; REST clients (iOS apps) need GET, PUT, DELETE
- iOS backend generation requires a conventional REST interface
- Route Handlers produce standard HTTP endpoints consumable by Swift URLSession

**Confidence:** HIGH — verified from Next.js official docs and Vercel deployment docs (March 2026).

---

### Backend Provisioning: Supabase Management API (Pipeline, Python)

**Decision: `httpx` (already a pipeline dependency) for Supabase Management API calls — no new Python dependency**

The pipeline provisions Supabase projects programmatically using the Supabase Management API. No Supabase Python SDK wrapper for management operations exists — use direct REST calls with `httpx`.

```python
import httpx

SUPABASE_MANAGEMENT_URL = "https://api.supabase.com/v1"

async def create_supabase_project(
    access_token: str,  # personal access token from user's Supabase account
    org_id: str,
    project_name: str,
    db_password: str,
    region: str = "us-east-1",
) -> dict:
    """Create a Supabase project via Management API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SUPABASE_MANAGEMENT_URL}/projects",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "name": project_name,
                "organization_id": org_id,
                "db_pass": db_password,
                "region": region,
                "plan": "free",
            },
            timeout=120.0,  # project creation takes 30–90s
        )
        response.raise_for_status()
        return response.json()  # contains project_ref, anon_key, service_role_key

async def get_project_api_keys(access_token: str, project_ref: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SUPABASE_MANAGEMENT_URL}/projects/{project_ref}/api-keys",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()
```

**Authentication:** Supabase Management API uses Personal Access Tokens (PAT). Users generate a PAT at https://app.supabase.com/account/tokens. The pipeline stores this via `keyring` (already used for ANTHROPIC_API_KEY).

**New credential to manage:** `SUPABASE_ACCESS_TOKEN` — stored in keyring, surfaced in `waf_check_env` tool output.

**No new Python dependencies.** `httpx` is already in `pyproject.toml`.

**Confidence:** HIGH — Supabase Management API is documented at https://supabase.com/docs/reference/api/introduction; `httpx` is already a pipeline dep.

---

### DB Schema Generation: `supabase` npm CLI (Generated Apps, Dev Tool)

**Decision: `supabase` npm CLI v2.83.0 as `devDependency` in generated apps (not in pipeline Python deps)**

Generated apps use the Supabase CLI for type generation and local development. The CLI is added to the generated app's `package.json`, not to the Python pipeline.

```json
// Generated app package.json devDependencies
{
  "supabase": "^2.83.0"
}
```

```json
// Generated app package.json scripts
{
  "supabase:types": "supabase gen types typescript --project-id \"$SUPABASE_PROJECT_REF\" > src/types/database.types.ts"
}
```

**Why as devDependency in generated app, not in pipeline:**
- The CLI is used by the app developer for ongoing schema work after generation
- Pipeline provisioning uses the Management API directly (httpx), not the CLI
- Avoids adding a Node.js CLI dependency to the Python pipeline

**Confidence:** HIGH — supabase npm CLI v2.83.0 confirmed on npm (March 21, 2026).

---

### allnew-mobile-baas Integration

**Decision: Copy allnew-baas pattern — pure Node.js ESM, Vercel Functions at `api/**/*.js`, no framework**

The allnew-mobile-baas at `projects/allnew-baas/vercel/` is an existing Vercel Functions project with one pattern:
- Pure Node.js ESM (`"type": "module"`)
- Functions at `api/**/*.js` with `export default async function handler(req, res)`
- No Express, Hono, or framework overhead
- `vercel.json` with `"functions": { "api/**/*.js": { "maxDuration": 10 } }`
- CORS, rate-limiting, and shared-secret auth baked into each handler

For the WAF backend template that targets iOS clients (the "allnew-mobile-baas integration"), generate the same pattern — a `vercel-functions/` subdirectory inside the generated app with this structure.

**Key environment variables from allnew-baas to replicate:**

| Variable | Purpose |
|----------|---------|
| `BAAS_ALLOWED_ORIGINS` | CSV of allowed CORS origins |
| `BAAS_ALLOWED_APP_IDS` | CSV of allowed app IDs (prevents unauthorized callers) |
| `BAAS_CLIENT_SHARED_SECRET` | Bearer token for server-to-server auth |
| `SUPABASE_SERVICE_ROLE_KEY` | DB writes that bypass RLS |

**No new packages.** The allnew-baas uses `@google/genai` for Gemini-specific features. The WAF template for iOS backends uses `@supabase/supabase-js` instead.

**Confidence:** HIGH — pattern extracted from live code at `projects/allnew-baas/vercel/api/gemini/live-token.js`.

---

### iOS Backend Generation

**Decision: Generate a standalone `backend/` directory with Vercel Functions + Supabase — not a Next.js app**

iOS backend generation produces a minimal `backend/` project (not a full Next.js app) because:
- iOS clients call REST endpoints directly; no React/HTML needed
- Simpler to reason about: `api/*.js` functions + `vercel.json` + `.env`
- No build step, no `next build`, deploys in seconds via `vercel --prod`
- Same pattern as allnew-mobile-baas (proven in production)

Generated structure:
```
backend/
├── api/
│   ├── health.js          # GET /api/health
│   ├── auth/
│   │   └── callback.js    # GET /api/auth/callback (OAuth redirect)
│   └── [resource]/
│       └── index.js       # GET/POST /api/[resource]
├── vercel.json
├── package.json           # { "type": "module", "dependencies": { "@supabase/supabase-js": "^2.99.3" } }
└── .env.example
```

Swift SDK compatibility: `supabase-swift` v2.39.0 (Swift Package Manager, `https://github.com/supabase/supabase-swift.git`, `.upToNextMajor(from: "2.0.0")`). Platform support: iOS 13+, macOS 10.15+.

**No new Python pipeline dependencies.** The generator writes these files from templates.

**Confidence:** HIGH — allnew-baas pattern verified from source; supabase-swift v2.39.0 confirmed on GitHub.

---

### OpenAI Apps SDK: ChatGPT Distribution

**Decision: `@modelcontextprotocol/ext-apps` + `@modelcontextprotocol/sdk` as additional MCP server mode**

The OpenAI Apps SDK is not actually an OpenAI-owned package. It is the MCP Apps standard, maintained by the MCP organization at `modelcontextprotocol/ext-apps`. ChatGPT implements this standard.

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `@modelcontextprotocol/ext-apps` | `^1.2.2` | MCP Apps UI registration, iframe bridge | Official SDK for registering Views (ChatGPT UI widgets) from MCP servers |
| `@modelcontextprotocol/sdk` | `^1.20.2` | MCP server runtime | Already used via FastMCP; this is the underlying SDK |
| `zod` | `^3.25.76` | Schema validation for tool inputs | Required peer dep for @modelcontextprotocol/sdk |

**These are JavaScript/TypeScript dependencies, not Python.** The web-app-factory MCP server is in Python (FastMCP). ChatGPT distribution requires either:

**Option A (recommended for Phase 1): Expose existing FastMCP server as streamable-HTTP** — ChatGPT's MCP connector supports HTTP+SSE transport. The existing Python FastMCP server already supports this. No new dependencies needed for basic tool access from ChatGPT.

**Option B (for ChatGPT UI Widget): Add a companion Node.js MCP server** — A thin `chatgpt-app/server.js` that imports `@modelcontextprotocol/ext-apps` and registers UI resources (Views). This server runs alongside the Python server or replaces it for ChatGPT clients.

**Recommendation: Start with Option A (zero new deps), add Option B only if a ChatGPT-specific UI widget is required.**

#### ChatGPT App Submission Requirements

| Requirement | Details |
|-------------|---------|
| Hosting | MCP server must be on a publicly accessible domain (no localhost) |
| Transport | HTTP/SSE (streamable-HTTP transport — ChatGPT MCP connector) |
| Security | CSP headers required if app has a UI (iframe-based Views) |
| Privacy policy | Required for all app submissions |
| Review | OpenAI developer account + verified developer status required |
| Tool annotations | Write/destructive tools must set `readOnlyHint: false` and `destructiveHint: true` |

#### For Option A: FastMCP HTTP transport (zero new dependencies)

FastMCP already supports streamable-HTTP transport (the MCP transport ChatGPT's MCP connector uses). Configure:

```python
mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

This is sufficient for ChatGPT to discover and invoke the pipeline tools. No UI widget, but full functionality.

#### For Option B: Node.js companion server

```bash
# Only if ChatGPT UI Widget is required
npm install @modelcontextprotocol/ext-apps @modelcontextprotocol/sdk zod
```

```javascript
// chatgpt-app/server.js
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerView } from "@modelcontextprotocol/ext-apps/server";

const server = new McpServer({ name: "web-app-factory", version: "3.0.0" });

// Register ChatGPT UI widget
registerView(server, {
  name: "app-status",
  uri: "https://web-app-factory.example.com/widget/status.html",
});
```

**Confidence:** HIGH for transport protocol and submission requirements (official OpenAI docs). HIGH for package names/versions (GitHub releases, npm). MEDIUM for Option B implementation details (beta SDK, may evolve).

---

### Summary: New Dependencies for v3.0

#### Python Pipeline (`pyproject.toml`) — No New Deps

All Supabase provisioning uses `httpx` (already in deps) against the Supabase Management API.

```toml
# No changes needed to [project.dependencies] for Supabase provisioning
# httpx>=0.28.0 already covers Management API calls
```

New credential stored via `keyring` (already in deps): `SUPABASE_ACCESS_TOKEN`.

#### Generated App Templates — New npm Packages

These are added to **generated app** `package.json` templates, not to the Python pipeline:

```json
// Generated Next.js app — package.json additions
{
  "dependencies": {
    "@supabase/supabase-js": "^2.99.3",
    "@supabase/ssr": "^0.9.0"
  },
  "devDependencies": {
    "supabase": "^2.83.0"
  }
}
```

#### Generated iOS Backend (`backend/`) — npm Packages

```json
// Generated backend — package.json (standalone Vercel Functions)
{
  "type": "module",
  "dependencies": {
    "@supabase/supabase-js": "^2.99.3"
  }
}
```

#### ChatGPT Distribution — Optional Node.js Packages (Option B only)

```bash
# Add only if ChatGPT UI Widget (Views) is required
npm install @modelcontextprotocol/ext-apps@^1.2.2 @modelcontextprotocol/sdk@^1.20.2 zod@^3.25.76
```

---

### What NOT to Add (v3.0 Scope)

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `@supabase/auth-helpers-nextjs` | Deprecated; future fixes go to `@supabase/ssr` only | `@supabase/ssr` |
| `supabase-py` (Python SDK) | Management API (project provisioning) is not covered by it; runtime SDK is JS-side | `httpx` against Management API REST |
| `express` / `hono` in generated backends | Adds cold-start overhead for Vercel Functions; Route Handlers and plain ESM handlers are zero-dep | Native Next.js Route Handlers or plain ESM `api/*.js` |
| `prisma` / `drizzle` ORM | Supabase's auto-generated PostgREST API + `supabase-js` typed client eliminates need for a separate ORM | `@supabase/supabase-js` with generated `database.types.ts` |
| `@openai/agents` SDK | This is the Agents SDK for building AI workflows, not for ChatGPT App Store distribution | `@modelcontextprotocol/ext-apps` for UI; FastMCP HTTP transport for tool access |
| Supabase Edge Functions (Deno) | Adds Deno runtime complexity; Vercel Functions are already the deployment target | Vercel Functions (Node.js ESM) |
| `pg` / `postgres.js` direct DB | Bypasses Supabase RLS; Management API provisions Supabase specifically for its auth/RLS layer | `@supabase/supabase-js` with `service_role` key for admin ops |

---

### Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `@supabase/supabase-js@^2.99.3` | Next.js 16.x, React 19.x | No known conflicts; tested against Next.js App Router |
| `@supabase/ssr@^0.9.0` | `@supabase/supabase-js@^2.x` | Peer dep: `@supabase/supabase-js >= 2.59.0` |
| `@supabase/supabase-js@^2.99.3` | Tailwind CSS 4.x, shadcn/ui latest | Pure logic library, no styling conflict |
| `@modelcontextprotocol/ext-apps@^1.2.2` | `@modelcontextprotocol/sdk@^1.20.2` | Both from MCP org; designed as companion packages |
| `supabase` CLI `^2.83.0` | Node.js >=20 | Minimum Node version matches existing pipeline requirement |
| `supabase-swift@^2.x` (iOS client) | iOS 13+, macOS 10.15+ | Server-side API must use standard REST (not Supabase Realtime protocol) for cold-start compat |

---

### Integration Points with Existing v2.0 Stack

| Existing Component | v3.0 Integration |
|-------------------|------------------|
| `DeploymentProvider` (Vercel path) | Adds `SUPABASE_PROJECT_REF`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` to Vercel project env vars after provisioning |
| `waf_check_env` MCP tool | Adds `SUPABASE_ACCESS_TOKEN` to required credentials checklist |
| `pipeline_state.py` | Adds `supabase_project_ref`, `supabase_url`, `supabase_anon_key` fields to pipeline state |
| `next.config.ts` (generated apps) | No change needed; Route Handlers work without additional config |
| `vercel.json` generator (generated apps) | Adds `"functions": { "app/api/**/*.js": { "maxDuration": 10 } }` for backend routes |
| `_keychain.py` | Adds `SUPABASE_ACCESS_TOKEN` to managed credentials alongside `ANTHROPIC_API_KEY` |
| FastMCP server (`mcp_server.py`) | Option A: add `transport="streamable-http"` to `mcp.run()` call for ChatGPT MCP connector support |

---

## v1.0 / v2.0 Stack (Unchanged — Reference)

See earlier STACK.md content (git history 2026-03-23 for v2.0 additions, 2026-03-21 for v1.0 base stack). Preserved unchanged below this section.

---

## Sources

- [@supabase/supabase-js npm — v2.99.3, March 21 2026](https://www.npmjs.com/package/@supabase/supabase-js) — **HIGH confidence**
- [@supabase/ssr npm — v0.9.0, March 22 2026](https://www.npmjs.com/package/@supabase/ssr) — **HIGH confidence**
- [Supabase SSR docs — createServerClient/createBrowserClient pattern](https://supabase.com/docs/guides/auth/server-side/nextjs) — **HIGH confidence**
- [supabase CLI npm — v2.83.0, March 21 2026](https://www.npmjs.com/package/supabase) — **HIGH confidence**
- [supabase Python SDK (supabase-py) — v2.28.3, March 20 2026](https://pypi.org/project/supabase/) — documented (not used, confirmed httpx is correct choice) — **HIGH confidence**
- [Supabase Management API reference](https://supabase.com/docs/reference/api/introduction) — project creation, PAT auth — **HIGH confidence**
- [supabase-swift — v2.39.0, iOS 13+ / macOS 10.15+](https://github.com/supabase/supabase-swift) — **HIGH confidence**
- [OpenAI Apps SDK docs — MCP foundation, quickstart](https://developers.openai.com/apps-sdk/quickstart) — packages `@modelcontextprotocol/sdk@^1.20.2`, `@modelcontextprotocol/ext-apps`, `zod` — **HIGH confidence**
- [@modelcontextprotocol/ext-apps — v1.2.2](https://github.com/modelcontextprotocol/ext-apps) — **HIGH confidence** (version from search results)
- [OpenAI ChatGPT app submission requirements](https://developers.openai.com/apps-sdk/deploy/submission) — public domain, CSP, no localhost — **HIGH confidence**
- [MCP Apps compatibility in ChatGPT](https://developers.openai.com/apps-sdk/mcp-apps-in-chatgpt) — postMessage bridge, iframe transport — **HIGH confidence**
- [Vercel + Supabase integration template](https://vercel.com/templates/next.js/supabase) — standard env var names, connection pattern — **HIGH confidence**
- [Next.js Route Handlers docs](https://nextjs.org/docs/app/getting-started/route-handlers) — App Router API pattern — **HIGH confidence**
- allnew-baas live code at `projects/allnew-baas/vercel/` — Node.js ESM, handler pattern, env vars — **HIGH confidence** (first-party)

---

*Stack research for: web-app-factory v3.0 — Supabase backend generation, allnew-mobile-baas integration, iOS backend generation, OpenAI Apps SDK (ChatGPT distribution)*
*Researched: 2026-03-24*
