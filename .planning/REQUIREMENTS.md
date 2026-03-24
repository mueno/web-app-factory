# Requirements: Web App Factory

**Defined:** 2026-03-24
**Core Value:** A single command takes a web app idea from concept to deployed, production-quality web application — now with full-stack backend, database, and authentication

## v3.0 Requirements

Requirements for Full Stack milestone. Each maps to roadmap phases.

### MCP Infrastructure

- [x] **MCPH-01**: Tool logic extracted to `_tool_impls.py` — both stdio and HTTP servers share identical business logic
- [ ] **MCPH-02**: HTTP transport entry point (`openai_mcp_server.py`) serves all 7 existing `waf_*` tools over HTTPS
- [x] **MCPH-03**: All 7 existing tools annotated with `readOnlyHint`, `destructiveHint`, `openWorldHint` per OpenAI Apps SDK spec
- [ ] **MCPH-04**: `waf_` prefix CI assertion extended to cover both stdio and HTTP server tool registrations

### Supabase Provisioning

- [ ] **SUPA-01**: `SupabaseProvisioner` creates a Supabase project via Management API and polls until `ACTIVE_HEALTHY`
- [ ] **SUPA-02**: Generated migration SQL has RLS enabled on every table with `WITH CHECK (auth.uid() = user_id)` owner policy
- [ ] **SUPA-03**: `supabase_gate.py` verifies: project created, credentials injected into Vercel env, RLS enabled on all tables
- [ ] **SUPA-04**: `waf_check_env` extended to detect `SUPABASE_ACCESS_TOKEN` and `SUPABASE_ORG_ID` presence
- [ ] **SUPA-05**: Supabase credentials (`SUPABASE_ACCESS_TOKEN`) stored and retrieved via OS keychain (same as v2.0 pattern)
- [ ] **SUPA-06**: Dual Supabase client pattern generated: `supabase-browser.ts` (anon key) and `supabase-server.ts` (service_role, server-only)

### Backend API Generation

- [ ] **BGEN-01**: Phase 1b produces `backend-spec.json` (entities, relationships, endpoints) alongside `screen-spec.json`
- [ ] **BGEN-02**: Phase 2b `generate_api_routes` sub-step creates Next.js Route Handlers from `backend-spec.json`
- [ ] **BGEN-03**: Every generated API route includes Zod input validation — no route without schema validation
- [ ] **BGEN-04**: Standardized error response shape `{ error: string, code: string }` in all generated routes
- [ ] **BGEN-05**: Health endpoint (`GET /api/health`) always generated — matches allnew-baas pattern
- [ ] **BGEN-06**: `BackendSpecValidator` gate scans generated routes for missing Zod imports, raw secrets, and unvalidated inputs
- [ ] **BGEN-07**: `templates/backend/` directory extracted from allnew-baas patterns (CORS, rate-limit, auth helpers)

### Supabase Auth

- [ ] **AUTH-01**: Generated apps include `@supabase/ssr` with `createBrowserClient` / `createServerClient` pattern
- [ ] **AUTH-02**: `middleware.ts` with `updateSession()` generated for cookie-based auth in Next.js App Router
- [ ] **AUTH-03**: Sign-in / sign-up / sign-out pages generated under `app/auth/`
- [ ] **AUTH-04**: Protected route pattern generated — server component checks session, redirects to login if absent
- [ ] **AUTH-05**: Google OAuth scaffold generated with code + README manual steps (not automated provisioning)
- [ ] **AUTH-06**: `SPEC_AGENT` and `BUILD_AGENT` system prompts updated to prefer Supabase Auth when Supabase DB is in use

### iOS Backend

- [ ] **IOSB-01**: `app_type` parameter on `waf_generate_app` — accepts `"web"` (default) or `"ios-backend"`
- [ ] **IOSB-02**: `pipeline-contract.ios-backend.v1.yaml` — same 5 phases, iOS-specific executors (no frontend, JSON-only API)
- [ ] **IOSB-03**: iOS backend generates standalone Vercel Functions (`api/*.js`) — no Next.js app, matches allnew-baas structure
- [ ] **IOSB-04**: Generated API returns camelCase JSON, includes bearer token auth middleware, CORS configured for iOS clients
- [ ] **IOSB-05**: OpenAPI spec auto-generated from API routes as secondary deliverable (handoff to ios-app-factory)
- [ ] **IOSB-06**: allnew-baas existing endpoints preserved as backward-compatible template — LyricsSnap must not break
- [ ] **IOSB-07**: Executor registry supports contract-type dispatch — `(phase_id, contract_type)` selects correct executor

### OpenAI Apps Distribution

