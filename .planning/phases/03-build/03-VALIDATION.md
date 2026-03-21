---
phase: 3
slug: build
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_phase_2a_executor.py tests/test_phase_2b_executor.py tests/test_build_gate.py tests/test_static_analysis_gate.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | BILD-01 | unit | `uv run pytest tests/test_phase_2a_executor.py::test_scaffold_subprocess_flags -x` | created in Plan 01 | ⬜ pending |
| 03-01-02 | 01 | 1 | BILD-01 | unit | `uv run pytest tests/test_phase_2a_executor.py::test_self_registration -x` | created in Plan 01 | ⬜ pending |
| 03-02-01 | 02 | 2 | GATE-01 | unit | `uv run pytest tests/test_build_gate.py::test_build_gate_pass_fail -x` | created in Plan 02 | ⬜ pending |
| 03-02-02 | 02 | 2 | GATE-05 | unit | `uv run pytest tests/test_static_analysis_gate.py::test_use_client_in_layout -x` | created in Plan 02 | ⬜ pending |
| 03-02-03 | 02 | 2 | GATE-05 | unit | `uv run pytest tests/test_static_analysis_gate.py::test_use_client_in_error_is_ok -x` | created in Plan 02 | ⬜ pending |
| 03-02-04 | 02 | 2 | GATE-06 | unit | `uv run pytest tests/test_static_analysis_gate.py::test_next_public_secret -x` | created in Plan 02 | ⬜ pending |
| 03-03-01 | 03 | 3 | BILD-02 | unit | `uv run pytest tests/test_phase_2b_executor.py::test_agent_called -x` | created in Plan 03 | ⬜ pending |
| 03-03-02 | 03 | 3 | BILD-02 | unit | `uv run pytest tests/test_phase_2b_executor.py::test_prompt_contains_prd -x` | created in Plan 03 | ⬜ pending |
| 03-03-03 | 03 | 3 | BILD-07 | unit | `uv run pytest tests/test_phase_2b_executor.py::test_npm_validation -x` | created in Plan 03 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `mock_agent_query` fixture in `tests/conftest.py` — already exists from Phase 2
- [ ] `mock_subprocess` fixture — shared fixture for subprocess.run mocking (created in Plan 01 or 02)

*Existing infrastructure reused: `tmp_project_dir`, `sample_contract_path`, `mock_agent_query` from Phase 2*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Generated app renders correctly in browser | BILD-05 | Visual layout validation | Run `npm run dev`, open in browser, resize for mobile/tablet/desktop |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
