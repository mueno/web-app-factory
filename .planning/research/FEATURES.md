# Feature Landscape

**Domain:** Automated web application generation pipeline (idea → deployed web app)
**Researched:** 2026-03-23 (v2.0 milestone update; v1.0 section preserved below)
**Overall confidence:** HIGH (MCP packaging), MEDIUM (multi-cloud deploy), HIGH (tool signatures)

---

## v2.0 Milestone: MCP App Distribution + Multi-Cloud Deployment

This section covers only the NEW features for v2.0. The v1.0 pipeline (5-phase, 10 gates, Vercel deploy, state persistence) already ships and is documented in the v1.0 section below.

### Context: What Users Actually Install

MCP Apps (officially released 2026-01-26) support two distribution paths relevant to this project:

1. **Desktop Extensions (.mcpb bundles)** — one-click install via Claude Desktop Settings > Extensions. ZIP archives containing server + manifest.json. Node.js ships with Claude Desktop so Node servers have zero dependency friction. Python servers can use an experimental UV runtime (v0.4+) but **cannot portably bundle compiled dependencies** (pydantic, which the MCP Python SDK requires). Workaround: expose a thin Node.js manifest wrapper that delegates to `uvx web-app-factory` for the heavy Python pipeline.

2. **`claude mcp add` (Claude Code)** — command-line registration. Format for local Python servers: `claude mcp add web-app-factory -- uvx web-app-factory`. Supports `stdio`, `http`, and `sse` transports. Scope flag: `--scope project` writes to `.mcp.json` for team sharing.

Users arriving via Claude Code expect `claude mcp add` + one command to work immediately. Users on Claude Desktop expect double-click install via .mcpb file.

---

## Table Stakes (v2.0)

Features users expect when installing an MCP code-generation tool. Missing = product feels broken.

| Feature | Why Expected | Complexity | Dependencies on v1.0 |
|---------|--------------|------------|----------------------|
| `generate_app` MCP tool | Core action — turns idea into deployed app. Without this, users cannot start. | Med | Wraps `factory.py` + existing pipeline |
| `get_status` MCP tool | Pipeline takes 10-30 min. Users cannot stare at a terminal. They need async progress. | Low | `pipeline_state.py` (read-only) |
| `approve_gate` MCP tool (public surface) | Existing internal tool must be in the public MCP interface; otherwise interactive mode has no approval mechanism | Low | `factory_mcp_server.py` (exists) |
| `check_environment` MCP tool | Users will have missing Node.js, Vercel CLI, missing API keys. Silent failure at pipeline start is unacceptable. | Med | Extends `startup_preflight.py` |
| `start_dev_server` MCP tool | "Preview before you deploy" is the standard expectation for any code generator. Users do not trust blind deploys. | Med | New: subprocess `npm run dev`, port management |
| `stop_dev_server` MCP tool | Pair with start. Without this, dev servers become orphan processes. | Low | Companion to start_dev_server |
| `list_runs` MCP tool | Users need discoverability of previous runs without checking the filesystem. | Low | Reads `output/` directory |
| `claude mcp add` installability | Single command install. If this fails, users abandon the product immediately. | Med | `pyproject.toml` entry point + uv packaging |
| Resumable runs exposed via MCP | v1.0 has `--resume` on CLI; MCP tool must support `resume_run_id` parameter | Low | `pipeline_state.py` (exists) |
| Clear error for missing credentials | `ANTHROPIC_API_KEY`, `VERCEL_TOKEN`, `gcloud auth` — users need actionable guidance, not stack traces | Low | Extend `startup_preflight.py` |

---

## Differentiators (v2.0)

Features that create meaningful user delight beyond the table stakes.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multi-cloud deploy target selection | Users choose Vercel / Cloud Run / local-only — not locked to Vercel | High | See deploy target section below |
| Dual-mode pipeline (auto vs interactive) | Power users review each phase; beginners use fire-and-forget | Med | `mode` parameter on `generate_app`; changes gate behavior |
| Environment setup wizard output | `check_environment` returns structured gap report with exact fix commands | Med | Returns JSON with per-check status + remediation instructions |
| Preview URL in tool response | After `start_dev_server`, return `http://localhost:3000` so Claude can surface it conversationally | Low | subprocess + port detection; 3000 default, auto-increment on conflict |
| Progress streaming via MCP Tasks | Uses SEP-1686 Tasks protocol: `taskId` returned immediately, poll via `tasks/get`. Better than file-based polling. | Med | FastMCP 3.x `@mcp.tool(task=True)` decorator; experimental |
| `local-only` deploy target | No cloud credentials needed; pipeline still generates and validates the app | Low | New adapter that skips deploy phase, returns local URL only |

