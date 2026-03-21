# Phase 1: Infrastructure - Research

**Researched:** 2026-03-21
**Domain:** Python pipeline orchestration fork — ios-app-factory infrastructure adapted for web app generation
**Confidence:** HIGH — primary source is direct inspection of the ios-app-factory codebase at `/Users/masa/Development/ios-app-factory/`

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Fork strategy:** Copy domain-agnostic files verbatim from ios-app-factory: `contract_pipeline_runner.py`, `pipeline_state.py`, `factory_mcp_server.py`, `governance_monitor.py`, `error_router.py`. Adapt `factory.py` (strip iOS flags, add web flags). Adapt `startup_preflight.py` for web tools. Do NOT copy phase executors, agent definitions, or iOS-specific gates.
- **YAML contract:** `contracts/pipeline-contract.web.v1.yaml` with 5 sub-phases (1a, 1b, 2a, 2b, 3). Each entry has `purpose`, `deliverables` with `quality_criteria`, `gates`. Quality criteria must be content-verifying. Contract validated against JSON schema at startup (CONT-03). Quality self-assessment `quality-self-assessment-{phase_id}.json` before every gate (CONT-04).
- **CLI interface:** `python factory.py --idea "description" --project-dir ./output/AppName`. Flags: `--deploy-target vercel`, `--framework nextjs`, `--dry-run`, `--resume`.
- **Project setup:** `pyproject.toml` with uv. Dependencies: `claude-agent-sdk>=0.1.50`, `mcp>=1.26.0`, `fastmcp>=3.1.0`, `httpx>=0.28.0`. Directory mirrors ios-app-factory: `tools/`, `agents/`, `contracts/`, `pipeline_runtime/`, `config/`, `output/`.
- **Startup preflight checks:** Node.js 20.9+, npm, Vercel CLI, Python 3.10+, Claude CLI reachability.
- **MCP server:** Reuse `factory_mcp_server.py` as-is. Single implementation rule. Integration test asserts `state.json` updates after `phase_reporter` MCP call.
- **Agents stub:** `agents/definitions.py` with placeholder web agent names (spec-agent, build-agent, deploy-agent).

### Claude's Discretion

- Exact directory structure within `tools/` (as long as it follows ios-app-factory patterns)
- Test file organization
- Exact error messages in preflight checks
- Config module design (`config/settings.py` adaptation)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PIPE-01 | Pipeline executes phases in order defined by YAML contract, blocking on gate failure | `contract_pipeline_runner.py` (verbatim copy) handles phase loop and gate blocking; PHASE_ORDER constant in `pipeline_state.py` must be updated to web phase IDs |
| PIPE-02 | Pipeline state persists to `state.json` and `activity-log.jsonl`, surviving interruption | `pipeline_state.py` (verbatim copy) provides full state persistence — `_write_state()` and `_append_activity_log()` are domain-agnostic |
| PIPE-03 | Pipeline resumes from last completed phase after interruption | `pipeline_state.py` provides `get_resume_phase()` and `find_latest_run()`; resume logic is domain-agnostic |
| PIPE-04 | MCP server provides approval gates for human-in-the-loop sign-off | `factory_mcp_server.py` (verbatim copy) provides `approve_gate` and `phase_reporter` MCP tools via FastMCP; file-based polling for approval response |
| PIPE-05 | Governance monitor detects and blocks phase skipping, direct file edits, and gate bypasses | `governance_monitor.py` (verbatim copy) — `GovernanceViolationError` fires for `phase_order_violation`, `write_without_phase_start`, `gate_before_phase_violation`; all blocking violation kinds are domain-agnostic |
| PIPE-06 | CLI entry point accepts `--idea` and `--project-dir` flags | Adapt `factory.py` — strip iOS flags (`--mode rejection-fix`, `--asc-app-id`, `--listing-mode`, `--auto-ideate`), add `--deploy-target`, `--framework` |
| PIPE-07 | Startup preflight validates environment (Node.js, Python, Vercel CLI) before execution | Adapt `startup_preflight.py` — replace Xcode/xcrun/simctl checks with `node --version`, `npm --version`, `vercel --version` checks; single-flight lock logic is reusable verbatim |
| CONT-01 | YAML contract defines all phases with purpose, deliverables, quality criteria, and gate types | New file `contracts/pipeline-contract.web.v1.yaml`; structure mirrors ios-app-factory's `pipeline-contract.v1.yaml` with web-specific content |
| CONT-02 | Each deliverable has `quality_criteria` array driving content verification | Enforced by YAML structure: every deliverable block must have a `quality_criteria` list with specific, content-verifying strings |
| CONT-03 | Contract validated against JSON schema at pipeline startup | JSON schema file created alongside the YAML contract; `jsonschema.validate()` called in pipeline startup |
| CONT-04 | Quality self-assessment JSON generated before every gate submission | `QualitySelfAssessment` pattern from ios-app-factory's `_ExecuteModeExecutor` — adapted in Phase 1 as a stub pattern |

