# Phase 7: Ship Directory Fix - Research

**Researched:** 2026-03-22
**Domain:** Python pipeline wiring — PhaseContext.extra propagation, subprocess cwd, deploy agent sandbox
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPL-01 | Pipeline deploys to Vercel via CLI (`vercel pull → build → deploy --prebuilt`) | Root cause confirmed: `_provision` and `_deploy_preview` run with `cwd=ctx.project_dir` (pipeline root). Fix: use `ctx.extra["nextjs_dir"]` |
| DEPL-02 | Preview URL captured in `docs/pipeline/deployment.json` after deploy | Downstream of DEPL-01. The URL capture regex and JSON write are correct; they will work once cwd points to the Next.js project |
| DEPL-03 | Deploy gate verifies HTTP 200 on deployed URL within 30 seconds | Downstream of DEPL-01/DEPL-02. `deployment_gate.py` implementation is correct; gate needs a valid URL from a real deploy |
| LEGL-01 | Legal phase generates Privacy Policy from web-adapted template | Root cause confirmed: `run_deploy_agent` called with `project_dir=str(ctx.project_dir)` (pipeline root). Fix: pass `nextjs_dir` |
| LEGL-02 | Legal phase generates Terms of Service from web-adapted template | Same root cause as LEGL-01 |
| LEGL-03 | Legal documents reference actual app features from build output | Downstream of LEGL-01/02. `run_legal_gate` reads from `project_dir`; needs the Next.js project dir to find `src/app/privacy/page.tsx` |
</phase_requirements>

## Summary

Phase 7 closes a single structural wiring gap that blocks all 6 remaining v1.0 requirements. The root cause is precisely documented in the milestone audit: `contract_pipeline_runner.py` computes `nextjs_dir` at line 343 but omits it from `PhaseContext.extra` at lines 421-424. Because Phase 3 executor never receives `nextjs_dir`, every operation runs against `ctx.project_dir` (the pipeline root), which has no `package.json` and no `src/app/` directory.

The fix is a surgical two-file change: (1) add `"nextjs_dir": nextjs_dir` to the `extra` dict in `run_pipeline()`, and (2) update Phase 3 executor to resolve `nextjs_dir = ctx.extra.get("nextjs_dir", str(ctx.project_dir))` and use it as `cwd` for all Vercel subprocess calls and as `project_dir` for the deploy agent. A third change is needed for `run_legal_gate`: the gate currently checks for legal files relative to `project_dir`, so it must receive `nextjs_dir` as well.

The existing 439 tests must all pass after the fix. One new integration test is required by the success criteria: it must verify that the runner's `extra` dict carries `nextjs_dir` into the context received by Phase 3 executor.

**Primary recommendation:** Two-file code change (runner + executor) with one new integration test. No architectural changes, no schema changes, no contract YAML changes.

## Standard Stack

### Core (already in use — no new dependencies)

| Module | Current Role | Phase 7 Change |
|--------|-------------|----------------|
| `tools/contract_pipeline_runner.py` | Builds `PhaseContext.extra` dict | Add `"nextjs_dir": nextjs_dir` to the dict |
| `tools/phase_executors/phase_3_executor.py` | Ship phase orchestrator | Read `ctx.extra["nextjs_dir"]` and use as cwd |
| `tools/phase_executors/deploy_agent_runner.py` | Wraps agent SDK | No change needed — already takes `project_dir` param |
| `tools/gates/legal_gate.py` | Checks legal file presence | Needs to receive `nextjs_dir` or the executor must pass it |
| `tests/test_contract_runner.py` | Contract runner unit tests | Add integration test for `nextjs_dir` propagation |
| `tests/test_phase_3_executor.py` | Phase 3 unit tests | Add test verifying cwd uses `ctx.extra["nextjs_dir"]` |

## Architecture Patterns

### Pattern 1: nextjs_dir Propagation (established in Phase 5)

Phase 5 solved the identical problem for build/static_analysis gates. The resolution pattern is already in the codebase and tested.

**Phase 5 solution (reference):**
```python
# contract_pipeline_runner.py — run_pipeline()
nextjs_dir = str(Path(project_dir).parent / app_name)  # line 343

# Passed to _run_gate_checks (already works):
gate_passed, gate_issues = _run_gate_checks(
    contract_phase, project_dir, nextjs_dir=nextjs_dir
)

# NOT YET passed to PhaseContext.extra (the gap):
ctx = PhaseContext(
    ...
    extra={
        "company_name": company_name,
        "contact_email": contact_email,
        # "nextjs_dir": nextjs_dir   <-- MISSING
    },
)
```

