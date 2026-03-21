# Phase 2: Spec - Research

**Researched:** 2026-03-21
**Domain:** Claude Agent SDK multi-turn executor pattern; web app spec agent implementation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Agent orchestration model**
- Spec agent uses Claude Agent SDK multi-turn tool-use loop (not single-shot prompt generation)
- Tools available to spec agent: web search (competitor discovery, market data), npm registry lookup (package validation for tech feasibility)
- Phase 1a and 1b are separate executor classes, each calling the spec-agent with phase-specific system prompt sections
- Single `AgentDefinition` for spec-agent in `agents/definitions.py`, but each executor constructs a phase-specific prompt that includes the YAML contract's purpose and quality_criteria for that phase
- Max turns capped per executor call (defense against runaway loops — follow ios-app-factory pattern)

**Market research sources**
- Hybrid approach: web search tools for real competitor discovery and market data, with LLM synthesis for analysis
- Competitor names must come from web search results, not LLM hallucination — the quality criteria requires "named competitor apps with specific feature comparisons"
- Market size estimates should cite web search sources where available; LLM extrapolation acceptable when cited as such
- Tech feasibility memo uses npm registry lookup to validate that referenced packages actually exist (hallucination prevention, aligns with BILD-07)

**Go/No-Go decision handling**
- No-Go result stops the pipeline at Phase 1a gate — does NOT auto-proceed
- The idea-validation.md must contain an explicit "Go" or "No-Go" recommendation with supporting rationale
- On No-Go: pipeline surfaces the validation report via MCP approval gate (`approve_gate`), letting the human review the analysis
- Human can: approve (override No-Go and proceed), reject (abort pipeline), or restart with a refined idea via CLI re-invocation
- No auto-pivot — the pipeline reports findings; the human decides next action
- Go/No-Go is a structured field in the validation report, not just prose (parseable by the gate checker)

**PRD-to-build handoff format**
- `screen-spec.json` follows a strict JSON schema defining: screens, routes, component inventory, layout regions, responsive breakpoints, interactive states
- Component names in screen-spec.json must match the PRD component inventory exactly (cross-reference validation in Phase 1b gate)
- Each screen entry includes: `route` (URL path), `layout` (regions: header/sidebar/main/footer), `components` (list with hierarchy), `states` (loading/error/empty/populated), `responsive` (mobile vs desktop differences)
- `prd.md` is human-readable markdown with MoSCoW-labeled requirements; `screen-spec.json` is the machine-readable counterpart consumed by the build agent
- Both files are generated in a single Phase 1b executor run — the agent writes markdown first, then derives the JSON from it (ensuring consistency)

### Claude's Discretion
- Exact spec agent system prompt wording (as long as it contains no iOS references per SPEC-04)
- Sub-step granularity within each executor (e.g., research → analyze → write → self-assess)
- Web search query formulation strategy for competitor discovery
- screen-spec.json schema field names and nesting structure (as long as it covers the required information)
- Error handling and retry strategy for web search failures

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SPEC-01 | Phase 1a validates idea with market research, competitor analysis, and Go/No-Go decision | Claude Agent SDK `query()` with `WebSearch` tool; output to `docs/pipeline/idea-validation.md` |
| SPEC-02 | Phase 1b generates structured PRD with MoSCoW classification and component inventory | Claude Agent SDK `query()` with Write tool; output to `docs/pipeline/prd.md` |
| SPEC-03 | Phase 1b produces tech feasibility memo evaluating implementation approach | npm registry lookup pattern from MEMORY.md; output to `docs/pipeline/tech-feasibility-memo.json`; validated npm packages only |
| SPEC-04 | Spec agent uses Claude Agent SDK with web-specific system prompt (no iOS references) | `AgentDefinition` in `agents/definitions.py` with clean web-only prompt; smoke test verifiable by grepping for iOS terms |
</phase_requirements>

---

## Summary

Phase 2 replaces the two stub executors (`Phase1aStubExecutor`, `Phase1bStubExecutor`) with real implementations that call a spec agent via the Claude Agent SDK. The spec agent is Claude Code running with web search and file I/O tools, given a phase-specific system prompt that injects the YAML contract's `purpose` and `quality_criteria` so it knows what "good" looks like before generating.

