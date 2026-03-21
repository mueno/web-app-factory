---
phase: 4
slug: ship
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (uv) |
| **Config file** | `[tool.pytest.ini_options]` in pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_phase_3_executor.py tests/test_lighthouse_gate.py tests/test_accessibility_gate.py tests/test_security_headers_gate.py tests/test_link_integrity_gate.py tests/test_deployment_gate.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | GATE-02 | unit | `uv run pytest tests/test_lighthouse_gate.py -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | GATE-07 | unit | `uv run pytest tests/test_accessibility_gate.py -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | GATE-03 | unit | `uv run pytest tests/test_security_headers_gate.py -x` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | GATE-04 | unit | `uv run pytest tests/test_link_integrity_gate.py -x` | ❌ W0 | ⬜ pending |
| 04-01-05 | 01 | 1 | DEPL-03 | unit | `uv run pytest tests/test_deployment_gate.py -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | DEPL-01, DEPL-02, DEPL-04 | unit | `uv run pytest tests/test_phase_3_executor.py -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 1 | LEGL-01, LEGL-02, LEGL-03 | unit | `uv run pytest tests/test_phase_3_executor.py -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | ALL | integration | `uv run pytest tests/test_contract_runner.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_lighthouse_gate.py` — Lighthouse gate (score parsing, threshold failure, subprocess timeout)
- [ ] `tests/test_accessibility_gate.py` — axe-core gate (critical violations filter, zero violations pass)
- [ ] `tests/test_security_headers_gate.py` — Security headers gate (missing header detection, all-present pass)
- [ ] `tests/test_link_integrity_gate.py` — Link integrity gate (404 detection, 200/301 pass)
- [ ] `tests/test_deployment_gate.py` — Deployment gate (HTTP 200 check, URL capture)
- [ ] `tests/test_phase_3_executor.py` — Phase 3 executor tests (sub-step flow, retry logic, legal generation, deploy)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Vercel preview deploy succeeds | DEPL-01 | Requires Vercel account + network | Run full pipeline against test app, verify preview URL accessible |
| Lighthouse scores on live URL | GATE-02 | Requires deployed app + headless Chrome | Run Lighthouse against deployed preview URL |
| MCP human approval flow | DEPL-04 | Requires MCP server running + human interaction | Start MCP server, trigger approval gate, approve via tool |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
