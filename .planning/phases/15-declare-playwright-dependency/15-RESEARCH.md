# Phase 15: Declare Playwright Dependency - Research

**Researched:** 2026-03-24
**Domain:** Python packaging (pyproject.toml), uv/uvx dependency resolution, Playwright browser setup
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- playwright must be declared in pyproject.toml so `uvx web-app-factory` installs it automatically
- Optional dependency group (e.g., `[project.optional-dependencies] e2e = ["playwright"]`) vs direct dependency — researcher/planner should determine which approach ensures `uvx` picks it up by default
- Browser binaries (chromium) need to be installed after pip install — document or automate `playwright install chromium`
- The existing try/except import pattern in e2e_gate.py (line 32-36) should remain as a safety fallback even after playwright becomes a declared dependency
- The gate's "playwright is required but not installed" error message should be updated to reflect that playwright should already be installed

### Claude's Discretion

- Whether to use optional-dependencies or direct dependencies (whichever ensures `uvx` default install works)
- Whether to add a post-install hook or document `playwright install chromium` as a manual step
- Test strategy for verifying the dependency chain works

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| QUAL-02 | E2E Playwright gate validates form submission → result page flows after build | Playwright must be declared as direct dependency; browser binaries need `playwright install chromium` post-install step; e2e_gate.py already has correct implementation once playwright is importable |
</phase_requirements>

## Summary

Phase 15 is a focused packaging fix: declare `playwright` as a direct dependency in `pyproject.toml` so that `uvx web-app-factory` installs it automatically, enabling the E2E gate (already fully implemented in `tools/gates/e2e_gate.py`) to run on fresh installations rather than returning BLOCKED.

The core research question is: **which dependency table makes `uvx` pick up playwright by default?** The answer is clear: only `[project.dependencies]` (direct dependencies) are installed when `uvx package-name` is run. `[project.optional-dependencies]` are NOT installed unless the user runs `uvx 'package[extra]'`. `[dependency-groups]` are also NOT installed by `uvx` (they are a local/dev concept that uvx ignores). Therefore playwright MUST go in `[project.dependencies]`.

The secondary challenge is Playwright's two-step install: the Python package (`pip install playwright`) only installs the Python bindings; browser binaries must be installed separately via `playwright install chromium`. This cannot be automated through pyproject.toml alone. The correct approach is to document it clearly in README/error messages, and update the gate's BLOCKED message to guide users to run `playwright install chromium`.

**Primary recommendation:** Add `playwright>=1.50.0` to `[project.dependencies]` in pyproject.toml, and update the e2e_gate.py BLOCKED message to say "playwright browser not found — run: playwright install chromium".

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| playwright | >=1.50.0 | Browser automation for E2E gate | Already installed in project .venv at 1.58.0; official Microsoft library; only Python E2E option in use |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| axe-playwright-python | (already declared) | accessibility_gate.py dependency | Already uses playwright; no change needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| direct dependency | optional-dependency [e2e] | Optional deps are NOT installed by `uvx` by default — would break the goal |
| direct dependency | [dependency-groups] dev | Dev groups are NOT installed by `uvx` — would break the goal |
| manual `playwright install chromium` | automated post-install | Python pyproject.toml has no supported post-install hook mechanism; console_scripts entry points run only on explicit invocation, not at install time |

**Installation:**
```bash
# After adding playwright to [project.dependencies]:
uv sync
uv run playwright install chromium
```

## Architecture Patterns

### Recommended Project Structure

No structural changes needed. The change is confined to:
- `pyproject.toml` — add playwright to `[project.dependencies]`
- `tools/gates/e2e_gate.py` — update BLOCKED message (line ~157)
- `tests/test_e2e_gate.py` — update `test_playwright_missing_issue_mentions_playwright` assertion if message text changes

### Pattern 1: Direct Dependency Declaration

**What:** Add playwright to `[project.dependencies]` so all install methods (pip, uv, uvx) get it
**When to use:** Any library that is required at runtime by the main package
**Example:**
```toml
# pyproject.toml — [project] section
dependencies = [
    "claude-agent-sdk>=0.1.50",
    "fastmcp>=3.1.0",
    "httpx>=0.28.0",
    "jsonschema>=4.20.0",
    "keyring>=25.0.0",
    "mcp>=1.26.0",
    "playwright>=1.50.0",   # ← add this line
    "pyyaml>=6.0",
]
```

### Pattern 2: Updated BLOCKED Error Message

**What:** When playwright Python package is installed but browser binaries are missing, provide actionable guidance
**When to use:** After playwright is a declared dependency, the BLOCKED message should distinguish "package missing" from "browser binaries missing"

Current message (line 157 in e2e_gate.py):
```python
issues=["playwright is required but not installed — run: pip install playwright && playwright install chromium"],
```