Phase 1a produces `idea-validation.md` (Go/No-Go decision with named competitor analysis and real market data from web search) and `tech-feasibility-memo.json` (Next.js SSR/SSG/ISR evaluation with npm-validated packages). Phase 1b produces `prd.md` (MoSCoW-labeled PRD) and `screen-spec.json` (machine-readable screen spec with component names that exactly match the PRD). Both phases follow the same executor pattern: instantiate `ClaudeAgentOptions` with `max_turns` cap, run the async `query()` loop inside `asyncio.run()`, collect `ResultMessage`, parse and write deliverables, then run quality self-assessment before gate submission.

The key architectural insight is that the web-app-factory project already has `claude-agent-sdk==0.1.50` installed and the infrastructure wiring (`register()`, `PhaseExecutor.execute()`, gate checker, `quality_self_assessment`) is complete from Phase 1. Phase 2 is purely about implementing the two executor classes and defining the spec agent system prompt — no new infrastructure is needed.

**Primary recommendation:** Implement `Phase1aSpecExecutor` and `Phase1bSpecExecutor` as concrete `PhaseExecutor` subclasses that self-register at module import. Each wraps a single `ClaudeAgentOptions`-configured `query()` call with `max_turns=25`, `permission_mode="bypassPermissions"`, and `allowed_tools=["WebSearch", "Read", "Write"]`. The system prompt is injected with the phase's `purpose` and `quality_criteria` from the YAML contract.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `claude-agent-sdk` | 0.1.50 (installed) | Run spec agent as Claude Code sub-process with tool use | Already in pyproject.toml; used by decision |
| `asyncio` | stdlib | Run async `query()` inside sync `execute()` | SDK is async; `asyncio.run()` is the standard bridge |
| `pyyaml` | >=6.0 (installed) | Read YAML contract quality_criteria for prompt injection | Already in pyproject.toml |
| `httpx` | >=0.28.0 (installed) | npm registry lookup for package validation (SPEC-03) | Already in pyproject.toml |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` (stdlib) | — | Parse agent output, write screen-spec.json | Always — deliverables are JSON/markdown |
| `re` (stdlib) | — | Extract Go/No-Go field from agent markdown output | Phase 1a gate check |
| `pathlib.Path` | stdlib | All file writes follow existing pattern | Follow base.py conventions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `claude-agent-sdk query()` | Direct Anthropic API | SDK is decided; provides Claude Code tools (WebSearch, Write) natively |
| `asyncio.run()` | `anyio.run()` | `asyncio.run()` is simpler; anyio not in pyproject.toml |
| npm registry via `httpx` | `subprocess npm view` | httpx is already installed; no subprocess needed for JSON API |

**Installation:**
No new packages needed. All dependencies are already in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure

```
tools/
  phase_executors/
    phase_1a_executor.py     # Phase1aSpecExecutor — idea validation
    phase_1b_executor.py     # Phase1bSpecExecutor — PRD + screen spec
agents/
  definitions.py             # Update SPEC_AGENT with real system prompt
tests/
  test_phase_1a_executor.py  # Unit tests with mocked SDK
  test_phase_1b_executor.py  # Unit tests with mocked SDK
```

Each executor file is ≤400 lines (code-health rule). The agent prompt lives in `agents/definitions.py` as a string constant.

### Pattern 1: Sync-wrapping the Async SDK

**What:** `execute()` is synchronous (matches `PhaseExecutor` interface). The SDK's `query()` is async. Bridge with `asyncio.run()`.

**When to use:** Every executor that calls the spec agent.

**Example:**
```python
# Source: claude_agent_sdk/query.py (installed 0.1.50)
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import ResultMessage

def _run_spec_agent(prompt: str, system_prompt: str, max_turns: int = 25) -> str:
    """Run agent and return the final result text."""
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        allowed_tools=["WebSearch", "Read", "Write"],
        max_turns=max_turns,
        cwd=str(project_dir),
    )
    async def _inner() -> str:
        result_text = ""
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                result_text = message.result or ""
        return result_text

    return asyncio.run(_inner())
```

### Pattern 2: Quality-Criteria Injection into System Prompt

**What:** Extract `quality_criteria` for the phase from the YAML contract and inject into the agent's system prompt so the agent knows what constitutes "good" output before generating.

**When to use:** Both 1a and 1b executors.

**Example:**
```python
# Source: derived from agents/definitions.py + contracts/pipeline-contract.web.v1.yaml
def _build_phase_system_prompt(base_prompt: str, quality_criteria: list[str]) -> str:
    criteria_block = "\n".join(f"- {c}" for c in quality_criteria)
    return (
        f"{base_prompt}\n\n"
        "## Quality Criteria (MUST satisfy ALL before writing output)\n"
        f"{criteria_block}\n\n"
        "Generate output that satisfies every criterion above. "
        "Do not optimize for gate markers — optimize for the stated quality criteria."
    )
