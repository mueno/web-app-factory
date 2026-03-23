# Architecture Patterns: MCP App Integration

**Domain:** MCP App packaging + local dev server + multi-cloud deploy for web-app-factory v2.0
**Researched:** 2026-03-23
**Confidence:** HIGH (MCP packaging, FastMCP tasks), MEDIUM (deploy abstraction, local server lifecycle)

---

## Context: What v1.0 Already Has

The existing pipeline has three layers worth understanding before adding v2.0 concerns:

```
factory.py (CLI) → contract_pipeline_runner → phase executors (1a/1b/2a/2b/3)
                                          ↑
             pipeline_state (state.json, activity-log.jsonl)
             factory_mcp_server (approve_gate, phase_reporter)  ← internal use only
             pipeline_runtime (startup_preflight, governance_monitor, error_router)
```

The existing `factory_mcp_server.py` (FastMCP, stdio) is an **internal process** — it handles human approval gates and phase progress logging. It is started as a subprocess by the pipeline and is NOT the user-facing MCP App. This distinction is critical for v2.0 design.

---

## Recommended Architecture for v2.0

### Overview

v2.0 adds a new user-facing layer on top of the existing pipeline. The existing code does not change its internal contracts — the MCP App becomes a thin adapter that calls `run_pipeline()` and `load_contract()` the same way `factory.py` does today.

```
┌─────────────────────────────────────────────────────────────┐
│   USER-FACING MCP APP LAYER (NEW)                           │
│                                                             │
│   web_app_factory/mcp_app.py  ← FastMCP server             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  Tools (exposed to Claude):                         │   │
│   │    generate_app(idea, deploy_target, mode)          │   │
│   │    get_pipeline_status(run_id)                      │   │
│   │    approve_phase(run_id, phase, decision)           │   │
│   │    list_runs()                                      │   │
│   │    get_preview_url(run_id)                          │   │
│   │    start_local_server(run_id)                       │   │
│   │    stop_local_server(run_id)                        │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────────┘
                      │  calls existing API
┌─────────────────────▼───────────────────────────────────────┐
│   EXISTING PIPELINE (UNCHANGED)                             │
│                                                             │
│   contract_pipeline_runner.run_pipeline()                   │
│   factory.py (CLI remains functional)                       │
│   pipeline_state, phase_executors, gates, agents            │
│                                                             │
│   Internal MCP: factory_mcp_server.py (approve + reporter)  │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│   NEW SUPPORTING MODULES                                    │
│                                                             │
│   deploy/                                                   │
│     deploy_provider.py    ← abstract base                   │
│     vercel_provider.py    ← existing logic extracted here   │
│     aws_provider.py       ← new                             │
│     gcp_provider.py       ← new                             │
│     provider_registry.py  ← maps name -> class              │
│                                                             │
│   local_server/                                             │
│     server_manager.py     ← subprocess lifecycle            │
│     port_allocator.py     ← find free port                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Integration Point 1: MCP App Packaging

### How `claude mcp add` Works

MCP servers for Claude Code are installed via:
```bash
# Python package via uvx (recommended for PyPI distribution)
claude mcp add web-app-factory -- uvx web-app-factory

# Or directly from local checkout (development)
claude mcp add web-app-factory -- uv --directory /path/to/web-app-factory run web_app_factory/mcp_app.py

# Or via npx for node-based servers (not applicable here)
```

The server runs as a **stdio process** (stdin/stdout JSON-RPC). This is the same transport the existing `factory_mcp_server.py` uses. Claude Code keeps it running for the session lifetime.

### pyproject.toml Entry Point (Required)

```toml
[project.scripts]
web-app-factory = "web_app_factory.mcp_app:main"
```

Where `main()` calls `mcp.run(transport="stdio")`. This is the executable that `uvx web-app-factory` runs after PyPI install.

The package name on PyPI must match: `web-app-factory` (kebab case). The Python module uses underscore: `web_app_factory`.

### MCP App Source Layout Change

The current project has no top-level Python package (code is in `tools/`, `pipeline_runtime/`, `agents/`, `config/`). For `uvx web-app-factory` to work, there needs to be an importable package. Two options:

**Option A: Add `web_app_factory/` package (recommended)**
```
web_app_factory/
  __init__.py
  mcp_app.py          ← new user-facing MCP server
  _pipeline_bridge.py ← thin wrapper calling run_pipeline()