</phase_requirements>

---

## Summary

Phase 1 is a fork-and-adapt operation. The ios-app-factory pipeline infrastructure at `/Users/masa/Development/ios-app-factory/` is architecturally clean: domain-agnostic orchestration is completely separated from iOS-specific phase content. Five files (`pipeline_state.py`, `governance_monitor.py`, `error_router.py`, `factory_mcp_server.py`, and the gate dataclasses) can be copied verbatim with zero modification. Two files (`startup_preflight.py` and `factory.py`) need targeted adaptation — primarily removing iOS-specific code paths and adding web equivalents. The YAML contract is entirely new; the config module needs path rewiring.

The critical risk in Phase 1 is the dual implementation trap: `factory_mcp_server.py` has a `project_dir` bridge that writes to `state.json` — this bridge must remain intact in the copy. The integration test that asserts `state.json` is updated after a `phase_reporter` MCP call is the safety net. Missing this bridge is what caused the HealthStockBoardV30 incident in ios-app-factory.

**Primary recommendation:** Copy the five verbatim files first, write the YAML contract second, then adapt `factory.py` and `startup_preflight.py` against the contract. The YAML contract is the schema everything else is built against — writing it before the CLI keeps the data flow direction correct.

---

## Standard Stack

### Core (Pipeline — Python)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.10+ | Runtime | Required by Claude Agent SDK; ios-app-factory already uses 3.10+ |
| `claude-agent-sdk` | 0.1.50 (PyPI 2026-03-20) | LLM orchestration in phase executors (Phase 2+) | Same SDK as ios-app-factory; `AgentDefinition` dataclass and fallback shim needed in stub form for Phase 1 |
| `fastmcp` | 3.1.1 (PyPI 2026-03-14) | MCP server for `approve_gate` and `phase_reporter` | ios-app-factory's `factory_mcp_server.py` uses `from mcp.server.fastmcp import FastMCP`; `fastmcp` 3.x is the standard wrapper |
| `mcp` | 1.26.0+ | Base MCP protocol (fastmcp dependency) | Required by factory_mcp_server import path |
| `pyyaml` | 6.0+ | Parse YAML pipeline contract | Pipeline contract is YAML |
| `jsonschema` | 4.20+ | Validate YAML contract at startup (CONT-03) | Standard Python JSON Schema validator |
| `httpx` | 0.28+ | Async HTTP for future phase executor API calls | Matches ios-app-factory dependency |
| `uv` | latest (Astral) | Package manager | ios-app-factory uses uv; `uv run pytest` ensures lockfile sync |

### Development Tools

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| `pytest` | 9.0+ | Test runner | `uv run pytest -q` is the standard invocation |
| `ruff` | 0.15.4+ | Linter + formatter | Replaces Black + flake8; already configured in ios-app-factory's `pyproject.toml` — copy that config |
| `mypy` | 1.19.1+ | Static type checking | Optional but used in ios-app-factory |

**Installation:**

```bash
uv sync
# Install from lockfile (CI / first setup)
```

```toml
# pyproject.toml
[project]
name = "web-app-factory"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "claude-agent-sdk>=0.1.50",
    "fastmcp>=3.1.0",
    "httpx>=0.28.0",
    "jsonschema>=4.20.0",
    "mcp>=1.26.0",
    "pyyaml>=6.0",
]

[dependency-groups]
dev = [
    "mypy>=1.19.1",
    "pytest>=9.0.2",
    "ruff>=0.15.4",
]
```

---

## Architecture Patterns

### Recommended Project Structure

```
web-app-factory/
├── factory.py                              # CLI entry point (ADAPTED)
├── pyproject.toml                          # NEW
├── uv.lock                                 # NEW (generated)
│
├── contracts/
│   ├── pipeline-contract.web.v1.yaml       # NEW — 5-phase web contract
│   └── pipeline-contract.schema.json       # NEW — JSON schema for CONT-03
│
├── agents/
│   └── definitions.py                      # ADAPTED — stub web agent names
│
├── pipeline_runtime/
│   ├── governance_monitor.py               # COPY VERBATIM
│   ├── error_router.py                     # COPY VERBATIM (or minor agent-name tweaks)
│   └── startup_preflight.py               # ADAPTED — web tool checks
│
├── tools/
│   ├── contract_pipeline_runner.py         # COPY VERBATIM (v2 is split — see notes)
│   ├── pipeline_state.py                   # COPY VERBATIM + PHASE_ORDER update
│   ├── factory_mcp_server.py              # COPY VERBATIM (remove iOS-only renderers)
│   │
│   ├── phase_executors/                    # NEW stubs only in Phase 1
│   │   ├── __init__.py
│   │   ├── base.py                         # COPY VERBATIM from ios-app-factory
│   │   └── registry.py                     # COPY VERBATIM from ios-app-factory
│   │
│   └── gates/
│       ├── gate_result.py                  # COPY VERBATIM
│       └── gate_policy.py                  # COPY VERBATIM
│
├── config/
│   └── settings.py                         # ADAPTED — remove iOS paths, add web paths
│
├── tests/
│   ├── test_pipeline_state.py              # ADAPTED from ios-app-factory tests
│   ├── test_startup_preflight.py          # ADAPTED from ios-app-factory tests
│   ├── test_factory_mcp_bridge.py         # NEW — MCP→state.json integration test
│   └── test_contract_schema.py            # NEW — YAML contract validation test
│
└── output/                                 # Generated apps land here
    └── {AppName}/
        ├── src/                            # Next.js application (Phase 2+)
        └── docs/pipeline/                  # Pipeline artifacts
            ├── runs/{run_id}/
            │   ├── state.json
            │   └── handoff.md
            ├── activity-log.jsonl
            └── quality-self-assessment-*.json
```