Updated message (since `pip install playwright` will already have happened via uvx):
```python
issues=["playwright browser binaries not found — run: playwright install chromium"],
```

### Pattern 3: Chromium Binary Installation

**What:** Playwright Python package does not bundle browser binaries. Binaries must be installed separately.
**When to use:** After first install on any machine, and in CI/CD environments
**Example:**
```bash
# Install binaries (one-time per machine, stored in ~/.cache/ms-playwright/)
playwright install chromium

# Or with uv:
uv run playwright install chromium
```

**CI/CD pattern:**
```bash
# In GitHub Actions or similar:
- run: uv sync
- run: uv run playwright install chromium --with-deps
```

### Anti-Patterns to Avoid

- **Adding to `[project.optional-dependencies]`:** uvx does NOT install extras by default. The user would have to run `uvx 'web-app-factory[e2e]'` explicitly — defeating the goal of automatic availability.
- **Adding to `[dependency-groups] dev`:** uvx ignores dependency-groups entirely. Only `uv sync` and `uv run` in project context install dev groups.
- **Post-install hooks:** Python packaging (PEP 517/518) does not support post-install hooks in pyproject.toml. Any attempt to auto-install chromium via entry_points or setup.py tricks is non-standard and fragile.
- **Bundling chromium:** Chromium binaries are 100-400MB per platform. They must never be included as a Python package file.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Browser binary installation | Custom download script in pyproject.toml | `playwright install chromium` CLI command | Playwright handles versioning, platform detection, and caching (~/.cache/ms-playwright/) |
| Import guard | Replace try/except with hard import | Keep existing try/except in e2e_gate.py | Safety fallback when binaries installed but package somehow absent in edge cases |

**Key insight:** The hard part of this phase is NOT the code change — it is understanding that `playwright install chromium` cannot be automated via packaging alone, and that the right solution is documentation + an improved error message.

## Common Pitfalls

### Pitfall 1: Using optional-dependencies instead of direct dependencies

**What goes wrong:** `[project.optional-dependencies] e2e = ["playwright"]` is added but uvx does not install extras by default. Gate still returns BLOCKED on fresh install.
**Why it happens:** Optional dependencies are opt-in. `uvx web-app-factory` installs only `[project.dependencies]`.
**How to avoid:** Use `[project.dependencies]`. Playwright is a runtime requirement for the E2E gate, not an optional feature.
**Warning signs:** Tests pass locally (playwright already in .venv) but gate returns BLOCKED on a fresh machine.

### Pitfall 2: Assuming playwright install chromium is automatic

**What goes wrong:** Developer adds playwright to dependencies, ships the change, and the gate still returns BLOCKED because browser binaries are missing.
**Why it happens:** `pip install playwright` (or `uv sync`) installs the Python package and CLI, but does NOT download browser executables. Browser binaries require a separate command.
**How to avoid:** Document the two-step install prominently. Update the gate's BLOCKED message to say "run: playwright install chromium" not "run: pip install playwright".
**Warning signs:** `import playwright` succeeds but `sync_playwright()` raises an error about missing browser executable.

### Pitfall 3: Version constraint too tight

**What goes wrong:** Pinning `playwright==1.58.0` causes dependency conflicts when users have other playwright-dependent tools installed.
**Why it happens:** Over-constraining package versions.
**How to avoid:** Use `playwright>=1.50.0` (current project uses 1.58.0; 1.50.0 was the first stable version with the API patterns used in e2e_gate.py).
**Warning signs:** uv/pip reports dependency conflict on install.

### Pitfall 4: Forgetting to update uv.lock

**What goes wrong:** pyproject.toml updated but uv.lock not regenerated; CI installs from stale lockfile without playwright.
**Why it happens:** uv.lock is not auto-updated on pyproject.toml edit.
**How to avoid:** Run `uv lock` after modifying `[project.dependencies]`.
**Warning signs:** `uv sync --frozen` (used in CI) installs from stale lockfile.

### Pitfall 5: Breaking test_fails_when_playwright_missing test

**What goes wrong:** test_e2e_gate.py line 249 patches `sys.modules["playwright"]` to None to simulate missing playwright. After declaring playwright as a real dependency, this test still works because it patches the module-level `sync_playwright` attribute directly — but if the BLOCKED message text changes, `test_playwright_missing_issue_mentions_playwright` may fail.
**Why it happens:** Test assertion checks for "playwright" in `result.issues[0].lower()` — this is text-content-dependent.
**How to avoid:** Verify the updated message still contains "playwright" (it does: "playwright browser binaries not found — run: playwright install chromium"). The test should continue to pass.
**Warning signs:** Test failure on `assert "playwright" in result.issues[0].lower()`.

## Code Examples

