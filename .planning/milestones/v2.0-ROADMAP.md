# Roadmap: Web App Factory

## Overview

Web App Factory transforms a natural-language app idea into a deployed, production-quality Next.js web application. v1.0 shipped a 5-phase pipeline with 10 quality gates and Vercel deployment. v2.0 wraps that proven pipeline in a first-class MCP App distributable via `claude mcp add` — adding installable packaging, a 7-tool public API, a multi-cloud deployment abstraction, and a local dev server for iteration without cloud credentials.

## Milestones

- ✅ **v1.0 Core Pipeline** - Phases 1-7 (shipped 2026-03-22)
- 🚧 **v2.0 MCP Apps** - Phases 8-13 (in progress)

## Phases

<details>
<summary>✅ v1.0 Core Pipeline (Phases 1-7) - SHIPPED 2026-03-22</summary>

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
- [x] 01-01-PLAN.md — Project skeleton, YAML contract, JSON schema, contract validation
- [x] 01-02-PLAN.md — Pipeline state, governance monitor, gates, phase executor base
- [x] 01-03-PLAN.md — MCP server, config, agents, error router, quality self-assessment
- [x] 01-04-PLAN.md — CLI entry point, startup preflight, pipeline runner

### Phase 2: Spec
**Goal**: The spec agent produces a validated market analysis and structured PRD that the build agent can consume
**Depends on**: Phase 1
**Requirements**: SPEC-01, SPEC-02, SPEC-03, SPEC-04
**Success Criteria** (what must be TRUE):
  1. Phase 1a generates a Go/No-Go decision with named competitor analysis, a defined target user, and a tech feasibility memo that references the actual app being built
  2. Phase 1b produces a PRD with MoSCoW-classified requirements, a component inventory, and a screen specification with component names cross-referenced against the PRD
  3. The spec agent prompt contains no iOS-specific references and is validated by running a smoke test against a sample idea
**Plans:** 3/3 plans complete

Plans:
- [x] 02-01-PLAN.md — Spec agent definition, shared runner utility, test mock infrastructure
- [x] 02-02-PLAN.md — Phase 1a executor: idea validation + tech feasibility memo
- [x] 02-03-PLAN.md — Phase 1b executor: PRD + screen specification

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
- [x] 03-01-PLAN.md — Build agent runner, BUILD_AGENT system prompt, Phase 2a scaffold executor
- [x] 03-02-PLAN.md — Build gate and static analysis gate executors
- [x] 03-03-PLAN.md — Phase 2b code generation executor and pipeline integration

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
- [x] 04-01-PLAN.md — Deploy infrastructure: deploy-agent runner, DEPLOY_AGENT prompt, deployment gate, MCP approval gate, CLI flags
- [x] 04-02-PLAN.md — Quality gates: Lighthouse, accessibility (axe-core), security headers, link integrity
- [x] 04-03-PLAN.md — Phase 3 executor, legal doc generation, gate dispatch wiring

### Phase 5: Build Pipeline Directory Fix + Governance Wiring
**Goal**: The build pipeline correctly propagates the Next.js project directory from Phase 2a through Phase 2b and build gates, and the GovernanceMonitor enforces phase ordering at runtime
**Depends on**: Phase 4
**Requirements**: BILD-02, BILD-03, BILD-04, PIPE-05
**Gap Closure**: Closes gaps from v1.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. Phase 2a stores the scaffolded Next.js project path in PhaseResult or state, and Phase 2b receives it as the build agent's working directory
  2. The build gate runs `npm run build` and `tsc --noEmit` inside the scaffolded Next.js project directory, not the pipeline project_dir
  3. GovernanceMonitor is instantiated in contract_pipeline_runner.py and blocks phase-skip attempts at runtime
  4. All existing tests continue to pass after directory handoff changes
**Plans:** 1/1 plans complete

Plans:
- [x] 05-01-PLAN.md — project_dir propagation, Phase 2a/2b executor fixes, build gate directory fix, GovernanceMonitor wiring