### Pattern 1: Verbatim Copy with PHASE_ORDER Adaptation

**What:** Copy `pipeline_state.py` verbatim, then update exactly one constant.

**The constant to update:**

```python
# ios-app-factory (original):
PHASE_ORDER = ["1a", "1b", "1b+", "2c", "2d", "2a", "2b", "3", "4a", "5", "6"]

# web-app-factory (adapted):
PHASE_ORDER = ["1a", "1b", "2a", "2b", "3"]

PHASE_LABELS = {
    "1a": "Idea Validation",
    "1b": "Spec & Design",
    "2a": "Scaffold",
    "2b": "Build",
    "3": "Ship",
}
```

All other functions (`init_run`, `load_state`, `phase_start`, `phase_complete`, `mark_failed`, `find_latest_run`, `get_resume_phase`) are domain-agnostic and must not be changed.

### Pattern 2: factory.py CLI Adaptation

**What to strip (iOS-specific):**

```python
# REMOVE these args:
--mode rejection-fix
--rejection-reason
--asc-app-id
--listing-mode
--auto-ideate
--ideate-feedback
--ideate-selector
--ideate-provider
--app-plan
--backend  # hidden iOS compat flag
--auto-approve  # poipoi-studio specific
```

**What to add (web-specific):**

```python
# ADD these args:
--deploy-target  # choices=["vercel", "github-pages"], default="vercel"
--framework      # choices=["nextjs"], default="nextjs" (v1 only)
```

**What to keep unchanged:**

```python
--idea          # positional + named
--project-dir
--resume
--dry-run
--output-json
--unsafe-no-gates  # debug flag
```

### Pattern 3: Startup Preflight Web Adaptation

**What changes in `startup_preflight.py`:**

```python
# ios-app-factory checks (REMOVE):
# - Xcode CLI tools presence: xcode-select --print-path
# - xcodebuild version
# - simctl availability
# - xcrun sanity check

# web-app-factory checks (ADD):
def _check_nodejs(which, run_subprocess) -> dict:
    """Node.js 20.9+ required by Next.js 16."""
    node = which("node")
    if not node:
        return {"passed": False, "reason": "node not found in PATH"}
    proc = run_subprocess(["node", "--version"], capture_output=True, text=True, timeout=10)
    # Parse 'v20.9.0' -> (20, 9, 0); fail if < (20, 9, 0)
    ...

def _check_npm(which, run_subprocess) -> dict:
    """npm required for Next.js project management."""
    ...

def _check_vercel_cli(which, run_subprocess) -> dict:
    """Vercel CLI required for deployment (Phase 3+). Non-blocking for dry-run."""
    ...
```

**What stays unchanged:**
- Single-flight lock logic (`acquire_pipeline_singleflight_lock`, `release_pipeline_singleflight_lock`)
- Lock file path constant (rename from `.ios-factory-run.lock` to `.web-factory-run.lock`)
- `write_startup_preflight_report()` function
- `run_startup_preflight()` orchestrator function signature

### Pattern 4: YAML Contract Structure

**What the contract file must contain (CONT-01, CONT-02):**

```yaml
version: "1"
schema: pipeline-contract
metadata:
  created: "2026-03-21"
  description: "Web App Factory pipeline contract v1"

defaults:
  strict_mode: true
  gate_policy: fail-closed
  strict_quality_assessment_required: true

phases:
  - id: "1a"
    name: "Idea Validation"
    purpose: "Validate market opportunity and technical feasibility; produce Go/No-Go evidence"
    deliverables:
      - name: "Idea Validation Report"
        path: "docs/idea-validation.md"
        quality_criteria:
          - "3+ named competitor apps analyzed with feature comparison"
          - "Target user persona has concrete pain point and usage context"
          - "Differentiation derived from competitor analysis (not generic)"
          - "3+ risks with mitigation strategies"
      - name: "Tech Feasibility Memo"
        path: "docs/pipeline/tech-feasibility-memo.json"
        quality_criteria:
          - "Next.js suitability for the app type is evaluated"
          - "External API dependencies listed with rate limit considerations"
          - "Vercel deployment constraints noted (60s function timeout, bundle size)"
    gates:
      - type: artifact
        description: "Required documents present"
        checks:
          required_files:
            - path: "docs/idea-validation.md"
            - path: "docs/pipeline/tech-feasibility-memo.json"
        fail_action: block
      - type: tool_invocation
        description: "Content quality verification"
        checks:
          required_output_markers:
            - marker: "competitor"
              glob: "**/idea-validation.md"
        fail_action: block
```

