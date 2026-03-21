# Architecture Research

**Domain:** Automated web application generation pipeline (fork of ios-app-factory)
**Researched:** 2026-03-21
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         CLI Entry Point                              │
│  factory.py  --idea "..."  --project-dir ./output/AppName            │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│                    Pipeline Orchestration Layer                       │
│  ┌──────────────────────────┐  ┌────────────────────────────────┐   │
│  │  contract_pipeline_runner│  │  pipeline_state                │   │
│  │  (YAML-driven phase loop)│  │  (state.json, activity-log)    │   │
│  └────────────┬─────────────┘  └────────────────────────────────┘   │
│               │                                                      │
│  ┌────────────▼───────────────────────────────────────────────────┐  │
│  │                   pipeline_runtime/                            │  │
│  │  governance_monitor  error_router  startup_preflight           │  │
│  └────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │  dispatches per phase
┌───────────────────────────────▼──────────────────────────────────────┐
│                     Phase Executor Layer                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────────┐ │
│  │ phase_1a  │  │ phase_1b  │  │ phase_2a  │  │ phase_3_deploy    │ │
│  │ (idea     │  │ (spec &   │  │ (scaffold │  │ (Vercel deploy,   │ │
│  │  validate)│  │  design)  │  │  & build) │  │  CI setup)        │ │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────────┬─────────┘ │
└────────┼──────────────┼──────────────┼───────────────────┼───────────┘
         │              │              │                   │
┌────────▼──────────────▼──────────────▼───────────────────▼───────────┐
│                    Web-Specific Agent Layer                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────────┐  │
│  │ spec-agent │  │ build-agent│  │ test-agent │  │ deploy-agent  │  │
│  │            │  │            │  │            │  │               │  │
│  └────────────┘  └────────────┘  └────────────┘  └───────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────────────┐
│                        Gate Layer                                      │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ artifact_gate│  │ lighthouse_gate│  │ build_gate │  │ legal    │  │
│  │ (file exist) │  │ (perf/a11y/SEO)│  │ (npm build)│  │ gate     │  │
│  └──────────────┘  └────────────────┘  └────────────┘  └──────────┘  │
└───────────────────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────────────┐
│                     MCP Server (Human Gate)                            │
│  approve_gate  phase_reporter  (stdin/stdout FastMCP)                  │
└───────────────────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────────────┐
│                     Generated App Output                               │
│  output/{AppName}/                                                     │
│    src/  (Next.js app)   docs/pipeline/  (state, gates, handoff)       │
└───────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Reuse Status |
|-----------|----------------|--------------|
| `factory.py` | CLI entry point, argument parsing, pipeline dispatch | Adapt (strip iOS flags, add web flags) |
| `contracts/pipeline-contract.web.v1.yaml` | Phase ordering, deliverables, quality criteria, gate types | New — web-specific YAML replacing iOS YAML |
| `tools/contract_pipeline_runner.py` | YAML-driven phase loop, gate enforcement, resume logic | Reuse as-is (domain-agnostic) |
| `tools/pipeline_state.py` | Run lifecycle, state.json, activity-log.jsonl, handoff.md | Reuse as-is (domain-agnostic) |
| `pipeline_runtime/governance_monitor.py` | Phase ordering enforcement, bypass detection | Reuse as-is (domain-agnostic) |
| `pipeline_runtime/error_router.py` | Gate failure classification, agent delegation | Reuse with minor agent-name changes |
| `pipeline_runtime/startup_preflight.py` | Environment checks, single-flight lock | Reuse with web tool checks (Node.js, Vercel CLI) |
| `tools/factory_mcp_server.py` | approve_gate, phase_reporter MCP tools | Reuse as-is (domain-agnostic) |
| `tools/phase_executors/phase_*.py` | Per-phase LLM orchestration and artifact generation | New — all iOS executors replaced with web executors |
| `agents/definitions.py` | Agent prompt definitions per specialization | New — web-focused agent prompts |
| `tools/gates/` | Quality gate checkers (build, content, runtime) | Partially new — iOS gates replaced with web gates |

---

## Recommended Project Structure

### web-app-factory Repository