**Phase 7 fix — runner side:**
```python
ctx = PhaseContext(
    run_id=run_id,
    phase_id=phase_id,
    project_dir=Path(project_dir),
    idea=idea,
    app_name=app_name,
    extra={
        "company_name": company_name,
        "contact_email": contact_email,
        "nextjs_dir": nextjs_dir,          # <-- ADD THIS
    },
)
```

### Pattern 2: Phase 3 Executor cwd Resolution

The executor should resolve `nextjs_dir` with a fallback for backward compatibility (e.g., tests that do not supply it):

```python
# phase_3_executor.py — at top of execute()
nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)
```

Then use `nextjs_dir` as `cwd` for all subprocess calls:

```python
def _provision(self, ctx: PhaseContext) -> SubStepResult:
    nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)
    proc = subprocess.run(
        ["vercel", "link", "--yes"],
        cwd=nextjs_dir,           # <-- was: str(ctx.project_dir)
        ...
    )
```

Same change applies to:
- `_deploy_preview` (`cwd` for `vercel --yes`)
- `_run_gate_with_retry` (`cwd` for re-deploy subprocess)
- `_deploy_production` (`cwd` for `vercel promote`)

### Pattern 3: Deploy Agent cwd Fix

The `_generate_legal` method passes `project_dir=str(ctx.project_dir)` to `run_deploy_agent`. The agent writes `src/app/privacy/page.tsx` relative to its `cwd`. Fix:

```python
def _generate_legal(self, ctx: PhaseContext) -> SubStepResult:
    nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)
    ...
    agent_result = run_deploy_agent(
        prompt=prompt,
        system_prompt=DEPLOY_AGENT.system_prompt,
        project_dir=nextjs_dir,           # <-- was: str(ctx.project_dir)
    )
```

### Pattern 4: Legal Gate directory

`run_legal_gate(str(ctx.project_dir), phase_id="3")` in `_gate_legal` must also receive `nextjs_dir`:

```python
def _gate_legal(self, ctx: PhaseContext) -> SubStepResult:
    nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)
    gate_result = run_legal_gate(nextjs_dir, phase_id="3")  # <-- was: str(ctx.project_dir)
```

Verify this is consistent: `run_legal_gate` signature accepts `project_dir` and looks for `src/app/privacy/page.tsx` relative to it. The legal files are written by the deploy agent into the Next.js project, so the gate must look there.

### Pattern 5: deployment.json Write Path

`_deploy_preview` writes `deployment.json` using `ctx.project_dir / _DEPLOYMENT_JSON_PATH`. This is correct — `deployment.json` should remain in the **pipeline root's** `docs/pipeline/` directory (that is what `_read_deployment_url()` in the runner expects). No change needed here.

### Recommended Change Scope

| File | Lines Changed | Change Type |
|------|---------------|-------------|
| `tools/contract_pipeline_runner.py` | ~2 lines (extra dict) | Add `nextjs_dir` to `PhaseContext.extra` |
| `tools/phase_executors/phase_3_executor.py` | ~8 lines (5 cwd references + 1 agent call + 1 legal gate) | Replace `str(ctx.project_dir)` with `nextjs_dir` local var |
| `tests/test_contract_runner.py` | ~30 lines | New integration test class |
| `tests/test_phase_3_executor.py` | ~20 lines | New test verifying cwd from extra |

### Anti-Patterns to Avoid