```

### Pattern 3: Self-Registration at Module Import

**What:** Executor self-registers at the bottom of its module file, identical to the ios-app-factory pattern and consistent with the registry's design.

**When to use:** Both executor files.

**Example:**
```python
# Source: tools/phase_executors/registry.py (web-app-factory)
from tools.phase_executors.registry import register

class Phase1aSpecExecutor(PhaseExecutor):
    ...

# Self-register at module load
register(Phase1aSpecExecutor())
```

The `contract_pipeline_runner.py` must import these modules to trigger registration. This is the established import-side-effect pattern.

### Pattern 4: Go/No-Go as Structured Field

**What:** The agent must include a parseable Go/No-Go marker in `idea-validation.md`. The gate checker reads this field, not just the file's existence.

**When to use:** Phase 1a only.

**Example:**
```markdown
<!-- Source: CONTEXT.md decision — must be parseable by gate checker -->
## Decision
**go_no_go: Go**

Supporting rationale: ...
```

The gate checker regex: `r'^go_no_go:\s*(Go|No-Go)'` (multiline). A No-Go triggers the `approve_gate` MCP tool rather than auto-proceeding.

### Pattern 5: npm Registry Validation (SPEC-03)

**What:** Before writing `tech-feasibility-memo.json`, validate that every npm package name mentioned actually exists by querying the registry API. This prevents hallucinated package names from flowing to the build phase.

**When to use:** Phase 1a tech-feasibility-memo generation.

**Example:**
```python
# Source: httpx docs + BILD-07 requirement
import httpx

async def _npm_package_exists(package: str) -> bool:
    """Check npm registry for package existence."""
    url = f"https://registry.npmjs.org/{package}/latest"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
```

### Anti-Patterns to Avoid

- **Parsing gate markers from the system prompt:** The agent must not receive `required_output_markers` from the gate — only `quality_criteria`. Injecting gate conditions creates gate-gaming behavior (per `45-quality-driven-execution.md`).
- **Blocking the event loop:** Never call `asyncio.run()` inside an already-running event loop. If the pipeline runner is async in the future, use `asyncio.get_event_loop().run_until_complete()` instead.
- **Treating ResultMessage.result as always text:** The agent may have failed silently. Always check for non-empty result before writing deliverables.
- **Including iOS-specific language in the system prompt:** SPEC-04 requires zero iOS references. The smoke test checks this with `grep -i "ios\|swift\|xcode\|app store"` on the rendered prompt.
- **Writing screen-spec.json before prd.md:** Phase 1b must write markdown first, then derive JSON from it. Writing JSON first leads to component name mismatches.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Web search during spec | Custom HTTP scraping | `WebSearch` tool via agent | SDK provides it natively; no rate-limit handling needed |
| Async→sync bridge | Custom thread executor | `asyncio.run()` | Standard Python pattern; asyncio is stdlib |
| Quality self-assessment | Custom assessor | `generate_quality_self_assessment()` from `tools/quality_self_assessment.py` | Already implemented, tested, and wired to gate system |
| Gate marker checking | Custom regex in executor | Existing gate checker in `tools/gates/` | Gate checker is already wired; executor just writes files |
| npm registry check | `subprocess npm view` | `httpx` GET to `registry.npmjs.org` | No subprocess needed; httpx already installed |

**Key insight:** Phase 1 already built all infrastructure. Phase 2 only adds business logic (agent prompts + executor classes). Never re-implement what already exists in `tools/`.

---

## Common Pitfalls

### Pitfall 1: asyncio.run() called in an active event loop
**What goes wrong:** If the pipeline runner is ever made async, `asyncio.run()` inside `execute()` raises `RuntimeError: This event loop is already running`.
**Why it happens:** asyncio does not allow nested event loops.
**How to avoid:** Use `anyio.from_thread.run_sync()` or structure the executor to detect the current loop. For Phase 2, the pipeline runner is sync (`asyncio.run()` is safe) — document this assumption.
**Warning signs:** `RuntimeError: This event loop is already running` in tests.

### Pitfall 2: Agent produces hallucinated competitor names
**What goes wrong:** Without explicit WebSearch enforcement, the agent may list competitor apps that don't exist.
**Why it happens:** The LLM knows about apps from training data, but training data is stale.
**How to avoid:** System prompt must say "use WebSearch tool to discover competitors — do NOT rely on your training data for competitor names". The quality criterion "named competitor apps with specific feature comparisons" also enforces this.
**Warning signs:** idea-validation.md lists competitors but screen-spec.json cites no web search sources.

### Pitfall 3: screen-spec.json component names differ from prd.md
**What goes wrong:** Phase 1b gate checker validates component name cross-reference. Mismatched names cause gate failure.
**Why it happens:** Agent writes markdown first then extracts JSON, but names drift in the extraction step.
**How to avoid:** System prompt must instruct: "Extract component names for screen-spec.json verbatim from the Component Inventory section of prd.md. Do not rephrase or abbreviate."
**Warning signs:** Gate fails on "component inventory cross-reference" check.

### Pitfall 4: max_turns too low causing incomplete output
**What goes wrong:** Agent truncates work mid-analysis when it hits the turn cap.
**Why it happens:** Web search + analysis + writing multiple files requires many turns.
**How to avoid:** Set `max_turns=25` as the default. Use 15 turns for smoke tests to keep CI fast.
**Warning signs:** Deliverable files are written but content is sparse or cut off.

### Pitfall 5: Go/No-Go field not machine-parseable
**What goes wrong:** Gate checker cannot find the Go/No-Go decision and fails.
**Why it happens:** Agent writes prose like "I recommend proceeding" instead of the structured marker.
**How to avoid:** System prompt must include an exact template: `## Decision\n**go_no_go: Go**` or `**go_no_go: No-Go**`. Gate checker regex anchors to this pattern.
**Warning signs:** idea-validation.md exists but gate fails on "Go/No-Go decision" check.

