# Phase 14: Wire Interactive Gate Approval - Research

**Researched:** 2026-03-24
**Domain:** Python threading / file-based IPC / pipeline flow control
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TOOL-03 | `waf_approve_gate` allows user to approve or reject a gate with feedback | Two concrete gaps identified (BREAK-01, BREAK-02); exact code changes mapped |
</phase_requirements>

---

## Summary

Phase 14 closes two HIGH-severity integration gaps documented by the v2.0 milestone audit. The pipeline currently ignores `mode='interactive'` entirely (BREAK-01) and `waf_approve_gate` writes gate decisions to a different file path than the one the pipeline polls (BREAK-02). The result is that calling `waf_approve_gate` has no effect on a running pipeline, making TOOL-03 non-functional end-to-end.

The fix is surgical and touches three files: `_pipeline_bridge.py` (forward `interactive` flag to the runner), `contract_pipeline_runner.py` (add a pause-and-poll loop at every `mcp_approval` gate when interactive mode is active), and `tools/gates/mcp_approval_gate.py` (poll the same `output/.gate-responses/{run_id}.json` path that `waf_approve_gate` writes). No new modules are needed; the existing `ProgressStore` already tracks mode, and the existing gate infrastructure (GateResult, `_run_gate_checks`) is the correct injection point.

The threading model is the primary complexity: the pipeline runs in a `ThreadPoolExecutor` worker thread (not the asyncio event loop), so the pause mechanism must be a blocking poll in that thread — it cannot use asyncio primitives. A `time.sleep` polling loop reading a JSON file is the correct, consistent approach (it mirrors how `factory_mcp_server.approve_gate` already works).

**Primary recommendation:** Add `interactive_mode` boolean to `run_pipeline()` signature; in `_run_gate_checks`, when interactive mode is active and gate type is `mcp_approval`, replace the direct function call with a file-poll loop reading `output/.gate-responses/{run_id}.json`; forward `mode='interactive'` from `_pipeline_bridge.start_pipeline_async` to `run_pipeline` as `interactive_mode=True`.

---

## Standard Stack

### Core (already in project — no new dependencies)

| Module | Location | Purpose |
|--------|----------|---------|
| `time.sleep` / polling | stdlib | Block worker thread at gate checkpoint without asyncio |
| `json` | stdlib | Read/write gate decision JSON |
| `pathlib.Path` | stdlib | File operations for gate-response file |
| `threading` | stdlib | Worker thread already running pipeline |

### No New Dependencies

This phase requires no additions to `pyproject.toml`. The entire implementation uses existing stdlib and project modules.

---

## Architecture Patterns

### The Two Gaps — Exact Code Locations

**BREAK-01: `mode='interactive'` silently dropped**

In `_pipeline_bridge.py` `start_pipeline_async()` (lines 177-189), the `mode` parameter is tracked in `ProgressStore` but never forwarded to `run_pipeline()`:

```python
# Current (broken):
pipeline_kwargs: dict[str, Any] = {
    "project_dir": project_dir,
    "idea": idea,
    "dry_run": (mode == "dry_run"),   # interactive → dry_run=False, not forwarded
    "on_progress": _on_progress,
}
```

`run_pipeline()` signature (`contract_pipeline_runner.py` line 344) has no `mode` or `interactive_mode` parameter.

**BREAK-02: Gate response file path mismatch**

`waf_approve_gate` writes to:
```
output/.gate-responses/{run_id}.json
```

`mcp_approval_gate.run_mcp_approval_gate` calls `approve_gate()` from `factory_mcp_server.py` which polls:
```
/tmp/factory_approve_response_{pid}-{uuid}
```

These paths are completely unrelated. The fix: replace the `approve_gate()` function call in `mcp_approval_gate.py` with direct polling of `output/.gate-responses/{run_id}.json` when a `run_id` is available.

---

### Pattern 1: Forward `interactive_mode` Through Bridge

In `_pipeline_bridge.py`, add `interactive_mode` to `pipeline_kwargs`:

```python
# Source: _pipeline_bridge.py start_pipeline_async()
pipeline_kwargs: dict[str, Any] = {
    "project_dir": project_dir,
    "idea": idea,
    "dry_run": (mode == "dry_run"),
    "interactive_mode": (mode == "interactive"),   # NEW
    "on_progress": _on_progress,
}
```

