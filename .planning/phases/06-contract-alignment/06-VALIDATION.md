---
phase: 6
slug: contract-alignment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_quality_assessment.py tests/test_contract_schema.py tests/test_contract_runner.py tests/test_phase_3_executor.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_quality_assessment.py tests/test_contract_schema.py tests/test_contract_runner.py tests/test_phase_3_executor.py -x -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | CONT-04 | unit | `uv run pytest tests/test_quality_assessment.py::TestGenerateQualitySelfAssessment::test_phase_3_deliverable_paths_match_executor -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 0 | CONT-04 | unit | `uv run pytest tests/test_contract_runner.py -x -k "mcp_approval"` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 0 | CONT-04 | unit | `uv run pytest tests/test_contract_schema.py -x -q` | ✅ | ⬜ pending |
| 06-01-04 | 01 | 1 | CONT-04 | unit | `uv run pytest tests/test_quality_assessment.py tests/test_contract_schema.py tests/test_contract_runner.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_quality_assessment.py::TestGenerateQualitySelfAssessment::test_phase_3_deliverable_paths_match_executor` — asserts Phase 3 quality assessment contains `src/app/privacy/page.tsx`, `src/app/terms/page.tsx`, and `docs/pipeline/deployment.json` (not old paths)
- [ ] `tests/test_contract_runner.py::TestGateDispatch::test_phase3_no_mcp_approval_gate_in_yaml` — asserts that Phase 3 gates list in the YAML does NOT contain `mcp_approval` type
- [ ] `tests/test_contract_runner.py` — assert that `run_pipeline()` for Phase 3 does NOT invoke `run_mcp_approval_gate` via gate dispatch

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| *None* | — | — | — |

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
