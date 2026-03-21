# Stack Research

**Domain:** Automated web app generation pipeline (Python orchestration) + Generated Next.js/React web applications
**Researched:** 2026-03-21
**Confidence:** HIGH (core pipeline stack verified via PyPI + official docs; generated app stack verified via Next.js official blog + npm)

---

## Stack 1: Pipeline (Python Orchestration)

The pipeline is a fork of ios-app-factory. The Python infrastructure is already chosen and running. Research here confirms versions are current and no changes are needed.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.10+ | Runtime | Required by Claude Agent SDK; ios-app-factory already uses 3.10+ |
| `claude-agent-sdk` | 0.1.50 (PyPI, 2026-03-20) | LLM orchestration — phase executors talk to Claude via agent loop | Same tools, context management, and hooks as Claude Code itself; gives built-in MCP tool support in-process; ios-app-factory proven on this exact SDK |
| `fastmcp` | 3.1.1 (PyPI, 2026-03-14) | MCP server for approval gates and phase reporting | De-facto standard for Python MCP servers; 1M+ downloads/day; 70% of MCP servers use some version; fully replaces `mcp` package for server authoring |
| `uv` | latest (Astral) | Package manager and task runner | 10–100x faster than pip; `uv run pytest` ensures lockfile sync before test; `uv lock --frozen` gives deterministic CI installs; ios-app-factory already uses it |
| `ruff` | 0.15.4+ | Linter + formatter (replaces Black + isort + flake8) | Single tool, 10–100x faster than ESLint/Black/isort in combination; ios-app-factory already configured with it |
| `pytest` | 9.0+ | Test runner | Standard Python testing; ios-app-factory test suite already uses it |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `jsonschema` | 4.20+ | Validate YAML contract schemas at pipeline startup | Always — gate contracts and deliverable manifests must be schema-validated |
| `pyyaml` | 6.0+ | Parse phase contracts (YAML) | Always — pipeline contracts are YAML |
| `httpx` | 0.28+ | Async HTTP for any API calls phase executors make | When a phase executor needs to call external APIs (e.g., Vercel REST API, npm registry) |
| `playwright` | 1.58.2 | Browser automation for quality gate checks (Lighthouse, security headers, link integrity) | In the web-quality-gate phase executor; headless Chromium for automated quality checks |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` | Dependency resolution, lockfile, virtual env | Use `uv sync` to install, `uv run` to execute. `uv.lock` must be committed. |
| `ruff check` | Lint | Runs in CI pre-commit; configured in `pyproject.toml` with `target-version = "py310"` |
| `ruff format` | Format | Replaces Black; same config file |
| `mypy` | Static type checking | Optional at dev time but valuable for pipeline code; ios-app-factory uses it |
| `pytest-asyncio` | Async test support | Required if phase executors use async code with the Agent SDK |

### Installation (Pipeline)

```bash
# Install uv (if not present)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync from lockfile (CI / first setup)
uv sync

# Add dependencies
uv add claude-agent-sdk fastmcp jsonschema pyyaml httpx playwright
uv add --dev mypy pytest ruff pyyaml

