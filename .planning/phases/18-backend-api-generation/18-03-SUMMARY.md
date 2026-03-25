---
phase: 18-backend-api-generation
plan: 03
subsystem: api
tags: [nextjs, zod, route-handlers, backend-spec, pipeline-gate, tdd]

# Dependency graph
requires:
  - phase: 18-01
    provides: BackendSpecValidator gate (run_backend_spec_gate) and backend template files
  - phase: 18-02
    provides: Phase 1b extension that produces backend-spec.json from spec agent

provides:
  - Phase 2b generate_api_routes sub-step that creates Route Handlers from backend-spec.json
  - API routes prompt template (Zod validation, error shape, health endpoint, no Pitfall 2 content)
  - backend_spec gate wired into contract_pipeline_runner._run_gate_checks dispatch
  - backend_spec gate type in pipeline-contract.web.v1.yaml Phase 2b
  - backend-spec.json as optional deliverable in pipeline-contract.web.v1.yaml Phase 1b
  - optional property added to pipeline-contract.schema.json deliverable definition
  - backend_spec enum added to pipeline-contract.schema.json gate type

affects:
  - Phase 19 (auth scaffolding) — API routes already generated so auth middleware can wrap them
  - Phase 20 (iOS backend) — same backend-spec.json driving mobile API generation

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "generate_api_routes runs AFTER generate_pages (src/lib/supabase/server.ts available) and BEFORE generate_integration"
    - "Conditional sub-step pattern: check for optional input file, skip with info log if absent"
    - "Pitfall 2 avoidance: API routes prompt embeds ONLY backend-spec.json, never prd.md or screen-spec.json"
    - "Lazy import of backend_spec_gate in _run_gate_checks (consistent with lighthouse/accessibility pattern)"

key-files:
  created:
    - tests/test_gate_dispatch_backend_spec.py
  modified:
    - tools/phase_executors/phase_2b_executor.py
    - agents/definitions.py
    - tools/contract_pipeline_runner.py
    - contracts/pipeline-contract.web.v1.yaml
    - contracts/pipeline-contract.schema.json
    - tests/test_phase_2b_executor.py

key-decisions:
  - "generate_api_routes positioned as step 4 (after pages, before integration) — pages ensure Supabase server client is available; integration step can then check API routes exist"
  - "API routes prompt excludes prd.md and screen-spec.json content (Pitfall 2) — only backend-spec.json embedded for focused route generation"
  - "Graceful skip when backend-spec.json absent — frontend-only apps not penalized, sub-step records success with skip note"
  - "Schema updated to allow optional deliverables and backend_spec gate type — was blocking full test suite"

patterns-established:
  - "Conditional sub-step: check optional file existence before calling run_build_agent"
  - "Gate dispatch extension: add elif branch with lazy import, use nextjs_dir fallback pattern"
  - "Contract YAML extension: optional: true flag on deliverables that may not always be produced"

requirements-completed: [BGEN-02, BGEN-03, BGEN-04, BGEN-05]

# Metrics
duration: 6min
completed: 2026-03-25
---

# Phase 18 Plan 03: Backend API Generation Summary

**Phase 2b extended with generate_api_routes sub-step that creates Zod-validated Next.js Route Handlers from backend-spec.json, with BackendSpecValidator gate wired into the pipeline runner**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-25T00:54:26Z
- **Completed:** 2026-03-25T01:00:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `generate_api_routes` as Step 4 in Phase 2b executor (6 total sub-steps, was 5)
- API routes prompt template embeds backend-spec.json only — does NOT re-embed prd.md or screen-spec.json (Pitfall 2 mitigated)
- Sub-step skips gracefully when backend-spec.json absent (frontend-only apps not penalized)
- Wired `backend_spec` gate type into `_run_gate_checks` dispatch with lazy import and nextjs_dir fallback
- Updated pipeline-contract.web.v1.yaml: backend_spec gate in Phase 2b, optional backend-spec.json deliverable in Phase 1b
- Updated pipeline-contract.schema.json: added `optional` boolean to deliverable definition and `backend_spec` to gate type enum