- **Changing `deployment.json` write path**: It belongs in pipeline root (`ctx.project_dir / docs/pipeline/deployment.json`). The runner reads it from there in `_read_deployment_url()`. Do not change this.
- **Changing `_PRD_PATH`**: The PRD is at `ctx.project_dir / docs/pipeline/prd.md`. The PRD is a pipeline artifact, not part of the Next.js project. Do not change this.
- **Over-scoping the fix**: Do not touch gates that receive `deployment_url` (lighthouse, accessibility, security_headers, link_integrity) — they work correctly already; they operate on the deployed URL, not a filesystem path.
- **Hardcoding nextjs_dir in executor**: The executor should always read from `ctx.extra.get("nextjs_dir")` — do not compute it independently inside the executor using `ctx.project_dir.parent / ctx.app_name`. That pattern is fragile; the runner is the single source of truth for the path.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Directory resolution | Custom path computation in executor | Read from `ctx.extra["nextjs_dir"]` set by runner | Runner already computes `nextjs_dir` correctly at line 343; duplication risks divergence |
| Backward compatibility | Separate code paths per executor | `ctx.extra.get("nextjs_dir") or str(ctx.project_dir)` fallback | Keeps existing tests working without modification |
| Test isolation | Complex subprocess mocking | Same `patch("...subprocess.run")` pattern already used in test_phase_3_executor.py | 30+ existing tests demonstrate the pattern |

## Common Pitfalls

### Pitfall 1: Partial cwd Fix (Missing Subprocess Sites)

**What goes wrong:** Developer fixes `_provision` cwd but misses `_deploy_preview`, `_run_gate_with_retry` re-deploy, or `_deploy_production`. The later sub-steps still run in the wrong directory.

**Why it happens:** There are 5 places where `ctx.project_dir` is used as `cwd` for subprocess calls. A grep for `cwd=str(ctx.project_dir)` finds all of them:
- `_provision`: `cwd=str(ctx.project_dir)` (line 269)
- `_deploy_preview`: `cwd=str(ctx.project_dir)` (line 317)
- `_run_gate_with_retry` re-deploy: `cwd=str(ctx.project_dir)` (line 567)
- `_deploy_production`: `cwd=str(ctx.project_dir)` (line 678)

**How to avoid:** Resolve `nextjs_dir` once at the top of `execute()` and store as a local variable, then grep for all `cwd=str(ctx.project_dir)` occurrences in the file to confirm all are replaced.

**Warning signs:** Tests that assert the `cwd` kwarg of mock subprocess calls using `ctx.project_dir` instead of `nextjs_dir`.

### Pitfall 2: Legal Gate Remains Uncorrected

**What goes wrong:** Vercel CLI runs correctly after the cwd fix, but the legal gate still points to `ctx.project_dir` and fails because `src/app/privacy/page.tsx` was written to `nextjs_dir/src/app/privacy/page.tsx`.

**Why it happens:** `_gate_legal` has its own `str(ctx.project_dir)` argument to `run_legal_gate`. It is not a subprocess call, so the grep for `cwd=` won't catch it.

**How to avoid:** After fixing subprocess `cwd` references, search separately for `run_legal_gate` and `run_deploy_agent` call sites and fix those too.

### Pitfall 3: Breaking Existing Tests by Changing Context Construction

**What goes wrong:** Existing tests create `PhaseContext` without `nextjs_dir` in `extra`. If the executor requires `ctx.extra["nextjs_dir"]` (KeyError on missing), those tests fail.

**Why it happens:** `ctx.extra.get("nextjs_dir")` vs `ctx.extra["nextjs_dir"]` — missing the fallback.

**How to avoid:** Always use `ctx.extra.get("nextjs_dir") or str(ctx.project_dir)` with the fallback. The 439 existing tests pass `extra={}` or `extra={"company_name": ..., "contact_email": ...}` — they must keep working.

### Pitfall 4: deployment.json Confusion (Two Different Directories)

**What goes wrong:** Developer mistakenly moves `deployment.json` to `nextjs_dir/docs/pipeline/deployment.json`. The `_read_deployment_url()` function in the runner reads from `project_dir/docs/pipeline/deployment.json` — it will not find the file.

**Why it happens:** `deployment.json` is a pipeline artifact (not part of the Next.js project), but it is written inside `_deploy_preview` which is being modified.

**How to avoid:** `_DEPLOYMENT_JSON_PATH` is relative to `ctx.project_dir` and should remain so. Only the subprocess `cwd` and agent `project_dir` change — not the JSON write path.

## Code Examples

### Where to Add nextjs_dir in run_pipeline()

Source: `tools/contract_pipeline_runner.py`, lines 414-425 (current state)

```python
# Current (lines 414-425):
ctx = PhaseContext(
    run_id=run_id,
    phase_id=phase_id,
    project_dir=Path(project_dir),
    idea=idea,
    app_name=app_name,
    extra={
        "company_name": company_name,
        "contact_email": contact_email,
    },
)

# Fixed:
ctx = PhaseContext(
    run_id=run_id,
    phase_id=phase_id,
    project_dir=Path(project_dir),
    idea=idea,
    app_name=app_name,
    extra={
        "company_name": company_name,
        "contact_email": contact_email,
        "nextjs_dir": nextjs_dir,          # nextjs_dir already computed at line 343
    },
)
```