### Phase 6: Contract Alignment + Ship Fixes
**Goal**: The YAML contract deliverable paths match what executors actually produce, and the MCP approval gate is invoked exactly once
**Depends on**: Phase 5
**Requirements**: CONT-04
**Gap Closure**: Closes gaps from v1.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. Contract legal deliverable paths match the TSX pages that Phase 3 executor generates
  2. Contract deployment deliverable path matches the actual file name (`deployment.json`)
  3. The MCP approval gate is invoked exactly once per pipeline run (not both from executor and contract gate dispatch)
  4. Quality self-assessment for Phase 3 correctly reports all deliverables as present
**Plans:** 1/1 plans complete

Plans:
- [x] 06-01-PLAN.md — YAML contract path fixes, duplicate MCP approval removal, self-assessment verification

### Phase 7: Ship Directory Fix
**Goal**: Phase 3 (Ship) executor operates in the generated Next.js project directory for all deploy and legal operations
**Depends on**: Phase 6
**Requirements**: DEPL-01, DEPL-02, DEPL-03, LEGL-01, LEGL-02, LEGL-03
**Gap Closure**: Closes gaps from v1.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. `contract_pipeline_runner.py` passes `nextjs_dir` in `PhaseContext.extra` to the Phase 3 executor
  2. Phase 3 executor uses `ctx.extra["nextjs_dir"]` as `cwd` for all Vercel CLI operations
  3. Deploy agent writes legal documents inside the Next.js project, not the pipeline root
  4. Deploy gate verifies HTTP 200 on a URL derived from a successful deploy
  5. All existing tests continue to pass after the directory handoff fix
  6. New integration test verifies `nextjs_dir` propagation from runner to Phase 3 executor
**Plans:** 1/1 plans complete

Plans:
- [x] 07-01-PLAN.md — nextjs_dir propagation to PhaseContext.extra, Phase 3 executor cwd fix, deploy agent cwd fix, integration test

</details>

### v2.0 MCP Apps (In Progress)

**Milestone Goal:** Make web-app-factory installable via `claude mcp add` with local-first development and multi-cloud deployment.

#### Phase 8: MCP Infrastructure Foundation
**Goal**: The security architecture, async execution model, and packaging conventions are locked before any user-facing feature is built
**Depends on**: Phase 7
**Requirements**: MCPI-01, MCPI-02, MCPI-03, MCPI-04, MCPI-05
**Success Criteria** (what must be TRUE):
  1. Running `claude mcp add web-app-factory -- uvx web-app-factory` installs and starts the server with no manual Python setup
  2. All subprocess calls in MCP tool handlers use list-form arguments with `shlex.quote()` — no `shell=True` path exists in any tool handler
  3. Calling a pipeline-starting tool returns a `run_id` immediately (under 1 second) and the pipeline continues in a background thread
  4. All public MCP tools carry a `waf_` prefix and a CI uniqueness assertion prevents collision with the internal approval gate server
  5. Credentials are stored and retrieved from the OS keychain — no API keys appear in config files or tool outputs
**Plans:** 3/3 plans complete

Plans:
- [x] 08-01-PLAN.md — Package skeleton, FastMCP server entry point, pyproject.toml updates, tool namespace CI assertion
- [x] 08-02-PLAN.md — Async pipeline bridge (ThreadPoolExecutor), input validation, subprocess security audit
- [x] 08-03-PLAN.md — OS keychain credential module with env-var fallback

#### Phase 9: Deploy Abstraction
**Goal**: The deployment layer supports three providers through a common interface, and the existing Vercel path remains backward compatible
**Depends on**: Phase 8
**Requirements**: DEPL-01, DEPL-02, DEPL-03, DEPL-04, DEPL-05, DEPL-06
**Success Criteria** (what must be TRUE):
  1. `DeployProvider` ABC defines `deploy`, `get_url`, and `verify` methods; all three concrete providers implement it without modification to the ABC
  2. Vercel deployment works identically to v1.0 — existing integration tests pass with the extracted `VercelProvider`
  3. Google Cloud Run deployment succeeds via `gcloud run deploy --source .` and returns a `*.run.app` URL that passes the deployment gate
  4. `AWSProvider` raises `NotImplementedError` with actionable guidance pointing to v3.0 timeline and manual CDK instructions
  5. `LocalOnlyProvider` skips cloud deploy and returns a localhost URL that the Phase 3 executor accepts as a valid deployment result
  6. The deploy target is selectable via `waf_generate_app` parameter at generation time
