# Project Research Summary

**Project:** web-app-factory
**Domain:** MCP-distributed automated web application generation pipeline (idea → deployed web app)
**Researched:** 2026-03-21 (v1.0) | Updated: 2026-03-23 (v2.0 milestone)
**Confidence:** HIGH (stack, pitfalls), MEDIUM (multi-cloud deploy abstractions, FastMCP async tasks)

## Executive Summary

web-app-factory v2.0 extends a validated 5-phase pipeline (idea → deployed Next.js app) into a first-class MCP App distributable via `claude mcp add`. The v1.0 pipeline — phase-ordered execution, quality gates, resumable state, multi-agent specialization, Vercel deployment — is shipped and production-proven. The v2.0 milestone adds three capabilities on top: an installable user-facing MCP server with 7 tools (`waf_generate`, `waf_status`, `waf_approve`, `waf_check_env`, `waf_start_preview`, `waf_stop_preview`, `waf_list_runs`), a local dev server for preview before deploy, and a multi-cloud deployment abstraction (Vercel, Google Cloud Run, local-only). The recommended architecture keeps the existing pipeline unchanged and wraps it with a new `web_app_factory/` Python package that becomes the PyPI entry point for `uvx web-app-factory`.

The deployment expansion is achievable but asymmetric. Vercel remains the zero-friction path (existing, fully automated). Google Cloud Run is achievable via `gcloud run deploy --source .` with no new Python dependencies — a single command that handles build, push, and deploy atomically. AWS via CDK + `open-next-cdk` works but carries MEDIUM confidence on exact package versions and requires optional dependencies. AWS Amplify is explicitly deferred to v3.0: its Git-connected SSR deployment model makes programmatic automation non-trivial. The `local-only` deploy target (skip cloud deploy, return local URL) is a low-effort differentiator that removes the credential barrier entirely for users who only want to preview generated apps.

The dominant risks are security-related and must be treated as infrastructure requirements before any feature is implemented. MCP tool handlers must never use `shell=True`; all user input must be validated and quoted with `shlex.quote()`; 43% of 2026 MCP CVEs involved command injection. The long-running pipeline (10-30 minutes) must use the three-tool start/status/result split pattern from day one — a synchronous MCP tool wrapping `run_pipeline()` will hit the 60-second client timeout and orphan the pipeline process. The MCP tool namespace collision risk (internal approval gate server and new user-facing server sharing a session) mandates a `waf_` prefix on all public tools before any tool is registered; this convention cannot be changed after deployment.

## Key Findings

### Recommended Stack

The v2.0 additions land cleanly on the existing stack with one net-new always-installed dependency. FastMCP 3.1.1 (already in `pyproject.toml`) is sufficient for all MCP server features including background tasks via `task=True`. The only new always-installed dependency is `vercel-cli>=50.0.0` — a Python package that bundles its own Node.js binary, removing the system Node requirement for Vercel deployment. AWS support is optional via `pip install web-app-factory[aws]`. GCP support requires no Python dependencies — only `gcloud` CLI on the user's PATH.

**Core technologies (v1.0 unchanged):**
- Python 3.10+ + `uv`: runtime and package manager — required by claude-agent-sdk; `uvx web-app-factory` is the install path
- `claude-agent-sdk 0.1.50` + `fastmcp 3.1.1`: pipeline orchestration + MCP server — same versions as ios-app-factory
- Next.js 16.2 + React 19.2 + TypeScript 5.1 + Tailwind CSS v4 + shadcn/ui: generated app stack — App Router, Turbopack stable
- Vitest 4.x + Playwright 1.58.2: testing in generated apps — Vitest replaces Jest, Playwright for E2E gates

**New dependencies (v2.0):**
- `vercel-cli>=50.0.0`: Python wrapper for Vercel CLI, bundles Node.js — always installed, replaces subprocess-based vercel invocation
- `aws-cdk-lib>=2.240.0` + `open-next-cdk>=0.1.0` + `constructs>=10.0.0`: AWS CDK deployment — optional `[aws]` extra only
- stdlib `subprocess` + `shutil` + `socket`: GCP deploy, local dev server, environment detection — no new Python deps