### How Phase 3 Executor Should Resolve nextjs_dir

Source: `tools/phase_executors/phase_3_executor.py`, execute() method

```python
def execute(self, ctx: PhaseContext) -> PhaseResult:
    sub_step_results: list[SubStepResult] = []
    contract_path = Path(ctx.extra.get("contract_path", str(_DEFAULT_CONTRACT_PATH)))

    # Resolve the Next.js project directory.
    # The runner passes this via PhaseContext.extra["nextjs_dir"].
    # Fallback to ctx.project_dir for backward compatibility with tests
    # that do not supply nextjs_dir.
    nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)

    # ── Step 1: Provision ──────────────────────────────────────────────
    result = self._provision(ctx, nextjs_dir=nextjs_dir)
    ...
```

Alternatively, pass `nextjs_dir` as a parameter to each sub-step, or resolve it once inside `execute()` and pass as an arg. Either approach is valid; passing as an explicit parameter is slightly more testable.

### Integration Test Template

```python
class TestNextjsDirPropagationToPhase3(object):
    """Integration test: run_pipeline passes nextjs_dir in PhaseContext.extra to Phase 3."""

    def test_phase3_context_receives_nextjs_dir(self, tmp_path):
        """run_pipeline builds PhaseContext with nextjs_dir in extra for Phase 3 executor."""
        from tools.contract_pipeline_runner import load_contract, run_pipeline
        import tools.phase_executors.phase_3_executor  # ensure registration

        captured_contexts: list = []

        def capture_ctx(ctx):
            captured_contexts.append(ctx)
            from tools.phase_executors.base import PhaseResult
            return PhaseResult(phase_id=ctx.phase_id, success=False,
                               error="test stop")

        contract = load_contract(CONTRACT_PATH)
        # Use patch on Phase3ShipExecutor.execute to capture ctx before running
        with patch("tools.phase_executors.phase_3_executor.Phase3ShipExecutor.execute",
                   side_effect=capture_ctx):
            run_pipeline(
                contract=contract,
                project_dir=str(tmp_path),
                idea="A weight tracking app",
                skip_gates=True,
            )

        # Find the Phase 3 context
        phase3_ctx = next((c for c in captured_contexts if c.phase_id == "3"), None)
        assert phase3_ctx is not None, "Phase 3 executor was never called"
        assert "nextjs_dir" in phase3_ctx.extra, (
            "nextjs_dir missing from PhaseContext.extra — runner did not propagate it"
        )
        # Verify the value points to the expected directory
        expected_nextjs_dir_suffix = "A-weight-tracking-app"  # derived from idea slug
        assert phase3_ctx.extra["nextjs_dir"]  # not empty
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Build gates used `project_dir` for npm/tsc | Build gates use `nextjs_dir` | Phase 5 (2026-03-21) | BILD-02/03/04 now work |
| Build agent ran in `project_dir` | Build agent runs in `nextjs_dir` | Phase 5 (2026-03-21) | BILD-02 code generation works |
| Phase 3 executor still uses `project_dir` | **Phase 7: fix to use `nextjs_dir`** | Phase 7 (pending) | DEPL-01/02/03, LEGL-01/02/03 |

## Open Questions

1. **Does `run_legal_gate` also need to check `nextjs_dir`?**
   - What we know: `run_legal_gate` is called with `project_dir` arg and looks for `src/app/privacy/page.tsx` relative to it. The deploy agent writes this file into `nextjs_dir`.
   - What's unclear: Whether there are any integration paths where `run_legal_gate` is called from the contract runner's `_run_gate_checks` with the pipeline-root `project_dir` (in which case that call site also needs fixing).
   - Recommendation: Check `_run_gate_checks` for `gate_type == "legal"` — it calls `run_legal_gate(project_dir=project_dir, phase_id=phase_id)` using the pipeline root. For Phase 3's contract YAML gate, the runner must also pass `nextjs_dir` to this gate. However, given Phase 6 already removed the duplicate MCP approval gate and the contract YAML's legal gate paths were fixed, the primary path is through the executor's `_gate_legal`. The runner's `_run_gate_checks` also dispatches a `"legal"` gate type — that dispatch at line 288 also needs `nextjs_dir`. **Confidence: HIGH** that both call sites need the fix.

2. **Do the retry re-deploy subprocesses in `_run_gate_with_retry` need `nextjs_dir`?**
   - What we know: `_run_gate_with_retry` has an inline `subprocess.run(["vercel", "--yes"], cwd=str(ctx.project_dir), ...)` at line 567.
   - Recommendation: Yes, this must also use `nextjs_dir`. The method signature will need to accept `nextjs_dir` or resolve it from `ctx`.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (439 tests currently passing) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/test_phase_3_executor.py tests/test_contract_runner.py -x -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPL-01 | Vercel CLI runs in `nextjs_dir` (not pipeline root) | unit | `uv run pytest tests/test_phase_3_executor.py -k "provision or deploy_preview" -x` | ✅ (extend existing) |
| DEPL-02 | `deployment.json` written with valid URL | unit | `uv run pytest tests/test_phase_3_executor.py -k "deploy_preview" -x` | ✅ (existing passes) |
| DEPL-03 | Deploy gate gets valid non-empty URL | unit | `uv run pytest tests/test_phase_3_executor.py tests/test_deployment_gate.py -x` | ✅ (existing passes) |
| LEGL-01 | Deploy agent receives `nextjs_dir` as `project_dir` | unit | `uv run pytest tests/test_phase_3_executor.py -k "generate_legal" -x` | ✅ (extend existing) |
| LEGL-02 | Deploy agent writes to correct dir (same as LEGL-01) | unit | `uv run pytest tests/test_phase_3_executor.py -k "generate_legal" -x` | ✅ (extend existing) |
| LEGL-03 | Legal gate checks correct dir | unit | `uv run pytest tests/test_phase_3_executor.py -k "gate_legal" -x` | ✅ (extend existing) |
| SC-6 | Integration: `nextjs_dir` flows from runner to Phase 3 executor | integration | `uv run pytest tests/test_contract_runner.py -k "nextjs_dir" -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_phase_3_executor.py tests/test_contract_runner.py -x -q`
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** Full suite green (439+ tests) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_contract_runner.py::TestNextjsDirPropagationToPhase3` — integration test for `nextjs_dir` in `PhaseContext.extra` (SC-6)
- [ ] Additional assertions in existing `TestProvisionSubStep` and `TestDeployPreviewSubStep` tests to verify `cwd` kwarg matches `nextjs_dir` (not `ctx.project_dir`)

