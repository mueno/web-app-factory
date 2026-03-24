# Project Research Summary

**Project:** web-app-factory
**Domain:** MCP-distributed automated web application generation pipeline (idea → deployed web app)
**Researched:** 2026-03-21 (v1.0) | Updated: 2026-03-23 (v2.0) | Updated: 2026-03-24 (v3.0)
**Confidence:** HIGH (stack, security pitfalls) | MEDIUM (ChatGPT App Store submission, iOS executor design)

---

## Executive Summary

web-app-factory is a mature LLM-orchestrated pipeline that generates and deploys production Next.js web applications from a natural language idea. v1.0 established the five-phase pipeline (spec → scaffold → codegen → test → deploy) with 10 quality gates. v2.0 added MCP App distribution (7 tools, `claude mcp add`), multi-cloud deployment (Vercel, GCP, AWS stub), and local dev server preview. v3.0 promotes four previously deferred capabilities: backend API generation (Vercel Functions), Supabase DB/Auth automated provisioning, iOS backend generation (JSON-only API variant), and ChatGPT distribution via the OpenAI Apps SDK. The core architecture — FastMCP server, `_pipeline_bridge.py`, `contract_pipeline_runner.py`, `PhaseExecutor` ABC, `DeployProvider` ABC — is unchanged and must not be broken by v3.0 work.

The recommended approach for v3.0 is incremental extension of the existing pipeline, not redesign. Supabase provisioning slots into Phase 2a (scaffold + provision together). Backend API generation is a new sub-step in Phase 2b. iOS backend generation is a second contract variant (`pipeline-contract.ios-backend.v1.yaml`) reusing the existing `VercelProvider`. ChatGPT distribution requires a second MCP server entry point (`openai_mcp_server.py`) sharing business logic with the existing `mcp_server.py` via a new `_tool_impls.py` extraction. No new Python pipeline dependencies are needed — `httpx` already covers Supabase Management API calls. New npm packages (`@supabase/supabase-js`, `@supabase/ssr`) go into generated app templates, not the pipeline itself.

The dominant risks for v3.0 are security-layer failures in generated code. Supabase RLS is disabled by default on every new table — CVE-2025-48757 affected 170+ Lovable-generated apps with this exact omission. The `service_role` key (superuser bypass) is routinely misplaced into client-side code by LLMs. Generated API routes commonly lack input validation. These are not theoretical: they are the documented failure modes of every major AI app generator released before WAF. Prevention requires treating security as a phase gate at the point of generation, not a post-hoc audit: every generated SQL table must have RLS + owner policy inline, every generated API route must start with Zod schema validation, and the existing `env-exposure` gate must be extended to scan for Supabase-specific patterns.

---

## Key Findings

### Recommended Stack

**v3.0 additions — Python pipeline: no new deps.** Supabase Management API is called via `httpx` (already in `pyproject.toml`). Generated app templates gain `@supabase/supabase-js@^2.99.3` and `@supabase/ssr@^0.9.0`. The deprecated `@supabase/auth-helpers-nextjs` must not be used. Generated iOS backends follow the allnew-mobile-baas pattern: pure Node.js ESM, `api/*.js` files, `vercel.json` with `maxDuration: 10`, no framework overhead. ChatGPT distribution requires HTTP transport via FastMCP (`transport="streamable-http"`) — zero new packages for Option A (tool access); Option B (ChatGPT UI widget) would add `@modelcontextprotocol/ext-apps@^1.2.2`.

**Core technologies (v1.0 base — unchanged):**
- Python 3.10+ + `uv`: runtime and package manager — `uvx web-app-factory` is the install path
- `claude-agent-sdk 0.1.50` + `fastmcp 3.1.1`: pipeline orchestration + MCP server
- Next.js 16.2 + React 19.2 + TypeScript 5.1 + Tailwind CSS v4 + shadcn/ui: generated app stack
- Vitest 4.x + Playwright 1.58.2: testing in generated apps

