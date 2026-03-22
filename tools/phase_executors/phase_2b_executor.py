# SPDX-License-Identifier: MIT
"""Phase 2b executor: Code Generation.

Drives the build agent to generate all pages, components, and API routes
from the PRD and screen specification produced in Phase 1b.

Four-step approach per CONTEXT.md locked decisions:
  Step 1 (load_spec): Read docs/pipeline/prd.md and docs/pipeline/screen-spec.json
    from ctx.project_dir. Both files are Phase 1b outputs. If either is missing,
    return PhaseResult(success=False) immediately with a descriptive error.
  Step 2 (generate_code): Build a user prompt that includes the full content of
    both spec files and instructs the build agent on generation order, error.tsx
    placement (BILD-06), and mobile-first responsive design. Call run_build_agent().
  Step 3 (validate_packages): After agent completes, check if package.json has
    new dependencies. Call validate_npm_packages() for any extras. Log results
    but do NOT fail — the build gate will catch actual build failures.
  Step 4 (self_assess): Generate quality self-assessment.

Self-registers in the executor registry at module import time so
contract_pipeline_runner.py only needs to import this module once.

Security note: all file paths are rooted in project_dir which is resolved
and validated by PhaseContext.__post_init__. The build agent is sandboxed
to the generated project directory via cwd in ClaudeAgentOptions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from agents.definitions import BUILD_AGENT
from tools.phase_executors.base import PhaseContext, PhaseExecutor, PhaseResult, SubStepResult
from tools.phase_executors.build_agent_runner import (
    build_phase_system_prompt,
    load_phase_quality_criteria,
    run_build_agent,
)
from tools.phase_executors.phase_1a_executor import validate_npm_packages
from tools.phase_executors.registry import get_executor, register
from tools.quality_self_assessment import generate_quality_self_assessment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default contract path (absolute — resolves relative to this file)
# ---------------------------------------------------------------------------
_DEFAULT_CONTRACT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "contracts"
    / "pipeline-contract.web.v1.yaml"
)

# Phase 1b output paths relative to project_dir
_PRD_PATH = Path("docs") / "pipeline" / "prd.md"
_SCREEN_SPEC_PATH = Path("docs") / "pipeline" / "screen-spec.json"

# Baseline create-next-app packages (always present — not "extra")
_SCAFFOLD_PACKAGES = frozenset({
    "next",
    "react",
    "react-dom",
    "typescript",
    "tailwindcss",
    "postcss",
    "autoprefixer",
    "@types/node",
    "@types/react",
    "@types/react-dom",
    "eslint",
    "eslint-config-next",
})


# ---------------------------------------------------------------------------
# Phase 2b Executor
# ---------------------------------------------------------------------------


class Phase2bBuildExecutor(PhaseExecutor):
    """Executor for Phase 2b: Code Generation.

    Uses the build agent to generate all pages, components, and API routes
    from the PRD and screen specification produced in Phase 1b.
    """

    @property
    def phase_id(self) -> str:
        """Phase ID for Phase 2b."""
        return "2b"

    @property
    def sub_steps(self) -> list:
        """Ordered sub-steps for Phase 2b."""
        return ["load_spec", "generate_code", "validate_packages", "self_assess"]

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        """Execute Phase 2b: generate all code from PRD and screen spec.

        Step 1: Load docs/pipeline/prd.md and docs/pipeline/screen-spec.json.
          Return failure immediately if either is missing.
        Step 2: Build a user prompt embedding full spec content, call run_build_agent().
        Step 3: Validate npm packages extracted from package.json against registry.
          Log results but do NOT fail — build gate catches real failures.
        Step 4: Generate quality self-assessment.

        Args:
            ctx: Phase execution context with idea, app_name, project_dir.

        Returns:
            PhaseResult with success=True and artifacts list on success,
            or success=False with error message on failure.
        """
        sub_step_results: list[SubStepResult] = []

        # ── Step 1: Load spec files ────────────────────────────────────────
        prd_result, prd_content, screen_spec_content = self._load_spec_files(ctx)
        sub_step_results.append(prd_result)

        if not prd_result.success:
            return PhaseResult(
                phase_id="2b",
                success=False,
                error=prd_result.error,
                sub_steps=sub_step_results,
            )

        # ── Derive Next.js project directory ──────────────────────────────
        # ctx.project_dir is the pipeline root (e.g. /runs/abc/pipeline-root).
        # create-next-app places the generated project at a sibling directory
        # named after ctx.app_name (same pattern used in Phase 2a).
        nextjs_dir = ctx.project_dir.parent / ctx.app_name

        # ── Step 2: Generate code via build agent ──────────────────────────
        contract_path = Path(
            ctx.extra.get("contract_path", str(_DEFAULT_CONTRACT_PATH))
        )
        quality_criteria = load_phase_quality_criteria("2b", contract_path)
        system_prompt = build_phase_system_prompt(
            BUILD_AGENT.system_prompt, quality_criteria
        )

        user_prompt = self._build_generation_prompt(ctx, prd_content, screen_spec_content)

        agent_result = run_build_agent(
            prompt=user_prompt,
            system_prompt=system_prompt,
            project_dir=str(nextjs_dir),
        )

        if not agent_result:
            sub_step_results.append(
                SubStepResult(
                    sub_step_id="generate_code",
                    success=False,
                    error="Build agent returned empty result during Phase 2b code generation",
                )
            )
            return PhaseResult(
                phase_id="2b",
                success=False,
                error="Build agent returned empty result during Phase 2b code generation",
                sub_steps=sub_step_results,
            )

        sub_step_results.append(
            SubStepResult(
                sub_step_id="generate_code",
                success=True,
                notes="Build agent completed code generation",
            )
        )

        # ── Step 3: Validate npm packages ─────────────────────────────────
        npm_results = self._validate_extra_npm_packages(nextjs_dir)
        sub_step_results.append(
            SubStepResult(
                sub_step_id="validate_packages",
                success=True,
                notes=f"npm package validation results: {npm_results}",
            )
        )

        # ── Step 4: Generate quality self-assessment ───────────────────────
        try:
            generate_quality_self_assessment(
                phase_id="2b",
                project_dir=str(nextjs_dir),
                contract_path=str(contract_path),
            )
        except Exception as exc:
            logger.warning("Quality self-assessment generation failed: %s", type(exc).__name__)

        sub_step_results.append(
            SubStepResult(
                sub_step_id="self_assess",
                success=True,
                notes="Quality self-assessment generated",
            )
        )

        # ── Return success ─────────────────────────────────────────────────
        return PhaseResult(
            phase_id="2b",
            success=True,
            artifacts=[str(nextjs_dir)],
            sub_steps=sub_step_results,
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _load_spec_files(
        self, ctx: PhaseContext
    ) -> tuple[SubStepResult, str, str]:
        """Load PRD and screen-spec.json from project_dir.

        Returns (sub_step_result, prd_content, screen_spec_content).
        If either file is missing, sub_step_result.success is False and
        both content strings are empty.
        """
        prd_path = ctx.project_dir / _PRD_PATH
        spec_path = ctx.project_dir / _SCREEN_SPEC_PATH

        if not prd_path.exists():
            return (
                SubStepResult(
                    sub_step_id="load_spec",
                    success=False,
                    error=(
                        f"Phase 2b requires docs/pipeline/prd.md but it was not found. "
                        f"Expected at: {prd_path}"
                    ),
                ),
                "",
                "",
            )

        if not spec_path.exists():
            return (
                SubStepResult(
                    sub_step_id="load_spec",
                    success=False,
                    error=(
                        f"Phase 2b requires docs/pipeline/screen-spec.json but it was not found. "
                        f"Expected at: {spec_path}"
                    ),
                ),
                "",
                "",
            )

        try:
            prd_content = prd_path.read_text(encoding="utf-8")
        except OSError as exc:
            return (
                SubStepResult(
                    sub_step_id="load_spec",
                    success=False,
                    error=f"Failed to read prd.md: {type(exc).__name__}",
                ),
                "",
                "",
            )

        try:
            screen_spec_content = spec_path.read_text(encoding="utf-8")
        except OSError as exc:
            return (
                SubStepResult(
                    sub_step_id="load_spec",
                    success=False,
                    error=f"Failed to read screen-spec.json: {type(exc).__name__}",
                ),
                "",
                "",
            )

        return (
            SubStepResult(
                sub_step_id="load_spec",
                success=True,
                artifacts=[str(prd_path), str(spec_path)],
                notes="PRD and screen-spec.json loaded successfully",
            ),
            prd_content,
            screen_spec_content,
        )

    def _build_generation_prompt(
        self, ctx: PhaseContext, prd_content: str, screen_spec_content: str
    ) -> str:
        """Construct the user-facing prompt for the build agent.

        Embeds full PRD and screen-spec content — the build agent needs the
        actual content, not just file paths (per CONTEXT.md pattern).

        Instructs:
        - Generation order: shared components first, then pages route-by-route
        - error.tsx per route segment with async data dependencies (BILD-06)
        - Mobile-first responsive Tailwind classes

        Args:
            ctx: Phase execution context.
            prd_content: Full text content of docs/pipeline/prd.md.
            screen_spec_content: Full text content of docs/pipeline/screen-spec.json.

        Returns:
            Formatted user prompt string.
        """
        return f"""\
