---
phase: 18-backend-api-generation
plan: "01"
subsystem: backend-quality-gates
tags: [gate, zod, validation, sql-injection, templates, tdd]
dependency_graph:
  requires:
    - tools/gates/gate_result.py
    - tools/gates/static_analysis_gate.py  # pattern reference
  provides:
    - tools/gates/backend_spec_gate.py
    - web_app_factory/templates/backend/
  affects:
    - Phase 18 plans 02 and 03 (gate will be invoked in pipeline)
tech_stack:
  added: []
  patterns:
    - GateResult regex-scan gate (same as static_analysis_gate.py)
    - TDD (RED → GREEN flow)
key_files:
  created:
    - tools/gates/backend_spec_gate.py
    - tests/test_backend_spec_gate.py
    - web_app_factory/templates/backend/error-helpers.ts.tmpl
    - web_app_factory/templates/backend/health-route.ts.tmpl
    - web_app_factory/templates/backend/with-validation.ts.tmpl
  modified: []
decisions:
  - "Health endpoint excluded from Zod validation: health route has no user inputs, so Zod import requirement is skipped for src/app/api/health/route.ts only"
  - "Graceful skip for apps without backend: if src/app/api/ does not exist, gate returns passed=True — frontend-only apps are not penalized"
  - "All issues blocking (per locked user decision from CONTEXT.md): no advisories ever emitted by backend_spec_gate"
metrics:
  duration_minutes: 10
  completed_date: "2026-03-25"
  tasks_completed: 1
  tasks_total: 1
  files_created: 5
  files_modified: 0
---

# Phase 18 Plan 01: BackendSpecValidator Gate and Templates Summary

**One-liner:** BackendSpecValidator gate with regex scans for missing Zod, SQL injection, hardcoded secrets, and missing health endpoint — plus three TypeScript backend templates for generated apps.

## What Was Built

### `tools/gates/backend_spec_gate.py`

`run_backend_spec_gate(project_dir, *, phase_id="2b") -> GateResult` scans all `route.ts` and `route.js` files under `src/app/api/` and enforces four rules:

1. **BGEN-03/06: Zod validation required** — every route (except health) must have `from "zod"` import AND `.safeParse(` call
2. **BGEN-05: Health endpoint required** — `src/app/api/health/route.ts` must exist
3. **BGEN-06: No hardcoded secrets** — `apiKey/secret/token/password = "20+ char value"` pattern blocked
4. **SECG-03: No SQL injection** — string concatenation or template literals in `supabase.rpc()`/`supabase.sql()` blocked

Graceful skip: returns `passed=True` when `src/app/api/` directory does not exist (frontend-only apps).

All issues go to `GateResult.issues` (blocking) — `advisories` is always empty, per locked user decision.

### `web_app_factory/templates/backend/`

Three `.tmpl` files the build agent will reference when generating API routes:

- **`error-helpers.ts.tmpl`** — `apiError(message, code, status)` enforces `{ error: string, code: string }` shape (BGEN-04)
- **`health-route.ts.tmpl`** — `GET /api/health` returning `{ ok, service, timestamp }` (BGEN-05)
- **`with-validation.ts.tmpl`** — `withValidation<T>(schema, request, handler)` HOF demonstrating Zod safeParse pattern

### `tests/test_backend_spec_gate.py`

28 tests across 9 test classes covering all gate behaviors including: missing Zod import, missing safeParse, template literal SQL injection, string concat SQL injection, safe Supabase queries, hardcoded API keys, env var references, missing health endpoint, present health endpoint, all-issues-blocking verification, graceful skip scenarios, health route Zod exclusion, and template file content checks.

## Decisions Made

1. **Health route excluded from Zod check**: The health endpoint (`src/app/api/health/route.ts`) has no user inputs — requiring Zod there would be a false positive. The gate checks the path and skips Zod validation for exactly that file.

2. **Graceful skip when no backend**: If `src/app/api/` does not exist, the gate returns `passed=True`. Frontend-only generated apps should not fail because they lack an API layer.

3. **All issues blocking** (pre-existing locked decision from CONTEXT.md): The gate never emits `advisories`. Every detected issue is hard-blocking. This matches the user's explicit constraint: "advisory は使わない."

## Deviations from Plan

None — plan executed exactly as written.

## Verification

```
28 passed in 0.06s (tests/test_backend_spec_gate.py)
Full suite: 893 passed, 4 pre-existing failures (unrelated to this plan)
Template files: all 3 present and contain expected patterns
```

## Self-Check: PASSED

Files verified:
- `tools/gates/backend_spec_gate.py` — FOUND
- `tests/test_backend_spec_gate.py` — FOUND
- `web_app_factory/templates/backend/error-helpers.ts.tmpl` — FOUND
- `web_app_factory/templates/backend/health-route.ts.tmpl` — FOUND
- `web_app_factory/templates/backend/with-validation.ts.tmpl` — FOUND

Commit verified: `256fab4` — feat(18-01): add BackendSpecValidator gate and backend TypeScript templates
