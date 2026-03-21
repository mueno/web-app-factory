# Phase 6: Contract Alignment + Ship Fixes - Research

**Researched:** 2026-03-22
**Domain:** Python pipeline internals — YAML contract path alignment, quality self-assessment, MCP gate deduplication
**Confidence:** HIGH

## Summary

Phase 6 is a surgical fix phase with three discrete problems, all identified and fully verified by the v1.0 milestone audit. The root causes are confirmed by direct source code reading. No external dependencies are involved — this is pure intra-codebase alignment.

**Problem 1 — Legal deliverable paths:** The YAML contract declares `docs/pipeline/legal/privacy-policy.md` and `docs/pipeline/legal/terms-of-service.md` for Phase 3 legal deliverables. The Phase 3 executor (step 3: `_generate_legal`) actually instructs the deploy agent to create `src/app/privacy/page.tsx` and `src/app/terms/page.tsx`. The legal gate (`tools/gates/legal_gate.py`) also checks for the TSX paths, not the markdown paths. The quality self-assessment reads paths from the YAML contract, so it reports the deliverables as "pending" even when the TSX files exist.

**Problem 2 — Deployment deliverable filename:** The YAML contract declares `docs/pipeline/deployment-report.json` as the deployment deliverable path. The executor writes `docs/pipeline/deployment.json` (confirmed in `phase_3_executor.py` line 63: `_DEPLOYMENT_JSON_PATH = Path("docs") / "pipeline" / "deployment.json"`). The quality self-assessment again reads the contract path, so it sees `deployment-report.json` and reports the deployment deliverable as pending even after a successful deploy.

**Problem 3 — MCP approval gate invoked twice:** Phase 3 executor step 9 (`_gate_mcp_approval`) calls `run_mcp_approval_gate()` directly. After the executor returns success, `contract_pipeline_runner.py`'s `_run_gate_checks()` iterates the Phase 3 gates in the YAML contract and encounters the `mcp_approval` gate type (line 229-233 in the YAML), dispatching to `run_mcp_approval_gate()` a second time. A human must approve twice per pipeline run.

**Primary recommendation:** Fix the YAML contract to match what the implementation actually produces — not the reverse. The executor, legal gate, and deployment logic are already correct and consistent. The YAML is the outlier.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONT-04 | Quality self-assessment JSON generated before every gate submission | Three path mismatches in the contract cause `generate_quality_self_assessment()` to report all Phase 3 deliverables as "pending" even after they are produced. Fixing the YAML paths fixes CONT-04. The duplicate MCP gate invocation is a co-located bug that must be resolved in the same change. |
</phase_requirements>

## Standard Stack

### Core (all already present in project)
| Module | Version | Purpose | Why Standard |
|--------|---------|---------|--------------|
| YAML (PyYAML) | 6.x (existing dep) | Load and rewrite `pipeline-contract.web.v1.yaml` | Already used throughout pipeline; `yaml.safe_load` + `yaml.dump` pattern established |
| `pathlib.Path` (stdlib) | Python 3.12 | Path comparisons and assertions in tests | Already used everywhere |
| `pytest` | 7.x (existing dep) | Test framework | 432+ tests passing; no change to framework |

### No New Dependencies
This phase adds zero new packages. All required code already exists.

**Installation:** None needed.

## Architecture Patterns

### Fix-Site vs Fix-Root Decision

The three problems can each be fixed at either end of the mismatch:

**Option A — Fix YAML contract (recommended):**
- Change `docs/pipeline/legal/privacy-policy.md` → `src/app/privacy/page.tsx`
- Change `docs/pipeline/legal/terms-of-service.md` → `src/app/terms/page.tsx`
- Change `docs/pipeline/deployment-report.json` → `docs/pipeline/deployment.json`
- Remove the `mcp_approval` gate from Phase 3 gates in the YAML (executor already handles it)

**Option B — Fix executor and legal gate:**
- Change Phase 3 executor to write markdown files instead of TSX pages
- Change legal gate to check markdown paths
- Change `_DEPLOYMENT_JSON_PATH` constant

Option A is correct because: the legal documents ARE TSX pages (React Server Components in the Next.js app). Generating them as `.md` files in `docs/pipeline/` would break the actual deployment — the Next.js router would not serve them. The executor writes them to the right place. The YAML contract was written with incorrect assumptions about where legal docs live.

### Recommended Fix: YAML-Only Change