**New dependencies (v2.0 — existing):**
- `vercel-cli>=50.0.0`: Python wrapper, bundles Node.js — replaces subprocess-based Vercel invocation
- `aws-cdk-lib>=2.240.0` + `open-next-cdk>=0.1.0`: AWS deployment — optional `[aws]` extra

**New packages for v3.0 (in generated app templates only, not pipeline):**
- `@supabase/supabase-js@^2.99.3`: Supabase DB/Auth/Realtime client
- `@supabase/ssr@^0.9.0`: Cookie-based auth for Next.js App Router SSR
- `supabase@^2.83.0` (devDep): CLI for TypeScript type generation post-generation
- `@supabase/supabase-js@^2.99.3` (iOS backend): standalone Vercel Functions package.json

**Critical constraints:**
- Do NOT use `@supabase/auth-helpers-nextjs` (deprecated)
- Do NOT use `supabase-py` Python SDK for Management API (not covered; use `httpx`)
- Do NOT use Express/Hono in generated backends (cold-start overhead; use native Route Handlers)
- Do NOT use Supabase Edge Functions/Deno (second runtime; Vercel Functions are the target)
- Do NOT use Prisma/Drizzle ORM (Supabase JS client + PostgREST eliminates the need)

### Expected Features

**Must ship — v3.0 core:**
- Supabase project auto-provisioning via Management API (blocks all backend features)
- Email/password auth working on first run (`@supabase/ssr`, protected routes, `middleware.ts`)
- RLS enabled on all generated tables with `WITH CHECK` owner-scoped policy (security gate)
- CRUD API route generation per entity (Next.js Route Handlers, Zod validation, standard error shape)
- Health endpoint (`/api/health`) always generated — matches allnew-baas pattern
- Backend generation phase in pipeline (new Phase 2b sub-step with dedicated gate)
- HTTP transport on WAF MCP server (enables ChatGPT connection)
- Tool annotations on all 7 existing tools (`readOnlyHint`, `destructiveHint`, `openWorldHint`)
- `check_environment` extended for Supabase credentials (`SUPABASE_ACCESS_TOKEN`, `SUPABASE_ORG_ID`)

**Add after core works:**
- Social auth scaffold (Google OAuth — code + README manual steps; NOT automated provisioning)
- iOS backend mode (`app_type="ios-backend"` parameter on `waf_generate_app`)
- OpenAPI spec auto-generated from API routes (secondary deliverable, ios-app-factory handoff)
- ChatGPT UI widget (iframe progress display; esbuild bundle)

**Defer to v4.0:**
- Apple Sign-In full integration (Developer Portal automation not feasible; scaffold only)
- Generated Swift client `APIClient.swift` (requires stable OpenAPI spec first)
- Push notification endpoint (APNs certificate management complexity)
- ChatGPT App Directory submission (reviewer API key problem unsolved)

**Must have — v2.0 (existing, shipped):**
- `waf_generate`/`waf_status`/`waf_approve`/`waf_check_env`/`waf_start_preview`/`waf_stop_preview`/`waf_list_runs` MCP tools
- Dual-mode pipeline (auto vs. interactive), resumable runs, multi-cloud deploy
- Local dev server preview with port detection from stdout

**Must have — v1.0 (existing, shipped):**
- Phase-ordered execution, fail-closed quality gates, `state.json` state persistence, resumability
- Quality self-assessment JSON before every gate submission; gate-gaming prevention
- Responsive design, WCAG 2.1 AA, security headers, legal documents

### Architecture Approach

v3.0 extends the existing layered architecture without restructuring it. The MCP server layer gains a second entry point (`openai_mcp_server.py`) sharing business logic extracted into `_tool_impls.py`. The pipeline bridge gains an `app_type` parameter to select contract variants. Phase 2a gains a `SupabaseProvisioner` sub-step. Phase 2b gains a `generate_api_routes` sub-step. A second contract YAML (`pipeline-contract.ios-backend.v1.yaml`) enables iOS backend mode with phase-specific executors. All existing contracts, gates, and the `DeployProvider` ABC remain unchanged.

