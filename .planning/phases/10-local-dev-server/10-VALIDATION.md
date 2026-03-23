---
phase: 10
slug: local-dev-server
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/test_dev_server.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_dev_server.py -x -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-F1 | 01 | 1 | LDEV-01 | unit | `uv run pytest tests/test_dev_server.py::TestStartDevServer -x -q` | ❌ W0 | ⬜ pending |
| 10-01-F1 | 01 | 1 | LDEV-02 | unit | `uv run pytest tests/test_dev_server.py::TestStartDevServer::test_returns_detected_url -x -q` | ❌ W0 | ⬜ pending |
| 10-01-F1 | 01 | 1 | LDEV-03 | unit | `uv run pytest tests/test_dev_server.py::TestDuplicatePrevention -x -q` | ❌ W0 | ⬜ pending |
| 10-01-F1 | 01 | 1 | LDEV-04 | unit | `uv run pytest tests/test_dev_server.py::TestCleanup -x -q` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 2 | TOOL-06 | unit | `uv run pytest tests/test_mcp_server_tool_names.py -x -q` | ✅ | ⬜ pending |
| 10-02-02 | 02 | 2 | TOOL-07 | unit | `uv run pytest tests/test_mcp_server_tool_names.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_dev_server.py` — stubs for LDEV-01 through LDEV-04

*Existing pytest infrastructure covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dev server serves pages in browser | LDEV-01 | Requires visual confirmation | Start server, open URL in browser, verify page renders |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
