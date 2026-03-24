# SPDX-License-Identifier: MIT
"""Phase 2b executor: Code Generation.

Drives the build agent to generate all pages, components, and API routes
from the PRD and screen specification produced in Phase 1b.

Five-step approach per QUAL-01 (Phase 13):
  Step 1 (load_spec): Read docs/pipeline/prd.md and docs/pipeline/screen-spec.json
    from ctx.project_dir. Both files are Phase 1b outputs. If either is missing,
    return PhaseResult(success=False) immediately with a descriptive error.
  Step 2 (generate_shared_components): Build a focused prompt for shared component
    generation only. Call run_build_agent() with a prompt targeting src/components/
    and NOT page or route creation.
  Step 3 (generate_pages): Build a focused prompt for page generation. Informs the
    agent that shared components already exist and instructs route-by-route page
    creation from screen-spec.json. Includes BILD-06 error.tsx requirements.
  Step 4 (generate_integration): Build a focused integration prompt for verifying
    cross-page URLSearchParams contracts in src/lib/types.ts. Does NOT embed PRD
    or screen-spec content (prevents agent from re-generating already-written files —
    see RESEARCH.md Pitfall 2).
  Step 5 (validate_packages): After all agent calls complete, check if package.json
    has new dependencies. Call validate_npm_packages() for any extras. Log results
    but do NOT fail — the build gate will catch actual build failures.

Each generation sub-step sets PhaseResult.resume_point on failure, enabling
checkpoint-based resumption via ctx.resume_sub_step + _start_index().

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
# Focused prompt templates (module-level constants per QUAL-01)
# ---------------------------------------------------------------------------

# Sub-step 2: shared components only — do NOT create pages or routes yet
_SHARED_COMPONENTS_PROMPT_TEMPLATE = """\
You are executing Phase 2b Step 1: Shared Component Generation.

App name: {app_name}
App idea: {idea}

## Phase 1b Context: PRD

{prd_content}

## Generation Instructions

**CRITICAL: Generate ONLY shared components. Do NOT create any pages or routes.**

Generate every component listed in the ## Component Inventory section of the PRD above.
Place each component in `src/components/<ComponentName>.tsx`.

Rules:
- Each shared component must be fully typed with TypeScript interfaces for all props.
- All props must have explicit TypeScript interfaces or type aliases.
- All function return types must be explicit.
- No `@ts-ignore` or `as any`.
- Enable strict mode — treat all type errors as blocking.

Do NOT create `src/app/` pages or routes. Do NOT create API routes.
Only `src/components/` files should be generated in this step.

**Data security (when PRD includes a Data Security section — MUST follow):**
The scaffold already provides `src/lib/crypto.ts` and `src/lib/password.ts`.
Use them — do NOT implement your own encryption or hashing.

Generate all shared components from the Component Inventory now.
"""

# Sub-step 3: pages only — shared components already exist
_PAGES_PROMPT_TEMPLATE = """\
You are executing Phase 2b Step 2: Page Generation.

App name: {app_name}
App idea: {idea}

The shared components in `src/components/` are already generated from the previous step.
Do NOT re-create or overwrite shared components.

## Phase 1b Context: Screen Specification

```json
{screen_spec_content}
```

## Generation Instructions

Now implement each page listed in the screen-spec.json above in route order.
For each route, create the corresponding `src/app/<route>/page.tsx`.

**Error boundaries (BILD-06 requirement — MUST follow for every route segment):**
For every route segment that has async data dependencies (loading states in
screen-spec.json), create TWO additional files in that route segment:
- `error.tsx` — MUST start with `"use client"` directive. This is an error
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

**Cross-page data flow contracts (CRITICAL — most common source of bugs):**
When a form or component navigates to another page with URL search parameters
(via `router.push`, `<Link>`, or `URLSearchParams`), you MUST:
1. Define a shared TypeScript interface in `src/lib/types.ts` for the parameter
   schema (e.g., `SimulationSearchParams`).