# Install Playwright browsers
uv run playwright install chromium
```

---

## Stack 2: Generated Web Applications (Next.js)

These are the apps the pipeline produces. Each generated project gets this exact stack scaffolded.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Next.js | 16.2.0 (released 2026-03-17) | Full-stack React framework | App Router is mature and default; Turbopack is now stable default bundler (2–5x faster builds); Cache Components + PPR solve the static/dynamic dichotomy; Vercel-native; `create-next-app` scaffolds TypeScript + Tailwind by default. **Node.js 20.9+ required.** |
| React | 19.2 | UI library | Bundled with Next.js 16; View Transitions, `useEffectEvent`, and `Activity` are production-ready; Server Components are the idiomatic pattern for generated apps |
| TypeScript | 5.1+ | Type safety | Next.js 16 minimum; `next.config.ts` is the default; required for Zod inference to work correctly |
| Tailwind CSS | 4.2.2 (2026-03-18) | Utility-first styling | Oxide engine (Rust) makes full builds 5x faster; CSS-first config (`@theme` directive); single `@import "tailwindcss"` replaces all directives; `create-next-app` includes it by default |
| shadcn/ui | latest (no pinned version — copies source) | Component library | Copies components as local TypeScript files — no version conflicts, no library lock-in; built on Radix UI primitives for WAI-ARIA compliance; fully compatible with Tailwind v4; generates components into `src/components/ui/` |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Zod | 4.x | Runtime schema validation | Always — Server Actions must validate input at runtime because TypeScript types vanish; use `z.safeParse()` in all Server Actions |
| React Hook Form | 7.x | Form state management | When the generated app has forms; pairs with Zod resolver (`@hookform/resolvers`) for unified client+server validation |
| `@tanstack/react-query` | 5.x | Server state / data fetching for CSR patterns | When the app has dynamic data fetched client-side; skip if the app is purely Server Component–driven |
| `next-themes` | 0.4+ | Dark/light mode | For generated apps that need theme switching; trivial to add |
| Lucide React | latest | Icon library | Default icon set for shadcn/ui components; consistent and tree-shakable |

### Testing Stack (Per Generated App)

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| Vitest | 4.1.0 | Unit + integration testing | For React component tests, utility functions, Server Action logic; native ESM support is 6x faster cold start than Jest; replaces Jest completely |
| `@testing-library/react` | 16.x | React component rendering in Vitest | For component unit tests |
| Playwright | 1.58.2 | E2E + quality gate tests | For pipeline quality gates AND as the generated app's own E2E test suite; headless Chromium for CI |
| `@axe-core/playwright` | 4.x | WCAG accessibility checks | Pipeline quality gate: accessibility score is a pass/fail criterion; `@axe-core/playwright` integrates with Playwright natively (avoids the React 18+ incompatibility of `@axe-core/react`) |

### Quality Gate Tools (Pipeline-Driven, Run Against Generated App)

| Tool | Purpose | How Used |
|------|---------|---------|
| Playwright + Lighthouse (via Chrome DevTools Protocol) | Performance score gate | Pipeline `quality-gate` phase executor launches headless Chrome, connects via CDP, runs Lighthouse; fail if score < 90 |
| `@axe-core/playwright` | WCAG 2.1 AA gate | Playwright page visit + `checkA11y()` on every generated page; fail on any critical/serious violations |
| `nosecone` (npm) or `next.config.ts` headers | Security headers gate | Pipeline verifies CSP, HSTS, X-Frame-Options, X-Content-Type-Options are set; `nosecone` provides sensible defaults for Next.js |
| ESLint (flat config, v9) | Code quality gate | `next lint` was removed in Next.js 16; pipeline runs `eslint` directly; `@next/eslint-plugin-next` defaults to flat config in v16 |

### Deployment

| Tool | Purpose | Notes |
|------|---------|-------|
| Vercel CLI | Programmatic deployment from pipeline | `vercel pull` → `vercel build --prod` → `vercel deploy --prebuilt --prod`; requires `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` as env vars |
| `vercel.json` | Deployment configuration | Generated by pipeline; defines rewrites, security headers, function timeouts |
| GitHub Actions | CI/CD for the generated app post-deploy | Pipeline scaffolds a `.github/workflows/ci.yml`; runs Vitest + Playwright + Lighthouse on every PR |

### Development Tools (Per Generated App)

| Tool | Purpose | Notes |
|------|---------|-------|
| `create-next-app` | Project scaffold | `npx create-next-app@latest --typescript --tailwind --app --src-dir --turbopack`; produces the baseline the pipeline then populates |
| Turbopack | Default bundler (Next.js 16) | No configuration needed; 2–5x faster builds; opt out with `--webpack` only if custom webpack plugins are required (unusual for generated apps) |
| ESLint 9 (flat config) | Linting | `eslint.config.mjs`; `@next/eslint-plugin-next` included; run separately from `next build` (removed in v16) |

### Installation (Generated App)

```bash
# Scaffold
npx create-next-app@latest my-app --typescript --tailwind --app --src-dir --turbopack
cd my-app

# UI components (shadcn/ui)
npx shadcn@latest init

# Core runtime deps
npm install zod react-hook-form @hookform/resolvers next-themes lucide-react

# Testing
npm install -D vitest @testing-library/react @testing-library/user-event @vitejs/plugin-react jsdom
npm install -D playwright @playwright/test @axe-core/playwright

# Security headers
npm install nosecone

# Dev
npm install -D eslint eslint-config-next
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Next.js 16 App Router | Remix | If the app is form-heavy/mutation-heavy and you prefer loader/action over Server Components; smaller community today |
| Next.js 16 App Router | Vite + React SPA | If there is absolutely no SSR need and no API routes; simpler but no server-side generation |
| Vercel | Railway / Fly.io | If the generated app needs persistent server processes or long-running workers (outside v1 scope) |
| Vercel | AWS Amplify | If the organization has an AWS-only mandate; significantly more config overhead |
| Vitest | Jest | Never for new Next.js 16 projects — Vitest is faster, supports native ESM, and is the officially recommended testing framework in Next.js docs |
| Tailwind CSS v4 | Tailwind CSS v3 | Never for new projects — v3 is end-of-life; the Oxide engine and CSS-first config are strictly better |
| Zod v4 | Yup / Joi | If the codebase has heavy existing Yup investment; Zod v4 is faster and TypeScript-first |
| `fastmcp` 3.x | `mcp` (base Python SDK) | Never — FastMCP is the maintained superset; the base SDK incorporated FastMCP 1.0 and then diverged |
| `@axe-core/playwright` | `@axe-core/react` | `@axe-core/react` does not support React 18+; use the Playwright integration for all accessibility testing |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Next.js Pages Router (new files) | App Router is the default in v16; Pages Router is in maintenance mode | App Router only |
| `middleware.ts` | Deprecated in Next.js 16 in favor of `proxy.ts`; will be removed in v17 | `proxy.ts` |
| `next lint` command | Removed from Next.js 16 | Run `eslint` directly |
| `experimental.ppr` flag | Removed in Next.js 16; replaced by `cacheComponents` | `cacheComponents: true` in `next.config.ts` |
| Jest in new Next.js projects | Slower cold start (6x), no native ESM, worse DX with Server Components | Vitest 4.x |
| `@axe-core/react` | Does not support React 18+ — silently misses violations | `@axe-core/playwright` |
| `create-react-app` | Unmaintained; no SSR; no Turbopack | `create-next-app@latest` |
| CSS Modules as primary styling | More verbose than Tailwind for generated code; harder for AI to reason about | Tailwind CSS v4 |
| Python `pip` or `poetry` directly | uv is 10–100x faster and already used by ios-app-factory; consistency required | `uv` |
| `mcp` Python SDK (server authoring) | Raw SDK requires more boilerplate; FastMCP 3.x is the standard wrapper | `fastmcp` |