```
web-app-factory/
├── factory.py                         # CLI entry point (adapted from ios-app-factory)
├── pyproject.toml                     # Python dependencies
├── uv.lock
│
├── contracts/
│   └── pipeline-contract.web.v1.yaml  # SINGLE SOURCE — phases, deliverables, gates
│
├── agents/
│   └── definitions.py                 # 5 web-specialized agent prompts
│
├── pipeline_runtime/                  # Copied from ios-app-factory (unchanged)
│   ├── governance_monitor.py
│   ├── error_router.py
│   ├── startup_preflight.py
│   └── bypass_intent_detector.py
│
├── tools/
│   ├── contract_pipeline_runner.py    # Copied from ios-app-factory (unchanged)
│   ├── pipeline_state.py              # Copied from ios-app-factory (unchanged)
│   ├── factory_mcp_server.py          # Copied from ios-app-factory (unchanged)
│   ├── skill_evidence.py              # Copied from ios-app-factory (unchanged)
│   │
│   ├── phase_executors/               # ALL NEW — web-specific executors
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── phase_1a_idea.py           # Idea validation, market research
│   │   ├── phase_1b_spec.py           # PRD, wireframes, tech spec
│   │   ├── phase_2a_scaffold.py       # Next.js scaffold, project init
│   │   ├── phase_2b_build.py          # Component generation, API routes
│   │   ├── phase_2c_test.py           # Unit tests, E2E, Playwright
│   │   ├── phase_3a_legal.py          # ToS, Privacy Policy generation
│   │   └── phase_3b_deploy.py         # Vercel deploy, GitHub Actions setup
│   │
│   └── gates/                         # PARTIALLY NEW — web-specific gates
│       ├── __init__.py
│       ├── gate_policy.py             # Copied from ios-app-factory
│       ├── gate_result.py             # Copied from ios-app-factory
│       ├── artifact_gate.py           # NEW — required file existence check
│       ├── build_gate.py              # NEW — `npm run build` succeeds
│       ├── lighthouse_gate.py         # NEW — Lighthouse CI perf/a11y/SEO scores
│       ├── security_headers_gate.py   # NEW — CSP, HSTS, X-Frame-Options
│       ├── link_integrity_gate.py     # NEW — no broken links or 404s
│       ├── legal_gate.py              # NEW — ToS and Privacy Policy present
│       ├── deploy_gate.py             # NEW — Vercel deploy URL live and responsive
│       └── tool_invocation_gate.py    # Copied from ios-app-factory
│
├── config/
│   └── settings.py                    # Adapted from ios-app-factory
│
└── output/                            # Generated apps land here
    └── {AppName}/                     # One directory per generated app
        ├── src/                       # Next.js application source
        └── docs/pipeline/             # Pipeline artifacts (state, gates, handoff)
```

### Generated App Structure (Next.js)

Each generated app in `output/{AppName}/` follows this structure:

```
{AppName}/
├── package.json
├── next.config.js
├── tsconfig.json
├── tailwind.config.js
├── .env.example
├── .gitignore
│
├── src/
│   ├── app/                          # Next.js App Router
│   │   ├── layout.tsx                # Root layout
│   │   ├── page.tsx                  # Home page
│   │   ├── (marketing)/              # Marketing pages group
│   │   │   ├── about/page.tsx
│   │   │   └── pricing/page.tsx
│   │   └── api/                      # API routes (serverless functions)
│   │       └── [route]/route.ts
│   │
│   ├── components/
│   │   ├── ui/                       # Primitive components (Button, Card, etc.)
│   │   └── [feature]/                # Feature-specific components
│   │
│   ├── lib/
│   │   ├── utils.ts                  # Shared utilities
│   │   └── [service].ts              # Service clients
│   │
│   └── types/
│       └── index.ts
│
├── public/                           # Static assets
│
├── docs/                             # User-facing docs
│   ├── privacy-policy.md
│   ├── terms-of-service.md
│   └── idea-validation.md            # From Phase 1a
│
└── docs/pipeline/                    # Pipeline execution artifacts (never shipped)
    ├── runs/{run_id}/
    │   ├── state.json
    │   └── handoff.md
    ├── activity-log.jsonl
    └── quality-self-assessment-*.json
```

---

## Component Boundaries

### Reuse-As-Is (Copy Verbatim)

These components are domain-agnostic and require no modification:

| Component | Why Reusable |
|-----------|--------------|
| `tools/contract_pipeline_runner.py` | Reads any YAML contract; phase loop logic is domain-free |
| `tools/pipeline_state.py` | Manages run IDs, state.json, activity-log — no domain knowledge |
| `tools/factory_mcp_server.py` | approve_gate and phase_reporter are domain-agnostic MCP tools |
| `pipeline_runtime/governance_monitor.py` | Monitors tool call ordering, not domain logic |
| `pipeline_runtime/error_router.py` | Classifies failures by severity; agent names are configurable |
| `tools/skill_evidence.py` | Records skill invocation evidence; skill names are variable |
| `tools/gates/gate_policy.py` | Gate pass/fail policy evaluation; domain-free |
| `tools/gates/gate_result.py` | GateResult dataclass; domain-free |
| `tools/gates/tool_invocation_gate.py` | Checks that required tools were called; domain-free |

### Adapt (Thin Wrapper or Config Change)

| Component | What Changes |
|-----------|-------------|
| `factory.py` | Remove iOS-specific args (`--asc-app-id`, `--mode rejection-fix`); add web args (`--deploy-target`, `--framework`) |
| `pipeline_runtime/startup_preflight.py` | Replace Xcode/xcodebuild checks with Node.js/npm/Vercel CLI checks |
| `config/settings.py` | Replace App Store Director paths with Vercel project config |
| `agents/definitions.py` | Replace iOS agent prompts with web agent prompts; same dataclass structure |

### New (Web-Specific)

| Component | What It Does |
|-----------|-------------|
| `contracts/pipeline-contract.web.v1.yaml` | 5-phase web pipeline definition (phases: 1a, 1b, 2a, 2b, 3) |
| `tools/phase_executors/phase_*.py` | 5-7 executor files — one per phase/sub-phase, all web-focused |
| `tools/gates/lighthouse_gate.py` | Runs `lhci autorun` against deployed or local preview URL |
| `tools/gates/build_gate.py` | Runs `npm run build` in generated app directory, checks exit code |
| `tools/gates/security_headers_gate.py` | Checks HTTP response headers via requests or Playwright |
| `tools/gates/deploy_gate.py` | Verifies Vercel deployment URL is live and returns HTTP 200 |
| `tools/gates/link_integrity_gate.py` | Crawls internal links in generated app, checks for 404s |
| `tools/gates/legal_gate.py` | Checks that ToS and Privacy Policy files exist and are non-empty |

---

## Data Flow

### Pipeline Execution Flow

```
User:  python factory.py --idea "SaaS dashboard for X" --project-dir ./output/MyApp
            │
            ▼
factory.py  → startup_preflight() → checks Node.js, npm, Vercel CLI present
            │
            ▼
contract_pipeline_runner.load_contract("contracts/pipeline-contract.web.v1.yaml")
            │
            ▼
pipeline_state.init_run(run_id, app_name, project_dir)
  → creates: output/MyApp/docs/pipeline/runs/{run_id}/state.json
  → creates: output/MyApp/docs/pipeline/activity-log.jsonl
            │
            ▼ (for each phase in YAML)
phase_executor.execute(phase_id, phase_spec, project_dir)
  → spec-agent / build-agent / test-agent / deploy-agent (Claude Agent SDK)
  → agent writes deliverables to output/MyApp/docs/ and output/MyApp/src/
            │
            ▼
pipeline_state.phase_complete(phase_id)
  → updates state.json
            │
            ▼
gate_checker.run_gates(phase_spec.gates, project_dir)
  → artifact_gate: checks required files exist
  → build_gate: runs `npm run build`
  → lighthouse_gate: runs lhci against localhost preview
  → legal_gate: checks docs/privacy-policy.md, docs/terms-of-service.md
            │
   gate FAIL▼               gate PASS▼
error_router.route()         approve_gate (MCP) → human approval
  → escalate or retry             │
                                  ▼
                            next phase begins
```

### Phase-to-Artifact Data Flow

```
Phase 1a (Idea Validation)
  → docs/idea-validation.md
  → docs/pipeline/concept-sheet.md
  → docs/pipeline/tech-feasibility-memo.json
        │
        ▼ (input to Phase 1b)
Phase 1b (Spec & Design)
  → docs/pipeline/prd.md
  → docs/pipeline/screen-spec.json         (wireframe descriptions)
  → docs/pipeline/design-principles.json
        │
        ▼ (input to Phase 2a)
Phase 2a (Scaffold)
  → src/  (full Next.js project skeleton via `npx create-next-app`)
  → package.json, tsconfig.json, tailwind.config.js
  → .github/workflows/ci.yml
        │
        ▼ (input to Phase 2b)
Phase 2b (Build)
  → src/app/**  (pages, API routes)
  → src/components/**
  → src/lib/**
        │
        ▼ (input to Phase 3a and 3b)
Phase 3a (Legal)
  → docs/privacy-policy.md
  → docs/terms-of-service.md

Phase 3b (Deploy)
  → vercel.json
  → .github/workflows/deploy.yml
  → [Vercel deployment URL in state.json]
```

