# Milestones: Web App Factory

## v2.0 MCP Apps (Shipped: 2026-03-24)

**Phases completed:** 15 phases, 31 plans, 9 tasks

**Delivered:** Web-app-factory is now an installable MCP App — `claude mcp add web-app-factory -- uvx web-app-factory` takes a user from idea to deployed web app through natural conversation.

**Key accomplishments:**
- MCP App packaging with FastMCP server, `waf_` namespace, and OS keychain credential management
- 7-tool public API: generate, status, approve, list runs, check env, start/stop dev server
- Multi-cloud deployment via DeployProvider ABC (Vercel, GCP Cloud Run, AWS stub, LocalOnly)
- Local dev server with process lifecycle management, auto-port detection, and orphan cleanup
- Interactive gate approval — `mode='interactive'` pauses pipeline, `waf_approve_gate` consumes decisions via file-based polling
- Pipeline quality: Phase 2b three-sub-step decomposition with checkpoint resume, E2E Playwright form flow gate

**Stats:**
- 88 commits, 104 files changed, +18,180 / -954 lines
- Timeline: 2 days (2026-03-23 → 2026-03-24)
- Requirements: 27/27 complete
- Gap closures: Phase 14 (TOOL-03 interactive gate), Phase 15 (QUAL-02 playwright dependency)

---

## v1.0 — Core Pipeline (2026-03-21 → 2026-03-22)

**Goal:** A single command takes a web app idea from concept to deployed Next.js app on Vercel.

**What shipped:**
- 5-phase pipeline (idea validation → spec → scaffold → build → ship)
- 10 quality gates (build, static analysis, lighthouse, accessibility, security headers, link integrity, legal, deployment, mcp approval, quality assessment)
- Claude Agent SDK integration (spec-agent, build-agent, deploy-agent)
- State persistence, resumption, governance monitoring
- CLI entry point (`python factory.py "idea"`)
- 447 tests, 36/36 requirements satisfied

**Phases:** 7 (4 planned + 3 gap closures)
**Last phase number:** 7

**Post-v1.0 fixes (2026-03-23):**
- BILD-05/06 automated gate coverage
- LEGL-03 PRD path fix
- Quality self-assessment dedup
- FLOW-01 form-page parameter mismatch gate
