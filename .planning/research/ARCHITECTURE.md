# Architecture Research: v3.0 Feature Integration

**Domain:** Backend generation, Supabase provisioning, iOS backend templates, OpenAI Apps SDK integration into existing MCP pipeline
**Researched:** 2026-03-24
**Confidence:** HIGH (existing codebase analysis, OpenAI Apps SDK docs), MEDIUM (Supabase Management API flow, iOS template patterns), LOW (ChatGPT App Store submission specifics)

---

## Context: Existing v2.0 Architecture (What Must Not Break)

```
┌────────────────────────────────────────────────────────────┐
│  User-Facing Layer (MCP App — stdio transport)             │
│  web_app_factory/mcp_server.py (FastMCP 3.x)               │
│  7 tools: waf_generate_app, waf_get_status, waf_approve_gate│
│           waf_list_runs, waf_start_dev_server, waf_stop_dev │
│           waf_check_env                                     │
└────────────────────┬───────────────────────────────────────┘
                     │ start_pipeline_async (ThreadPoolExecutor)
┌────────────────────▼───────────────────────────────────────┐
│  Bridge Layer                                               │
│  web_app_factory/_pipeline_bridge.py                        │
│  ThreadPoolExecutor (3 workers), run_id registry            │
└────────────────────┬───────────────────────────────────────┘
                     │ run_pipeline(idea, project_dir, **opts)
┌────────────────────▼───────────────────────────────────────┐
│  Pipeline Core                                              │
│  tools/contract_pipeline_runner.py                          │
│  PHASE_ORDER: 1a → 1b → 2a → 2b → 3                        │
│  YAML contract: contracts/pipeline-contract.web.v1.yaml     │
└──────┬─────────────────────────────────┬────────────────────┘
       │ phase dispatch                  │ gate evaluation
┌──────▼────────────────┐  ┌────────────▼───────────────────┐
│  Phase Executors       │  │  Quality Gates (10)             │
│  phase_1a_executor    │  │  build, static_analysis,        │
│  phase_1b_executor    │  │  lighthouse, a11y, security,    │
│  phase_2a_executor    │  │  link_integrity, legal,         │
│  phase_2b_executor    │  │  deployment, mcp_approval,      │
│  phase_3_executor     │  │  e2e (Playwright)               │
└──────┬────────────────┘  └────────────────────────────────┘
       │ agent calls
┌──────▼────────────────────────────────────────────────────┐
│  Agents (Claude Agent SDK)                                 │
│  spec_agent, build_agent, deploy_agent                     │
└───────────────────┬───────────────────────────────────────┘
                    │
┌───────────────────▼───────────────────────────────────────┐
│  Deploy Providers (ABC pattern)                            │
│  VercelProvider, GCPProvider, AWSProvider, LocalProvider   │
└───────────────────────────────────────────────────────────┘
```

**Key invariants that must be preserved:**
- `waf_` tool prefix enforced by CI test (`tests/test_mcp_server_tool_names.py`)
- `start_pipeline_async` returns `run_id` BEFORE thread submission (deadlock prevention)
- `GATE_RESPONSES_DIR` shared constant between writer (mcp_server) and reader (mcp_approval_gate)
- Pipeline contract YAML is the single source of phase definitions and gate conditions
- `PhaseExecutor` ABC — all executors implement `execute(ctx: PhaseContext) -> PhaseResult`
- `DeployProvider` ABC — all providers implement `deploy()`, `get_url()`, `verify()`

---

## New Features and Integration Analysis

### Feature 1: Backend API Generation (REST endpoints)

**What it is:** The pipeline generates Vercel Functions (Node.js ES modules) as backend API alongside the Next.js frontend. The allnew-mobile-baas codebase is the reference implementation.

**allnew-baas code pattern:**
```
projects/allnew-baas/vercel/
├── api/
│   ├── health.js             # GET /api/health — liveness probe
│   └── gemini/
│       └── live-token.js     # POST /api/gemini/live-token — token issuance
└── vercel.json               # Function config: maxDuration=10, Cache-Control headers
```

Each function is a named ESM export `default async function handler(req, res)` — standard Vercel Functions pattern. The functions include: rate limiting (in-memory Map), CORS headers with allowlist, shared secret authentication, JSON error utilities.

**Integration point: Phase 1b (Spec and Design)**

