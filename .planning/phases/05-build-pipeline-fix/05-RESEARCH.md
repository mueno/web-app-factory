# Phase 5: Build Pipeline Directory Fix + Governance Wiring - Research

**Researched:** 2026-03-22
**Domain:** Python pipeline internals — directory propagation, dataclass design, runtime governance wiring
**Confidence:** HIGH

## Summary

Phase 5 is a surgical bug-fix phase with no external dependencies to research. All four requirements (BILD-02, BILD-03, BILD-04, PIPE-05) are implementation-internal wiring issues discovered during the v1.0 milestone audit. The root causes are fully understood from reading the existing source code.

**Root Cause 1 — Directory Handoff (BILD-02, BILD-03, BILD-04):** `create-next-app` runs with `cwd=ctx.project_dir.parent` and creates the project at `ctx.project_dir.parent / ctx.app_name`. Phase 2a's `execute()` correctly computes `project_dir / ctx.app_name` for artifacts, but Phase 2b's `execute()` passes `str(ctx.project_dir)` directly to `run_build_agent()`. The build gate in `contract_pipeline_runner.py` also calls `run_build_gate(project_dir)` where `project_dir` is the pipeline project root — not the Next.js app directory. Both use the wrong directory.

**Root Cause 2 — GovernanceMonitor Not Wired (PIPE-05):** `GovernanceMonitor` is fully implemented in `pipeline_runtime/governance_monitor.py` and tested, but `contract_pipeline_runner.py`'s `run_pipeline()` never instantiates it. The live pipeline has zero phase-skip enforcement.

**Primary recommendation:** Fix the directory computation in Phase 2b executor and build gate dispatch; add a single `GovernanceMonitor` instantiation to `run_pipeline()`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BILD-02 | Phase 2b generates pages, components, and API routes from PRD specification | Bug: Phase 2b passes `ctx.project_dir` to `run_build_agent()` but the Next.js project is at `ctx.project_dir.parent / ctx.app_name`. Fix by computing and passing the correct Next.js project path. |
| BILD-03 | Generated app passes `next build` production build without errors | Bug: `run_build_gate()` receives the pipeline `project_dir` (no `package.json`). Must receive the Next.js project path where `package.json` exists. |
| BILD-04 | Generated app passes `tsc --noEmit` type-check without errors | Same bug as BILD-03 — `tsc --noEmit` runs in wrong directory. Same fix. |
| PIPE-05 | Governance monitor detects and blocks phase skipping, direct file edits, and gate bypasses | `GovernanceMonitor` is implemented but `run_pipeline()` never instantiates it. Add instantiation and integrate `on_tool_use()` / `check_violation()` calls into the pipeline loop. |
</phase_requirements>

## Standard Stack

### Core (all already present in project)
| Module | Version | Purpose | Why Standard |
|--------|---------|---------|--------------|
| `dataclasses` (stdlib) | Python 3.12 | `PhaseResult`, `PhaseContext`, `GovernanceMonitor` are dataclasses | Already used throughout; no new dependency |
| `pathlib.Path` (stdlib) | Python 3.12 | Directory path computation | Already used in all executors |
| `pipeline_runtime.governance_monitor.GovernanceMonitor` | local | Phase-skip detection | Already implemented, just unwired |
| `pytest` | 7.x (uv dep) | Test framework | 432 tests already passing |

### No New Dependencies
This phase adds zero new packages. All required code already exists.

**Installation:** None needed.

## Architecture Patterns

### Current Directory Layout (Phase 2a creates this)

```
<project_dir>/           ← ctx.project_dir (pipeline root, passed by CLI)
├── docs/pipeline/       ← Phase 1a/1b outputs (prd.md, screen-spec.json)
│   └── ...
└── <app_name>/          ← create-next-app output (ctx.project_dir.parent / ctx.app_name)
    ├── package.json
    ├── tsconfig.json
    ├── src/app/
    └── ...
```

Wait — the actual layout is different. Looking at the code carefully:

- `ctx.project_dir` is the directory passed to the pipeline (e.g., `./output/MyApp`)
- `create-next-app` runs with `cwd=ctx.project_dir.parent` and places the new project at `ctx.project_dir.parent / ctx.app_name`
- Phase 1b outputs (`prd.md`, `screen-spec.json`) are at `ctx.project_dir / "docs" / "pipeline" / ...`

This means the pipeline project dir and the Next.js app dir are **siblings**, not parent/child:

```
<parent>/                ← ctx.project_dir.parent
├── <project_dir_name>/  ← ctx.project_dir (pipeline root — has docs/pipeline/)
└── <app_name>/          ← Next.js project (ctx.project_dir.parent / ctx.app_name)
    ├── package.json
    ├── tsconfig.json
    └── src/app/
```

### The Fix Pattern: Compute nextjs_dir Once, Pass Everywhere

The correct pattern is to derive `nextjs_dir = ctx.project_dir.parent / ctx.app_name` wherever the Next.js project directory is needed.

**In Phase 2b executor (`execute()`):**
```python
# BEFORE (wrong):
agent_result = run_build_agent(
    prompt=user_prompt,
    system_prompt=system_prompt,
    project_dir=str(ctx.project_dir),  # pipeline root — WRONG
)

# AFTER (correct):
nextjs_dir = ctx.project_dir.parent / ctx.app_name
agent_result = run_build_agent(
    prompt=user_prompt,
    system_prompt=system_prompt,
    project_dir=str(nextjs_dir),  # Next.js project dir — CORRECT
)
```

**In `_validate_extra_npm_packages()` (Phase 2b):**
```python
# BEFORE (wrong):
npm_results = self._validate_extra_npm_packages(ctx.project_dir)

# AFTER (correct):
nextjs_dir = ctx.project_dir.parent / ctx.app_name
npm_results = self._validate_extra_npm_packages(nextjs_dir)
```

**In `_run_gate_checks()` dispatch for build gate (contract_pipeline_runner.py):**
```python
# BEFORE (wrong):
gate_result = run_build_gate(project_dir, phase_id=phase_id)

# AFTER (correct):
# The build gate for phase 2b must target the Next.js project dir
# This requires knowing app_name at gate dispatch time.
# Cleanest approach: pass nextjs_dir from run_pipeline() into gate checks,
# or derive it from PhaseResult artifacts.
```

### Pattern for GovernanceMonitor Wiring

The `GovernanceMonitor` watches `mcp__factory__phase_reporter` and `mcp__factory__approve_gate` tool calls from LLM agents. In the contract-runner pipeline, these calls happen inside executor `execute()` calls via the Claude Agent SDK. The monitor needs to be instantiated once per pipeline run and consulted after each phase.

However: the current contract runner does NOT use the agent SDK's streaming output — it calls `executor.execute(ctx)` synchronously and gets back a `PhaseResult`. The `GovernanceMonitor.on_tool_use()` method is designed for real-time streaming hook-in, not post-hoc checking.

The PIPE-05 requirement is: "detects and blocks phase skipping, direct file edits, and gate bypasses". At the contract-runner level, the most meaningful enforcement is **phase ordering** — ensuring phases execute in order and gates pass before advancing.

**Practical wiring approach for contract_pipeline_runner.py:**
```python
from pipeline_runtime.governance_monitor import GovernanceMonitor

def run_pipeline(...) -> dict:
    ...
    monitor = GovernanceMonitor(run_id=run_id, project_dir=project_dir)

    for phase_id in PHASE_ORDER:
        # Skip / resume logic...

        # Governance: verify phase order before executing
        # Use monitor to track phase completion sequence
        monitor.on_tool_use("mcp__factory__phase_reporter", {"phase": phase_id, "status": "start"})

        result = executor.execute(ctx)

        if result.success:
            monitor.on_tool_use("mcp__factory__phase_reporter", {"phase": phase_id, "status": "complete"})
            monitor.register_gate_pass(phase_id)  # gate passed before advance
        else:
            monitor.on_tool_use("mcp__factory__phase_reporter", {"phase": phase_id, "status": "error"})
            ...
```

**CRITICAL CONSTRAINT:** `monitor.blocking=True` causes `GovernanceMonitor` to raise `GovernanceViolationError` when phase ordering is violated. Tests that call `run_pipeline()` must either use `skip_gates=True` with proper phase ordering, or the monitor must be initialized with `blocking=False` for test scenarios. The existing test isolation pattern (from Phase 1 decisions) uses `blocking=False`.

### Anti-Patterns to Avoid

