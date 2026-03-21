---
phase: 7
slug: ship-directory-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (439 tests currently passing) |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/test_phase_3_executor.py tests/test_contract_runner.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_phase_3_executor.py tests/test_contract_runner.py -x -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | SC-6 | integration | `uv run pytest tests/test_contract_runner.py -k "nextjs_dir" -x` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | DEPL-01 | unit | `uv run pytest tests/test_phase_3_executor.py -k "provision" -x` | ✅ extend | ⬜ pending |
| 07-01-03 | 01 | 1 | DEPL-01 | unit | `uv run pytest tests/test_phase_3_executor.py -k "deploy_preview" -x` | ✅ extend | ⬜ pending |
| 07-01-04 | 01 | 1 | LEGL-01, LEGL-02 | unit | `uv run pytest tests/test_phase_3_executor.py -k "generate_legal" -x` | ✅ extend | ⬜ pending |
| 07-01-05 | 01 | 1 | LEGL-03 | unit | `uv run pytest tests/test_phase_3_executor.py -k "gate_legal" -x` | ✅ extend | ⬜ pending |
| 07-01-06 | 01 | 1 | DEPL-02, DEPL-03 | unit | `uv run pytest tests/test_phase_3_executor.py tests/test_deployment_gate.py -x` | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_contract_runner.py::TestNextjsDirPropagationToPhase3` — integration test for `nextjs_dir` in `PhaseContext.extra` (SC-6)
- [ ] Additional assertions in existing `TestProvisionSubStep` and `TestDeployPreviewSubStep` tests to verify `cwd` kwarg matches `nextjs_dir`

*Existing test infrastructure covers all other requirements — only the integration test and cwd assertion additions are new.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
