---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: MCP Apps
status: completed
stopped_at: Completed 13-01-PLAN.md — Phase 2b three-sub-step decomposition with checkpoint resume
last_updated: "2026-03-24T06:22:33.946Z"
last_activity: 2026-03-24 — Phase 12 Plan 02 complete (waf_check_env registered, 7 tools total)
progress:
  total_phases: 13
  completed_phases: 12
  total_plans: 28
  completed_plans: 28
  percent: 96
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** A single command takes a web app idea from concept to deployed, production-quality web application
**Current focus:** Phase 13 — Pipeline Quality (next)

## Current Position

Phase: 12 complete (2 of 2 plans done), Phase 13 next
Plan: 12-02 complete (waf_check_env MCP tool)
Status: Phase 12 complete. Next: Phase 13 (Pipeline Quality — depends only on Phase 8).
Last activity: 2026-03-24 — Phase 12 Plan 02 complete (waf_check_env registered, 7 tools total)

Progress: [█████████░] 96% (v2.0 milestone — 12 of 13 phases complete)

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Carried from v1.0 + v2.0 research:

- Fork, not refactor — ios-app-factory continues independent development
- Three-tool async pattern: waf_generate returns run_id immediately, pipeline in background thread
- waf_ prefix on all public tools — must not be changed after first deployment (collision risk)
- AWS provider is stub only in v2 — full CDK implementation deferred to v3.0
- Phase 13 (Pipeline Quality) depends only on Phase 8, not on Phases 9-12 (independent execution path)
- [Phase 08-mcp-infrastructure-foundation]: FastMCP 3.x tool introspection uses asyncio.run(mcp.list_tools()) not _tool_manager._tools (path doesn't exist in fastmcp 3.x)
- [Phase 08-mcp-infrastructure-foundation]: Public server uses 'from fastmcp import FastMCP'; internal server uses 'from mcp.server.fastmcp import FastMCP' — maintaining clear import separation
- [Phase 08-mcp-infrastructure-foundation]: Flat-layout project requires [tool.setuptools.packages.find] include=['web_app_factory*'] to prevent multi-package discovery error on uv pip install -e .
- [Phase 08-mcp-infrastructure-foundation]: Credential values never logged at any level — key names and type(exc).__name__ only, per security-core.md contract
- [Phase 08-mcp-infrastructure-foundation]: Use _run_pipeline_sync() wrapper to isolate import boundary for test patching without complex mock machinery
- [Phase 08-mcp-infrastructure-foundation]: Generate run_id BEFORE executor submission (Pitfall 5: prevents queue-full blocking on run_id return)
- [Phase 08-mcp-infrastructure-foundation]: Static subprocess audit test catches shell=True regressions in CI before merge
- [Phase 09-deploy-abstraction Plan 01]: Placeholder stubs for VercelProvider and GCPProvider created so registry.py imports work in Plan 01; Plans 02/03 overwrite with full implementations
- [Phase 09-deploy-abstraction Plan 01]: ABC used over Protocol — runtime TypeError at instantiation preferred for gate-safety
- [Phase 09-deploy-abstraction Plan 01]: LocalOnlyProvider.verify() returns True unconditionally — deployment_gate skipped for local targets per user decision
- [Phase 09-deploy-abstraction]: GCPProvider extracts Service URL from stderr (not stdout) — gcloud run deploy writes URL to stderr
- [Phase 09-deploy-abstraction]: deploy_target unconditionally forwarded in pipeline_kwargs (not conditional on truthiness like company_name) — always has a string value
- [Phase Phase 09-deploy-abstraction Plan 02]: VercelProvider.deploy() orchestrates provision+preview+promote atomically; phase_3_executor is now subprocess-free and deploy-target-agnostic
- [Phase 10-local-dev-server]: start_new_session=True on Popen enables os.killpg for full npm/node/next process tree termination
- [Phase 10-local-dev-server]: _PROC_MAP separate from frozen DevServerInfo registry — mutable Popen cannot live in frozen dataclass
- [Phase 10-local-dev-server]: [Phase 10-local-dev-server Plan 02]: waf_start_dev_server uses run_in_executor because start_dev_server blocks up to 30s; waf_stop_dev_server calls stop_dev_server directly (fast path)
- [Phase 12-environment-detection-distribution Plan 01]: Patch target for 'from X import f' imports is the importing module (web_app_factory._env_checker.*), not the source module (pipeline_runtime.startup_preflight.*)
- [Phase 12-environment-detection-distribution Plan 01]: Python status always 'present' in _env_checker — MCP server cannot be running without Python >= 3.10 (per RESEARCH.md Pitfall 6)
- [Phase 12-environment-detection-distribution Plan 01]: node on linux has no _INSTALL_ARGS entry — too many distro variants; returns manual nodesource/nvm instructions instead
- [Phase 12-environment-detection-distribution]: waf_check_env uses run_in_executor for check_env and install_tool — both may call subprocess and block 2-5s
- [Phase 12-environment-detection-distribution]: execute_install=True without tool_to_install returns error string (guard against accidental installs)
- [Phase 13]: Use sync_playwright (not async) — pipeline is synchronous, event loop conflicts avoided
- [Phase 13]: skip_allowed pattern for E2E gate: skipped=True + skip_allowed=True for apps without forms — not applicable, not a failure
- [Phase 13-pipeline-quality]: Integration prompt omits PRD/screen-spec to prevent agent re-generating already-written files (Pitfall 2 per RESEARCH.md)

### Pending Todos

- BL-001: Phase 2b WBS decomposition → QUAL-01 in Phase 13
- BL-002: E2E Playwright gate → QUAL-02 in Phase 13
- BL-003: Phase 1b data flow schema in screen-spec.json (not in v2.0 scope)

### Blockers/Concerns

- ✅ ~~FastMCP task=True marked experimental~~ — Resolved: Phase 8 uses ThreadPoolExecutor bridge pattern instead (proven reliable)
- open-next-cdk Python version MEDIUM confidence — run integration test in Phase 9 before committing; fallback is Vercel + GCP only
- Vercel API tokens cannot be project-scoped (platform constraint) — waf_check_env must warn users explicitly

## Session Continuity

Last session: 2026-03-24T06:18:23.481Z
Stopped at: Completed 13-01-PLAN.md — Phase 2b three-sub-step decomposition with checkpoint resume
Resume file: None
