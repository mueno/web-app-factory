---
phase: 5
slug: build-pipeline-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_phase_2b_executor.py tests/test_contract_runner.py tests/test_governance_monitor.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_phase_2b_executor.py tests/test_contract_runner.py tests/test_governance_monitor.py -x -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | BILD-02 | unit | `uv run pytest tests/test_phase_2b_executor.py::TestPhase2bBuildExecutorSuccess::test_execute_passes_project_dir_to_run_build_agent -x` | ✅ (needs update) | ⬜ pending |
| 05-01-02 | 01 | 0 | BILD-03, BILD-04 | unit | `uv run pytest tests/test_contract_runner.py -x -k build_gate_receives_nextjs_dir` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 0 | PIPE-05 | unit | `uv run pytest tests/test_contract_runner.py -x -k governance` | ❌ W0 | ⬜ pending |
| 05-01-04 | 01 | 1 | BILD-02 | unit | `uv run pytest tests/test_phase_2b_executor.py -x -q` | ✅ | ⬜ pending |
| 05-01-05 | 01 | 1 | BILD-03, BILD-04 | unit | `uv run pytest tests/test_contract_runner.py -x -k gate` | ✅ | ⬜ pending |
| 05-01-06 | 01 | 1 | PIPE-05 | unit | `uv run pytest tests/test_contract_runner.py -x -k governance` | ✅ | ⬜ pending |
| 05-01-07 | 01 | 2 | ALL | integration | `uv run pytest -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase_2b_executor.py` — update `test_execute_passes_project_dir_to_run_build_agent` to assert `nextjs_dir` not `ctx.project_dir`
- [ ] `tests/test_contract_runner.py` — add `test_build_gate_receives_nextjs_dir` asserting `run_build_gate` is called with Next.js project dir
- [ ] `tests/test_contract_runner.py` — add `test_governance_monitor_instantiated_in_run_pipeline` asserting GovernanceMonitor is used

*Existing infrastructure covers framework/fixture needs.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