```
The existing `tools/`, `pipeline_runtime/`, etc. stay as-is. `mcp_app.py` imports from them.

**Option B: Make the project root itself the package**
Not recommended — breaks existing relative imports in `tools/`.

**Verdict: Option A.** Add `web_app_factory/` as the new public API surface. Internal modules untouched.

### .mcp.json for Project-scoped Installation

For teams sharing the repo, add `.mcp.json` at project root:
```json
{
  "mcpServers": {
    "web-app-factory": {
      "command": "uv",
      "args": ["--directory", ".", "run", "web_app_factory/mcp_app.py"],
      "env": {
        "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}"
      }
    }
  }
}
```

---

## Integration Point 2: MCP Tool → Pipeline Entry Point Mapping

### Tool Design Principles

The pipeline is inherently long-running (minutes to hours). MCP tools must either:
1. Return immediately with a `run_id` and let the user poll via `get_pipeline_status`, or
2. Use FastMCP's `task=True` background task decorator (FastMCP 3.x) with progress tracking.

**Verdict: Use FastMCP background tasks for `generate_app`, immediate returns for status/control tools.**

FastMCP 3.x `task=True` pattern:
```python
@mcp.tool(task=True)
async def generate_app(idea: str, deploy_target: str = "vercel") -> str:
    """Generate and deploy a web application from an idea."""
    # runs in background, returns immediately to Claude with task_id
    # progress updates via Progress dependency
    ...
```

### Tool → Pipeline Mapping

| MCP Tool | Calls Into | Notes |
|----------|-----------|-------|
| `generate_app(idea, deploy_target, mode)` | `run_pipeline()` | Background task. Returns run_id. |
| `get_pipeline_status(run_id)` | `load_state()` | Reads state.json. Immediate. |
| `approve_phase(run_id, decision)` | Writes approval response file | Same mechanism as current `approve_gate` |
| `list_runs()` | Scans output/ dir for state.json files | Immediate. |
| `get_preview_url(run_id)` | Reads `deployment.json` | Immediate. |
| `start_local_server(run_id)` | `ServerManager.start()` | Immediate, returns port. |
| `stop_local_server(run_id)` | `ServerManager.stop()` | Immediate. |
| `check_environment()` | `run_startup_preflight()` | Environment check. Immediate. |

### The `approve_phase` Tool: Replacing the File-Poll Gate

Current architecture: `factory_mcp_server.py` exposes `approve_gate` as an MCP tool that the Claude **agent** running the pipeline calls. The agent polls a file.

v2.0 architecture: The user-facing MCP App exposes `approve_phase` that the **user's Claude session** calls when they want to approve or reject. The internal agent still calls `approve_gate`. The MCP App bridges these:

```
User Claude ──[approve_phase(run_id, "yes")]──► MCP App
                                                   │ writes response file
                                              Internal agent polls file
                                              Internal agent reads "yes"
                                              Internal agent proceeds
```

This means the existing file-based polling in `approve_gate` is preserved. The MCP App just writes the response file in the correct format. No changes to `factory_mcp_server.py`.

### Interactive (Phase-by-Phase) Mode

The `mode` parameter on `generate_app` controls whether the pipeline auto-approves gates or waits:

```python
generate_app(idea="recipe app", mode="interactive")  # pauses at each gate
generate_app(idea="recipe app", mode="auto")          # auto-approves (WEB_FACTORY_APPROVAL_TIMEOUT_SEC=0 → auto)
```

In `interactive` mode, the pipeline pauses at `approve_gate`. The MCP App can surface the pending approval as a notification to the user. The user calls `approve_phase` to unblock.

---

## Integration Point 3: Deploy Provider Abstraction Layer

### Problem

Phase 3 executor (`phase_3_executor.py`) has Vercel tightly coupled throughout — `vercel link`, `vercel deploy`, `vercel promote`. To support AWS Amplify and GCP Cloud Run, this logic must be extracted behind an interface.

### Abstraction Interface

```python
# deploy/deploy_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class DeployResult:
    success: bool
    preview_url: str | None = None
    production_url: str | None = None
    error: str | None = None
    raw_output: str = ""