---

## Anti-Features (v2.0)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Custom domain / DNS management | Every cloud provider has different DNS flows; scope creep; high support surface | Return platform subdomain URL in deploy result |
| Database provisioning | Requires cloud-specific setup (RDS, Cloud SQL); dramatically expands credential surface | Document as out-of-scope; generated apps use serverless API routes + external DBaaS |
| Payment processing setup | PCI scope; provider-specific SDK integration | Scaffold Stripe boilerplate as placeholder code only |
| OAuth / auth provider setup | Complex; each provider has different console flows | Scaffold NextAuth.js boilerplate; user completes provider config manually |
| Interactive MCP App UI (approval cards via `ui://` iframe) | MCP Apps spec released 2026-01-26; iframe sandbox behavior varies by client; debugging surface is large | Use text-based approval gates for v2.0; plan MCP App UI for v3.0 |
| AWS Amplify deploy adapter | Amplify programmatic API for Next.js SSR requires Git-connected app (no `amplify publish` for SSR); automation is non-trivial | Vercel + Cloud Run cover the use case; revisit Amplify in v3.0 |
| Windows native support | Python pipeline has POSIX subprocess assumptions; `npm run dev` works but CI matrix doubles | Document macOS/Linux only; WSL2 acceptable for Windows users |

---

## Expected MCP Tool Signatures

### `generate_app`

```python
@mcp.tool()
async def generate_app(
    idea: str,                          # Required. "A recipe sharing app for home cooks"
    deploy_target: str = "vercel",      # "vercel" | "cloud-run" | "local-only"
    mode: str = "auto",                 # "auto" | "interactive" (phase-by-phase approval)
    framework: str = "nextjs",          # "nextjs" only in v2.0
    project_dir: str = "",              # Optional: override output directory
    resume_run_id: str = "",            # Optional: resume an interrupted run
) -> str:
    """Generate and deploy a web application from a natural language idea.

    Returns a run_id immediately. Use get_status(run_id) to track progress.
    In 'interactive' mode, approve_gate will be called between each phase.
    The pipeline is fully resumable if interrupted.
    """
```

**Immediate return value:**
```json
{
  "run_id": "20260323-120000-recipe-app",
  "status": "started",
  "message": "Pipeline started. Use get_status('20260323-120000-recipe-app') to track progress.",
  "project_dir": "/path/to/output/RecipeApp"
}
```

**Confidence:** MEDIUM — signature derived from MCP Tasks spec (SEP-1686) + existing `factory.py` args. Async/task semantics depend on FastMCP version.

---

### `get_status`

```python
@mcp.tool()
async def get_status(
    run_id: str = "",    # Specific run; empty = most recent run
) -> str:
    """Get current pipeline status for a run."""
```

**Return value:**
```json
{
  "run_id": "20260323-120000-recipe-app",
  "status": "running",
  "current_phase": "2b",
  "phases_complete": ["1a", "1b", "2a"],
  "deploy_url": null,
  "error": null,
  "last_updated": "2026-03-23T12:05:00Z"
}
```

`status` values: `"running"` | `"waiting_approval"` | `"completed"` | `"failed"`

---

### `check_environment`

```python
@mcp.tool()
async def check_environment(
    deploy_target: str = "vercel",    # Check prereqs for this target
) -> str:
    """Check that required tools and credentials are available.

    Returns a structured report of what is present, missing, and how to fix gaps.
    """
```

**Return value:**
```json
{
  "ready": false,
  "checks": [
    {"name": "node", "status": "ok", "version": "20.19.0"},
    {"name": "npm", "status": "ok", "version": "10.2.0"},
    {"name": "ANTHROPIC_API_KEY", "status": "ok"},
    {"name": "vercel-cli", "status": "missing", "fix": "npm install -g vercel"},
    {"name": "VERCEL_TOKEN", "status": "missing", "fix": "Run: vercel login"}
  ],
  "blocking": ["vercel-cli", "VERCEL_TOKEN"]
}
```

