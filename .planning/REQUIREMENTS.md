# Requirements: Web App Factory

**Defined:** 2026-03-21
**Core Value:** A single command takes a web app idea from concept to deployed, production-quality web application

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Pipeline Infrastructure

- [x] **PIPE-01**: Pipeline executes phases in order defined by YAML contract, blocking on gate failure
- [x] **PIPE-02**: Pipeline state persists to `state.json` and `activity-log.jsonl`, surviving interruption
- [x] **PIPE-03**: Pipeline resumes from last completed phase after interruption (no re-run from scratch)
- [x] **PIPE-04**: MCP server provides approval gates for human-in-the-loop sign-off
- [x] **PIPE-05**: Governance monitor detects and blocks phase skipping, direct file edits, and gate bypasses
- [x] **PIPE-06**: CLI entry point accepts `--idea` and `--project-dir` flags to initiate pipeline
- [x] **PIPE-07**: Startup preflight validates environment (Node.js, Python, Vercel CLI) before execution

### Contract Design

- [x] **CONT-01**: YAML contract defines all phases with purpose, deliverables, quality criteria, and gate types
- [x] **CONT-02**: Each deliverable has `quality_criteria` array driving content verification (not just file existence)
- [x] **CONT-03**: Contract validated against JSON schema at pipeline startup
- [x] **CONT-04**: Quality self-assessment JSON generated before every gate submission

### Spec Agent

- [x] **SPEC-01**: Phase 1a validates idea with market research, competitor analysis, and Go/No-Go decision
- [x] **SPEC-02**: Phase 1b generates structured PRD with MoSCoW classification and component inventory
- [x] **SPEC-03**: Phase 1b produces tech feasibility memo evaluating implementation approach
- [x] **SPEC-04**: Spec agent uses Claude Agent SDK with web-specific system prompt (no iOS references)

### Build Agent

- [x] **BILD-01**: Phase 2a scaffolds Next.js project via `create-next-app` with TypeScript, Tailwind v4, App Router
- [x] **BILD-02**: Phase 2b generates pages, components, and API routes from PRD specification
- [x] **BILD-03**: Generated app passes `next build` production build without errors
- [x] **BILD-04**: Generated app passes `tsc --noEmit` type-check without errors
- [x] **BILD-05**: Generated app is responsive (mobile-first Tailwind classes)
- [x] **BILD-06**: Generated app includes error boundaries (`error.tsx`, `not-found.tsx`)
- [x] **BILD-07**: npm packages validated against registry before install (hallucination prevention)

### Quality Gates

- [x] **GATE-01**: Build gate fails pipeline if `next build` or `tsc --noEmit` returns non-zero
- [x] **GATE-02**: Lighthouse gate runs against deployed preview URL with thresholds (perf ≥85, a11y ≥90, SEO ≥85)
- [x] **GATE-03**: Security headers gate verifies CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- [x] **GATE-04**: Link integrity gate verifies no internal 404s in deployed app
- [x] **GATE-05**: Static analysis gate flags `"use client"` in `layout.tsx` or `page.tsx`
- [x] **GATE-06**: Static analysis gate fails on `NEXT_PUBLIC_` + secret-pattern environment variables
- [x] **GATE-07**: axe-core accessibility check runs in addition to Lighthouse a11y score

### Legal

- [x] **LEGL-01**: Legal phase generates Privacy Policy from web-adapted template
- [x] **LEGL-02**: Legal phase generates Terms of Service from web-adapted template
- [x] **LEGL-03**: Legal documents reference actual app features from build output

### Deployment

- [x] **DEPL-01**: Pipeline deploys to Vercel via CLI (`vercel pull → build → deploy --prebuilt`)
- [x] **DEPL-02**: Preview URL captured in `docs/pipeline/deployment.json` after deploy
- [x] **DEPL-03**: Deploy gate verifies HTTP 200 on deployed URL within 30 seconds
- [x] **DEPL-04**: MCP approval gate wraps deployment (human sign-off before production deploy)

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
| PIPE-01 | Phase 1 | Complete |
| PIPE-02 | Phase 1 | Complete |
| PIPE-03 | Phase 1 | Complete |
| PIPE-04 | Phase 1 | Complete |
| PIPE-05 | Phase 1 | Complete |
| PIPE-06 | Phase 1 | Complete |
| PIPE-07 | Phase 1 | Complete |
| CONT-01 | Phase 1 | Complete |
| CONT-02 | Phase 1 | Complete |
| CONT-03 | Phase 1 | Complete |
| CONT-04 | Phase 1 | Complete |
| SPEC-01 | Phase 2 | Complete |
| SPEC-02 | Phase 2 | Complete |
| SPEC-03 | Phase 2 | Complete |
| SPEC-04 | Phase 2 | Complete |
| BILD-01 | Phase 3 | Complete |
| BILD-02 | Phase 3 | Complete |
| BILD-03 | Phase 3 | Complete |
| BILD-04 | Phase 3 | Complete |
| BILD-05 | Phase 3 | Complete |
| BILD-06 | Phase 3 | Complete |
| BILD-07 | Phase 3 | Complete |
| GATE-01 | Phase 3 | Complete |
| GATE-02 | Phase 4 | Complete |
| GATE-03 | Phase 4 | Complete |
| GATE-04 | Phase 4 | Complete |
| GATE-05 | Phase 3 | Complete |
| GATE-06 | Phase 3 | Complete |
| GATE-07 | Phase 4 | Complete |
| LEGL-01 | Phase 4 | Complete |
| LEGL-02 | Phase 4 | Complete |
| LEGL-03 | Phase 4 | Complete |
| DEPL-01 | Phase 4 | Complete |
| DEPL-02 | Phase 4 | Complete |
| DEPL-03 | Phase 4 | Complete |
| DEPL-04 | Phase 4 | Complete |

**Coverage:**
- v1 requirements: 36 total
- Mapped to phases: 36
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-21*
*Last updated: 2026-03-21 after roadmap creation*