### Pitfall 6: Stub executors still registered when real executors load
**What goes wrong:** `register()` raises `ValueError: Duplicate executor registration for phase '1a'` if stubs were registered earlier.
**Why it happens:** `register_all_stubs()` was called in test setup or pipeline initialization.
**How to avoid:** Real executor files must NOT call `register_all_stubs()`. Only the real executor's self-registration call counts. Tests that use stubs must use `_clear_registry()` in teardown.
**Warning signs:** `ValueError: Duplicate executor registration` during import.

---

## Code Examples

Verified patterns from the installed codebase:

### ClaudeAgentOptions — Full field reference
```python
# Source: .venv/lib/python3.13/site-packages/claude_agent_sdk/types.py (0.1.50)
from claude_agent_sdk import ClaudeAgentOptions

options = ClaudeAgentOptions(
    system_prompt="You are a web app spec agent...",
    permission_mode="bypassPermissions",   # Allow all tools without prompting
    allowed_tools=["WebSearch", "Read", "Write"],
    max_turns=25,                          # Cap against runaway loops
    cwd="/path/to/project",               # Working directory for file writes
    model=None,                           # None = use Claude's default
)
```

### ResultMessage extraction
```python
# Source: .venv/lib/python3.13/site-packages/claude_agent_sdk/types.py (0.1.50)
from claude_agent_sdk.types import ResultMessage

async def _collect_result() -> str:
    result_text = ""
    async for message in query(prompt=user_prompt, options=options):
        if isinstance(message, ResultMessage):
            result_text = message.result or ""
    return result_text
```

### PhaseExecutor subclass skeleton (web-app-factory conventions)
```python
# Source: tools/phase_executors/base.py + tools/phase_executors/registry.py
from __future__ import annotations
from tools.phase_executors.base import PhaseContext, PhaseExecutor, PhaseResult, SubStepResult
from tools.phase_executors.registry import register

class Phase1aSpecExecutor(PhaseExecutor):

    @property
    def phase_id(self) -> str:
        return "1a"

    @property
    def sub_steps(self) -> list:
        return ["research", "analyze", "write", "self_assess"]

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        results: list[SubStepResult] = []
        artifacts: list[str] = []
        # ... call agent, collect results
        return PhaseResult(
            phase_id=self.phase_id,
            success=True,
            artifacts=artifacts,
            sub_steps=results,
        )

register(Phase1aSpecExecutor())
```

