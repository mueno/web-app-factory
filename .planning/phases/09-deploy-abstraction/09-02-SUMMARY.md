---
phase: 09-deploy-abstraction
plan: 02
subsystem: infra
tags: [python, vercel, deploy, provider, subprocess, refactor, backward-compat]

# Dependency graph
requires:
  - phase: 09-01
    provides: "DeployProvider ABC + registry.py + placeholder vercel_provider.py stub"
provides:
  - VercelProvider with full provision/deploy_preview/promote lifecycle via deploy()
  - get_url() extracting URL from DeployResult
  - verify() delegating to run_deployment_gate()
  - phase_3_executor refactored to use provider interface (deploy_target-agnostic)
affects: [09-03-gcp-provider, phase_3_executor, future-deploy-targets]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Provider delegation: execute() calls provider.deploy() which atomically handles provision+preview+promote"
    - "Provider registry selection: get_provider(deploy_target) resolves at execute() start, stored as self._provider"
    - "Retry redeploy via provider: _run_gate_with_retry calls self._provider.deploy() instead of inline subprocess"
    - "deploy_target='local' short-circuit: skips cloud gates after provider.deploy() returns localhost URL"
    - "Backwards-compatible test migration: patch target moved from phase_3_executor.subprocess to vercel_provider.subprocess"

key-files:
  created: []
  modified:
    - tools/deploy_providers/vercel_provider.py
    - tools/phase_executors/phase_3_executor.py
    - tests/test_deploy_providers.py
    - tests/test_phase_3_executor.py

key-decisions:
  - "Provider delegation: provider.deploy() wraps provision+preview+promote atomically; DeployResult.metadata['step'] identifies which internal step failed"
  - "Backward-compatible test migration: all tests updating patch target to tools.deploy_providers.vercel_provider.subprocess.run (phase_3_executor no longer calls subprocess directly)"
  - "deploy_target='local' short-circuit after provider.deploy(): local target returns immediately without cloud gate checks (no generate_legal, no lighthouse, no MCP approval)"
  - "deploy_production sub-step recorded as success in execute() since promote is handled inside provider.deploy() for Vercel; future providers may have different promote semantics"

patterns-established:
  - "VercelProvider internal methods (_provision/_deploy_preview/_promote): return None on success, error string on failure — explicit None-or-error contract"
  - "phase_3_executor subprocess-free: all subprocess calls delegated to providers; phase_3_executor only calls gates, agents, and providers"
  - "Self._provider instance: stored at execute() start for access in _run_gate_with_retry retry cycle"

requirements-completed: [DEPL-02]

# Metrics
duration: 10min
completed: 2026-03-23
---

# Phase 9 Plan 02: VercelProvider + Phase3Executor Refactor Summary

**VercelProvider extracted from phase_3_executor with provision/deploy_preview/promote lifecycle; Phase3ShipExecutor refactored to delegate all deployment steps to the DeployProvider interface**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-23T08:00:49Z
- **Completed:** 2026-03-23T08:11:27Z
- **Tasks:** 2 (VercelProvider + executor refactor)
- **Files modified:** 4

## Accomplishments

- VercelProvider implements full Vercel lifecycle: _provision() (vercel link) → _deploy_preview() (vercel --yes, URL capture, deployment.json) → _promote() (vercel promote)
- deploy() returns DeployResult with success/url/provider/metadata; internal step failure identified via metadata["step"]
- get_url() returns URL from DeployResult or raises ValueError; verify() delegates to run_deployment_gate()
- Phase3ShipExecutor.execute() uses get_provider(deploy_target) and calls provider.deploy() atomically for steps 1+2+10
- Old _provision/_deploy_preview/_deploy_production/_VERCEL_URL_RE deleted from Phase3ShipExecutor
- _run_gate_with_retry redeploy cycle updated to call self._provider.deploy() instead of inline subprocess
- deploy_target="local" short-circuits after provider.deploy() — skips all cloud gates
- deploy_target="aws" returns PhaseResult(success=False) from NotImplementedError
- All 75 tests pass (43 deploy_providers + 31 phase_3_executor + 1 subprocess audit)
- 8 new TestVercelProvider tests added; xfail removed from test_registry_vercel

## Task Commits

Each task was committed atomically:

1. **Task 1: Create VercelProvider** - `2e226a9` (feat)
2. **Task 2: Refactor phase_3_executor.py to delegate to DeployProvider** - `73c63da` (feat)

## Files Created/Modified

- `tools/deploy_providers/vercel_provider.py` — Full VercelProvider replacing placeholder stub; _provision/_deploy_preview/_promote internal methods; verify() delegates to run_deployment_gate()
- `tools/phase_executors/phase_3_executor.py` — Old Vercel-specific methods deleted; execute() uses get_provider(); subprocess/json/os/re imports removed; _run_gate_with_retry uses provider.deploy() for redeploy
- `tests/test_deploy_providers.py` — TestVercelProvider (8 tests) added; xfail removed from test_registry_vercel
- `tests/test_phase_3_executor.py` — All tests updated to patch at tools.deploy_providers.vercel_provider.subprocess.run; TestProvisionSubStep/TestDeployPreviewSubStep/TestDeployProductionSubStep/NextjsDir tests rewritten to use VercelProvider methods directly

## Decisions Made

- VercelProvider.deploy() orchestrates all 3 Vercel steps atomically (provision+preview+promote) — caller gets one DeployResult with all-or-nothing semantics; failed step identified via metadata["step"]
- deploy_production sub-step in execute() is recorded as a synthetic success (promote already ran inside provider.deploy()); this maintains backward compatibility with the 10-step sub_steps reporting expected by tests
- Backward-compatible test migration: since phase_3_executor no longer calls subprocess, all 31 tests were updated to patch at vercel_provider.subprocess.run instead — this is necessary for correct mock behavior, not optional
- Self._provider stored at execute() time enables _run_gate_with_retry to call provider.deploy() for the redeploy-after-fix cycle without re-initializing the provider

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test patch target migration**
- **Found during:** Task 2 (refactor phase_3_executor.py)
- **Issue:** Removing subprocess from phase_3_executor meant all 31 test_phase_3_executor.py tests patching `tools.phase_executors.phase_3_executor.subprocess.run` would silently no-op (mocks would not intercept subprocess calls in vercel_provider)
- **Fix:** Updated all patch targets to `tools.deploy_providers.vercel_provider.subprocess.run`; rewrote TestProvisionSubStep, TestDeployPreviewSubStep, TestDeployProductionSubStep, all NextjsDir tests to call VercelProvider internal methods directly
- **Files modified:** tests/test_phase_3_executor.py
- **Verification:** 75/75 tests pass including all 25 non-NextjsDir tests
- **Committed in:** 73c63da (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - test migration required by architecture change)
**Impact on plan:** Essential migration — without this, tests would pass trivially (mocks not capturing subprocess) giving false green. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- VercelProvider fully implemented — Plan 09-03 (GCPProvider) can implement the same pattern
- phase_3_executor is now deploy-target-agnostic; any provider implementing DeployProvider ABC can be plugged in via get_provider()
- DEPL-02 requirement satisfied
- 31 phase_3_executor tests fully updated and passing — no technical debt from migration

---
*Phase: 09-deploy-abstraction*
*Completed: 2026-03-23*
