# Feature Research

**Domain:** Automated web application generation pipeline (idea → deployed web app)
**Researched:** 2026-03-21
**Confidence:** HIGH (pipeline features), MEDIUM (generated app features), HIGH (deployment features)

---

## Context

This system forks ios-app-factory's proven multi-phase pipeline to produce web apps. The "user" of
this system is the pipeline operator (developer/AI agent running the factory), not end-users of the
generated app. Features therefore span two dimensions:

1. **Pipeline features** — what the factory pipeline itself does (orchestration, gates, state)
2. **Generated app features** — what the output web app contains (quality, accessibility, SEO)

The ios-app-factory has 68 phase executors, 26 quality gates, 6 specialized agents. The web
adaptation needs to map each iOS-specific component to a web equivalent, not rebuild from scratch.

---

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

---

### Differentiators — Pipeline

Features that distinguish this pipeline from manual development or simpler generators (Lovable,
Bolt.new, v0). These are what make "web app factory" better than "vibe coding."

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

### Differentiators — Deployment

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Lighthouse audit against Vercel preview URL (not localhost) | Running Lighthouse on localhost misses CDN, network conditions; factory audits real deployment | MEDIUM | Vercel preview URL captured in state; Lighthouse CI runs against it |
| Deployment URL written to project output for downstream use | Enables integration with other tools (email notification, monitoring setup) | LOW | `docs/pipeline/deployment.json` with preview + production URLs |
| Vercel project auto-provisioned (no manual dashboard setup) | Manual project creation breaks factory automation | MEDIUM | Vercel CLI `vercel link` or API project creation |

---

### Anti-Features

Features that seem useful but create problems in the context of a generation pipeline.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time streaming output during generation | "See progress as it happens" feels responsive | Streaming mid-phase corrupts state; phase must complete atomically before state is written | Emit phase-start/complete events to `activity-log.jsonl`; operator can tail the log |
| Custom framework support (Vue, Svelte, Angular) | Flexibility feels valuable | Multi-framework support multiplies gate complexity (each framework needs its own build gate, Lighthouse config, deploy adapter); maintenance cost is 3-5x | Next.js only for v1; framework flexibility deferred until core pipeline is stable |
| Database provisioning (PostgreSQL, MySQL) | "Full-stack app" sounds complete | Database setup requires secrets management, migration system, schema design agent — doubles pipeline scope; v1 generates serverless API routes which cover most use cases | Supabase client-side SDK as optional add-on; full database provisioning is v2 |
| Authentication system generation | "Users need to log in" | Auth is security-critical and jurisdiction-sensitive (GDPR, CCPA data residency); auto-generated auth with LLM is risky without dedicated security review gate | Ship auth-ready scaffolding (Clerk or NextAuth placeholders); operator configures and audits |
| Visual design customization during pipeline | "Make it match my brand" mid-run | Interrupting generation for design feedback creates resumability complexity; pipeline needs deterministic phases | Design tokens generated in spec phase based on brand description; operator applies post-deploy |
| One-click "regenerate everything" | Appeals as a recovery mechanism | Full regeneration from scratch is expensive (LLM tokens) and loses intermediate human approvals | Resume from specific phase: `factory.py --resume-from spec --project-dir ./output/AppName` |
| Parallel phase execution | Appears to speed up pipeline | Phase N output is phase N+1 input; true parallelism requires dependency graph analysis and creates state race conditions | Within-phase parallelism is fine (multiple agents in same phase); cross-phase ordering must remain serial |
| Automated App Store / marketplace submission | Seems like natural extension | Web apps don't have an App Store; the deployment target is a URL, not a review queue. Adding store concepts pollutes the web-native model | Keep web-native: deploy → URL is the whole delivery model |

---

## Feature Dependencies

```
Idea Input
    └──requires──> Market Validation Phase
                       └──requires──> Spec Phase
                                          └──requires──> Build Phase
                                                             └──requires──> Quality Gate Suite
                                                                                └──requires──> Legal Phase
                                                                                                   └──requires──> Deploy Phase
                                                                                                                      └──requires──> Lighthouse Gate (on preview URL)

State Persistence
    └──enables──> Resumability
    └──enables──> Audit Trail

Quality Self-Assessment
    └──required-before──> Gate Submission
    └──prevents──> Gate-Gaming

MCP Approval Gates
    └──wraps──> Legal Phase (human sign-off)
    └──wraps──> Deploy Phase (human sign-off)

Vercel Preview Deployment
    └──enables──> Lighthouse Gate on real URL
    └──enables──> Human Review before production promotion
```

