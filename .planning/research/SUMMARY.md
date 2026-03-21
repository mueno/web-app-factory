# Project Research Summary

**Project:** web-app-factory
**Domain:** Automated web application generation pipeline (Python orchestration + Next.js/Vercel output)
**Researched:** 2026-03-21
**Confidence:** HIGH

## Executive Summary

Web App Factory is a fork of ios-app-factory's proven multi-phase pipeline architecture, retargeted to produce deployable Next.js web applications from a natural-language idea prompt. The core insight from research is that the majority of the hard infrastructure — YAML contract runner, state management, governance monitor, MCP approval gates, quality-driven execution model — is domain-agnostic and can be copied verbatim from ios-app-factory. The web-specific work is confined to: a new pipeline YAML contract (5 phases instead of 11), web-focused phase executors (spec, scaffold, build, legal, deploy agents), and a new gate suite targeting npm builds, Lighthouse scores, security headers, and Vercel deployment.

The recommended stack is unambiguous and well-researched at HIGH confidence: Next.js 16.2 + React 19.2 + TypeScript 5.1 + Tailwind CSS v4 + shadcn/ui for the generated apps; Python 3.10+ + claude-agent-sdk 0.1.50 + fastmcp 3.1.1 + uv for the pipeline. All versions are current-stable as of 2026-03-21. The competing generators (Lovable, Bolt.new, v0) optimize for speed-to-first-deploy; this factory optimizes for quality-of-first-deploy through blocking gates: Lighthouse perf/a11y/SEO, WCAG axe-core, security headers, npm package validation, and legal document generation. These are the differentiators.

The dominant risk is gate-gaming: LLMs optimize for gate conditions, producing hollow deliverables that pass existence checks but contain no real content. This is ios-app-factory's most destructive documented pattern and must be built into the contract design from day one — not retrofitted. The second cluster of risks is web-specific: npm package hallucination (19.7% rate per USENIX Security 2025 research), Next.js client/server boundary misplacement silently degrading performance, environment variable leakage into client bundles, and a CVSS 9.1 middleware auth bypass (CVE-2025-29927) that LLMs will reproduce from pre-patch training data.

## Key Findings

### Recommended Stack

The pipeline runs on Python infrastructure inherited from ios-app-factory with no version changes needed. The generated app stack uses Next.js 16 which requires Node.js 20.9+ minimum (Node 18 was dropped). Two critical deprecations in Next.js 16 must be reflected in generated code: `middleware.ts` is replaced by `proxy.ts`, and `next lint` was removed so ESLint must be run directly. Tailwind CSS v4 uses CSS-first configuration (no `tailwind.config.js`), and the `@axe-core/react` package does not support React 18+ — only `@axe-core/playwright` works for accessibility testing.

**Core technologies:**
- **Next.js 16.2 / React 19.2**: Full-stack framework — App Router is default, Turbopack is stable, Cache Components replace the deprecated `experimental.ppr`
- **TypeScript 5.1+ / Zod v4**: Type safety at build time + runtime schema validation in Server Actions (types vanish at runtime)
- **Tailwind CSS v4 + shadcn/ui**: Styling — Oxide engine, CSS-first config; shadcn copies components as local files eliminating version conflicts
- **Vitest 4.x / Playwright 1.58.2**: Testing — Vitest replaces Jest completely (6x faster cold start, native ESM); Playwright for E2E and quality gates
- **Python 3.10+ / claude-agent-sdk 0.1.50 / fastmcp 3.1.1 / uv**: Pipeline — same versions as ios-app-factory; uv for lockfile-deterministic installs
- **Vercel CLI**: Programmatic deployment — `vercel pull → vercel build --prod → vercel deploy --prebuilt --prod`

### Expected Features

**Must have (table stakes) — Pipeline:**
- Phase-ordered execution with fail-closed quality gates — pipeline is unreliable without this
- State persistence (`state.json`) and resumability — multi-hour pipelines must survive interruption
- Deliverable manifest (quality criteria arrays) — prevents gate-gaming by driving from `purpose`, not gate conditions
- Quality self-assessment JSON before every gate submission — mandatory, not optional
- MCP approval gates for legal and deploy phases — human sign-off is a deliberate safety feature
- Governance bypass detection (`governance_monitor.py`) — inherited from ios-app-factory, reuse verbatim

**Must have (table stakes) — Generated App:**
- Responsive design, WCAG 2.1 AA accessibility, valid HTML, security headers, working build, type-check pass
- Privacy policy + terms of service — legal requirement and Vercel ToS requirement
- Automated Vercel deployment with preview URL captured in state

