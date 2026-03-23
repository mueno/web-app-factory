# SPDX-License-Identifier: MIT
"""Phase 1a executor: Idea Validation and Technical Feasibility.

Calls the spec agent via the Claude Agent SDK to produce:
- docs/pipeline/idea-validation.md  (competitor analysis, target user, Go/No-Go)
- docs/pipeline/tech-feasibility-memo.json (rendering strategy, npm-validated packages)

Self-registers in the executor registry at module import time so
contract_pipeline_runner.py only needs to import this module once.

Security note: all file paths are rooted in project_dir which is resolved
and validated by PhaseContext.__post_init__. Executor never executes shell
commands; the spec agent is restricted to WebSearch/Read/Write tools.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from agents.definitions import SPEC_AGENT
from tools.phase_executors.base import PhaseContext, PhaseExecutor, PhaseResult, SubStepResult
from tools.phase_executors.registry import get_executor, register
from tools.phase_executors.spec_agent_runner import (
    build_phase_system_prompt,
    load_phase_quality_criteria,
    run_spec_agent,
)


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default contract path (absolute — resolves relative to this file)
# ---------------------------------------------------------------------------
_DEFAULT_CONTRACT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "contracts"
    / "pipeline-contract.web.v1.yaml"
)

# Expected deliverable paths relative to project_dir
_IDEA_VALIDATION_PATH = Path("docs") / "pipeline" / "idea-validation.md"
_FEASIBILITY_MEMO_PATH = Path("docs") / "pipeline" / "tech-feasibility-memo.json"

# npm registry base URL for package validation
_NPM_REGISTRY_BASE = "https://registry.npmjs.org"


# ---------------------------------------------------------------------------
# Module-level npm validation utility (Phase 1a specific)
# ---------------------------------------------------------------------------


def validate_npm_packages(packages: list[str]) -> dict[str, bool]:
    """Check each package name against the npm registry.

    Performs HTTP GET to https://registry.npmjs.org/{pkg}/latest for each
    package. Returns True if the response status is 200, False otherwise.

    This is a synchronous wrapper around async httpx calls, consistent with
    the asyncio.run() bridge pattern used in spec_agent_runner.py.

    Args:
        packages: List of npm package names to validate.

    Returns:
        Dict mapping each package name to True (exists) or False (not found).
    """

    async def _check_all() -> dict[str, bool]:
        results: dict[str, bool] = {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            for pkg in packages:
                url = f"{_NPM_REGISTRY_BASE}/{pkg}/latest"
                try:
                    response = await client.get(url)
                    results[pkg] = response.status_code == 200
                except Exception:
                    results[pkg] = False
        return results

    return asyncio.run(_check_all())


# ---------------------------------------------------------------------------
# Phase 1a Executor
# ---------------------------------------------------------------------------


class Phase1aSpecExecutor(PhaseExecutor):
    """Executor for Phase 1a: Idea Validation and Technical Feasibility.

    Uses the spec agent to research competitors, analyze market fit, and
    produce structured deliverables for Go/No-Go decision-making.
    """

    @property
    def phase_id(self) -> str:
        """Phase ID for Phase 1a."""
        return "1a"

    @property
    def sub_steps(self) -> list:
        """Ordered sub-steps for Phase 1a."""
        return [
            "research",
            "analyze",
            "write_validation",
            "write_feasibility",
        ]

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        """Execute Phase 1a: produce idea-validation.md and tech-feasibility-memo.json.

        Orchestrates the spec agent to:
        1. Research competitors via WebSearch
        2. Analyze market fit and target users
        3. Write idea-validation.md with structured sections
        4. Write tech-feasibility-memo.json with rendering strategy
        5. Validate npm packages referenced in the memo
        6. Generate quality self-assessment

        Args:
            ctx: Phase execution context with idea, app_name, project_dir.

        Returns:
            PhaseResult with success=True and artifacts list on success,
            or success=False with error message on failure.
        """
        sub_step_results: list[SubStepResult] = []

        # ── Resolve contract path ──────────────────────────────────────────
        contract_path = Path(
            ctx.extra.get("contract_path", str(_DEFAULT_CONTRACT_PATH))
        )

        # ── Step 1: Load quality criteria and build system prompt ──────────
        quality_criteria = load_phase_quality_criteria("1a", contract_path)
        system_prompt = build_phase_system_prompt(
            SPEC_AGENT.system_prompt, quality_criteria
        )
        sub_step_results.append(
            SubStepResult(
                sub_step_id="research",
                success=True,
                notes="Quality criteria loaded and system prompt constructed",
            )
        )

        # ── Step 2: Build user prompt ──────────────────────────────────────
        user_prompt = self._build_user_prompt(ctx)
        sub_step_results.append(
            SubStepResult(
                sub_step_id="analyze",
                success=True,
                notes="User prompt constructed",
            )
        )

        # ── Step 3: Run spec agent ─────────────────────────────────────────
        agent_result = run_spec_agent(
            prompt=user_prompt,
            system_prompt=system_prompt,
            project_dir=str(ctx.project_dir),
        )

        if not agent_result:
            return PhaseResult(
                phase_id="1a",
                success=False,
                error="Spec agent returned empty result for Phase 1a",
                sub_steps=sub_step_results,
            )

        # ── Step 4: Validate deliverables exist on disk ────────────────────
        deliverables_ok, missing = self._validate_deliverables(ctx.project_dir)

        if not deliverables_ok:
            sub_step_results.append(
                SubStepResult(
                    sub_step_id="write_validation",
                    success=False,
                    error=f"Missing deliverables after agent run: {missing}",
                )
            )
            return PhaseResult(
                phase_id="1a",
                success=False,
                error=f"Phase 1a deliverables not produced: {missing}",
                sub_steps=sub_step_results,
            )

        sub_step_results.append(
            SubStepResult(
                sub_step_id="write_validation",
                success=True,
                artifacts=[str(ctx.project_dir / _IDEA_VALIDATION_PATH)],
            )
        )

        # ── Step 5: Validate npm packages in feasibility memo ──────────────
        memo_path = ctx.project_dir / _FEASIBILITY_MEMO_PATH
        npm_results = self._validate_npm_packages_in_memo(memo_path)

        sub_step_results.append(
            SubStepResult(
                sub_step_id="write_feasibility",
                success=True,
                artifacts=[str(memo_path)],
                notes=f"npm validation results: {npm_results}",
            )
        )

        # ── Return success ─────────────────────────────────────────────────
        # Quality self-assessment is generated by contract_pipeline_runner (CONT-04)
        artifacts = [
            str(ctx.project_dir / _IDEA_VALIDATION_PATH),
            str(ctx.project_dir / _FEASIBILITY_MEMO_PATH),
        ]

        return PhaseResult(
            phase_id="1a",
            success=True,
            artifacts=artifacts,
            sub_steps=sub_step_results,
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _build_user_prompt(self, ctx: PhaseContext) -> str:
        """Construct the user-facing prompt for the spec agent.

        Instructs the agent to research competitors, validate the idea, and
        write both deliverables to the expected file paths.

        Args:
            ctx: Phase execution context.

        Returns:
            Formatted user prompt string.
        """
        return f"""\
