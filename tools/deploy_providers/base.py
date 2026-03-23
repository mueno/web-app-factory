"""DeployProvider ABC and DeployResult dataclass.

Defines the provider contract that all deployment targets must satisfy.
Mirrors existing codebase patterns:
- DeployResult follows GateResult frozen dataclass convention
- DeployProvider follows PhaseExecutor ABC convention

Security: all concrete deploy() implementations MUST use
subprocess with explicit arg lists (no shell=True). This is
enforced by tests/test_subprocess_audit.py which scans tools/.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class DeployResult:
    """Immutable deploy result — mirrors GateResult convention (frozen=True).

    Post-construction mutation requires dataclasses.replace() to produce
    a new DeployResult instance (copy-on-write). Direct attribute assignment
    is blocked by frozen=True.
    """

    success: bool
    url: Optional[str]
    provider: str
    metadata: dict = field(default_factory=dict)


class DeployProvider(ABC):
    """Abstract base class for all deploy providers.

    All providers must implement the three core methods:
    - deploy(): Execute deployment, return DeployResult
    - get_url(): Extract deployed URL from result
    - verify(): Health-check the deployed URL

    Security: all concrete deploy() implementations MUST use
    subprocess with explicit arg lists (no shell=True). This is
    enforced by tests/test_subprocess_audit.py which scans tools/.
    """

    @abstractmethod
    def deploy(self, project_dir: Path, env: dict) -> DeployResult:
        """Execute deployment.

        Args:
            project_dir: The project root directory.
            env: Runtime environment dict (nextjs_dir, app_name, etc.)

        Returns:
            DeployResult with success=True and url set on success,
            or success=False and error in metadata on failure.

        Note: Implementations must NOT raise exceptions for expected
        failures. Return DeployResult(success=False, ...) instead,
        so Phase 3 executor can include the error in SubStepResult.
        """
        ...

    @abstractmethod
    def get_url(self, deploy_result: DeployResult) -> str:
        """Extract the deployed URL from a DeployResult.

        Args:
            deploy_result: The result from a previous deploy() call.

        Returns:
            The deployment URL as a string.

        Raises:
            ValueError: If no URL is available (e.g., deploy failed).
        """
        ...

    @abstractmethod
    def verify(self, url: str) -> bool:
        """Health-check the deployed URL.

        Args:
            url: The URL to verify.

        Returns:
            True if the URL is reachable and healthy, False otherwise.

        Note: LocalOnlyProvider returns True unconditionally (no HTTP check).
        Other providers delegate to run_deployment_gate().
        """
        ...
