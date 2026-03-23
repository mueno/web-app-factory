# Technology Stack

**Project:** web-app-factory
**Researched:** 2026-03-23
**Scope of this update:** v2.0 additions only — MCP App distribution, local dev server, multi-cloud deployment, environment detection. Do not change the v1.0 stack already documented below.

---

## v2.0 Stack Additions (NEW — Research for This Milestone)

### Distribution: MCP App Packaging

**Decision: `fastmcp install claude-code` command (not .mcpb)**

The MCP ecosystem has two distribution paths. The right one for this project is the `fastmcp` CLI installer.

| Path | Mechanism | Best For | Python Limitation |
|------|-----------|----------|-------------------|
| `fastmcp install claude-code server.py` | Calls `claude mcp add` under the hood, adds to `~/.claude.json` (user scope) | CLI tool users, developers | None — uv handles deps |
| `.mcpb` Desktop Extension | ZIP bundle with `manifest.json`, double-click install in Claude Desktop | End-user one-click install | Compiled C extensions (pydantic, mcp SDK) cannot be portably bundled |

**Use `fastmcp install claude-code`** because:
- This project's users are developers with `uv` installed (or can install it)
- The `mcp` Python SDK requires `pydantic` which has compiled C extensions that break `.mcpb` portability
- `fastmcp install` auto-generates the correct `claude mcp add` command with `uv run` transport
- The resulting `~/.claude.json` entry works across all projects (user scope) — appropriate for a pipeline tool

The `.mcpb` path is a FUTURE option if a non-technical end-user distribution channel is needed, but it requires either switching to a Node.js wrapper or stripping all compiled extensions.

#### Installation Command Generated

```bash
# What fastmcp install claude-code server.py generates behind the scenes:
claude mcp add web-app-factory --scope user -- \
  uv run --with fastmcp fastmcp run /path/to/web_app_factory/mcp_server.py
```

#### Manual `claude mcp add` Equivalent

```bash
# For users who prefer manual setup, or for project-scoped install:
claude mcp add web-app-factory --scope project -- \
  uv run --with "web-app-factory[mcp]" web-app-factory-mcp

# With env vars:
claude mcp add web-app-factory --scope user \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" -- \
  uv run --with "web-app-factory[mcp]" web-app-factory-mcp
```

**Scope recommendation:** `--scope user` for personal dev tool (available across all projects). Use `--scope project` if teams want to share the MCP server config via `.mcp.json` in the repo.

#### pyproject.toml entry point

```toml
[project.scripts]
web-app-factory-mcp = "web_app_factory.mcp_server:main"
web-app-factory = "web_app_factory.cli:main"

[project.optional-dependencies]
mcp = ["fastmcp>=3.1.0"]
```

**Confidence:** HIGH — verified via FastMCP docs (gofastmcp.com) and Claude Code MCP docs.

---

### MCP App API: FastMCP 3.x Tool Definitions

**Decision: Use FastMCP 3.1.1 (already a dependency — no version bump needed)**

The existing `fastmcp>=3.1.0` dependency is sufficient. The v2.0 MCP server exposes tools using the standard FastMCP decorator pattern:

```python
from fastmcp import FastMCP

mcp = FastMCP("web-app-factory")

@mcp.tool()
async def generate_app(
    idea: str,
    target: str = "vercel",
    mode: str = "auto"
) -> str:
    """Generate a web app from an idea description."""
    ...

@mcp.tool()
async def get_status(pipeline_id: str) -> dict:
    """Get the current pipeline status."""
    ...

@mcp.tool()
async def approve_phase(pipeline_id: str, phase_id: str) -> str:
    """Approve a phase checkpoint in interactive mode."""
    ...
```

No new dependencies needed — `fastmcp>=3.1.0` already covers this.

**Confidence:** HIGH — FastMCP 3.1.1 is current (March 14, 2026), already in pyproject.toml.

---

### Local Dev Server: Subprocess-Managed Next.js

**Decision: `next dev` for local preview (not `next build` + standalone `server.js`)**

For local development preview before cloud deploy, use `next dev` via Python subprocess. This is the correct choice because:
- `next dev` starts in seconds; `next build` + `node .next/standalone/server.js` takes 30–120s
- The goal is preview/iteration, not production accuracy
- Standalone mode (`output: 'standalone'`) is reserved for cloud deployment packaging