class DeployProvider(ABC):
    """Abstract deploy provider. One implementation per cloud target."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier: 'vercel', 'aws', 'gcp'"""
        ...

    @abstractmethod
    def provision(self, project_dir: str, project_name: str) -> DeployResult:
        """Link/initialize the project with the platform."""
        ...

    @abstractmethod
    def deploy_preview(self, project_dir: str) -> DeployResult:
        """Deploy to a preview/staging environment. Returns preview_url."""
        ...

    @abstractmethod
    def deploy_production(self, project_dir: str, preview_url: str) -> DeployResult:
        """Promote preview to production."""
        ...

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if credentials are available for this provider."""
        ...
```

### Provider Implementations

**VercelProvider** (extracted from existing phase_3_executor.py):
- `provision`: `vercel link --yes`
- `deploy_preview`: `vercel deploy` → parse URL from stdout with `_VERCEL_URL_RE`
- `deploy_production`: `vercel promote {preview_url} --yes --timeout=5m`

**AWSProvider** (new):
- Uses `amplify` CLI or `aws cloudfront` + S3
- Next.js on AWS: AWS Amplify is the lowest-friction option for Next.js
- `provision`: `amplify init && amplify add hosting`
- `deploy_preview`: `amplify publish` with branch-based preview
- Complexity: HIGH — Amplify requires AWS credentials, region, account ID

**GCPProvider** (new):
- Uses Cloud Run (containerized) or Firebase Hosting
- For Next.js: Firebase Hosting + Cloud Functions or Cloud Run
- `provision`: `firebase init hosting` or `gcloud run deploy`
- Complexity: HIGH — requires Dockerfile for Cloud Run; Firebase is simpler but limited

**Verdict for v2.0:** Vercel is fully implemented (extracted). AWS and GCP are stubbed with clear provider interface. The architecture is set, implementations are deferred.

### Provider Registry

```python
# deploy/provider_registry.py
_REGISTRY: dict[str, type[DeployProvider]] = {}

def register_provider(cls: type[DeployProvider]) -> type[DeployProvider]:
    _REGISTRY[cls().name] = cls
    return cls

def get_provider(name: str) -> DeployProvider:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown deploy provider: {name!r}. Available: {list(_REGISTRY)}")
    return cls()
```

### Phase 3 Executor Refactor

The key change: `Phase3ShipExecutor` receives a `DeployProvider` instance (injected via `PhaseContext.extra["deploy_provider"]`) instead of calling `vercel` CLI directly.

```python
# In contract_pipeline_runner.py (or factory.py):
from deploy.provider_registry import get_provider

provider = get_provider(args.deploy_target)  # "vercel", "aws", "gcp"
# inject into PhaseContext.extra
ctx = PhaseContext(..., extra={"deploy_provider": provider})
```

This is a surgical change to Phase 3 only. Phases 1a, 1b, 2a, 2b are untouched.

---

## Integration Point 4: Local Dev Server Lifecycle

### Requirements

- Start `npm run dev` in the generated project's Next.js directory
- Detect when the server is ready (port listening, not just process started)
- Return the URL to the user
- Track running servers by `run_id`
- Stop servers on request or session end

### Implementation: ServerManager

```python
# local_server/server_manager.py

import asyncio
import subprocess
import socket
import time
from pathlib import Path

class LocalDevServer:
    def __init__(self, run_id: str, project_dir: Path, port: int):
        self.run_id = run_id
        self.project_dir = project_dir
        self.port = port
        self.process: subprocess.Popen | None = None
        self.url: str = f"http://localhost:{port}"

    def start(self) -> None:
        """Start npm run dev. Non-blocking."""
        self.process = subprocess.Popen(
            ["npm", "run", "dev", "--", "-p", str(self.port)],
            cwd=str(self.project_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def wait_ready(self, timeout: float = 60.0) -> bool:
        """Poll until port is listening or timeout. Returns True if ready."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("localhost", self.port), timeout=1.0):
                    return True
            except (ConnectionRefusedError, OSError):
                time.sleep(1.0)
        return False

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()

