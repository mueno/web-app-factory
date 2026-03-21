# Phase 2: Spec - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

The spec agent validates a web app idea and produces a structured PRD that the build agent can consume. This phase replaces the Phase 1a and 1b stub executors with real implementations that call the spec-agent via Claude Agent SDK. Deliverables: idea-validation.md, tech-feasibility-memo.json, prd.md, screen-spec.json.

</domain>

<decisions>
## Implementation Decisions

### Agent orchestration model
- Spec agent uses Claude Agent SDK multi-turn tool-use loop (not single-shot prompt generation)
- Tools available to spec agent: web search (competitor discovery, market data), npm registry lookup (package validation for tech feasibility)
- Phase 1a and 1b are separate executor classes, each calling the spec-agent with phase-specific system prompt sections
- Single `AgentDefinition` for spec-agent in `agents/definitions.py`, but each executor constructs a phase-specific prompt that includes the YAML contract's purpose and quality_criteria for that phase
- Max turns capped per executor call (defense against runaway loops — follow ios-app-factory pattern)

### Market research sources
- Hybrid approach: web search tools for real competitor discovery and market data, with LLM synthesis for analysis
- Competitor names must come from web search results, not LLM hallucination — the quality criteria requires "named competitor apps with specific feature comparisons"
- Market size estimates should cite web search sources where available; LLM extrapolation acceptable when cited as such
- Tech feasibility memo uses npm registry lookup to validate that referenced packages actually exist (hallucination prevention, aligns with BILD-07)

### Go/No-Go decision handling
- No-Go result stops the pipeline at Phase 1a gate — does NOT auto-proceed
- The idea-validation.md must contain an explicit "Go" or "No-Go" recommendation with supporting rationale
- On No-Go: pipeline surfaces the validation report via MCP approval gate (`approve_gate`), letting the human review the analysis
- Human can: approve (override No-Go and proceed), reject (abort pipeline), or restart with a refined idea via CLI re-invocation
- No auto-pivot — the pipeline reports findings; the human decides next action
- Go/No-Go is a structured field in the validation report, not just prose (parseable by the gate checker)

### PRD-to-build handoff format
- `screen-spec.json` follows a strict JSON schema defining: screens, routes, component inventory, layout regions, responsive breakpoints, interactive states
- Component names in screen-spec.json must match the PRD component inventory exactly (cross-reference validation in Phase 1b gate)
- Each screen entry includes: `route` (URL path), `layout` (regions: header/sidebar/main/footer), `components` (list with hierarchy), `states` (loading/error/empty/populated), `responsive` (mobile vs desktop differences)
- `prd.md` is human-readable markdown with MoSCoW-labeled requirements; `screen-spec.json` is the machine-readable counterpart consumed by the build agent
- Both files are generated in a single Phase 1b executor run — the agent writes markdown first, then derives the JSON from it (ensuring consistency)

### Claude's Discretion
- Exact spec agent system prompt wording (as long as it contains no iOS references per SPEC-04)
- Sub-step granularity within each executor (e.g., research → analyze → write → self-assess)
- Web search query formulation strategy for competitor discovery
- screen-spec.json schema field names and nesting structure (as long as it covers the required information)
- Error handling and retry strategy for web search failures

</decisions>

<specifics>
## Specific Ideas

- The ios-app-factory spec agent prompt is a proven reference — adapt its structure (role definition, output format instructions, quality anchors) while replacing all iOS-specific content with web/Next.js equivalents
- Quality criteria strings in the YAML contract are already detailed enough to serve as prompt constraints — the executor should inject them into the agent's system prompt so the LLM knows what "good" looks like before generating
- The tech-feasibility-memo.json should evaluate Next.js suitability (SSR vs SSG vs ISR) against the specific app requirements, not just rubber-stamp "Next.js is fine"

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PhaseExecutor` base class (`tools/phase_executors/base.py`): `execute()` → `PhaseResult` pattern, `PhaseContext` with validated run_id/phase_id/project_dir
- `Phase1aStubExecutor` / `Phase1bStubExecutor` (`tools/phase_executors/phase_stubs.py`): Replace these with real implementations
- `SPEC_AGENT` definition (`agents/definitions.py`): Update system_prompt from placeholder to real prompt
- `register()` function (`tools/phase_executors/registry.py`): Real executors self-register here
- `quality_self_assessment.py`: Generate self-assessment JSON before gate submission (CONT-04)
- `contract_pipeline_runner.py`: Reads YAML contract, dispatches to registered executors, enforces gates

### Established Patterns
- Frozen `PhaseContext` dataclass with security validation (path traversal, run_id format)
- `PhaseResult` with `sub_steps` list and optional `resume_point` for interruption recovery
- Gate policy is fail-closed (`defaults.gate_policy: fail-closed` in YAML contract)
- Quality self-assessment runs before every gate check

### Integration Points
- New executors register via `tools/phase_executors/registry.py` — pipeline runner looks up executor by phase_id
- Executors write deliverables to `{project_dir}/docs/pipeline/` — paths match YAML contract's `deliverables[].path`
- Gate checker reads deliverables from those paths and validates against `required_files` + `required_output_markers`
- MCP `approve_gate` tool provides human sign-off checkpoint (used for Go/No-Go review)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-spec*
*Context gathered: 2026-03-21*