2. The sending component MUST construct URLSearchParams using the EXACT field
   names defined in that interface.
3. The receiving page MUST read `searchParams` using the EXACT same field names.
4. NEVER invent different parameter names on the sending vs receiving side.

**TypeScript rules:**
- All props must have explicit TypeScript interfaces or type aliases.
- All function return types must be explicit.
- No `@ts-ignore` or `as any`.
- Enable strict mode — treat all type errors as blocking.

Generate each page from the screen specification in route order now.
"""

# Sub-step 4: integration pass — verify cross-page URLSearchParams contracts
# IMPORTANT: Do NOT embed PRD or screen-spec content here (RESEARCH.md Pitfall 2)
_INTEGRATION_PROMPT_TEMPLATE = """\
You are executing Phase 2b Step 3: Integration Verification.

App name: {app_name}
App idea: {idea}

The pages and components have already been generated in the previous steps.
This step is a focused integration pass ONLY — do NOT re-create or overwrite
any files that were already generated.

## Integration Task

Verify and fix URLSearchParams mismatches between form-sending pages and
receiving pages. Specifically:

1. Check that `src/lib/types.ts` defines shared TypeScript parameter interfaces
   for every form submission or `router.push` call that passes query parameters.
2. Verify that the sending component constructs URLSearchParams using the EXACT
   field names defined in the `src/lib/types.ts` interfaces.
3. Verify that the receiving page reads `searchParams` using the EXACT same
   field names.
4. If any mismatches are found, fix them in ALL places (both sender and receiver
   must use identical key names).

Example of what to look for:
```typescript
// src/lib/types.ts
export interface SimulationSearchParams {{
  originCity: string;  // ← both sender and receiver must use 'originCity'
}}

// Form (sender) — must use the interface field names
router.push(`/results?${{params.toString()}}`);

// Result page (receiver) — must use the same field names
const originCity = searchParams.originCity;
```

