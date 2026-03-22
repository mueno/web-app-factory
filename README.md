# web-app-factory

AI-powered pipeline that generates production-grade Next.js web applications from a text description, using Claude Agent SDK.

## What it does

Given an idea like "A recipe sharing app for home cooks", web-app-factory:

1. **Validates the idea** -- market research, competitor analysis, feasibility assessment
2. **Writes the spec** -- PRD with MoSCoW requirements, component inventory, screen specifications
3. **Scaffolds the project** -- Next.js + TypeScript + Tailwind CSS via create-next-app
4. **Implements the app** -- All pages, components, routing, and error handling
5. **Deploys & verifies** -- Vercel deployment with Lighthouse, accessibility, security, and legal gates

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Vercel CLI](https://vercel.com/docs/cli) (`npm i -g vercel && vercel login`)
- [Claude API key](https://console.anthropic.com/) (set as `ANTHROPIC_API_KEY` env var)

### Installation

```bash
git clone https://github.com/anthropics/web-app-factory.git  # placeholder URL
cd web-app-factory
pip install -e ".[dev]"
```

### Usage

```bash
# Generate and deploy a web app
python factory.py "A recipe sharing app for home cooks"

# With company info for legal documents
python factory.py "A recipe sharing app" --company-name "My Corp" --contact-email "hello@mycorp.com"

# Dry run (validate contract without executing)
python factory.py "test app" --dry-run

# Resume a failed run
python factory.py "test app" --resume 20260322-120000-test
```

### CLI Options

| Flag | Description |
|------|-------------|
| `--project-dir DIR` | Output directory (default: derived from idea) |
| `--company-name NAME` | Company name for legal documents |
| `--contact-email EMAIL` | Contact email for legal documents |
| `--deploy-target` | Deployment target: `vercel` (default) |
| `--dry-run` | Validate without executing |
| `--resume RUN_ID` | Resume from a previous run |
| `--output-json PATH` | Write structured result JSON |

## Pipeline Architecture

```
Phase 1a: Idea Validation (spec-agent + WebSearch)
    | gates: artifact existence, output markers
Phase 1b: Spec & Design (spec-agent)
    | gates: artifact existence, MoSCoW labels, component cross-validation
Phase 2a: Next.js Scaffold (create-next-app + build-agent)
    | gates: npm build, tsc --noEmit
Phase 2b: Implementation (build-agent)
    | gates: npm build, static analysis, tsc
Phase 3: Ship (deploy-agent)
    | gates: Lighthouse, accessibility, security headers, legal, link integrity
    -> Deployed application
```

## Quality Gates

| Gate | What it verifies |
|------|-----------------|
| **build** | `npm run build` + `tsc --noEmit` pass |
| **static_analysis** | No `use client` in layout/page, no exposed secrets |
| **lighthouse** | Performance >= 70, Accessibility >= 90, SEO >= 85 |
| **accessibility** | Zero critical axe-core violations |
| **security_headers** | CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| **legal** | Privacy policy + Terms of Service with no placeholder text |
| **link_integrity** | All internal links return 2xx/3xx |

## Configuration

The pipeline is driven by a YAML contract (`contracts/pipeline-contract.web.v1.yaml`) that defines phases, deliverables, quality criteria, and gate conditions. You can customize thresholds, add phases, or modify quality criteria by editing this file.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Type check
mypy .
```

## How it works

web-app-factory uses the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) to orchestrate three specialized agents:

- **spec-agent** -- Conducts market research (via WebSearch), writes PRD and screen specifications
- **build-agent** -- Implements Next.js pages and components with TypeScript strict mode
- **deploy-agent** -- Handles Vercel deployment, legal document generation, and quality gate fixes

Each agent runs in a sandboxed environment with controlled tool access and turn limits.

## License

MIT -- see [LICENSE](LICENSE) for details.
