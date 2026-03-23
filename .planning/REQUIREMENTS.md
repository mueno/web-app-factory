# Requirements: Web App Factory

**Defined:** 2026-03-23
**Core Value:** A single command takes a web app idea from concept to deployed, production-quality web application

## v2.0 Requirements

Requirements for MCP Apps milestone. Each maps to roadmap phases.

### MCP Infrastructure

- [ ] **MCPI-01**: Server is installable via `claude mcp add web-app-factory -- uvx web-app-factory`
- [ ] **MCPI-02**: Server exposes tools with `waf_` namespace prefix via FastMCP
- [ ] **MCPI-03**: Pipeline runs in background thread pool (not blocking MCP event loop)
- [ ] **MCPI-04**: All subprocess calls are audited for shell injection (no `shell=True`, all args via `shlex.quote`)
- [ ] **MCPI-05**: Credentials (API keys, deploy tokens) stored in OS keychain, never in config files

### MCP Tools

- [ ] **TOOL-01**: `waf_generate_app` accepts idea, mode (auto/interactive), and deploy target; starts pipeline in background
- [ ] **TOOL-02**: `waf_get_status` returns current phase, progress percentage, and recent activity for a run
- [ ] **TOOL-03**: `waf_approve_gate` allows user to approve or reject a gate with feedback
- [ ] **TOOL-04**: `waf_list_runs` returns all pipeline runs with status, timestamps, and output URLs
- [ ] **TOOL-05**: `waf_check_env` detects Node.js, Python, CLI tools and reports missing/outdated with install instructions
- [ ] **TOOL-06**: `waf_start_dev_server` starts local Next.js dev server for a generated app and returns URL
- [ ] **TOOL-07**: `waf_stop_dev_server` stops a running dev server by run ID, with orphan cleanup

### Environment Setup

- [ ] **ENVS-01**: Auto-detect Node.js, npm, Python, Vercel CLI, gcloud CLI presence and version
- [ ] **ENVS-02**: Provide install commands for each missing tool (platform-aware: macOS/Linux)
- [ ] **ENVS-03**: Optionally execute install with user permission (not silently)

### Local Development

- [ ] **LDEV-01**: Start local dev server (`npm run dev`) with auto-detected free port
- [ ] **LDEV-02**: Return localhost URL to user when server is ready (port detection from stdout)
- [ ] **LDEV-03**: Track running servers by run ID; prevent duplicate starts
- [ ] **LDEV-04**: Clean up orphan dev server processes on MCP server shutdown

### Deploy Abstraction

- [ ] **DEPL-01**: DeployProvider abstract interface with deploy/get_url/verify methods
- [ ] **DEPL-02**: VercelProvider extracted from existing Phase 3 executor (backward compatible)
- [ ] **DEPL-03**: GCPProvider using `gcloud run deploy --source .` for Google Cloud Run
- [ ] **DEPL-04**: AWSProvider stub (interface only, raises NotImplementedError with guidance)
- [ ] **DEPL-05**: LocalOnlyProvider that skips cloud deploy and returns localhost URL
- [ ] **DEPL-06**: Deploy target selectable via `waf_generate_app` parameter

### Pipeline Quality (Backlog)

- [ ] **QUAL-01**: Phase 2b executes in incremental sub-steps (shared components → pages → integration) with checkpoint per step (BL-001)
- [ ] **QUAL-02**: E2E Playwright gate validates form submission → result page flows after build (BL-002)

## v3.0 Requirements

Deferred to future release.

### Cloud Providers

- **CLOUD-01**: AWS CDK full implementation (open-next-cdk) with Lambda/CloudFront
- **CLOUD-02**: Azure Static Web Apps support
- **CLOUD-03**: Cloudflare Pages support

### Advanced Features

- **ADV-01**: Database provisioning (Supabase/Neon + ORM)
- **ADV-02**: Auth scaffolding (Clerk/NextAuth + RBAC)
- **ADV-03**: Multi-framework support (Vue/Nuxt, Svelte)

## Out of Scope

| Feature | Reason |
|---------|--------|
| AWS CDK full implementation | MEDIUM confidence on open-next-cdk stability; stub in v2, full in v3 |
| MCP App UI (iframe approval cards) | Spec is v0.1, client behavior too variable; text-based approval in v2 |
| Custom domain / DNS management | Platform subdomain sufficient for generated apps |
| Backend database provisioning | Frontend + serverless API routes only for v2 |
| iOS/Swift code generation | Handled by ios-app-factory |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MCPI-01 | Phase 8 | Pending |
| MCPI-02 | Phase 8 | Pending |
| MCPI-03 | Phase 8 | Pending |
| MCPI-04 | Phase 8 | Pending |
| MCPI-05 | Phase 8 | Pending |
| TOOL-01 | Phase 11 | Pending |
| TOOL-02 | Phase 11 | Pending |
| TOOL-03 | Phase 11 | Pending |
| TOOL-04 | Phase 11 | Pending |
| TOOL-05 | Phase 12 | Pending |
| TOOL-06 | Phase 10 | Pending |
| TOOL-07 | Phase 10 | Pending |
| ENVS-01 | Phase 12 | Pending |
| ENVS-02 | Phase 12 | Pending |
| ENVS-03 | Phase 12 | Pending |
| LDEV-01 | Phase 10 | Pending |
| LDEV-02 | Phase 10 | Pending |
| LDEV-03 | Phase 10 | Pending |
| LDEV-04 | Phase 10 | Pending |
| DEPL-01 | Phase 9 | Pending |
| DEPL-02 | Phase 9 | Pending |
| DEPL-03 | Phase 9 | Pending |
| DEPL-04 | Phase 9 | Pending |
| DEPL-05 | Phase 9 | Pending |
| DEPL-06 | Phase 9 | Pending |
| QUAL-01 | Phase 13 | Pending |
| QUAL-02 | Phase 13 | Pending |

**Coverage:**
- v2.0 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-23*
*Last updated: 2026-03-23 — traceability validated against ROADMAP.md v2.0 phases 8-13*
