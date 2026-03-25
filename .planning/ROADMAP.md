# Roadmap: Web App Factory

## Overview

Web App Factory transforms a natural-language app idea into a deployed, production-quality Next.js web application. Distributed as an MCP App installable via `claude mcp add`, it orchestrates specialized Claude agents through quality-gated phases to produce shippable web apps with multi-cloud deployment.

## Milestones

- ✅ **v1.0 Core Pipeline** — Phases 1-7 (shipped 2026-03-22)
- ✅ **v2.0 MCP Apps** — Phases 8-15 (shipped 2026-03-24)
- 🔄 **v3.0 Full Stack** — Phases 16-21 (active)

## Phases

<details>
<summary>✅ v1.0 Core Pipeline (Phases 1-7) — SHIPPED 2026-03-22</summary>

- [x] Phase 1: Infrastructure (4/4 plans) — completed 2026-03-21
- [x] Phase 2: Spec (3/3 plans) — completed 2026-03-21
- [x] Phase 3: Build (3/3 plans) — completed 2026-03-21
- [x] Phase 4: Ship (3/3 plans) — completed 2026-03-21
- [x] Phase 5: Build Pipeline Fix (1/1 plan) — completed 2026-03-21
- [x] Phase 6: Contract Alignment (1/1 plan) — completed 2026-03-21
- [x] Phase 7: Ship Directory Fix (1/1 plan) — completed 2026-03-22

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v2.0 MCP Apps (Phases 8-15) — SHIPPED 2026-03-24</summary>

- [x] Phase 8: MCP Infrastructure Foundation (3/3 plans) — completed 2026-03-23
- [x] Phase 9: Deploy Abstraction (3/3 plans) — completed 2026-03-23
- [x] Phase 10: Local Dev Server (2/2 plans) — completed 2026-03-23
- [x] Phase 11: MCP Tool Layer (0/0 plans, cross-phase) — completed 2026-03-24
- [x] Phase 12: Environment Detection + Distribution (2/2 plans) — completed 2026-03-24
- [x] Phase 13: Pipeline Quality (2/2 plans) — completed 2026-03-24
- [x] Phase 14: Wire Interactive Gate Approval (2/2 plans) — completed 2026-03-24
- [x] Phase 15: Declare Playwright Dependency (1/1 plan) — completed 2026-03-24

Full details: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)

</details>

### v3.0 Full Stack (Phases 16-21) — Active

- [x] **Phase 16: MCP Infrastructure Hardening** — Extract shared tool logic, add HTTP transport, annotate all tools for OpenAI Apps SDK (completed 2026-03-24)
- [x] **Phase 17: Supabase Provisioning** — Auto-provision Supabase project via Management API with RLS-default security baseline (completed 2026-03-24)
- [ ] **Phase 18: Backend API Generation** — Generate Next.js Route Handlers from backend-spec.json with Zod validation and SQL injection prevention
- [ ] **Phase 19: Supabase Auth Scaffolding** — Generate @supabase/ssr auth integration, protected routes, and sign-in/sign-up pages
- [ ] **Phase 20: iOS Backend Generation** — Add ios-backend contract variant, executor registry dispatch, and OpenAPI spec output
- [ ] **Phase 21: OpenAI Apps Distribution** — Deploy public HTTPS endpoint, add structuredContent returns, and prepare ChatGPT App Store submission

## Phase Details

### Phase 16: MCP Infrastructure Hardening
**Goal**: The MCP server has a clean dual-entry-point architecture (stdio + HTTP) with all tools annotated and security invariants locked before any new tools are added
**Depends on**: Nothing (first v3.0 phase — builds on shipped v2.0)
**Requirements**: MCPH-01, MCPH-02, MCPH-03, MCPH-04
**Success Criteria** (what must be TRUE):
  1. A ChatGPT client can connect to the WAF MCP server over HTTPS and call all 7 existing waf_* tools
  2. Both stdio and HTTP servers invoke identical business logic — a fix in one place fixes both
  3. All 7 tools have readOnlyHint, destructiveHint, and openWorldHint annotations visible in tool manifests
  4. CI fails if any tool registration in either server lacks the waf_ prefix