The spec agent system prompt must be updated to optionally produce a `backend-spec.json` alongside `screen-spec.json`. The backend spec defines:
- API routes (path, method, auth requirements)
- Request/response schemas per route
- Auth provider (Supabase JWT, shared secret, API key)
- Supabase tables required (names, columns, types)

**Integration point: Phase 2b (Code Generation)**

A new `phase_2b_backend_subagent` or sub-step within the existing Phase 2b executor generates API routes under `src/app/api/` (Next.js App Router route handlers) or a separate `api/` directory for standalone Vercel Functions. The build agent system prompt needs a backend generation section.

**New component: `BackendSpecValidator` gate** — verifies generated API routes have type-safe request/response handlers, no raw secrets in code, CORS headers present.

**Confidence:** HIGH — this follows the established allnew-baas pattern and fits cleanly into Phase 2b's sub-step decomposition.

---

### Feature 2: Supabase DB Provisioning

**What it is:** The pipeline programmatically creates a Supabase project (PostgreSQL + Realtime + Auth) using the Supabase Management API, injects the connection credentials into the generated app's environment.

**Supabase Management API flow:**

```
POST https://api.supabase.com/v1/projects
Authorization: Bearer <SUPABASE_ACCESS_TOKEN>
Body: { name, organization_id, db_pass, region, plan }

Response: { id, ref, api_url, anon_key, service_role_key }
```

The `ref` value is the project identifier used to construct:
- Project URL: `https://<ref>.supabase.co`
- API URL: `https://<ref>.supabase.co/rest/v1`
- Auth URL: `https://<ref>.supabase.co/auth/v1`
- Realtime URL: `wss://<ref>.supabase.co/realtime/v1`

After project creation, tables are provisioned via SQL through the Management API (`POST /v1/projects/{ref}/database/query`) or by generating a `supabase/migrations/` directory that Supabase CLI applies.

**Integration point: New Phase 2a sub-step or new Phase "2c"**

Option A (preferred): Add a sub-step to Phase 2a (`phase_2a_executor.py`) called `provision_supabase`. Phase 2a currently handles scaffolding. Adding Supabase provisioning here keeps the "scaffold + provision" concerns together before code generation in Phase 2b.

Option B: New Phase 2c executor (`phase_2c_executor.py`) — only needed if Supabase provisioning becomes complex enough to warrant its own phase with separate gates. Prefer Option A initially.

**New component: `SupabaseProvisioner`**

```
tools/
└── supabase_provisioner.py   # Management API client: create_project(), run_migration(), get_credentials()
```

Responsibilities:
- `create_project(name, org_id, region)` — calls Management API, returns `SupabaseCredentials`
- `run_migration(ref, sql)` — executes DDL via Management API database query endpoint
- `get_credentials(ref)` — fetches anon_key and service_role_key
- `inject_env(project_dir, creds)` — writes `.env.local` with `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`

**Credential storage:**

