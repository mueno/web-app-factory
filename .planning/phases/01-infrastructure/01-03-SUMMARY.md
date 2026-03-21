---
phase: 01-infrastructure
plan: 03
subsystem: infra
tags: [mcp-server, quality-assessment, error-router, agent-stubs, phase-stubs, gate-gaming-prevention]

# Dependency graph
requires:
  - phase: 01-infrastructure/01-01
    provides: pyproject.toml, YAML contract, JSON schema
  - phase: 01-infrastructure/01-02
    provides: pipeline_state functions (phase_start, phase_complete, init_run, load_state)

provides:
  - MCP server (approve_gate + phase_reporter) with project_dir bridge to pipeline_state (CRITICAL)
  - config/settings.py with web paths (APPROVAL_TMP_DIR, VERCEL_CONFIG_DIR, DEFAULT_FRAMEWORK)
  - agents/definitions.py with AgentDefinition dataclass and 3 stubs (spec, build, deploy)
  - pipeline_runtime/error_router.py with web failure patterns (next build, lighthouse, CSP)
  - tools/phase_executors/phase_stubs.py with stub executors for all 5 phases
  - tools/quality_self_assessment.py generate_quality_self_assessment (CONT-04)
  - tests/test_factory_mcp_bridge.py CRITICAL integration test (HealthStockBoardV30 safety net)
  - tests/test_quality_assessment.py quality assessment generation tests

affects:
  - 01-infrastructure/01-04 (CLI factory.py can now import from config.settings and MCP tools)
  - phase-02 (quality_self_assessment available for phase executors to call before gates)
  - phase-03 (error_router ready to classify build/deploy failures)

# Tech tracking
tech-stack:
  added:
    - PyYAML (via yaml import in quality_self_assessment.py — already in pyproject.toml)
  patterns:
    - "MCP server project_dir bridge: phase_reporter calls pipeline_state.phase_start/phase_complete"
    - "Fallback activity log: when bridge fails, writes directly to activity-log.jsonl"
    - "Phase normalization: 'Phase 1a: Idea Validation' -> '1a' via regex + NFKC unicode normalization"
    - "Quality assessment: pending criteria template generated from YAML contract before gate submission"
    - "Stub executor pattern: returns PhaseResult(success=False, error='not implemented') for all 5 phases"

key-files:
  created:
    - tools/factory_mcp_server.py
    - config/settings.py
    - agents/definitions.py
    - pipeline_runtime/error_router.py
    - tools/phase_executors/phase_stubs.py
    - tools/quality_self_assessment.py
    - tests/test_factory_mcp_bridge.py
    - tests/test_quality_assessment.py
  modified: []

key-decisions:
  - "iOS tools removed from MCP server (render_legal_template, render_pera1_pitch, scaffold_app, xac_evaluate, analyze_rejection, increment_build, register_bundle_id, create_asc_app_record, generate_promo_assets)"
  - "project_dir bridge preserved verbatim from ios-app-factory — this is the critical integration point"
  - "ship-agent renamed to deploy-agent in error router (reflects Vercel deploy vs ASC ship)"
  - "Test updated: pipeline_state.phase_start sets status 'running' not 'in_progress'; init_run generates run_id internally"
  - "Phase stubs do NOT auto-register at module load (registry stays empty until Phase 2+ executors added)"

patterns-established:
  - "Quality self-assessment: generate pending JSON from contract before gate, fill evidence during execution"
  - "MCP bridge test pattern: call async tool function directly via asyncio.run() in tests"

requirements-completed:
  - PIPE-04
  - CONT-04

# Metrics
duration: 5min
completed: 2026-03-21
---

# Phase 1 Plan 3: MCP Server, Quality Assessment, Error Router Summary

**MCP server adapted from ios-app-factory (iOS tools stripped, project_dir bridge preserved), quality self-assessment module reads YAML contract criteria, error router updated for web patterns, and CRITICAL integration test proves phase_reporter -> state.json bridge works**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-21T12:30:06Z
- **Completed:** 2026-03-21T12:35:01Z
- **Tasks:** 2 (Task 1 direct + Task 2 TDD)
- **Files modified:** 8

## Accomplishments

