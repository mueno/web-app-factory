"""Shared utility for running the spec agent via Claude Agent SDK.

This module provides three exported functions:

- ``load_phase_quality_criteria``: reads the pipeline YAML contract and extracts
  all quality_criteria strings for a given phase_id across all deliverables.

- ``build_phase_system_prompt``: appends a ``## Quality Criteria`` section to a
  base system prompt so the agent knows what "good" looks like before generating
  output. Includes an anti-gate-gaming instruction.

- ``run_spec_agent``: wraps the async ``claude_agent_sdk.query()`` call in
  ``asyncio.run()`` to provide a synchronous interface. This is the sync/async
  bridge used by Phase 1a and 1b executor classes.

Design notes:
- ClaudeAgentOptions uses ``permission_mode="bypassPermissions"`` and restricts
  allowed_tools to ``["WebSearch", "Read", "Write"]`` — no shell execution.
- ``max_turns`` defaults to 25, matching the ios-app-factory cap pattern.
- Returns ``ResultMessage.result`` text, or empty string when the agent
  produces no result (e.g., model refused or returned empty output).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yaml

from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import ResultMessage


def load_phase_quality_criteria(phase_id: str, contract_path: Path) -> list[str]:
    """Extract all quality_criteria strings for a phase from the YAML contract.

    Reads the pipeline contract YAML and collects every ``quality_criteria``
    entry under all deliverables for the given ``phase_id``.

    Args:
        phase_id: The phase identifier (e.g. ``"1a"``, ``"1b"``).
        contract_path: Absolute path to the pipeline contract YAML file.

    Returns:
        A flat list of quality criteria strings. Returns an empty list if
        the phase is not found or has no deliverables with criteria.
    """
    try:
        with open(contract_path, "r", encoding="utf-8") as f:
            contract: dict[str, Any] = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return []

    phases: list[dict[str, Any]] = contract.get("phases", [])
    criteria: list[str] = []

    for phase in phases:
        if str(phase.get("id", "")) == str(phase_id):
            for deliverable in phase.get("deliverables", []):
                for criterion in deliverable.get("quality_criteria", []):
                    if isinstance(criterion, str) and criterion.strip():
                        criteria.append(criterion.strip())
            break  # found our phase, stop scanning

    return criteria


def build_phase_system_prompt(base_prompt: str, quality_criteria: list[str]) -> str:
    """Append a Quality Criteria section to a base system prompt.

    Constructs a prompt that instructs the agent to satisfy every listed
    quality criterion. Includes an explicit anti-gate-gaming instruction so
    the agent understands it must produce substantive output, not minimum
    content that satisfies gate markers.

    Args:
        base_prompt: The base system prompt string.
        quality_criteria: List of criterion strings to append as bullet points.

    Returns:
        The augmented system prompt string with the Quality Criteria section
        appended. If ``quality_criteria`` is empty, returns the base prompt
        with an empty criteria section and the anti-gaming instruction.
    """
    lines: list[str] = [base_prompt.rstrip(), "", "## Quality Criteria"]

    if quality_criteria:
        for criterion in quality_criteria:
            lines.append(f"- {criterion}")
    else:
        lines.append("(No specific criteria defined for this phase.)")

    lines.extend(
        [
            "",
            "Generate output that satisfies every criterion above. "
            "Do not optimize for gate markers — produce substantive deliverables "
            "that are useful to a downstream build agent, not minimum content that "
            "passes gate checks.",
        ]
    )

    return "\n".join(lines)


def run_spec_agent(
    prompt: str,
    system_prompt: str,
    project_dir: str,
    max_turns: int = 25,
) -> str:
    """Run the spec agent synchronously and return the result text.

    Bridges the async ``claude_agent_sdk.query()`` into a synchronous call
    using ``asyncio.run()``. Iterates all messages from the async generator
    and returns the text from the first ``ResultMessage`` found.

    Args:
        prompt: The user-facing task prompt for this specific agent run.
        system_prompt: The agent's system prompt (base + injected quality criteria).
        project_dir: Working directory for the agent (project root path).
        max_turns: Maximum number of agentic turns before the SDK stops.
            Defaults to 25 to prevent runaway loops.

    Returns:
        The ``ResultMessage.result`` text, or an empty string if the agent
        produces no result message.
    """
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        allowed_tools=["WebSearch", "Read", "Write"],
        max_turns=max_turns,
        cwd=project_dir,
    )

    async def _run() -> str:
        async for message in query(prompt, options=options):
            if isinstance(message, ResultMessage):
                return message.result or ""
        return ""

    return asyncio.run(_run())