**What NOT to add:** `portpicker` (test-infra library; stdlib socket is sufficient), `google-cloud-run` Python SDK (REST API client, not a deploy tool), `.mcpb` packaging (compiled C extensions break Python portability), `cdk-nextjs` cdklabs (TypeScript-first, Python JSII bindings lag), `semver` PyPI (tuple comparison is sufficient).

### Expected Features

**Must have (table stakes — v2.0 MCP surface):**
- `waf_generate` MCP tool — starts pipeline as background task, returns `run_id` immediately; must NOT block synchronously
- `waf_status` MCP tool — reads `state.json` directly; no caching layer
- `waf_approve` MCP tool — user-facing approval gate for interactive mode; bridges to existing file-based approval mechanism
- `waf_check_env` MCP tool — structured gap report with exact fix instructions per deploy target
- `waf_start_preview` / `waf_stop_preview` MCP tools — `npm run dev` subprocess lifecycle, actual port from stdout
- `waf_list_runs` MCP tool — scans `output/` directory for prior runs
- Single-command install: `claude mcp add web-app-factory -- uvx web-app-factory` — zero Python setup friction
- Google Cloud Run deploy adapter (`gcloud run deploy --source .`)
- `local-only` deploy target (skip cloud deploy, return local URL)
- Resumable runs via `resume_run_id` parameter on `waf_generate`
- Cloud Run URL pattern (`*.run.app`) in deployment gate

**Should have (differentiators — v2.0):**
- Dual-mode pipeline: `auto` (fire-and-forget) vs `interactive` (phase-by-phase approval via `waf_approve`)
- Deploy target capability matrix: warn before generating ISR/Edge code for AWS/GCP targets
- `waf_check_env` structured output: per-check status + remediation command, including auth check (not just install check)
- Preview URL returned from `waf_start_preview` in conversational-friendly format

**Must have (table stakes — v1.0 pipeline, already shipped):**
- Phase-ordered execution with fail-closed quality gates; state persistence (`state.json`); resumability
- Deliverable manifests with `quality_criteria` arrays (gate-gaming prevention)
- Quality self-assessment JSON before every gate submission
- MCP approval gates for legal and deploy phases; governance bypass detection
- Responsive design, WCAG 2.1 AA, security headers, working build, privacy policy + ToS

**Defer to v3.0:**
- AWS Amplify adapter (Git-connected SSR deployment model, automation non-trivial)
- MCP App UI (interactive approval cards via `ui://` iframe — spec 0.1, client behavior varies)
- MCP Tasks async protocol (SEP-1686) — upgrade after basic polling validated
- Windows native support (doubles CI matrix)
- Database provisioning (Supabase/Neon), authentication scaffolding (Clerk/NextAuth)

### Architecture Approach

The recommended architecture is strictly additive: a new `web_app_factory/` Python package forms the public API surface without modifying any existing internal module. The user-facing MCP server (`mcp_app.py`) is a separate FastMCP instance from the existing internal approval gate server (`factory_mcp_server.py`) — different trust boundaries, different transports, different tool contracts. `run_pipeline()` is synchronous (uses `subprocess.run()` throughout) and must be wrapped in `ThreadPoolExecutor.run_in_executor()` rather than made async, to avoid a large refactor across all phase executors. Phase 3 executor receives the deploy provider via `PhaseContext.extra["deploy_provider"]` injection — the `extra` dict already exists, requiring no schema migration.

**Major components:**
1. `web_app_factory/mcp_app.py` — user-facing FastMCP server; 7 public tools with `waf_` prefix; singleton process per Claude session
2. `web_app_factory/_pipeline_bridge.py` — wraps `run_pipeline()` in `ThreadPoolExecutor` for async compatibility; writes `run_id` to `~/.web-factory/active-runs.json` for resume across sessions
3. `deploy/` module — `DeployProvider` ABC + `provider_registry.py` + `VercelProvider` (extracted from phase_3_executor) + `GCPProvider` (new, full) + `AWSProvider` (stub)
4. `local_server/server_manager.py` — `npm run dev` subprocess lifecycle; port detection via stdout parsing; PID registry at `~/.waf/preview-servers.json`; SIGINT/SIGTERM handlers
5. Existing pipeline (unchanged) — `contract_pipeline_runner`, phase executors 1a/1b/2a/2b/3, `pipeline_state.py`, all gates, `factory_mcp_server.py` (internal only)