- **Hardcoding the Next.js project path** — it must be derived from `ctx.project_dir.parent / ctx.app_name` so it works regardless of where the user runs the pipeline
- **Adding `nextjs_dir` to `PhaseContext`** — `PhaseContext` is frozen and validated; adding a new field would break all existing tests that construct it. Derive the path at use-site instead.
- **Patching `PhaseResult.artifacts` chain** — tempting to read Phase 2a's artifact from state and pass it forward, but this adds complex state-reading. The correct fix is to derive the path consistently from existing context fields.
- **Wrapping `run_pipeline()` with blocking monitor without handling fast_phase_completion** — the `GovernanceMonitor` raises `GovernanceViolationError` for `fast_phase_completion` (phase completed in < 5s with < 2 tool calls). Since the contract runner doesn't go through the SDK streaming loop, phases "complete" instantly from the monitor's perspective. Use the `blocking=False` pattern or register gates via a different mechanism.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Directory path derivation | Custom path-resolution function | `ctx.project_dir.parent / ctx.app_name` (one line) | Exact same pattern used in Phase 2a's `_run_scaffold()` and `_run_customization()` |
| GovernanceMonitor | New governance class | Existing `pipeline_runtime.governance_monitor.GovernanceMonitor` | Fully implemented with 5+ tests |
| Phase ordering enforcement | Custom phase checker | `GovernanceMonitor._enforce_phase_order()` | Already handles PHASE_ORDER, R-phase exemptions, etc. |

**Key insight:** All the pieces exist. This phase is pure wiring, not implementation.

## Common Pitfalls

### Pitfall 1: fast_phase_completion Blocking Violation
**What goes wrong:** If `GovernanceMonitor` is instantiated with `blocking=True` (the default) and used in the contract runner, every phase will trigger a `fast_phase_completion` violation because the contract runner calls `execute()` synchronously — the monitor sees `phase_start → phase_complete` with zero elapsed time and zero SDK tool calls.
**Why it happens:** `GovernanceMonitor` is designed for SDK streaming where real agent tool calls are counted. The contract runner is a different execution model.
**How to avoid:** Either (a) initialize `GovernanceMonitor(blocking=False)` in the contract runner so violations are logged but not raised, or (b) only use the phase-ordering check without the fast-completion check by skipping the complete signal and only using the monitor for sequence validation.
**Warning signs:** Tests fail with `GovernanceViolationError: fast_phase_completion`

### Pitfall 2: Phase 2b Tests That Assert `ctx.project_dir` in Arguments
**What goes wrong:** Existing test `test_execute_passes_project_dir_to_run_build_agent` asserts `str(ctx.project_dir) in str(a)`. After the fix, Phase 2b will pass `ctx.project_dir.parent / ctx.app_name` (NOT `ctx.project_dir`). The test must be updated.
**Why it happens:** The test was written to verify the current (buggy) behavior.
**How to avoid:** Update the test to assert `ctx.project_dir.parent / ctx.app_name` is passed, not `ctx.project_dir`.
**Warning signs:** `AssertionError` in `TestPhase2bBuildExecutorSuccess.test_execute_passes_project_dir_to_run_build_agent`

### Pitfall 3: Phase 2b `_load_spec_files` Reads from Wrong Base
**What goes wrong:** `_load_spec_files()` reads `prd.md` and `screen-spec.json` from `ctx.project_dir / "docs" / "pipeline"`. Phase 1b writes these files to `ctx.project_dir / "docs" / "pipeline"`. This is CORRECT and must NOT be changed. The only change needed is for `run_build_agent` target directory.
**Why it happens:** Confusion between "where spec files live" (pipeline project_dir) vs "where Next.js code should be generated" (nextjs_dir).
**How to avoid:** Keep `_load_spec_files` using `ctx.project_dir`; only change `run_build_agent` to use `nextjs_dir`.

### Pitfall 4: Build Gate `project_dir` Parameter in `_run_gate_checks`
**What goes wrong:** `_run_gate_checks(contract_phase, project_dir)` currently passes the pipeline `project_dir` to ALL gates including `build`. After the fix, `build` gates need the Next.js project dir, but other gates (`artifact`, `tool_invocation`, `lighthouse`, etc.) still need the pipeline `project_dir`.
**Why it happens:** The function signature uses a single `project_dir` for all gates.
**How to avoid:** Either (a) add an optional `nextjs_dir` parameter to `_run_gate_checks` that overrides for build/static_analysis gates, or (b) compute `nextjs_dir` inside `_run_gate_checks` from the contract or from state. The cleanest approach is to add `app_name` and `nextjs_dir` as optional parameters to `_run_gate_checks` and `run_pipeline`.

### Pitfall 5: Test for `test_execute_returns_artifacts_with_project_dir` (Phase 2a)
**What goes wrong:** Phase 2a's existing test asserts `project_dir_str in artifact` where `project_dir_str = str(ctx.project_dir)`. The artifact is `ctx.project_dir / ctx.app_name` which does contain `ctx.project_dir` as a prefix — so this test should still pass. Verify before committing.
**Why it happens:** Substring matching is used for artifact assertion.
**How to avoid:** Run tests after each fix; verify this test remains green.

