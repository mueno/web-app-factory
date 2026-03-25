---
phase: 19
slug: supabase-auth-scaffolding
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| 19-01-01 | 01 | 1 | AUTH-01 | unit | `uv run pytest tests/test_supabase_templates.py -q` | ✅ (Phase 17) | ⬜ pending |
| 19-01-02 | 01 | 1 | AUTH-02 | unit | `uv run pytest tests/test_auth_middleware_template.py -q` | ❌ W0 | ⬜ pending |
| 19-01-03 | 01 | 1 | AUTH-03 | unit | `uv run pytest tests/test_auth_page_templates.py -q` | ❌ W0 | ⬜ pending |
| 19-01-04 | 01 | 1 | AUTH-04 | unit | `uv run pytest tests/test_auth_page_templates.py -q` | ❌ W0 | ⬜ pending |
| 19-02-01 | 02 | 1 | AUTH-05 | unit | `uv run pytest tests/test_supabase_provisioner.py tests/test_env_checker.py -q` | Partial | ⬜ pending |
| 19-03-01 | 03 | 2 | AUTH-06 | unit | `uv run pytest tests/test_agent_definitions.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_auth_middleware_template.py` — stubs for AUTH-02: middleware template content validation
- [ ] `tests/test_auth_page_templates.py` — stubs for AUTH-03, AUTH-04: login/signup/signout/callback template validation
- [ ] `tests/test_agent_definitions.py` — stubs for AUTH-06: SPEC_AGENT + BUILD_AGENT prompt content checks

*Extend existing: `tests/test_supabase_provisioner.py` for new `configure_oauth_providers()` method; `tests/test_env_checker.py` for OAuth credential checks*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OAuth redirect flow works end-to-end | AUTH-05 | Requires real Google/Apple OAuth credentials | Configure test credentials in Supabase dashboard, navigate to /auth/login, click Google/Apple button, verify redirect and callback |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
