---
phase: 17
slug: supabase-provisioning
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-25
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `cd /Users/masa/Development/web-app-factory && python -m pytest tests/ -x -q --timeout=10` |
| **Full suite command** | `cd /Users/masa/Development/web-app-factory && python -m pytest tests/ -q --timeout=30` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --timeout=10`
- **After every plan wave:** Run `python -m pytest tests/ -q --timeout=30`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## TDD Strategy

All plans use **TDD-inline** (`tdd="true"` on tasks). Each task writes failing tests first (RED), then implements production code (GREEN). No separate Wave 0 stub plan is needed — test creation is embedded in each task's TDD cycle.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 17-01-01 | 01 | 1 | SUPA-05 | unit (TDD) | `pytest tests/test_keychain.py -q` | pending |
| 17-01-02 | 01 | 1 | SUPA-04 | unit (TDD) | `pytest tests/test_env_checker.py -q` | pending |
| 17-02-01 | 02 | 1 | SUPA-06 | unit (TDD) | `pytest tests/test_supabase_templates.py -q` | pending |
| 17-02-02 | 02 | 1 | SECG-01 | unit (TDD) | `pytest tests/test_static_analysis_gate.py -q` | pending |
| 17-03-01 | 03 | 2 | SUPA-01, SUPA-02 | unit (TDD) | `pytest tests/test_supabase_provisioner.py tests/test_supabase_migration.py -q` | pending |
| 17-03-02 | 03 | 2 | SUPA-03, SECG-02 | unit (TDD) | `pytest tests/test_supabase_gate.py -q` | pending |
| 17-04-01 | 04 | 3 | SUPA-06 | unit (TDD) | `pytest tests/test_supabase_template_renderer.py -q` | pending |
| 17-04-02 | 04 | 3 | SUPA-01, SUPA-03 | integration (TDD) | `pytest tests/test_phase_3_supabase.py -q` | pending |

*Status: pending | green | red | flaky*

---

## Requirement Coverage

| Req ID | Covered By (Task) | Test File |
|--------|-------------------|-----------|
| SUPA-01 | 17-03-01, 17-04-02 | test_supabase_provisioner.py, test_phase_3_supabase.py |
| SUPA-02 | 17-03-01 | test_supabase_migration.py |
| SUPA-03 | 17-03-02, 17-04-02 | test_supabase_gate.py, test_phase_3_supabase.py |
| SUPA-04 | 17-01-02 | test_env_checker.py |
| SUPA-05 | 17-01-01 | test_keychain.py |
| SUPA-06 | 17-02-01, 17-04-01 | test_supabase_templates.py, test_supabase_template_renderer.py |
| SECG-01 | 17-02-02 | test_static_analysis_gate.py |
| SECG-02 | 17-03-02 | test_supabase_gate.py |

All 8 requirements have automated test coverage.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Supabase project creation | SUPA-01 | Requires real Supabase account + API token | Create test project, verify ACTIVE_HEALTHY in dashboard |
| Vercel env injection (live) | SUPA-03 | Requires Vercel project link | Verify env vars appear in Vercel dashboard |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] TDD-inline covers all test creation (no Wave 0 needed)
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
