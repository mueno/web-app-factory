---
phase: 2
slug: spec
status: draft
nyquist_compliant: true
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
| 02-01-01 | 01 | 1 | SPEC-04 | unit | `uv run pytest tests/test_phase_spec_agent.py -x` | created in Plan 01 | ⬜ pending |
| 02-02-01 | 02 | 2 | SPEC-01 | unit | `uv run pytest tests/test_phase_1a_executor.py -x` | created in Plan 02 | ⬜ pending |
| 02-02-02 | 02 | 2 | SPEC-03 | unit | `uv run pytest tests/test_phase_1a_executor.py::test_feasibility_evaluates_rendering_strategy -x` | created in Plan 02 | ⬜ pending |
| 02-02-03 | 02 | 2 | SPEC-01 | unit | `uv run pytest tests/test_phase_1a_executor.py::test_go_no_go_field_parseable -x` | created in Plan 02 | ⬜ pending |
| 02-03-01 | 03 | 3 | SPEC-02 | unit | `uv run pytest tests/test_phase_1b_executor.py::test_prd_has_moscow_labels -x` | created in Plan 03 | ⬜ pending |
| 02-03-02 | 03 | 3 | SPEC-02 | unit | `uv run pytest tests/test_phase_1b_executor.py::test_component_name_cross_reference -x` | created in Plan 03 | ⬜ pending |
| 02-03-03 | 03 | 3 | SPEC-02 | unit | `uv run pytest tests/test_phase_1b_executor.py::test_phase_1a_context_injected_in_prompt -x` | created in Plan 03 | ⬜ pending |
| 02-01-02 | 01 | 1 | SPEC-04 | integration | `uv run pytest tests/test_phase_spec_agent.py::test_smoke_sample_idea -x` | created in Plan 01 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `mock_agent_query` fixture in `tests/conftest.py` — patches `claude_agent_sdk.query` with canned `ResultMessage` for unit tests (created in Plan 01, Task 1)

*Wave 0 scope is limited to the mock fixture. SPEC-01/03 test files are created inside Plan 02 (TDD). SPEC-02 test files are created inside Plan 03 (TDD). SPEC-04 test files are created inside Plan 01 (TDD).*

*Existing infrastructure reused: `tmp_project_dir` and `sample_contract_path` fixtures from Phase 1*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Competitor names from real web search | SPEC-01 | Live API results vary | Run with real idea, verify output contains real company names |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
