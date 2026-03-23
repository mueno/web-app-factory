# Web App Factory

## What This Is

An automated web application development pipeline that transforms a user's app idea into a production-ready, deployed web application. Distributed as an MCP App, users install it via `claude mcp add` and generate web apps through natural conversation with Claude. The system orchestrates specialized Claude agents through quality-gated phases to produce shippable web apps.

## Core Value

A single command takes a web app idea from concept to deployed, production-quality web application — with market validation, UX design, implementation, testing, legal compliance, and deployment handled automatically.

## Current Milestone: v2.0 MCP Apps

**Goal:** Make web-app-factory installable via `claude mcp add` with local-first development and multi-cloud deployment.

**Target features:**
- MCP App packaging (`claude mcp add` installable)
- MCP tools exposing full pipeline (generate, status, approve)
- Dual mode: full-auto + interactive (phase-by-phase confirmation)
- Environment detection and setup assistance
- Local dev server for preview before deploy
- Multi-cloud deployment (Vercel, AWS, Google Cloud)

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

### Active

(Defined in REQUIREMENTS.md after research)

### Out of Scope

- iOS/Swift code generation — handled by ios-app-factory
- App Store submission — web apps deploy to web hosting
- Custom domain / DNS management — platform subdomain sufficient
- Backend database provisioning — v2 generates frontend + serverless API routes
- Payment processing integration — too complex for automated generation

## Context

- v1.0 shipped 2026-03-22: 7 phases, 16 plans, 447+ tests, 36/36 requirements
- Post-v1.0: FLOW-01 gate added to catch form-page parameter mismatches
- BACKLOG has 3 items: BL-001 (WBS decomposition), BL-002 (E2E Playwright gate), BL-003 (Phase 1b data flow schema)
- MCP SDK and FastMCP are already dependencies; internal MCP server exists for approval gates
- Anthropic MCP Apps ecosystem is evolving rapidly — research needed on latest specs

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
| MCP App distribution (v2) | Users install via `claude mcp add`, no manual setup | — Pending |
| Local-first development (v2) | Preview before deploy, no cloud dependency for iteration | — Pending |
| Multi-cloud deploy (v2) | User choice: Vercel, AWS, GCP | — Pending |

---
*Last updated: 2026-03-23 after v2.0 milestone start*