`SUPABASE_ACCESS_TOKEN` (user's personal access token) stored via the existing `_keychain.py` / env-var fallback pattern. Never logged. The `VERCEL_ENV_ALLOWLIST` in `vercel_provider.py` must be extended to include Supabase env vars.

**New gate: `supabase_provisioning_gate`** — verifies project was created, `.env.local` exists, migration SQL ran successfully.

**Confidence:** MEDIUM — Management API is documented but credential lifecycle (when to create vs reuse an existing project) needs design decisions.

---

### Feature 3: Supabase Auth Scaffolding

**What it is:** The build agent generates Supabase Auth integration code: `@supabase/ssr` setup, OAuth callback route handler, middleware for session refresh, sign-in pages for Apple/Google/Email.

**Pattern (from Supabase official docs):**
```
src/
├── lib/
│   ├── supabase/
│   │   ├── client.ts    # createBrowserClient() — "use client" components
│   │   └── server.ts    # createServerClient() — Server Components, Route Handlers
├── app/
│   ├── auth/
│   │   ├── callback/
│   │   │   └── route.ts   # GET /auth/callback — exchanges code for session
│   │   ├── login/
│   │   │   └── page.tsx   # Sign-in UI
│   │   └── logout/
│   │       └── route.ts   # POST /auth/logout
│   └── middleware.ts       # Session refresh on every request
```

**Integration point: Build agent system prompt update**

The BUILD_AGENT system prompt in `agents/definitions.py` needs a `## Supabase Auth (when auth is required)` section specifying:
- Use `@supabase/ssr` not `@supabase/auth-helpers-nextjs` (deprecated)
- `supabase.auth.getUser()` in server components for session validation (never `getSession()`)
- OAuth providers configured via Supabase dashboard (Apple requires Service ID + key)
- Callback route pattern and PKCE flow requirement

**Integration point: Spec agent system prompt update**

SPEC_AGENT already mentions `NextAuth.js or Clerk` as auth options in its stack context. This must be updated to include `Supabase Auth` as the preferred option when Supabase DB is also being used (avoid mixing auth providers).

**No new executor needed** — auth scaffolding is part of Phase 2b code generation. The `backend-spec.json` produced in Phase 1b should include an `auth` field specifying which providers are required.

**Confidence:** HIGH — Supabase + Next.js App Router auth is well-documented with SSR package.

---

### Feature 4: allnew-mobile-baas Integration

**What it is:** The `projects/allnew-baas/vercel/` codebase becomes a template source for WAF-generated backends. When a user requests an iOS-compatible backend, WAF copies and adapts the allnew-baas API structure.

**allnew-baas key patterns to extract:**
- `setCorsHeaders()` with allowlist — iOS apps need explicit CORS origin allowlisting
- `isRateLimited()` in-memory Map — basic rate limiting without Redis (acceptable for starter projects)
- `resolveAppId()` from header or payload — mobile app identification pattern
- `BAAS_CLIENT_SHARED_SECRET` authentication — pre-shared key suitable for iOS app → server
- `vercel.json` function config — `maxDuration: 10`, `Cache-Control: no-store`

**New component: Backend templates directory**

```
web_app_factory/
└── templates/
    └── backend/
        ├── vercel-functions/
        │   ├── api/
        │   │   ├── health.js         # Liveness probe template
        │   │   └── _shared/
        │   │       ├── cors.js       # setCorsHeaders() helper
        │   │       ├── rate-limit.js # isRateLimited() helper
        │   │       └── auth.js       # resolveAppId(), isAllowedApp() helpers
        │   └── vercel.json           # Function config template
        └── supabase/
            ├── schema.sql            # Base tables template
            └── auth.sql              # Auth triggers template
```

**Integration point: Template-driven code generation**

Phase 2b builds a prompt that references these templates. The build agent copies and customizes the templates based on `backend-spec.json`. This avoids the agent hallucinating API patterns from scratch.

**Confidence:** MEDIUM — template extraction is straightforward. The question is whether to use file-based templates or embed them as strings in the agent system prompt. File-based templates are more maintainable.

---

### Feature 5: iOS Backend Generation

**What it is:** When `waf_generate_app` receives `target: "ios-backend"` (or a similar parameter), the pipeline generates a REST API designed to serve iOS clients rather than a web frontend. The output is a deployable Vercel Functions project with no Next.js frontend.

**Key differences from web app generation:**

| Aspect | Web App | iOS Backend |
|--------|---------|-------------|
| Output | Next.js app + API routes | Vercel Functions only (no frontend) |
| Auth | Supabase Auth (JWT, OAuth) | Supabase Auth + Apple Sign-In callback + APNS token |
| CORS | Same-origin preferred | iOS app bundle ID origin |
| Response format | HTML pages + JSON APIs | JSON-only APIs |
| Dev server | `next dev` | `vercel dev` |

**Integration point: New `waf_generate_app` parameter**

Add `app_type: str = "web"` parameter to `waf_generate_app` MCP tool. Valid values: `"web"` (default), `"ios-backend"`, `"fullstack"` (web + backend). The `app_type` is passed through the bridge to `run_pipeline()` and then to the `PhaseContext`.

**Integration point: New contract variant**

A new `pipeline-contract.ios-backend.v1.yaml` with phases:
- Phase 1a: iOS app validation (instead of web app validation)
- Phase 1b: API spec (instead of screen spec — no UI)
- Phase 2a: Scaffold Vercel Functions project (instead of Next.js scaffold)
- Phase 2b: Generate API routes from spec
- Phase 3: Deploy to Vercel (reuse existing VercelProvider)

The existing `pipeline-contract.web.v1.yaml` is unchanged. The `_pipeline_bridge.py` selects the contract based on `app_type`.

**New phase executors: iOS backend variants**

Since the phase *IDs* remain the same (1a, 1b, 2a, 2b, 3), the executor registry needs a way to dispatch by both phase ID and contract type. Options:

Option A: Separate executor registry per contract — `get_executor(phase_id, contract_type)`. Adds `contract_type` parameter to `PhaseContext`.

Option B: Single executors with `app_type` branching — existing executors check `ctx.app_type` and call different sub-routines. Simpler but muddies separation.

Recommendation: Option A — matches the existing pattern of "one executor per phase", extends cleanly, avoids `if app_type == "ios"` branching in every executor.

**Confidence:** MEDIUM — contract-per-app-type is the right pattern but adds executor registry complexity.

---

### Feature 6: OpenAI Apps SDK Support (ChatGPT Distribution)

**What it is:** The web-app-factory MCP server is additionally distributed as a ChatGPT App via the OpenAI Apps SDK. This requires a fundamentally different transport: HTTP/HTTPS instead of stdio.

**Critical architecture difference:**

| Aspect | Claude (current) | ChatGPT (new) |
|--------|-----------------|----------------|
| Transport | stdio (stdin/stdout) | Streamable HTTP (HTTPS POST to `/mcp`) |
| Install method | `claude mcp add web-app-factory -- uvx web-app-factory` | ChatGPT connector: paste HTTPS URL |
| Auth | None (process isolation) | Developer-implemented (API key, OAuth) |
| UI components | N/A (text only) | HTML widgets in ChatGPT iframe (`mcp-app` MIME type) |
| Tool returns | `content` only | `structuredContent` (model), `content` (text), `_meta` (UI widget) |
| Hosting | Local process via uvx | Remote HTTPS server (Vercel, Fly.io, etc.) |

**New component: `openai_mcp_server.py`**

A second FastMCP server instance running in HTTP mode, exposing the same logical tools as `mcp_server.py` but with:
1. HTTP transport: `mcp.run(transport="http", host="0.0.0.0", port=8000)`
2. Auth middleware: verify `X-API-Key` header or OAuth token before dispatching
3. `structuredContent` in tool returns (for ChatGPT model narration)
4. Registered HTML resource for ChatGPT UI widget (optional, but enables richer UX)

```python
# web_app_factory/openai_mcp_server.py
from fastmcp import FastMCP

mcp_chatgpt = FastMCP(
    "web-app-factory-chatgpt",
    instructions="...",
)

# Same tools, different return format
@mcp_chatgpt.tool()
async def waf_generate_app(...) -> dict:
    result = await _run_generate(...)  # shared impl
    return {
        "structuredContent": {"run_id": result.run_id, "status": "started"},
        "content": [{"type": "text", "text": result.plan_markdown}],
    }
```

**Shared implementation pattern:**

Both `mcp_server.py` (stdio) and `openai_mcp_server.py` (HTTP) import from a shared `web_app_factory/_tool_impls.py` module that contains the actual logic. The server files are thin adapters with transport-specific return formatting.

```
web_app_factory/
├── mcp_server.py           # Claude: stdio transport, content-only returns
├── openai_mcp_server.py    # ChatGPT: HTTP transport, structuredContent returns
├── _tool_impls.py          # NEW: shared business logic for all tools
├── _pipeline_bridge.py     # Unchanged: async bridge to pipeline
└── ...
```

**New pyproject.toml entry point:**

```toml
[project.scripts]
web-app-factory-mcp = "web_app_factory.mcp_server:main"          # Claude (existing)
web-app-factory-openai = "web_app_factory.openai_mcp_server:main" # ChatGPT (new)
```

**ChatGPT App Store submission requirements:**

- HTTPS endpoint (deploy `openai_mcp_server.py` to Vercel/Fly.io/etc.)
- Organization verification in OpenAI Platform Dashboard (Owner role required)
- App metadata: name, logo, description, company, privacy policy URL
- MCP server tool annotations: `readOnly`, `destructive`, `openWorld` flags per tool
- Test prompts with expected responses (reviewed by OpenAI manually)
- Active MCP server during review (cannot be localhost)

**Key insight:** The OpenAI Apps SDK mandates HTTP transport with a public HTTPS URL. The Claude distribution uses local stdio. These are two separate server entry points, not one server with dual transport. They share implementation via `_tool_impls.py` but are deployed differently.

**Confidence:** HIGH — OpenAI Apps SDK docs are clear on transport, auth, and submission. FastMCP 3.x supports both transports with separate `run()` calls.

---

## System Overview: v3.0 Target Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Distribution Layer                                               │
│  ┌──────────────────────────┐  ┌──────────────────────────────┐  │
│  │  Claude (stdio)          │  │  ChatGPT (HTTPS)             │  │
│  │  mcp_server.py           │  │  openai_mcp_server.py        │  │
│  │  `claude mcp add ...`    │  │  Deployed to Vercel/Fly.io   │  │
│  │  Local process (uvx)     │  │  ChatGPT App Store           │  │
│  └──────────┬───────────────┘  └──────────────┬───────────────┘  │
│             └──────────────┬──────────────────┘                  │
│                   ┌────────▼────────┐                            │
│                   │  _tool_impls.py │  (NEW — shared logic)      │
│                   └────────┬────────┘                            │
└────────────────────────────┼────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Bridge + Pipeline Core (UNCHANGED)                              │
│  _pipeline_bridge.py → contract_pipeline_runner → phases 1a→3   │
└──────────────────────┬──────────────────────────────────────────┘
                       │ PhaseContext.app_type dispatch
            ┌──────────┴──────────────────────┐
            ▼                                 ▼
┌─────────────────────────┐    ┌──────────────────────────────┐
│  Web Contract            │    │  iOS Backend Contract        │
│  pipeline-contract.web   │    │  pipeline-contract.ios-      │
│  .v1.yaml                │    │  backend.v1.yaml (NEW)       │
│  Phases 1a→1b→2a→2b→3   │    │  Phases 1a→1b→2a→2b→3       │
│  (web executors)         │    │  (ios-backend executors)     │
└──────────┬──────────────┘    └──────────────────────────────┘
           │
     ┌─────▼──────────────────────────────────────────────────┐
     │  Phase 2a: Scaffold + Supabase Provision (MODIFIED)    │
     │  + SupabaseProvisioner.create_project()                │
     │  + SupabaseProvisioner.run_migration()                 │
     │  + inject credentials to .env.local                   │
     └─────┬──────────────────────────────────────────────────┘
           │
     ┌─────▼──────────────────────────────────────────────────┐
     │  Phase 2b: Code Gen — web + backend (MODIFIED)         │
     │  Sub-steps:                                            │
     │    generate_shared_components (existing)               │
     │    generate_pages (existing)                           │
     │    generate_integration (existing)                     │
     │    generate_api_routes (NEW — backend-spec.json)       │
     │    validate_packages (existing)                        │
     └─────┬──────────────────────────────────────────────────┘
           │
     ┌─────▼──────────────────────────────────────────────────┐
     │  Deploy Providers (EXTENDED)                           │
     │  VercelProvider: add SUPABASE_* to env allowlist       │
     └────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Status | Responsibility | Communicates With |
|-----------|--------|----------------|-------------------|
| `mcp_server.py` | EXISTING — no change to tools | Claude stdio entry point | `_tool_impls.py` (refactor target) |
| `openai_mcp_server.py` | NEW | ChatGPT HTTP entry point | `_tool_impls.py` |
| `_tool_impls.py` | NEW (refactor) | Shared tool business logic | `_pipeline_bridge.py`, `_dev_server.py`, `_env_checker.py` |
| `_pipeline_bridge.py` | EXISTING — add `app_type` param | Async bridge, run_id registry | `contract_pipeline_runner` |
| `SupabaseProvisioner` | NEW | Supabase Management API client | Phase 2a executor |
| `supabase_gate.py` | NEW | Verify project created, creds injected | Phase 2a executor |
| `templates/backend/` | NEW | Vercel Functions template files | Phase 2b build agent (prompt context) |
| `pipeline-contract.ios-backend.v1.yaml` | NEW | iOS backend phase/gate definitions | `contract_pipeline_runner` |
| Phase 2a executor | MODIFIED | Add Supabase provisioning sub-step | `SupabaseProvisioner` |
| Phase 2b executor | MODIFIED | Add backend generation sub-step | build agent, `templates/backend/` |
| Phase 1b executor | MODIFIED | Produce `backend-spec.json` when backend requested | spec agent |
| `agents/definitions.py` | MODIFIED | Update BUILD_AGENT + SPEC_AGENT system prompts | Phase executors |
| `config/settings.py` | MODIFIED | Add `SUPABASE_*` constants | `SupabaseProvisioner`, `vercel_provider.py` |
| `vercel_provider.py` | MODIFIED | Extend env allowlist for Supabase vars | Phase 3 executor |

---

## Data Flow Changes

### New data flow: Backend-enabled app generation

```
waf_generate_app(idea, app_type="fullstack")
    ↓
_tool_impls.generate_app_impl()
    ↓
_pipeline_bridge.start_pipeline_async(app_type="fullstack")
    ↓
contract_pipeline_runner selects pipeline-contract.web.v1.yaml
    ↓
Phase 1a: idea validation (unchanged)
    ↓
Phase 1b: spec + design
    ↓ produces: prd.md, screen-spec.json, backend-spec.json (NEW)
    ↓
Phase 2a: scaffold + provision
    ↓
    ├─ Next.js scaffold (existing)
    └─ SupabaseProvisioner.create_project() → .env.local (NEW)
    ↓
Phase 2b: code generation
    ↓
    ├─ generate_shared_components (existing)
    ├─ generate_pages (existing)
    ├─ generate_integration (existing)
    └─ generate_api_routes from backend-spec.json (NEW)
    ↓
Phase 3: deploy
    ↓
    ├─ vercel deploy (existing — now with SUPABASE_* env vars injected)
    ├─ legal gate (existing)
    ├─ lighthouse gate (existing)
    └─ mcp approval gate (existing)
```

### New data flow: iOS backend generation

```
waf_generate_app(idea, app_type="ios-backend")
    ↓
_pipeline_bridge.start_pipeline_async(app_type="ios-backend")
    ↓
contract_pipeline_runner selects pipeline-contract.ios-backend.v1.yaml
    ↓
Phase 1a: iOS API validation (NEW contract, NEW executor)
Phase 1b: API spec only — backend-spec.json, no screen-spec.json (NEW executor)
Phase 2a: Vercel Functions scaffold + Supabase provision (NEW executor)
Phase 2b: Generate API routes from backend-spec.json (NEW executor — no frontend gen)
Phase 3: Deploy to Vercel (REUSE existing VercelProvider — no change needed)
```

### New data flow: ChatGPT App Store

```
openai_mcp_server.py running on HTTPS endpoint (Vercel/Fly.io)
    ↓ POST /mcp
ChatGPT sends tool call: waf_generate_app
    ↓
_tool_impls.generate_app_impl() — same as Claude path
    ↓
Returns structuredContent + content (ChatGPT-specific format)
    ↓
User receives: run_id + execution plan in ChatGPT conversation
    ↓
ChatGPT calls waf_get_status(run_id) to poll progress
```

---

## Build Order (Dependency-Ordered)

The following order respects inter-component dependencies. Each phase can start only after its prerequisites are complete.

### Phase A: Foundation — Tool Impl Refactor (no new features, zero regressions)

1. Extract `_tool_impls.py` from `mcp_server.py` — move all business logic out of the @mcp.tool() handlers into standalone async functions. `mcp_server.py` becomes a thin routing layer.
2. Update tests to import from `_tool_impls.py` — no behavior changes.
3. CI must stay green throughout.

**Why first:** All other features depend on shared logic being in `_tool_impls.py`. OpenAI server cannot be built without it.

### Phase B: OpenAI MCP Server (HTTP transport, no backend features yet)

1. Build `openai_mcp_server.py` — wraps `_tool_impls.py` with HTTP transport and ChatGPT return format.
2. Add `web-app-factory-openai` pyproject.toml entry point.
3. Add auth middleware (API key verification).
4. Write E2E test: start server in HTTP mode, send POST to `/mcp`, verify tool response.

**Why second:** Validates the dual-server architecture before adding complexity. Can be tested locally with ngrok.

### Phase C: Backend Spec in Phase 1b

1. Update SPEC_AGENT system prompt to produce `backend-spec.json` when backend is requested.
2. Update Phase 1b executor to optionally output `backend-spec.json`.
3. Update Phase 1b gate in `pipeline-contract.web.v1.yaml` to conditionally require `backend-spec.json` when `app_type != "web"`.
4. Update `screen-spec.json` schema to reference backend endpoints.

**Why third:** `backend-spec.json` is consumed by both Phase 2a (Supabase provisioning) and Phase 2b (API route generation). Both depend on this output.

### Phase D: Supabase Provisioner

1. Build `tools/supabase_provisioner.py` — Management API client.
2. Add `SUPABASE_ACCESS_TOKEN` to `_keychain.py` / `_env_checker.py`.
3. Add `SUPABASE_*` constants to `config/settings.py`.
4. Extend `VERCEL_ENV_ALLOWLIST` in `vercel_provider.py`.
5. Build `tools/gates/supabase_gate.py`.
6. Add Supabase provisioning sub-step to Phase 2a executor.

**Why fourth:** Supabase credentials are needed by Phase 2b to generate correct API client code. Provisioning must run before code gen.

### Phase E: Backend Code Generation (Phase 2b extension)

1. Create `web_app_factory/templates/backend/` with extracted allnew-baas templates.
2. Update BUILD_AGENT system prompt with backend generation section.
3. Add `generate_api_routes` sub-step to Phase 2b executor.
4. Add `BackendSpecValidator` gate or extend existing `build_gate.py`.

**Why fifth:** Depends on Phase C (`backend-spec.json`) and Phase D (Supabase credentials in `.env.local`).

### Phase F: iOS Backend Contract + Executors

1. Create `pipeline-contract.ios-backend.v1.yaml`.
2. Add `app_type` parameter to `PhaseContext` and `_pipeline_bridge.start_pipeline_async`.
3. Add `app_type` to `waf_generate_app` tool in `_tool_impls.py`.
4. Create iOS backend phase executors (1a, 1b, 2a, 2b — reuse Phase 3 unchanged).
5. Update executor registry to dispatch by `(phase_id, contract_type)`.

**Why last:** Depends on all backend infrastructure (Phases C, D, E) being proven in the web fullstack path first. iOS backend is a variant, not a different technology.

---

## Architectural Patterns

### Pattern 1: Dual Transport, Shared Logic

**What:** Two FastMCP server entry points (stdio for Claude, HTTP for ChatGPT) that import shared tool implementation functions from `_tool_impls.py`.

**When to use:** When the same pipeline must be distributed across two different AI platforms with incompatible transport protocols.

**Trade-offs:**
- Pro: Zero duplication of business logic; fixing one fixes both
- Pro: Independently deployable (Claude via uvx local, ChatGPT via HTTPS server)
- Con: Two server processes to maintain and test
- Con: HTTP server requires external hosting (Vercel/Fly.io) and HTTPS

**Example:**
```python
# _tool_impls.py
async def generate_app_impl(idea: str, mode: str, ...) -> AppGenResult: ...

# mcp_server.py (stdio — Claude)
@mcp.tool()
async def waf_generate_app(idea: str, ...) -> str:
    result = await generate_app_impl(idea, ...)
    return result.plan_markdown  # plain text for Claude

# openai_mcp_server.py (HTTP — ChatGPT)
@mcp_chatgpt.tool()
async def waf_generate_app(idea: str, ...) -> dict:
    result = await generate_app_impl(idea, ...)
    return {"structuredContent": {...}, "content": [...]}  # ChatGPT format
```

### Pattern 2: Contract-Per-App-Type

**What:** Separate YAML contract files per app type (`web`, `ios-backend`), selected by `contract_pipeline_runner` based on `app_type` in `PhaseContext`.

**When to use:** When two app types share the same phase ID namespace but have different deliverables, gates, and executor behavior.

**Trade-offs:**
- Pro: Clear separation — iOS backend contract doesn't inherit web app gates
- Pro: Existing web contract is untouched, no risk of regression
- Con: Duplicate phase structure in YAML (can be mitigated with YAML anchors)
- Con: Two sets of phase executors to maintain

### Pattern 3: Sub-Step Decomposition (Existing Pattern — Extended)

**What:** Complex phases are broken into named sub-steps with checkpoint resume support. Phase 2b already uses this (5 sub-steps). Phase 2a extends this for Supabase provisioning.

**When to use:** When a phase has multiple atomic operations that can fail independently, and partial progress should be resumable.

**Trade-offs:**
- Pro: Checkpoint resume prevents re-running expensive operations (API calls, deployments)
- Pro: Each sub-step has a clear success/fail boundary
- Con: Adds complexity to `PhaseResult` (resume_point field)

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Single Server, Dual Transport

**What people do:** Try to run `mcp.run()` twice with different transports in the same FastMCP instance, or add an HTTP endpoint to the existing stdio server.

**Why it's wrong:** FastMCP 3.x does not support simultaneous stdio + HTTP from one instance. Each `run()` call is blocking. The Claude and ChatGPT distributions have fundamentally different deployment models — Claude runs locally via uvx, ChatGPT requires a public HTTPS server. Conflating them in one server creates a deployment impossibility.

**Do this instead:** Two separate server files (`mcp_server.py` and `openai_mcp_server.py`), shared logic via `_tool_impls.py`.

### Anti-Pattern 2: Supabase Credentials in Generated App Code

**What people do:** Hardcode the Supabase `service_role_key` in generated API routes or commit `.env.local` to git.

**Why it's wrong:** `service_role_key` bypasses Row Level Security — it is a full-access database credential. Exposing it in client-side code or version control is a critical security vulnerability.

**Do this instead:** Inject credentials via `.env.local` (gitignored). `NEXT_PUBLIC_SUPABASE_ANON_KEY` is safe for browser use (RLS enforced). `SUPABASE_SERVICE_ROLE_KEY` goes only in server-side environment variables.

### Anti-Pattern 3: Modifying the Existing Web Contract for iOS Backend

**What people do:** Add optional fields to `pipeline-contract.web.v1.yaml` to accommodate both web and iOS backend use cases.

**Why it's wrong:** Optional fields in a fail-closed contract create ambiguity about what constitutes a passing gate. The web contract's gates reference `screen-spec.json` (which iOS backend doesn't produce). Mixing the two creates conditional gate logic that is hard to reason about and test.

**Do this instead:** Separate YAML contract per app type.

### Anti-Pattern 4: Inlining allnew-baas Code in Agent Prompts

**What people do:** Copy the full `live-token.js` source into the BUILD_AGENT system prompt as a "template to follow".

**Why it's wrong:** Agent system prompts with large code blocks increase token cost and reduce prompt effectiveness. The agent may copy the template verbatim rather than adapting it.

**Do this instead:** File-based templates in `web_app_factory/templates/backend/`. The prompt references the template's *pattern* (authentication shape, error handling convention) rather than including the full source. The Phase 2b executor reads the template file and injects only the relevant pattern description into the agent's context.

---

## Integration Points: External Services

| Service | Integration Pattern | New Component | Notes |
|---------|---------------------|---------------|-------|
| Supabase Management API | REST calls from `SupabaseProvisioner` | `tools/supabase_provisioner.py` | Personal access token or OAuth2; project creation is async (poll until active) |
| Supabase Auth (generated app) | `@supabase/ssr` package in generated Next.js | Templates + BUILD_AGENT prompt | Apple Sign-In requires ASC Service ID; out of WAF scope |
| OpenAI Apps SDK / ChatGPT | HTTP MCP server on public HTTPS | `openai_mcp_server.py` + deployment config | Must be always-on during ChatGPT review |
| Vercel (extended) | Existing VercelProvider + env var injection | Extend `_VERCEL_ENV_ALLOWLIST` | No structural change to provider |

---

## Sources

- Existing codebase analysis: `web_app_factory/mcp_server.py`, `_pipeline_bridge.py`, `tools/contract_pipeline_runner.py`, `agents/definitions.py`, `tools/deploy_providers/base.py`, `tools/deploy_providers/vercel_provider.py`, `tools/phase_executors/phase_2b_executor.py`, `tools/phase_executors/phase_3_executor.py`
- allnew-baas reference: `projects/allnew-baas/vercel/api/gemini/live-token.js`, `vercel.json`
- [OpenAI Apps SDK: Build MCP Server](https://developers.openai.com/apps-sdk/build/mcp-server) — HTTP transport requirement, authentication pattern (MEDIUM confidence — docs current)
- [OpenAI Apps SDK: MCP Apps in ChatGPT](https://developers.openai.com/apps-sdk/mcp-apps-in-chatgpt) — MCP Apps open standard for embedded UIs (MEDIUM confidence)
- [OpenAI Apps SDK: Submit and Maintain Your App](https://developers.openai.com/apps-sdk/deploy/submission) — Submission requirements, review process (MEDIUM confidence — process may evolve)
- [Supabase Management API: Create a Project](https://supabase.com/docs/reference/api/create-a-project) — Programmatic project provisioning (HIGH confidence — official docs)
- [Supabase: Setting up Server-Side Auth for Next.js](https://supabase.com/docs/guides/auth/server-side/nextjs) — `@supabase/ssr` package, App Router pattern (HIGH confidence — official docs)
- [FastMCP: Running Your Server](https://gofastmcp.com/deployment/running-server) — HTTP transport, `/mcp` endpoint path, single transport per run() (HIGH confidence — official FastMCP docs)
- [Next.js: Building APIs](https://nextjs.org/blog/building-apis-with-nextjs) — Route Handler pattern for iOS-compatible REST APIs (HIGH confidence — official Next.js)

---

*Architecture research for: v3.0 full stack — backend generation, Supabase, iOS backend, OpenAI Apps SDK*
*Researched: 2026-03-24*