For the final "build and deploy" step, use standalone mode to produce `server.js` for AWS/GCP container deployments.

#### Port Detection

Use Python's `socket` stdlib (not an external library) to find an available port before starting:

```python
import socket
import subprocess

def find_free_port(preferred: int = 3000) -> int:
    """Find an available port, trying preferred first."""
    for port in [preferred, preferred + 1, preferred + 2, 3100, 3200, 8080]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return port
            except OSError:
                continue
    # Fallback: let OS assign
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]

def start_local_dev_server(app_dir: str) -> tuple[subprocess.Popen, int]:
    port = find_free_port()
    proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "-p", str(port)],
        cwd=app_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc, port
```

**Do NOT add `portpicker`** — it is a Google test-infra library designed for unit tests, not production port management. The stdlib `socket.bind(('localhost', 0))` pattern is idiomatic and has zero dependencies.

#### `next.config.ts` for dual mode

The generated apps must support both dev and standalone:

```typescript
// next.config.ts — supports both next dev (local) and standalone (cloud)
const nextConfig: NextConfig = {
  output: process.env.NEXT_BUILD_TARGET === "standalone" ? "standalone" : undefined,
  // ... rest of config
};
```

Pipeline sets `NEXT_BUILD_TARGET=standalone` before running `next build` for cloud deploy.

**Confidence:** HIGH — verified from Next.js official docs and confirmed PORT env var handling in server.js.

---

### Multi-Cloud Deployment

**Decision: Three-tier deploy abstraction with platform-specific CLI wrappers**

Build a `DeploymentProvider` abstract base class with three implementations. No shared "cloud SDK" meta-library — each provider uses its native tool.

```python
from abc import ABC, abstractmethod

class DeploymentProvider(ABC):
    @abstractmethod
    async def deploy(self, app_dir: str, env_vars: dict) -> DeploymentResult: ...

    @abstractmethod
    async def check_prerequisites(self) -> list[str]: ...  # returns list of missing tools
```

#### Provider 1: Vercel (existing, enhanced)

**Tool: `vercel-cli` Python package (v50.35.0, auto-updated)**

```python
# pyproject.toml addition:
# "vercel-cli>=50.0.0"
from vercel_cli import run_vercel

exit_code = run_vercel(
    ["deploy", "--prod", "--yes"],
    cwd=app_dir,
    env={"VERCEL_TOKEN": token, "VERCEL_ORG_ID": org_id, "VERCEL_PROJECT_ID": proj_id}
)
```

Why `vercel-cli` Python package over raw `subprocess` + system `vercel`:
- Bundles its own Node.js binary (via `nodejs-wheel-binaries`) — no Node.js installation required from user
- `run_vercel()` is a proper Python API, not a subprocess string
- Auto-updated via GitHub Actions tracking npm releases
- Version 50.35.0 released March 22, 2026 — actively maintained

**Do NOT require system-installed Node.js for Vercel deployment.**

**New dependency:** `vercel-cli>=50.0.0`

**Confidence:** HIGH — verified pypi.org and GitHub repo (101 releases, active CI).

#### Provider 2: AWS (new)

**Tool: `aws-cdk-lib` + `open-next-cdk` Python packages**

```toml
# pyproject.toml additions (optional-dependencies, cloud extras):
[project.optional-dependencies]
aws = [
    "aws-cdk-lib>=2.240.0",
    "open-next-cdk>=0.1.0",
    "constructs>=10.0.0",
]
```

Architecture (CloudFront + Lambda@Edge + S3):
1. Next.js app built with `output: 'standalone'`
2. `open-next-cdk` converts standalone output to Lambda-compatible format
3. `aws-cdk-lib` synthesizes CloudFormation template
4. `cdk deploy` (CLI, invoked via subprocess) deploys the stack

Why `open-next-cdk` over `cdk-nextjs` (cdklabs):
- `open-next-cdk` has explicit Python package support on PyPI
- `cdk-nextjs` (cdklabs) is TypeScript-first; Python bindings are generated JSII and can lag
- `open-next-cdk` uses OpenNext which supports all Next.js features in serverless context

