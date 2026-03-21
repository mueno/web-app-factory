---
phase: 1
slug: infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ -q --tb=short` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -q --tb=short`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | PIPE-06 | unit | `uv run pytest tests/test_factory_cli.py -q` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | PIPE-01 | unit | `uv run pytest tests/test_contract_runner.py -q` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | PIPE-02 | unit | `uv run pytest tests/test_pipeline_state.py -q` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 1 | PIPE-03 | unit | `uv run pytest tests/test_pipeline_state.py -q` | ❌ W0 | ⬜ pending |
| 01-01-05 | 01 | 1 | PIPE-04 | integration | `uv run pytest tests/test_mcp_server.py -q` | ❌ W0 | ⬜ pending |
| 01-01-06 | 01 | 1 | PIPE-05 | unit | `uv run pytest tests/test_governance.py -q` | ❌ W0 | ⬜ pending |
| 01-01-07 | 01 | 1 | PIPE-07 | unit | `uv run pytest tests/test_preflight.py -q` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | CONT-01 | unit | `uv run pytest tests/test_contract.py -q` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 1 | CONT-02 | unit | `uv run pytest tests/test_contract.py -q` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 1 | CONT-03 | unit | `uv run pytest tests/test_contract.py -q` | ❌ W0 | ⬜ pending |
| 01-02-04 | 02 | 1 | CONT-04 | unit | `uv run pytest tests/test_quality_assessment.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures (temp dirs, mock state)
- [ ] `tests/test_factory_cli.py` — CLI argument parsing and dispatch
- [ ] `tests/test_contract_runner.py` — YAML contract loading and phase ordering
- [ ] `tests/test_pipeline_state.py` — state.json persistence and resume
- [ ] `tests/test_mcp_server.py` — MCP tool integration (phase_reporter → state.json)
- [ ] `tests/test_governance.py` — phase ordering enforcement and bypass detection
- [ ] `tests/test_preflight.py` — startup environment checks
- [ ] `tests/test_contract.py` — YAML contract schema validation and quality criteria
- [ ] `tests/test_quality_assessment.py` — self-assessment generation

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MCP approval gate blocks until human approves | PIPE-04 | Requires interactive MCP client | Start pipeline, wait for approval gate, approve via MCP client, verify pipeline continues |
| Pipeline resumes after kill -9 | PIPE-03 | Requires process interruption | Run pipeline, kill process mid-phase, re-run, verify resume from last phase |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
