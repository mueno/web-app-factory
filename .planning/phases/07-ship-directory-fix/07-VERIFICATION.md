---
phase: 07-ship-directory-fix
verified: 2026-03-22T00:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 7: Ship Directory Fix Verification Report

**Phase Goal:** Fix the nextjs_dir propagation gap that blocks all 6 remaining v1.0 requirements (DEPL-01/02/03, LEGL-01/02/03).
**Verified:** 2026-03-22
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Phase 3 executor receives `nextjs_dir` from `PhaseContext.extra` and uses it as `cwd` for all Vercel CLI subprocess calls | VERIFIED | `phase_3_executor.py` line 266, 310, 572, 680: `nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)`; subprocess `cwd=nextjs_dir` at lines 270, 314, 572, 680 |
| 2 | Deploy agent writes legal documents (`privacy/page.tsx`, `terms/page.tsx`) inside the Next.js project directory, not the pipeline root | VERIFIED | `phase_3_executor.py` line 439-444: `nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)` then `run_deploy_agent(project_dir=nextjs_dir)` |
| 3 | Legal gate checks for legal files in the Next.js project directory | VERIFIED | `phase_3_executor.py` line 461-463: `nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)` then `run_legal_gate(nextjs_dir, phase_id="3")` |
| 4 | The contract runner's `_run_gate_checks` passes `nextjs_dir` to the legal gate dispatch | VERIFIED | `contract_pipeline_runner.py` lines 286-292: `legal_dir = nextjs_dir if nextjs_dir else project_dir; gate_result = run_legal_gate(project_dir=legal_dir, ...)` |
| 5 | All 439+ existing tests continue to pass after the fix | VERIFIED | `uv run pytest -x -q` → 447 passed (439 pre-existing + 8 new), 0 failures |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tools/contract_pipeline_runner.py` | `nextjs_dir` added to `PhaseContext.extra` dict | VERIFIED | Line 428: `"nextjs_dir": nextjs_dir` in `extra={...}` block; `_run_gate_checks` accepts `nextjs_dir` kwarg (line 152) and uses `legal_dir` (line 291) |
| `tools/phase_executors/phase_3_executor.py` | Uses `ctx.extra.get("nextjs_dir")` as cwd | VERIFIED | 6 occurrences of `ctx.extra.get("nextjs_dir") or str(ctx.project_dir)` at lines 266, 310, 439, 461, 558, 675; zero remaining `cwd=str(ctx.project_dir)` for subprocess calls |
| `tests/test_contract_runner.py` | `TestNextjsDirPropagationToPhase3` integration test class | VERIFIED | Class at line 954; `test_phase3_context_receives_nextjs_dir` method confirmed; `TestNewGateDispatchLegalNextjsDir` at line 1035 |
| `tests/test_phase_3_executor.py` | 6 new test classes covering `nextjs_dir` in each sub-step | VERIFIED | `TestProvisionNextjsDir`, `TestDeployPreviewNextjsDir`, `TestGenerateLegalNextjsDir`, `TestGateLegalNextjsDir`, `TestGateRetryNextjsDir`, `TestDeployProductionNextjsDir` — all confirmed at lines 725-870 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tools/contract_pipeline_runner.py` | `tools/phase_executors/phase_3_executor.py` | `PhaseContext.extra["nextjs_dir"]` | WIRED | `"nextjs_dir": nextjs_dir` at line 428 of runner; `ctx.extra.get("nextjs_dir")` at 6 sites in executor |
| `tools/phase_executors/phase_3_executor.py` | `subprocess.run` | `cwd=nextjs_dir` | WIRED | `cwd=nextjs_dir` at lines 270, 314, 572, 680 (all Vercel CLI calls) |
| `tools/phase_executors/phase_3_executor.py` | `tools/phase_executors/deploy_agent_runner.py` | `project_dir=nextjs_dir` | WIRED | `run_deploy_agent(project_dir=nextjs_dir)` at lines 444 and 563 |
| `tools/contract_pipeline_runner.py` | `tools/gates/legal_gate.py` | `_run_gate_checks` legal dispatch uses `nextjs_dir` | WIRED | `legal_dir = nextjs_dir if nextjs_dir else project_dir; run_legal_gate(project_dir=legal_dir, ...)` at lines 291-292 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DEPL-01 | 07-01-PLAN.md | Pipeline deploys to Vercel via CLI (`vercel pull → build → deploy --prebuilt`) | SATISFIED | All Vercel CLI subprocess calls (`vercel link`, `vercel --yes`, `vercel promote`) now use `cwd=nextjs_dir` — the directory containing `package.json` |
| DEPL-02 | 07-01-PLAN.md | Preview URL captured in `docs/pipeline/deployment.json` after deploy | SATISFIED | Downstream of DEPL-01; `deployment_json_path = ctx.project_dir / _DEPLOYMENT_JSON_PATH` (pipeline root, correct) preserved; URL capture logic in `_deploy_preview` unchanged |
| DEPL-03 | 07-01-PLAN.md | Deploy gate verifies HTTP 200 on deployed URL within 30 seconds | SATISFIED | Downstream of DEPL-01/02; the deploy gate receives a real URL (not empty string) once Vercel CLI runs in the correct directory |
| LEGL-01 | 07-01-PLAN.md | Legal phase generates Privacy Policy from web-adapted template | SATISFIED | `_generate_legal` passes `project_dir=nextjs_dir` to `run_deploy_agent`; agent writes into `src/app/privacy/page.tsx` in the Next.js project |
| LEGL-02 | 07-01-PLAN.md | Legal phase generates Terms of Service from web-adapted template | SATISFIED | Same as LEGL-01 — both privacy and terms are handled by the same `_generate_legal` sub-step |
| LEGL-03 | 07-01-PLAN.md | Legal documents reference actual app features from build output | SATISFIED | `_gate_legal` passes `nextjs_dir` as first arg to `run_legal_gate`; legal gate now checks the correct directory for document presence and feature references |

