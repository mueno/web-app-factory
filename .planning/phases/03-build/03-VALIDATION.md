---
phase: 3
slug: build
status: draft
nyquist_compliant: true
wave_0_complete: true
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
| **Quick run command** | `uv run pytest tests/test_phase_2a_executor.py tests/test_phase_2b_executor.py tests/test_build_gate.py tests/test_static_analysis_gate.py tests/test_contract_runner.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~10 seconds |

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
| 03-01-01 | 01 | 1 | BILD-01 | unit | `uv run pytest tests/test_phase_2a_executor.py -x -k "build_agent or system_prompt"` | created in Plan 01 | pending |
| 03-01-01b | 01 | 1 | BILD-03,BILD-04 | unit | `uv run pytest tests/test_phase_2a_executor.py -x -k "typescript_strict or implicit_any or typed_props"` | created in Plan 01 | pending |
| 03-01-02 | 01 | 1 | BILD-01 | unit | `uv run pytest tests/test_phase_2a_executor.py -x -k "self_registration"` | created in Plan 01 | pending |
| 03-02-01 | 02 | 1 | GATE-01 | unit | `uv run pytest tests/test_build_gate.py -x -q` | created in Plan 02 | pending |
| 03-02-02 | 02 | 1 | GATE-05 | unit | `uv run pytest tests/test_static_analysis_gate.py -x -k "use_client_in_layout"` | created in Plan 02 | pending |
| 03-02-03 | 02 | 1 | GATE-05 | unit | `uv run pytest tests/test_static_analysis_gate.py -x -k "use_client_in_error"` | created in Plan 02 | pending |
| 03-02-04 | 02 | 1 | GATE-06 | unit | `uv run pytest tests/test_static_analysis_gate.py -x -k "next_public_secret"` | created in Plan 02 | pending |
| 03-03-01 | 03 | 2 | BILD-02 | unit | `uv run pytest tests/test_phase_2b_executor.py -x -k "agent_called or prompt_contains"` | created in Plan 03 | pending |
| 03-03-01b | 03 | 2 | BILD-06 | unit | `uv run pytest tests/test_phase_2b_executor.py -x -k "error_tsx"` | created in Plan 03 | pending |
| 03-03-02 | 03 | 2 | BILD-07 | unit | `uv run pytest tests/test_phase_2b_executor.py -x -k "npm_validation"` | created in Plan 03 | pending |
| 03-03-03 | 03 | 2 | GATE-01 | unit | `uv run pytest tests/test_contract_runner.py -x -k "gate_dispatch_build"` | created in Plan 03 | pending |
| 03-03-04 | 03 | 2 | GATE-05,GATE-06 | unit | `uv run pytest tests/test_contract_runner.py -x -k "gate_dispatch_static"` | created in Plan 03 | pending |
| 03-03-05 | 03 | 2 | BILD-02 | unit | `uv run pytest tests/test_contract_runner.py -x -k "executor_registration_2"` | created in Plan 03 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `mock_agent_query` fixture in `tests/conftest.py` — already exists from Phase 2
- [x] `mock_build_agent_query` fixture in `tests/conftest.py` — created in Plan 01 Task 1
- [x] `mock_subprocess` fixture in `tests/conftest.py` — created in Plan 03 Task 2 (patches `subprocess.run` with default `returncode=0`)
- [x] `tmp_project_dir` fixture in `tests/conftest.py` — already exists from Phase 2
- [x] `sample_contract_path` fixture in `tests/conftest.py` — already exists from Phase 2

*All Wave 0 fixtures are either existing or explicitly created in plan tasks.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Generated app renders correctly in browser | BILD-05 | Visual layout validation | Run `npm run dev`, open in browser, resize for mobile/tablet/desktop |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (revision pass)