Affected YAML sections in `contracts/pipeline-contract.web.v1.yaml`:

```yaml
# BEFORE (wrong):
  - id: "3"
    deliverables:
      - name: "Deployed Web Application"
        path: "docs/pipeline/deployment-report.json"   # <-- wrong name
      - name: "Privacy Policy"
        path: "docs/pipeline/legal/privacy-policy.md"  # <-- wrong path
      - name: "Terms of Service"
        path: "docs/pipeline/legal/terms-of-service.md" # <-- wrong path
    gates:
      ...
      - type: "mcp_approval"   # <-- duplicate: executor already calls this
        description: "Human approval gate via MCP server before public deployment"
        conditions:
          tool: "approve_gate"
          phase: "3"

# AFTER (correct):
  - id: "3"
    deliverables:
      - name: "Deployed Web Application"
        path: "docs/pipeline/deployment.json"          # matches _DEPLOYMENT_JSON_PATH
      - name: "Privacy Policy"
        path: "src/app/privacy/page.tsx"               # matches legal_gate.LEGAL_FILES[0]
      - name: "Terms of Service"
        path: "src/app/terms/page.tsx"                 # matches legal_gate.LEGAL_FILES[1]
    gates:
      ...
      # mcp_approval gate removed — Phase3ShipExecutor._gate_mcp_approval() handles this
```

### The MCP Approval Gate Duplication Pattern

The Phase 3 executor is a "fat executor" — it handles all of Phase 3 internally in 10 sub-steps, including the MCP approval gate. This is a different model from phases 1a, 1b, 2a, 2b where the executor does the work and the contract runner dispatches gates.

The contract_pipeline_runner.py `_run_gate_checks()` is designed as the gate-dispatch layer for phases whose executors do not handle gates internally. Phase 3's executor is self-contained — it should NOT have the runner re-run its gates.

Two resolution approaches:

**A (recommended): Remove `mcp_approval` gate from Phase 3 YAML.** The executor handles it. The YAML gate entry was placed there as a declaration, but the executor's execute() already enforces it. Removing it from the YAML prevents the runner from dispatching a second invocation.

**B (alternative): Detect executor-handled gates in the runner.** The runner could skip gate dispatch for phases whose executor is "fat" (handles all gates internally). This is over-engineered for a single phase.

Option A is correct. The Phase 3 executor was always designed to be self-contained (10 sub-steps, handles every gate type). The YAML `mcp_approval` gate entry is the mistake.

### Anti-Patterns to Avoid

- **Fixing the executor to write markdown files** — this would break the actual Next.js deployment; the pages need to be TSX files served by the router
- **Changing `legal_gate.LEGAL_FILES`** — the legal gate is correct; it checks TSX paths in the right place
- **Adding a "skip-if-executor-handles" flag to the runner** — over-engineering; just remove the duplicate gate from the YAML
- **Changing `_DEPLOYMENT_JSON_PATH` constant in the executor** — the filename `deployment.json` is fine; the YAML was wrong
- **Updating only the YAML without updating tests** — the quality self-assessment tests check specific deliverable paths from the contract; they must be updated to match new paths

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML editing | Custom serializer | Read YAML, update dict, write with `yaml.dump` (or direct text edit) | PyYAML is already in the venv; full round-trip works for this file |
| Path verification | Custom path-checker | Existing `generate_quality_self_assessment()` with updated contract | The function already works correctly — only the YAML input was wrong |
| Gate deduplication | New runner logic | Remove the duplicate gate entry from YAML | The runner's gate dispatch is correct; the contract declared a gate it shouldn't have |

**Key insight:** All three bugs are data bugs (wrong values in the YAML), not code bugs. The code is correct. The YAML contract misrepresents what the code does.

## Common Pitfalls

### Pitfall 1: Quality Self-Assessment Tests Check Contract Deliverable Paths
**What goes wrong:** `tests/test_quality_assessment.py::TestGenerateQualitySelfAssessment::test_criteria_count_matches_contract` and related tests assert on the number of criteria and deliverable structure by reading the actual contract. After changing the YAML, these tests will still pass because they test the shape of the output (criteria count = 5 for Phase 1a), not Phase 3 paths specifically.
**Why it happens:** Tests use `CONTRACT_PATH` constant pointing to the live contract file, so they reflect whatever is in the YAML.
**How to avoid:** Run full test suite after YAML change to confirm no regressions.
**Warning signs:** Any test failure in `test_quality_assessment.py` after YAML change — check if path assertions are hardcoded.

