---
phase: 19
slug: supabase-auth-scaffolding
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-25
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `cd /Users/masa/Development/web-app-factory && uv run pytest tests/test_supabase_templates.py tests/test_supabase_provisioner.py -q` |
| **Full suite command** | `cd /Users/masa/Development/web-app-factory && uv run pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_supabase_templates.py tests/test_supabase_provisioner.py -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | AUTH-01 | unit | `uv run pytest tests/test_supabase_templates.py -q` | yes (Phase 17) | pending |
| 19-01-02 | 01 | 1 | AUTH-02 | unit | `uv run pytest tests/test_auth_templates.py -q` | yes (Plan 01 creates) | pending |
| 19-01-03 | 01 | 1 | AUTH-03 | unit | `uv run pytest tests/test_auth_templates.py -q` | yes (Plan 01 creates) | pending |
| 19-01-04 | 01 | 1 | AUTH-04 | unit | `uv run pytest tests/test_auth_templates.py -q` | yes (Plan 01 creates) | pending |
| 19-02-01 | 02 | 1 | AUTH-05 | unit | `uv run pytest tests/test_supabase_provisioner.py tests/test_env_checker.py -q` | Partial | pending |
| 19-03-01 | 03 | 2 | AUTH-06 | unit | `uv run pytest tests/test_phase_2b_executor.py tests/test_phase_3_supabase.py -q` | yes (Plan 03 creates) | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

All Wave 0 test files are created by their respective plans during TDD (tests-first):

- `tests/test_auth_templates.py` — created by Plan 01: middleware + login/signup/signout/callback template content validation (AUTH-02, AUTH-03, AUTH-04)
- `tests/test_phase_2b_executor.py` — created by Plan 03 Task 2: generate_auth_pages sub-step tests
- `tests/test_phase_3_supabase.py` — extended by Plan 03 Task 3: supabase_oauth_config tests

*Extend existing: `tests/test_supabase_provisioner.py` for new `configure_oauth_providers()` method; `tests/test_env_checker.py` for OAuth credential checks*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OAuth redirect flow works end-to-end | AUTH-05 | Requires real Google/Apple OAuth credentials | Configure test credentials in Supabase dashboard, navigate to /auth/login, click Google/Apple button, verify redirect and callback |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready
