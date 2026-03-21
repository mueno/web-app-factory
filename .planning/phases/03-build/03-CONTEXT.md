# Phase 3: Build - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

The build agent scaffolds a Next.js project (Phase 2a) and generates all pages, components, and API routes from the PRD and screen specification (Phase 2b). Build and static analysis gates enforce compilation, type-checking, server/client boundary correctness, and secret leak prevention. This phase replaces the Phase 2a and 2b stub executors with real implementations.

</domain>

<decisions>
## Implementation Decisions

### Build agent tool set and security model
- Build agent uses Claude Agent SDK multi-turn tool-use loop (same pattern as spec agent via `run_spec_agent` → rename/generalize to `run_agent`)
- Allowed tools: `Read`, `Write`, `Bash` — build agent MUST be able to write files and run shell commands (`npm install`, `npm run build`, `npx create-next-app`)
- `Bash` tool is restricted by `cwd` set to the generated project directory (not the pipeline root) — the agent cannot escape the project sandbox
- No `WebSearch` for build agent — code generation draws from PRD/screen-spec context, not live web data
- Max turns: 50 (higher than spec agent's 25 — code generation requires more iterations for multi-screen apps)

### Scaffold approach (Phase 2a)
- Phase 2a executor runs `npx create-next-app@latest` as a deterministic subprocess (NOT through the agent) with explicit flags: `--typescript --tailwind --app --src-dir --no-git --use-npm`
- After subprocess completes, the executor calls the build agent to customize the scaffold: replace boilerplate `page.tsx` with a meaningful landing placeholder, configure `next.config.ts`, set strict TypeScript mode
- This two-step approach (subprocess for reproducible scaffold, agent for customization) prevents the agent from hallucinating the project structure
- npm package validation from Phase 1a (`validate_npm_packages` pattern via httpx) is reused in Phase 2b for any additional dependencies the build agent wants to install (BILD-07)

### Code generation strategy (Phase 2b)
- Build agent receives the full PRD text and screen-spec.json content in its prompt (same content-injection pattern as Phase 1b receiving Phase 1a output)
- Generation order: shared components first (from PRD component inventory), then page-by-page following screen-spec.json route order
- Single agent call with multi-turn loop — the agent reads screen-spec, creates components, then creates pages that compose those components
- Error boundaries: agent generates `error.tsx` and `not-found.tsx` for every route segment with async data dependencies (BILD-06)
- Responsive: agent uses mobile-first Tailwind classes — base styles for mobile, `md:` and `lg:` prefixes for larger screens (BILD-05)

### Build gate implementation
- New gate executor files in `tools/gates/`: `build_gate.py`, `static_analysis_gate.py`
- Build gate runs `subprocess.run(["npm", "run", "build"], cwd=project_dir)` and `subprocess.run(["npx", "tsc", "--noEmit"], cwd=project_dir)` — returns `GateResult(passed=True/False)` based on exit codes
- Gate executor uses `subprocess.run` with `capture_output=True`, `timeout=120` (2-minute cap per command)
- On failure: stderr output is captured and included in `GateResult.issues` for diagnostic use by error_router

### Static analysis gate implementation
- Regex-based file scanning (not AST) — sufficient for the two checks needed and avoids adding a TypeScript parser dependency
- Check 1 (`no_use_client_in_layout`): scan `src/app/layout.tsx` and `src/app/page.tsx` for `"use client"` directive — fail if found
- Check 2 (`no_next_public_secrets`): scan all files under `src/` for `NEXT_PUBLIC_.*KEY|NEXT_PUBLIC_.*SECRET|NEXT_PUBLIC_.*TOKEN` pattern — fail if found
- Both checks produce structured issue records in `GateResult` with file path and line number

### Agent runner generalization
- Rename/generalize `spec_agent_runner.py` → extract a shared `run_agent()` function that both spec and build agents use
- Or: create `build_agent_runner.py` following the same pattern with build-specific tool set (Bash instead of WebSearch)
- `load_phase_quality_criteria()` and `build_phase_system_prompt()` are already generic and reusable as-is
- BUILD_AGENT definition in `agents/definitions.py` gets a real system prompt (web-centric, Next.js App Router expertise, no iOS references)

### Claude's Discretion
- Exact build agent system prompt wording
- Sub-step breakdown within Phase 2a and 2b executors
- Whether to generalize `run_spec_agent` or create a parallel `run_build_agent`
- Tailwind CSS v4 configuration details (PostCSS setup)
- Error handling for `create-next-app` subprocess failures
- Exact timeout values for gate subprocess calls

</decisions>

<specifics>
## Specific Ideas

- The YAML contract already specifies gate types (`build`, `static_analysis`) with conditions — the gate executors must match these types and conditions exactly
- STATE.md flags "Build-agent prompt engineering for Next.js App Router is high-risk" — the system prompt must include explicit rules: server components by default, `"use client"` only in interactive leaf components, never in layout.tsx or page.tsx
- npm hallucination prevention (BILD-07) is critical — the build agent must validate every `npm install` command against the registry before executing, using the Phase 1a `validate_npm_packages` pattern
- The build gate runs in the generated project directory (a subdirectory of `output/`), not the pipeline root — `cwd` parameter is essential

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `spec_agent_runner.py`: `load_phase_quality_criteria()` and `build_phase_system_prompt()` are fully generic — work for any phase_id
- `run_spec_agent()` pattern: async/sync bridge via `asyncio.run()`, `ClaudeAgentOptions` construction — clone for build agent with different `allowed_tools`
- `phase_1a_executor.py` / `phase_1b_executor.py`: executor structure (sub-steps, self-registration, quality self-assessment) — follow identical pattern
- `GateResult` dataclass (`tools/gates/gate_result.py`): frozen, dict-compatible, with `issues` and `advisories` lists
- `GatePolicy` (`tools/gates/gate_policy.py`): fail-closed policy enforcement
- `validate_npm_packages()` in `phase_1a_executor.py`: httpx-based npm registry validation — reuse or extract to shared module
- `Phase2aStubExecutor` / `Phase2bStubExecutor` (`phase_stubs.py`): Replace with real implementations

### Established Patterns
- Executor self-registration at module import with reload-safe guard (`get_executor(id) is None`)
- PhaseContext with security-validated `project_dir` (path traversal prevention)
- Quality self-assessment JSON before gate submission
- Content injection: prior phase deliverables embedded as full text in agent prompts (not just file paths)
- Sub-step tracking via `SubStepResult` list in `PhaseResult`

### Integration Points
- `contract_pipeline_runner.py` already imports phase_1a and phase_1b executors — add imports for phase_2a and phase_2b
- Gate types in YAML contract (`build`, `static_analysis`) need matching gate executor implementations
- `contract_pipeline_runner.py` dispatches to gate executors by type — new gate types must be registered/handled
- Generated project lives at `{project_dir}/` — all gate commands run with `cwd=project_dir`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-build*
*Context gathered: 2026-03-21*