### Dependency Notes

- **Build Phase requires Spec Phase:** The build agent consumes the structured PRD and tech feasibility memo produced by the spec agent; without spec, build agent produces inconsistent output.
- **Lighthouse Gate requires Vercel Preview Deployment:** Lighthouse against localhost misses CDN behavior, network conditions, and Vercel-specific optimizations. The gate must run against the deployed preview URL, so preview deployment is a prerequisite.
- **Legal Phase requires Build Phase:** Legal documents reference specific app features, data collected, and service description — these come from the build output, not just the idea.
- **Quality Self-Assessment requires Deliverable Manifest:** Self-assessment is driven by `quality_criteria` in the deliverable manifest. The criteria must exist and be specific (not generic) for self-assessment to catch gaps.
- **MCP Approval Gates require Human Operator:** Legal and deploy gates are user-exclusive; the pipeline must pause and wait. This is a deliberate safety feature, not a limitation.
- **Governance Bypass Detection requires State Persistence:** The governance monitor detects when agents attempt to read `state.json` directly or skip phases; it requires state to be the single source of truth.

---

## MVP Definition

### Launch With (v1)

Minimum viable pipeline that produces a deployable, production-quality web app from an idea.

- [ ] **Pipeline orchestration reused from ios-app-factory** — contract_pipeline_runner, pipeline_state, governance_monitor, activity-log; zero net-new infrastructure
- [ ] **4-phase pipeline contract (YAML):** Idea Validation → Spec → Build → Deploy; legal phase present but lightweight for v1
- [ ] **Phase executors (web-specific):** Replace all iOS executors with web equivalents; Next.js scaffolding, component generation, serverless API route generation
- [ ] **Build gate:** `next build` + `tsc --noEmit` pass; no broken links; no secrets in output
- [ ] **Lighthouse gate on Vercel preview URL:** Performance ≥85, Accessibility ≥90, SEO ≥85, Best Practices ≥90
- [ ] **Security headers gate:** CSP, HSTS, X-Content-Type-Options present
- [ ] **Vercel deployment automation:** `vercel --prod` in deploy phase; URL captured in state
- [ ] **Legal document generation:** Privacy policy + ToS generated from web templates; links in app footer
- [ ] **MCP approval gates:** Human sign-off required for deploy phase
- [ ] **Quality self-assessment per phase:** Every phase produces `quality-self-assessment-{id}.json` before gate submission

### Add After Validation (v1.x)

- [ ] **Open Graph + sitemap + robots.txt generation** — SEO baseline; add once build phase is stable
- [ ] **Structured data (JSON-LD)** — Add once core output quality is validated
- [ ] **Analytics scaffolding** — Vercel Analytics integration; add when operators want usage data
- [ ] **Lighthouse score remediation suggestions** — If gate fails, generate specific fix instructions; add when gate failure patterns are understood
- [ ] **Resume-from-phase CLI flag** — `--resume-from build`; add after resumability is battle-tested

### Future Consideration (v2+)

- [ ] **Database provisioning (Supabase integration)** — Doubles scope; defer until v1 output quality is validated
- [ ] **Authentication scaffolding (Clerk/NextAuth)** — Security-critical; requires dedicated security review gate; defer
- [ ] **Multi-framework support (Vue, Svelte)** — Multiplies maintenance; only after Next.js pipeline is stable
- [ ] **Visual regression testing gate** — Screenshots of generated UI vs spec wireframes; high value but requires Playwright setup
- [ ] **Competitor monitoring / SEO tracking** — Post-deploy monitoring; not in generation scope

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Phase orchestration (reuse from ios-app-factory) | HIGH | LOW | P1 |
| State persistence + resumability | HIGH | LOW | P1 |
| Web phase executors (spec, build, deploy agents) | HIGH | HIGH | P1 |
| Build gate (next build + tsc) | HIGH | LOW | P1 |
| Lighthouse gate on preview URL | HIGH | MEDIUM | P1 |
| Security headers gate | HIGH | LOW | P1 |
| Vercel deployment automation | HIGH | LOW | P1 |
| Legal document generation | MEDIUM | MEDIUM | P1 |
| MCP approval gates | HIGH | LOW | P1 |
| Quality self-assessment per phase | HIGH | MEDIUM | P1 |
| Governance bypass detection (reuse) | HIGH | LOW | P1 |
| Market validation phase | HIGH | MEDIUM | P1 |
| Open Graph / sitemap / robots.txt | MEDIUM | LOW | P2 |
| Analytics scaffolding | MEDIUM | LOW | P2 |
| Structured data (JSON-LD) | MEDIUM | MEDIUM | P2 |
| Lighthouse remediation suggestions | MEDIUM | MEDIUM | P2 |
| Resume-from-phase CLI | MEDIUM | MEDIUM | P2 |
| Database provisioning | HIGH | HIGH | P3 |
| Authentication scaffolding | HIGH | HIGH | P3 |
| Visual regression testing gate | MEDIUM | HIGH | P3 |
| Multi-framework support | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v1 launch — pipeline is broken or untrustworthy without it
- P2: Should have — adds significant value, add in v1.x after core is validated
- P3: Nice to have — defer until product-market fit established