**Major components — v3.0 new/modified:**
1. `_tool_impls.py` (NEW) — shared tool business logic extracted from `mcp_server.py`; both servers import from here
2. `openai_mcp_server.py` (NEW) — FastMCP in HTTP mode; ChatGPT entry point; deployed to public HTTPS
3. `SupabaseProvisioner` in `tools/supabase_provisioner.py` (NEW) — Management API: `create_project()`, `run_migration()`, `inject_env()`
4. `templates/backend/` (NEW) — Vercel Functions templates modeled on allnew-baas (`cors.js`, `rate-limit.js`, `auth.js`, `health.js`)
5. `pipeline-contract.ios-backend.v1.yaml` (NEW) — same 5 phases, different executors (no frontend, JSON-only API)
6. Phase 2a executor (MODIFIED) — `provision_supabase` sub-step before scaffold
7. Phase 2b executor (MODIFIED) — `generate_api_routes` sub-step consuming `backend-spec.json` from Phase 1b
8. Phase 1b executor (MODIFIED) — produce `backend-spec.json` alongside `screen-spec.json` when backend requested
9. `supabase_gate.py` (NEW) — verify project created, credentials injected, RLS enabled on all tables

**Invariants that must be preserved:**
- `waf_` tool prefix enforced by CI test
- `start_pipeline_async` returns `run_id` BEFORE thread submission (deadlock prevention)
- `GATE_RESPONSES_DIR` shared constant between mcp_server and mcp_approval_gate
- Pipeline contract YAML is single source of phase definitions and gate conditions
- `PhaseExecutor` ABC — all executors implement `execute(ctx: PhaseContext) -> PhaseResult`
- `DeployProvider` ABC — all providers implement `deploy()`, `get_url()`, `verify()`

### Critical Pitfalls

**Top 5 for v3.0:**

1. **Supabase RLS disabled by default — full data exposure** — Every `CREATE TABLE` must be immediately followed by `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` and a `WITH CHECK (auth.uid() = user_id)` owner policy. Post-generation gate scans every migration file. Test with anon key, not `service_role`. CVE-2025-48757 affected 170+ Lovable-generated apps with this exact omission.

2. **`service_role` key in generated client-side code** — Generate separate `supabase-browser.ts` (anon key) and `supabase-server.ts` (service_role, server-only). Never generate `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY`. Extend the existing `env-exposure` gate to scan for `NEXT_PUBLIC_*SERVICE*ROLE*` patterns.

3. **RLS policy missing `WITH CHECK` — ownership forgery** — INSERT and UPDATE policies require both `USING (auth.uid() = user_id)` AND `WITH CHECK (auth.uid() = user_id)`. USING alone only protects reads. Integration tests must include a cross-user write attempt asserting policy violation.

4. **Generated API routes without input validation — injection risk** — Every generated API route must import Zod and validate all inputs before any DB/filesystem operation. Backend generation gate must scan for routes missing `import { z } from 'zod'`. Code generation prompts must explicitly prohibit string concatenation in query chains.

5. **MCP tool synchronous timeout orphans the pipeline** — The existing three-tool split (`waf_generate` returns `run_id`, `waf_status` polls, `waf_result` fetches) must be preserved. Never make the generate call synchronous. Guard with a job registry to detect and kill orphaned processes.

**Top 5 from v1.0/v2.0 (still critical):**

6. **Gate-gaming — LLM optimizing for gate passage, not quality** — Directly caused the HealthStockBoardV30 incident. Prevention: `45-quality-driven-execution.md` — purpose-first prompts, deliverable manifests, mandatory `quality-self-assessment-{phase}.json`. Never pass raw gate conditions to phase executor prompts.

7. **npm package hallucination ("slopsquatting")** — 19.7% of LLM-generated package references are hallucinations; attackers register phantom names with malware. Prevention: `npm-verify` gate validates each package against npm registry API before `npm install`.

