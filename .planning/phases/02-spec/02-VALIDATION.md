---
phase: 2
slug: spec
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | SPEC-01 | unit | `uv run pytest tests/test_phase_1a_executor.py -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | SPEC-01 | unit | `uv run pytest tests/test_phase_1a_executor.py::test_go_no_go_field_parseable -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 0 | SPEC-02 | unit | `uv run pytest tests/test_phase_1b_executor.py::test_prd_has_moscow_labels -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 0 | SPEC-02 | unit | `uv run pytest tests/test_phase_1b_executor.py::test_component_name_cross_reference -x` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 0 | SPEC-03 | unit | `uv run pytest tests/test_phase_1a_executor.py::test_feasibility_evaluates_rendering_strategy -x` | ❌ W0 | ⬜ pending |
| 02-01-06 | 01 | 0 | SPEC-04 | unit | `uv run pytest tests/test_phase_spec_agent.py::test_no_ios_references_in_system_prompt -x` | ❌ W0 | ⬜ pending |
| 02-01-07 | 01 | 0 | SPEC-04 | integration | `uv run pytest tests/test_phase_spec_agent.py::test_smoke_sample_idea -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase_1a_executor.py` — stubs for SPEC-01, SPEC-03 (requires mocked claude_agent_sdk query)
- [ ] `tests/test_phase_1b_executor.py` — stubs for SPEC-02 (requires mocked claude_agent_sdk query)
- [ ] `tests/test_phase_spec_agent.py` — stubs for SPEC-04 (system prompt validation + smoke test)
- [ ] Mock fixture for `claude_agent_sdk.query` in `conftest.py` — returns canned `ResultMessage` for unit tests

*Existing infrastructure reused: `tmp_project_dir` and `sample_contract_path` fixtures from Phase 1*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Competitor names from real web search | SPEC-01 | Live API results vary | Run with real idea, verify output contains real company names |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