In `contract_pipeline_runner.run_pipeline()`, add the parameter:

```python
def run_pipeline(
    contract: dict[str, Any],
    project_dir: str,
    idea: str,
    *,
    resume_run_id: Optional[str] = None,
    dry_run: bool = False,
    skip_gates: bool = False,
    contract_path: Optional[str] = None,
    company_name: Optional[str] = None,
    contact_email: Optional[str] = None,
    deploy_target: str = "vercel",
    on_progress: Optional[ProgressCallback] = None,
    interactive_mode: bool = False,        # NEW
) -> dict[str, Any]:
```

Pass `interactive_mode` into `_run_gate_checks`:

```python
gate_passed, gate_issues = _run_gate_checks(
    contract_phase, project_dir, nextjs_dir=nextjs_dir,
    interactive_mode=interactive_mode,    # NEW
    run_id=run_id,                        # NEW — needed for polling path
)
```

---

### Pattern 2: Poll the Shared File Path in the Gate

The `mcp_approval` gate branch in `_run_gate_checks` currently calls `run_mcp_approval_gate()`. In interactive mode, this should block the worker thread by polling the gate-responses file written by `waf_approve_gate`.

Two approaches for the polling location:

**Option A (recommended): Modify `mcp_approval_gate.run_mcp_approval_gate` to accept a run_id and poll the correct path.**

```python
# tools/gates/mcp_approval_gate.py
def run_mcp_approval_gate(
    phase_id: str,
    project_dir: str,
    *,
    interactive: bool = False,
    run_id: str = "",
) -> GateResult:
    if interactive and run_id:
        return _poll_mcp_gate_file(phase_id, project_dir, run_id)
    # ... existing approve_gate() path (used by legacy/auto mode)
```

```python
def _poll_mcp_gate_file(
    phase_id: str,
    project_dir: str,
    run_id: str,
    *,
    poll_interval: float = 2.0,
    timeout_seconds: int = 0,
) -> GateResult:
    """Block the pipeline worker thread by polling for waf_approve_gate decisions."""
    import time, json
    from pathlib import Path

    # Same location as waf_approve_gate writes
    gate_file = Path(project_dir).parent.parent / "output" / ".gate-responses" / f"{run_id}.json"
    started = time.monotonic()
    while True:
        if gate_file.exists():
            try:
                data = json.loads(gate_file.read_text(encoding="utf-8"))
                decision = data.get("decision", "")
                feedback = data.get("feedback", "")
                gate_file.unlink(missing_ok=True)  # consume — prevent double-reads
                if decision == "approve":
                    return GateResult(gate_type="mcp_approval", phase_id=phase_id,
                                      passed=True, status="PASS", ...)
                else:
                    return GateResult(gate_type="mcp_approval", phase_id=phase_id,
                                      passed=False, status="BLOCKED", ...)
            except (json.JSONDecodeError, OSError):
                pass
        if timeout_seconds > 0 and (time.monotonic() - started) >= timeout_seconds:
            return GateResult(passed=False, status="BLOCKED", issues=["Timeout waiting for gate"])
        time.sleep(poll_interval)
```

**Option B: Inline the poll loop directly in `_run_gate_checks`.**

Less clean — prefer Option A so gate logic stays in the gate module.

---

### Pattern 3: Status Surfacing in `waf_get_status`

When the pipeline is paused at a gate, `waf_get_status` should indicate this. Two sub-approaches:

**Sub-approach A (minimal):** Emit a `gate_waiting` progress event from the worker thread before entering the poll loop. The `ProgressStore` already handles arbitrary `event_type` strings. `format_status` renders the last 8 events, so users will see it.

```python
# In _poll_mcp_gate_file (before the poll loop starts):
_emit_progress(on_progress, "gate_waiting", phase_id,
               f"Waiting for gate approval — call waf_approve_gate('{run_id}', 'approve')",
               {"phase_id": phase_id, "run_id": run_id})
```

But `on_progress` callback is not available inside `mcp_approval_gate.py`. The callback must be passed in or emitted from `_run_gate_checks` before delegating.

**Sub-approach B (recommended):** Emit the `gate_waiting` event from `contract_pipeline_runner._run_gate_checks` just before calling `run_mcp_approval_gate(interactive=True)`. `_emit_progress` is available there.