8. **Subprocess injection via user input** — 43% of 2026 MCP CVEs involved command injection. List-form subprocess only, `shlex.quote()` on all user input, strict `^[a-zA-Z0-9_-]{1,50}$` validation. Never `shell=True`.

9. **Next.js ISR/Edge silently breaks on non-Vercel targets** — ISR, Edge Middleware, and `runtime: 'edge'` are unsupported on AWS OpenNext and GCP Cloud Run. Parameterize code generation by deploy target; add pre-deploy compatibility gate.

10. **Prompt injection via app description → deployed code** — Wrap user descriptions in `[USER_DESCRIPTION_START]...[END]` delimiters; scan generated code for exfiltration patterns (unexpected external `fetch()` calls).

---

## Implications for Roadmap

The v3.0 milestone adds 6 implementation phases on top of the shipped v2.0 system. Supabase provisioning is the hard dependency for all three backend feature categories (A, B, C from FEATURES.md). HTTP transport (MCP infrastructure) is a prerequisite for ChatGPT distribution and is independent of backend features. Security gates must be established at the point of generation, not post-hoc.

### Phase 1 (v3.0): MCP Infrastructure Hardening + HTTP Transport

**Rationale:** Two pre-requisites must be in place before any v3.0 feature work: (1) extract shared tool logic into `_tool_impls.py` for the dual-server pattern, (2) add HTTP transport entry point (`openai_mcp_server.py`) for ChatGPT. Security invariants (subprocess injection, `waf_` prefix CI check) must be locked before adding new tools. No user-visible features but unblocks all downstream.

**Delivers:** `_tool_impls.py` refactor, `openai_mcp_server.py` skeleton, HTTP transport functional, all 7 existing tools annotated (`readOnlyHint`/`destructiveHint`/`openWorldHint`), `waf_` prefix CI test extended, subprocess security audit complete.

**Addresses:** FEATURES.md Category D table stakes (tool annotations, HTTP transport). PITFALLS — v2-P1 (synchronous timeout), v2-P2 (tool name collision), v2-P5 (subprocess injection).

**Avoids:** Architectural decisions forcing a rewrite when dual-server is added.

**Research flag:** Standard patterns. FastMCP HTTP transport is documented; refactor pattern is mechanical.

### Phase 2 (v3.0): Supabase Provisioning

**Rationale:** Supabase provisioning is the hard dependency for backend API generation, auth scaffolding, and iOS backend. Nothing in Categories A, B, or C can be built without a provisioned project. This phase also establishes the RLS security baseline preventing the Lovable-class CVE.

**Delivers:** `SupabaseProvisioner` component, Phase 2a `provision_supabase` sub-step, `supabase_gate.py` (RLS verification), `check_environment` extended with Supabase credential checks, `SUPABASE_ACCESS_TOKEN` via keyring, `VERCEL_ENV_ALLOWLIST` extended for Supabase vars.

**Addresses:** FEATURES.md Category B table stakes (auto-provisioning, env var injection, RLS default-on). PITFALLS — v3-P1 (RLS disabled), v3-P2 (service_role exposure).

**Avoids:** Local Docker Supabase (wrong for automated generation), `supabase-py` Python SDK (incorrect for Management API).

**Needs research:** Credential lifecycle — create vs. reuse existing Supabase project on re-runs. ARCHITECTURE.md rates this MEDIUM confidence; design decision needed before implementation.

### Phase 3 (v3.0): Backend API Generation

**Rationale:** With Supabase provisioned, backend generation can proceed. The allnew-baas template library provides known-good patterns (CORS, rate limiting, auth) so the LLM adapts templates rather than hallucinating API patterns from scratch.

**Delivers:** `templates/backend/` directory (allnew-baas pattern), Phase 1b updated to produce `backend-spec.json`, Phase 2b `generate_api_routes` sub-step, `BackendSpecValidator` gate (type-safe handlers, no raw secrets, CORS present, Zod validation in every route), standardized error shape `{ error: string, code: string }`, health endpoint always generated.