You are executing Phase 2b: Code Generation.

App name: {ctx.app_name}
App idea: {ctx.idea}

## Phase 1b Context: PRD

{prd_content}

## Phase 1b Context: Screen Specification

```json
{screen_spec_content}
```

## Generation Instructions

**Generation order (MUST follow this order):**
1. Create shared components first — implement every component listed in the \
## Component Inventory section of the PRD above. Place them in \
`src/components/`. Each shared component must be fully typed with TypeScript \
interfaces for all props.
2. Then generate pages page-by-page following the screen-spec.json route order \
above. For each route, create the corresponding `src/app/<route>/page.tsx`.

**Error boundaries (BILD-06 requirement — MUST follow for every route segment):**
For every route segment that has async data dependencies (loading states in \
screen-spec.json), create TWO additional files in that route segment:
- `error.tsx` — MUST start with `"use client"` directive. This is an error \
boundary component with `error` and `reset` props.
- `not-found.tsx` — Server component (NO "use client"). Returns a 404 UI.

Example for a route `/dashboard` with async data:
```
src/app/dashboard/page.tsx        ← the page (Server Component)
src/app/dashboard/error.tsx       ← "use client" error boundary (REQUIRED)
src/app/dashboard/not-found.tsx   ← server component 404 handler (REQUIRED)
```

