"""GCPProvider placeholder stub — full implementation in Plan 09-03.

This file is a placeholder so registry.py imports work immediately.
Plan 09-03 will overwrite this with the full GCPProvider using
'gcloud run deploy --source .' for Google Cloud Run.
"""
from __future__ import annotations

from pathlib import Path

from .base import DeployProvider, DeployResult

_NOT_IMPLEMENTED_MSG = (
    "GCPProvider is not yet fully implemented. "
    "See Plan 09-03 for the full implementation using 'gcloud run deploy --source .'"
)


class GCPProvider(DeployProvider):
    """Google Cloud Run deployment provider — placeholder stub.

    Full implementation using gcloud run deploy --source . is coming in Plan 09-03.
    """

    def deploy(self, project_dir: Path, env: dict) -> DeployResult:
        """Not yet implemented. See Plan 09-03."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def get_url(self, deploy_result: DeployResult) -> str:
        """Not yet implemented. See Plan 09-03."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def verify(self, url: str) -> bool:
        """Not yet implemented. See Plan 09-03."""
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)