**Addresses:** FEATURES.md Category A table stakes (CRUD, TypeScript, input validation, error standardization, allnew-baas fidelity). PITFALLS — v3-P3 (`WITH CHECK` ownership forgery), v3-P4 (no input validation in generated API), v1-P2 (npm hallucination — extend allowlist to backend packages).

**Avoids:** ORM generation (doubles scope), GraphQL (overkill), OpenAPI-first approach (code-first then infer spec).

**Research flag:** Standard patterns. Next.js Route Handlers + Zod + Supabase JS client are well-documented; allnew-baas is first-party reference.

### Phase 4 (v3.0): Supabase Auth Scaffolding

**Rationale:** Auth is a distinct concern from DB provisioning. This phase generates `@supabase/ssr` integration code, protected routes, sign-in/sign-up pages, and OAuth callback. The `SPEC_AGENT` system prompt must be updated to prefer Supabase Auth when Supabase DB is in use (avoid mixing auth providers).

**Delivers:** `createBrowserClient`/`createServerClient` pattern in generated apps, `middleware.ts` with `updateSession()`, `app/auth/` routes (callback, login, logout), `BUILD_AGENT` and `SPEC_AGENT` system prompt updates, `auth` field in `backend-spec.json`.

**Addresses:** FEATURES.md Category B table stakes (email/password on first run, session persistence, protected routes). PITFALLS — v3-P2 (service_role via two-client pattern), v3-P3 (RLS `WITH CHECK` in generated policies), v1-P5 (env var leakage — extended to Supabase patterns).

**Avoids:** Local Docker Supabase, custom JWT/session management, NextAuth/Clerk mixing with Supabase DB.

**Research flag:** HIGH confidence. Official Vercel Supabase template and `@supabase/ssr` docs are comprehensive.

### Phase 5 (v3.0): iOS Backend Generation

**Rationale:** iOS backend is a contract variant, not a new pipeline. The `pipeline-contract.ios-backend.v1.yaml` reuses the existing `VercelProvider` and 5-phase structure with iOS-specific executors (no frontend, JSON-only API, bearer token auth, camelCase responses).

**Delivers:** `pipeline-contract.ios-backend.v1.yaml`, iOS-specific executor variants (1a, 1b, 2a, 2b), `app_type` parameter on `waf_generate_app`, executor registry with contract-type dispatch, OpenAPI spec as secondary deliverable (handoff to ios-app-factory).

**Addresses:** FEATURES.md Category C table stakes (REST from Swift URLSession, bearer token auth, CORS, camelCase JSON, health endpoint, allnew-baas template). PITFALLS — v3-P5 (Apple Sign-In rotation — use `signInWithIdToken` native flow, not OAuth flow), v3-P6 (allnew-baas backward compatibility for LyricsSnap).