---

## Stack Patterns by Variant

**If the generated app has no dynamic data (fully static site):**
- Use `output: 'export'` in `next.config.ts` for static export
- Deploy to Vercel or GitHub Pages
- Skip `@tanstack/react-query`

**If the generated app has a database:**
- Add Prisma ORM + Neon (serverless Postgres) or Turso (SQLite at edge)
- This is outside v1 scope but the stack supports it without changes

**If the generated app needs authentication:**
- Add Clerk (managed auth, easiest) or NextAuth.js v5 (self-hosted)
- This is outside v1 scope but the generated scaffold can include stub auth setup

**If the pipeline CI needs faster test feedback:**
- Use `vitest --pool=forks` for CPU-bound tests
- Parallelize Playwright tests with `--workers=4`

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Next.js 16.x | Node.js 20.9+, React 19.2, TypeScript 5.1+ | Node.js 18 dropped in Next.js 16; minimum is now 20.9.0 LTS |
| Tailwind CSS 4.x | Next.js 16, `@tailwindcss/vite` for Turbopack | No `tailwind.config.js` needed; CSS-only config |
| shadcn/ui | Tailwind CSS 4.x (full support since Jan 2026) | Run `npx shadcn@latest init` to get Tailwind v4 config |
| Zod v4 | TypeScript 5.x | Breaking change from v3: import path changed to `"zod"` (no sub-path needed) |
| Vitest 4.x | Vite 6.x | Bundled together; check `@vitejs/plugin-react` is on matching major |
| `claude-agent-sdk` 0.1.50 | Python 3.10–3.13 | Uses bundled Claude CLI binary; Python 3.12+ recommended for best type inference |
| `fastmcp` 3.1.1 | Python 3.10+, `mcp` 1.x | Drop-in replacement for raw `mcp` server authoring; ios-app-factory's existing `mcp>=1.26.0` dep is compatible |

---

## Sources

- [Next.js 16 Release Blog](https://nextjs.org/blog/next-16) — Verified: version 16.2.0, Node.js 20.9+ minimum, Turbopack stable, `proxy.ts` replaces `middleware.ts`, `next lint` removed — **HIGH confidence**
- [PyPI: claude-agent-sdk](https://pypi.org/project/claude-agent-sdk/) — Verified: version 0.1.50, Python 3.10+ — **HIGH confidence**
- [PyPI: fastmcp](https://pypi.org/project/fastmcp/) — Verified: version 3.1.1, Python 3.10+, Apache-2.0 — **HIGH confidence**
- [Tailwind CSS releases (GitHub)](https://github.com/tailwindlabs/tailwindcss/releases) — Verified: latest stable v4.2.2 — **HIGH confidence**
- [Vitest blog](https://vitest.dev/blog/vitest-4) — Verified: current stable is 4.1.0 (March 2026) — **HIGH confidence**
- [Playwright releases (GitHub)](https://github.com/microsoft/playwright/releases) — Verified: 1.58.2 current stable — **HIGH confidence**
- WebSearch: Zod v4 stable (2025/2026), 14x faster string parsing — **MEDIUM confidence** (multiple sources agree, no single official version number pinned from PyPI)
- WebSearch: `@axe-core/react` React 18+ incompatibility — **HIGH confidence** (confirmed in official Deque documentation and multiple independent sources)
- WebSearch: Vercel CLI programmatic deploy pattern (`vercel pull` → `vercel build` → `vercel deploy --prebuilt`) — **HIGH confidence** (Vercel official KB)
- WebSearch: `nosecone` library for Next.js security headers — **MEDIUM confidence** (emerging tool, less established than manual `next.config.ts` headers)
- ios-app-factory `pyproject.toml` — Verified existing pipeline deps (`claude-agent-sdk>=0.1.35`, `mcp>=1.26.0`, `fastmcp` via factory_mcp_server.py pattern) — **HIGH confidence**

---
*Stack research for: web-app-factory — Python pipeline orchestration + Next.js generated apps*
*Researched: 2026-03-21*