*(Existing test infrastructure covers all other requirements — only the integration test and cwd assertion additions are new)*

## Sources

### Primary (HIGH confidence)

- Direct code inspection: `tools/contract_pipeline_runner.py` lines 343, 414-425 — `nextjs_dir` computed but not added to `extra`
- Direct code inspection: `tools/phase_executors/phase_3_executor.py` lines 269, 317, 443, 554-570, 678 — all `cwd=str(ctx.project_dir)` targets
- Direct code inspection: `.planning/v1.0-MILESTONE-AUDIT.md` — root cause statement, line references, 6 affected requirements
- Direct code inspection: `tools/phase_executors/phase_2b_executor.py` lines 134, 150 — precedent pattern for `nextjs_dir` resolution in an executor

### Secondary (MEDIUM confidence)

- Phase 5 implementation in `tools/contract_pipeline_runner.py` `_run_gate_checks()` — confirmed working pattern for `nextjs_dir` propagation to gate checks

### Tertiary (LOW confidence)

- None — this is an entirely internal code wiring issue; no external library research needed.

## Metadata

**Confidence breakdown:**
- Root cause identification: HIGH — audit document precisely names the missing dict key and line numbers
- Fix approach: HIGH — Phase 5 established the identical pattern for build gates; same approach applies
- Test approach: HIGH — 439 existing tests provide clear patterns to follow; all are unit tests with subprocess mocking
- Scope completeness: MEDIUM — 5 subprocess cwd sites identified via grep; legal gate call site also identified; may be 1-2 additional `str(ctx.project_dir)` references in the executor that grep for `cwd=` would miss (legal gate call, agent call)

**Research date:** 2026-03-22
**Valid until:** Indefinitely (internal codebase, no external dependency changes)