### Pitfall 2: Phase 3 Executor Tests Assert Sub-Step Count
**What goes wrong:** `tests/test_phase_3_executor.py::TestPhase3ExecutorProperties` may test `len(executor.sub_steps) == 10`. The executor sub-steps list will NOT change (the fix is YAML-only). But if any test asserts the Phase 3 YAML gate count, it will need updating.
**Why it happens:** Tests that count gates in the contract will fail if the `mcp_approval` gate is removed.
**How to avoid:** Search for tests that count Phase 3 gates or check for `mcp_approval` gate presence in the contract.
**Warning signs:** Tests asserting `len(contract_phase["gates"]) == 7` will fail when it becomes 6.

### Pitfall 3: Legal Gate Tests May Use Paths From Legal Gate Module (Not Contract)
**What goes wrong:** `tests/test_legal_gate.py` checks `LEGAL_FILES` which are `src/app/privacy/page.tsx` and `src/app/terms/page.tsx` — these are correct. The legal gate is NOT broken. Do not "fix" the legal gate.
**Why it happens:** The legal gate was written to match the executor, not the contract. The contract was wrong.
**How to avoid:** Leave `tools/gates/legal_gate.py` unchanged. Only change the YAML.
**Warning signs:** If you touch `legal_gate.py`, you will break the already-working legal checks.

### Pitfall 4: Deployment Gate Tests May Assert `deployment.json` vs `deployment-report.json`
**What goes wrong:** `tests/test_deployment_gate.py` or `test_contract_runner.py` may assert the deployment JSON path. If any test reads `deployment-report.json` from the YAML and asserts it equals what the executor writes, the test would have been failing already (it would be asserting a path mismatch).
**Why it happens:** Tests written before the audit may have been written against incorrect contract paths.
**How to avoid:** Run the full test suite before and after the YAML fix to see what changes.
**Warning signs:** Green tests that use `deployment-report.json` in assertions — these tests were wrong and should be updated.

### Pitfall 5: YAML Quality Self-Assessment Output Path in Phase 3 Tests
**What goes wrong:** Any test that calls `generate_quality_self_assessment("3", ...)` and then asserts deliverable paths in the output JSON will fail if test was written against old YAML. After fix, the output JSON will contain the new paths (`src/app/privacy/page.tsx` etc.).
**Why it happens:** The function reads paths from the live contract; tests asserting specific paths against the old contract will now see different paths.
**How to avoid:** Update assertions in any test that checks Phase 3 deliverable paths in the quality self-assessment output.
**Warning signs:** `AssertionError` involving `docs/pipeline/legal/` or `deployment-report.json` in Phase 3 quality assessment tests.

## Code Examples

### The Three Exact Fixes Required

**Fix 1: Legal deliverable paths in YAML**
```yaml
# Source: contracts/pipeline-contract.web.v1.yaml, Phase 3 deliverables section
# CHANGE:
      - name: "Privacy Policy"
        path: "docs/pipeline/legal/privacy-policy.md"  # WRONG

# TO:
      - name: "Privacy Policy"
        path: "src/app/privacy/page.tsx"               # CORRECT — matches legal_gate.LEGAL_FILES[0]
```

```yaml
# CHANGE:
      - name: "Terms of Service"
        path: "docs/pipeline/legal/terms-of-service.md"  # WRONG

# TO:
      - name: "Terms of Service"
        path: "src/app/terms/page.tsx"                    # CORRECT — matches legal_gate.LEGAL_FILES[1]
```

**Fix 2: Deployment deliverable filename in YAML**
```yaml
# Source: contracts/pipeline-contract.web.v1.yaml, Phase 3 deliverables section
# CHANGE:
      - name: "Deployed Web Application"
        path: "docs/pipeline/deployment-report.json"  # WRONG

# TO:
      - name: "Deployed Web Application"
        path: "docs/pipeline/deployment.json"         # CORRECT — matches _DEPLOYMENT_JSON_PATH
```

**Fix 3: Remove duplicate mcp_approval gate from Phase 3**
```yaml
# Source: contracts/pipeline-contract.web.v1.yaml, Phase 3 gates section
# REMOVE this entire gate block:
      - type: "mcp_approval"
        description: "Human approval gate via MCP server before public deployment"
        conditions:
          tool: "approve_gate"
          phase: "3"
# REASON: Phase3ShipExecutor._gate_mcp_approval() already calls run_mcp_approval_gate()
# in step 9. This gate entry causes a second invocation via _run_gate_checks().
```

### Verification: What the Quality Self-Assessment Will Report After Fix

After the YAML fix, `generate_quality_self_assessment("3", project_dir, contract_path)` will produce:
```json
{
  "phase_id": "3",
  "timestamp": "...",
  "deliverables": [
    {
      "name": "Deployed Web Application",
      "path": "docs/pipeline/deployment.json",
      "criteria": [...]
    },
    {
      "name": "Privacy Policy",
      "path": "src/app/privacy/page.tsx",
      "criteria": [...]
    },
    {
      "name": "Terms of Service",
      "path": "src/app/terms/page.tsx",
      "criteria": [...]
    }
  ]
}
```

These paths match what the executor produces, so a future verifier can check file existence against the assessment and find all deliverables present (not "pending" due to wrong paths).

### How to Confirm the MCP Approval Gate Count Before Fix

```python
# Source: confirmed by reading contracts/pipeline-contract.web.v1.yaml lines 193-234
import yaml
contract = yaml.safe_load(open("contracts/pipeline-contract.web.v1.yaml").read())
phase_3 = next(p for p in contract["phases"] if p["id"] == "3")
gate_types = [g["type"] for g in phase_3["gates"]]
# Current: ["lighthouse", "accessibility", "security_headers", "link_integrity",
#           "deployment", "mcp_approval"]  ← 6 gates, last one is duplicate
# After fix: ["lighthouse", "accessibility", "security_headers", "link_integrity",
#              "deployment"]  ← 5 gates, no duplicate
```

### Path Cross-Reference Table (Before → After)

| Deliverable | YAML Path (BEFORE) | Actual Path (AFTER fix) | Source of Truth |
|-------------|-------------------|------------------------|-----------------|
| Deployed Web Application | `docs/pipeline/deployment-report.json` | `docs/pipeline/deployment.json` | `phase_3_executor.py:63` (`_DEPLOYMENT_JSON_PATH`) |
| Privacy Policy | `docs/pipeline/legal/privacy-policy.md` | `src/app/privacy/page.tsx` | `legal_gate.py:25` (`LEGAL_FILES[0]`) |
| Terms of Service | `docs/pipeline/legal/terms-of-service.md` | `src/app/terms/page.tsx` | `legal_gate.py:26` (`LEGAL_FILES[1]`) |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Contract declares markdown legal docs | Contract matches TSX pages that executor actually writes | This phase | Quality self-assessment correctly identifies present deliverables |
| `deployment-report.json` in contract | `deployment.json` in contract | This phase | Deployment deliverable no longer reported as "pending" |
| 6 Phase 3 gates including `mcp_approval` | 5 Phase 3 gates (executor handles MCP approval) | This phase | Human approves exactly once per pipeline run |

**Deprecated/outdated:**
- `docs/pipeline/legal/privacy-policy.md` path in contract: removed (wrong location)
- `docs/pipeline/legal/terms-of-service.md` path in contract: removed (wrong location)
- `docs/pipeline/deployment-report.json` path in contract: replaced with `deployment.json`
- `mcp_approval` gate entry in Phase 3 YAML: removed (executor handles it)

## Open Questions

1. **Are there any tests that count Phase 3 YAML gates and will break when `mcp_approval` is removed?**
   - What we know: `test_contract_schema.py` validates the contract against JSON schema — this will still pass (schema allows any number of gates). `test_phase_3_executor.py` tests the executor, not the YAML gate list.
   - What's unclear: Whether `test_contract_runner.py` asserts the count of gates for Phase 3.
   - Recommendation: Run `uv run pytest tests/test_contract_runner.py tests/test_quality_assessment.py tests/test_phase_3_executor.py -x -q` after the YAML change to catch any gate-count assertions.

2. **Should `contract_pipeline_runner.py`'s `_run_gate_checks()` skip Phase 3 gates entirely since the executor handles them?**
   - What we know: After removing `mcp_approval` from the YAML, the remaining Phase 3 gates (lighthouse, accessibility, security_headers, link_integrity, deployment) will still be dispatched by the runner after the executor returns success. This could mean duplicate gate runs for those as well.
   - What's unclear: Whether running those gates twice is harmful. Lighthouse/accessibility/security_headers running twice is wasteful but not harmful. Link integrity running twice is benign.
   - Recommendation: Only remove the `mcp_approval` gate for now (blocking fix). The redundant non-blocking gate runs are not harmful and removing all Phase 3 gates from the YAML would deviate from the contract-first design. Document as tech debt for future cleanup.

