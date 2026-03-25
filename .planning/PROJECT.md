# Web App Factory

## What This Is

An automated web application development pipeline that transforms a user's app idea into a production-ready, deployed web application. Distributed as an MCP App, users install it via `claude mcp add` and generate web apps through natural conversation with Claude. The system orchestrates specialized Claude agents through quality-gated phases to produce shippable web apps.

## Core Value

A single command takes a web app idea from concept to deployed, production-quality web application — with market validation, UX design, implementation, testing, legal compliance, and deployment handled automatically.

## Current Milestone: v3.0 Full Stack

**Goal:** Add backend generation (REST API + Supabase DB + Auth), integrate allnew-mobile-baas, support iOS app backends, and distribute to both Claude and ChatGPT via OpenAI Apps SDK.

**Target features:**
- Backend API generation from natural language (Vercel Functions + Supabase)
- DB provisioning (Supabase PostgreSQL + Realtime)
- Authentication scaffolding (Supabase Auth — Apple/Google/Email)
- allnew-mobile-baas integration as WAF backend template
- iOS app backend generation (server-side API for iOS clients)
- OpenAI Apps SDK full support (ChatGPT UI Widget + App Store submission)
- Dual distribution: Claude MCP + ChatGPT App Store

## Current State

v2.0 shipped 2026-03-24. Web-app-factory is now a distributable MCP App.

**Shipped capabilities:**
- MCP App packaging (`claude mcp add web-app-factory -- uvx web-app-factory`)
- 7 MCP tools exposing full pipeline (generate, status, approve, list, env check, dev server start/stop)
- Dual mode: full-auto + interactive (phase-by-phase gate confirmation)
- Environment detection with platform-aware install guidance
- Local dev server for preview before deploy
- Multi-cloud deployment (Vercel, GCP Cloud Run, AWS stub, LocalOnly)

## Requirements

### Validated

- ✓ Pipeline orchestration (factory.py, contract_pipeline_runner, pipeline_state) — v1.0
- ✓ Web-adapted phase contract (YAML) with 5 phases — v1.0
- ✓ Web-specific phase executors (1a, 1b, 2a, 2b, 3) — v1.0
- ✓ Web-specialized agents (spec-agent, build-agent, deploy-agent) — v1.0
- ✓ 10 quality gates (build, static analysis, lighthouse, a11y, security, link integrity, legal, deployment, mcp approval, quality assessment) — v1.0
- ✓ Vercel deployment automation — v1.0
- ✓ State persistence and resumption — v1.0
- ✓ Governance monitoring and runtime guards — v1.0
- ✓ CLI entry point — v1.0
- ✓ FLOW-01 form-page parameter consistency gate — v1.0 post-fix

- ✓ MCP App packaging (installable via `claude mcp add`) — v2.0
- ✓ 7 MCP tools (generate, status, approve, list, check env, dev server start/stop) — v2.0
- ✓ Dual mode: full-auto + interactive gate approval — v2.0
- ✓ Environment detection and setup assistance — v2.0
- ✓ Local dev server for preview — v2.0
- ✓ Multi-cloud deploy abstraction (Vercel, GCP, AWS stub, LocalOnly) — v2.0
- ✓ Phase 2b three-sub-step decomposition with checkpoint resume — v2.0
- ✓ E2E Playwright form flow gate — v2.0

- ✓ Backend API generation (REST endpoints from backend-spec.json → Next.js Route Handlers) — v3.0 Phase 18
- ✓ Supabase DB provisioning (PostgreSQL + Realtime) — v3.0 Phase 17
- ✓ Supabase Auth scaffolding (Passkey + Google/Apple OAuth, protected routes, middleware session refresh) — v3.0 Phase 19

### Active
- [ ] allnew-mobile-baas integration into WAF
- [ ] iOS backend generation (server-side API for iOS apps)
- [ ] OpenAI Apps SDK support (ChatGPT distribution)
- [ ] ChatGPT UI Widget / components
- [ ] OpenAI App Store submission & review compliance

### Out of Scope

- iOS/Swift code generation — handled by ios-app-factory
- App Store submission — web apps deploy to web hosting
- Custom domain / DNS management — platform subdomain sufficient
- ~~Backend database provisioning~~ — **promoted to v3.0 Active** (Supabase)
- Payment processing integration — too complex for automated generation
- AWS CDK full implementation — deferred to v4.0 (Vercel prioritized for backend)
- Azure Static Web Apps / Cloudflare Pages — deferred to v4.0

## Context

