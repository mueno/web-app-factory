# Roadmap: Web App Factory

## Overview

Web App Factory transforms a natural-language app idea into a deployed, production-quality Next.js web application through four phases: a forked pipeline infrastructure, a spec agent that validates and plans, a build agent that generates the application, and a ship phase that enforces quality gates and deploys. Each phase has a quality gate that blocks forward progress until observable success criteria are met.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure** - Pipeline plumbing forked and running — CLI, state, MCP, governance (completed 2026-03-21)
- [x] **Phase 2: Spec** - Spec agent validates market fit and produces structured PRD (completed 2026-03-21)
- [x] **Phase 3: Build** - Build agent generates Next.js app that passes build and static analysis gates (completed 2026-03-21)
- [x] **Phase 4: Ship** - Quality gates (Lighthouse, security, a11y), legal docs, and Vercel deployment (completed 2026-03-21)
- [x] **Phase 5: Build Pipeline Directory Fix + Governance Wiring** - Fix Phase 2a→2b project_dir handoff, wire GovernanceMonitor into live pipeline (gap closure) (completed 2026-03-21)
- [x] **Phase 6: Contract Alignment + Ship Fixes** - Align YAML contract paths with implementation, remove duplicate MCP approval gate (gap closure) (completed 2026-03-21)
- [ ] **Phase 7: Ship Directory Fix** - Fix nextjs_dir handoff to Phase 3 executor so deploy and legal operations target the correct directory (gap closure)

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
  1. Phase 1a generates a Go/No-Go decision with named competitor analysis, a defined target user, and a tech feasibility memo that references the actual app being built — readable as a real business decision document, not a placeholder
  2. Phase 1b produces a PRD with MoSCoW-classified requirements, a component inventory, and a screen specification with component names cross-referenced against the PRD
  3. The spec agent prompt contains no iOS-specific references and is validated by running a smoke test against a sample idea
**Plans:** 3/3 plans complete

Plans:
- [ ] 02-01-PLAN.md — Spec agent definition, shared runner utility, test mock infrastructure
- [ ] 02-02-PLAN.md — Phase 1a executor: idea validation + tech feasibility memo
- [ ] 02-03-PLAN.md — Phase 1b executor: PRD + screen specification

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
**Plans:** 3/3 plans complete

Plans:
- [ ] 03-01-PLAN.md — Build agent runner, BUILD_AGENT system prompt, Phase 2a scaffold executor
- [ ] 03-02-PLAN.md — Build gate and static analysis gate executors
- [ ] 03-03-PLAN.md — Phase 2b code generation executor and pipeline integration

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
**Plans:** 3/3 plans complete

Plans:
- [ ] 04-01-PLAN.md — Deploy infrastructure: deploy-agent runner, DEPLOY_AGENT prompt, deployment gate, MCP approval gate, CLI flags
- [ ] 04-02-PLAN.md — Quality gates: Lighthouse, accessibility (axe-core), security headers, link integrity
- [ ] 04-03-PLAN.md — Phase 3 executor, legal doc generation, gate dispatch wiring

### Phase 5: Build Pipeline Directory Fix + Governance Wiring
**Goal**: The build pipeline correctly propagates the Next.js project directory from Phase 2a scaffold through Phase 2b code generation and build gates, and the GovernanceMonitor enforces phase ordering at runtime
**Depends on**: Phase 4
**Requirements**: BILD-02, BILD-03, BILD-04, PIPE-05
**Gap Closure**: Closes gaps from v1.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. Phase 2a stores the scaffolded Next.js project path in PhaseResult or state, and Phase 2b receives it as the build agent's working directory
  2. The build gate runs `npm run build` and `tsc --noEmit` inside the scaffolded Next.js project directory, not the pipeline project_dir
  3. GovernanceMonitor is instantiated in contract_pipeline_runner.py and blocks phase-skip attempts at runtime
  4. All existing tests continue to pass after directory handoff changes

Plans:
- [ ] 05-01-PLAN.md — project_dir propagation, Phase 2a/2b executor fixes, build gate directory fix, GovernanceMonitor wiring

### Phase 6: Contract Alignment + Ship Fixes
**Goal**: The YAML contract deliverable paths match what executors actually produce, and the MCP approval gate is invoked exactly once
**Depends on**: Phase 5
**Requirements**: CONT-04
**Gap Closure**: Closes gaps from v1.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. Contract legal deliverable paths match the TSX pages that Phase 3 executor generates (`src/app/privacy/page.tsx`, `src/app/terms/page.tsx`)
  2. Contract deployment deliverable path matches the actual file name (`deployment.json`)
  3. The MCP approval gate is invoked exactly once per pipeline run (either from Phase 3 executor or from contract gate dispatch, not both)
  4. Quality self-assessment for Phase 3 correctly reports all deliverables as present (no false "pending" from path mismatches)

Plans:
- [ ] 06-01-PLAN.md — YAML contract path fixes, duplicate MCP approval removal, self-assessment verification

### Phase 7: Ship Directory Fix
**Goal**: Phase 3 (Ship) executor operates in the generated Next.js project directory for all deploy and legal operations, fixing the 6 unsatisfied requirements identified by milestone audit
**Depends on**: Phase 6
**Requirements**: DEPL-01, DEPL-02, DEPL-03, LEGL-01, LEGL-02, LEGL-03
**Gap Closure**: Closes gaps from v1.0 milestone audit (single root cause: nextjs_dir not in PhaseContext.extra)
**Success Criteria** (what must be TRUE):
  1. `contract_pipeline_runner.py` passes `nextjs_dir` in `PhaseContext.extra` to the Phase 3 executor
  2. Phase 3 executor uses `ctx.extra["nextjs_dir"]` as `cwd` for all Vercel CLI operations (`vercel pull`, `vercel build`, `vercel deploy`)
  3. Deploy agent writes legal documents (`privacy/page.tsx`, `terms/page.tsx`) inside the Next.js project, not the pipeline root
  4. Deploy gate verifies HTTP 200 on a URL derived from a successful deploy (not an empty/invalid URL)
  5. All existing tests (439+) continue to pass after the directory handoff fix
  6. New integration test verifies `nextjs_dir` propagation from runner to Phase 3 executor

Plans:
- [ ] 07-01-PLAN.md — nextjs_dir propagation to PhaseContext.extra, Phase 3 executor cwd fix, deploy agent cwd fix, integration test

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure | 4/4 | Complete    | 2026-03-21 |
| 2. Spec | 3/3 | Complete    | 2026-03-21 |
| 3. Build | 3/3 | Complete    | 2026-03-21 |
| 4. Ship | 3/3 | Complete   | 2026-03-21 |
| 5. Build Pipeline Fix | 1/1 | Complete   | 2026-03-21 |
| 6. Contract Alignment | 1/1 | Complete   | 2026-03-21 |
| 7. Ship Directory Fix | 0/1 | Not Started | — |