**Key structural insight from ios-app-factory:** The `quality_criteria` list is read by the `QualitySelfAssessment` module (Phase 2+). In Phase 1, it documents the intent. The criteria strings must be specific and verifiable — not generic headings.

### Pattern 5: MCP Server — Single Implementation Rule

**What to copy verbatim from `factory_mcp_server.py`:**
- `approve_gate` tool (lines 64-125): File-polling approval flow is domain-agnostic
- `phase_reporter` tool (lines 133-260): Phase lifecycle logging with `project_dir` bridge

**Critical: The `project_dir` bridge in `phase_reporter` must be preserved.**

From the ios-app-factory source, `phase_reporter` calls into `pipeline_state` functions via the `project_dir` parameter. This is the bridge that makes `state.json` update. Without it, the MCP server logs locally but `state.json` stays stale (the HealthStockBoardV30 root cause).

**What to strip from `factory_mcp_server.py`:**
- `render_legal_template` tool (iOS-specific)
- `render_pera1_pitch_html` tool (iOS-specific)
- Imports of `factory_mcp_renderers`, `template_renderer` (iOS-specific modules)

**What to update:**
- `from config.settings import APPROVAL_TMP_DIR` — keep this pattern, update `config/settings.py`

### Pattern 6: Phase Executor Stub Pattern (Phase 1 only)

Phase 1 requires stub executors so the pipeline runner can load without error. Full implementation is Phase 2+.

```python
# tools/phase_executors/phase_1a_stub.py
from tools.phase_executors.base import PhaseContext, PhaseExecutor, PhaseResult

class Phase1aStubExecutor(PhaseExecutor):
    @property
    def phase_id(self) -> str:
        return "1a"

    @property
    def sub_steps(self) -> list[str]:
        return ["stub"]

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        return PhaseResult(
            phase_id=self.phase_id,
            success=False,
            error="Phase 1a executor not yet implemented (Phase 2 work item)",
        )
```

Register stubs in `tools/phase_executors/registry.py` so the contract runner can find them without crashing.

### Anti-Patterns to Avoid

- **Do not import from ios-app-factory at runtime.** The fork is a copy, not a symlink. After Phase 1, web-app-factory must have zero runtime dependencies on `ios-app-factory/`.
- **Do not rewrite domain-agnostic files.** `governance_monitor.py`, `pipeline_state.py`, and `contract_pipeline_runner.py` contain battle-tested edge-case handling (atomic state writes, lock management, bypass detection). Rewriting introduces regressions.
- **Do not strip the `project_dir` bridge from `phase_reporter`.** This is the single most dangerous omission possible — it would pass all unit tests but silently break state persistence.
- **Do not put actual iOS agent definitions in `agents/definitions.py`.** The stub file should reference web agent names only. iOS-specific prompts in the web codebase will confuse Phase 2+ work.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP server for approval gates | Custom HTTP server or polling loop | `fastmcp` 3.x `FastMCP` class | File-based polling for approval is already in `factory_mcp_server.py`; copy it |
| State persistence and run lifecycle | Custom JSON writer | `pipeline_state.py` (verbatim copy) | Already handles atomic writes, run IDs, activity log appending, resume logic |
| Phase ordering enforcement | Custom sequence checker | `governance_monitor.py` (verbatim copy) | Handles `phase_order_violation`, write-without-phase-start, and fast-completion detection |
| Single-flight pipeline lock | Custom PID file | `startup_preflight.py` flock-based lock | Already POSIX-compatible with Windows fallback (fcntl import guard) |
| YAML parsing | ad-hoc parser | `pyyaml` | Standard library with good error messages |
| Contract schema validation | Custom schema checker | `jsonschema` 4.20+ | Standard Python JSON Schema validator |

---

## Common Pitfalls

### Pitfall 1: Dual Implementation Divergence (CRITICAL)

**What goes wrong:** The MCP `phase_reporter` tool and the direct Python path diverge. The MCP version succeeds (returns "OK") but never updates `state.json`. This happened in ios-app-factory's HealthStockBoardV30 incident — 14 phases ran forward on ghost state.

**Why it happens:** When copying `factory_mcp_server.py`, the `project_dir` bridge (the call into `pipeline_state.py` functions) may be overlooked because the MCP tool returns success without it.