**Plans:** 3/3 plans complete

Plans:
- [x] 09-01-PLAN.md — DeployProvider ABC, DeployResult dataclass, provider registry, AWSProvider stub, LocalOnlyProvider
- [x] 09-02-PLAN.md — VercelProvider extraction from phase_3_executor.py, executor refactor to use provider interface
- [x] 09-03-PLAN.md — GCPProvider (Cloud Run), deploy_target wiring through pipeline bridge and runner

#### Phase 10: Local Dev Server
**Goal**: Users can preview generated apps locally before any cloud deployment, with clean process lifecycle management
**Depends on**: Phase 8
**Requirements**: LDEV-01, LDEV-02, LDEV-03, LDEV-04, TOOL-06, TOOL-07
**Success Criteria** (what must be TRUE):
  1. `waf_start_dev_server` starts `npm run dev` on an auto-detected free port and returns the localhost URL once the server is ready (port detected from stdout, not assumed)
  2. Calling `waf_start_dev_server` for a run ID that already has a running server returns the existing URL without starting a duplicate process
  3. `waf_stop_dev_server` terminates the specified server process and removes it from the PID registry
  4. All dev server processes are cleaned up when the MCP server shuts down — no orphan `npm run dev` processes remain after `waf_stop_dev_server` or SIGTERM
**Plans:** 2/2 plans complete

Plans:
- [x] 10-01-PLAN.md — Dev server lifecycle module (TDD): DevServerRegistry, start/stop logic, readiness detection, process group cleanup
- [x] 10-02-PLAN.md — MCP tool registration: waf_start_dev_server and waf_stop_dev_server in mcp_server.py

#### Phase 11: MCP Tool Layer
**Goal**: The full pipeline is accessible through four conversational MCP tools that expose generation, status, approval, and run history
**Depends on**: Phase 8, Phase 9, Phase 10
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04
**Success Criteria** (what must be TRUE):
  1. `waf_generate_app` starts a pipeline run in the background, returns a `run_id` within 1 second, and accepts idea text, mode (auto/interactive), deploy target, and optional `resume_run_id`
  2. `waf_get_status` returns current phase name, progress percentage, and the 5 most recent activity log entries for any run ID — reads `state.json` directly with no caching layer
  3. `waf_approve_gate` in interactive mode unblocks a waiting pipeline gate and resumes execution; in auto mode it returns a clear error explaining the mode mismatch
  4. `waf_list_runs` returns all runs from the `output/` directory with status, start time, and output URL — runs that are in progress show live phase information
**Plans:** 0/0 (implemented across Phases 8-10; gap fixes applied 2026-03-24)

Plans:
- No dedicated plans — TOOL-01 through TOOL-04 were implemented as part of Phases 8 (mcp_server.py, pipeline bridge), 9 (deploy_target wiring), and 10 (dev server tools). Gap fixes (resume_run_id wiring, auto-mode gate rejection, output URL in list_runs) applied 2026-03-24.

#### Phase 12: Environment Detection and Distribution
**Goal**: Users can verify their environment is ready before generating, and the package is installable from PyPI via a single command
**Depends on**: Phase 11
**Requirements**: TOOL-05, ENVS-01, ENVS-02, ENVS-03
**Success Criteria** (what must be TRUE):
  1. `waf_check_env` returns a structured per-tool status report covering Node.js, npm, Python, and any deploy-target-specific CLIs — each entry shows version found (or missing), minimum required, and the exact install command for the user's platform (macOS/Linux)
  2. `waf_check_env` distinguishes between "tool missing", "tool outdated", and "tool present but not authenticated" — Vercel token scope warning is included when Vercel is the deploy target
  3. `waf_check_env` offers to execute missing-tool installs with explicit user permission — it does not silently install anything
  4. `claude mcp add web-app-factory -- uvx web-app-factory` succeeds on a clean macOS and Linux machine with only Python and `uv` installed
