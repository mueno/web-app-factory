# Phase 4: Ship - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Run comprehensive quality gates (Lighthouse, axe-core, security headers, link integrity) against a deployed Vercel preview URL, generate legally compliant Privacy Policy and Terms of Service, obtain human approval via MCP gate, and promote to production deployment. This phase adds 6 new gate types to the pipeline runner and implements the Phase 3 executor with deploy-agent orchestration.

</domain>

<decisions>
## Implementation Decisions

### Deploy-then-gate flow
- **Deploy first**: Vercel preview deploy → get preview URL → run all quality gates against live URL → MCP human approval → production promote
- **Auto-provisioning**: `vercel link --yes` auto-creates a new Vercel project if none is linked; no manual pre-setup required
- **Preview → Approval → Production**: Pipeline deploys to preview first, runs all gates against the preview URL, then requires MCP `approve_gate` sign-off before promoting to production via `vercel --prod`
- **MCP approval timing**: After all quality gates pass, before production deploy. Human sees Lighthouse scores, security results, and legal docs before deciding

### Security headers configuration
- **Set in next.config.ts headers()**: The build agent (Phase 2b) should include security headers in the generated `next.config.ts` — they are part of the app, not deployment config
- **Basic CSP**: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'` — allows Next.js inline scripts while blocking external scripts
- **Other required headers**: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`
- **HSTS**: Vercel provides HSTS automatically; the security headers gate verifies its presence but does not inject it
- **Verification method**: httpx GET request to deployed URL → check response headers contain all required headers

### Legal document generation
- **LLM-generated with PRD context**: Deploy-agent reads PRD and build output to generate Privacy Policy and Terms of Service that reference actual app features (data types collected, functionality offered)
- **Jurisdiction**: Japanese law (APPI) as primary basis, with basic GDPR/CCPA mentions for international coverage. AllNew LLC is a Japanese entity
- **Company information source**: CLI flags `--company-name` and `--contact-email`. If not provided, legal docs contain placeholder text and the legal quality gate fails (forces explicit company info)
- **Link placement**: Footer links on all pages — `/privacy` and `/terms` routes with Privacy Policy and Terms of Service content
- **Quality gate**: Legal docs must not contain template placeholders (`YOUR_APP_NAME`, `YOUR_COMPANY`, etc.) and must reference at least one app-specific feature by name

### Gate failure remediation
- **Auto-fix + retry**: When Lighthouse or axe-core gates fail, deploy-agent reads the diagnostic report, applies code fixes, re-deploys, and re-runs the failing gate
- **Retry limit**: Maximum 3 attempts per gate. After 3 failures, pipeline stops and escalates to human with full diagnostic history
- **Fix scope**: Performance optimization (image optimization, JS removal, CSS minification) AND accessibility fixes (alt text, contrast, ARIA attributes) are both permitted — not limited to non-destructive changes
- **axe-core critical violations**: Same auto-fix + retry pattern. Deploy-agent fixes the violation (e.g., adds missing alt text, fixes contrast ratio) → re-deploy → re-gate
- **Retry cycle**: fix code → `npm run build` → `vercel deploy` (new preview) → re-run failing gate only (not all gates)

### Claude's Discretion
- Deploy-agent system prompt wording (web deployment expertise, Lighthouse optimization knowledge)
- Exact Lighthouse CI invocation method (lighthouse-ci CLI or programmatic API)
- axe-core invocation method (Playwright + @axe-core/playwright or standalone CLI)
- Link integrity checker implementation (custom httpx crawler or existing tool)
- Sub-step breakdown within Phase 3 executor
- Exact retry backoff timing between attempts
- Whether to generate legal docs before or after quality gates (order within the phase)

</decisions>

<specifics>
## Specific Ideas

- The YAML contract defines Phase 3 (internal id "3") as Ship — the executor must register with phase_id "3"
- `_run_gate_checks` in `contract_pipeline_runner.py` needs 6 new gate type dispatchers: `lighthouse`, `accessibility`, `security_headers`, `link_integrity`, `deployment`, `mcp_approval`
- The error_router already classifies Phase 4 gate types correctly — `deploy-agent` handles deployment/lighthouse/accessibility/seo, `deploy-agent` also handles security_headers
- DEPLOY_AGENT in `agents/definitions.py` has a placeholder system prompt — needs real prompt with Vercel/Lighthouse/a11y expertise
- STATE.md flags: "Legal templates need GDPR/CCPA adaptation from ios-app-factory iOS-focused originals" — resolved by LLM generation with Japanese law basis
- STATE.md flags: "Vercel auto-provisioning CLI flow needs prototype validation" — `vercel link --yes` is the approach
- The deploy-agent needs `Bash` tool access (like build-agent) to run vercel CLI, lighthouse, and axe-core commands
- Security headers should be injected by the Phase 2b build agent during code generation — not by the ship phase. The ship phase only verifies their presence

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `build_agent_runner.py`: `run_build_agent()` pattern with Claude Agent SDK — clone for deploy-agent with different tool set and system prompt
- `GateResult` dataclass (`tools/gates/gate_result.py`): Frozen, dict-compatible, with `issues` and `advisories` — use for all 6 new gate types
- `run_build_gate()` / `run_static_analysis_gate()`: Gate executor patterns to follow for new gates
- `error_router.py`: Already classifies Phase 4 gate failures to `deploy-agent` with correct gate_types sets
- `approve_gate` MCP tool: Already implemented in `factory_mcp_server.py` — reuse for MCP approval gate
- `validate_npm_packages()` pattern: httpx-based HTTP validation — same pattern for link integrity checker and security headers checker
- `PhaseExecutor` base class and self-registration pattern: Follow for Phase 3 executor

### Established Patterns
- Gate dispatch in `_run_gate_checks`: switch on `gate.type` → call gate executor function → return `GateResult`
- Content injection: Prior phase deliverables embedded in agent prompts (PRD text injected into build agent prompt)
- Quality self-assessment before gate submission (CONT-04)
- Sub-step tracking via `SubStepResult` list in `PhaseResult`
- Max turns cap per agent call (spec: 25, build: 50 — deploy TBD)

### Integration Points
- `contract_pipeline_runner.py _run_gate_checks()`: Add 6 new gate type dispatchers (currently handles artifact, tool_invocation, build, static_analysis)
- `tools/phase_executors/registry.py`: Register Phase 3 executor
- `agents/definitions.py`: Replace DEPLOY_AGENT placeholder prompt
- `factory.py`: Add `--company-name` and `--contact-email` CLI flags
- `config/settings.py`: Already has `DEFAULT_DEPLOY_TARGET = "vercel"` — may need Lighthouse threshold settings

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-ship*
*Context gathered: 2026-03-22*