**How to avoid:**
- Integration test that asserts `state.json` contains the phase record after calling the `phase_reporter` MCP tool with a valid `project_dir`
- Code review checklist: "Does the MCP tool implementation call the same Python function as the direct path?"

**Warning signs:** `state.json` shows phases as `pending` after the agent has reported them. `activity-log.jsonl` is empty while the pipeline "runs."

### Pitfall 2: iOS Lock File Path in Web Factory

**What goes wrong:** The lock file path constant `PIPELINE_SINGLE_FLIGHT_LOCK_PATH` defaults to `docs/pipeline/.ios-factory-run.lock` in `startup_preflight.py`. Copying verbatim leaves this iOS-named path in the web factory.

**How to avoid:** Change the lock file name in the constant definition:

```python
# startup_preflight.py (web-app-factory)
PIPELINE_SINGLE_FLIGHT_LOCK_PATH = Path("docs/pipeline/.web-factory-run.lock")
```

This is the only required change to `startup_preflight.py`'s lock logic.

### Pitfall 3: PHASE_ORDER Mismatch Breaks Resume Logic

**What goes wrong:** If `PHASE_ORDER` in `pipeline_state.py` still contains iOS phase IDs (1b+, 2c, 2d, 4a, 5, 6), the resume logic calculates incorrect resume points for web phases. `get_resume_phase()` uses `PHASE_ORDER.index()` — an iOS phase ID in the list makes the web phase index wrong.

**How to avoid:** Update `PHASE_ORDER` to `["1a", "1b", "2a", "2b", "3"]` immediately after copying `pipeline_state.py`. This is a required change, not optional.

### Pitfall 4: factory_mcp_server.py iOS Imports Cause ImportError

**What goes wrong:** `factory_mcp_server.py` imports `from tools.factory_mcp_renderers import render_pera1_pitch_html` and `from tools.template_renderer import render_legal_template_text`. These modules don't exist in web-app-factory, causing an `ImportError` at server startup.

**How to avoid:** When copying `factory_mcp_server.py`, remove these imports and the `render_legal_template` MCP tool registration. The import removal must be done before first run.

**What to keep:** The `from config.settings import APPROVAL_TMP_DIR` import — this path must be provided by the web-app-factory `config/settings.py`.

### Pitfall 5: Contract Schema Written After Phase Executors (CONT-03 Debt)

**What goes wrong:** The YAML contract is written after some phase executors are already stubbed. Executor stubs reference paths and phase IDs not yet in the contract. When the contract schema validator runs, it rejects the contract because executors wrote artifacts to paths that don't match contract deliverable paths.

**How to avoid:** Write the YAML contract first, schema second, then executors. The contract is the schema everything else is built against. This is a build-order constraint.

### Pitfall 6: Quality Criteria Written as Gate Bypass Hints

**What goes wrong:** Quality criteria are written as file existence checks ("docs/idea-validation.md exists") instead of content-verifying assertions ("3+ competitor apps named with feature comparison"). The LLM reads these criteria and generates the minimum content to technically satisfy them.

**How to avoid:** Every `quality_criteria` string must describe observable content properties:
- BAD: "Idea validation report is present"
- BAD: "Report contains competitor analysis"
- GOOD: "3+ named competitor apps analyzed with feature comparison table"
- GOOD: "Target user persona includes concrete pain point and usage context (job-to-be-done format)"

---

## Code Examples

### Pipeline State — Domain-Agnostic Functions (verified from source)

```python
# Source: /Users/masa/Development/ios-app-factory/tools/pipeline_state.py
# These functions require only PHASE_ORDER update — no other changes needed

def init_run(app_name: str, project_dir: str, idea: str) -> tuple[str, PipelineState]:
    """Initialize a new pipeline run. Returns (run_id, state)."""
    # Generates run_id as YYYYMMDD-HHMMSS-{slug}
    # Creates docs/pipeline/runs/{run_id}/state.json
    # Creates docs/pipeline/activity-log.jsonl entry

def get_resume_phase(state: PipelineState) -> str | None:
    """Determine resume point from state. Uses PHASE_ORDER for ordering."""
    # Returns the first phase in PHASE_ORDER that is not 'completed'
```

### GateResult Dataclass (copy verbatim from ios-app-factory)

```python
# Source: /Users/masa/Development/ios-app-factory/tools/gates/gate_result.py
# Frozen dataclass with dict-like access for backward compat

@dataclass(frozen=True)
class GateResult:
    schema_version: str = "gate-result.v2"
    gate_type: str = ""
    phase_id: str = ""
    passed: bool = False
    status: str = "BLOCKED"
    issues: list[str] = field(default_factory=list)
    # ... dict access via __getitem__ / get() / __contains__
```

### Phase Executor Base (copy verbatim)