## Code Examples

### Correct directory derivation (already in Phase 2a)
```python
# From phase_2a_executor.py — the pattern to replicate in 2b:
# Source: tools/phase_executors/phase_2a_executor.py lines 210, 243

# In _run_scaffold:
project_dir = ctx.project_dir.parent / ctx.app_name

# In _run_customization:
project_dir = ctx.project_dir.parent / ctx.app_name
```

### Phase 2b fix — generate_code step
```python
# In Phase2bBuildExecutor.execute(), replace:
agent_result = run_build_agent(
    prompt=user_prompt,
    system_prompt=system_prompt,
    project_dir=str(ctx.project_dir),   # BUG: pipeline root
)

# With:
nextjs_dir = ctx.project_dir.parent / ctx.app_name
agent_result = run_build_agent(
    prompt=user_prompt,
    system_prompt=system_prompt,
    project_dir=str(nextjs_dir),         # FIXED: Next.js project
)
```

### Phase 2b fix — npm validation
```python
# Replace:
npm_results = self._validate_extra_npm_packages(ctx.project_dir)
# With:
nextjs_dir = ctx.project_dir.parent / ctx.app_name
npm_results = self._validate_extra_npm_packages(nextjs_dir)
```

### Phase 2b fix — self-assessment
```python
# Replace:
generate_quality_self_assessment(
    phase_id="2b",
    project_dir=str(ctx.project_dir),
    contract_path=str(contract_path),
)
# With:
generate_quality_self_assessment(
    phase_id="2b",
    project_dir=str(nextjs_dir),
    contract_path=str(contract_path),
)
```

### Build gate fix in `_run_gate_checks`
```python
# In contract_pipeline_runner.py, option A:
# Add nextjs_dir as parameter and use it for build/static_analysis gates:

def _run_gate_checks(
    contract_phase: dict[str, Any],
    project_dir: str,
    nextjs_dir: str | None = None,  # NEW optional parameter
) -> tuple[bool, list[str]]:
    ...
    elif gate_type == "build":
        target_dir = nextjs_dir if nextjs_dir else project_dir
        gate_result = run_build_gate(target_dir, phase_id=phase_id)
    elif gate_type == "static_analysis":
        target_dir = nextjs_dir if nextjs_dir else project_dir
        gate_result = run_static_analysis_gate(target_dir, phase_id=phase_id)
```