**Should have (competitive differentiators):**
- Market validation phase before code generation — Lovable/Bolt have none
- Lighthouse gate blocking deployment (perf ≥85, a11y ≥90, SEO ≥85) — no competitor does this
- Spec-agent producing structured PRD before build — creates reproducible, consistent output
- Open Graph / sitemap / robots.txt generation (v1.x)
- Structured data JSON-LD for primary content type (v1.x)

**Defer to v2+:**
- Database provisioning (Supabase/Neon) — doubles pipeline scope
- Authentication scaffolding (Clerk/NextAuth) — security-critical, needs dedicated review gate
- Multi-framework support (Vue, Svelte) — multiplies gate maintenance 3-5x
- Visual regression testing gate — high value but non-trivial Playwright setup

### Architecture Approach

The architecture has one governing principle: fork, don't rewrite. The domain-agnostic orchestration layer (`contract_pipeline_runner.py`, `pipeline_state.py`, `factory_mcp_server.py`, `governance_monitor.py`, `error_router.py`) is copied verbatim from ios-app-factory. The web-specific work is a new YAML contract (5 phases: 1a idea validation, 1b spec, 2a scaffold, 2b build, 3 ship), new phase executor Python files (one per phase), and a new gate suite. The YAML contract is the single source of truth — phase order, deliverables, quality criteria, and gate types all live there. Everything else is driven by the contract.

**Major components:**
1. **`factory.py` (adapted)** — CLI entry point; strips iOS flags, adds web flags (`--deploy-target`, `--framework`)
2. **`contracts/pipeline-contract.web.v1.yaml` (new)** — 5-phase web pipeline, deliverable manifests, gate definitions; must be written before any executor code
3. **`tools/phase_executors/phase_*.py` (all new)** — 7 executor files for phases 1a, 1b, 2a, 2b, 2c, 3a, 3b; each uses claude-agent-sdk; phase 2b (Build) is highest risk and most complex
4. **`tools/gates/` (partially new)** — `artifact_gate`, `build_gate`, `lighthouse_gate`, `security_headers_gate`, `link_integrity_gate`, `legal_gate`, `deploy_gate`; base gate infrastructure reused from ios-app-factory
5. **`pipeline_runtime/` (reuse verbatim)** — `governance_monitor`, `error_router`, `startup_preflight`
6. **`tools/` infrastructure (reuse verbatim)** — `contract_pipeline_runner`, `pipeline_state`, `factory_mcp_server`, `skill_evidence`

### Critical Pitfalls

1. **Gate-gaming — LLM optimizes for gate passage, not quality** — Drive phase execution from `purpose` and `deliverables`, never from gate conditions. Mandate `quality-self-assessment-{phase}.json` before every gate. Build deliverable quality criteria that check content, not just file existence. This must be in the contract from day one; retrofitting is expensive.

2. **npm package hallucination ("slopsquatting")** — 19.7% of LLM-generated package references are hallucinations; attackers register phantom names with malware. Add an `npm-verify` gate that validates each package against the npm registry API before `npm install`. Use an allowlist of approved packages for common patterns.