### npm registry validation
```python
# Source: httpx docs + BILD-07 design decision
import asyncio
import httpx

def validate_npm_packages(packages: list[str]) -> dict[str, bool]:
    """Returns {package_name: exists} for each package."""
    async def _check_all() -> dict[str, bool]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            results = {}
            for pkg in packages:
                try:
                    r = await client.get(f"https://registry.npmjs.org/{pkg}/latest")
                    results[pkg] = (r.status_code == 200)
                except httpx.HTTPError:
                    results[pkg] = False
            return results
    return asyncio.run(_check_all())
```

### Quality self-assessment call (existing API)
```python
# Source: tools/quality_self_assessment.py (Phase 1 implementation)
from tools.quality_self_assessment import generate_quality_self_assessment
from pathlib import Path

# Call BEFORE gate submission — this is the CONT-04 requirement
assessment = generate_quality_self_assessment(
    phase_id="1a",
    project_dir=str(ctx.project_dir),
    contract_path=str(contract_path),
)
# assessment is written to docs/pipeline/quality-self-assessment-1a.json automatically
```

### Prompt injection of quality criteria from YAML
```python
# Source: contracts/pipeline-contract.web.v1.yaml structure + CONTEXT.md decision
import yaml
from pathlib import Path

def _load_phase_quality_criteria(phase_id: str, contract_path: Path) -> list[str]:
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    for phase in contract.get("phases", []):
        if phase["id"] == phase_id:
            criteria = []
            for deliverable in phase.get("deliverables", []):
                criteria.extend(deliverable.get("quality_criteria", []))
            return criteria
    return []
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ios-app-factory uses xAI/Grok for spec agent | web-app-factory uses Claude Agent SDK directly | Phase 2 decision | Simpler; no separate API key; uses WebSearch natively |
| ios-app-factory spec agent: iOS-specific concepts (HIG, App Store guidelines) | web-app-factory spec agent: web-specific concepts (Next.js SSR/SSG, Vercel constraints) | This phase | Cleaner prompt; no iOS contamination |
| Single-shot prompt (ios-app-factory Phase 1a for some sub-steps) | Multi-turn tool-use loop | CONTEXT.md decision | Agent can search web, discover real competitors, write files autonomously |

**Deprecated/outdated:**
- `Phase1aStubExecutor` / `Phase1bStubExecutor`: These are replaced by real executors in this phase. Do not register them in production code.

---

## Open Questions

1. **screen-spec.json schema validation**
   - What we know: screen-spec.json must be valid JSON consumed by the build agent. Fields are defined by CONTEXT.md decisions.
   - What's unclear: Should there be a JSON Schema file for screen-spec.json to validate the agent's output before gate submission?
   - Recommendation: Define an inline schema validator in Phase 1b executor. If validation fails, return PhaseResult(success=False). Do not add a separate schema file to contracts/ at this stage — it's overkill for Phase 2.

2. **Contract path injection into executors**
   - What we know: `generate_quality_self_assessment()` needs `contract_path`. The pipeline runner has this value but executors currently don't receive it.
   - What's unclear: Should `contract_path` be passed via `PhaseContext.extra`, or should executors hard-code the default contract path?
   - Recommendation: Pass contract path via `ctx.extra["contract_path"]` with a fallback to the default `contracts/pipeline-contract.web.v1.yaml`. This matches how `quality_context` is passed in the ios-app-factory pattern.

3. **No-Go handling in contract_pipeline_runner.py**
   - What we know: On No-Go, the pipeline should surface the report via `approve_gate`. The runner currently has no No-Go handling.
   - What's unclear: Does the executor return success=False to trigger gate failure (which naturally blocks), or does it write a special state marker?
   - Recommendation: Executor returns `success=True` with the idea-validation.md written (the agent did its job). The gate checker detects `go_no_go: No-Go` in the file and adds an `mcp_approval` gate condition. This requires a small gate type addition in Phase 2. Alternatively: executor detects No-Go and returns `success=False` with `error="No-Go decision"`, which stops the pipeline cleanly without requiring gate changes.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPEC-01 | Phase1aSpecExecutor.execute() produces idea-validation.md with Go/No-Go | unit | `uv run pytest tests/test_phase_1a_executor.py -x` | ❌ Wave 0 |
| SPEC-01 | Go/No-Go field is machine-parseable (`go_no_go: Go/No-Go`) | unit | `uv run pytest tests/test_phase_1a_executor.py::test_go_no_go_field_parseable -x` | ❌ Wave 0 |
| SPEC-01 | Competitor names come from web search (not hallucinated) | unit (mocked WebSearch) | `uv run pytest tests/test_phase_1a_executor.py::test_competitor_names_from_websearch -x` | ❌ Wave 0 |
| SPEC-02 | Phase1bSpecExecutor.execute() produces prd.md with MoSCoW labels | unit | `uv run pytest tests/test_phase_1b_executor.py::test_prd_has_moscow_labels -x` | ❌ Wave 0 |
| SPEC-02 | PRD component inventory matches screen-spec.json component names | unit | `uv run pytest tests/test_phase_1b_executor.py::test_component_name_cross_reference -x` | ❌ Wave 0 |
| SPEC-03 | tech-feasibility-memo.json evaluates SSR vs SSG vs ISR | unit | `uv run pytest tests/test_phase_1a_executor.py::test_feasibility_evaluates_rendering_strategy -x` | ❌ Wave 0 |
| SPEC-03 | npm packages in feasibility memo are registry-validated | unit | `uv run pytest tests/test_phase_1a_executor.py::test_npm_packages_validated -x` | ❌ Wave 0 |
| SPEC-04 | Spec agent system prompt contains no iOS references | unit | `uv run pytest tests/test_phase_spec_agent.py::test_no_ios_references_in_system_prompt -x` | ❌ Wave 0 |
| SPEC-04 | Smoke test: run agent with sample idea, verify no iOS terms in output | integration (mocked SDK) | `uv run pytest tests/test_phase_spec_agent.py::test_smoke_sample_idea -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest -q`
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase_1a_executor.py` — covers SPEC-01, SPEC-03 (requires mocked claude_agent_sdk query)
- [ ] `tests/test_phase_1b_executor.py` — covers SPEC-02 (requires mocked claude_agent_sdk query)
- [ ] `tests/test_phase_spec_agent.py` — covers SPEC-04 smoke test and system prompt validation
- [ ] Mock fixture for `claude_agent_sdk.query` — shared in `conftest.py`; returns a canned `ResultMessage` for unit tests