**Build order (dependency graph):**
- Phase A: Foundation (`web_app_factory/` package, `pyproject.toml` entry point, `_pipeline_bridge.py`)
- Phase B: Deploy abstraction (ABC + registry + Vercel extraction + GCP full + AWS stub) — parallel with C
- Phase C: Local server (server manager + port allocator + signal handlers) — parallel with B
- Phase D: MCP tools (all 7 tools; depends on A, B, C)
- Phase E: Environment detection UX + `.mcp.json` + PyPI publish configuration

### Critical Pitfalls

1. **MCP synchronous timeout orphans the pipeline (v2-P1)** — A 10-30 minute pipeline in a single synchronous MCP tool call hits the 60-second client timeout. The pipeline continues as an orphan process; `state.json` gets corrupted on the next invocation. Prevention: `waf_generate` returns `run_id` immediately and runs in background. Must be designed before any tool is implemented.

2. **MCP tool name collision with internal approval gate server (v2-P2)** — Two FastMCP servers in the same Claude session with overlapping tool names produce undefined behavior. The approval gate could be triggered by user interaction. Prevention: mandate `waf_` prefix on all public tools before the first tool is registered. Add CI uniqueness assertion across all server configs.

3. **Subprocess injection via user-provided input (v2-P5, highest severity)** — 43% of 2026 MCP CVEs involved command injection. `subprocess.run(shell=True)` with user-provided project names or app descriptions = RCE on user's machine. Prevention: always list-form subprocess, `shlex.quote()` on all user input, strict pattern validation (`^[a-zA-Z0-9_-]{1,50}$`), security review (per `.claude/rules/60-security-review.md`) for every tool accepting user input.

4. **Next.js ISR/Edge features silently break on non-Vercel targets (v2-P6)** — ISR (`revalidate`), Edge Middleware, Partial Prerendering, and `runtime: 'edge'` are unsupported or broken on AWS OpenNext and GCP Cloud Run. Prevention: parameterize code generation prompt by deploy target; add pre-deploy compatibility gate; warn users selecting non-Vercel targets before generation starts.

5. **Gate-gaming — LLM optimizes for gate passage, not quality (P1, v1.0 pattern, still critical)** — LLM reverses gate conditions to produce minimum content. Directly caused the HealthStockBoardV30 incident in ios-app-factory. Prevention: `45-quality-driven-execution.md` protocol — purpose-first prompts, deliverable manifests, mandatory `quality-self-assessment-{phase}.json` before every gate submission. Never pass raw gate conditions to phase executor prompts.

6. **npm package hallucination — "slopsquatting" (P2)** — 19.7% of LLM-generated package references are hallucinations; attackers register phantom names with malware. Prevention: `npm-verify` gate validates each package against npm registry API before `npm install`. Pre-approved allowlist for common patterns.

## Implications for Roadmap

The v2.0 milestone adds 5 implementation phases on top of the existing v1.0 pipeline. The v1.0 roadmap phases (Infrastructure Fork through End-to-End Validation) remain the prerequisite foundation. The v2.0 phases begin after v1.0 is complete or in parallel if v1.0 pipeline is already stable.

### Phase 1 (v1.0): Infrastructure Fork
**Rationale:** The YAML contract runner, state management, and governance monitor must be working and tested before any executor code is written. The dual-implementation pitfall must be caught here with an integration test.
**Delivers:** Working Python project, CLI stub (`factory.py`), copied pipeline infrastructure, placeholder YAML contract, integration test asserting `state.json` updates after MCP `phase_reporter` call.
**Avoids:** Dual MCP implementation divergence (P3), state file corruption (P9)
**Research flag:** Standard patterns — direct ios-app-factory reuse, no additional research needed.

### Phase 2 (v1.0): YAML Contract Design
**Rationale:** Contract is the schema everything else builds against. Executors, gates, and quality criteria are all driven by what the YAML declares. Gate-gaming prevention must be built in now.
**Delivers:** `contracts/pipeline-contract.web.v1.yaml` — 5 phases, deliverable manifests with `quality_criteria` arrays, gate type definitions.
**Avoids:** Gate-gaming (P1) — quality criteria must be content-specific, not existence-only
**Research flag:** Needs research into quality criteria design patterns. What makes a `quality_criterion` genuinely content-verifying vs. vacuous?