```python
# Source: /Users/masa/Development/ios-app-factory/tools/phase_executors/base.py
# PhaseContext (frozen dataclass), PhaseResult, SubStepResult, PhaseExecutor ABC
# Security: project_dir resolved to realpath, run_id validated against pattern

class PhaseExecutor(ABC):
    @property
    @abstractmethod
    def phase_id(self) -> str: ...

    @property
    @abstractmethod
    def sub_steps(self) -> list[str]: ...

    @abstractmethod
    def execute(self, ctx: PhaseContext) -> PhaseResult: ...
```

### CLI Entry Point Pattern (adapt from ios-app-factory)

```python
# factory.py — adapted structure
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Web App Factory — idea to deployed web app"
    )
    parser.add_argument("idea", nargs="?")
    parser.add_argument("--idea", dest="idea_flag")
    parser.add_argument("--project-dir", default=None)
    parser.add_argument("--deploy-target",
                        choices=["vercel", "github-pages"],
                        default="vercel")
    parser.add_argument("--framework",
                        choices=["nextjs"],
                        default="nextjs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", default=None, metavar="RUN_ID")
    parser.add_argument("--unsafe-no-gates", action="store_true")
    parser.add_argument("--output-json", default=None)
    return parser.parse_args()
```

### Startup Preflight Web Checks (new code)

```python
# pipeline_runtime/startup_preflight.py — new web checks
def _check_nodejs(which=shutil.which, run_subprocess=subprocess.run) -> dict:
    node = which("node")
    if not node:
        return {"check": "nodejs", "passed": False,
                "reason": "node not found in PATH. Install Node.js 20.9+ from nodejs.org"}
    try:
        proc = run_subprocess(["node", "--version"],
                              capture_output=True, text=True, timeout=10, check=False)
        version_str = proc.stdout.strip().lstrip("v")  # "20.11.0"
        major, minor, *_ = (int(x) for x in version_str.split("."))
        if (major, minor) < (20, 9):
            return {"check": "nodejs", "passed": False,
                    "reason": f"Node.js {version_str} < 20.9 (Next.js 16 minimum)"}
        return {"check": "nodejs", "passed": True, "version": version_str}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {"check": "nodejs", "passed": False,
                "reason": f"node --version failed: {type(exc).__name__}"}
```

### YAML Contract Schema (new file)