class ServerManager:
    """Tracks active local dev servers by run_id."""

    def __init__(self) -> None:
        self._servers: dict[str, LocalDevServer] = {}

    def start(self, run_id: str, project_dir: Path) -> tuple[bool, str]:
        """Start dev server. Returns (success, url_or_error)."""
        if run_id in self._servers:
            s = self._servers[run_id]
            if s.process and s.process.poll() is None:
                return True, s.url  # already running

        port = self._find_free_port()
        server = LocalDevServer(run_id, project_dir, port)
        server.start()
        if server.wait_ready():
            self._servers[run_id] = server
            return True, server.url
        server.stop()
        return False, "Server did not start within timeout"

    def stop(self, run_id: str) -> None:
        server = self._servers.pop(run_id, None)
        if server:
            server.stop()

    def stop_all(self) -> None:
        for server in list(self._servers.values()):
            server.stop()
        self._servers.clear()

    @staticmethod
    def _find_free_port(start: int = 3000, end: int = 3100) -> int:
        for port in range(start, end):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("localhost", port))
                    return port
            except OSError:
                continue
        raise RuntimeError("No free port found in range 3000-3100")
```

**MCP App lifecycle:** `ServerManager` is a module-level singleton in `mcp_app.py`. On MCP server shutdown, `stop_all()` is called. This ensures no orphaned `npm run dev` processes.

---

## Component Boundaries (New vs. Modified)

### New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| User-facing MCP server | `web_app_factory/mcp_app.py` | Exposes tools to Claude, background tasks |
| Pipeline bridge | `web_app_factory/_pipeline_bridge.py` | Calls `run_pipeline()` in thread pool |
| Deploy provider base | `deploy/deploy_provider.py` | Abstract interface |
| Deploy provider registry | `deploy/provider_registry.py` | Maps name → class |
| Vercel provider (extracted) | `deploy/vercel_provider.py` | Existing Vercel logic |
| AWS provider (stub) | `deploy/aws_provider.py` | Stub + interface |
| GCP provider (stub) | `deploy/gcp_provider.py` | Stub + interface |
| Local server manager | `local_server/server_manager.py` | Subprocess lifecycle |
| Port allocator | `local_server/port_allocator.py` | (inline in server_manager or separate) |

### Modified Components

| Component | Location | Change |
|-----------|----------|--------|
| Phase 3 executor | `tools/phase_executors/phase_3_executor.py` | Accept `DeployProvider` from `PhaseContext.extra`; call `provider.deploy_preview()` etc. instead of `vercel` directly |
| `PhaseContext` | `tools/phase_executors/base.py` | `extra` dict already exists — no schema change needed |
| `startup_preflight.py` | `pipeline_runtime/startup_preflight.py` | Make Vercel CLI check conditional on deploy_target=vercel |
| `pyproject.toml` | root | Add `[project.scripts]` entry point for `web-app-factory` |
| `config/settings.py` | root | Add env vars for deploy provider selection |

### Unchanged Components

Everything else: `factory_mcp_server.py`, `contract_pipeline_runner.py`, `pipeline_state.py`, all gate implementations (1–9), phase executors 1a/1b/2a/2b, `governance_monitor.py`, `error_router.py`, YAML contract.

---

## Data Flow Changes

### v1.0 Flow (unchanged internally)

```
User → CLI (factory.py) → run_pipeline() → phases → state.json
```

### v2.0 Additional Flow

```
User Claude session
       │ calls MCP tool
       ▼
MCP App (web_app_factory/mcp_app.py)
  generate_app(idea="...", deploy_target="vercel")
       │ submits background task
       ▼