---

### `start_dev_server` / `stop_dev_server`

```python
@mcp.tool()
async def start_dev_server(
    run_id: str,       # Which run's project to serve
    port: int = 3000,  # Default; auto-increments on conflict (Next.js behavior)
) -> str:
    """Start the local Next.js dev server for a generated app.

    Returns the localhost URL for preview.
    """

@mcp.tool()
async def stop_dev_server(
    run_id: str,
) -> str:
    """Stop a running dev server by run_id."""
```

**`start_dev_server` return value:**
```json
{
  "url": "http://localhost:3000",
  "pid": 12345,
  "run_id": "20260323-120000-recipe-app",
  "project_dir": "/path/to/output/RecipeApp"
}
```

---

### `approve_gate` (public MCP surface)

Existing internal tool; expose with same signature in the public MCP server:

```python
@mcp.tool()
async def approve_gate(
    phase: str,         # Phase name
    summary: str,       # What was completed
    artifacts: str,     # List of artifacts produced
    next_action: str,   # What happens next if approved
) -> str:
    """Human approval gate between pipeline phases (interactive mode).

    Returns: APPROVED | REJECTED | FEEDBACK:<text>
    """
```

---

### `list_runs`

```python
@mcp.tool()
async def list_runs() -> str:
    """List all previous pipeline runs with their status and deploy URLs."""
```

**Return value:**
```json
{
  "runs": [
    {
      "run_id": "20260323-120000-recipe-app",
      "idea": "A recipe sharing app",
      "status": "completed",
      "deploy_url": "https://recipe-app.vercel.app",
      "created_at": "2026-03-23T12:00:00Z"
    }
  ]
}
```

---

## Deploy Target Selection UX

### Recommended Pattern: Single Parameter, Adapter per Target

The user specifies `deploy_target` in `generate_app`. The factory selects the matching deploy adapter. No interactive wizard needed at call time — Claude can ask conversationally if the parameter is absent.

```
deploy_target = "vercel"       → VercelDeployAdapter    (v1.0, extend)
deploy_target = "cloud-run"    → CloudRunAdapter         (NEW)
deploy_target = "local-only"   → LocalOnlyAdapter        (NEW — skip deploy phase)
```

### Credential Requirements per Target

| Target | Required Env Vars | Required CLIs | Automation Complexity |
|--------|-------------------|---------------|-----------------------|
| `vercel` | `VERCEL_TOKEN` | `vercel` (npm) | Low — existing |
| `cloud-run` | `GOOGLE_CLOUD_PROJECT` | `gcloud` (Google Cloud SDK) | Medium — single command |
| `local-only` | none | `node` 18+, `npm` | Low |

### Deploy Complexity Assessment

**Vercel (existing):** Zero-config for Next.js. `vercel deploy --prod` is one command. Fully automated. HIGH confidence.

**Google Cloud Run (new):** MEDIUM confidence / MEDIUM complexity. `gcloud run deploy --source . --region us-central1 --allow-unauthenticated` is a single command that builds via Cloud Build and deploys. Next.js requires `output: 'standalone'` in `next.config.js`. Official Next.js + Cloud Run template exists (`nextjs/deploy-google-cloud-run`). Achievable in v2.0.

**AWS Amplify (deferred):** LOW confidence / HIGH complexity. Amplify's programmatic API for Next.js SSR requires Git-connected apps via Amplify Console — `amplify publish` does NOT work for SSR deployments. Alternative is containerizing and pushing to ECR + App Runner. This is significantly more complex than the other targets. Recommend deferring to v3.0 or replacing with AWS App Runner.

---

## User Environment Setup Expectations

Users installing via `claude mcp add` expect:

1. **Zero Python setup** — They should not need to know Python exists. `uvx web-app-factory` handles Python transparently. Users without `uv` get a clear error with the install URL (https://docs.astral.sh/uv/).

2. **No manual JSON editing** — `claude mcp add web-app-factory -- uvx web-app-factory` is the full install command. The server detects missing env vars at first tool call and returns actionable guidance, not a crash.

3. **API key via environment** — `ANTHROPIC_API_KEY` read from environment automatically (matches SDK default behavior). If missing, `check_environment` returns a failure with exact fix instruction.

4. **Deploy credentials on demand** — Don't require all credentials at install time. Only check deploy target credentials when `generate_app` is called with that target. `check_environment` surfaces gaps proactively.

5. **Node.js is a hard dependency** — Next.js generation requires Node.js 18+. Cannot be shimmed. `check_environment` must catch and report this clearly if absent.

---

## Feature Dependencies (v2.0)

```
generate_app (MCP tool, new)
    → factory.py (CLI, exists) — wraps existing CLI
    → pipeline (contract_pipeline_runner, exists)
    → deploy_target adapter (NEW)
        → VercelDeployAdapter (extend v1.0)
        → CloudRunAdapter (NEW — gcloud CLI)
        → LocalOnlyAdapter (NEW — skip deploy phase)

get_status (MCP tool, new)
    → pipeline_state.py (read-only, exists)

approve_gate (MCP tool, expose existing)
    → factory_mcp_server.py:approve_gate (exists — expose in public server)

check_environment (MCP tool, new)
    → startup_preflight.py (extend)
    → deploy-target-specific checks (new per target)

start_dev_server / stop_dev_server (MCP tools, new)
    → generated project structure (package.json with "dev": "next dev")
    → subprocess management + port detection

list_runs (MCP tool, new)
    → output/ directory + pipeline_state.py

MCP App packaging (mcpb + uv)
    → pyproject.toml (entry_points / scripts)
    → manifest.json (NEW — mcpb bundle spec)
    → UV runtime (experimental v0.4+)
```

### Risks from v1.0 Dependencies

| v2.0 Feature | v1.0 Dependency | Risk |
|--------------|----------------|------|
| `generate_app` | `factory.py` (parse_args, main) | Low — wraps existing CLI |
| `get_status` | `pipeline_state.py` | Low — read-only access |
| Cloud Run adapter | `tools/gates/deployment_gate.py` | Med — gate must accept Cloud Run URLs, not just Vercel URLs |
| `start_dev_server` | Generated project `package.json` | Low — `npm run dev` is standard Next.js |
| `check_environment` | `startup_preflight.py` | Low — additive extension |
| MCP packaging | `pyproject.toml` | Low — add `[project.scripts]` entry point |

---

## MVP Recommendation (v2.0)

### Must Ship

1. `generate_app` MCP tool — wraps existing CLI, returns run_id immediately
2. `get_status` MCP tool — reads pipeline_state.py
3. `approve_gate` MCP tool — expose existing internal tool
4. `check_environment` MCP tool — preflight for node, API keys, deploy CLI
5. `start_dev_server` / `stop_dev_server` — local preview before deploy
6. `list_runs` — discovery of prior runs
7. MCP App packaging — `mcpb`-compatible manifest + `uvx` install path (`pyproject.toml` entry point)
8. Google Cloud Run adapter — `gcloud run deploy --source` path
9. `local-only` deploy target — skip deploy phase, return local URL
10. Dual-mode (auto vs interactive) — `mode` parameter on `generate_app`
11. Cloud Run URL support in deployment gate — extend gate to accept `*.run.app` URLs

### Defer to v3.0

- AWS Amplify adapter — Git-based deploy requirement makes automation non-trivial
- MCP App UI (interactive approval cards via `ui://` iframe) — spec too new, client behavior varies
- MCP Tasks async protocol (SEP-1686) — upgrade path after basic polling works
- Windows native support — doubles testing matrix
- Azure Static Web Apps — outside stated scope

---

## Sources

- MCP Apps announcement: [https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/)
- Desktop Extensions (.mcpb): [https://www.anthropic.com/engineering/desktop-extensions](https://www.anthropic.com/engineering/desktop-extensions)
- MCPB bundle spec: [https://github.com/modelcontextprotocol/mcpb](https://github.com/modelcontextprotocol/mcpb)
- MCP Tasks (SEP-1686) call-now fetch-later: [https://agnost.ai/blog/long-running-tasks-mcp/](https://agnost.ai/blog/long-running-tasks-mcp/)
- FastMCP background tasks (`task=True`): [https://gofastmcp.com/servers/tasks](https://gofastmcp.com/servers/tasks)
- `claude mcp add` command reference: [https://code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp)
- MCP tool best practices (contracts, idempotency): [https://mcp-best-practice.github.io/mcp-best-practice/best-practice/](https://mcp-best-practice.github.io/mcp-best-practice/best-practice/)
- Cloud Run + Next.js quickstart: [https://docs.cloud.google.com/run/docs/quickstarts/frameworks/deploy-nextjs-service](https://docs.cloud.google.com/run/docs/quickstarts/frameworks/deploy-nextjs-service)
- AWS Amplify + Next.js SSR limitations: [https://docs.aws.amazon.com/amplify/latest/userguide/deploy-nextjs-app.html](https://docs.aws.amazon.com/amplify/latest/userguide/deploy-nextjs-app.html)
- Next.js deployment comparison 2026: [https://dev.to/zahg_81752b307f5df5d56035/the-complete-guide-to-deploying-nextjs-apps-in-2026-vercel-self-hosted-and-everything-in-between-48ia](https://dev.to/zahg_81752b307f5df5d56035/the-complete-guide-to-deploying-nextjs-apps-in-2026-vercel-self-hosted-and-everything-in-between-48ia)
- MCP Apps interactive patterns: [https://workos.com/blog/2026-01-27-mcp-apps](https://workos.com/blog/2026-01-27-mcp-apps)
- MCP server best practices 2026: [https://www.cdata.com/blog/mcp-server-best-practices-2026](https://www.cdata.com/blog/mcp-server-best-practices-2026)

---

---

# v1.0 Feature Research (preserved)

**Domain:** Automated web application generation pipeline (idea → deployed web app)
**Researched:** 2026-03-21
**Confidence:** HIGH (pipeline features), MEDIUM (generated app features), HIGH (deployment features)

## Context

This system forks ios-app-factory's proven multi-phase pipeline to produce web apps. The "user" of
this system is the pipeline operator (developer/AI agent running the factory), not end-users of the
generated app. Features therefore span two dimensions:

1. **Pipeline features** — what the factory pipeline itself does (orchestration, gates, state)
2. **Generated app features** — what the output web app contains (quality, accessibility, SEO)

The ios-app-factory has 68 phase executors, 26 quality gates, 6 specialized agents. The web
adaptation needs to map each iOS-specific component to a web equivalent, not rebuild from scratch.

## Feature Landscape

### Table Stakes — Pipeline

Features a generation pipeline must have to be considered functional. Missing any = pipeline is
broken or unreliable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Phase-ordered execution | Output of phase N is input to phase N+1; order violations corrupt downstream artifacts | LOW | Reuse ios-app-factory phase ordering enforcement via `contract_pipeline_runner.py` |
| State persistence (`state.json`) | Pipeline must survive interruption; re-running from scratch on failure is unacceptable for multi-hour pipelines | LOW | Direct reuse: `pipeline_state.py`, `activity-log.jsonl` |
| Resumability (continue from last completed phase) | LLM calls fail, timeouts occur, costs accumulate — operator must resume not restart | MEDIUM | Reuse ios-app-factory resume logic; web phases have fewer steps so simpler state graph |
| Fail-closed quality gates | Gates that fail silently produce low-quality output that looks like it passed; operators lose trust in pipeline | MEDIUM | Gate policy reuse: `gate_policy.py`; replace iOS gate implementations with web equivalents |
| Deliverable manifest (not just required_files) | Gate-gaming: if gates only check file existence, LLM produces minimum content; quality criteria prevent this | MEDIUM | Direct reuse of ios-app-factory quality-driven execution model (45-quality-driven-execution.md) |
| Quality self-assessment before gate submission | LLM reverses from gate → minimum output without this; mandatory self-eval catches gaps before the gate does | MEDIUM | Reuse: `quality-self-assessment-{phase_id}.json` pattern |
| MCP approval gates (human-in-the-loop) | Deployment and legal phases require human sign-off; automated pass-through is unsafe | LOW | Direct reuse: `factory_mcp_server.py`, `approve_gate.py` |
| CLI entry point (`factory.py --idea "..." --project-dir ./output/AppName`) | Operators need a single command to initiate the pipeline | LOW | New entry point mirroring ios-app-factory pattern |
| Governance bypass detection | LLM agents will take shortcuts if not guarded; runtime guards prevent phase skipping, direct file edits, gate bypasses | HIGH | Reuse: `governance_monitor.py`, `pipeline-intent-guard.py` |
| ANDON / escalation on repeated failure | Meta-ANDON prevents infinite retry loops; after N failures, escalate to human rather than continue burning tokens | MEDIUM | Reuse: `andon_escalation.py`, `70-kaizen-learning.md` patterns |

### Table Stakes — Generated App

Features that any generated web app must have to be considered shippable. Missing = app is broken
for a segment of users or fails production requirements.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Responsive design (mobile + desktop) | >60% of web traffic is mobile; non-responsive app fails the majority of users | MEDIUM | Next.js + Tailwind CSS default; generate with mobile-first approach |
| WCAG 2.1 AA accessibility | Legal requirement in many jurisdictions; >15% of users have some disability | MEDIUM | Lighthouse accessibility audit gate; axe-core integration |
| Valid HTML / no broken links | Crawlers and screen readers break on invalid markup; broken links damage SEO and UX | LOW | HTML validator + link checker in quality gate |
| Security headers (CSP, HSTS, X-Frame-Options) | Missing headers = instant fail on security scanners; OWASP baseline requirement | LOW | Next.js `next.config.js` headers; gate checks via securityheaders.com API or `@next/security-headers` |
| Environment variable safety (no secrets in output) | Generated code must not embed API keys, tokens, or credentials | LOW | Gate: scan output for known secret patterns before deployment |
| Error boundaries / 404 page | Missing = unhandled errors surface raw stack traces to users | LOW | Next.js default `not-found.tsx` and `error.tsx` |
| Working build (`next build` passes) | App that does not build cannot be deployed | LOW | Build gate: `next build` exit code 0 required |
| TypeScript type-check passes | Type errors indicate broken logic; deploy with type errors is shipping known bugs | LOW | `tsc --noEmit` as pre-deploy gate |
| Privacy policy + terms of service pages | Legal requirement for any app collecting user data; required by Vercel ToS | MEDIUM | Legal phase generates from template (ios-app-factory pattern); web-adapted templates |

### Table Stakes — Deployment

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Automated deployment to Vercel | Manual deployment defeats the purpose of a factory | LOW | Vercel CLI: `vercel --prod`; project auto-provisioned via API |
| Preview URL per run | Operator needs to verify the deployed result before considering pipeline complete | LOW | Vercel preview deployment; URL captured in `state.json` |
| Deployment URL in pipeline output | Operator must know where the app lives without searching Vercel dashboard | LOW | Write deployment URL to `docs/pipeline/deployment.json` |
| Build/deploy failure surfaces as gate failure | Silent deploy failures leave pipeline in ambiguous state | LOW | Deploy gate: check Vercel deployment status API |

### Differentiators — Pipeline

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Market validation phase before code generation | Lovable/Bolt skip idea validation entirely; factory prevents building wrong thing | HIGH | Phase 1: competitor analysis, user persona, Go/No-Go gate before writing code |
| Spec-agent produces structured PRD before build | "Code from prompt" produces inconsistent output; structured spec creates reproducible builds | HIGH | Spec phase generates PRD with MoSCoW classification, tech feasibility memo, UI component inventory |
| Multi-agent specialization (spec/build/test/legal/deploy agents) | Single-agent generation degrades on complex apps ("70% problem"); specialized agents maintain context | HIGH | Reuse ios-app-factory agent specialization pattern; swap iOS agents for web agents |
| Deliverable quality criteria (not just file existence) | All competing generators check "did it produce output?"; factory checks "is the output good?" | HIGH | Each deliverable has `quality_criteria` array; self-assessment before gate |
| Resumable pipeline (human reviews intermediate artifacts) | Lovable/Bolt are one-shot or require manual retry; factory allows inspect-and-continue at each phase | MEDIUM | MCP approval gates between phases enable human review |
| Automated Lighthouse gate (performance + accessibility + SEO + best practices) | No AI generator runs Lighthouse as a blocking gate; factory ships only apps that pass | MEDIUM | Lighthouse CI integration; configurable thresholds (performance ≥85, accessibility ≥90, SEO ≥90) |
| Legal document generation (ToS + privacy policy) | Generators ship apps without legal documents; factory includes legal phase | MEDIUM | Web-adapted legal templates from ios-app-factory; jurisdiction-aware generation |
| Governance audit trail (`activity-log.jsonl`) | No generator produces an immutable audit log of every phase decision | LOW | Direct reuse; log is valuable for debugging and compliance |
| Gate-gaming prevention (Blind Gate / quality-driven model) | LLMs optimize for gate conditions, not quality; anti-gaming architecture produces better output | HIGH | Quality-driven execution (45-quality-driven-execution.md): purpose-first, deliverables-second, gates-last |

### Differentiators — Generated App

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Lighthouse score ≥85 all categories on first deploy | v0 produces good UI but no performance guarantee; factory ships with verified scores | MEDIUM | Lighthouse gate; auto-remediation suggestions if score fails |
| Open Graph / social meta tags generated | Most generators omit social sharing metadata; factory generates for every app | LOW | og:title, og:description, og:image, Twitter card in every Next.js layout |
| Sitemap + robots.txt generated | SEO baseline; most generators skip this | LOW | Next.js `sitemap.ts` + `robots.ts` generation |
| Structured data (JSON-LD) for primary content type | Enhances search result appearance; competitors omit this | MEDIUM | Generate appropriate schema.org markup based on app type |
| Analytics integration hook | Factory apps include analytics scaffolding (Vercel Analytics or Google Analytics placeholder) | LOW | Optional; scaffolded but not required — operator configures API key |

### Anti-Features (v1.0)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time streaming output during generation | "See progress as it happens" feels responsive | Streaming mid-phase corrupts state; phase must complete atomically before state is written | Emit phase-start/complete events to `activity-log.jsonl`; operator can tail the log |
| Custom framework support (Vue, Svelte, Angular) | Flexibility feels valuable | Multi-framework support multiplies gate complexity; maintenance cost is 3-5x | Next.js only for v1; framework flexibility deferred |
| Database provisioning (PostgreSQL, MySQL) | "Full-stack app" sounds complete | Database setup requires secrets management, migration system, schema design agent — doubles pipeline scope | Supabase client-side SDK as optional add-on |
| Authentication system generation | "Users need to log in" | Auth is security-critical and jurisdiction-sensitive; auto-generated auth with LLM is risky | Ship auth-ready scaffolding (NextAuth placeholders); operator configures |
| Visual design customization during pipeline | "Make it match my brand" mid-run | Interrupting generation for design feedback creates resumability complexity | Design tokens generated in spec phase based on brand description |
| One-click "regenerate everything" | Appeals as a recovery mechanism | Full regeneration is expensive and loses intermediate human approvals | Resume from specific phase |
| Parallel phase execution | Appears to speed up pipeline | Phase N output is phase N+1 input; cross-phase ordering must remain serial | Within-phase parallelism is fine |

## Feature Dependencies (v1.0)

```
Idea Input
    └──requires──> Market Validation Phase
                       └──requires──> Spec Phase
                                          └──requires──> Build Phase
                                                             └──requires──> Quality Gate Suite
                                                                                └──requires──> Legal Phase
                                                                                                   └──requires──> Deploy Phase
                                                                                                                      └──requires──> Lighthouse Gate (on preview URL)
```

## Sources (v1.0)

- [v0 vs Bolt vs Lovable comparison 2026](https://freeacademy.ai/blog/v0-vs-bolt-vs-lovable-ai-app-builders-comparison-2026)
- [Lovable vs Bolt vs v0 feature comparison](https://uibakery.io/blog/bolt-vs-lovable-vs-v0)
- [Lighthouse CI integration guide](https://www.cognixia.com/blog/integrating-lighthouse-test-automation-into-your-ci-cd-pipeline/)
- [Google Lighthouse overview](https://developer.chrome.com/docs/lighthouse/overview/)
- [Vercel Lighthouse integration](https://vercel.com/integrations/lighthouse)
- [Spec-driven development with AI — GitHub Blog](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
- [Agentic design patterns 2026 — SitePoint](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/)
- [Top AI app builders 2026 — Lovable guide](https://lovable.dev/guides/top-ai-platforms-app-development-2026)

---
*Last updated: 2026-03-23 (v2.0 milestone additions)*
