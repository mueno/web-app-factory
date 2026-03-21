---
phase: 07-ship-directory-fix
plan: 01
subsystem: pipeline-wiring
tags: [nextjs_dir, phase3, deployment, legal, tdd, cwd-fix]
dependency_graph:
  requires: []
  provides:
    - nextjs_dir propagated through PhaseContext.extra to Phase 3 executor
    - All Vercel CLI subprocess calls use correct project directory
    - Legal gate and deploy agent receive correct project directory
  affects:
    - tools/contract_pipeline_runner.py
    - tools/phase_executors/phase_3_executor.py
tech_stack:
  added: []
  patterns:
    - "ctx.extra.get('nextjs_dir') or str(ctx.project_dir) fallback pattern for backward compatibility"
    - "TDD Red-Green cycle with 8 targeted unit/integration tests"
key_files:
  created:
    - none
  modified:
    - tools/contract_pipeline_runner.py
    - tools/phase_executors/phase_3_executor.py
    - tests/test_contract_runner.py
    - tests/test_phase_3_executor.py
decisions:
  - "Resolved nextjs_dir locally inside each sub-step method (not as instance variable) for full backward compatibility with tests that call sub-steps directly"
  - "Integration test uses CapturingPhase3Executor registered directly (not class-level patch) to survive module reload"
  - "deployment.json and PRD paths kept relative to ctx.project_dir (pipeline root) — correct by design"
metrics:
  duration_seconds: 230
  completed_date: "2026-03-22"
  tasks_completed: 2
  files_modified: 4
---

# Phase 07 Plan 01: Ship Directory Fix Summary

**One-liner:** Surgical 2-file fix wires `nextjs_dir` from `run_pipeline()` through `PhaseContext.extra` to Phase 3 executor, fixing all 6 remaining v1.0 requirements (DEPL-01/02/03, LEGL-01/02/03) via 8 new TDD tests.

## What Was Built

Fixed a single structural wiring gap that caused all Vercel CLI deployments and legal document operations to run in the pipeline root directory (which has no `package.json` or `src/app/`) instead of the Next.js project directory.

### Root Cause
`contract_pipeline_runner.py` computed `nextjs_dir` at line 343 but omitted it from `PhaseContext.extra` at lines 421-424. Phase 3 executor never received it, so every operation ran against `ctx.project_dir` (pipeline root).

### Fix Applied

**`tools/contract_pipeline_runner.py`:**
1. Added `"nextjs_dir": nextjs_dir` to the `PhaseContext.extra` dict in `run_pipeline()`
2. Fixed legal gate dispatch in `_run_gate_checks` to use `nextjs_dir` when provided (legal files live in Next.js project dir, not pipeline root)

**`tools/phase_executors/phase_3_executor.py`:**
- `_provision`: uses `nextjs_dir` as `cwd` for `vercel link --yes`
- `_deploy_preview`: uses `nextjs_dir` as `cwd` for `vercel --yes`
- `_generate_legal`: passes `nextjs_dir` as `project_dir` to `run_deploy_agent`
- `_gate_legal`: passes `nextjs_dir` as first arg to `run_legal_gate`
- `_run_gate_with_retry`: uses `nextjs_dir` as `project_dir` for fix agent and `cwd` for re-deploy subprocess
- `_deploy_production`: uses `nextjs_dir` as `cwd` for `vercel promote`

**Pattern used in each sub-step:**
```python
nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)
```
This provides full backward compatibility — tests that create `PhaseContext` without `nextjs_dir` in `extra` continue to pass unchanged.

**Deliberately NOT changed:**
- `_deploy_preview`: `deployment_json_path = ctx.project_dir / _DEPLOYMENT_JSON_PATH` — deployment.json belongs in pipeline root
- `_generate_legal`: `prd_path = ctx.project_dir / _PRD_PATH` — PRD is a pipeline artifact
- `_deploy_production`: `deployment_json_path = ctx.project_dir / _DEPLOYMENT_JSON_PATH` — same reason
- `_gate_mcp_approval`: `project_dir=str(ctx.project_dir)` — MCP approval uses pipeline root
- `generate_quality_self_assessment`: `project_dir=str(ctx.project_dir)` — assessment lives in pipeline root

