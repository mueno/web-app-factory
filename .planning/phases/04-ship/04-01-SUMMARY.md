---
phase: 04-ship
plan: "01"
subsystem: deploy-infrastructure
tags: [deploy-agent, gates, cli, vercel, lighthouse, legal-docs, mcp-approval]
dependency_graph:
  requires: [03-03]
  provides: [deploy-agent-runner, deployment-gate, mcp-approval-gate, company-cli-flags]
  affects: [04-02, 04-03]
tech_stack:
  added: [httpx (deployment gate HTTP checks)]
  patterns: [asyncio.run() sync bridge, GateResult dataclass, direct function import for MCP approval]
key_files:
  created:
    - agents/definitions.py (DEPLOY_AGENT system prompt — was placeholder)
    - tools/phase_executors/deploy_agent_runner.py
    - tools/gates/deployment_gate.py
    - tools/gates/mcp_approval_gate.py
    - tests/test_deploy_agent_runner.py
    - tests/test_deployment_gate.py
    - tests/test_mcp_approval_gate.py
  modified:
    - factory.py (--company-name and --contact-email flags)
    - tools/contract_pipeline_runner.py (company_name and contact_email params in run_pipeline)
decisions:
  - "DEPLOY_AGENT system prompt capped at 1863 chars (under 2000 budget limit)"
  - "deploy_agent_runner uses max_turns=75 (vs build's 50) to accommodate legal gen + fix-retry cycles"
  - "deployment_gate uses httpx.get with follow_redirects=True and timeout=30 (not subprocess)"
  - "mcp_approval_gate calls approve_gate function directly via asyncio.run() — not MCP transport"
  - "APPROVED: prefix from approve_gate -> passed=True; any other response -> passed=False"
  - "company_name and contact_email forwarded into PhaseContext.extra dict for Phase 3 executor access"
metrics:
  duration_minutes: 5
  completed_date: "2026-03-21"
  tasks_completed: 3
  files_changed: 9
---

# Phase 4 Plan 01: Deploy Infrastructure Summary

**One-liner:** Deploy agent with Vercel/Lighthouse/APPI expertise, HTTP deployment gate, file-polling MCP approval gate, and company info CLI passthrough via PhaseContext.extra.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | DEPLOY_AGENT system prompt + deploy-agent runner | 4d00ebc | agents/definitions.py, tools/phase_executors/deploy_agent_runner.py, tests/test_deploy_agent_runner.py |
| 2 | Deployment gate + MCP approval gate | 157a629 | tools/gates/deployment_gate.py, tools/gates/mcp_approval_gate.py, tests/test_deployment_gate.py, tests/test_mcp_approval_gate.py |
| 3 | CLI flags for company info and pipeline passthrough | 1c197f2 | factory.py, tools/contract_pipeline_runner.py |

## What Was Built

### Task 1: DEPLOY_AGENT System Prompt + Deploy-Agent Runner

Replaced the placeholder `DEPLOY_AGENT.system_prompt` ("System prompt to be defined in Phase 4") with a real 1,863-character prompt covering:
- Vercel CLI usage (`vercel link --yes`, preview and production deploys)
- Lighthouse performance/a11y/SEO gating and axe-core accessibility remediation
- Japanese law (APPI) as primary jurisdiction for legal docs, with GDPR/CCPA mentions
- Explicit no-placeholder instruction (YOUR_APP_NAME, YOUR_COMPANY, etc. forbidden)
- Gate failure remediation loop (read report → fix → rebuild → redeploy → re-gate, max 3x)

Created `deploy_agent_runner.py` by cloning `build_agent_runner.py` with:
- `max_turns=75` (vs build's 50 — deploy phase has more work: legal gen + retry cycles)
- Same `allowed_tools=["Read", "Write", "Bash"]` and `cwd=project_dir` sandbox pattern
- Identical `asyncio.run()` bridge for sync/async interface

17 tests cover all behaviors.

### Task 2: Deployment Gate + MCP Approval Gate

**deployment_gate.py:** HTTP health check using `httpx.get(url, timeout=30, follow_redirects=True)`. HTTP 200 → passed=True; any other status code or `httpx.RequestError` → passed=False with descriptive issue. `gate_type="deployment"`, default `phase_id="3"`.

**mcp_approval_gate.py:** Calls `approve_gate` from `factory_mcp_server` directly (function import, not MCP transport — per RESEARCH.md Open Question 3). Uses `asyncio.run()` to bridge the async coroutine. Response parsing: `"APPROVED:"` prefix → passed=True; any other response (REJECTED, FEEDBACK, timeout) or exception → passed=False with issue.

35 tests cover pass/fail/exception paths for both gates.

### Task 3: CLI Flags for Company Info and Pipeline Passthrough

Added `--company-name NAME` and `--contact-email EMAIL` flags to `factory.py` `parse_args()`. Both default to `None`.

`run_pipeline()` in `contract_pipeline_runner.py` now accepts `company_name: Optional[str] = None` and `contact_email: Optional[str] = None`. Both are forwarded into `PhaseContext.extra` dict:
```python
extra={"company_name": company_name, "contact_email": contact_email}
```

Phase 3 executor can read `ctx.extra["company_name"]` and `ctx.extra["contact_email"]` to populate legal document content without hardcoding placeholder strings.

All 32 existing CLI and pipeline runner tests continue to pass.

## Deviations from Plan

None — plan executed exactly as written.

Pre-existing failures in `tests/test_link_integrity_gate.py` (14 tests) exist in the codebase before this plan and are out of scope. Deferred per deviation rules.

## Verification

- `uv run pytest tests/test_deploy_agent_runner.py tests/test_deployment_gate.py tests/test_mcp_approval_gate.py tests/test_contract_runner.py tests/test_factory_cli.py -x -q` → 84 passed
- `python factory.py --help` → shows --company-name and --contact-email
- `agents/definitions.py` DEPLOY_AGENT.system_prompt is NOT the placeholder string
- Full suite (excluding pre-existing link_integrity failures): 364 passed

## Self-Check: PASSED

All 7 created/modified files confirmed present on disk.
All 3 task commits verified in git log: 4d00ebc, 157a629, 1c197f2.
