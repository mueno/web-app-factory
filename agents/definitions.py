"""Stub agent definitions for web-app-factory pipeline.

Full agent system prompts and configurations are defined in Phase 2+.
These stubs provide the structure needed by the pipeline runner and MCP server.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentDefinition:
    """Minimal agent definition for pipeline routing and logging."""

    name: str
    description: str
    system_prompt: str


# ── Agent Stubs ────────────────────────────────────────────────

SPEC_AGENT = AgentDefinition(
    name="spec-agent",
    description="Validates ideas and generates PRDs",
    system_prompt="System prompt to be defined in Phase 2",
)

BUILD_AGENT = AgentDefinition(
    name="build-agent",
    description="Scaffolds and builds Next.js applications",
    system_prompt="System prompt to be defined in Phase 2",
)

DEPLOY_AGENT = AgentDefinition(
    name="deploy-agent",
    description="Deploys to Vercel and runs quality gates",
    system_prompt="System prompt to be defined in Phase 2",
)

# Registry for lookup by name
AGENT_DEFINITIONS: list[AgentDefinition] = [SPEC_AGENT, BUILD_AGENT, DEPLOY_AGENT]

_AGENT_BY_NAME: dict[str, AgentDefinition] = {a.name: a for a in AGENT_DEFINITIONS}


def get_agent(name: str) -> AgentDefinition | None:
    """Look up an agent definition by name. Returns None if not found."""
    return _AGENT_BY_NAME.get(name)
