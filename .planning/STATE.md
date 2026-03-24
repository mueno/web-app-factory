---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Full Stack
status: planning
stopped_at: Completed 17-supabase-provisioning 17-01-PLAN.md
last_updated: "2026-03-24T22:33:58.365Z"
last_activity: 2026-03-24 — Phase 17 Plan 01 complete (SUPA-04, SUPA-05 satisfied)
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 6
  completed_plans: 4
  percent: 17
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** A single command takes a web app idea from concept to deployed, production-quality web application — now with full-stack backend, database, authentication, iOS backend support, and ChatGPT distribution
**Current focus:** Phase 17 — Supabase Provisioning

## Current Position

Phase: 17 — Supabase Provisioning
Plan: 1 of 4 complete
Status: In progress
Last activity: 2026-03-24 — Phase 17 Plan 01 complete (SUPA-04, SUPA-05 satisfied)

Progress: [██░░░░░░░░] 17% (v3.0 milestone — 1/6 phases complete)

## Phase Summary

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 16 | MCP Infrastructure Hardening | MCPH-01 to MCPH-04 (4) | ✓ Complete (2026-03-24) |
| 17 | Supabase Provisioning | SUPA-01 to SUPA-06, SECG-01, SECG-02 (8) | In progress (1/4 plans) |
| 18 | Backend API Generation | BGEN-01 to BGEN-07, SECG-03 (8) | Not started |
| 19 | Supabase Auth Scaffolding | AUTH-01 to AUTH-06 (6) | Not started |
| 20 | iOS Backend Generation | IOSB-01 to IOSB-07 (7) | Not started |
| 21 | OpenAI Apps Distribution | OAPI-01 to OAPI-05, SECG-04 (6) | Not started |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.

**v3.0 architecture decisions (from research):**
- Vercel + Supabase for backend — Supabase iOS SDK available, Vercel already primary deploy target, auth + DB + realtime in one platform
- OpenAI Apps full support — MCP is shared protocol; dual distribution to Claude + ChatGPT maximizes reach
- allnew-baas integration — Consolidate backend infrastructure under WAF; avoid per-app BaaS proliferation
- SECG requirements distributed to phases where concern is introduced (not a separate security phase)
- [Phase 16-mcp-infrastructure-hardening]: Impl layer pattern: _tool_impls.py holds all tool business logic; transports are thin wrappers delegating via return await impl_*()
- [Phase 16-mcp-infrastructure-hardening]: Tool safety classification: waf_get_status=readOnly, waf_stop_dev_server=destructive, waf_generate_app=openWorld; all others readOnly=false/destructive=false/openWorld=false
- [Phase 16]: HTTP server (openai_mcp_server.py) uses separate FastMCP instance; never cross-imports with stdio server; both import _tool_impls.py only
- [Phase 16]: Dual transport architecture confirmed — stdio + HTTP servers share _tool_impls.py, CI locks tool-name parity
- [Phase 17-supabase-provisioning]: NEXT_PUBLIC_SUPABASE_ANON_KEY allowlisted in GATE-06: Supabase anon key is intentionally public, blocking it was a false positive
- [Phase 17-supabase-provisioning]: SECG-01 regex uses two branches (SERVICE*ROLE and SVC*ROLE) to catch common SVC abbreviation variant
- [Phase 17-supabase-provisioning]: banto as priority-1 credential backend: banto unifies all credential management across Supabase, Vercel, and Anthropic keys
- [Phase 17-supabase-provisioning]: SecureVault=None stub when banto absent: enables patch() in tests without create=True workaround
- [Phase 17-supabase-provisioning]: check_env('supabase') as distinct deploy_target: keeps Supabase and Vercel credential checks orthogonal

### Pending Todos

- BL-003: Phase 1b data flow schema in screen-spec.json (carried from v2.0)
- Design decision needed (Phase 17 planning): create vs. reuse existing Supabase project on re-runs
- Design spike needed (Phase 20 planning): executor registry contract-type dispatch — Option A (separate registry per contract) vs. Option B
- Sandbox mode design needed (Phase 21 planning): ChatGPT App Store reviewer API key problem

### Blockers/Concerns

- OpenAI Apps SDK ChatGPT reviewer credential problem — no documented solution; sandbox mode design required before Phase 21 planning
- allnew-baas backward compatibility — Phase 20 templates must not break LyricsSnap (IOSB-06)
- Supabase free tier limits may affect generated app viability in production

### Research Flags (from SUMMARY.md)

- Phase 17 (Supabase Provisioning): MEDIUM confidence on credential lifecycle — create vs. reuse project on re-runs
- Phase 20 (iOS Backend): MEDIUM confidence on executor registry dispatch design
- Phase 21 (ChatGPT Submission): MEDIUM confidence — reviewer API key problem unresolved

## Session Continuity

Last session: 2026-03-24T22:33:58.363Z
Stopped at: Completed 17-supabase-provisioning 17-01-PLAN.md
Resume file: None