**Avoids:** iOS Swift code generation (ios-app-factory's domain), WebSocket push (APNs only), Vapor/Kitura Swift server.

**Needs research:** Executor registry contract-type dispatch (Option A — separate registry per contract — recommended in ARCHITECTURE.md but adds complexity; design spike needed before committing).

### Phase 6 (v3.0): ChatGPT App Store Preparation

**Rationale:** HTTP transport (Phase 1) is the foundation. This phase completes the ChatGPT submission path: deploy `openai_mcp_server.py` to a public HTTPS endpoint, add `structuredContent` returns, prepare privacy policy, and document test credential requirements for App Store review.

**Delivers:** `openai_mcp_server.py` deployed to Vercel/Fly.io, `structuredContent` in tool returns, privacy policy URL, tool annotations verified against submission requirements, reviewer credential documentation (or sandbox mode if feasible).

**Addresses:** FEATURES.md Category D table stakes (MCP compatibility, tool parity, annotations, privacy policy). PITFALLS — v2-P3 (manifest spec volatility), v3-P7 (ChatGPT iframe `postMessage` origin bypass — use `@modelcontextprotocol/ext-apps` App Bridge).

**Avoids:** ChatGPT-only features breaking Claude parity, instant checkout (prohibited for digital products).

**Needs research:** Reviewer API key problem. WAF requires `ANTHROPIC_API_KEY` to function but App Store reviewers cannot be expected to provide their own. Demo/sandbox mode design is needed. MEDIUM confidence on feasibility; no documented solution exists in research.

### Phase Ordering Rationale (v3.0)

- **MCP infrastructure first** — dual-server pattern and security invariants locked before adding new tools
- **Supabase provisioning second** — hard dependency for all three backend feature categories (A, B, C)
- **Auth after provisioning, before iOS** — iOS backend requires Supabase Auth for JWT validation
- **iOS backend after web backend** — contract variant design validated against web backend before adding second variant
- **ChatGPT last** — transport layer is independent of features; submission readiness depends on all features being stable

### Research Flags (v3.0)

Phases needing deeper research during planning:
- **Phase 2 (Supabase Provisioning):** Credential lifecycle — create vs. reuse project on re-runs; MEDIUM confidence
- **Phase 5 (iOS Backend):** Executor registry contract-type dispatch — Option A adds complexity; design spike needed
- **Phase 6 (ChatGPT Submission):** Reviewer API key problem — no documented solution; sandbox mode design required

Standard patterns, skip research:
- **Phase 3 (Backend API Generation):** allnew-baas is first-party reference; Next.js Route Handlers + Zod well-documented
- **Phase 4 (Auth Scaffolding):** Official Vercel Supabase template + `@supabase/ssr` docs are comprehensive; HIGH confidence
- **Phase 1 (MCP Infrastructure):** Refactor is mechanical; FastMCP HTTP transport is documented

---

## Previous Milestones Reference

### v1.0 Phases (shipped)

Phase 1: Infrastructure Fork — YAML contract runner, state management, governance monitor, dual-implementation integration test.
Phase 2: YAML Contract Design — 5-phase contract with deliverable manifests, `quality_criteria` arrays, gate-gaming prevention.
Phase 3: Spec Agent (Phases 1a + 1b) — idea validation, PRD, screen spec, quality self-assessments.
Phase 4: Scaffold + Build Agents (Phases 2a + 2b) — npm-verify gate, static analysis for `"use client"` boundary and `NEXT_PUBLIC_` exposure, `next build` production gate.
Phase 5: Quality Gates + Deploy — Lighthouse, axe-core, security headers, legal documents, deploy gate.

### v2.0 Phases (shipped)

Phase 6: MCP Infrastructure Foundation — `web_app_factory/` package, `_pipeline_bridge.py`, `waf_` prefix convention, input validation utilities.
Phase 7: Deploy Abstraction Layer — `DeployProvider` ABC, `VercelProvider` extraction, `GCPProvider`, `AWSProvider` stub, target capability matrix.
Phase 8: Local Dev Server — `server_manager.py`, port detection from stdout, PID registry, SIGINT/SIGTERM cleanup.
Phase 9: MCP Tool Layer — all 7 `waf_*` tools, interactive vs auto mode, `resume_run_id` support.
Phase 10: Environment Detection and Distribution — `waf_check_env` structured gap report, `.mcp.json`, PyPI publish CI.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All packages verified on npm/GitHub as of March 21-22, 2026; allnew-baas is first-party code; no new Python pipeline deps required |
| Features | HIGH (web + Supabase) / MEDIUM (ChatGPT App Store) | Web backend and Supabase features are well-scoped; ChatGPT reviewer credential problem is unresolved |
| Architecture | HIGH (existing) / MEDIUM (new components) | Existing architecture fully documented; `SupabaseProvisioner` and contract variant dispatch are designed but not yet validated in code |
| Pitfalls | HIGH (security) / MEDIUM (allnew-baas migration) | Security pitfalls backed by CVE corpus and official Supabase docs; allnew-baas integration scope needs scoping in Phase 5 planning |

**Overall confidence:** HIGH for must-ship features. MEDIUM for ChatGPT App Store submission feasibility and iOS backend executor complexity.

### Gaps to Address

- **Supabase project lifecycle:** Create vs. reuse on re-runs. Design decision needed before Phase 2 implementation.
- **ChatGPT reviewer credentials:** WAF requires `ANTHROPIC_API_KEY`; App Store review requires working demo. Sandbox mode or reviewer account approach needed; no documented solution.
- **allnew-baas backward compatibility:** Phase 5 iOS backend templates based on allnew-baas patterns must not break LyricsSnap (existing iOS app using live allnew-baas). Explicit compatibility layer needed.
- **`backend-spec.json` schema definition:** Versioned JSON schema needed before Phase 1b (producer) and Phase 2b (consumer) are implemented. Schema drift is a known failure mode (v2-Pitfall 11).
- **`open-next-cdk` Python version (v2.0 gap, still open):** MEDIUM confidence on compatibility. Run minimal integration test before committing AWS provider. Fallback: ship Vercel + GCP only.
- **Build-agent prompt templates (v1.0 gap, still open):** Exact prompt language reliably preventing `"use client"` misplacement and npm hallucination needs empirical iteration.

---

## Sources

### Primary (HIGH confidence)
- `@supabase/supabase-js` npm v2.99.3, `@supabase/ssr` npm v0.9.0, `supabase` CLI npm v2.83.0 — March 21-22, 2026
- Supabase SSR docs (createServerClient/createBrowserClient pattern) — official docs, March 2026
- Supabase Management API reference (project creation, PAT auth) — official docs
- Next.js Route Handlers docs (App Router API pattern) — official docs, March 2026
- `projects/allnew-baas/vercel/` — first-party live code (allnew-mobile-baas pattern)
- OpenAI Apps SDK docs (MCP foundation, transport, submission requirements) — developer.openai.com
- `@modelcontextprotocol/ext-apps@^1.2.2`, `@modelcontextprotocol/sdk@^1.20.2` — GitHub/npm releases
- CVE-2025-48757 (Supabase RLS mass exposure, Lovable) — CVE corpus, March 2026
- OWASP LLM Top 10 + academic studies on LLM-generated code vulnerabilities — security research
- FastMCP docs (gofastmcp.com) — HTTP transport, background tasks, MCP server lifecycle
- Claude Code MCP docs — stdio transport, uvx install pattern
- MCP Security 2026 — 30 CVEs in 60 days corpus (command injection 43%, path traversal 82%)
- OpenNext AWS comparison table — ISR/Edge/PPR feature parity gaps
- `ios-app-factory/` codebase — governance monitor, contract runner, MCP server patterns
- Next.js 16 release blog, CVE-2025-29927 (CVSS 9.1), CVE-2025-66478 (CVSS 10.0)

### Secondary (MEDIUM confidence)
- Supabase Management API provisioning flow — documented but credential lifecycle edge cases unclear
- iOS backend executor registry design (Option A vs B) — architectural recommendation without code validation
- ChatGPT App Store submission specifics — some requirements documented as MEDIUM in ARCHITECTURE.md
- `open-next-cdk` Python version pinning — needs implementation-time validation
- FastMCP `task=True` background task — marked experimental in docs; fallback pattern documented

### Tertiary (LOW confidence)
- ChatGPT App Directory listing requirements for tools requiring user API keys — needs direct validation with OpenAI during Phase 6 planning
- `@modelcontextprotocol/ext-apps` Option B implementation details — beta SDK, may evolve
- MCP App manifest spec `0.1` — explicitly pre-stable; field names may change

---

*Research completed: 2026-03-24 (v3.0 update)*
*Covers: v1.0 pipeline, v2.0 MCP distribution, v3.0 backend generation + Supabase + iOS backend + ChatGPT distribution*
*Ready for roadmap: yes*