Thread pool / asyncio task
  _pipeline_bridge.run_pipeline_async(idea, project_dir, deploy_provider)
       │ calls
       ▼
  contract_pipeline_runner.run_pipeline(...)
       │ phases 1a → 1b → 2a → 2b → 3
       │ Phase 3 calls provider.deploy_preview()
       │ deploy_provider = VercelProvider() (or AWSProvider etc.)
       │ state changes written to state.json
       ▼
  returns {"status": "completed", "run_id": "..."}

User Claude session
  get_pipeline_status(run_id) → reads state.json → returns summary
  get_preview_url(run_id) → reads deployment.json → returns URL
  start_local_server(run_id) → ServerManager.start() → returns localhost:3000
```

### State Files (Unchanged Locations)

```
output/{slug}/
  docs/pipeline/
    runs/{run_id}/
      state.json          ← phase status (read by get_pipeline_status)
      handoff.md          ← human-readable summary
    activity-log.jsonl    ← events log
    deployment.json       ← preview_url, production_url (read by get_preview_url)
    startup-preflight.json
```

---

## Suggested Build Order (Dependency-Driven)

**Phase A: Foundation (no deps)**
1. Add `web_app_factory/` package with `__init__.py`
2. Update `pyproject.toml` with entry point and package discovery
3. Write `web_app_factory/mcp_app.py` skeleton with FastMCP, no tools yet
4. Write `web_app_factory/_pipeline_bridge.py` wrapping `run_pipeline()` in asyncio

**Phase B: Deploy Abstraction (deps: Phase A)**
5. Create `deploy/deploy_provider.py` (abstract base + `DeployResult`)
6. Create `deploy/provider_registry.py`
7. Extract Vercel logic from `phase_3_executor.py` into `deploy/vercel_provider.py`
8. Modify `phase_3_executor.py` to use `PhaseContext.extra["deploy_provider"]`
9. Add AWS and GCP stubs
10. Update `startup_preflight.py` to gate Vercel CLI check on `deploy_target`

**Phase C: Local Server (deps: Phase A)**
11. Write `local_server/server_manager.py`
12. Write integration tests for start/stop/port-detection

**Phase D: MCP Tools (deps: Phase A, B, C)**
13. Add `generate_app` tool (background task, calls `_pipeline_bridge`)
14. Add `get_pipeline_status`, `list_runs`, `get_preview_url` tools
15. Add `approve_phase` tool (writes approval file)
16. Add `start_local_server`, `stop_local_server` tools
17. Add `check_environment` tool (calls `run_startup_preflight`)

**Phase E: Environment Detection + UX Polish**
18. Add environment setup guidance in `check_environment` responses
19. Add `.mcp.json` for project-scoped installation
20. Update `README.md` with `claude mcp add` installation instruction

**Why this order:**
- Deploy abstraction (Phase B) can be done independently of MCP packaging
- Local server (Phase C) can be done independently of deploy abstraction
- MCP tools (Phase D) depend on B and C being testable
- Phases B and C can be done in parallel; Phase D requires both complete

---

## Key Architectural Decisions

### 1. User-facing MCP App is a Separate Module from Internal MCP Server

Do not extend `factory_mcp_server.py` with user-facing tools. That server is an internal agent tool (approve_gate, phase_reporter). The user-facing MCP App is a separate FastMCP instance in `web_app_factory/mcp_app.py`.

**Rationale:** Different trust boundaries, different transports (internal server may be started per-pipeline-run; user-facing server runs for entire session), different tool contracts.

### 2. `run_pipeline()` Called in Thread Pool (Not Direct Async)

`run_pipeline()` is synchronous (blocking I/O via subprocess). Calling it directly in an async FastMCP tool would block the event loop. Wrap it:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=2)

async def _run_pipeline_async(idea: str, project_dir: str, **kwargs) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: run_pipeline(contract=..., idea=idea, project_dir=project_dir, **kwargs)
    )
```

**Do NOT make `run_pipeline()` itself async** — it uses `subprocess.run()` calls throughout which would need `asyncio.create_subprocess_exec()`. That's a large refactor across all phase executors.

### 3. Deploy Provider Injected via `PhaseContext.extra`

