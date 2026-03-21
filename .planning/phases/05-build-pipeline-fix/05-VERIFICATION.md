---
phase: 05-build-pipeline-fix
verified: 2026-03-22T00:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
---

# Phase 5: Build Pipeline Directory Fix + Governance Wiring Verification Report

**Phase Goal:** Fix the Phase 2a-to-2b project directory handoff so build agent and gates target the Next.js project directory, and wire GovernanceMonitor into the live pipeline runner
**Verified:** 2026-03-22
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                                                      | Status     | Evidence                                                                                    |
|----|--------------------------------------------------------------------------------------------------------------------------------------------|------------|---------------------------------------------------------------------------------------------|
| 1  | Phase 2b passes the Next.js project directory (ctx.project_dir.parent / ctx.app_name) to run_build_agent, not the pipeline root           | VERIFIED  | `phase_2b_executor.py:134` — `nextjs_dir = ctx.project_dir.parent / ctx.app_name`; `line 150` — `project_dir=str(nextjs_dir)` passed to `run_build_agent` |
| 2  | Build gate runs npm run build and tsc --noEmit inside the Next.js project directory, not the pipeline root                                 | VERIFIED  | `contract_pipeline_runner.py:208` — `target_dir = nextjs_dir if nextjs_dir else project_dir`; `line 209` — `run_build_gate(target_dir, ...)`; same pattern for `static_analysis` at lines 216-217 |
| 3  | GovernanceMonitor is instantiated in run_pipeline() and tracks phase start/complete events                                                 | VERIFIED  | `contract_pipeline_runner.py:38` — import; `line 381` — `GovernanceMonitor(run_id=run_id, project_dir=project_dir, blocking=False)`; `lines 400, 435, 447, 478` — lifecycle events |
| 4  | All existing tests continue to pass after the changes                                                                                      | VERIFIED  | `uv run pytest -q` → 436 passed in 1.92s; targeted suite `test_phase_2b_executor.py + test_contract_runner.py` → 54 passed in 0.74s |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact                                          | Expected                                                                                           | Status    | Details                                                                                                            |
|---------------------------------------------------|----------------------------------------------------------------------------------------------------|-----------|--------------------------------------------------------------------------------------------------------------------|
| `tools/phase_executors/phase_2b_executor.py`      | Fixed nextjs_dir computation for run_build_agent, _validate_extra_npm_packages, and generate_quality_self_assessment | VERIFIED | `line 134`: `nextjs_dir = ctx.project_dir.parent / ctx.app_name`; used at lines 150, 177, 190, 208 — all four substitution points present |
| `tools/contract_pipeline_runner.py`               | nextjs_dir parameter for build/static_analysis gate dispatch; GovernanceMonitor instantiation in run_pipeline | VERIFIED | `line 38`: GovernanceMonitor import; `line 152`: `nextjs_dir: str | None = None` kwarg on `_run_gate_checks`; `lines 343, 463`: `nextjs_dir` computed and forwarded in `run_pipeline` |
| `tests/test_phase_2b_executor.py`                 | Updated test asserting nextjs_dir is passed to run_build_agent                                    | VERIFIED | `test_execute_passes_nextjs_dir_to_run_build_agent` at line 457; `_make_ctx` uses `pipeline-root` / `myapp` split to make pipeline root differ from nextjs_dir |
| `tests/test_contract_runner.py`                   | New tests for build gate nextjs_dir dispatch and GovernanceMonitor wiring                          | VERIFIED | `TestNextjsDirGateDispatch` (3 tests, lines 743-853); `TestGovernanceIntegration` (1 test, lines 861-911); keyword "governance" present in class names |

### Key Link Verification