**Plans:** 2/2 plans complete

Plans:
- [ ] 12-01-PLAN.md — Environment checker module (TDD): check_env, install_tool, format_env_report with platform-aware detection
- [ ] 12-02-PLAN.md — MCP tool registration: waf_check_env in mcp_server.py + distribution packaging validation

#### Phase 13: Pipeline Quality
**Goal**: The Phase 2b build step produces higher-quality output through incremental sub-steps, and form flows are validated end-to-end before deployment
**Depends on**: Phase 8
**Requirements**: QUAL-01, QUAL-02
**Success Criteria** (what must be TRUE):
  1. Phase 2b execution is split into three checkpointed sub-steps (shared components, pages, integration) — a failure in any sub-step shows exactly which step failed and allows resumption from that checkpoint
  2. The E2E Playwright gate executes a form submission flow on the built Next.js app and confirms the result page renders the expected output — the pipeline is blocked if this gate fails
  3. The FLOW-01 form-page parameter consistency gate and the new E2E gate operate independently — either can fail without masking the other
**Plans:** 2/2 plans complete

Plans:
- [ ] 13-01-PLAN.md — Phase 2b three-sub-step decomposition with checkpoint resume
- [ ] 13-02-PLAN.md — E2E Playwright form flow gate with contract and runner wiring

#### Phase 14: Wire Interactive Gate Approval
**Goal**: The interactive pipeline mode works end-to-end — `mode='interactive'` pauses the pipeline at gates, and `waf_approve_gate` decisions are consumed by the waiting pipeline
**Depends on**: Phase 11
**Requirements**: TOOL-03
**Gap Closure**: Closes TOOL-03, BREAK-01, BREAK-02, Flow B from v2.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. `_pipeline_bridge.py` forwards `mode='interactive'` to `run_pipeline()` and the pipeline pauses at gate checkpoints when interactive mode is active
  2. `waf_approve_gate` write path and `mcp_approval_gate` poll path use the same file location — gate decisions written by the MCP tool are consumed by the waiting pipeline
  3. Calling `waf_approve_gate` with `action='approve'` unblocks the paused pipeline and execution continues to the next phase
  4. Calling `waf_approve_gate` with `action='reject'` stops the pipeline with a clear rejection status in `waf_get_status`
  5. In auto mode, `waf_approve_gate` returns an error explaining the mode mismatch (no silent failure)
**Plans:** 2/2 plans complete

Plans:
- [ ] 14-01-PLAN.md — Shared GATE_RESPONSES_DIR constant, mcp_approval_gate interactive polling, path consistency
- [ ] 14-02-PLAN.md — Wire interactive_mode through bridge and runner, integration test for approve/reject flow

#### Phase 15: Declare Playwright Dependency
**Goal**: The E2E Playwright gate is functional on fresh installations via `uvx web-app-factory` by declaring playwright as a dependency
**Depends on**: Phase 13
**Requirements**: QUAL-02
**Gap Closure**: Closes QUAL-02, GAP-01 from v2.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. `playwright` is declared in `pyproject.toml` as a direct dependency (not optional) so `uvx web-app-factory` installs it automatically
  2. `uvx web-app-factory` installs playwright as part of the default dependency set, or the E2E gate install instructions are documented
  3. The E2E gate imports playwright successfully and executes the form flow test (not returning BLOCKED due to missing import)
**Plans:** 1/1 plans complete

Plans:
- [ ] 15-01-PLAN.md — Add playwright to pyproject.toml direct dependencies, update E2E gate BLOCKED message

## Progress

**Execution Order:**
v1.0 phases (1-7) complete. v2.0 phases execute in order: 8 → 9 → 10 → 11 → 12 (Phase 13 can run after 8, independent of 9-12). Gap closure: 14 (after 11), 15 (after 13).

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
| 15. Declare Playwright Dependency | 1/1 | Complete    | 2026-03-24 | - |
