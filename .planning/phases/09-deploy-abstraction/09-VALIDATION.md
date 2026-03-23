---
phase: 09
slug: deploy-abstraction
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/test_deploy_provider.py tests/test_vercel_provider.py tests/test_gcp_provider.py tests/test_local_provider.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command (phase 9 tests only)
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | DEPL-01 | unit | `uv run pytest tests/test_deploy_provider.py -x -q` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | DEPL-02 | unit+integration | `uv run pytest tests/test_vercel_provider.py -x -q` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 2 | DEPL-03 | unit | `uv run pytest tests/test_gcp_provider.py -x -q` | ❌ W0 | ⬜ pending |
| 09-02-02 | 02 | 2 | DEPL-04 | unit | `uv run pytest tests/test_aws_provider.py -x -q` | ❌ W0 | ⬜ pending |
| 09-02-03 | 02 | 2 | DEPL-05 | unit | `uv run pytest tests/test_local_provider.py -x -q` | ❌ W0 | ⬜ pending |
| 09-03-01 | 03 | 3 | DEPL-06 | integration | `uv run pytest tests/test_deploy_integration.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_deploy_provider.py` — stubs for DEPL-01 (ABC interface tests)
- [ ] `tests/test_vercel_provider.py` — stubs for DEPL-02 (extracted Vercel tests)
- [ ] `tests/test_gcp_provider.py` — stubs for DEPL-03
- [ ] `tests/test_aws_provider.py` — stubs for DEPL-04
- [ ] `tests/test_local_provider.py` — stubs for DEPL-05
- [ ] `tests/test_deploy_integration.py` — stubs for DEPL-06

*Existing test infrastructure (pytest, conftest) covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GCP Cloud Run live deploy | DEPL-03 | Requires gcloud auth + billing | `gcloud run deploy --source . --region us-central1` then verify URL |
| Vercel end-to-end deploy | DEPL-02 | Requires VERCEL_TOKEN | Run pipeline with `deploy_target=vercel` against sample app |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
