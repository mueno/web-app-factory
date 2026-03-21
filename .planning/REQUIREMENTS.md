# Requirements: Web App Factory

**Defined:** 2026-03-21
**Core Value:** A single command takes a web app idea from concept to deployed, production-quality web application

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Pipeline Infrastructure

- [ ] **PIPE-01**: Pipeline executes phases in order defined by YAML contract, blocking on gate failure
- [ ] **PIPE-02**: Pipeline state persists to `state.json` and `activity-log.jsonl`, surviving interruption
- [ ] **PIPE-03**: Pipeline resumes from last completed phase after interruption (no re-run from scratch)
- [ ] **PIPE-04**: MCP server provides approval gates for human-in-the-loop sign-off
- [ ] **PIPE-05**: Governance monitor detects and blocks phase skipping, direct file edits, and gate bypasses
- [ ] **PIPE-06**: CLI entry point accepts `--idea` and `--project-dir` flags to initiate pipeline
- [ ] **PIPE-07**: Startup preflight validates environment (Node.js, Python, Vercel CLI) before execution

### Contract Design

- [ ] **CONT-01**: YAML contract defines all phases with purpose, deliverables, quality criteria, and gate types
- [ ] **CONT-02**: Each deliverable has `quality_criteria` array driving content verification (not just file existence)
- [ ] **CONT-03**: Contract validated against JSON schema at pipeline startup
- [ ] **CONT-04**: Quality self-assessment JSON generated before every gate submission

### Spec Agent

- [ ] **SPEC-01**: Phase 1a validates idea with market research, competitor analysis, and Go/No-Go decision
- [ ] **SPEC-02**: Phase 1b generates structured PRD with MoSCoW classification and component inventory
- [ ] **SPEC-03**: Phase 1b produces tech feasibility memo evaluating implementation approach
- [ ] **SPEC-04**: Spec agent uses Claude Agent SDK with web-specific system prompt (no iOS references)

### Build Agent

- [ ] **BILD-01**: Phase 2a scaffolds Next.js project via `create-next-app` with TypeScript, Tailwind v4, App Router
- [ ] **BILD-02**: Phase 2b generates pages, components, and API routes from PRD specification
- [ ] **BILD-03**: Generated app passes `next build` production build without errors
- [ ] **BILD-04**: Generated app passes `tsc --noEmit` type-check without errors
- [ ] **BILD-05**: Generated app is responsive (mobile-first Tailwind classes)
- [ ] **BILD-06**: Generated app includes error boundaries (`error.tsx`, `not-found.tsx`)
- [ ] **BILD-07**: npm packages validated against registry before install (hallucination prevention)

### Quality Gates

- [ ] **GATE-01**: Build gate fails pipeline if `next build` or `tsc --noEmit` returns non-zero
- [ ] **GATE-02**: Lighthouse gate runs against deployed preview URL with thresholds (perf ≥85, a11y ≥90, SEO ≥85)
- [ ] **GATE-03**: Security headers gate verifies CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- [ ] **GATE-04**: Link integrity gate verifies no internal 404s in deployed app
- [ ] **GATE-05**: Static analysis gate flags `"use client"` in `layout.tsx` or `page.tsx`
- [ ] **GATE-06**: Static analysis gate fails on `NEXT_PUBLIC_` + secret-pattern environment variables
- [ ] **GATE-07**: axe-core accessibility check runs in addition to Lighthouse a11y score

### Legal

- [ ] **LEGL-01**: Legal phase generates Privacy Policy from web-adapted template
- [ ] **LEGL-02**: Legal phase generates Terms of Service from web-adapted template
- [ ] **LEGL-03**: Legal documents reference actual app features from build output

### Deployment

- [ ] **DEPL-01**: Pipeline deploys to Vercel via CLI (`vercel pull → build → deploy --prebuilt`)
- [ ] **DEPL-02**: Preview URL captured in `docs/pipeline/deployment.json` after deploy
- [ ] **DEPL-03**: Deploy gate verifies HTTP 200 on deployed URL within 30 seconds
- [ ] **DEPL-04**: MCP approval gate wraps deployment (human sign-off before production deploy)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Data Layer

- **DATA-01**: Database provisioning via Supabase or Neon
- **DATA-02**: ORM integration (Drizzle or Prisma)

### Authentication

- **AUTH-01**: Authentication scaffolding via Clerk or NextAuth
- **AUTH-02**: Role-based access control patterns

### SEO & Analytics

- **SEO-01**: Sitemap.xml and robots.txt auto-generation
- **SEO-02**: Open Graph and Twitter card meta tags
- **SEO-03**: JSON-LD structured data for primary content type
- **SEO-04**: Analytics integration hook (Vercel Analytics or GA placeholder)

### Multi-Framework

- **FRMK-01**: Vue/Nuxt support as alternative framework
- **FRMK-02**: Svelte/SvelteKit support as alternative framework

### Advanced Quality

- **QUAL-01**: Visual regression testing gate
- **QUAL-02**: Bundle size monitoring gate

## Out of Scope

| Feature | Reason |
|---------|--------|
| iOS/Swift code generation | Handled by ios-app-factory; separate system |
| App Store submission | Web apps deploy to hosting, not app stores |
| Mobile-native features (APNs push, etc.) | Web-only scope; PWA support is v2+ |
| Custom domain / DNS management | Vercel subdomain sufficient for v1 |
| Backend infrastructure (databases, queues) | Doubles pipeline scope; v2 with dedicated review |
| Multi-framework support | Multiplies gate complexity 3-5x; Next.js only for v1 |
| Parallel phase execution | Creates state race conditions; serial pipeline only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PIPE-01 | Phase 1 | Pending |
| PIPE-02 | Phase 1 | Pending |
| PIPE-03 | Phase 1 | Pending |
| PIPE-04 | Phase 1 | Pending |
| PIPE-05 | Phase 1 | Pending |
| PIPE-06 | Phase 1 | Pending |
| PIPE-07 | Phase 1 | Pending |
| CONT-01 | Phase 1 | Pending |
| CONT-02 | Phase 1 | Pending |
| CONT-03 | Phase 1 | Pending |
| CONT-04 | Phase 1 | Pending |
| SPEC-01 | Phase 2 | Pending |
| SPEC-02 | Phase 2 | Pending |
| SPEC-03 | Phase 2 | Pending |
| SPEC-04 | Phase 2 | Pending |
| BILD-01 | Phase 3 | Pending |
| BILD-02 | Phase 3 | Pending |
| BILD-03 | Phase 3 | Pending |
| BILD-04 | Phase 3 | Pending |
| BILD-05 | Phase 3 | Pending |
| BILD-06 | Phase 3 | Pending |
| BILD-07 | Phase 3 | Pending |
| GATE-01 | Phase 3 | Pending |
| GATE-02 | Phase 4 | Pending |
| GATE-03 | Phase 4 | Pending |
| GATE-04 | Phase 4 | Pending |
| GATE-05 | Phase 3 | Pending |
| GATE-06 | Phase 3 | Pending |
| GATE-07 | Phase 4 | Pending |
| LEGL-01 | Phase 4 | Pending |
| LEGL-02 | Phase 4 | Pending |
| LEGL-03 | Phase 4 | Pending |
| DEPL-01 | Phase 4 | Pending |
| DEPL-02 | Phase 4 | Pending |
| DEPL-03 | Phase 4 | Pending |
| DEPL-04 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 36 total
- Mapped to phases: 36
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-21*
*Last updated: 2026-03-21 after roadmap creation*
