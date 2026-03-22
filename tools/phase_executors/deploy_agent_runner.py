"""Shared utility for running the deploy agent via Claude Agent SDK.

This module provides one exported function:

- ``run_deploy_agent``: wraps the async ``claude_agent_sdk.query()`` call in
  ``asyncio.run()`` to provide a synchronous interface. This is the sync/async
  bridge used by the Phase 3 (ship) executor.

Design notes:
- ClaudeAgentOptions uses ``permission_mode="bypassPermissions"`` and restricts
  allowed_tools to ``["Read", "Write", "Bash"]`` — the deploy agent needs shell
  execution for ``vercel``, ``lighthouse``, and ``axe-core`` CLI operations.
- ``WebSearch`` is intentionally excluded — deploy agent draws from PRD context
  and live deployment URLs, not general web search.
- ``cwd`` is set to ``project_dir`` to sandbox the agent to the generated project
  directory. The agent cannot escape to the pipeline root.
- ``max_turns`` defaults to 75 (higher than build agent's 50 — deploy phase
  includes legal document generation plus fix-and-retry iterations).
- Returns ``ResultMessage.result`` text, or empty string when the agent
  produces no result (e.g., model refused or returned empty output).
"""

from __future__ import annotations

import asyncio

from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import ResultMessage


def run_deploy_agent(
    prompt: str,
    system_prompt: str,
    project_dir: str,
    max_turns: int = 75,
) -> str:
    """Run the deploy agent synchronously and return the result text.

    Bridges the async ``claude_agent_sdk.query()`` into a synchronous call
    using ``asyncio.run()``. Iterates all messages from the async generator
    and returns the text from the first ``ResultMessage`` found.

    The deploy agent is sandboxed to ``project_dir`` via the ``cwd`` option —
    shell commands from the agent are executed relative to the project, not the
    pipeline root.

    Args:
        prompt: The user-facing task prompt for this specific agent run.
        system_prompt: The agent's system prompt (base + injected quality criteria).
        project_dir: Working directory for the agent (generated project path).
            This is used as ``cwd`` in ``ClaudeAgentOptions``, sandboxing the
            agent to the project directory.
        max_turns: Maximum number of agentic turns before the SDK stops.
            Defaults to 75 — deploy phase requires more turns than build phase
            due to legal document generation and gate fix-and-retry cycles.

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