```python
# In _run_gate_checks, mcp_approval branch:
elif gate_type == "mcp_approval":
    if interactive_mode and run_id:
        _emit_progress(on_progress, "gate_waiting", phase_id,
                       f"Paused at gate — call waf_approve_gate('{run_id}', 'approve') to continue",
                       {"run_id": run_id, "phase_id": phase_id})
    gate_result = run_mcp_approval_gate(
        phase_id=phase_id, project_dir=project_dir,
        interactive=interactive_mode, run_id=run_id or "",
    )
```

However, `_run_gate_checks` currently receives no `on_progress` callback. It must be added to the function signature:

```python
def _run_gate_checks(
    contract_phase: dict[str, Any],
    project_dir: str,
    *,
    nextjs_dir: str | None = None,
    interactive_mode: bool = False,
    run_id: str = "",
    on_progress: Optional[ProgressCallback] = None,
) -> tuple[bool, list[str]]:
```

---

### Pattern 4: Rejection Stops Pipeline with Clear Status

The `run_pipeline` loop already handles `gate_passed=False` by calling `mark_failed` and returning with `status="failed"`. No changes needed there. The rejection message from the gate file `feedback` field propagates through `gate_issues` and appears in the returned dict's `"gate_issues"` key — visible via `waf_get_status` disk fallback.

For a rejection to show in the live status (before the run is complete), the `gate_result` issue should be emitted as a progress event:

```python
# Already done by existing _emit_progress in run_pipeline after gate check:
_emit_progress(on_progress, "gate_result", phase_id,
               f"Gates {'passed' if gate_passed else 'failed'} for {phase_label}",
               {"passed": gate_passed})
```

So rejection automatically triggers `phase_statuses[phase_id] = "failed"` in `ProgressStore.get_run_summary`.

---

### Pattern 5: Auto-Mode Returns Error (Already Implemented)

`waf_approve_gate` already checks `store.get_mode(run_id)` and returns an error when mode is "auto":

```python
# mcp_server.py lines 192-200 — already correct, no change needed
if run_mode == "auto":
    return (
        f"Run `{run_id}` is in **auto** mode. "
        "Gates are approved automatically — manual approval is not applicable.\n\n"
        "To use manual gate approval, start the pipeline with `mode='interactive'`."
    )
```

---

### File Path Consistency: Critical Detail

`waf_approve_gate` computes the gate file path as:
```python
gate_dir = _PROJECT_ROOT / "output" / ".gate-responses"
gate_file = gate_dir / f"{run_id}.json"
```

Where `_PROJECT_ROOT = Path(__file__).parent.parent` (i.e., the `web-app-factory/` project root).

The polling in `mcp_approval_gate.py` must derive the same path. The gate module receives `project_dir` (e.g., `web-app-factory/output/my-recipe-app/`). The gate-responses directory is a sibling of `output/` sub-directories, one level up:

```
web-app-factory/
  output/
    .gate-responses/
      {run_id}.json      ← written by waf_approve_gate
    my-recipe-app/
      docs/pipeline/...  ← project_dir passed to mcp_approval_gate
```

The polling code must use a stable reference (either the known project root or a configurable path), not a relative calculation from `project_dir`. Options:

1. **Pass gate_responses_dir directly** from `run_pipeline` (which already knows `_PROJECT_ROOT` via the runner's own `Path(__file__)`).
2. **Use `config.settings.APPROVAL_TMP_DIR` equivalent** — but this is currently `/tmp`, which is the wrong location for the new path.
3. **Compute from `project_dir` by going up 2 levels** (`Path(project_dir).parent.parent / "output" / ".gate-responses"`) — fragile if project_dir depth changes.

**Recommended:** Add a `gate_dir` parameter to `run_mcp_approval_gate` and pass `_PROJECT_ROOT / "output" / ".gate-responses"` from the pipeline runner. This makes the path explicit and testable.

Alternatively, add a new setting in `config/settings.py`:

```python
GATE_RESPONSES_DIR = _env_path(
    "WEB_FACTORY_GATE_RESPONSES_DIR",
    PROJECT_ROOT / "output" / ".gate-responses",
)
```

Both `waf_approve_gate` (in `mcp_server.py`) and `mcp_approval_gate.py` can then import `GATE_RESPONSES_DIR` — single source of truth, env-overridable for testing.

---

### Anti-Patterns to Avoid

- **Using asyncio.Event or threading.Event** in the pipeline worker thread as the pause mechanism: The `waf_approve_gate` tool runs in the asyncio event loop; the pipeline runs in a ThreadPoolExecutor worker. Sharing an asyncio primitive across these threads is problematic. File-based polling is simpler and consistent with the existing pattern in `factory_mcp_server.approve_gate`.
- **Modifying the pipeline contract YAML** to add an `interactive` flag per-gate: Unnecessary complexity; the mode is a run-level setting, not a gate-level setting.
- **Calling `asyncio.run()` inside the polling loop**: `mcp_approval_gate.py` currently calls `asyncio.run(approve_gate(...))` — this creates a new event loop inside the worker thread. Replace this with direct file polling, which avoids the asyncio-in-thread pattern entirely.
- **Relying on gate file existence checking from the MCP tool** to know if the pipeline is paused: The pipeline emits progress events; use `ProgressStore` for status queries.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|------------|
| Thread-safe blocking pause | Custom threading.Event + asyncio bridge | `time.sleep` poll loop (same as existing `factory_mcp_server.approve_gate`) |
| Gate file path | Custom discovery logic | `config.settings.GATE_RESPONSES_DIR` (new setting, one source of truth) |
| Gate file JSON schema | Custom serialization | `json.dumps` / `json.loads` (already used in `waf_approve_gate`) |
| Progress status for "waiting at gate" | Custom status field in PipelineState | `ProgressStore.emit("gate_waiting", ...)` event (existing event system) |

---

## Common Pitfalls

### Pitfall 1: Path Mismatch Between Writer and Reader

**What goes wrong:** `waf_approve_gate` writes to path A, `mcp_approval_gate` polls path B. Decision never consumed, pipeline blocks forever.

**Why it happens:** The two modules were implemented independently without a shared path constant.

**How to avoid:** Introduce `GATE_RESPONSES_DIR` in `config/settings.py` and import it in both `mcp_server.py` and `mcp_approval_gate.py`.

**Warning signs:** Test where `waf_approve_gate` writes then `run_mcp_approval_gate` reads — if they don't agree on the path, the test hangs (use a short timeout in tests).

### Pitfall 2: asyncio.run() Called in Worker Thread

**What goes wrong:** `mcp_approval_gate.run_mcp_approval_gate` currently calls `asyncio.run(approve_gate(...))`. When `run_pipeline` is called from a ThreadPoolExecutor worker, and that worker already has an asyncio event loop (which `run_in_executor` does not guarantee), `asyncio.run()` may conflict with the outer event loop.

**Why it happens:** The original implementation assumed the gate would be called from a fresh thread with no event loop.

**How to avoid:** Replace `asyncio.run(approve_gate(...))` with the synchronous file-poll loop. No async needed.

**Warning signs:** `RuntimeError: This event loop is already running` when running `mcp_approval_gate` from inside the pipeline worker.

### Pitfall 3: Double-Consume Race on Gate File

**What goes wrong:** Two poll iterations both see the gate file exist and both try to read+delete it. Second reader gets `FileNotFoundError`.

**Why it happens:** TOCTOU between `gate_file.exists()` check and `gate_file.read_text()`.

**How to avoid:** Use `try/except (FileNotFoundError, json.JSONDecodeError)` around the read — treat missing file as "not yet available" and continue polling. Use `gate_file.unlink(missing_ok=True)` after reading.

### Pitfall 4: Worker Thread Blocks Forever on Missing Run ID

**What goes wrong:** Interactive mode active, but `run_id` is empty or `None`. Poll loop waits for a file that will never be written because the MCP tool can't know the correct filename.

**Why it happens:** `run_id` not propagated through `_run_gate_checks`.

**How to avoid:** Gate check must early-return `passed=False` with a clear issue message if `interactive_mode=True` but `run_id=""`.

### Pitfall 5: `_run_gate_checks` Signature Change Breaks Existing Callers

**What goes wrong:** `_run_gate_checks` is called in `run_pipeline` — adding `interactive_mode`, `run_id`, `on_progress` must be keyword-only with defaults so existing callers (including `factory.py` CLI) still work.

**How to avoid:** All new parameters should have default values (`interactive_mode: bool = False`, `run_id: str = ""`, `on_progress: Optional[ProgressCallback] = None`).

### Pitfall 6: `waf_approve_gate` Mode Check for Unknown Runs

**What goes wrong:** `store.get_mode(run_id)` returns `None` for runs not in the ProgressStore (e.g., runs started in a previous MCP session). Current code skips the auto-mode guard and writes the gate file.

**Why it happens:** In-memory ProgressStore is not persisted across restarts.

**How to avoid:** When `run_mode is None`, treat as "not known to be interactive" — write the gate file anyway (optimistic path) and let the pipeline consume or ignore it. Or display a warning. Do not silently block. This is existing behavior; Phase 14 should not regress it.

---

## Code Examples

### Complete Flow — End-to-End

```
waf_generate_app("recipe app", mode="interactive")
  → start_pipeline_async(mode="interactive")
    → ProgressStore.set_plan(run_id, plan, mode="interactive")
    → pipeline_kwargs["interactive_mode"] = True         ← NEW
    → loop.run_in_executor(_EXECUTOR, lambda: _run_pipeline_sync(**pipeline_kwargs))
      └─ run_pipeline(..., interactive_mode=True)        ← NEW
           [Phase 1a executes]
           _run_gate_checks(contract_phase, ..., interactive_mode=True, run_id=run_id)
             [for mcp_approval gate:]
               _emit_progress(..., "gate_waiting", ...)  ← NEW
               run_mcp_approval_gate(..., interactive=True, run_id=run_id)
                 → _poll_mcp_gate_file(...)              ← NEW (blocks worker thread)
                   while True: time.sleep(2)
                   # waf_approve_gate writes output/.gate-responses/{run_id}.json
                   # poll sees file, reads it, deletes it
                   → GateResult(passed=True) if "approve"
           [continues to next phase]

waf_approve_gate(run_id, "approve")
  → checks store.get_mode(run_id) → "interactive"  (already implemented)
  → writes output/.gate-responses/{run_id}.json     (already implemented)
  → returns "✓ Gate approved for run ..."           (already implemented)
```

### Gate File Schema (already defined in mcp_server.py, no change)

```json
{
    "run_id": "20260324-143000-recipe-app",
    "decision": "approve",
    "feedback": ""
}
```

### Settings Addition

```python
# config/settings.py — NEW
GATE_RESPONSES_DIR = _env_path(
    "WEB_FACTORY_GATE_RESPONSES_DIR",
    PROJECT_ROOT / "output" / ".gate-responses",
)
```

### mcp_server.py — Use Shared Constant

```python
# Replace existing hardcoded path:
# gate_dir = _PROJECT_ROOT / "output" / ".gate-responses"

from config.settings import GATE_RESPONSES_DIR  # NEW import

@mcp.tool()
async def waf_approve_gate(run_id: str, decision: str, feedback: str = "") -> str:
    ...
    gate_dir = GATE_RESPONSES_DIR   # ← use shared constant
    gate_dir.mkdir(parents=True, exist_ok=True)
    gate_file = gate_dir / f"{run_id}.json"
    ...
```

---

## State of the Art

| Old Approach | New Approach | Impact |
|--------------|--------------|--------|
| `asyncio.run(approve_gate(...))` in worker thread | `time.sleep` poll loop on file | Eliminates asyncio-in-thread risk; consistent with existing pattern |
| `mode='interactive'` tracked in ProgressStore only | Forwarded to `run_pipeline` as `interactive_mode=True` | Pipeline actually pauses |
| Two independent file paths | Single `GATE_RESPONSES_DIR` constant | No path mismatch |

---

## Open Questions

1. **Timeout for interactive gate polling**
   - What we know: `factory_mcp_server.approve_gate` uses `WEB_FACTORY_APPROVAL_TIMEOUT_SEC` env var (default 0 = no timeout)
   - What's unclear: Should the MCP gate poll use the same timeout, a separate one, or always no-timeout?
   - Recommendation: Default to no timeout (0) for interactive mode — human review has no defined deadline. Env var `WEB_FACTORY_APPROVAL_TIMEOUT_SEC` should apply consistently.

2. **Behavior when `waf_approve_gate` is called before the pipeline reaches the gate**
   - What we know: The gate file is written immediately; the poll loop will find it on first check
   - What's unclear: Could an early write for run A be consumed as the response for a different gate pause?
   - Recommendation: The file is keyed by `run_id`, not by `phase_id`. There is currently only one gate per run (Phase 3 mcp_approval). If multiple gates per run become possible, the file key should be `{run_id}-{phase_id}.json`. For Phase 14 scope with a single gate, `{run_id}.json` is sufficient.

3. **`_run_gate_checks` receives `on_progress` callback**
   - What we know: Currently does not receive it; `run_pipeline` has it
   - Recommendation: Pass it in. The signature change is backward-compatible with default=None. The planner should add this to the implementation task.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_mcp_tools.py tests/test_pipeline_bridge.py tests/test_mcp_approval_gate.py -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOOL-03 | `_pipeline_bridge` forwards `mode='interactive'` as `interactive_mode=True` to `run_pipeline` | unit | `uv run pytest tests/test_pipeline_bridge.py -k interactive -x` | ❌ Wave 0 |
| TOOL-03 | Pipeline pauses at `mcp_approval` gate when `interactive_mode=True` | unit | `uv run pytest tests/test_contract_runner.py -k interactive -x` | ❌ Wave 0 |
| TOOL-03 | `waf_approve_gate` write path and `mcp_approval_gate` poll path use same `GATE_RESPONSES_DIR` | unit | `uv run pytest tests/test_mcp_tools.py -k approve -x` | ✅ exists (needs update) |
| TOOL-03 | Calling `waf_approve_gate(action='approve')` unblocks pipeline | integration | `uv run pytest tests/test_interactive_gate_flow.py -x` | ❌ Wave 0 |
| TOOL-03 | Calling `waf_approve_gate(action='reject')` stops pipeline with rejection status | unit | `uv run pytest tests/test_contract_runner.py -k reject -x` | ❌ Wave 0 |
| TOOL-03 | Auto mode returns error (no silent failure) | unit | `uv run pytest tests/test_mcp_tools.py::TestWafApproveGate::test_auto_mode_returns_error -x` | ✅ exists |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_mcp_tools.py tests/test_pipeline_bridge.py tests/test_mcp_approval_gate.py -q`
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_pipeline_bridge.py` — add `TestInteractiveModeForwarded` class covering `interactive_mode=True` in `pipeline_kwargs`
- [ ] `tests/test_contract_runner.py` — add `TestInteractiveGate` class covering pause/unblock/reject paths (mock `run_mcp_approval_gate` with short poll)
- [ ] `tests/test_interactive_gate_flow.py` — new integration test: write gate file after a short delay, verify pipeline completes (uses threading; must mock actual phase execution)
- [ ] `tests/test_mcp_approval_gate.py` — add `TestPollMcpGateFile` class covering file-read, timeout, reject, missing-run-id paths

---

## Sources

### Primary (HIGH confidence)

- Direct source code inspection: `web_app_factory/mcp_server.py`, `web_app_factory/_pipeline_bridge.py`, `web_app_factory/_progress_store.py`, `tools/contract_pipeline_runner.py`, `tools/gates/mcp_approval_gate.py`, `tools/factory_mcp_server.py`, `config/settings.py`
- `.planning/v2.0-MILESTONE-AUDIT.md` — BREAK-01 and BREAK-02 documented with exact evidence
- `tests/test_mcp_tools.py`, `tests/test_pipeline_bridge.py`, `tests/test_mcp_approval_gate.py` — existing test baseline confirmed (51 tests pass)

### Secondary (MEDIUM confidence)

- Phase 11 VERIFICATION.md — confirms what was and was not implemented in the MCP tool layer

---

## Metadata

**Confidence breakdown:**
- Gap analysis: HIGH — gaps confirmed by reading exact source code; matches milestone audit
- Fix pattern: HIGH — file-based polling is already used by `factory_mcp_server.approve_gate`; pattern is proven in this codebase
- Threading safety: HIGH — `time.sleep` poll in worker thread is the established pattern here; no new threading primitives needed
- Test strategy: HIGH — existing test infrastructure is solid; identified exactly which tests need to be added

**Research date:** 2026-03-24
**Valid until:** N/A — this is internal codebase research, not external API research