### Phase 3 (v1.0): Spec Agent (Phases 1a + 1b)
**Rationale:** No runnable code generated here — lower risk, good place to validate the executor/gate framework before complex codegen in Phase 4.
**Delivers:** `phase_1a_idea.py` (idea validation, market research, Go/No-Go), `phase_1b_spec.py` (PRD, screen spec, tech feasibility), artifact gates, quality self-assessments.
**Research flag:** Standard patterns — ios-app-factory spec patterns transfer directly.

### Phase 4 (v1.0): Scaffold + Build Agents (Phases 2a + 2b)
**Rationale:** Highest-risk phase. Three active pitfalls cluster here: npm hallucination, client/server boundary misplacement, env var leakage. `next build` production build (not dev-mode) is required in the gate.
**Delivers:** `phase_2a_scaffold.py`, `phase_2b_build.py`, `build_gate.py`, `npm_verify_gate.py`, static analysis gates for `"use client"` boundary and `NEXT_PUBLIC_` env var exposure.
**Avoids:** npm hallucination (P2), client/server boundary (P4), env var leakage (P5), middleware auth bypass CVE-2025-29927 (P6), hydration errors (P7)
**Research flag:** Needs research. Build-agent prompt engineering for Next.js App Router is non-trivial. Questions: what prompt constraints reliably prevent `"use client"` misplacement? Package allowlist for 80% of app patterns? Zod patterns for Server Actions?

### Phase 5 (v1.0): Quality Gates + Deploy
**Rationale:** Lighthouse, axe-core, and security header gates require a running Next.js app. Legal documents reference build output. Deploy gate must verify live HTTP 200, not just CLI exit code.
**Delivers:** `lighthouse_gate.py`, `security_headers_gate.py`, `link_integrity_gate.py`, axe-core integration, `phase_3a_legal.py`, `phase_3b_deploy.py`, `deploy_gate.py`.
**Research flag:** Legal templates need web/GDPR adaptation from iOS originals. Lighthouse CI integration is well-documented.

### Phase 6 (v2.0): MCP Infrastructure Foundation
**Rationale:** Security constraints and architectural conventions that cannot be reversed later must be established before any v2.0 feature is built. Tool naming, async execution model, and subprocess security posture are foundation decisions. Getting these wrong requires rearchitecting all downstream tools.
**Delivers:** `web_app_factory/` package skeleton, `pyproject.toml` entry point for `uvx`, `_pipeline_bridge.py` with `ThreadPoolExecutor`, `waf_` prefix convention enforced, CI tool-name uniqueness check, input validation utilities (strict pattern + `shlex.quote()` wrappers), active-runs registry at `~/.web-factory/`.
**Avoids:** v2-P1 (synchronous timeout — three-tool pattern from day one), v2-P2 (tool name collision), v2-P5 (subprocess injection — security review at this phase)

### Phase 7 (v2.0): Deploy Abstraction Layer
**Rationale:** Phase 3 executor has Vercel tightly coupled. The abstraction must be extracted before any new adapter is built. Writing AWS and GCP adapters before locking the interface prevents Vercel-ism leakage (v2-P12). The target capability matrix (ISR/Edge support per platform) must be defined here to parameterize code generation in phases above.
**Delivers:** `DeployProvider` ABC, `provider_registry.py`, `VercelProvider` (extracted from phase_3_executor), `GCPProvider` (full — `gcloud run deploy --source .`), `AWSProvider` (stub), deploy target capability matrix, Phase 3 executor refactored to accept injected provider, Vercel CLI check in preflight made conditional on deploy target.
**Uses:** `vercel-cli>=50.0.0` (new dep), `gcloud` CLI (stdlib subprocess only), `aws-cdk-lib` (optional)
**Avoids:** v2-P6 (ISR feature incompatibility — capability matrix defined here), v2-P12 (Vercel-ism leakage — interface tested with two concrete implementations before locking)

