"""Async pipeline bridge for Web App Factory MCP server.

Provides a non-blocking wrapper around the synchronous ``run_pipeline``
function from ``tools.contract_pipeline_runner``.

Architecture:
    The MCP server runs in an asyncio event loop.  The pipeline is a
    long-running, CPU-bound process that must NOT block that loop.  This
    module solves the problem with the standard Python pattern:

        asyncio event loop
            └─ loop.run_in_executor(_EXECUTOR, ...)
                    └─ ThreadPoolExecutor (3 workers)
                            └─ run_pipeline(...)   # runs in a thread

References (from Phase 8 research, Pattern 2 / Pitfall 5):
  * Generate run_id BEFORE submitting to executor — prevents a subtle
    deadlock if the thread pool queue is full and submission blocks.
  * Use ThreadPoolExecutor with max_workers=3 (researched recommendation).
  * Store the Future in _ACTIVE_RUNS so callers can poll or await it.

Public API:
    start_pipeline_async(idea, project_dir, *, ...) -> str (run_id)

Internal:
    _EXECUTOR       — shared ThreadPoolExecutor
    _ACTIVE_RUNS    — dict[run_id, asyncio.Future]
    _generate_run_id(idea) -> str
    _run_pipeline_sync(**kwargs)  — thin wrapper; patched in tests
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── sys.path adjustment so 'tools' is importable when running from any cwd ──
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Module-level executor (3 workers per research recommendation) ────────────
_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="waf-pipeline")

# ── Active runs registry (bounded — completed futures are auto-removed) ──────
_ACTIVE_RUNS: dict[str, asyncio.Future] = {}
_MAX_ACTIVE_RUNS = 100  # safety cap to prevent unbounded memory growth


# ── Default contract path (used by bridge when no contract is provided) ──────
_DEFAULT_CONTRACT_PATH = _PROJECT_ROOT / "contracts" / "pipeline-contract.web.v1.yaml"

# ── Allowed contract directory (P1 security fix — path traversal prevention) ─
_CONTRACTS_DIR = (_PROJECT_ROOT / "contracts").resolve()


def _generate_run_id(idea: str) -> str:
    """Generate a run ID in the format YYYYMMDD-HHMMSS-<idea-slug>.

    Args:
        idea: Free-form idea string; converted to a URL-safe slug.

    Returns:
        String like "20240315-142301-recipe-app"
    """
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    # Create a slug: lowercase, replace non-alphanumeric with hyphens, strip
    slug = re.sub(r"[^a-z0-9]+", "-", idea.lower().strip())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    slug = slug[:30] or "pipeline"  # max 30 chars, fallback to "pipeline"
    return f"{timestamp}-{slug}"


def _run_pipeline_sync(**kwargs: Any) -> dict[str, Any]:
    """Thin synchronous wrapper around ``run_pipeline``.

    Separated from the main function so tests can patch this name without
    needing to reach into the ``tools`` package import machinery.

    This function is the sole import boundary between the bridge and the
    pipeline runner.  Patching ``web_app_factory._pipeline_bridge._run_pipeline_sync``
    in tests completely isolates the bridge from the real pipeline.
    """
    from tools.contract_pipeline_runner import run_pipeline  # noqa: PLC0415
    import yaml  # noqa: PLC0415

    # Load contract if not provided
    contract = kwargs.pop("contract", None)
    if contract is None:
        contract_path = kwargs.get("contract_path", str(_DEFAULT_CONTRACT_PATH))
        # P1 security: validate contract_path is under contracts/ directory
        resolved = Path(contract_path).resolve()
        try:
            resolved.relative_to(_CONTRACTS_DIR)
        except ValueError:
            raise ValueError(
                f"contract_path must be under {_CONTRACTS_DIR}, "
                f"got {resolved}"
            )
        with open(resolved, encoding="utf-8") as fh:
            contract = yaml.safe_load(fh)

    return run_pipeline(contract, **kwargs)


async def start_pipeline_async(
    idea: str,
    project_dir: str,
    *,
    deploy_target: str = "vercel",
    mode: str = "auto",
    contract_path: str | None = None,
    company_name: str | None = None,
    contact_email: str | None = None,
) -> str:
    """Start the pipeline in a background thread and return a run_id immediately.

    The MCP event loop is never blocked.  The pipeline runs in a thread from
    ``_EXECUTOR`` and the resulting Future is stored in ``_ACTIVE_RUNS``.

    Args:
        idea:           The app idea string (plain text description).
        project_dir:    Root directory for the project being built.
        deploy_target:  Deployment target ("vercel", "gcp", "aws").  Default "vercel".
        mode:           Pipeline execution mode ("auto", "dry_run").  Default "auto".
        contract_path:  Path to the pipeline contract YAML.  Defaults to
                        ``contracts/pipeline-contract.web.v1.yaml``.
        company_name:   Company name for legal document generation.
        contact_email:  Contact email for legal document generation.

    Returns:
        run_id: String identifier for this pipeline run, formatted as
                "YYYYMMDD-HHMMSS-<idea-slug>".  Callers use this to poll
                the run status via waf_get_status().
    """
    # Step 1: Generate run_id BEFORE submitting to executor (Pitfall 5: avoids
    # blocking if the thread pool queue is momentarily full).
    run_id = _generate_run_id(idea)

    # Step 2: Build kwargs for the synchronous pipeline function.
    pipeline_kwargs: dict[str, Any] = {
        "project_dir": project_dir,
        "idea": idea,
        "dry_run": (mode == "dry_run"),
    }
    if contract_path:
        pipeline_kwargs["contract_path"] = contract_path
    if company_name:
        pipeline_kwargs["company_name"] = company_name
    if contact_email:
        pipeline_kwargs["contact_email"] = contact_email
    pipeline_kwargs["deploy_target"] = deploy_target

    # Safety cap: reject if too many concurrent/completed runs are tracked
    if len(_ACTIVE_RUNS) >= _MAX_ACTIVE_RUNS:
        # Evict completed futures before rejecting
        _evict_completed_runs()
    if len(_ACTIVE_RUNS) >= _MAX_ACTIVE_RUNS:
        raise RuntimeError(
            f"Too many active pipeline runs ({_MAX_ACTIVE_RUNS}). "
            "Wait for existing runs to complete."
        )

    # Step 3: Submit to thread pool — returns immediately.
    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.run_in_executor(
        _EXECUTOR,
        lambda: _run_pipeline_sync(**pipeline_kwargs),
    )

    # Step 4: Track the future and register cleanup callback.
    _ACTIVE_RUNS[run_id] = future
    future.add_done_callback(lambda _f, _rid=run_id: _on_run_complete(_rid))

    return run_id


def _on_run_complete(run_id: str) -> None:
    """Callback invoked when a pipeline future completes. Removes from registry."""
    _ACTIVE_RUNS.pop(run_id, None)
    logger.debug("Pipeline run %s completed and removed from active registry", run_id)


def _evict_completed_runs() -> None:
    """Remove any completed futures from _ACTIVE_RUNS."""
    completed = [rid for rid, fut in _ACTIVE_RUNS.items() if fut.done()]
    for rid in completed:
        _ACTIVE_RUNS.pop(rid, None)