## Task Commits

Each task was committed atomically:

1. **Task 1: Add generate_api_routes sub-step and update BUILD_AGENT prompt** - `869c7aa` (feat)
2. **Task 2: Wire backend_spec gate into pipeline runner and update contract YAML** - `60b17b9` (feat)

_Note: Both tasks used TDD (RED → GREEN). Schema fix was inline auto-fix during Task 2._

## Files Created/Modified

- `tools/phase_executors/phase_2b_executor.py` - Added `_BACKEND_SPEC_PATH`, `_API_ROUTES_PROMPT_TEMPLATE`, `generate_api_routes` sub-step with conditional execution
- `agents/definitions.py` - Added Route Handler generation instructions to `_BUILD_AGENT_SYSTEM_PROMPT` (15 lines, kept under 35)
- `tools/contract_pipeline_runner.py` - Added `elif gate_type == "backend_spec":` dispatch branch
- `contracts/pipeline-contract.web.v1.yaml` - Added `backend_spec` gate to Phase 2b; added optional `backend-spec.json` deliverable to Phase 1b
- `contracts/pipeline-contract.schema.json` - Added `optional` property to deliverable definition; added `backend_spec` to gate type enum
- `tests/test_phase_2b_executor.py` - 8 new tests for `generate_api_routes` sub-step (35 total)
- `tests/test_gate_dispatch_backend_spec.py` - 6 new gate dispatch tests (created)

## Decisions Made

- `generate_api_routes` positioned after `generate_pages` and before `generate_integration` — ensures Supabase server client (generated during pages step) is available before API routes are created
- API routes prompt strictly excludes prd.md and screen-spec.json content — only backend-spec.json embedded to prevent agent from re-generating already-created page files (Pitfall 2 from RESEARCH.md)
- Graceful skip when no backend-spec.json: records success with "Skipped — frontend-only app" note, does not fail

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated pipeline-contract.schema.json to support new features**
- **Found during:** Task 2 (update contract YAML)
- **Issue:** Adding `optional: true` to deliverable and `backend_spec` to gate type caused 13 test failures due to JSON schema validation blocking the new properties
- **Fix:** Added `optional` boolean property to deliverable definition in schema; added `backend_spec` to gate type enum
- **Files modified:** `contracts/pipeline-contract.schema.json`
- **Verification:** `uv run pytest tests/test_contract_schema.py tests/test_contract_runner.py -q` — 60 passed
- **Committed in:** `60b17b9` (Task 2 commit)

**2. [Rule 1 - Bug] Updated existing test `test_sub_steps_contains_expected_steps` for 6-step list**
- **Found during:** Task 1 full test run
- **Issue:** Pre-existing test checked exact 5-element sub_steps list; after adding `generate_api_routes`, test failed
- **Fix:** Updated test to include `generate_api_routes` at index 3; renamed `test_sub_steps_is_five_elements` to `test_sub_steps_is_six_elements`
- **Files modified:** `tests/test_phase_2b_executor.py`
- **Verification:** `uv run pytest tests/test_phase_2b_executor.py -q` — 35 passed
- **Committed in:** `869c7aa` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (Rule 1 - Bug in both cases)
**Impact on plan:** Both fixes necessary for correctness — schema needed updating to accept new contract features; test updated to reflect intended new behavior. No scope creep.

## Issues Encountered

- Pre-existing test failure `test_factory_cli.py::TestFactoryCLIFlags::test_deploy_target_github_pages` (tests intentionally invalid `--deploy-target github-pages` argument) — confirmed pre-existing via git stash test, out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 18 is complete (3/3 plans)
- Phase 2b now generates API routes from backend-spec.json with full Zod validation enforcement
- BackendSpecValidator gate runs automatically after Phase 2b — catches missing validation, SQL injection, raw secrets, missing health endpoint
- Ready for Phase 19 (Supabase Auth Scaffolding) which can wrap the generated API routes with auth middleware

---
*Phase: 18-backend-api-generation*
*Completed: 2026-03-25*
