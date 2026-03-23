"""Provider registry — factory function for selecting deploy providers.

Mirrors tools/phase_executors/registry.py pattern but uses a simple dict
(no dynamic registration needed for four static providers).

Usage:
    from tools.deploy_providers.registry import get_provider

    provider = get_provider("vercel")  # returns VercelProvider instance
    provider = get_provider("gcp")     # returns GCPProvider instance
    provider = get_provider("aws")     # returns AWSProvider instance
    provider = get_provider("local")   # returns LocalOnlyProvider instance
"""
from __future__ import annotations

from .aws_provider import AWSProvider
from .base import DeployProvider
from .gcp_provider import GCPProvider
from .local_provider import LocalOnlyProvider
from .vercel_provider import VercelProvider

VALID_DEPLOY_TARGETS: frozenset[str] = frozenset({"vercel", "gcp", "aws", "local"})

_PROVIDERS: dict[str, type[DeployProvider]] = {
    "vercel": VercelProvider,
    "gcp": GCPProvider,
    "aws": AWSProvider,
    "local": LocalOnlyProvider,
}


def get_provider(deploy_target: str) -> DeployProvider:
    """Instantiate and return the provider for the given deploy_target.

    Args:
        deploy_target: One of "vercel", "gcp", "aws", "local".

    Returns:
        A DeployProvider instance ready for use.

    Raises:
        ValueError: If deploy_target is not a recognized value.
            The error message lists all valid targets.

    Example:
        >>> provider = get_provider("local")
        >>> result = provider.deploy(project_dir, env)
    """
    cls = _PROVIDERS.get(deploy_target)
    if cls is None:
        valid = ", ".join(sorted(VALID_DEPLOY_TARGETS))
        raise ValueError(
            f"Unknown deploy_target: {deploy_target!r}. "
            f"Valid values: {valid}"
        )
    return cls()
