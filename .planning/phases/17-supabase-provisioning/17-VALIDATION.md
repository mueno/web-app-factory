---
phase: 17
slug: supabase-provisioning
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --timeout=10`
- **After every plan wave:** Run `python -m pytest tests/ -q --timeout=30`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | SUPA-05 | unit | `pytest tests/test_keychain.py -q` | ✅ | ⬜ pending |
| 17-01-02 | 01 | 1 | SUPA-04 | unit | `pytest tests/test_env_checker.py -q` | ✅ | ⬜ pending |
| 17-02-01 | 02 | 2 | SUPA-01 | unit | `pytest tests/test_supabase_provisioner.py -q` | ❌ W0 | ⬜ pending |
| 17-02-02 | 02 | 2 | SUPA-02 | unit | `pytest tests/test_migration_generator.py -q` | ❌ W0 | ⬜ pending |
| 17-02-03 | 02 | 2 | SUPA-03 | unit | `pytest tests/test_supabase_gate.py -q` | ❌ W0 | ⬜ pending |
| 17-02-04 | 02 | 2 | SUPA-06 | unit | `pytest tests/test_supabase_client_gen.py -q` | ❌ W0 | ⬜ pending |
| 17-02-05 | 02 | 2 | SECG-01 | unit | `pytest tests/test_static_analysis_gate.py -q` | ✅ | ⬜ pending |
| 17-02-06 | 02 | 2 | SECG-02 | unit | `pytest tests/test_supabase_gate.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_supabase_provisioner.py` — stubs for SUPA-01 (project creation, health polling)
- [ ] `tests/test_migration_generator.py` — stubs for SUPA-02 (RLS migration SQL generation)
- [ ] `tests/test_supabase_gate.py` — stubs for SUPA-03, SECG-02 (gate verification)
- [ ] `tests/test_supabase_client_gen.py` — stubs for SUPA-06 (dual client template generation)

*Existing test files cover: test_keychain.py (SUPA-05 banto integration), test_env_checker.py (SUPA-04), test_static_analysis_gate.py (SECG-01)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Supabase project creation | SUPA-01 | Requires real Supabase account + API token | Create test project, verify ACTIVE_HEALTHY in dashboard |
| Vercel env injection | SUPA-03 | Requires Vercel project link | Verify env vars appear in Vercel dashboard |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
