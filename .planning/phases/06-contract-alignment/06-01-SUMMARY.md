---
phase: 06-contract-alignment
plan: "01"
subsystem: contract-alignment
tags: [contract, yaml, quality-assessment, tdd, regression-tests]
dependency_graph:
  requires: []
  provides: [CONT-04]
  affects: [tools/quality_self_assessment.py, tools/contract_pipeline_runner.py]
tech_stack:
  added: []
  patterns: [TDD Red-Green, contract alignment, regression guard]
key_files:
  created: []
  modified:
    - contracts/pipeline-contract.web.v1.yaml
    - tests/test_quality_assessment.py
    - tests/test_contract_runner.py
decisions:
  - "YAML deliverable paths corrected to match executor output; quality_self_assessment.py reads from YAML so fix flows automatically without touching Python code"
  - "mcp_approval gate removed from Phase 3 YAML gates; Phase3ShipExecutor already invokes it in sub-step 9 — YAML entry caused double human-approval request per pipeline run"
  - "Three regression tests added: two in test_quality_assessment.py (path correctness + no-old-paths guard), one in test_contract_runner.py (no duplicate mcp_approval gate)"
metrics:
  duration: "117s"
  completed_date: "2026-03-21"
  tasks_completed: 2
  files_changed: 3
---

# Phase 6 Plan 01: Contract Alignment — Path and Gate Deduplication Summary

Contract deliverable paths corrected from stale docs/pipeline/legal/ paths to the TSX files the executor actually produces (src/app/privacy/page.tsx, src/app/terms/page.tsx), deployment path fixed from deployment-report.json to deployment.json, and duplicate mcp_approval gate removed from Phase 3 YAML.

## What Was Done

### Task 1: Write Regression Tests (TDD RED)

Added three new test methods across two existing test files:

**tests/test_quality_assessment.py** — class `TestGenerateQualitySelfAssessment`:
- `test_phase_3_deliverable_paths_match_executor`: calls `generate_quality_self_assessment("3", ...)` and asserts the returned deliverable paths exactly equal `{"docs/pipeline/deployment.json", "src/app/privacy/page.tsx", "src/app/terms/page.tsx"}`
- `test_phase_3_no_old_legal_paths`: regression guard asserting no deliverable path contains `"docs/pipeline/legal/"`

**tests/test_contract_runner.py** — new class `TestPhase3ContractAlignment`:
- `test_phase3_no_mcp_approval_gate_in_yaml`: loads the live YAML, finds Phase 3, collects gate types, asserts `"mcp_approval" not in gate_types`

All three tests failed RED against the original YAML (confirmed before commit).

### Task 2: Fix YAML Contract (GREEN)

Three path corrections and one gate removal in `contracts/pipeline-contract.web.v1.yaml` Phase 3 section:

| Field | Before | After |
|-------|--------|-------|
| Deployed Web Application path | `docs/pipeline/deployment-report.json` | `docs/pipeline/deployment.json` |
| Privacy Policy path | `docs/pipeline/legal/privacy-policy.md` | `src/app/privacy/page.tsx` |
| Terms of Service path | `docs/pipeline/legal/terms-of-service.md` | `src/app/terms/page.tsx` |
| Phase 3 gates | included `mcp_approval` (6 gates) | removed `mcp_approval` (5 gates) |

After the fix: all three new tests pass GREEN, full suite 439 tests with zero failures.

## Deviations from Plan

None — plan executed exactly as written. TDD cycle followed: RED commit (740b010) then GREEN fix commit (bdb8924).

## Key Design Links

- `tools/quality_self_assessment.py` reads `deliverable.get("path")` from YAML — no Python changes needed, path fix in YAML propagates automatically
- `tools/contract_pipeline_runner.py` gate dispatch `gate_type == "mcp_approval"` code remains intact — needed for other phase contexts; only the Phase 3 YAML entry was removed
- `tools/gates/legal_gate.py` `LEGAL_FILES` already had correct TSX paths; YAML was lagging behind

## Self-Check

Verified:
- contracts/pipeline-contract.web.v1.yaml: FOUND (correct paths confirmed in lines 169, 178, 186; no mcp_approval in Phase 3 gates)
- tests/test_quality_assessment.py: FOUND (test_phase_3_deliverable_paths_match_executor, test_phase_3_no_old_legal_paths added)
- tests/test_contract_runner.py: FOUND (TestPhase3ContractAlignment.test_phase3_no_mcp_approval_gate_in_yaml added)
- Commits: 740b010 (test RED), bdb8924 (fix GREEN) — both present in git log

## Self-Check: PASSED