3. **Does the quality self-assessment output need to be updated in any existing output/ directory?**
   - What we know: The `output/` directory is gitignored and contains runtime artifacts. Any stale quality-self-assessment-3.json files there are from prior test runs.
   - Recommendation: No action needed. The fix only affects future runs.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_quality_assessment.py tests/test_contract_schema.py tests/test_contract_runner.py tests/test_phase_3_executor.py -x -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONT-04 | Quality self-assessment for Phase 3 uses correct deliverable paths | unit | `uv run pytest tests/test_quality_assessment.py -x -q` | Exists (may need Phase 3 path assertions) |
| CONT-04 | Phase 3 YAML no longer contains `mcp_approval` gate | unit | `uv run pytest tests/test_contract_schema.py -x -q` | Exists (schema validation) |
| CONT-04 | Quality self-assessment reports `src/app/privacy/page.tsx` not `docs/pipeline/legal/privacy-policy.md` | unit | `uv run pytest tests/test_quality_assessment.py::TestGenerateQualitySelfAssessment -x` | Exists (needs new test for Phase 3 paths) |
| CONT-04 | MCP approval gate invoked exactly once (executor, not runner) | integration | `uv run pytest tests/test_contract_runner.py -x -k "mcp_approval"` | May need new test |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_quality_assessment.py tests/test_contract_schema.py tests/test_contract_runner.py tests/test_phase_3_executor.py -x -q`
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** Full suite green (432+ tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New test: `tests/test_quality_assessment.py::TestGenerateQualitySelfAssessment::test_phase_3_deliverable_paths_match_executor` — asserts Phase 3 quality assessment contains `src/app/privacy/page.tsx`, `src/app/terms/page.tsx`, and `docs/pipeline/deployment.json` (not old paths)
- [ ] New test: `tests/test_contract_runner.py::TestGateDispatch::test_phase3_no_mcp_approval_gate_in_yaml` — asserts that Phase 3 gates list in the YAML does NOT contain `mcp_approval` type (prevents regression)
- [ ] New test or update: `tests/test_contract_runner.py` — assert that `run_pipeline()` for Phase 3 does NOT invoke `run_mcp_approval_gate` via gate dispatch (executor handles it)

*(All test files exist; Wave 0 adds targeted assertions to verify the YAML fix is correct and complete.)*

## Sources

### Primary (HIGH confidence)
- Direct source code reading — `contracts/pipeline-contract.web.v1.yaml` lines 168-234 — confirmed three wrong values (legal paths, deployment filename, duplicate mcp_approval gate)
- Direct source code reading — `tools/phase_executors/phase_3_executor.py` line 63 (`_DEPLOYMENT_JSON_PATH`), lines 414-435 (`_generate_legal` prompt with TSX targets), lines 640-665 (`_gate_mcp_approval` sub-step)
- Direct source code reading — `tools/gates/legal_gate.py` lines 23-27 (`LEGAL_FILES` constant with TSX paths)
- Direct source code reading — `tools/contract_pipeline_runner.py` lines 280-284 (`mcp_approval` gate dispatch in `_run_gate_checks`)
- Direct source code reading — `tools/quality_self_assessment.py` lines 67-78 (`_extract_deliverables` reads paths from YAML, not from executor)
- `.planning/v1.0-MILESTONE-AUDIT.md` integration gaps section — authoritative audit description matches code analysis exactly

### Secondary (MEDIUM confidence)
- `tests/test_quality_assessment.py` — existing test patterns confirm `generate_quality_self_assessment` reads from contract
- `tests/test_phase_3_executor.py` — confirms executor does not change when YAML is fixed

### Tertiary (LOW confidence)
- None — all findings are code-verified

## Metadata

**Confidence breakdown:**
- Root cause analysis: HIGH — all three bugs confirmed by direct code reading; cross-referenced with milestone audit
- Fix approach: HIGH — YAML-only change; code is correct; clear path alignment evidence
- Test impact: MEDIUM — test count changes are predictable; specific test names need runtime verification
- Regression risk: LOW — change is scoped to YAML; no code logic changes; tests will catch path assertion regressions

**Research date:** 2026-03-22
**Valid until:** Does not expire — pure code/config analysis, no external dependencies
