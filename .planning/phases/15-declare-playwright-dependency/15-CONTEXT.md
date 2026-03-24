# Phase 15: Declare Playwright Dependency - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Declare playwright as a dependency in pyproject.toml so the E2E gate (tools/gates/e2e_gate.py) works on fresh installations via `uvx web-app-factory`. Currently playwright is imported with a try/except fallback — the gate returns BLOCKED when playwright is missing. This phase makes it a proper dependency.

</domain>

<decisions>
## Implementation Decisions

### Dependency declaration
- playwright must be declared in pyproject.toml so `uvx web-app-factory` installs it automatically
- Optional dependency group (e.g., `[project.optional-dependencies] e2e = ["playwright"]`) vs direct dependency — researcher/planner should determine which approach ensures `uvx` picks it up by default
- Browser binaries (chromium) need to be installed after pip install — document or automate `playwright install chromium`

### Gate behavior
- The existing try/except import pattern in e2e_gate.py (line 32-36) should remain as a safety fallback even after playwright becomes a declared dependency
- The gate's "playwright is required but not installed" error message should be updated to reflect that playwright should already be installed

### Claude's Discretion
- Whether to use optional-dependencies or direct dependencies (whichever ensures `uvx` default install works)
- Whether to add a post-install hook or document `playwright install chromium` as a manual step
- Test strategy for verifying the dependency chain works

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/gates/e2e_gate.py`: Already has try/except import for playwright (lines 32-36) and sync_playwright usage (line 283)
- `tests/test_e2e_gate.py`: Comprehensive test suite with mocked playwright — 15+ tests including `test_fails_when_playwright_missing`

### Established Patterns
- `pyproject.toml`: No current playwright dependency — needs to be added
- Try/except import pattern: Used in e2e_gate.py for graceful degradation when playwright is absent

### Integration Points
- `pyproject.toml` dependencies section — where playwright gets declared
- `e2e_gate.py` import block (lines 32-36) — fallback to None when not installed
- `uvx web-app-factory` install path — must resolve playwright automatically

</code_context>

<specifics>
## Specific Ideas

No specific requirements — this is a pure infrastructure/packaging change. The goal is straightforward: make `uvx web-app-factory` include playwright so the E2E gate doesn't return BLOCKED on fresh installs.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-declare-playwright-dependency*
*Context gathered: 2026-03-24*