```json
// contracts/pipeline-contract.schema.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["version", "schema", "phases"],
  "properties": {
    "version": {"type": "string"},
    "schema": {"const": "pipeline-contract"},
    "phases": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "name", "purpose", "deliverables", "gates"],
        "properties": {
          "id": {"type": "string"},
          "deliverables": {
            "type": "array",
            "items": {
              "required": ["name", "path", "quality_criteria"],
              "properties": {
                "quality_criteria": {
                  "type": "array",
                  "minItems": 1
                }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## File-by-File Copy/Adapt Decision Table

The definitive guide for what to do with each ios-app-factory file in Phase 1.

| Source File | Action | Changes Required |
|-------------|--------|-----------------|
| `tools/pipeline_state.py` (559 lines) | COPY then adapt | Update `PHASE_ORDER` and `PHASE_LABELS` only; all functions verbatim |
| `tools/factory_mcp_server.py` (774 lines) | COPY then adapt | Remove 3 iOS-only MCP tools + their imports; keep `approve_gate` + `phase_reporter` verbatim |
| `pipeline_runtime/governance_monitor.py` (580 lines) | COPY VERBATIM | Zero changes — all violation kinds are domain-agnostic |
| `pipeline_runtime/error_router.py` (259 lines) | COPY then minor adapt | Update agent names in `_FAILURE_PATTERNS` from `xcodebuild`/iOS to web error patterns |
| `pipeline_runtime/startup_preflight.py` (280 lines) | COPY then adapt | Replace Xcode checks with Node.js/npm/Vercel checks; update lock file name constant |
| `tools/phase_executors/base.py` | COPY VERBATIM | No iOS knowledge; `PhaseContext`, `PhaseResult`, `PhaseExecutor` ABC are universal |
| `tools/phase_executors/registry.py` | COPY VERBATIM | No iOS knowledge; will be populated with web executors in Phase 2 |
| `tools/gates/gate_result.py` | COPY VERBATIM | No iOS knowledge; frozen dataclass is universal |
| `tools/gates/gate_policy.py` | COPY VERBATIM | No iOS knowledge; gate pass/fail policy is universal |
| `factory.py` | ADAPT (do not copy) | Strip iOS modes, add web flags; structure and singleflight lock pattern preserved |
| `config/settings.py` | ADAPT (do not copy) | Remove all iOS/ASC paths; add web-equivalent paths (`VERCEL_CONFIG_DIR`, etc.) |
| `agents/definitions.py` | NEW (do not copy) | Stub with `spec-agent`, `build-agent`, `deploy-agent` names only; no iOS prompts |
| `contracts/pipeline-contract.v1.yaml` | NEW (do not copy) | Web-specific 5-phase contract |
| `contracts/pipeline-contract.schema.json` | NEW | JSON Schema for CONT-03 |

**Important:** ios-app-factory uses `tools/contract_pipeline_runner_v2.py` as a thin wrapper that redirects to `tools/runner_v2_core.py`, which itself is split across `runner_v2_core_preflight.py`, `runner_v2_core_phase_loop.py`, `runner_v2_models.py`, `runner_v2_state.py`, `runner_v2_gates.py`, and `runner_v2_diagnostics.py`. This 6-module split is the production code; the v1 `contract_pipeline_runner.py` is a legacy file. For web-app-factory, use the v2 core structure as the model but collapse the split into fewer files appropriate to Phase 1 scope (no rejection-fix mode, no iOS-specific substeps).

---

## State of the Art

| Old Approach | Current Approach | Impact on Phase 1 |
|--------------|------------------|-------------------|
| Single `contract_pipeline_runner.py` (770 lines) | Split into `runner_v2_core.py` + 5 support modules | Start with a single runner file (< 400 lines); plan split when it grows |
| `mcp` base SDK for server | `fastmcp` 3.x | `factory_mcp_server.py` already uses `from mcp.server.fastmcp import FastMCP`; no change needed |
| No contract schema validation | `jsonschema.validate()` at startup | CONT-03 requires this; build it into startup preflight as a new check |
| Phase ordering as best-effort log | `GovernanceViolationError` raises immediately on violation | Copy `governance_monitor.py` verbatim — the error class is already implemented |

**Deprecated/outdated in ios-app-factory that we do NOT copy:**
- `tools/contract_pipeline_runner.py` (the original v1): Use v2 architecture as the model
- `tools/antigravity_pipeline_runner.py`: Gemini-specific, irrelevant
- `tools/reject_fix_helpers.py`: iOS App Store rejection flow, not applicable
- All `tools/asc_*.py` files: App Store Connect, not applicable
- All `tools/phase_executors/phase_*.py` (iOS executors): Replace entirely in Phase 2

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` section |
| Quick run command | `uv run pytest -q tests/` |
| Full suite command | `uv run pytest -v tests/` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | Phase loop executes in PHASE_ORDER sequence | unit | `uv run pytest tests/test_contract_runner.py::test_phase_order -x` | Wave 0 |
| PIPE-02 | `state.json` persists phase records; `activity-log.jsonl` appended | unit | `uv run pytest tests/test_pipeline_state.py -x` | Wave 0 |
| PIPE-03 | `get_resume_phase()` returns correct resume point after interruption | unit | `uv run pytest tests/test_pipeline_state.py::test_resume -x` | Wave 0 |
| PIPE-04 | MCP `approve_gate` waits for file-based response | unit | `uv run pytest tests/test_factory_mcp.py::test_approve_gate -x` | Wave 0 |
| PIPE-04 | MCP `phase_reporter` updates `state.json` via bridge | integration | `uv run pytest tests/test_factory_mcp_bridge.py -x` | Wave 0 — CRITICAL |
| PIPE-05 | `GovernanceViolationError` raised on `phase_order_violation` | unit | `uv run pytest tests/test_governance_monitor.py -x` | Wave 0 |
| PIPE-06 | CLI `--idea` + `--project-dir` args parsed correctly | unit | `uv run pytest tests/test_factory_cli.py -x` | Wave 0 |
| PIPE-07 | Preflight fails when Node.js < 20.9 | unit | `uv run pytest tests/test_startup_preflight.py::test_nodejs_version -x` | Wave 0 |
| PIPE-07 | Preflight fails when Vercel CLI absent | unit | `uv run pytest tests/test_startup_preflight.py::test_vercel_cli -x` | Wave 0 |
| CONT-01 | YAML contract file parses without error | unit | `uv run pytest tests/test_contract_schema.py::test_parse -x` | Wave 0 |
| CONT-02 | Every deliverable block has `quality_criteria` with >= 1 item | unit | `uv run pytest tests/test_contract_schema.py::test_quality_criteria -x` | Wave 0 |
| CONT-03 | `jsonschema.validate()` passes at pipeline startup | unit | `uv run pytest tests/test_contract_schema.py::test_schema_validation -x` | Wave 0 |
| CONT-04 | `quality-self-assessment-{phase}.json` written before gate | unit | `uv run pytest tests/test_quality_assessment.py -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest -q tests/ -x` (stop on first failure)
- **Per wave merge:** `uv run pytest -v tests/`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps (Test Infrastructure to Create)

- [ ] `tests/__init__.py` — package marker
- [ ] `tests/conftest.py` — shared fixtures (`tmp_path` project dir, mock MCP server)
- [ ] `tests/test_pipeline_state.py` — adapted from ios-app-factory's `tests/test_pipeline_state.py` (201 lines)
- [ ] `tests/test_startup_preflight.py` — adapted from ios-app-factory's `tests/test_startup_preflight.py` (350 lines); replace Xcode mock with Node.js/npm/Vercel mocks
- [ ] `tests/test_factory_mcp_bridge.py` — NEW; critical integration test for PIPE-04 state bridge
- [ ] `tests/test_contract_schema.py` — NEW; validates YAML contract structure
- [ ] `tests/test_governance_monitor.py` — adapted from ios-app-factory's governance monitor tests
- [ ] `tests/test_factory_cli.py` — NEW; arg parsing unit tests