Focus ONLY on `src/lib/types.ts` and cross-page parameter contracts.
Do NOT re-implement components or pages.
"""


# ---------------------------------------------------------------------------
# Phase 2b Executor
# ---------------------------------------------------------------------------


class Phase2bBuildExecutor(PhaseExecutor):
    """Executor for Phase 2b: Code Generation.

    Uses three sequential build agent calls to generate shared components,
    pages, and verify integration contracts — each with a focused prompt.
    Supports checkpoint-based resumption via ctx.resume_sub_step.
    """

    @property
    def phase_id(self) -> str:
        """Phase ID for Phase 2b."""
        return "2b"

    @property
    def sub_steps(self) -> list:
        """Ordered sub-steps for Phase 2b (5 steps, QUAL-01)."""
        return [
            "load_spec",
            "generate_shared_components",
            "generate_pages",
            "generate_integration",
            "validate_packages",
        ]

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        """Execute Phase 2b: generate all code from PRD and screen spec.

        Step 1: Load docs/pipeline/prd.md and docs/pipeline/screen-spec.json.
          Return failure immediately if either is missing.
        Step 2: Generate shared components only via focused prompt.
        Step 3: Generate pages route-by-route (references existing components).
        Step 4: Verify integration — fix URLSearchParams cross-page contracts.
        Step 5: Validate npm packages extracted from package.json against registry.
          Log results but do NOT fail — build gate catches real failures.

        Resume: ctx.resume_sub_step causes _start_index() to skip earlier sub-steps.

        Args:
            ctx: Phase execution context with idea, app_name, project_dir.

        Returns:
            PhaseResult with success=True and artifacts list on success,
            or success=False with error message and resume_point on failure.
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

        # ── Load quality criteria + system prompt once (shared across calls) ─
        contract_path = Path(
            ctx.extra.get("contract_path", str(_DEFAULT_CONTRACT_PATH))
        )
        quality_criteria = load_phase_quality_criteria("2b", contract_path)
        system_prompt = build_phase_system_prompt(
            BUILD_AGENT.system_prompt, quality_criteria
        )

        # ── Determine resume start index ──────────────────────────────────
        # _start_index() maps ctx.resume_sub_step to the sub_steps list index.
        # sub_steps indices: 0=load_spec, 1=generate_shared_components,
        #                    2=generate_pages, 3=generate_integration,
        #                    4=validate_packages
        start_idx = self._start_index(ctx)

        # ── Step 2: Generate shared components ────────────────────────────
        if start_idx <= 1:
            shared_prompt = _SHARED_COMPONENTS_PROMPT_TEMPLATE.format(
                app_name=ctx.app_name,
                idea=ctx.idea,
                prd_content=prd_content,
            )
            shared_result = run_build_agent(
                prompt=shared_prompt,
                system_prompt=system_prompt,
                project_dir=str(nextjs_dir),
            )

            if not shared_result:
                sub_step_results.append(
                    SubStepResult(
                        sub_step_id="generate_shared_components",
                        success=False,
                        error="Build agent returned empty result during shared component generation",
                    )
                )
                return PhaseResult(
                    phase_id="2b",
                    success=False,
                    error="Build agent returned empty result during shared component generation",
                    sub_steps=sub_step_results,
                    resume_point="generate_shared_components",
                )

            sub_step_results.append(
                SubStepResult(
                    sub_step_id="generate_shared_components",
                    success=True,
                    artifacts=[str(nextjs_dir / "src" / "components")],
                    notes="Build agent generated shared components",
                )
            )

        # ── Step 3: Generate pages ─────────────────────────────────────────
        if start_idx <= 2:
            pages_prompt = _PAGES_PROMPT_TEMPLATE.format(
                app_name=ctx.app_name,
                idea=ctx.idea,
                screen_spec_content=screen_spec_content,
            )
            pages_result = run_build_agent(
                prompt=pages_prompt,
                system_prompt=system_prompt,
                project_dir=str(nextjs_dir),
            )

            if not pages_result:
                sub_step_results.append(
                    SubStepResult(
                        sub_step_id="generate_pages",
                        success=False,
                        error="Build agent returned empty result during page generation",
                    )
                )
                return PhaseResult(
                    phase_id="2b",
                    success=False,
                    error="Build agent returned empty result during page generation",
                    sub_steps=sub_step_results,
                    resume_point="generate_pages",
                )

            sub_step_results.append(
                SubStepResult(
                    sub_step_id="generate_pages",
                    success=True,
                    artifacts=[str(nextjs_dir / "src" / "app")],
                    notes="Build agent generated pages",
                )
            )

        # ── Step 4: Generate integration ──────────────────────────────────
        if start_idx <= 3:
            integration_prompt = _INTEGRATION_PROMPT_TEMPLATE.format(
                app_name=ctx.app_name,
                idea=ctx.idea,
            )
            integration_result = run_build_agent(
                prompt=integration_prompt,
                system_prompt=system_prompt,
                project_dir=str(nextjs_dir),
            )

            if not integration_result:
                sub_step_results.append(
                    SubStepResult(
                        sub_step_id="generate_integration",
                        success=False,
                        error="Build agent returned empty result during integration verification",
                    )
                )
                return PhaseResult(
                    phase_id="2b",
                    success=False,
                    error="Build agent returned empty result during integration verification",
                    sub_steps=sub_step_results,
                    resume_point="generate_integration",
                )

            sub_step_results.append(
                SubStepResult(
                    sub_step_id="generate_integration",
                    success=True,
                    artifacts=[str(nextjs_dir / "src" / "lib" / "types.ts")],
                    notes="Build agent verified cross-page parameter contracts",
                )
            )

        # ── Step 5: Validate npm packages ─────────────────────────────────
        npm_results = self._validate_extra_npm_packages(nextjs_dir)
        sub_step_results.append(
            SubStepResult(
                sub_step_id="validate_packages",
                success=True,
                notes=f"npm package validation results: {npm_results}",
            )
        )

        # ── Return success ─────────────────────────────────────────────────
        # Quality self-assessment is generated by contract_pipeline_runner (CONT-04)
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