## TDD Execution

**RED phase (Task 1):** 8 failing tests added, all confirmed failing before production code change:
- `TestNextjsDirPropagationToPhase3::test_phase3_context_receives_nextjs_dir`
- `TestNewGateDispatchLegalNextjsDir::test_legal_gate_dispatch_uses_nextjs_dir`
- `TestProvisionNextjsDir::test_provision_uses_nextjs_dir_as_cwd`
- `TestDeployPreviewNextjsDir::test_deploy_preview_uses_nextjs_dir_as_cwd`
- `TestGenerateLegalNextjsDir::test_legal_generation_uses_nextjs_dir`
- `TestGateLegalNextjsDir::test_legal_gate_uses_nextjs_dir`
- `TestGateRetryNextjsDir::test_retry_redeploy_uses_nextjs_dir_as_cwd`
- `TestDeployProductionNextjsDir::test_deploy_production_uses_nextjs_dir_as_cwd`

**GREEN phase (Task 2):** All 8 new tests pass; all 439 existing tests continue to pass (447 total).

## Verification Results

1. `uv run pytest tests/test_contract_runner.py tests/test_phase_3_executor.py -x -q` — 71 passed
2. `uv run pytest -x -q` — 447 passed (zero failures)
3. `grep -n 'cwd=str(ctx.project_dir)' tools/phase_executors/phase_3_executor.py` — zero matches
4. `grep -n '"nextjs_dir"' tools/contract_pipeline_runner.py` — confirms key present (line 428)
5. `grep -n 'ctx.extra.get("nextjs_dir")' tools/phase_executors/phase_3_executor.py` — 6 resolution lines confirmed

## Requirements Addressed

| Req ID | Description | Status |
|--------|-------------|--------|
| DEPL-01 | Pipeline deploys to Vercel via CLI (`vercel pull → build → deploy --prebuilt`) | Fixed — Vercel CLI now runs in `nextjs_dir` |
| DEPL-02 | Preview URL captured in `docs/pipeline/deployment.json` after deploy | Fixed — downstream of DEPL-01 |
| DEPL-03 | Deploy gate verifies HTTP 200 on deployed URL within 30 seconds | Fixed — downstream of DEPL-01/02 |
| LEGL-01 | Legal phase generates Privacy Policy from web-adapted template | Fixed — deploy agent now receives `nextjs_dir` |
| LEGL-02 | Legal phase generates Terms of Service from web-adapted template | Fixed — same as LEGL-01 |
| LEGL-03 | Legal documents reference actual app features from build output | Fixed — legal gate now checks `nextjs_dir` |

## Commits

| Hash | Message |
|------|---------|
| `2e64148` | `test(07-01): add failing tests for nextjs_dir propagation and cwd usage` |
| `e0537b5` | `feat(07-01): fix nextjs_dir propagation to Phase 3 executor` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Integration test approach needed revision**
- **Found during:** Task 2 (GREEN phase verification)
- **Issue:** The original test design patched `Phase3ShipExecutor.execute` at class level, but the executor instance was retrieved from the registry after a `importlib.reload()` which re-created the class, bypassing the patch.
- **Fix:** Rewrote `TestNextjsDirPropagationToPhase3` to use a `CapturingPhase3Executor` class registered directly in the executor registry, which the pipeline runner retrieves via `get_executor("3")`. This approach is registry-aware and not susceptible to class identity issues after module reload.
- **Files modified:** `tests/test_contract_runner.py`
- **Commit:** `e0537b5`

## Self-Check: PASSED
- `tools/contract_pipeline_runner.py` — exists, `nextjs_dir` key confirmed at line 428
- `tools/phase_executors/phase_3_executor.py` — exists, 6 `ctx.extra.get("nextjs_dir")` calls confirmed
- `tests/test_contract_runner.py` — exists, `TestNextjsDirPropagationToPhase3` and `TestNewGateDispatchLegalNextjsDir` classes present
- `tests/test_phase_3_executor.py` — exists, 6 new test classes confirmed
- Commit `2e64148` — exists (test RED phase)
- Commit `e0537b5` — exists (production fix GREEN phase)
- Full suite: 447 passed, 0 failed