---

## Open Questions

1. **contract_pipeline_runner v1 vs v2 architecture**
   - What we know: ios-app-factory's production runner is split across 6 modules (`runner_v2_core.py`, `runner_v2_core_preflight.py`, `runner_v2_core_phase_loop.py`, `runner_v2_models.py`, `runner_v2_state.py`, `runner_v2_gates.py`). The v1 `contract_pipeline_runner.py` is kept for legacy compat.
   - What's unclear: Should web-app-factory start with the v2 split structure, or a consolidated single-file runner that hasn't yet grown to need splitting?
   - Recommendation: Start with a single `tools/contract_pipeline_runner.py` (< 400 lines) that implements the YAML-driven phase loop. Use v2 as the behavioral reference, not the structural reference. Add the split only when the single file exceeds the code-health threshold.

2. **`factory_mcp_server.py` iOS-only tool count**
   - What we know: The file has at least 3 iOS-specific MCP tools beyond `approve_gate` and `phase_reporter`: `render_legal_template`, `render_pera1_pitch_html`, and possibly others
   - What's unclear: Whether the full 774-line file has additional iOS-coupled logic beyond these named tools
   - Recommendation: Read the full file during implementation and create an explicit "remove list" before copying

3. **`error_router.py` failure pattern adaptation**
   - What we know: `_FAILURE_PATTERNS` contains iOS-specific patterns like `"xcodebuild"`, `"xcresult"`, `"BUILD FAILED"` (iOS Xcode build failure strings)
   - What's unclear: Exact set of patterns to replace vs. keep
   - Recommendation: Keep the router structure verbatim; replace iOS gate type strings (`build` → npm build) and agent names. All patterns are configuration data, not logic.

---

## Sources

### Primary (HIGH confidence — direct source inspection)

- `/Users/masa/Development/ios-app-factory/tools/pipeline_state.py` — 559 lines, full domain-agnostic state management API
- `/Users/masa/Development/ios-app-factory/pipeline_runtime/governance_monitor.py` — 580 lines, all violation kinds and blocking logic
- `/Users/masa/Development/ios-app-factory/pipeline_runtime/startup_preflight.py` — 280 lines, singleflight lock + backend session checks
- `/Users/masa/Development/ios-app-factory/pipeline_runtime/error_router.py` — 259 lines, failure classification patterns
- `/Users/masa/Development/ios-app-factory/tools/factory_mcp_server.py` — 774 lines, `approve_gate` + `phase_reporter` MCP tools
- `/Users/masa/Development/ios-app-factory/tools/phase_executors/base.py` — `PhaseContext`, `PhaseResult`, `PhaseExecutor` ABC
- `/Users/masa/Development/ios-app-factory/tools/gates/gate_result.py` — frozen `GateResult` dataclass
- `/Users/masa/Development/ios-app-factory/factory.py` — CLI structure, singleflight + preflight orchestration
- `/Users/masa/Development/ios-app-factory/contracts/pipeline-contract.v1.yaml` — YAML structure reference
- `/Users/masa/Development/ios-app-factory/pyproject.toml` — dependency versions and ruff config
- `MEMORY.md` — `Dual Implementation Divergence (phase_reporter)` section: direct evidence of the bridge failure

### Secondary (MEDIUM confidence)

- `.planning/research/ARCHITECTURE.md` — system architecture and component responsibility table
- `.planning/research/STACK.md` — verified versions for `fastmcp` 3.1.1, `claude-agent-sdk` 0.1.50
- `.planning/research/PITFALLS.md` — pitfall catalog including dual implementation divergence and gate-gaming

### Tertiary (CONTEXT.md — user decisions, authoritative for this phase)

- `.planning/phases/01-infrastructure/01-CONTEXT.md` — locked decisions on fork strategy, CLI interface, YAML contract structure

---

## Metadata

**Confidence breakdown:**
- File copy decisions: HIGH — based on direct source inspection of ios-app-factory files
- PHASE_ORDER adaptation: HIGH — single constant change, clearly documented
- YAML contract structure: HIGH — mirrors confirmed ios-app-factory structure with web content
- Test infrastructure: HIGH — adapted from existing test files (350 + 201 lines in ios-app-factory)
- `factory_mcp_server.py` iOS tool removal: MEDIUM — full 774-line file not fully read; "remove list" must be verified during implementation

**Research date:** 2026-03-21
**Valid until:** 2026-04-21 (stable domain — Python/uv/fastmcp stack is not rapidly changing)