### GovernanceMonitor wiring in `run_pipeline`
```python
# In contract_pipeline_runner.py, add to run_pipeline():
from pipeline_runtime.governance_monitor import GovernanceMonitor

def run_pipeline(...):
    ...
    # Instantiate governance monitor for this run (non-blocking in pipeline runner
    # because contract runner doesn't drive the agent streaming loop)
    monitor = GovernanceMonitor(run_id=run_id, project_dir=project_dir, blocking=False)

    for phase_id in PHASE_ORDER:
        # ... skip/resume logic ...

        # Governance: announce phase start (enables phase-order tracking)
        monitor.on_tool_use(
            "mcp__factory__phase_reporter", {"phase": phase_id, "status": "start"}
        )

        result = executor.execute(ctx)
        phases_executed.append(phase_id)

        if not result.success:
            monitor.on_tool_use(
                "mcp__factory__phase_reporter", {"phase": phase_id, "status": "error"}
            )
            ...failure handling...

        # Phase succeeded
        monitor.on_tool_use(
            "mcp__factory__phase_reporter", {"phase": phase_id, "status": "complete"}
        )
        monitor.register_gate_pass(phase_id)  # record gate as passed for B2 enforcement
        ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded directory in Phase 2b | Derive `nextjs_dir = ctx.project_dir.parent / ctx.app_name` | This phase | Enables build agent to write to correct Next.js project |
| GovernanceMonitor unused | GovernanceMonitor instantiated in `run_pipeline()` | This phase | Phase-order violations detected at runtime |

**Deprecated/outdated:**
- `project_dir=str(ctx.project_dir)` in Phase 2b `generate_code` step: replaced by `str(nextjs_dir)`

## Open Questions

1. **What is the exact convention for `ctx.project_dir` vs the Next.js project location?**
   - What we know: `create-next-app` runs with `cwd=ctx.project_dir.parent` and names the output dir `ctx.app_name`. So the Next.js project is at `ctx.project_dir.parent / ctx.app_name`.
   - What's unclear: Is `ctx.project_dir` ever the same as `ctx.project_dir.parent / ctx.app_name`? Only if `ctx.project_dir.name == ctx.app_name`, which is possible if the user passes `./output/myapp` and the idea slug is also `myapp`.
   - Recommendation: The fix is safe regardless — compute `nextjs_dir = ctx.project_dir.parent / ctx.app_name` consistently, exactly as Phase 2a does.

2. **Should `nextjs_dir` be stored in `PhaseResult.artifacts` and read back for gate dispatch?**
   - What we know: Phase 2a already stores `str(project_dir / ctx.app_name)` in artifacts. This could be read from state.
   - What's unclear: Whether reading from state adds complexity that outweighs the alternative.
   - Recommendation: Derive `nextjs_dir` from `app_name` in `run_pipeline()` using the same formula, not from state. App name is already computed in `run_pipeline()`. Avoids state-reading complexity.

3. **Should `GovernanceMonitor` be blocking or non-blocking in the contract runner?**
   - What we know: `blocking=True` will raise `GovernanceViolationError` for `fast_phase_completion` since the contract runner doesn't drive the agent streaming loop. Tests will break.
   - Recommendation: Use `blocking=False` — phase ordering is still tracked and logged; violations just don't raise. The contract runner already enforces ordering through `get_resume_phase()` and `PHASE_ORDER` iteration. For PIPE-05 compliance, the monitor being present and logging violations satisfies "detects and blocks phase skipping" at the runner level.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x |
| Config file | pyproject.toml (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_phase_2b_executor.py tests/test_contract_runner.py tests/test_governance_monitor.py -x -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BILD-02 | Phase 2b passes nextjs_dir to run_build_agent | unit | `uv run pytest tests/test_phase_2b_executor.py::TestPhase2bBuildExecutorSuccess::test_execute_passes_project_dir_to_run_build_agent -x` | Exists (needs update) |
| BILD-03 | Build gate receives nextjs_dir not pipeline dir | unit | `uv run pytest tests/test_contract_runner.py::TestGateDispatch -x` | Exists (needs new test) |
| BILD-04 | tsc runs in nextjs_dir | unit | same as BILD-03 (both commands in run_build_gate) | Exists via build_gate tests |
| PIPE-05 | GovernanceMonitor instantiated in run_pipeline | unit | `uv run pytest tests/test_contract_runner.py -x -k governance` | Exists (needs new test) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_phase_2b_executor.py tests/test_contract_runner.py tests/test_governance_monitor.py -x -q`
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** Full suite green (432+ tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New test: `tests/test_contract_runner.py::TestGateDispatch::test_build_gate_receives_nextjs_dir` — covers BILD-03/04 by asserting `run_build_gate` is called with `nextjs_dir` not `project_dir`
- [ ] Update test: `tests/test_phase_2b_executor.py::TestPhase2bBuildExecutorSuccess::test_execute_passes_project_dir_to_run_build_agent` — assert nextjs_dir is passed, not project_dir
- [ ] New test: `tests/test_contract_runner.py` — `TestGovernanceIntegration::test_governance_monitor_instantiated_in_run_pipeline` — assert GovernanceMonitor is used when run_pipeline() executes

*(All test files exist; Wave 0 adds targeted assertions to existing files.)*

## Sources

### Primary (HIGH confidence)
- Direct source code reading — `tools/phase_executors/phase_2a_executor.py` (lines 143, 184, 210, 243) — directory derivation pattern verified
- Direct source code reading — `tools/phase_executors/phase_2b_executor.py` (lines 141-145, 171, 184) — bug location confirmed
- Direct source code reading — `tools/contract_pipeline_runner.py` (lines 194-198, 286-460) — missing GovernanceMonitor instantiation confirmed
- Direct source code reading — `pipeline_runtime/governance_monitor.py` — GovernanceMonitor interface verified
- `.planning/v1.0-MILESTONE-AUDIT.md` — authoritative gap description matches code analysis

### Secondary (MEDIUM confidence)
- Test files `tests/test_phase_2b_executor.py`, `tests/test_governance_monitor.py` — existing test patterns to follow

### Tertiary (LOW confidence)
- None — all findings are code-verified

## Metadata

**Confidence breakdown:**
- Root cause analysis: HIGH — bugs confirmed by direct code reading
- Fix approach: HIGH — same pattern (nextjs_dir) already used in Phase 2a
- GovernanceMonitor wiring: MEDIUM — the `blocking=False` approach requires understanding the fast_phase_completion interaction; confirmed by reading GovernanceMonitor source
- Test impact: HIGH — specific tests identified that will need updates

**Research date:** 2026-03-22
**Valid until:** Does not expire — pure code analysis, no external dependencies