- [ ] **OAPI-01**: `openai_mcp_server.py` deployed to public HTTPS endpoint (Vercel or Fly.io)
- [ ] **OAPI-02**: Tool returns include `structuredContent` for ChatGPT model narration
- [ ] **OAPI-03**: Privacy policy URL served from deployed endpoint
- [ ] **OAPI-04**: Pre-submission checklist gate validates tool annotations, privacy policy, and demo credentials
- [ ] **OAPI-05**: ChatGPT UI Widget displays pipeline progress (iframe + esbuild bundle)

### Security Gates (Generated Code)

- [ ] **SECG-01**: Env exposure gate extended to scan for `NEXT_PUBLIC_*SERVICE*ROLE*` patterns (Supabase service_role leak)
- [ ] **SECG-02**: RLS gate scans every migration file — rejects if any `CREATE TABLE` lacks immediate `ENABLE ROW LEVEL SECURITY`
- [ ] **SECG-03**: Backend route gate scans for string concatenation in query chains (SQL injection prevention)
- [ ] **SECG-04**: Cross-user write test generated for every RLS-protected table (policy violation assertion)

## v4.0 Requirements

Deferred to future release.

### Cloud Providers
- **CLOUD-01**: AWS CDK full implementation (open-next-cdk) with Lambda/CloudFront
- **CLOUD-02**: Azure Static Web Apps support
- **CLOUD-03**: Cloudflare Pages support

### Advanced Features
- **ADV-01**: Apple Sign-In full integration (Developer Portal automation)
- **ADV-02**: Generated Swift client `APIClient.swift` (requires stable OpenAPI spec)
- **ADV-03**: Multi-framework support (Vue/Nuxt, Svelte)
- **ADV-04**: Push notification endpoint (APNs certificate management)
- **ADV-05**: ChatGPT App Directory formal submission (reviewer API key problem)

## Out of Scope

| Feature | Reason |
|---------|--------|
| iOS/Swift code generation | Handled by ios-app-factory |
| Apple Sign-In full automation | Developer Portal `.p8` key requires manual steps; scaffold only in v3 |
| Prisma/Drizzle ORM | Supabase JS client + PostgREST eliminates need |
| Express/Hono framework in backends | Cold-start overhead; native Route Handlers preferred |
| Supabase Edge Functions (Deno) | Second runtime; Vercel Functions are the target |
| GraphQL | REST sufficient for generated apps; GraphQL doubles scope |
| Custom domain / DNS | Platform subdomain sufficient |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MCPH-01 | Phase 16 | Complete |
| MCPH-02 | Phase 16 | Pending |
| MCPH-03 | Phase 16 | Complete |
| MCPH-04 | Phase 16 | Pending |
| SUPA-01 | Phase 17 | Pending |
| SUPA-02 | Phase 17 | Pending |
| SUPA-03 | Phase 17 | Pending |
| SUPA-04 | Phase 17 | Pending |
| SUPA-05 | Phase 17 | Pending |
| SUPA-06 | Phase 17 | Pending |
| SECG-01 | Phase 17 | Pending |
| SECG-02 | Phase 17 | Pending |
| BGEN-01 | Phase 18 | Pending |
| BGEN-02 | Phase 18 | Pending |
| BGEN-03 | Phase 18 | Pending |
| BGEN-04 | Phase 18 | Pending |
| BGEN-05 | Phase 18 | Pending |
| BGEN-06 | Phase 18 | Pending |
| BGEN-07 | Phase 18 | Pending |
| SECG-03 | Phase 18 | Pending |
| AUTH-01 | Phase 19 | Pending |
| AUTH-02 | Phase 19 | Pending |
| AUTH-03 | Phase 19 | Pending |
| AUTH-04 | Phase 19 | Pending |
| AUTH-05 | Phase 19 | Pending |
| AUTH-06 | Phase 19 | Pending |
| IOSB-01 | Phase 20 | Pending |
| IOSB-02 | Phase 20 | Pending |
| IOSB-03 | Phase 20 | Pending |
| IOSB-04 | Phase 20 | Pending |
| IOSB-05 | Phase 20 | Pending |
| IOSB-06 | Phase 20 | Pending |
| IOSB-07 | Phase 20 | Pending |
| OAPI-01 | Phase 21 | Pending |
| OAPI-02 | Phase 21 | Pending |
| OAPI-03 | Phase 21 | Pending |
| OAPI-04 | Phase 21 | Pending |
| OAPI-05 | Phase 21 | Pending |
| SECG-04 | Phase 21 | Pending |

**Coverage:**
- v3.0 requirements: 39 total
- Mapped to phases: 39
- Unmapped: 0

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 after roadmap creation — all 39 requirements mapped*