*(No changes to conftest.py fixture infrastructure needed — `tmp_project_dir` and `sample_contract_path` from Phase 1 are reusable)*

---

## Sources

### Primary (HIGH confidence)
- `/Users/masa/Development/web-app-factory/.venv/lib/python3.13/site-packages/claude_agent_sdk/types.py` — `ClaudeAgentOptions`, `AgentDefinition`, `ResultMessage` field names
- `/Users/masa/Development/web-app-factory/.venv/lib/python3.13/site-packages/claude_agent_sdk/query.py` — `query()` function signature, async iterator pattern
- `/Users/masa/Development/web-app-factory/tools/phase_executors/base.py` — `PhaseExecutor`, `PhaseContext`, `PhaseResult`, `SubStepResult` — current web-app-factory API
- `/Users/masa/Development/web-app-factory/tools/phase_executors/registry.py` — `register()` pattern and `_clear_registry()` for tests
- `/Users/masa/Development/web-app-factory/tools/quality_self_assessment.py` — `generate_quality_self_assessment()` API
- `/Users/masa/Development/web-app-factory/contracts/pipeline-contract.web.v1.yaml` — Phase 1a and 1b `quality_criteria` and gate `required_output_markers`
- `/Users/masa/Development/web-app-factory/.planning/phases/02-spec/02-CONTEXT.md` — All locked decisions

### Secondary (MEDIUM confidence)
- `/Users/masa/Development/ios-app-factory/tools/phase_executors/phase_1a_idea.py` — Sub-step pattern, `_run_*` method naming, self-registration
- `/Users/masa/Development/ios-app-factory/tools/phase_executors/base.py` — `_ExecuteModeExecutor` with dry-run/execute mode handling
- `/Users/masa/Development/ios-app-factory/agents/definitions.py` — iOS spec-agent system prompt structure (adapt for web)
- MEMORY.md entry: "Claude CLI `-p` Hangs via subprocess" — confirmed `--version` check pattern; same risk for SDK subprocess

### Tertiary (LOW confidence)
- None — all findings verified against installed code

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — confirmed installed versions from pyproject.toml and .venv
- Architecture patterns: HIGH — derived directly from installed SDK types and existing base.py code
- Pitfalls: HIGH — derived from MEMORY.md lessons + ios-app-factory code analysis
- Validation: HIGH — test framework confirmed (95 passing tests), gaps are known new files

**Research date:** 2026-03-21
**Valid until:** 2026-04-20 (claude-agent-sdk 0.1.50 API stable; pyproject.toml pinned)