Prerequisite checks the provider must validate:
- AWS CLI installed (`shutil.which("aws")`)
- AWS credentials configured (`~/.aws/credentials` or `AWS_ACCESS_KEY_ID` env)
- CDK bootstrapped in target region (check via `aws cloudformation describe-stacks --stack-name CDKToolkit`)

**Confidence:** MEDIUM — `open-next-cdk` Python version verified on PyPI; architecture confirmed via multiple sources; exact version pinning needs validation at implementation time.

#### Provider 3: Google Cloud (new)

**Tool: `gcloud` CLI via subprocess (no Python SDK wrapper)**

For GCP Cloud Run deployments, use `gcloud run deploy --source .` directly. Do NOT add `google-cloud-run` Python client library because:
- The Python client library (`google-cloud-run 0.15.0`) is a REST API wrapper, not a deployment tool
- The actual deployment workflow requires Docker image build + push + service update — the `gcloud` CLI handles all of this atomically with `--source .`
- Adding Google Auth SDK dependencies (`google-auth`, `google-api-python-client`) adds significant weight for marginal benefit

Architecture (Cloud Run + Artifact Registry):
1. Next.js app built with `output: 'standalone'`
2. `Dockerfile` generated by pipeline using multi-stage build
3. `gcloud run deploy --source . --region us-central1 --allow-unauthenticated` handles build+push+deploy

```python
import subprocess
import shutil

def deploy_to_cloud_run(app_dir: str, project_id: str, service_name: str, region: str = "us-central1") -> str:
    if not shutil.which("gcloud"):
        raise EnvironmentError("gcloud CLI not found. Install Google Cloud SDK.")

    result = subprocess.run(
        [
            "gcloud", "run", "deploy", service_name,
            "--source", ".",
            "--project", project_id,
            "--region", region,
            "--platform", "managed",
            "--allow-unauthenticated",
            "--memory", "512Mi",
            "--cpu-boost",  # reduces cold start
            "--format", "json",
        ],
        cwd=app_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout  # JSON with service URL
```

Prerequisite checks:
- `shutil.which("gcloud")` — gcloud CLI installed
- `shutil.which("docker")` — Docker installed (required by `gcloud run deploy --source`)
- `gcloud auth print-access-token` — authenticated
- Project ID configured

**No new Python dependencies for GCP.** Only stdlib `subprocess` and `shutil`.

**Confidence:** HIGH — gcloud deploy pattern verified from official Google Cloud documentation and Next.js deploy-google-cloud-run template (2026).

---

### Environment Detection

**Decision: stdlib only (`shutil.which`, `subprocess`, `socket`) — no new dependencies**

Environment detection runs before pipeline start to give users clear actionable errors. It checks three categories:

#### Category 1: Python Environment

```python
import sys

MINIMUM_PYTHON = (3, 10)

def check_python() -> list[str]:
    issues = []
    if sys.version_info < MINIMUM_PYTHON:
        issues.append(f"Python {'.'.join(map(str, MINIMUM_PYTHON))}+ required, found {sys.version}")
    return issues
```

#### Category 2: Node.js / npm (required for generated app development)

```python
import shutil
import subprocess
import re

NODE_MINIMUM = (20, 9, 0)

def check_node() -> list[str]:
    issues = []
    node_path = shutil.which("node")
    if not node_path:
        issues.append("Node.js not found. Install from https://nodejs.org (v20.9+ required for Next.js 16)")
        return issues

    result = subprocess.run(["node", "--version"], capture_output=True, text=True)
    match = re.match(r"v(\d+)\.(\d+)\.(\d+)", result.stdout.strip())
    if match:
        version = tuple(int(x) for x in match.groups())
        if version < NODE_MINIMUM:
            issues.append(f"Node.js {'.'.join(map(str, NODE_MINIMUM))}+ required, found {result.stdout.strip()}")

    npm_path = shutil.which("npm")
    if not npm_path:
        issues.append("npm not found. Reinstall Node.js.")

    return issues
```

#### Category 3: Cloud CLI Tools (per-provider, checked lazily)

