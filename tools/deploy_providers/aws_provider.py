"""AWSProvider stub — AWS CDK deployment not implemented in v2.0.

AWS deployment is planned for v3.0. All methods raise NotImplementedError
with actionable guidance pointing to the AWS CDK documentation.
"""
from __future__ import annotations

from pathlib import Path

from .base import DeployProvider, DeployResult


class AWSProvider(DeployProvider):
    """AWS CDK stub — not implemented in web-app-factory v2.0.

    AWS deployment is deferred to v3.0. Users who need to deploy to AWS
    should use the AWS CDK directly. See the guidance message below.
    """

    _GUIDANCE = (
        "AWS deployment is not implemented in web-app-factory v2.0. "
        "It is planned for v3.0. "
        "To deploy manually, use the AWS CDK: "
        "https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html"
    )

    def deploy(self, project_dir: Path, env: dict) -> DeployResult:
        """Not implemented. Raises NotImplementedError with v3.0 guidance."""
        raise NotImplementedError(self._GUIDANCE)

    def get_url(self, deploy_result: DeployResult) -> str:
        """Not implemented. Raises NotImplementedError with v3.0 guidance."""
        raise NotImplementedError(self._GUIDANCE)

    def verify(self, url: str) -> bool:
        """Not implemented. Raises NotImplementedError with v3.0 guidance."""
        raise NotImplementedError(self._GUIDANCE)