---

## Phase Structure for Web App Pipeline

The iOS pipeline has 11 phases (1a, 1b, 1b+, 2c, 2d, 2a, 2b, 3, 4a, 5, 6). The web pipeline should be leaner — 5 phases covering the same logical steps without App Store review, Xcode build system complexity, or device testing:

| Phase | Name | Purpose | Key Deliverables | Gates |
|-------|------|---------|-----------------|-------|
| 1a | Idea Validation | Market research, feasibility, Go/No-Go | idea-validation.md, concept-sheet.md, tech-feasibility-memo.json | artifact_gate, tool_invocation_gate |
| 1b | Spec & Design | PRD, screen specs, design system | prd.md, screen-spec.json, design-principles.json | artifact_gate, content_quality_gate |
| 2a | Scaffold | Next.js project init, CI config | src/ (skeleton), package.json, CI YAML | artifact_gate, build_gate (TypeScript check) |
| 2b | Build | Page generation, API routes, styling | src/app/**, src/components/** | build_gate (npm build), lighthouse_gate (local) |
| 3 | Ship | Legal docs, Vercel deploy, CI pipeline | privacy-policy.md, ToS, Vercel URL, GitHub Actions | legal_gate, deploy_gate, link_integrity_gate, lighthouse_gate (prod) |

**Rationale for 5 phases vs 11:**
- No App Store review (Phase 5 in iOS) — web deployment is instant
- No Xcode build complexity (multiple iOS sub-phases) — npm/Next.js build is simpler
- No separate icon/screenshot pipeline (iOS Phase 2c/2d) — web images are part of Phase 2b
- Legal still required but no ASC metadata — single Phase 3a step

---

## Architectural Patterns

### Pattern 1: YAML Contract as Single Source of Truth

**What:** The pipeline-contract.web.v1.yaml file drives everything — phase order, deliverables, quality criteria, and gate types. Phase executors and gate checkers are selected dynamically by the contract runner based on the phase ID.

**When to use:** Always. Adding a phase means adding a YAML block, not changing Python orchestration.

**Build order implication:** The YAML contract must be written first (Phase 1 of the roadmap). All downstream components are slaves to what the contract declares.

```yaml
phases:
  - id: "2b"
    name: "Build"
    purpose: "Generate production-quality Next.js pages and API routes"
    deliverables:
      - name: "Home Page"
        path: "src/app/page.tsx"
        quality_criteria:
          - "Uses Tailwind CSS utility classes, not inline styles"
          - "Implements responsive breakpoints (mobile, tablet, desktop)"
          - "Passes WCAG AA accessibility check"
    gates:
      - type: build
        description: "npm run build exits 0"
        fail_action: block
      - type: lighthouse
        description: "Lighthouse performance >= 80"
        checks:
          min_performance: 80
          min_accessibility: 90
          min_seo: 80
        fail_action: block
```

### Pattern 2: Phase Executor Registry

**What:** Phase executors are registered by phase ID. The contract runner looks up `phase_executors/phase_{id}.py` and calls `execute(phase_spec, project_dir, agent_sdk)`. This mirrors ios-app-factory's pattern exactly.

**When to use:** When adding a new phase. New executor file, no changes to contract runner.

**Trade-offs:** Naming convention is a contract. If the file doesn't match the phase ID, the runner raises `ExecutorNotFound`.

```python
# tools/phase_executors/base.py
class BasePhaseExecutor:
    def execute(self, phase_spec: PhaseSpec, project_dir: Path, sdk) -> PhaseResult:
        raise NotImplementedError

# tools/phase_executors/phase_2b_build.py
class Phase2bBuildExecutor(BasePhaseExecutor):
    def execute(self, phase_spec, project_dir, sdk) -> PhaseResult:
        agent = sdk.create_agent(AGENTS["build-agent"])
        result = agent.run(
            f"Build the Next.js application in {project_dir}/src/ "
            f"according to the spec in {project_dir}/docs/pipeline/prd.md"
        )
        return PhaseResult(phase_id="2b", artifacts=result.artifacts)
```

### Pattern 3: Gate Type Dispatch

**What:** Gates in the YAML have a `type` field (`build`, `lighthouse`, `artifact`, `legal`, etc.). The gate dispatcher maps type strings to gate checker classes. iOS had 26 gates; web needs fewer, focused on different concerns.

**When to use:** When a phase needs an automated quality check. Add a gate entry to the YAML; the gate class is looked up by type string.

**Web-specific gate types to implement:**

| Gate Type | Implementation | Threshold |
|-----------|---------------|-----------|
| `artifact` | Check file exists, non-empty | Required |
| `build` | Run `npm run build`, check exit code | Exit 0 |
| `lighthouse` | `lhci autorun --config=lighthouserc.json` | Perf >= 80, A11y >= 90, SEO >= 80 |
| `security_headers` | HTTP response header check (CSP, HSTS) | All present |
| `link_integrity` | Crawl internal links, check 404s | 0 broken links |
| `legal` | File existence + minimum word count | 200+ words each |
| `deploy` | GET deployment URL, check HTTP 200 | HTTP 200 within 30s |
| `tool_invocation` | Evidence that required tools were called | All required refs present |

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Vercel CLI | `subprocess.run(["vercel", "deploy", "--prod"])` in deploy-agent | Requires `VERCEL_TOKEN` env var; zero-config for Next.js |
| GitHub API | GitHub Actions YAML generated as artifact, not via API | No token needed for generation; user pushes |
| Lighthouse CI | `subprocess.run(["lhci", "autorun"])` in lighthouse_gate.py | Requires `lighthouserc.json` in generated app |
| Claude Agent SDK | Phase executors call `sdk.query(agent, prompt)` | Same SDK as ios-app-factory |
| FastMCP | MCP server for approve_gate, phase_reporter | Same MCP server as ios-app-factory, reused as-is |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| factory.py → contract_pipeline_runner | Direct Python function call | `run_pipeline(contract_path, project_dir, idea)` |
| contract_pipeline_runner → phase_executors | Module import + `executor.execute()` | Executor selected by phase_id string lookup |
| phase_executors → agents | Claude Agent SDK `sdk.query()` | Each executor owns one agent interaction |
| contract_pipeline_runner → gates | Gate class instantiation + `gate.check(project_dir)` | Gate selected by type string from YAML |
| gates → generated app | Read-only file system inspection | Gates never write to generated app; only read |
| factory_mcp_server → human | stdin/stdout FastMCP protocol | User receives approval request in terminal |
| pipeline_state → disk | `state.json` writes in `docs/pipeline/runs/{run_id}/` | All state mutations go through pipeline_state API |

---

## Build Order Implications for Roadmap

The dependency graph dictates this construction order:

1. **Milestone 1: Infrastructure fork** — Copy domain-agnostic components from ios-app-factory verbatim (`pipeline_state.py`, `contract_pipeline_runner.py`, `factory_mcp_server.py`, `governance_monitor.py`, `error_router.py`). Write the pyproject.toml and basic `factory.py` CLI stub. Write a minimal `pipeline-contract.web.v1.yaml` with placeholder phases. Validate the plumbing with a dry-run.

2. **Milestone 2: YAML contract** — Define all 5 phases with full deliverable lists and quality criteria. Define gate types. This is the schema everything else is built against. No agent code yet.

3. **Milestone 3: Phase executors 1a + 1b** — Implement spec-agent. Validate that Phase 1a produces idea-validation.md and Phase 1b produces prd.md. Artifact gates only needed at this stage.

4. **Milestone 4: Phase executors 2a + 2b** — Implement build-agent. Scaffold and build a real Next.js project. Add build_gate (npm build). This is the highest-risk milestone — LLM-generated Next.js code may have quality variance.

5. **Milestone 5: Web-specific gates** — Implement lighthouse_gate, security_headers_gate, link_integrity_gate. These require a running local Next.js server, so they depend on Milestone 4 being stable.

6. **Milestone 6: Phase 3 (Legal + Deploy)** — Implement legal-agent and deploy-agent. Add legal_gate and deploy_gate. Vercel CLI integration here.

7. **Milestone 7: End-to-end validation** — Run the full 5-phase pipeline against a real idea. Fix any integration issues. Document the runbook.

**Critical dependency:** Milestones 3-6 are blocked on Milestone 2 (YAML contract). If the contract schema changes, phase executors and gates may need updates. Lock the contract schema early.

---

## Anti-Patterns

### Anti-Pattern 1: Rewriting Infrastructure Instead of Forking

**What people do:** Conclude that ios-app-factory's infrastructure is "too iOS-specific" and rewrite contract_pipeline_runner, pipeline_state, and governance_monitor from scratch for web.

**Why it's wrong:** These files are domain-agnostic — they contain no iOS knowledge. Rewriting them multiplies maintenance burden (two diverging implementations) and loses battle-tested behavior (gate enforcement, bypass detection, run ID management, activity logging).

**Do this instead:** Copy verbatim. Treat them as an external library. The only change allowed is updating the PHASE_ORDER constant in pipeline_state.py to reflect the web phase IDs.

### Anti-Pattern 2: One Executor Per Phase ID But Unlimited Size

**What people do:** Create `phase_2b_build.py` and put all build logic (scaffold, codegen, testing, linting) into a single 1000-line file because it is "one phase."

**Why it's wrong:** Phase 2b (Build) is the most complex phase. Unbounded file size leads to the same God File problem that plagues ios-app-factory's `all_phases.py` (5,733 lines).

**Do this instead:** Apply the ios-app-factory split pattern. `phase_2b_build.py` is the entry point and orchestrator; extract `phase_2b_scaffold.py`, `phase_2b_codegen.py`, `phase_2b_styles.py` as sub-modules. Cap each at 400 lines per the code-health rule.

### Anti-Pattern 3: Importing iOS Gate Classes Directly

**What people do:** To save time, import `tools/gates/build_gate.py` from ios-app-factory and try to reuse it for npm builds because it has similar structure.

**Why it's wrong:** ios-app-factory's `build_gate.py` invokes xcodebuild, checks xcresult bundles, and looks for iOS-specific artifacts. It will always fail for npm/Next.js targets.

**Do this instead:** Write new gate classes with the same base class interface (`gate_result.py` GateResult is reusable), but with entirely new implementation targeting npm, Lighthouse CI, and HTTP responses.

### Anti-Pattern 4: Generating Complete App Source in Phase 1a

**What people do:** Ask the spec-agent to write actual React components during idea validation "to validate the concept faster."

**Why it's wrong:** Phase 1a artifacts are planning documents. If the idea is rejected at the human approval gate after 1a, all generated code is waste. More importantly, mixing planning and implementation in the same phase makes it impossible to apply quality gates cleanly.

**Do this instead:** Phase 1a produces only markdown planning documents. Source code generation begins strictly in Phase 2a (scaffold) and Phase 2b (build). Gate boundaries enforce this separation.

---

## Scaling Considerations

This is a developer tool pipeline running locally or in CI — not a multi-tenant web service. Scaling considerations are different from a user-facing product:

| Concern | Single Developer | Team / CI |
|---------|-----------------|-----------|
| Parallel pipelines | Single-flight lock prevents concurrent runs | Lock is per `project_dir`; different apps can run in parallel |
| LLM token costs | Phase 2b (codegen) is the most expensive phase — $2-8 per run estimate | Budget flag (`--budget`) from ios-app-factory controls maximum spend |
| Lighthouse gate speed | Requires spawning a Next.js dev server; adds ~60s per run | Run `next build && next start` once per pipeline; share server across gate checks in Phase 3 |
| Vercel deploy speed | Cold deploy ~30-60s; subsequent deploys ~15-30s | Use `vercel deploy --prod --prebuilt` after local `vercel build` to minimize Vercel build time |

---

## Sources

- ios-app-factory codebase: `/Users/masa/Development/ios-app-factory/` (HIGH confidence — direct inspection)
- Next.js App Router project structure: [Next.js Official Docs](https://nextjs.org/docs/app/getting-started/project-structure) (HIGH confidence)
- Vercel CLI + GitHub Actions: [Vercel Knowledge Base](https://vercel.com/kb/guide/how-can-i-use-github-actions-with-vercel) (HIGH confidence)
- Lighthouse CI integration: [GoogleChrome/lighthouse](https://github.com/GoogleChrome/lighthouse) (HIGH confidence)
- Monorepo patterns for generated apps: [Next.js Monorepo Discussion](https://github.com/vercel/next.js/discussions/50866) (MEDIUM confidence — discussion thread, not official docs)

---
*Architecture research for: Automated web application generation pipeline (web-app-factory)*
*Researched: 2026-03-21*