The `extra: dict` field on `PhaseContext` already exists and is free-form. Injecting `deploy_provider` there avoids adding a typed field that breaks the dataclass `frozen=True` pattern and avoids a schema migration for the contract YAML.

### 4. Vercel CLI Check Made Conditional in Preflight

Currently, `startup_preflight.py` always checks for `vercel` CLI. With multi-cloud, the check should only fail if `deploy_target == "vercel"`. Pass `deploy_target` to `run_startup_preflight()`.

### 5. MCP App Server is a Singleton Process, Not Per-Run

The FastMCP server in `mcp_app.py` starts once when Claude loads the MCP server and stays alive. Multiple `generate_app` calls create multiple pipeline runs (different `run_id`). The `ServerManager` must be thread-safe (or use asyncio locks) since background tasks can run concurrently.

---

## Pitfalls Specific to This Integration

### Blocking `run_pipeline()` in Async Context

The biggest risk. `run_pipeline()` calls `subprocess.run()` (blocking) across all phase executors. If called directly in an async FastMCP tool without `run_in_executor`, it will block the entire MCP server event loop, preventing `get_pipeline_status` from responding while a pipeline runs.

**Prevention:** Always use `loop.run_in_executor()` for `run_pipeline()`.

### MCP Server Lifetime vs. Pipeline Lifetime

The FastMCP stdio server exits when Claude's session ends. If a pipeline is running and the session closes, the pipeline thread is orphaned. The `run_pipeline()` function writes state to disk, so the pipeline can be resumed via `--resume` in a new session, but in-progress state is not cleanly handed off.

**Prevention:** Write `run_id` to a well-known location (e.g., `~/.web-factory/active-runs.json`) so the next session can resume. Or accept the limitation and document it.

### Deploy Provider Stub APIs Break Phase 3 Tests

Extracting Vercel logic into `VercelProvider` changes the surface that Phase 3 executor tests mock. All existing Phase 3 tests mock `subprocess.run` for `vercel` commands. After extraction, they need to mock `VercelProvider.deploy_preview()` instead.

**Prevention:** Add `deploy_provider` injection support to existing Phase 3 tests before refactoring the executor.

### npm Run Dev Port Conflicts

Port 3000 is the Next.js default and is often already in use. The `ServerManager._find_free_port()` must search starting from 3000. If the user has multiple runs active, each needs its own port.

**Prevention:** `_find_free_port()` scans 3000-3100 using socket bind test (already in design above).

### `uvx web-app-factory` Requires All Dependencies at PyPI Publish Time

When users install via `uvx`, all dependencies (`fastmcp`, `mcp`, `claude-agent-sdk`, `pyyaml`, etc.) must be published in `pyproject.toml` `[project.dependencies]`. They already are. But the user also needs Node.js, npm, and optionally Vercel CLI installed separately — `uvx` cannot provide these.

**Prevention:** `check_environment` MCP tool surfaces missing dependencies clearly with install instructions. `startup_preflight.py` already does this — surface its output in the MCP tool response.

---

## Sources

- [MCP Apps Blog Post](https://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/) — MCP Apps extension specification
- [Anthropic Desktop Extensions](https://www.anthropic.com/engineering/desktop-extensions) — .mcpb packaging for Claude Desktop
- [Claude Code MCP Docs](https://code.claude.com/docs/en/mcp) — `claude mcp add` syntax, stdio/http/sse transports, uvx installation
- [FastMCP Background Tasks](https://gofastmcp.com/servers/tasks) — task=True decorator, Progress dependency (HIGH confidence)
- [FastMCP 3.0 Launch](https://www.jlowin.dev/blog/fastmcp-3-launch) — Component composition, authorization, OpenTelemetry
- [MCP Official Build Guide](https://modelcontextprotocol.io/docs/develop/build-server) — Python package structure, uv/uvx patterns, Claude Desktop config
- [OpenNext](https://opennext.js.org/) — Next.js multi-platform deployment adapters (AWS, Cloudflare, Netlify)
- [Next.js Deployment Guide](https://nextjs.org/docs/pages/getting-started/deploying) — Platform deployment options (MEDIUM confidence, AWS/GCP specifics)
