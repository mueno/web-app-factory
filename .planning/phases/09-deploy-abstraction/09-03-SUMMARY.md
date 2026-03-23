---
phase: 09-deploy-abstraction
plan: 03
subsystem: infra
tags: [python, gcp, cloud-run, subprocess, tdd, deploy, pipeline-wiring]

# Dependency graph
requires: [09-01]
provides:
  - GCPProvider with gcloud auth preflight and Cloud Run deploy
  - _GCP_URL_RE regex for extracting *.run.app URL from gcloud stderr
  - deploy_target parameter wired end-to-end: bridge → run_pipeline() → PhaseContext.extra
affects: [phase_3_executor, MCP waf_generate tool, 09-01-registry]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Preflight check chain: CLI presence → auth token → project config — fail fast with remediation commands"
    - "URL extraction from stderr: gcloud outputs Service URL to stderr not stdout — regex on stderr is correct"
    - "deploy_target always forwarded: unconditional pipeline_kwargs['deploy_target'] = deploy_target (not conditional on truthiness)"
    - "PhaseContext.extra as pass-through dict: deploy_target added alongside company_name, contact_email, nextjs_dir"

key-files:
  created: []
  modified:
    - tools/deploy_providers/gcp_provider.py
    - tests/test_deploy_providers.py
    - web_app_factory/_pipeline_bridge.py
    - tools/contract_pipeline_runner.py
    - tests/test_pipeline_bridge.py

key-decisions:
  - "URL extraction from gcloud stderr (not stdout): gcloud run deploy writes Service URL to stderr — regex matches there"
  - "deploy_target always added to pipeline_kwargs (unconditional): company_name/contact_email are conditional on truthiness but deploy_target always has a value ('vercel' default), so always forwarded"
  - "Default deploy_target='vercel' at every layer: bridge, run_pipeline(), and PhaseContext.extra all default to 'vercel' for backward compatibility"

patterns-established:
  - "GCPProvider auth preflight: check gcloud CLI → check auth token → check project (fail-fast with actionable error messages)"
  - "_GCP_URL_RE pattern: r'Service URL:\\s+(https://[^\\s]+\\.run\\.app)' — searches stderr not stdout"
  - "run_deployment_gate delegation in verify(): consistent with VercelProvider pattern from Plan 09-02"

requirements-completed: [DEPL-03, DEPL-06]

# Metrics
duration: 3min
completed: 2026-03-23
---

# Phase 9 Plan 03: GCPProvider + deploy_target Wiring Summary

**GCPProvider with gcloud CLI auth preflight, Cloud Run deploy via `gcloud run deploy --source .`, URL extraction from stderr, plus deploy_target parameter wired end-to-end from MCP bridge through run_pipeline() to PhaseContext.extra**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-23T07:59:05Z
- **Completed:** 2026-03-23T08:02:27Z
- **Tasks:** 2 (TDD for Task 1 + direct implementation for Task 2)
- **Files modified:** 5

## Accomplishments

- GCPProvider implements 3-step auth preflight: gcloud CLI presence, auth token validity, project configured
- Each preflight failure returns an actionable error with the exact remediation command to run
- `_GCP_URL_RE` regex extracts `https://...run.app` URL from gcloud stderr (not stdout — gcloud writes Service URL to stderr)
- GCPProvider.verify() delegates to run_deployment_gate() returning `.passed` — consistent with VercelProvider pattern
- Default region: reads `gcloud config get-value run/region`; if empty, defaults to `us-central1` with a log warning
- TimeoutExpired handled with clear 600-second timeout error message
- deploy_target forwarded unconditionally from `start_pipeline_async()` into `pipeline_kwargs` (not conditional on truthiness — always has a default value)
- `run_pipeline()` now accepts `deploy_target: str = "vercel"` and passes it into `PhaseContext.extra["deploy_target"]`
- 9 new GCPProvider tests + 2 new deploy_target forwarding tests — total 42 tests pass
- Subprocess audit continues to pass (no shell=True anywhere)
- xfail removed from `test_registry_gcp` (full implementation complete)

## Task Commits

Each task was committed atomically:

1. **RED Phase: Failing tests** — `1059350` (test)
2. **GREEN Phase: GCPProvider implementation** — `19538d5` (feat)
3. **Task 2: deploy_target wiring** — `4b0abbd` (feat)

_Note: TDD tasks have two commits (test → feat)_

## Files Created/Modified

- `tools/deploy_providers/gcp_provider.py` — Full GCPProvider: auth preflight, Cloud Run deploy, URL extraction (replaces placeholder stub)
- `tests/test_deploy_providers.py` — Added TestGCPProvider class (9 tests); removed xfail from test_registry_gcp
- `web_app_factory/_pipeline_bridge.py` — deploy_target unconditionally added to pipeline_kwargs
- `tools/contract_pipeline_runner.py` — deploy_target param in run_pipeline() signature; forwarded to PhaseContext.extra
- `tests/test_pipeline_bridge.py` — 2 new tests: test_deploy_target_forwarded, test_deploy_target_default

## Decisions Made

- `_extract_gcp_url` searches `stderr` not `stdout`: gcloud run deploy writes "Service URL:" to stderr, not stdout. This is the correct behavior as documented in gcloud output format.
- deploy_target added unconditionally to pipeline_kwargs (not wrapped in `if deploy_target:`): unlike company_name/contact_email which may be `None`, deploy_target always has a string value (default "vercel"), so it's always forwarded.
- Default "vercel" preserved at every layer: bridge default, run_pipeline() default, all backward-compatible.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

For GCPProvider to work, users need:
```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login

# Set project
gcloud config set project <PROJECT_ID>

# Optional: set default Cloud Run region
gcloud config set run/region us-central1
```

## Next Phase Readiness

- All three deploy providers are now fully implemented (VercelProvider in 09-02, GCPProvider here)
- deploy_target flows end-to-end: MCP tool → bridge → run_pipeline → PhaseContext.extra["deploy_target"]
- Phase 3 executor (phase_3_executor.py) can now read `ctx.extra.get("deploy_target", "vercel")` and use get_provider() to select the right provider
- Phase 9 is complete: DEPL-01, DEPL-02, DEPL-03, DEPL-04, DEPL-05, DEPL-06 all satisfied
- DEPL-02 (VercelProvider) was completed in Plan 09-02

## Self-Check: PASSED

- tools/deploy_providers/gcp_provider.py: FOUND
- web_app_factory/_pipeline_bridge.py: FOUND
- tools/contract_pipeline_runner.py: FOUND
- tests/test_deploy_providers.py: FOUND
- tests/test_pipeline_bridge.py: FOUND
- Commit 1059350 (RED): FOUND
- Commit 19538d5 (GREEN): FOUND
- Commit 4b0abbd (Task 2): FOUND

---
*Phase: 09-deploy-abstraction*
*Completed: 2026-03-23*