---

## Competitor Feature Analysis

The relevant competitors are: (a) manual development, (b) one-shot AI generators (Lovable, Bolt.new, v0), (c) spec-driven AI tools (GitHub Copilot Workspace).

| Feature | Manual Development | Lovable / Bolt.new | v0 (Vercel) | Web App Factory (this) |
|---------|--------------------|---------------------|-------------|------------------------|
| Idea → deployed app | Hours to weeks | Minutes (one-shot) | Frontend only, no deploy | Hours (pipeline) |
| Market validation before code | Human judgment | None | None | Structured phase with Go/No-Go gate |
| Spec-driven PRD | Manual PRD | None | None | Spec agent produces structured PRD |
| Multi-agent specialization | Human team | Single LLM | Single LLM | Specialized agents per phase |
| Lighthouse gate (blocking) | Manual or CI add-on | None | None | Built-in, blocking |
| Accessibility (WCAG) gate | Manual | None | Partial (UI quality) | Built-in axe-core + Lighthouse |
| Security headers gate | Manual | None | None | Built-in |
| Legal document generation | Manual or lawyer | None | None | Automated with templates |
| Pipeline resumability | N/A | No (restart from scratch) | No | Phase-level resume |
| Audit trail | Version control | None | None | Immutable activity-log.jsonl |
| Human approval gates | Natural | None | None | MCP gates for legal + deploy |
| Quality self-assessment | Code review | None | None | Per-phase, mandatory |
| Gate-gaming prevention | N/A | N/A | N/A | Governance monitor + quality-driven model |
| Database + auth | Full support | Supabase (Lovable) | None | Serverless API routes only (v1) |

**Key conclusion:** Competing generators optimize for speed-to-first-deploy. Web App Factory optimizes for quality-of-first-deploy. The differentiator is the quality gate stack: market validation + Lighthouse + WCAG + security headers + legal — all blocking, not advisory.

---

## Sources

- [v0 vs Bolt vs Lovable comparison 2026](https://freeacademy.ai/blog/v0-vs-bolt-vs-lovable-ai-app-builders-comparison-2026)
- [Lovable vs Bolt vs v0 feature comparison](https://uibakery.io/blog/bolt-vs-lovable-vs-v0)
- [Lighthouse CI integration guide](https://www.cognixia.com/blog/integrating-lighthouse-test-automation-into-your-ci-cd-pipeline/)
- [Google Lighthouse overview](https://developer.chrome.com/docs/lighthouse/overview/)
- [Vercel Lighthouse integration](https://vercel.com/integrations/lighthouse)
- [Automated Lighthouse score on Vercel PRs](https://dev.to/oskarahl/automated-lighthouse-score-on-your-pr-with-vercel-and-github-actions-2ng2)
- [Spec-driven development with AI — GitHub Blog](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
- [Spec-driven development best practices](https://www.softwareseni.com/spec-driven-development-in-2025-the-complete-guide-to-using-ai-to-write-production-code/)
- [Agentic design patterns 2026 — SitePoint](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/)
- [Next.js CI/CD with Vercel complete guide](https://codezup.com/deploy-nextjs-14-vercel-cicd/)
- [Top AI app builders 2026 — Lovable guide](https://lovable.dev/guides/top-ai-platforms-app-development-2026)
- [Best AI web app builders — Flatlogic](https://flatlogic.com/blog/top-8-ai-web-app-builders/)

---
*Feature research for: Automated web application generation pipeline (idea → deployed web app)*
*Researched: 2026-03-21*