**Plans:** 2/2 plans complete
Plans:
- [x] 16-01-PLAN.md — Extract shared impl logic to _tool_impls.py and annotate stdio server
- [x] 16-02-PLAN.md — Create HTTP transport server and extend CI prefix enforcement

### Phase 17: Supabase Provisioning
**Goal**: Running `waf_generate_app` with a Supabase-enabled spec automatically provisions a live Supabase project with RLS enforced on every table — no manual Supabase setup required
**Depends on**: Phase 16
**Requirements**: SUPA-01, SUPA-02, SUPA-03, SUPA-04, SUPA-05, SUPA-06, SECG-01, SECG-02
**Success Criteria** (what must be TRUE):
  1. After pipeline completion, a Supabase project exists in ACTIVE_HEALTHY state with the generated schema applied
  2. Generated migration SQL contains ENABLE ROW LEVEL SECURITY and WITH CHECK (auth.uid() = user_id) on every table — the supabase_gate.py fails if any table is missing this
  3. waf_check_env reports missing SUPABASE_ACCESS_TOKEN and SUPABASE_ORG_ID with actionable remediation steps
  4. Supabase credentials are read from OS keychain — the value is never logged or written to any file
  5. Generated apps have supabase-browser.ts (anon key only) and supabase-server.ts (service_role, server-only) as separate files — NEXT_PUBLIC_*SERVICE*ROLE* patterns cause the env-exposure gate to fail
**Plans:** 4/4 plans complete
Plans:
- [ ] 17-01-PLAN.md — Refactor _keychain.py to banto-first credential management and extend waf_check_env
- [ ] 17-02-PLAN.md — Create dual Supabase client TypeScript templates and SECG-01 service_role gate
- [ ] 17-03-PLAN.md — Build SupabaseProvisioner, migration SQL generator, and supabase_gate.py
- [ ] 17-04-PLAN.md — Wire provisioner and templates into Phase 3 executor pipeline

### Phase 18: Backend API Generation
**Goal**: Every generated app with a backend spec has fully functional Next.js Route Handlers with Zod input validation, standardized error responses, and a health endpoint — with a gate that rejects any route missing validation or containing SQL injection patterns
**Depends on**: Phase 17
**Requirements**: BGEN-01, BGEN-02, BGEN-03, BGEN-04, BGEN-05, BGEN-06, BGEN-07, SECG-03
**Success Criteria** (what must be TRUE):
  1. Phase 1b produces both screen-spec.json and backend-spec.json (entities, relationships, endpoints) as separate deliverables
  2. Every generated API route starts with a Zod schema import and validates all inputs before any database operation — the BackendSpecValidator gate rejects routes without this
  3. All generated error responses have the shape { error: string, code: string } — no naked Error objects or raw exception messages
  4. GET /api/health always returns 200 with a valid response body in every generated app
  5. The BackendSpecValidator gate catches string concatenation in query chains and fails the build before deployment
**Plans:** 1/3 plans executed
Plans:
- [ ] 18-01-PLAN.md — Create BackendSpecValidator gate and backend TypeScript templates
- [ ] 18-02-PLAN.md — Extend Phase 1b to produce backend-spec.json with cross-validation
- [ ] 18-03-PLAN.md — Add generate_api_routes sub-step to Phase 2b and wire gate into pipeline

### Phase 19: Supabase Auth Scaffolding
**Goal**: Generated apps have complete email/password authentication working on first run — users can sign up, sign in, stay logged in across sessions, and are redirected to login when accessing protected routes without a session
**Depends on**: Phase 17 (needs provisioned Supabase project), Phase 18 (auth integrated into backend spec)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06
**Success Criteria** (what must be TRUE):
  1. A user can create an account with email/password, sign in, and have their session persist across page reloads using cookie-based auth
  2. Accessing a protected route without a session redirects to the login page — the server component performs this check, not the client
  3. Generated app has /auth/login, /auth/signup, and /auth/signout pages under the app/auth/ directory
  4. middleware.ts calls updateSession() on every request — session tokens are automatically refreshed without user action
  5. SPEC_AGENT and BUILD_AGENT system prompts produce Supabase Auth when Supabase DB is in use — no mixing of auth providers
**Plans**: TBD