**Responsive design (BILD-05):**
Use mobile-first Tailwind CSS classes throughout:
- Base classes apply to mobile (smallest viewport)
- `md:` prefix for tablet breakpoint (768px+)
- `lg:` prefix for desktop breakpoint (1024px+)
Example: `className="flex flex-col md:flex-row lg:gap-8"`

**TypeScript rules:**
- All props must have explicit TypeScript interfaces or type aliases
- All function return types must be explicit
- No `@ts-ignore` or `as any`
- Enable strict mode — treat all type errors as blocking

Start with the shared components from the Component Inventory, then implement \
each page from the screen specification in route order.
"""

    def _validate_extra_npm_packages(self, project_dir: Path) -> dict[str, bool]:
        """Extract and validate npm packages not in the baseline scaffold.

        Reads package.json from project_dir, extracts all dependency and
        devDependency names, removes known scaffold packages, and calls
        validate_npm_packages() for the remainder.

        This is informational — results are logged but do NOT cause failure.
        The build gate will catch actual build failures from invalid packages.

        Args:
            project_dir: Root of the generated Next.js project.

        Returns:
            Dict mapping extra package names to their registry validation result.
            Returns an empty dict if package.json is missing or malformed.
        """
        pkg_path = project_dir / "package.json"
        if not pkg_path.exists():
            return {}

        try:
            pkg_data: dict[str, Any] = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

        all_deps: set[str] = set()
        for dep_key in ("dependencies", "devDependencies"):
            for name in pkg_data.get(dep_key, {}).keys():
                all_deps.add(name)

        # Filter out baseline scaffold packages to find only extras
        extra_packages = sorted(all_deps - _SCAFFOLD_PACKAGES)

        if not extra_packages:
            return {}

        results = validate_npm_packages(extra_packages)
        # Log results for observability
        for pkg, exists in results.items():
            if not exists:
                logger.warning(
                    "Phase 2b: npm package %r not found in registry — "
                    "may cause npm install failure",
                    pkg,
                )
        return results


# ---------------------------------------------------------------------------
# Self-registration — runs at module import time (and on importlib.reload)
# ---------------------------------------------------------------------------
# Guard: only register if not already registered. This allows tests to clear
# the registry and re-trigger registration via importlib.reload() without
# hitting the "duplicate registration" error on the first import.
if get_executor("2b") is None:
    register(Phase2bBuildExecutor())