You are executing Phase 1a: Idea Validation and Technical Feasibility.

App idea: {ctx.idea}
App name: {ctx.app_name}

Your tasks:
1. Use WebSearch to research at least 3 real competitors for this app idea.
   Search for "[app category] web app", "[problem] software", and current market data.
   Do NOT rely on training data for competitor names — use WebSearch.

2. Analyze market fit, target user persona, and differentiation opportunities.

3. Write the file `docs/pipeline/idea-validation.md` with these exact sections:
   - ## Competitors (at least 3 named competitors with feature comparisons)
   - ## Target User (persona with age range, occupation, concrete pain point)
   - ## Differentiation (derived from competitor gap analysis)
   - ## Risks (at least 3 risks with specific mitigation strategies)
   - ## Market Size (quantitative estimate with source)
   - ## Go/No-Go (must include exactly one of: `go_no_go: Go` or `go_no_go: No-Go`)

4. Write the file `docs/pipeline/tech-feasibility-memo.json` as valid JSON with keys:
   - "rendering_strategy": object with "recommendation" (SSR/SSG/ISR), "rationale", "alternatives_considered"
   - "packages": list of objects with "name", "version", "purpose" (use real, existing npm packages)
   - "external_apis": list of API dependencies with rate limits / cost implications
   - "vercel_constraints": object noting serverless timeout and bundle size implications
   - "browser_apis": list of required browser APIs with fallback strategies

5. Validate every npm package in the "packages" list against registry.npmjs.org to confirm
   it exists. Only include packages that are real and actively maintained.

Write both files to the `docs/pipeline/` directory relative to your working directory.
Produce substantive, detailed content — the downstream build agent depends on this analysis.
"""

    def _validate_deliverables(
        self, project_dir: Path
    ) -> tuple[bool, list[str]]:
        """Check that both expected deliverable files exist on disk.

        Args:
            project_dir: Root of the project being built.

        Returns:
            Tuple of (all_present: bool, missing_paths: list[str]).
        """
        missing: list[str] = []
        for rel_path in [_IDEA_VALIDATION_PATH, _FEASIBILITY_MEMO_PATH]:
            if not (project_dir / rel_path).exists():
                missing.append(str(rel_path))
        return (len(missing) == 0, missing)

    def _validate_npm_packages_in_memo(
        self, memo_path: Path
    ) -> dict[str, bool]:
        """Parse the feasibility memo and validate npm packages.

        Extracts the "packages" array from the JSON memo and calls
        validate_npm_packages() for each package name found.

        Args:
            memo_path: Path to tech-feasibility-memo.json.

        Returns:
            Dict mapping package names to their validation result.
            Returns an empty dict if the memo is missing or malformed.
        """
        if not memo_path.exists():
            return {}

        try:
            memo: dict[str, Any] = json.loads(memo_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

        packages_raw: list[Any] = memo.get("packages", [])
        package_names: list[str] = []
        for entry in packages_raw:
            if isinstance(entry, dict) and "name" in entry:
                package_names.append(str(entry["name"]))
            elif isinstance(entry, str):
                package_names.append(entry)

        if not package_names:
            return {}

        return validate_npm_packages(package_names)


# ---------------------------------------------------------------------------
# Self-registration — runs at module import time (and on importlib.reload)
# ---------------------------------------------------------------------------
# Guard: only register if not already registered. This allows tests to clear
# the registry and re-trigger registration via importlib.reload() without
# hitting the "duplicate registration" error on the first import.
if get_executor("1a") is None:
    register(Phase1aSpecExecutor())
