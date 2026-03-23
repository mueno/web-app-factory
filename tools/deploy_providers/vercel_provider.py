"""VercelProvider placeholder stub — full implementation in Plan 09-02.

This file is a placeholder so registry.py imports work immediately.
Plan 09-02 will overwrite this with the full VercelProvider extracted
from tools/phase_executors/phase_3_executor.py.
"""
from __future__ import annotations

from pathlib import Path

from .base import DeployProvider, DeployResult

_NOT_IMPLEMENTED_MSG = (
    "VercelProvider is not yet fully implemented. "
    "See Plan 09-02 for the full implementation extracted from phase_3_executor.py."
)


class VercelProvider(DeployProvider):
    """Vercel deployment provider — placeholder stub.

    Full implementation extracted from phase_3_executor.py is coming in Plan 09-02.
    """

    def deploy(self, project_dir: Path, env: dict) -> DeployResult:
        """Not yet implemented. See Plan 09-02."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def get_url(self, deploy_result: DeployResult) -> str:
        """Not yet implemented. See Plan 09-02."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def verify(self, url: str) -> bool:
        """Not yet implemented. See Plan 09-02."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)