- v1.0 shipped 2026-03-22: 7 phases, 16 plans, 447+ tests, 36/36 requirements
- v2.0 shipped 2026-03-24: 8 phases, 16 plans, 88 commits, 27/27 requirements
- Total: 15 phases, 31 plans shipped across 2 milestones
- allnew-mobile-baas: 稼働中 Vercel Functions (Gemini Live トークン発行)、projects/allnew-baas/vercel/ に存在
- OpenAI Apps SDK: MCP ベース、ChatGPT App Store 審査あり
- BL-003 (Phase 1b data flow schema in screen-spec.json) remains open
- Tech stack: Python 3.10+, FastMCP 3.x, Claude Agent SDK, Next.js (generated apps)
- New tech: Supabase (DB + Auth + Realtime), OpenAI Apps SDK

## Constraints

- **Tech stack (pipeline)**: Python 3.10+, Claude Agent SDK, MCP SDK — latest versions
- **Tech stack (generated apps)**: Next.js (React) as default framework
- **Distribution**: Must work with `claude mcp add` (Anthropic MCP Apps standard)
- **API key**: Users provide their own ANTHROPIC_API_KEY
- **Local-first**: Generated apps must run locally before any cloud deployment
- **Multi-cloud**: Deploy abstraction layer — not Vercel-only

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fork rather than extend ios-app-factory | Different phase content, gates, deployment targets | ✓ Good |
| Next.js as default generated framework | Most popular React framework, good DX | ✓ Good |
| Vercel as primary deploy target (v1) | Zero-config, preview deployments | ✓ Good — expanding to multi-cloud in v2 |
| Coarse phase structure (5 phases) | Leaner than iOS pipeline | ✓ Good |
| FLOW-01 form-page contract gate | Prevent cross-component parameter mismatches | ✓ Good — caught real bug |
| MCP App distribution (v2) | Users install via `claude mcp add`, no manual setup | ✓ Phase 8 |
| Local-first development (v2) | Preview before deploy, no cloud dependency for iteration | ✓ Phase 10 |
| Multi-cloud deploy (v2) | User choice: Vercel, AWS, GCP | ✓ Phase 9 |
| FastMCP 3.x for public server (v2) | `from fastmcp import FastMCP` canonical import; `list_tools()` for introspection | ✓ Phase 8 |
| waf_ prefix enforced in CI (v2) | Static assertion prevents tool name collisions between public/internal servers | ✓ Phase 8 |
| ThreadPoolExecutor async bridge (v2) | run_id returned before executor submission to prevent queue-full blocking | ✓ Phase 8 |
| keyring + env-var fallback (v2) | Credential values never logged; graceful degradation in headless/CI | ✓ Phase 8 |
| GATE_RESPONSES_DIR shared constant (v2) | Single source of truth for gate-response path; closes BREAK-02 writer/reader mismatch | ✓ Phase 14 |
| Interactive gate polling via file (v2) | _poll_mcp_gate_file blocks worker thread until gate file appears; gate file consumed after read | ✓ Phase 14 |
| interactive_mode wired bridge→runner→gate (v2) | Closes BREAK-01 — mode='interactive' no longer silently dropped | ✓ Phase 14 |

| Vercel + Supabase for backend (v3) | Supabase iOS SDK available, Vercel already primary deploy target, auth + DB + realtime in one platform | — Pending |
| OpenAI Apps full support (v3) | MCP is shared protocol; dual distribution to Claude + ChatGPT maximizes reach | — Pending |
| allnew-baas integration (v3) | Consolidate backend infrastructure under WAF; avoid per-app BaaS proliferation | — Pending |
| Impl layer pattern (v3) | _tool_impls.py holds all tool business logic; transports are thin wrappers delegating via `return await impl_*()` | ✓ Phase 16 |
| Dual transport architecture (v3) | stdio + HTTP servers as separate FastMCP instances, never cross-import, both import _tool_impls.py only | ✓ Phase 16 |
| Backend-spec optional sub-steps (v3) | Absence of backend-spec.json = graceful skip, not failure; frontend-only apps not penalized | ✓ Phase 18 |
| Pitfall 2 avoidance (v3) | API routes prompt embeds ONLY backend-spec.json, never prd.md or screen-spec.json — prevents agent from re-generating page files | ✓ Phase 18 |
| All backend gate issues blocking (v3) | No advisories — every detected issue (missing Zod, SQL injection, secrets, no health endpoint) is hard-blocking | ✓ Phase 18 |
| Passkey via @simplewebauthn (v3) | Supabase has no native WebAuthn; custom session bridge via admin generateLink + verifyOtp | ✓ Phase 19 |
| @supabase/auth-ui-react banned (v3) | Archived Feb 2024; custom OAuth buttons with signInWithOAuth() instead | ✓ Phase 19 |
| OAuth config as advisory (v3) | Google/Apple OAuth is optional — failure to configure is advisory, not blocking | ✓ Phase 19 |

---
*Last updated: 2026-03-25 after Phase 19*