Verified patterns from official sources:

### pyproject.toml Change (complete diff)
```toml
# Source: pyproject.toml current state + uv dependency rules
[project]
dependencies = [
    "claude-agent-sdk>=0.1.50",
    "fastmcp>=3.1.0",
    "httpx>=0.28.0",
    "jsonschema>=4.20.0",
    "keyring>=25.0.0",
    "mcp>=1.26.0",
    "playwright>=1.50.0",    # ← new line
    "pyyaml>=6.0",
]
```

### e2e_gate.py BLOCKED message update
```python
# Source: tools/gates/e2e_gate.py line ~157 — current:
issues=["playwright is required but not installed — run: pip install playwright && playwright install chromium"],

# Updated (playwright package now declared; only binaries may be missing):
issues=["playwright browser binaries not found — run: playwright install chromium"],
```

### Verification: confirm playwright is found by uvx after change
```bash
# After pyproject.toml change, verify on a clean install:
uvx web-app-factory  # should not error on playwright import
uv run python -c "from playwright.sync_api import sync_playwright; print('OK')"
```

### Test run command
```bash
# Quick validation:
uv run pytest tests/test_e2e_gate.py -q

# Full suite (1 pre-existing failure expected: test_deploy_target_github_pages):
uv run pytest -q
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Setup.py post-install hooks | No post-install hooks supported in pyproject.toml | PEP 517 (2019) | Browser binaries require explicit `playwright install` step |
| `[dependency-groups]` for runtime deps | `[project.dependencies]` for runtime deps | PEP 735 (2024) | dependency-groups are dev/local only; not seen by uvx |
| Optional extras for browser tools | Direct dependency | uvx design | uvx installs only direct deps by default |

**Deprecated/outdated:**
- Using `[dependency-groups] dev` for runtime dependencies: Dev groups are a local-only concept; they are not installed by `uvx` or when the package is installed from PyPI.

## Open Questions

1. **Should `playwright install chromium` be run in CI as part of the test suite?**
   - What we know: The 21 existing tests in test_e2e_gate.py all mock playwright; they do not require browser binaries. The gate itself requires binaries at runtime, not at test time.
   - What's unclear: Whether a new integration test should call the actual gate with real playwright + a real Next.js app.
   - Recommendation: Existing mock-based tests are sufficient for Phase 15 scope. Real browser integration test is out of scope (would require a built Next.js app). Document `playwright install chromium` in README only.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.x |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options] testpaths = ["tests"]` |
| Quick run command | `uv run pytest tests/test_e2e_gate.py -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUAL-02 | playwright importable after install | unit | `uv run pytest tests/test_e2e_gate.py -q` | ✅ (21 existing tests) |
| QUAL-02 | BLOCKED message updated to reflect binaries | unit | `uv run pytest tests/test_e2e_gate.py::TestE2eGatePlaywrightMissing -q` | ✅ (tests check message content) |
| QUAL-02 | All existing e2e_gate tests still pass | unit | `uv run pytest tests/test_e2e_gate.py -q` | ✅ |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_e2e_gate.py -q`
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** Full suite green (minus pre-existing `test_deploy_target_github_pages` failure) before `/gsd:verify-work`

### Wave 0 Gaps

None — existing test infrastructure covers all phase requirements. The 21 tests in `tests/test_e2e_gate.py` are comprehensive. No new test files needed; only potential message text assertion updates within existing tests.

## Sources

### Primary (HIGH confidence)

- uv official docs (https://docs.astral.sh/uv/guides/tools/) — uvx installs only direct `[project.dependencies]`, not optional-dependencies or dependency-groups
- uv official docs (https://docs.astral.sh/uv/concepts/projects/dependencies/) — distinction between `[project.dependencies]`, `[project.optional-dependencies]`, `[dependency-groups]`
- playwright.dev/python/docs/intro — two-step install: `pip install playwright` + `playwright install chromium`

### Secondary (MEDIUM confidence)

- Project .venv pip show playwright: playwright 1.58.0 already installed — version verified locally
- Existing pyproject.toml content verified by direct file read
- e2e_gate.py lines 31-38 and 148-158 verified by direct file read
- All 21 tests in tests/test_e2e_gate.py pass (verified: `uv run pytest tests/test_e2e_gate.py -q — 21 passed`)

### Tertiary (LOW confidence)

None — all critical claims verified from primary or secondary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — playwright version confirmed from local .venv; uvx behavior confirmed from official docs
- Architecture: HIGH — pyproject.toml structure verified directly; uvx optional-dependency behavior confirmed
- Pitfalls: HIGH — pitfalls derived from verified facts about uvx and playwright two-step install

**Research date:** 2026-03-24
**Valid until:** 2026-06-24 (stable tooling; 90-day estimate)