### Phase 8 (v2.0): Local Dev Server
**Rationale:** Self-contained module with no shared dependencies on Phase 7. Can be developed in parallel. Port conflict and orphan cleanup are best solved at the module level before MCP tool wrappers add complexity.
**Delivers:** `local_server/server_manager.py`, `port_allocator.py`, PID registry, SIGINT/SIGTERM cleanup handlers, integration tests for start/stop/port-detection.
**Avoids:** v2-P8 (port conflict — parse actual port from `next dev` stdout, not assumed default), v2-P13 (orphan dev servers — signal handlers + lockfiles + startup-time orphan detection)

### Phase 9 (v2.0): MCP Tool Layer
**Rationale:** All 7 tools can now be implemented against stable internal APIs (Phase 6 bridge, Phase 7 deploy, Phase 8 local server). This is the phase that turns the existing pipeline into a user-facing MCP product.
**Delivers:** All 7 `waf_*` MCP tools, `waf_generate` as FastMCP background task, interactive vs auto mode, `resume_run_id` support, dual-mode behavior wired to gate approval mechanism.
**Implements:** User-facing MCP server (`mcp_app.py`) as separate FastMCP instance from internal server
**Avoids:** v2-P11 (dual state — `waf_status` reads `state.json` directly, no cache layer)

### Phase 10 (v2.0): Environment Detection and Distribution
**Rationale:** Last phase because it requires knowing the complete tool surface to check prerequisites for. Also includes PyPI packaging and `.mcp.json` — distribution artifacts built against the final tool set.
**Delivers:** `waf_check_env` structured gap report (per-check status + fix command per deploy target, auth check not just install), `.mcp.json` for project-scoped install, `README.md` with `claude mcp add` command, PyPI publish CI.
**Avoids:** v2-P4 (environment detection false positives — minimum version checks, auth checks, no silent auto-install), v2-P7 (credential scope — OS keychain storage guidance, explicit Vercel token scope warning)

### Phase Ordering Rationale

- v1.0 phases (1-5) must precede v2.0 phases (6-10): the MCP layer wraps the existing pipeline; there is nothing to wrap until the pipeline is stable
- Phase 6 (MCP Foundation) before Phase 9 (MCP Tools): security constraints and async execution model must be locked before any tool is implemented
- Phase 7 (Deploy Abstraction) and Phase 8 (Local Server) can run in parallel: no shared dependencies
- Phase 9 (MCP Tools) after both Phase 7 and Phase 8: tools are thin adapters over internal modules that must be stable first
- Phase 10 (Distribution UX) last: requires complete tool surface to define comprehensive prerequisite checks

### Research Flags

Needs research during planning:
- **Phase 4 (Build Agent):** Build-agent prompt engineering for Next.js App Router — what prompt constraints reliably prevent `"use client"` misplacement, package allowlist for common patterns, Zod Server Action patterns
- **Phase 5 (Legal Templates):** GDPR/CCPA minimum requirements for generated web apps — iOS-era templates need web adaptation
- **Phase 7 (Deploy Abstraction):** `open-next-cdk` Python package version pinning (MEDIUM confidence) — needs working integration test before committing to it
- **Phase 9 (MCP Tools):** FastMCP `task=True` background task in 3.1.1 — verify production-ready vs experimental; have fallback `ThreadPoolExecutor` pattern documented

Standard patterns, skip research:
- **Phase 1 (Infrastructure Fork):** Direct ios-app-factory reuse, all patterns documented
- **Phase 3 (Spec Agent):** ios-app-factory spec patterns transfer directly
- **Phase 6 (MCP Foundation):** `pyproject.toml` entry points, thread pool async wrapping, FastMCP server instantiation — well-documented with existing usage
- **Phase 8 (Local Server):** `subprocess.Popen` + port polling via `socket.create_connection` — stdlib patterns, zero external dependencies

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All major packages verified on PyPI with active release cadence. FastMCP 3.1.1 current (March 14, 2026). `vercel-cli` Python package has 101 releases. One MEDIUM item: `open-next-cdk` Python version needs implementation-time pinning validation. |
| Features | HIGH | MCP tool signatures derived from FastMCP docs + existing `factory.py` CLI surface. v1.0 pipeline features from ios-app-factory direct inspection. One MEDIUM item: FastMCP `task=True` marked experimental in docs — fallback pattern documented. |
| Architecture | HIGH | Three-layer architecture (user-facing MCP / existing pipeline / new supporting modules) is explicitly defined. Build order and component boundaries are unambiguous. Async/sync boundary (`run_in_executor`) is the key architectural decision and is well-justified. |
| Pitfalls | HIGH | v2.0 security pitfalls backed by 30 CVEs corpus from March 2026. Multi-cloud feature compatibility verified via OpenNext comparison table and Next.js official docs. v1.0 pitfalls have direct evidence from ios-app-factory production incidents. |

