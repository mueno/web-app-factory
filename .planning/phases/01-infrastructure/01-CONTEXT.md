# Phase 1: Infrastructure - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Fork ios-app-factory's domain-agnostic pipeline infrastructure into web-app-factory. Deliver a working Python project with CLI entry point, YAML contract, state persistence, MCP server, governance monitor, and startup preflight — all adapted for web app generation. Phase executors and agents are placeholder stubs only (implemented in Phase 2+).

</domain>

<decisions>
## Implementation Decisions

### Fork strategy
- Copy domain-agnostic files verbatim from ios-app-factory: `contract_pipeline_runner.py`, `pipeline_state.py`, `factory_mcp_server.py`, `governance_monitor.py`, `error_router.py`
- Adapt `factory.py` CLI: strip iOS flags (`--backend`, `--rejection-fix`), add web flags (`--deploy-target vercel`, `--framework nextjs`)
- Adapt `startup_preflight.py`: check Node.js 20.9+, npm, Vercel CLI instead of Xcode/xcrun/simctl
- Do NOT copy phase executors, agent definitions, or iOS-specific gates — those are new code in later phases
- Adapt `agents/definitions.py` as a stub with placeholder web agent names (spec-agent, build-agent, deploy-agent)

### YAML contract
- Create `contracts/pipeline-contract.web.v1.yaml` defining 5 sub-phases: 1a (idea validation), 1b (spec), 2a (scaffold), 2b (build), 3 (ship)
- Each phase entry includes: `purpose`, `deliverables` (with `quality_criteria` arrays), `gates` (type + conditions)
- Quality criteria must be content-verifying, not file-existence-only (gate-gaming prevention from day one)
- Contract validated against JSON schema at pipeline startup (CONT-03)
- Quality self-assessment pattern: `quality-self-assessment-{phase_id}.json` generated before every gate (CONT-04)

### CLI interface
- Entry point: `python factory.py --idea "description" --project-dir ./output/AppName`
- `--deploy-target`: vercel (default), github-pages (future)
- `--framework`: nextjs (default, only option for v1)
- `--dry-run`: validate contract and preflight without executing phases
- `--resume`: continue from last completed phase (uses state.json)

### Project setup
- Python project with `pyproject.toml` using uv for dependency management
- Dependencies: `claude-agent-sdk>=0.1.50`, `mcp>=1.26.0`, `fastmcp>=3.1.0`, `httpx>=0.28.0`
- Directory structure mirrors ios-app-factory: `tools/`, `agents/`, `contracts/`, `pipeline_runtime/`, `config/`, `output/`
- Tests via pytest, matching ios-app-factory test patterns

### Startup preflight checks
- Node.js 20.9+ (Next.js 16 minimum)
- npm (package management)
- Vercel CLI (`vercel --version`)
- Python 3.10+ (pipeline itself)
- Claude CLI or API reachability (LLM orchestration)

### MCP server
- Reuse `factory_mcp_server.py` as-is — `approve_gate` and `phase_reporter` tools are domain-agnostic
- Single implementation rule: MCP tool calls the same Python function as direct path (prevent dual-implementation divergence)
- Integration test: assert `state.json` updates after `phase_reporter` MCP call

### Claude's Discretion
- Exact directory structure within `tools/` (as long as it follows ios-app-factory patterns)
- Test file organization
- Exact error messages in preflight checks
- Config module design (`config/settings.py` adaptation)

</decisions>

<specifics>
## Specific Ideas

- The ios-app-factory's `contract_pipeline_runner.py` is the primary reuse target — it reads YAML, dispatches phases, enforces gates, and manages state without any iOS knowledge
- The `governance_monitor.py` enforces phase ordering and blocks bypass attempts — copy verbatim, it's pure infrastructure
- The YAML contract is the single source of truth that everything else is built against — getting it right in Phase 1 prevents rework in Phases 2-4
- Follow ios-app-factory's pattern of `pipeline_runtime/` for guards and `tools/` for executors

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets (from ios-app-factory)
- `tools/contract_pipeline_runner.py` (770 lines): YAML-driven phase loop — copy verbatim
- `tools/pipeline_state.py`: state.json + activity-log.jsonl persistence — copy verbatim
- `tools/factory_mcp_server.py`: FastMCP server with approve_gate + phase_reporter — copy verbatim
- `pipeline_runtime/governance_monitor.py`: Phase ordering enforcement — copy verbatim
- `pipeline_runtime/error_router.py`: Failure classification — copy with minor agent-name changes
- `pipeline_runtime/startup_preflight.py`: Environment checks — adapt for web tools

### Established Patterns
- Phase executors follow `PhaseExecutor` base class with `execute()` method returning `PhaseResult`
- Gates follow `GateResult` pattern with pass/fail + evidence
- YAML contract structure: phases → deliverables → quality_criteria → gates
- Quality self-assessment JSON before every gate submission

### Integration Points
- `factory.py` → `contract_pipeline_runner` → phase executors → gates → MCP server
- `pipeline_state.py` is the persistence backbone — all components write through it
- `governance_monitor.py` wraps phase transitions — it's the enforcement layer

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-infrastructure*
*Context gathered: 2026-03-21*