### Phase 20: iOS Backend Generation
**Goal**: Running `waf_generate_app` with app_type="ios-backend" generates a standalone Vercel Functions API (no Next.js app) that an iOS client can consume via bearer token auth — without breaking existing allnew-baas deployments used by LyricsSnap
**Depends on**: Phase 19 (iOS backend inherits auth patterns from web auth phase)
**Requirements**: IOSB-01, IOSB-02, IOSB-03, IOSB-04, IOSB-05, IOSB-06, IOSB-07
**Success Criteria** (what must be TRUE):
  1. waf_generate_app accepts app_type="ios-backend" and selects the ios-backend contract variant — the default web behavior is unchanged
  2. Generated output is api/*.js Vercel Functions with no Next.js framework — structure matches allnew-baas
  3. Every generated endpoint accepts and validates a Bearer token, returns camelCase JSON, and has CORS headers permitting iOS client origins
  4. An OpenAPI spec file is generated alongside the API routes and can be handed off to ios-app-factory
  5. Deploying the generated ios-backend template to allnew-baas does not break the existing LyricsSnap endpoints
**Plans**: TBD

### Phase 21: OpenAI Apps Distribution
**Goal**: WAF is listed and functional in the ChatGPT App Store — a ChatGPT user can install WAF, call waf_generate_app, and see pipeline progress in a UI widget — and a pre-submission checklist gate catches any annotation or policy gaps before submission
**Depends on**: Phase 16 (HTTP transport), Phase 18 (stable tool set to annotate)
**Requirements**: OAPI-01, OAPI-02, OAPI-03, OAPI-04, OAPI-05, SECG-04
**Success Criteria** (what must be TRUE):
  1. openai_mcp_server.py is deployed to a public HTTPS endpoint and the ChatGPT App Store connection test passes
  2. Tool returns include structuredContent — ChatGPT narrates pipeline progress rather than displaying raw JSON
  3. A privacy policy URL is served from the deployed endpoint and resolves to human-readable text
  4. The pre-submission checklist gate fails if any tool is missing required annotations or if the privacy policy URL returns non-200
  5. The ChatGPT UI Widget displays real-time pipeline progress — a user can see which phase is running without calling waf_status manually
  6. Cross-user write tests are generated for every RLS-protected table — the test asserts a policy violation error when attempting to write another user's data
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure | v1.0 | 4/4 | Complete | 2026-03-21 |
| 2. Spec | v1.0 | 3/3 | Complete | 2026-03-21 |
| 3. Build | v1.0 | 3/3 | Complete | 2026-03-21 |
| 4. Ship | v1.0 | 3/3 | Complete | 2026-03-21 |
| 5. Build Pipeline Fix | v1.0 | 1/1 | Complete | 2026-03-21 |
| 6. Contract Alignment | v1.0 | 1/1 | Complete | 2026-03-21 |
| 7. Ship Directory Fix | v1.0 | 1/1 | Complete | 2026-03-22 |
| 8. MCP Infrastructure Foundation | v2.0 | 3/3 | Complete | 2026-03-23 |
| 9. Deploy Abstraction | v2.0 | 3/3 | Complete | 2026-03-23 |
| 10. Local Dev Server | v2.0 | 2/2 | Complete | 2026-03-23 |
| 11. MCP Tool Layer | v2.0 | 0/0 | Complete | 2026-03-24 |
| 12. Environment Detection + Distribution | v2.0 | 2/2 | Complete | 2026-03-24 |
| 13. Pipeline Quality | v2.0 | 2/2 | Complete | 2026-03-24 |
| 14. Wire Interactive Gate Approval | v2.0 | 2/2 | Complete | 2026-03-24 |
| 15. Declare Playwright Dependency | v2.0 | 1/1 | Complete | 2026-03-24 |
| 16. MCP Infrastructure Hardening | v3.0 | 2/2 | Complete | 2026-03-24 |
| 17. Supabase Provisioning | v3.0 | 4/4 | Complete | 2026-03-24 |
| 18. Backend API Generation | 1/3 | In Progress|  | - |
| 19. Supabase Auth Scaffolding | v3.0 | 0/? | Not started | - |
| 20. iOS Backend Generation | v3.0 | 0/? | Not started | - |
| 21. OpenAI Apps Distribution | v3.0 | 0/? | Not started | - |