**Overall confidence:** HIGH

### Gaps to Address

- **`open-next-cdk` exact version:** MEDIUM confidence on Python/CDK compatibility. Run a minimal integration test before committing the AWS provider implementation. Fallback: defer AWS adapter to v3.0 and ship Vercel + GCP only.
- **FastMCP `task=True` production readiness:** Verify the background task decorator works in production (not just docs-marked experimental) before `waf_generate` depends on it. Fallback pattern (manual `ThreadPoolExecutor` with `run_id` tracking) is fully documented in ARCHITECTURE.md.
- **Cloud Run URL pattern in deployment gate:** The existing gate checks `*.vercel.app`. The `*.run.app` pattern for Cloud Run URLs must be added to the gate regex — easy to miss, breaks Phase 7 deploy validation if absent.
- **Vercel token over-scope (platform constraint, no code fix):** Vercel API tokens cannot be project-scoped as of March 2026. The `waf_check_env` tool and onboarding documentation must explicitly warn users that the Vercel token grants access to all their Vercel projects.
- **Build-agent prompt templates (v1.0 gap):** Research identified what to prevent but not the exact prompt language that reliably prevents `"use client"` misplacement and npm hallucination. Needs empirical iteration in Phase 4.
- **Quality criteria specificity (v1.0 gap):** The right formulation for web app spec quality criteria is not directly transferable from iOS specs. Address in Phase 2 research.

## Sources

### Primary (HIGH confidence)
- FastMCP docs (gofastmcp.com) — `fastmcp install claude-code`, `task=True` background task decorator, MCP server lifecycle
- Claude Code MCP docs (code.claude.com/docs/en/mcp) — `claude mcp add --scope user|project`, stdio transport, uvx install pattern
- FastMCP 3.1.1 PyPI (pypi.org/project/fastmcp/) — current release March 14, 2026
- `vercel-cli` Python PyPI (v50.35.0, 101 releases, active CI) — bundles Node.js, `run_vercel()` API
- mcpb GitHub (modelcontextprotocol/mcpb) — Desktop Extensions format; Python compiled extension limitation confirmed
- Google Cloud Run + Next.js official docs — `gcloud run deploy --source .` pattern, official Next.js Cloud Run template
- Next.js output standalone docs — dual-mode `next.config.ts`, `NEXT_BUILD_TARGET` env var
- MCP Security 2026 — 30 CVEs in 60 days corpus — command injection (43%), path traversal (82% of surveyed servers)
- OpenNext AWS comparison table (opennext.js.org/aws/comparison) — ISR/Edge/PPR feature parity gaps
- `/Users/masa/Development/ios-app-factory/` — direct codebase inspection; governance monitor, contract runner, MCP server patterns
- Next.js 16 release blog, CVE-2025-29927 (CVSS 9.1), CVE-2025-66478 (CVSS 10.0)
- `45-quality-driven-execution.md` workspace rules — gate-gaming prevention principles

### Secondary (MEDIUM confidence)
- `open-next-cdk` PyPI — Python package verified; exact version pinning requires implementation-time validation
- FastMCP background tasks (gofastmcp.com/servers/tasks) — `task=True` marked experimental
- MCP Tasks spec SEP-1686 — async tool semantics; FastMCP implementation status needs verification
- MCP Apps announcement blog (2026-01-26) — Desktop Extensions, UV runtime for Python servers
- `aws-cdk-lib` PyPI (v2.240.0+) — Python CDK library confirmed; `open-next-cdk` integration MEDIUM
- USENIX Security 2025 — npm hallucination 19.7% rate, slopsquatting attack patterns

### Tertiary (LOW confidence)
- MCP App manifest spec `0.1` — explicitly pre-stable; field names and structure may change before stable release
- AWS Amplify SSR programmatic deploy — documented as Git-connected requirement; deferred to v3.0 based on this constraint

---
*Research completed: 2026-03-23 (v2.0 update)*
*Ready for roadmap: yes*