| From                                      | To                                                           | Via                                                            | Status    | Details                                                                        |
|-------------------------------------------|--------------------------------------------------------------|----------------------------------------------------------------|-----------|--------------------------------------------------------------------------------|
| `phase_2b_executor.py`                    | `run_build_agent`                                            | `project_dir=str(nextjs_dir)` passed as keyword argument       | WIRED     | Line 150 — `project_dir=str(nextjs_dir)` in `run_build_agent()` call         |
| `contract_pipeline_runner.py`             | `run_build_gate`                                             | `nextjs_dir` passed to build/static_analysis gates             | WIRED     | Lines 208-209 (build gate) and 216-217 (static_analysis gate) both use `target_dir = nextjs_dir if nextjs_dir else project_dir` |
| `contract_pipeline_runner.py`             | `pipeline_runtime.governance_monitor.GovernanceMonitor`      | Instantiated in `run_pipeline` with `blocking=False`           | WIRED     | Line 381 — `monitor = GovernanceMonitor(run_id=run_id, project_dir=project_dir, blocking=False)`; `on_tool_use` called at lines 400, 435, 447; `register_gate_pass` at line 478 |

### Requirements Coverage

| Requirement | Source Plan   | Description                                                                                    | Status    | Evidence                                                                                     |
|-------------|---------------|------------------------------------------------------------------------------------------------|-----------|----------------------------------------------------------------------------------------------|
| BILD-02     | 05-01-PLAN.md | Phase 2b generates pages, components, and API routes from PRD specification                    | SATISFIED | `nextjs_dir = ctx.project_dir.parent / ctx.app_name` (line 134) used for all executor output paths; build agent operates in the correct directory |
| BILD-03     | 05-01-PLAN.md | Generated app passes `next build` production build without errors                              | SATISFIED | `_run_gate_checks` passes `nextjs_dir` to `run_build_gate` (lines 208-209); build gate now runs in directory that has `package.json` |
| BILD-04     | 05-01-PLAN.md | Generated app passes `tsc --noEmit` type-check without errors                                  | SATISFIED | `_run_gate_checks` passes `nextjs_dir` to `run_static_analysis_gate` (lines 216-217); static analysis now scans the generated Next.js project |
| PIPE-05     | 05-01-PLAN.md | Governance monitor detects and blocks phase skipping, direct file edits, and gate bypasses     | SATISFIED | `GovernanceMonitor` imported (line 38) and instantiated with `blocking=False` (line 381); phase lifecycle events tracked at lines 400, 435, 447, 478 |

**Orphaned requirements check:** REQUIREMENTS.md traceability table maps BILD-02, BILD-03, BILD-04 and PIPE-05 to Phase 5. All four are claimed by 05-01-PLAN.md and verified above. No orphaned requirements.

### Anti-Patterns Found

No anti-patterns detected.

| File                                              | Line | Pattern   | Severity | Impact |
|---------------------------------------------------|------|-----------|----------|--------|
| —                                                 | —    | —         | —        | —      |

No TODOs, FIXMEs, placeholder comments, empty implementations, or stub patterns found in any of the four modified files.

### Human Verification Required

None. All verification points are programmatically verifiable and confirmed.

### Gaps Summary

No gaps. All four must-haves are verified at all three levels (exists, substantive, wired). All 436 tests pass including 4 new targeted tests for the directory handoff (BILD-02/03/04) and GovernanceMonitor integration (PIPE-05). The commits 340fbae (TDD RED) and 802d3ec (TDD GREEN) are present in git history.

---

**Verification details:**

- `phase_2b_executor.py` line 134: `nextjs_dir = ctx.project_dir.parent / ctx.app_name` — exact pattern from PLAN
- `phase_2b_executor.py` lines 150, 177, 190, 208: all four uses of `ctx.project_dir` replaced with `nextjs_dir`
- `contract_pipeline_runner.py` line 381: `GovernanceMonitor(run_id=run_id, project_dir=project_dir, blocking=False)` — exact pattern from PLAN
- `_run_gate_checks` signature (line 148-153): `nextjs_dir: str | None = None` keyword-only parameter
- `run_pipeline` (line 343): `nextjs_dir = str(Path(project_dir).parent / app_name)` — computed before phase loop
- `run_pipeline` (line 463): `_run_gate_checks(contract_phase, project_dir, nextjs_dir=nextjs_dir)` — forwarded to all gate checks
- Test helper `_make_ctx` uses `project_dir = tmp_path / "pipeline-root"` with `app_name = "myapp"` — correctly distinguishes pipeline root from Next.js project dir

---

_Verified: 2026-03-22_
_Verifier: Claude (gsd-verifier)_