No orphaned requirements — DEPL-04 (Phase 4, MCP approval gate) is correctly excluded from this phase and remains untouched in `_gate_mcp_approval` at line 645 using `project_dir=str(ctx.project_dir)` as designed.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `phase_3_executor.py` | 424, 431, 436 | "placeholder" text | Info | These are prompt strings instructing the deploy agent NOT to use placeholders — not code stubs |

No blockers. No warnings. Zero stubs detected in production code paths.

### Human Verification Required

The following items require runtime validation that cannot be verified statically:

#### 1. Vercel CLI Integration Test

**Test:** In a real pipeline run with a scaffolded Next.js project, verify `vercel link --yes` runs in the correct directory and creates a Vercel project.
**Expected:** The provisioned Vercel project is associated with the app's Next.js directory (containing `package.json`), not the pipeline root.
**Why human:** Requires a live Vercel account and a real scaffolded project; cannot be verified by static analysis or unit tests.

#### 2. Legal Document Path Resolution

**Test:** Run the full Phase 3 pipeline to completion and check that `privacy/page.tsx` and `terms/page.tsx` appear under `{nextjs_dir}/src/app/`.
**Expected:** Both files exist in the Next.js project's `src/app/` directory, not in the pipeline root.
**Why human:** Requires a live Claude Agent SDK call via `run_deploy_agent`; the deploy agent's file-writing behavior is exercised only in integration.

### Gaps Summary

No gaps. All 5 observable truths are verified. All 4 artifacts are substantive and wired. All 4 key links are confirmed with grep evidence. 6 requirements (DEPL-01/02/03, LEGL-01/02/03) are satisfied by the wiring fix. The full test suite (447 tests) passes. Two human-only integration scenarios are flagged for runtime validation but do not block the phase from being considered complete — they verify end-to-end behavior in a live environment, not the correctness of the wiring itself.

### Commit Verification

| Hash | Message | Exists |
|------|---------|--------|
| `2e64148` | `test(07-01): add failing tests for nextjs_dir propagation and cwd usage` | Confirmed |
| `e0537b5` | `feat(07-01): fix nextjs_dir propagation to Phase 3 executor` | Confirmed |

---

_Verified: 2026-03-22_
_Verifier: Claude (gsd-verifier)_
