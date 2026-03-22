"""Shared utility for running the build agent via Claude Agent SDK.

This module provides one exported function:

- ``run_build_agent``: wraps the async ``claude_agent_sdk.query()`` call in
  ``asyncio.run()`` to provide a synchronous interface. This is the sync/async
  bridge used by Phase 2a and 2b executor classes.

Design notes:
- ClaudeAgentOptions uses ``permission_mode="bypassPermissions"`` and restricts
  allowed_tools to ``["Read", "Write", "Bash"]`` — the build agent needs shell
  execution for ``npm install``, ``npm run build``, and other CLI operations.
- ``WebSearch`` is intentionally excluded — build agent draws from PRD/screen-spec
  context, not live web data.
- ``cwd`` is set to ``project_dir`` to sandbox the agent to the generated project
  directory. The agent cannot escape to the pipeline root.
- ``max_turns`` defaults to 50 (higher than spec agent's 25 — code generation
  requires more iterations for multi-screen apps).
- Returns ``ResultMessage.result`` text, or empty string when the agent
  produces no result (e.g., model refused or returned empty output).

Reusable helpers ``load_phase_quality_criteria`` and ``build_phase_system_prompt``
are imported from ``spec_agent_runner`` — they are fully generic and require no
changes for the build agent context.
"""

from __future__ import annotations

import asyncio

from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import ResultMessage

# Re-export generic helpers so callers can import from one place
from tools.phase_executors.spec_agent_runner import (  # noqa: F401
    build_phase_system_prompt,
    load_phase_quality_criteria,
)


def run_build_agent(
    prompt: str,
    system_prompt: str,
    project_dir: str,
    max_turns: int = 50,
) -> str:
    """Run the build agent synchronously and return the result text.

    Bridges the async ``claude_agent_sdk.query()`` into a synchronous call
    using ``asyncio.run()``. Iterates all messages from the async generator
    and returns the text from the first ``ResultMessage`` found.

    The build agent is sandboxed to ``project_dir`` via the ``cwd`` option —
    shell commands from the agent are executed relative to the project, not the
    pipeline root.

    Args:
        prompt: The user-facing task prompt for this specific agent run.
        system_prompt: The agent's system prompt (base + injected quality criteria).
        project_dir: Working directory for the agent (generated project path).
            This is used as ``cwd`` in ``ClaudeAgentOptions``, sandboxing the
            agent to the project directory.
        max_turns: Maximum number of agentic turns before the SDK stops.
            Defaults to 50 — code generation requires more turns than spec work.

    Returns:
        The ``ResultMessage.result`` text, or an empty string if the agent
        produces no result message.
    """
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        allowed_tools=["Read", "Write", "Bash"],
        max_turns=max_turns,
        cwd=project_dir,
    )

    async def _run() -> str:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                return message.result or ""
        return ""

    return asyncio.run(_run())
