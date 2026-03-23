# Phase 9: Deploy Abstraction - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a multi-cloud deployment abstraction layer with a common DeployProvider interface. Extract existing Vercel logic from Phase 3 executor into VercelProvider, add GCPProvider (Cloud Run), AWSProvider (stub), and LocalOnlyProvider. The deploy target becomes a selectable parameter. This phase does NOT change the MCP tool layer (Phase 11 wires providers to tools).

</domain>

<decisions>
## Implementation Decisions

### GCP Authentication Model
- GCP requires pre-authentication via `gcloud auth login` before running the pipeline — the provider does not handle auth flow
- GCPProvider checks for `gcloud` CLI presence and valid auth (`gcloud auth print-access-token`) before attempting deploy
- If auth is missing/expired, provider returns a clear error with the exact command to run: `gcloud auth login`
- GCP project ID is read from `gcloud config get-value project` — no separate config needed if user has a default project
- If no default project, error message includes `gcloud config set project <PROJECT_ID>`

### Local-Only Experience
- LocalOnlyProvider runs `npm run build` to verify the app builds successfully, then returns a synthetic result
- It does NOT start a dev server (that's Phase 10's waf_start_dev_server responsibility)
- The returned URL is `http://localhost:3000` as a placeholder — the actual dev server is started separately
- deployment_gate is skipped for local-only (no deployed URL to health-check)
- This allows users to iterate locally without cloud credentials, then switch to a cloud provider when ready

### Provider Selection Persistence
- Deploy target is set per-run via the `deploy_target` parameter (default: `"vercel"`)
- No project-level persistence — each pipeline run explicitly selects its target
- Supported values: `"vercel"`, `"gcp"`, `"aws"`, `"local"`
- `"aws"` raises NotImplementedError with guidance pointing to v3.0 timeline and manual CDK instructions
- Default of `"vercel"` maintains backward compatibility with v1.0 behavior

### Provider Interface Contract
- `DeployProvider` ABC with three required methods:
  - `deploy(project_dir: Path, env: dict) -> DeployResult` — execute deployment, return result
  - `get_url(deploy_result: DeployResult) -> str` — extract deployed URL from result
  - `verify(url: str) -> bool` — health check the deployed URL (delegates to existing deployment_gate)
- `DeployResult` dataclass with: `success: bool`, `url: str | None`, `provider: str`, `metadata: dict`
- VercelProvider additionally implements `provision()` and `promote()` for the preview→production workflow
- Providers are registered in a simple dict registry: `{"vercel": VercelProvider, "gcp": GCPProvider, ...}`

### Claude's Discretion
- Exact subprocess command construction for `gcloud run deploy`
- Error retry logic per provider (Vercel has its own patterns from Phase 3)
- How DeployResult metadata varies by provider
- Whether to extract a shared base class or keep providers fully independent

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. User trusts Claude to make reasonable defaults based on existing code patterns and requirements.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/phase_executors/phase_3_executor.py`: Contains full Vercel deployment logic (_provision, _deploy_preview, _deploy_production) — extract into VercelProvider
- `tools/gates/deployment_gate.py`: Already provider-agnostic HTTP health check — reuse as `verify()` implementation
- `web_app_factory/_keychain.py`: Credential retrieval (VERCEL_TOKEN, etc.) — providers use this for auth tokens
- `web_app_factory/_input_validator.py`: `safe_shell_arg()` for subprocess argument sanitization

### Established Patterns
- Phase 3 executor uses `subprocess.run()` with explicit arg lists (no shell=True) — all providers must follow this
- Gate results use `GateResult` dataclass pattern — DeployResult should follow similar structure
- PhaseContext.extra dict passes configuration between phases — deploy_target flows through this

### Integration Points
- Phase 3 executor will import and use DeployProvider instead of inline Vercel commands
- `contract_pipeline_runner.py` passes deploy_target in PhaseContext.extra
- Phase 11 (MCP Tool Layer) will read deploy_target from waf_generate_app parameter and pass to pipeline
- deployment_gate.py remains unchanged — providers call it internally for verify()

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-deploy-abstraction*
*Context gathered: 2026-03-23*