- MCP server adapted: 9 iOS-specific tools removed, approve_gate and phase_reporter kept verbatim with project_dir bridge intact
- CRITICAL bridge integration test: 5 tests prove phase_reporter -> state.json updates work (the HealthStockBoardV30 safety net)
- Quality self-assessment module: reads quality_criteria from YAML contract, generates pending JSON at docs/pipeline/quality-self-assessment-{phase_id}.json
- Error router updated for web: iOS patterns (xcodebuild, xcresult, signing) replaced with web patterns (next build, lighthouse, CSP, NEXT_PUBLIC)
- 3 agent stubs (spec-agent, build-agent, deploy-agent) defined with AgentDefinition dataclass
- 5 phase executor stubs (1a, 1b, 2a, 2b, 3) allow pipeline runner to load without crashing
- All 58 tests pass (43 from Plans 01-02 + 15 new)

## Task Commits

Each task was committed atomically:

1. **Task 1 (Direct):** `4eb47b5` — feat(01-03): adapt MCP server, config, error router, agent stubs, phase stubs
2. **Task 2 (TDD RED):** `0c711ca` — test(01-03): add failing tests for quality assessment and MCP bridge integration
3. **Task 2 (TDD GREEN):** `7b6cb11` — feat(01-03): implement quality self-assessment module + green MCP bridge tests

## Files Created/Modified

- `tools/factory_mcp_server.py` - FastMCP server with approve_gate + phase_reporter (iOS tools removed)
- `config/settings.py` - APPROVAL_TMP_DIR, VERCEL_CONFIG_DIR, DEFAULT_FRAMEWORK, DEFAULT_DEPLOY_TARGET
- `agents/definitions.py` - AgentDefinition dataclass + 3 stubs (spec-agent, build-agent, deploy-agent)
- `pipeline_runtime/error_router.py` - Web failure patterns; ship-agent -> deploy-agent
- `tools/phase_executors/phase_stubs.py` - 5 stub executors for phases 1a, 1b, 2a, 2b, 3
- `tools/quality_self_assessment.py` - generate_quality_self_assessment reads contract YAML criteria
- `tests/test_factory_mcp_bridge.py` - 5 CRITICAL integration tests: MCP -> state.json bridge
- `tests/test_quality_assessment.py` - 10 tests: quality assessment JSON structure, file output, contract fidelity

## Decisions Made

- iOS tools stripped (9 removed): render_legal_template, render_pera1_pitch, scaffold_app, xac_evaluate, analyze_rejection, increment_build, register_bundle_id, create_asc_app_record, generate_promo_assets — none relevant to web pipeline
- project_dir bridge preserved verbatim — this is the single most dangerous integration point per MEMORY.md Dual Implementation Divergence; without it, state.json never updates
- ship-agent renamed to deploy-agent throughout error_router.py (web deploy != iOS ship)
- Phase stub executors do NOT auto-register at module import (registry stays empty, Phase 2+ executors populate it)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_factory_mcp_bridge.py to match actual pipeline_state API**
- **Found during:** Task 2 (TDD GREEN - first run)
- **Issue:** Tests used `init_run(run_id, str(tmp_path))` but actual signature is `init_run(app_name, project_dir, idea)` which generates run_id internally; also expected "in_progress" status but pipeline_state uses "running"
- **Fix:** Updated tests to call `init_run("test-app", str(tmp_path), "idea")`, capture returned state's `run_id`, and assert `status == "running"`
- **Files modified:** tests/test_factory_mcp_bridge.py
- **Verification:** All 15 bridge + quality assessment tests pass
- **Committed in:** 7b6cb11 (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (test API mismatch discovered during GREEN phase)
**Impact on plan:** Fix necessary for test correctness. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- MCP server complete; plan 04 (CLI factory.py) can import config.settings and use approve_gate/phase_reporter
- Quality assessment available for Phase 2 executors to call before gate submission
- Error router ready to classify failures from build/test/deploy/legal gates
- Phase executor stubs allow pipeline runner to load all phases without ImportError
- All 58 tests pass across Plans 01, 02, and 03

## Self-Check: PASSED

All created files verified present on disk. All commits verified in git log.

| Item | Status |
|------|--------|
| tools/factory_mcp_server.py | FOUND |
| config/settings.py | FOUND |
| agents/definitions.py | FOUND |
| pipeline_runtime/error_router.py | FOUND |
| tools/phase_executors/phase_stubs.py | FOUND |
| tools/quality_self_assessment.py | FOUND |
| tests/test_factory_mcp_bridge.py | FOUND |
| tests/test_quality_assessment.py | FOUND |
| 4eb47b5 (Task 1 feat commit) | FOUND |
| 0c711ca (Task 2 RED commit) | FOUND |
| 7b6cb11 (Task 2 GREEN commit) | FOUND |

---
*Phase: 01-infrastructure*
*Completed: 2026-03-21*
