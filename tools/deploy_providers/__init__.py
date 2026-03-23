"""deploy_providers — multi-cloud deployment abstraction layer.

Re-exports the public API for the deploy_providers module.
See individual modules for full documentation.

Public API:
    DeployProvider  — Abstract base class for all providers
    DeployResult    — Frozen dataclass with success/url/provider/metadata
    get_provider    — Factory: get_provider("vercel") -> VercelProvider()

Example:
    from tools.deploy_providers import get_provider, DeployResult

    provider = get_provider("local")
    result = provider.deploy(project_dir, env)
    if result.success:
        url = provider.get_url(result)
"""
from __future__ import annotations

from .base import DeployProvider, DeployResult
from .registry import get_provider

__all__ = ["DeployProvider", "DeployResult", "get_provider"]