3. **Dual MCP implementation divergence** — When MCP tool and direct Python path implement the same operation, they silently diverge (ios-app-factory's documented failure: `state.json` never updated for weeks). Single implementation rule: MCP tool must call the same Python function as the direct path. Integration test must assert `state.json` updates after every `phase_reporter` MCP call.

4. **Next.js client/server component boundary misplacement** — LLMs add `"use client"` to layout or page components, silently disabling SSR, inflating JS bundles, and breaking metadata API. Static analysis gate: flag `"use client"` in `layout.tsx` or `page.tsx`. Build-agent prompt must include explicit boundary rules.

5. **Environment variable leakage** — Secret values accidentally prefixed with `NEXT_PUBLIC_` are inlined into client bundles and visible to all visitors. Static analysis gate: fail on `NEXT_PUBLIC_` + `KEY|SECRET|TOKEN|PRIVATE|PASSWORD|DATABASE` pattern. Never generate `.env.local` with real values; generate `.env.local.example` only.

6. **CVE-2025-29927 Middleware auth bypass (CVSS 9.1)** — LLMs reproduce vulnerable patterns trusting `x-middleware-subrequest` header. Security gate: scan `middleware.ts` for header-trust auth patterns. Pin Next.js to patched version.

## Implications for Roadmap

Based on the dependency graph from ARCHITECTURE.md and the pitfall-to-phase mapping from PITFALLS.md, the following phase structure is strongly recommended:

### Phase 1: Infrastructure Fork

**Rationale:** Everything downstream depends on the pipeline plumbing. The YAML contract runner, state management, and governance monitor must be working and tested before any executor code is written. The dual-implementation pitfall (Pitfall 3) must be caught at this phase with an integration test, not discovered weeks later.

**Delivers:** Working Python project (`pyproject.toml`, `uv.lock`), CLI stub (`factory.py`), copied pipeline infrastructure, placeholder YAML contract, dry-run test that executes without crashing, integration test asserting `state.json` updates after MCP `phase_reporter` call.

**Addresses:** Table-stakes pipeline features — state persistence, resumability, governance bypass detection, MCP approval gates (all reused, not rebuilt)

**Avoids:** Dual MCP implementation divergence (Pitfall 3), state file corruption (Pitfall 9)

**Research flag:** Standard patterns — well-documented in ios-app-factory codebase; no additional research needed.

---

### Phase 2: YAML Contract Design

**Rationale:** The contract is the schema everything else is built against. Phase executors, gates, and quality criteria are all slaves to what the YAML declares. This must be locked before any executor code is written, otherwise executor code and gate code will need constant revision as the contract evolves. Gate-gaming prevention (Pitfall 1) must be built into the contract structure at this phase.

**Delivers:** `contracts/pipeline-contract.web.v1.yaml` with all 5 phases fully specified: deliverable manifests with `quality_criteria` arrays, gate type definitions, purpose statements. Validated against jsonschema at startup.

**Addresses:** Gate-gaming prevention (deliverable manifests, quality criteria), phase ordering enforcement

**Avoids:** Gate-gaming (Pitfall 1) — quality criteria must be content-specific, not existence-only

**Research flag:** Needs deeper research into quality criteria design patterns. What makes a useful `quality_criterion` string vs. a vacuous one? Consider running a research-phase on "spec-driven quality gates for LLM pipelines."

---

### Phase 3: Spec Agent (Phases 1a + 1b)

**Rationale:** Market validation and spec generation produce no runnable code, so they are lower risk and a good place to validate the executor/gate framework before writing complex codegen. If Phase 1a quality criteria are wrong (trivially satisfied), better to discover that now than after Phase 2b (Build) runs.

**Delivers:** `phase_1a_idea.py` executor (idea validation, market research, Go/No-Go gate), `phase_1b_spec.py` executor (PRD, screen spec, tech feasibility memo), artifact gates for both phases, quality self-assessment for both phases.

**Addresses:** Market validation phase (differentiator), structured PRD before build (differentiator)

**Avoids:** Gate-gaming — first real-world test of quality criteria adequacy

**Research flag:** Standard patterns for spec-agent output quality. No deep research needed; ios-app-factory spec patterns are directly transferable.

---

### Phase 4: Scaffold + Build Agents (Phases 2a + 2b)

**Rationale:** This is the highest-risk phase in the entire roadmap. LLM-generated Next.js code has the highest variance. Three active pitfalls cluster here: npm hallucination, client/server boundary misplacement, and env var leakage. The build gate (npm build + tsc + production build, not dev-mode) must be added here. Note that `next build` production build is required — dev mode masks hydration errors, type errors, and missing env vars.

**Delivers:** `phase_2a_scaffold.py` (Next.js project init via `create-next-app`, CI YAML), `phase_2b_build.py` (page generation, components, API routes), `build_gate.py` (`npm run build` + `tsc --noEmit`), `npm_verify_gate.py` (registry validation before install), static analysis gates for `"use client"` boundary and env var exposure.

**Addresses:** Build phase (table stakes), responsive design, TypeScript type safety, working build

**Avoids:** npm package hallucination (Pitfall 2), client/server boundary (Pitfall 4), env var leakage (Pitfall 5), hydration errors (Pitfall 7), middleware auth bypass (Pitfall 6)

**Research flag:** Needs research-phase. Build-agent prompt engineering for Next.js App Router is non-trivial. Specific questions: (1) What constraints in the build-agent prompt most reliably prevent `"use client"` misplacement? (2) What package allowlist covers 80% of generated app patterns? (3) What Zod patterns for Server Action validation should be in the prompt template?

---

### Phase 5: Quality Gate Suite (Lighthouse + Security + Accessibility)

**Rationale:** These gates require a running Next.js server, so they are blocked on Phase 4 being stable. Lighthouse gate must run against the Vercel preview URL (not localhost) to catch CDN behavior. The axe-core gate must be in addition to Lighthouse — Lighthouse catches only 30-40% of accessibility issues (WebAIM 2025 data).

**Delivers:** `lighthouse_gate.py` (lhci autorun against preview URL, thresholds: perf ≥85, a11y ≥90, SEO ≥85), `security_headers_gate.py` (CSP, HSTS, X-Frame-Options, X-Content-Type-Options), `link_integrity_gate.py` (no 404s), axe-core integration in build gate.

**Addresses:** Lighthouse gate (differentiator), WCAG 2.1 AA (table stakes), security headers (table stakes)

**Avoids:** ARIA misuse (Pitfall 10), performance traps (`"use client"` on layouts, unoptimized images, font loading)

**Research flag:** Standard patterns — Lighthouse CI integration is well-documented. `@axe-core/playwright` integration is official and documented.

---

### Phase 6: Legal + Deploy (Phase 3)

**Rationale:** Legal documents reference specific app features from build output — the legal phase requires build output as input. Deploy gate must verify the Vercel URL is live (not just that `vercel deploy` returned 0). MCP approval gate wraps deployment — human sign-off required.

**Delivers:** `phase_3a_legal.py` (ToS + Privacy Policy from web templates), `phase_3b_deploy.py` (Vercel CLI deploy, GitHub Actions CI), `legal_gate.py` (file existence + 200+ word count), `deploy_gate.py` (HTTP 200 on Vercel URL within 30s), deployment URL written to `docs/pipeline/deployment.json`.

**Addresses:** Legal document generation (differentiator), automated Vercel deployment (table stakes), preview URL (table stakes)

**Avoids:** Vercel timeout (Pitfall 8) — static analysis for API routes; env var setup before deploy

**Research flag:** Web-adapted legal templates need to be written (ios-app-factory has iOS-specific templates). Consider whether a research-phase on GDPR/CCPA minimum requirements for a web app makes sense before writing templates.

---

### Phase 7: End-to-End Validation

**Rationale:** Run the full 5-phase pipeline against two real ideas of different types (content site and simple SaaS dashboard). Fix integration issues. Document runbook. Validate that quality self-assessments are non-trivial (not all ✅ with one-line justifications — warning sign from Pitfall 1).

**Delivers:** Two fully deployed web apps with Lighthouse scores meeting thresholds, runbook documentation, any gate threshold adjustments based on real runs.

**Addresses:** Resume-from-phase CLI validation, overall pipeline reliability

**Avoids:** "Looks done but isn't" checklist from PITFALLS.md — validate all 10 items on real output

**Research flag:** No additional research needed — this is empirical validation.

---

### Phase Ordering Rationale

- **Phases 1-2 must come first:** The infrastructure and contract are prerequisites for everything. Writing executors without a stable contract guarantees rework.
- **Phase 3 before Phase 4:** Spec agent is lower risk than build agent; validates the executor/gate framework before tackling the highest-risk phase.
- **Phase 5 after Phase 4:** Lighthouse and security gates require a running Next.js app. Cannot be implemented in isolation.
- **Phase 6 after Phase 4:** Legal documents reference build output; deploy requires a built app.
- **Phase 7 is the integration phase:** Cross-phase issues only surface at full pipeline runs.
- **Serial ordering is mandatory:** Cross-phase parallelism creates state race conditions (documented anti-feature in FEATURES.md). Within-phase agent parallelism is acceptable.

### Research Flags Summary

| Phase | Research Needed | Reason |
|-------|-----------------|--------|
| Phase 1 | No | Direct ios-app-factory reuse, well-documented |
| Phase 2 | Yes — quality criteria design | What makes quality criteria content-specific vs. vacuous? |
| Phase 3 | No | ios-app-factory spec patterns transfer directly |
| Phase 4 | Yes — build-agent prompt engineering | `"use client"` prevention, package allowlist, Zod patterns |
| Phase 5 | No | Lighthouse CI + axe-core integration are well-documented |
| Phase 6 | Possibly — legal templates | GDPR/CCPA minimum requirements for generated web apps |
| Phase 7 | No | Empirical validation |

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core versions verified against PyPI, npm, and official release blogs as of 2026-03-21. Two MEDIUM items: Zod v4 (no single pinned version from official source), `nosecone` library (emerging, less established). |
| Features | HIGH (pipeline) / MEDIUM (generated app) | Pipeline features derived from ios-app-factory direct inspection + research. Generated app feature completeness based on competitor analysis — may evolve as output quality is observed in practice. |
| Architecture | HIGH | Component boundaries validated against direct ios-app-factory codebase inspection. Build order implications are direct dependency analysis. One MEDIUM item: monorepo patterns for generated apps (discussion thread, not official docs). |
| Pitfalls | HIGH (inherited) / HIGH (Next.js specifics) / MEDIUM (LLM codegen) | ios-app-factory pitfalls have direct evidence (incident reports, governance monitor code). Next.js CVEs are documented with CVSS scores. LLM codegen pitfall rates from USENIX Security 2025 paper — research paper confidence, not first-party measurement. |

**Overall confidence:** HIGH

### Gaps to Address

- **Build-agent prompt templates:** Research identified what to prevent but not the exact prompt language that reliably prevents `"use client"` misplacement and npm hallucination. Needs empirical testing in Phase 4 and iteration.
- **Quality criteria specificity:** The YAML contract needs quality criteria that are genuinely content-verifying (not "file contains heading X"). The right formulation for web app specs is not directly transferable from iOS specs. Address in Phase 2 research.
- **Lighthouse thresholds for generated apps:** Research suggests perf ≥85, a11y ≥90, SEO ≥85 as reasonable thresholds. These may need adjustment once real generated apps are measured — some generated apps may structurally struggle with perf due to content complexity.
- **Legal template GDPR completeness:** ios-app-factory's legal templates are iOS/Japan-focused. Web apps targeting global audiences need GDPR/CCPA-compliant privacy policies. The minimum viable legal content for a generated web app needs explicit research.
- **Vercel project provisioning:** Research identified `vercel link` / API project creation as the mechanism but the exact CLI flow for auto-provisioning a new project (vs. linking an existing one) needs a working prototype to validate.

## Sources

### Primary (HIGH confidence)
- `/Users/masa/Development/ios-app-factory/` — direct codebase inspection; governance monitor, contract runner, MCP server patterns
- [Next.js 16 Release Blog](https://nextjs.org/blog/next-16) — version 16.2.0, Node.js 20.9+ minimum, `proxy.ts` replacement, `next lint` removal, Turbopack stable
- [PyPI: claude-agent-sdk 0.1.50](https://pypi.org/project/claude-agent-sdk/) — Python 3.10+, current stable
- [PyPI: fastmcp 3.1.1](https://pypi.org/project/fastmcp/) — current stable, Apache-2.0
- [Tailwind CSS releases](https://github.com/tailwindlabs/tailwindcss/releases) — v4.2.2 current stable
- [Vitest blog](https://vitest.dev/blog/vitest-4) — v4.1.0 current stable (March 2026)
- [Playwright releases](https://github.com/microsoft/playwright/releases) — v1.58.2 current stable
- CVE-2025-29927 — [projectdiscovery.io Next.js middleware auth bypass](https://projectdiscovery.io/blog/nextjs-middleware-authorization-bypass), CVSS 9.1
- CVE-2025-66478 — [nextjs.org/blog/CVE-2025-66478](https://nextjs.org/blog/CVE-2025-66478), CVSS 10.0
- `45-quality-driven-execution.md` workspace rules — gate-gaming prevention principles (direct)
- MEMORY.md — dual implementation divergence incident, Claude Agent SDK behavior

### Secondary (MEDIUM confidence)
- USENIX Security 2025, "We Have a Package for You!" ([arxiv.org/abs/2406.10279](https://arxiv.org/abs/2406.10279)) — npm hallucination 19.7% rate
- arxiv.org/abs/2501.19012 "Importing Phantoms" — slopsquatting attack patterns
- [Vercel CLI programmatic deploy pattern](https://vercel.com/kb/guide/how-can-i-use-github-actions-with-vercel) — `vercel pull → vercel build → vercel deploy --prebuilt`
- WebAIM Million 2025 — ARIA misuse statistics (57 errors on ARIA-using pages vs 25 without)
- [v0 vs Bolt vs Lovable 2026 comparison](https://freeacademy.ai/blog/v0-vs-bolt-vs-lovable-ai-app-builders-comparison-2026) — competitor feature gap analysis
- [Vercel Hobby plan function timeout](https://vercel.com/kb/guide/troubleshooting-function-250mb-limit) — 60-second limit, 250MB bundle limit

### Tertiary (LOW confidence)
- `nosecone` npm library for Next.js security headers — emerging tool, limited community validation; manual `next.config.ts` headers are a safe fallback
- Zod v4 stable — multiple sources agree, no single official PyPI-equivalent pinned version confirmed

---
*Research completed: 2026-03-21*
*Ready for roadmap: yes*