```python
PROVIDER_PREREQUISITES = {
    "vercel": [],  # vercel-cli Python package bundles its own Node.js
    "aws": [
        ("aws", "AWS CLI — install via https://aws.amazon.com/cli/"),
        ("cdk", "AWS CDK CLI — pip install aws-cdk-cli OR npm install -g aws-cdk"),
    ],
    "gcp": [
        ("gcloud", "Google Cloud SDK — install via https://cloud.google.com/sdk/install"),
        ("docker", "Docker — required for gcloud source deploy"),
    ],
}

def check_cloud_prerequisites(provider: str) -> list[str]:
    issues = []
    for cmd, install_hint in PROVIDER_PREREQUISITES.get(provider, []):
        if not shutil.which(cmd):
            issues.append(f"'{cmd}' not found. {install_hint}")
    return issues
```

#### Category 4: Anthropic API Key

```python
import os

def check_api_key() -> list[str]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ["ANTHROPIC_API_KEY environment variable not set."]
    return []
```

**No new dependencies.** All checks use `shutil`, `subprocess`, `os`, `socket`, and `re` from stdlib.

**Confidence:** HIGH — standard Python patterns, no library API to verify.

---

### Summary: New Dependencies for v2.0

| Package | Version | Added To | Why |
|---------|---------|---------|-----|
| `vercel-cli` | `>=50.0.0` | `dependencies` (always) | Python wrapper for Vercel CLI; bundles Node.js; replaces subprocess-based vercel deploy |
| `aws-cdk-lib` | `>=2.240.0` | `optional-dependencies[aws]` | AWS CDK Python constructs for CloudFormation/Lambda/S3 |
| `open-next-cdk` | `>=0.1.0` | `optional-dependencies[aws]` | Converts Next.js standalone output to Lambda-compatible format |
| `constructs` | `>=10.0.0` | `optional-dependencies[aws]` | Required peer dep for aws-cdk-lib |

**No new dependencies** for:
- GCP deployment (stdlib subprocess + gcloud CLI)
- Environment detection (stdlib only)
- Local dev server (stdlib socket + subprocess)
- MCP distribution (fastmcp already in dependencies)

#### Updated pyproject.toml additions

```toml
[project]
dependencies = [
    "claude-agent-sdk>=0.1.50",
    "fastmcp>=3.1.0",
    "httpx>=0.28.0",
    "jsonschema>=4.20.0",
    "mcp>=1.26.0",
    "pyyaml>=6.0",
    "vercel-cli>=50.0.0",  # NEW: Python wrapper for Vercel CLI
]

[project.optional-dependencies]
aws = [
    "aws-cdk-lib>=2.240.0",
    "constructs>=10.0.0",
    "open-next-cdk>=0.1.0",
]
mcp = []  # fastmcp already in main deps; this extra exists for documentation clarity

[project.scripts]
web-app-factory = "web_app_factory.cli:main"
web-app-factory-mcp = "web_app_factory.mcp_server:main"
```

---

### What NOT to Add (v2.0 Scope)

| Package | Why Not |
|---------|---------|
| `portpicker` | Test-infrastructure library; stdlib `socket.bind(('localhost', 0))` is idiomatic and sufficient |
| `google-cloud-run` Python SDK | REST API wrapper, not a deploy tool; `gcloud` CLI does the job with zero Python dependencies |
| `google-auth` / `google-api-python-client` | Heavy; not needed when `gcloud` CLI handles auth |
| `.mcpb` / `@anthropic-ai/mcpb` toolchain | Broken for Python MCP servers with compiled deps (pydantic); use `fastmcp install claude-code` instead |
| `semver` (PyPI) | Stdlib `tuple` comparison on version strings is sufficient for our detection needs |
| `cdk-nextjs` (cdklabs TypeScript) | TypeScript-first; Python JSII bindings lag; `open-next-cdk` has native Python package |
| Node.js as system requirement | `vercel-cli` Python package bundles its own Node.js; users should not need to install Node.js to USE the factory (they need it to DEVELOP the generated apps) |

---

### Integration Points with Existing Stack

