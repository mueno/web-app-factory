# SPDX-License-Identifier: MIT
"""Phase 1b executor: PRD and Screen Specification.

Calls the spec agent via the Claude Agent SDK to produce:
- docs/pipeline/prd.md           (MoSCoW-labeled PRD with component inventory and route structure)
- docs/pipeline/screen-spec.json (machine-readable screen specification derived from prd.md)

Phase 1a output (idea-validation.md, tech-feasibility-memo.json) is loaded as
context and its CONTENT is embedded directly into the agent prompt so the agent
can refer to competitor analysis and tech constraints when writing the PRD.

The executor cross-validates that every component name listed in screen-spec.json
appears in prd.md's Component Inventory section, returning failure if names diverge.

Self-registers in the executor registry at module import time so
contract_pipeline_runner.py only needs to import this module once.

Security note: all file paths are rooted in project_dir which is resolved
and validated by PhaseContext.__post_init__. Executor never executes shell
commands; the spec agent is restricted to WebSearch/Read/Write tools.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

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
_PRD_PATH = Path("docs") / "pipeline" / "prd.md"
_SCREEN_SPEC_PATH = Path("docs") / "pipeline" / "screen-spec.json"

# Phase 1a context paths relative to project_dir
_IDEA_VALIDATION_PATH = Path("docs") / "pipeline" / "idea-validation.md"
_FEASIBILITY_MEMO_PATH = Path("docs") / "pipeline" / "tech-feasibility-memo.json"


# ---------------------------------------------------------------------------
# Phase 1b Executor
# ---------------------------------------------------------------------------


class Phase1bSpecExecutor(PhaseExecutor):
    """Executor for Phase 1b: PRD and Screen Specification.

    Uses the spec agent to produce a structured Product Requirements Document
    and a machine-readable screen specification JSON, using Phase 1a output
    as context for informed design decisions.
    """

    @property
    def phase_id(self) -> str:
        """Phase ID for Phase 1b."""
        return "1b"

    @property
    def sub_steps(self) -> list:
        """Ordered sub-steps for Phase 1b."""
        return [
            "load_context",
            "write_prd",
            "derive_screen_spec",
            "cross_validate",
        ]

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        """Execute Phase 1b: produce prd.md and screen-spec.json.

        Orchestrates the spec agent to:
        1. Load Phase 1a context (idea-validation.md, tech-feasibility-memo.json)
        2. Build augmented system prompt from SPEC_AGENT + quality criteria
        3. Construct user prompt with embedded Phase 1a content
        4. Call run_spec_agent() to produce both deliverables
        5. Validate deliverables exist on disk
        6. Cross-validate component names between prd.md and screen-spec.json
        7. Generate quality self-assessment

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

        # ── Step 1: Load Phase 1a context ──────────────────────────────────
        phase_1a_context = self._load_phase_1a_context(ctx.project_dir)
        sub_step_results.append(
            SubStepResult(
                sub_step_id="load_context",
                success=True,
                notes=f"Phase 1a context loaded: {list(phase_1a_context.keys())}",
            )
        )

        # ── Step 2: Load quality criteria and build system prompt ──────────
        quality_criteria = load_phase_quality_criteria("1b", contract_path)
        system_prompt = build_phase_system_prompt(
            SPEC_AGENT.system_prompt, quality_criteria
        )

        # ── Step 3: Build user prompt with embedded Phase 1a context ───────
        user_prompt = self._build_user_prompt(ctx, phase_1a_context)

        # ── Step 4: Run spec agent ─────────────────────────────────────────
        agent_result = run_spec_agent(
            prompt=user_prompt,
            system_prompt=system_prompt,
            project_dir=str(ctx.project_dir),
        )

        if not agent_result:
            return PhaseResult(
                phase_id="1b",
                success=False,
                error="Spec agent returned empty result for Phase 1b",
                sub_steps=sub_step_results,
            )

        # ── Step 5: Validate deliverables exist on disk ────────────────────
        deliverables_ok, missing = self._validate_deliverables(ctx.project_dir)

        if not deliverables_ok:
            sub_step_results.append(
                SubStepResult(
                    sub_step_id="write_prd",
                    success=False,
                    error=f"Missing deliverables after agent run: {missing}",
                )
            )
            return PhaseResult(
                phase_id="1b",
                success=False,
                error=f"Phase 1b deliverables not produced: {missing}",
                sub_steps=sub_step_results,
            )

        sub_step_results.append(
            SubStepResult(
                sub_step_id="write_prd",
                success=True,
                artifacts=[str(ctx.project_dir / _PRD_PATH)],
            )
        )
        sub_step_results.append(
            SubStepResult(
                sub_step_id="derive_screen_spec",
                success=True,
                artifacts=[str(ctx.project_dir / _SCREEN_SPEC_PATH)],
            )
        )

        # ── Step 6: Cross-validate component names ─────────────────────────
        cross_ok, mismatches = self._cross_validate_components(ctx.project_dir)

        if not cross_ok:
            sub_step_results.append(
                SubStepResult(
                    sub_step_id="cross_validate",
                    success=False,
                    error=f"Component name mismatches: {mismatches}",
                )
            )
            return PhaseResult(
                phase_id="1b",
                success=False,
                error=(
                    f"screen-spec.json contains components not found in prd.md "
                    f"Component Inventory: {mismatches}"
                ),
                sub_steps=sub_step_results,
            )

        sub_step_results.append(
            SubStepResult(
                sub_step_id="cross_validate",
                success=True,
                notes="All screen-spec.json component names found in prd.md inventory",
            )
        )

        # ── Return success ─────────────────────────────────────────────────
        # Quality self-assessment is generated by contract_pipeline_runner (CONT-04)
        artifacts = [
            str(ctx.project_dir / _PRD_PATH),
            str(ctx.project_dir / _SCREEN_SPEC_PATH),
        ]

        return PhaseResult(
            phase_id="1b",
            success=True,
            artifacts=artifacts,
            sub_steps=sub_step_results,
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _load_phase_1a_context(self, project_dir: Path) -> dict[str, str]:
        """Load Phase 1a output files and return their content as strings.

        Reads idea-validation.md and tech-feasibility-memo.json if they exist.
        Returns a dict with string content for embedding into the agent prompt.

        Args:
            project_dir: Root of the project being built.

        Returns:
            Dict with optional keys 'idea_validation' and 'tech_feasibility',
            each containing the raw file content as a string.
        """
        context: dict[str, str] = {}

        idea_path = project_dir / _IDEA_VALIDATION_PATH
        if idea_path.exists():
            try:
                context["idea_validation"] = idea_path.read_text(encoding="utf-8")
            except OSError:
                pass

        memo_path = project_dir / _FEASIBILITY_MEMO_PATH
        if memo_path.exists():
            try:
                context["tech_feasibility"] = memo_path.read_text(encoding="utf-8")
            except OSError:
                pass

        return context

    def _build_user_prompt(
        self, ctx: PhaseContext, phase_1a_context: dict[str, str]
    ) -> str:
        """Construct the user-facing prompt for the spec agent.

        Embeds Phase 1a content directly into the prompt text so the agent
        can use competitor analysis and tech constraints when writing the PRD.
        Instructs prd.md to be written FIRST, then screen-spec.json derived.

        Args:
            ctx: Phase execution context.
            phase_1a_context: Dict with 'idea_validation' and/or 'tech_feasibility' content.

        Returns:
            Formatted user prompt string.
        """
        parts = [
            f"You are executing Phase 1b: PRD and Screen Specification.",
            f"",
            f"App idea: {ctx.idea}",
            f"App name: {ctx.app_name}",
            f"",
        ]

        # Embed Phase 1a context directly so the agent has full content
        if "idea_validation" in phase_1a_context:
            parts.extend([
                "## Phase 1a Context: Idea Validation",
                "",
                phase_1a_context["idea_validation"],
                "",
            ])

        if "tech_feasibility" in phase_1a_context:
            parts.extend([
                "## Phase 1a Context: Technical Feasibility",
                "",
                phase_1a_context["tech_feasibility"],
                "",
            ])

        parts.extend([
            "## Your Tasks",
            "",
            "**IMPORTANT: Write prd.md FIRST, then derive screen-spec.json from it.**",
            "Component names in screen-spec.json MUST exactly match component names in prd.md.",
            "",
            "### Task 1: Write docs/pipeline/prd.md",
            "",
            "Write a Product Requirements Document with these exact sections:",
            "- MoSCoW-labeled requirements (use exactly: Must, Should, Could, Won't labels)",
            "- ## Component Inventory — list every reusable UI component with parent-child hierarchy",
            "- ## Responsive Breakpoint Strategy — specify mobile/tablet/desktop breakpoints with pixel widths",
            "- ## Route Structure — list all pages with URL paths",
            "- Data flow description showing how data moves through the system",
            "",
            "Use the Phase 1a competitor analysis above to inform design decisions.",
            "Use the Phase 1a tech feasibility to inform component and architecture choices.",
            "",
            "### Task 2: Derive docs/pipeline/screen-spec.json from prd.md",
            "",
            "Write a machine-readable screen specification as valid JSON:",
            "```json",
            "{",
            '  "screens": [',
            "    {",
            '      "route": "/path",',
            '      "layout": "description of major layout regions",',
            '      "components": ["ComponentName1", "ComponentName2"],',
            '      "states": ["loading", "loaded", "error"],',
            '      "responsive": {',
            '        "mobile": "mobile-specific differences",',
            '        "tablet": "tablet-specific differences",',
            '        "desktop": "desktop layout description"',
            "      }",
            "    }",
            "  ]",
            "}",
            "```",
            "",
            "Component names in the 'components' arrays MUST match exactly the names in",
            "the ## Component Inventory section of prd.md. No new component names.",
            "",
            "Every screen must have all six keys: route, layout, components, states, responsive.",
            "Write substantive content — the downstream build agent depends on this specification.",
        ])

        return "\n".join(parts)

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
        for rel_path in [_PRD_PATH, _SCREEN_SPEC_PATH]:
            if not (project_dir / rel_path).exists():
                missing.append(str(rel_path))
        return (len(missing) == 0, missing)

    def _cross_validate_components(
        self, project_dir: Path
    ) -> tuple[bool, list[str]]:
        """Validate that every component in screen-spec.json appears in prd.md.

        Reads the Component Inventory section from prd.md and extracts all
        component names (bold-formatted names like **ComponentName**).
        Reads screen-spec.json and extracts all component names from
        screens[].components arrays.

        Every component name in screen-spec.json must appear in the PRD
        inventory. Names are compared case-sensitively.

        Args:
            project_dir: Root of the project being built.

        Returns:
            Tuple of (passed: bool, mismatches: list[str]) where mismatches
            lists component names present in screen-spec.json but absent from
            prd.md Component Inventory.
        """
        prd_path = project_dir / _PRD_PATH
        spec_path = project_dir / _SCREEN_SPEC_PATH

        if not prd_path.exists() or not spec_path.exists():
            return (False, ["deliverables missing"])

        # Extract component names from prd.md Component Inventory section
        prd_content = prd_path.read_text(encoding="utf-8")
        prd_components = self._extract_prd_component_names(prd_content)

        # Extract component names from screen-spec.json
        try:
            spec_data: dict[str, Any] = json.loads(
                spec_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError) as exc:
            return (False, [f"screen-spec.json parse error: {type(exc).__name__}"])

        spec_components: set[str] = set()
        for screen in spec_data.get("screens", []):
            for comp in screen.get("components", []):
                if isinstance(comp, str):
                    spec_components.add(comp)

        # Every spec component must be in PRD inventory
        mismatches = sorted(spec_components - prd_components)
        return (len(mismatches) == 0, mismatches)

    def _extract_prd_component_names(self, prd_content: str) -> set[str]:
        """Extract component names from the Component Inventory section of prd.md.

        Finds the ## Component Inventory section and extracts all bold-formatted
        names (**ComponentName**) as component identifiers. Also extracts
        any word-capitalized names following common list patterns.

        Args:
            prd_content: Full text content of prd.md.

        Returns:
            Set of component name strings found in the inventory.
        """
        # Find the Component Inventory section
        inventory_match = re.search(
            r"##\s+Component Inventory\s*\n(.*?)(?=\n##\s|\Z)",
            prd_content,
            re.DOTALL | re.IGNORECASE,
        )

        if not inventory_match:
            # If no explicit section, search whole document for bold names
            section_text = prd_content
        else:
            section_text = inventory_match.group(1)

        # Extract bold-formatted names: **ComponentName**, **myComponent**, **My_Component**
        bold_names = re.findall(r"\*\*([A-Za-z][A-Za-z0-9_-]*)\*\*", section_text)
        return set(bold_names)


# ---------------------------------------------------------------------------
# Self-registration — runs at module import time (and on importlib.reload)
# ---------------------------------------------------------------------------
# Guard: only register if not already registered. This allows tests to clear
# the registry and re-trigger registration via importlib.reload() without
# hitting the "duplicate registration" error on the first import.
if get_executor("1b") is None:
    register(Phase1bSpecExecutor())
