# Web App Factory

## What This Is

An automated web application development pipeline that transforms a user's app idea into a production-ready, deployed web application. Forked from ios-app-factory's proven multi-phase pipeline architecture, replacing iOS-specific components (Swift/Xcode/App Store) with web-specific equivalents (React or Next.js / Vercel / web standards). The system orchestrates specialized Claude agents through quality-gated phases to produce shippable web apps and services.

## Core Value

A single command takes a web app idea from concept to deployed, production-quality web application — with market validation, UX design, implementation, testing, legal compliance, and deployment handled automatically.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Pipeline orchestration reused from ios-app-factory (factory.py, contract_pipeline_runner, pipeline_state)
- [ ] Web-adapted phase contract (YAML) defining idea → spec → build → test → legal → deploy phases
- [ ] Web-specific phase executors replacing iOS executors
- [ ] Web-specialized agents (spec-agent, build-agent, test-agent, legal-agent, deploy-agent)
- [ ] Web quality gates (Lighthouse, WCAG accessibility, security headers, SEO, link integrity)
- [ ] Deployment automation (Vercel, GitHub Pages, or cloud hosting)
- [ ] MCP server for approval gates and phase reporting (reuse from ios-app-factory)
- [ ] Runtime guards (phase ordering, gate enforcement, bypass detection) reused from ios-app-factory
- [ ] State persistence (state.json, activity-log.jsonl) reused from ios-app-factory
- [ ] CLI entry point: `python factory.py --idea "..." --project-dir ./output/AppName`

### Out of Scope

- iOS/Swift code generation — handled by ios-app-factory
- App Store submission — web apps deploy to web hosting, not App Store
- HealthKit / Apple-specific framework integration — not relevant for web
- Mobile-native features (push notifications via APNs, etc.) — web-only scope for v1
- Custom domain / DNS management — deployment to platform subdomain is sufficient for v1
- Backend infrastructure provisioning (databases, queues, etc.) — v1 generates frontend + serverless API routes

## Context

- ios-app-factory is a mature 8-phase pipeline with 68 phase executors, 26 quality gates, 6 specialized agents, governance monitors, and runtime guards
- The architecture is highly modular: pipeline orchestration, state management, gate enforcement, and MCP integration are domain-agnostic
- Domain-specific components (phase executors, agent prompts, gates, skills) are cleanly separated and replaceable
- ios-app-factory uses Claude Agent SDK for LLM orchestration, FastMCP for approval gates, and Playwright for browser automation
- The existing pipeline contract (YAML) defines phases, gates, deliverables, and quality criteria — this structure maps directly to web app development
- AllNew LLC operates both ios-app-factory and this project in the same workspace (`/Users/masa/Development/`)

## Constraints

- **Tech stack (pipeline)**: Python 3.10+, Claude Agent SDK, FastMCP — must match ios-app-factory for shared infrastructure reuse
- **Tech stack (generated apps)**: Next.js (React) as default framework — widely supported, good DX, Vercel deployment
- **Architecture**: Fork, not refactor — ios-app-factory continues independent development for iOS; web-app-factory is a separate codebase that shares patterns but not code at runtime
- **Quality**: Inherit ios-app-factory's quality-driven execution model (45-quality-driven-execution.md) — gates verify quality, not just existence
- **Deployment**: Vercel as primary deployment target for v1 — zero-config, preview deployments, serverless functions

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fork rather than extend ios-app-factory | iOS and web pipelines have fundamentally different phase content, gates, and deployment targets; a monolithic system would be harder to maintain | — Pending |
| Next.js as default generated framework | Most popular React framework, built-in SSR/SSG, API routes, Vercel-native deployment, large ecosystem | — Pending |
| Vercel as primary deployment target | Zero-config deployment, preview URLs per commit, serverless functions, free tier for validation | — Pending |
| Reuse pipeline infrastructure as-is | contract_pipeline_runner, pipeline_state, MCP server, governance_monitor are domain-agnostic | — Pending |
| Coarse phase structure (3-5 phases) | Web apps have fewer deployment gates than iOS (no App Store review); leaner pipeline is appropriate | — Pending |

---
*Last updated: 2026-03-21 after initialization*