| Existing Component | v2.0 Integration |
|-------------------|------------------|
| `deploy-agent` (Phase 3) | Extends to call `DeploymentProvider.deploy()` instead of hardcoded Vercel CLI commands |
| `fastmcp` MCP server (approval gates) | The same server gets the three new tools: `generate_app`, `get_status`, `approve_phase` |
| `pipeline_state.py` | Stores `deployment_provider` selection and `local_preview_url` in pipeline state |
| `next.config.ts` (generated apps) | Adds `output: process.env.NEXT_BUILD_TARGET === 'standalone' ? 'standalone' : undefined` |
| `vercel.json` generator | Continues to work; no changes needed for Vercel path |
| CLI entry point | Adds `--cloud [vercel|aws|gcp]` flag and `--local-only` flag |

---

## v1.0 Stack (Unchanged — Reference)

The sections below are preserved from the v1.0 research (2026-03-21). Do not modify based on v2.0 research — these are validated and in production.

---

### Stack 1: Pipeline (Python Orchestration)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.10+ | Runtime | Required by Claude Agent SDK |
| `claude-agent-sdk` | 0.1.50 | LLM orchestration | Agent loop + MCP tool support; proven in v1.0 |
| `fastmcp` | 3.1.1 | MCP server for approval gates | De-facto standard; 1M+ downloads/day |
| `uv` | latest | Package manager | 10–100x faster than pip; already used |
| `ruff` | 0.15.4+ | Linter + formatter | Single tool; already configured |
| `pytest` | 9.0+ | Test runner | Standard; 447+ tests already pass |

### Stack 2: Generated Web Applications (Next.js)

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 16.2.0 | Full-stack React framework; App Router; Turbopack |
| React | 19.2 | UI library |
| TypeScript | 5.1+ | Type safety |
| Tailwind CSS | 4.2.2 | Styling; Oxide engine |
| shadcn/ui | latest | Component library |
| Zod | 4.x | Runtime validation |
| Vitest | 4.1.0 | Unit testing |
| Playwright | 1.58.2 | E2E + quality gates |

Full v1.0 stack details: See git history for 2026-03-21 STACK.md.

---

## Sources

- [FastMCP PyPI — v3.1.1, March 14 2026](https://pypi.org/project/fastmcp/) — **HIGH confidence**
- [FastMCP Claude Code Integration](https://gofastmcp.com/integrations/claude-code) — `fastmcp install claude-code` command details — **HIGH confidence**
- [FastMCP MCP JSON Configuration](https://gofastmcp.com/integrations/mcp-json-configuration) — `uv run` transport pattern — **HIGH confidence**
- [Claude Code MCP Docs](https://code.claude.com/docs/en/mcp) — `claude mcp add --scope user|project` scopes — **HIGH confidence**
- [mcpb GitHub](https://github.com/modelcontextprotocol/mcpb) — .mcpb format; Python compiled extension limitation — **HIGH confidence**
- [Anthropic Desktop Extensions Blog](https://www.anthropic.com/engineering/desktop-extensions) — .mcpb is for Claude Desktop; Python limitation confirmed — **HIGH confidence**
- [vercel-cli Python PyPI — v50.35.0](https://github.com/nuage-studio/vercel-cli-python) — bundles Node.js, `run_vercel()` API, 101 releases active — **HIGH confidence**
- [open-next-cdk PyPI](https://pypi.org/project/open-next-cdk/) — Python package for CDK + Next.js on AWS — **MEDIUM confidence** (architecture verified, exact latest version requires implementation-time pinning)
- [aws-cdk-lib PyPI — v2.240.0+](https://pypi.org/project/aws-cdk-lib/) — Python CDK library, Python 3.9+ — **HIGH confidence**
- [Google Cloud Run — Deploy Next.js](https://docs.cloud.google.com/run/docs/quickstarts/frameworks/deploy-nextjs-service) — `gcloud run deploy --source .` pattern — **HIGH confidence**
- [google-cloud-run PyPI — v0.15.0](https://pypi.org/project/google-cloud-run/) — REST API client (NOT recommended for deploy automation) — **HIGH confidence** (confirmed it is the wrong tool)
- [Next.js output standalone docs](https://nextjs.org/docs/app/api-reference/config/next-config-js/output) — standalone mode, `server.js`, `PORT` env var — **HIGH confidence**
- WebSearch: `next dev` port flag, `-p` option — **HIGH confidence** (multiple consistent sources)

---

*Stack research for: web-app-factory v2.0 — MCP App distribution, local dev server, multi-cloud deploy*
*Researched: 2026-03-23*
