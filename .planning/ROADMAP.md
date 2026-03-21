# Roadmap: Web App Factory

## Overview

Web App Factory transforms a natural-language app idea into a deployed, production-quality Next.js web application through four phases: a forked pipeline infrastructure, a spec agent that validates and plans, a build agent that generates the application, and a ship phase that enforces quality gates and deploys. Each phase has a quality gate that blocks forward progress until observable success criteria are met.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure** - Pipeline plumbing forked and running — CLI, state, MCP, governance (completed 2026-03-21)
- [ ] **Phase 2: Spec** - Spec agent validates market fit and produces structured PRD
- [ ] **Phase 3: Build** - Build agent generates Next.js app that passes build and static analysis gates
- [ ] **Phase 4: Ship** - Quality gates (Lighthouse, security, a11y), legal docs, and Vercel deployment

## Phase Details

### Phase 1: Infrastructure
**Goal**: The pipeline runs, state persists, governance guards enforce correctness
**Depends on**: Nothing (first phase)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07, CONT-01, CONT-02, CONT-03, CONT-04
**Success Criteria** (what must be TRUE):
  1. Running `python factory.py --idea "..." --project-dir ./output/Test` starts the pipeline, creates `state.json`, and blocks at the first incomplete phase
  2. Interrupting and re-running the pipeline resumes from the last completed phase without re-running earlier phases
  3. MCP approval gate tools are reachable and a human approval sign-off unblocks the waiting phase
  4. Attempting to skip a phase or directly edit a guarded file causes the governance monitor to reject the operation
  5. Startup preflight fails with a clear error if Node.js, Python, or Vercel CLI are missing from the environment
**Plans:** 4/4 plans complete

Plans:
- [ ] 01-01-PLAN.md — Project skeleton, YAML contract, JSON schema, contract validation
- [ ] 01-02-PLAN.md — Pipeline state, governance monitor, gates, phase executor base
- [ ] 01-03-PLAN.md — MCP server, config, agents, error router, quality self-assessment
- [ ] 01-04-PLAN.md — CLI entry point, startup preflight, pipeline runner

### Phase 2: Spec
**Goal**: The spec agent produces a validated market analysis and structured PRD that the build agent can consume
**Depends on**: Phase 1
**Requirements**: SPEC-01, SPEC-02, SPEC-03, SPEC-04
**Success Criteria** (what must be TRUE):
  1. Phase 1a generates a Go/No-Go decision with named competitor analysis and a defined target user — readable as a real business decision document, not a placeholder
  2. Phase 1b produces a PRD with MoSCoW-classified requirements, a component inventory, and a tech feasibility memo that references the actual app being built
  3. The spec agent prompt contains no iOS-specific references and is validated by running a smoke test against a sample idea
**Plans**: TBD

### Phase 3: Build
**Goal**: The build agent scaffolds and generates a Next.js application that compiles, type-checks, and passes static analysis gates
**Depends on**: Phase 2
**Requirements**: BILD-01, BILD-02, BILD-03, BILD-04, BILD-05, BILD-06, BILD-07, GATE-01, GATE-05, GATE-06
**Success Criteria** (what must be TRUE):
  1. The generated project passes `next build` without errors (production build, not dev mode)
  2. The generated project passes `tsc --noEmit` without type errors
  3. The build gate rejects the pipeline if either `next build` or `tsc --noEmit` returns non-zero
  4. The static analysis gate fails if `"use client"` appears in `layout.tsx` or `page.tsx`
  5. The static analysis gate fails if any environment variable matching `NEXT_PUBLIC_` + secret-name pattern is detected
  6. No npm packages are installed without prior validation against the npm registry (hallucination prevention)
**Plans**: TBD

### Phase 4: Ship
**Goal**: The deployed application meets quality thresholds, has legally compliant documents, and is live at a Vercel URL
**Depends on**: Phase 3
**Requirements**: GATE-02, GATE-03, GATE-04, GATE-07, LEGL-01, LEGL-02, LEGL-03, DEPL-01, DEPL-02, DEPL-03, DEPL-04
**Success Criteria** (what must be TRUE):
  1. Lighthouse scores on the deployed Vercel preview URL meet thresholds: performance >=85, accessibility >=90, SEO >=85
  2. axe-core accessibility check passes with zero critical violations on the deployed app
  3. Security headers gate verifies CSP, HSTS, X-Frame-Options, and X-Content-Type-Options are present on the deployed URL
  4. Link integrity gate confirms no internal 404s in the deployed application
  5. Privacy Policy and Terms of Service documents are present, reference actual app features, and are linked from the deployed app
  6. The Vercel deployment URL is captured in `docs/pipeline/deployment.json` and returns HTTP 200 within 30 seconds
  7. A human MCP approval sign-off is required before the production deploy proceeds
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure | 4/4 | Complete   | 2026-03-21 |
| 2. Spec | 0/TBD | Not started | - |
| 3. Build | 0/TBD | Not started | - |
| 4. Ship | 0/TBD | Not started | - |
