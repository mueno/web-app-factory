"""LocalOnlyProvider — skip cloud deployment; run npm build, return localhost URL.

Per user decision (09-CONTEXT.md):
- Runs 'npm run build' to verify the app builds successfully
- Does NOT start a dev server (that is Phase 10's waf_start_dev_server responsibility)
- Returns http://localhost:3000 as a placeholder (synthetic result)
- verify() returns True unconditionally (deployment_gate skipped for local-only)

Security: subprocess calls use explicit list args — no shell=True.
This is enforced by tests/test_subprocess_audit.py.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from .base import DeployProvider, DeployResult

logger = logging.getLogger(__name__)

_NPM_BUILD_TIMEOUT = 300  # seconds

# Allowlist for npm build subprocess — minimal env for Node.js toolchain.
_LOCAL_ENV_ALLOWLIST = frozenset({
    "PATH", "HOME", "USER", "SHELL", "LANG", "LC_ALL", "TERM",
    "TMPDIR", "TEMP", "TMP",
    "NODE_ENV", "NODE_OPTIONS", "NPM_CONFIG_PREFIX",
})


def _filtered_env() -> dict[str, str]:
    """Return a filtered copy of os.environ containing only allowlisted keys."""
    return {k: v for k, v in os.environ.items() if k in _LOCAL_ENV_ALLOWLIST}


class LocalOnlyProvider(DeployProvider):
    """Skip cloud deployment; run npm run build and return localhost URL.

    This provider verifies the Next.js app builds successfully without
    deploying to any cloud provider. The URL http://localhost:3000 is
    a synthetic placeholder — use waf_start_dev_server to actually
    start the development server.
    """

    def deploy(self, project_dir: Path, env: dict) -> DeployResult:
        """Run npm run build and return a localhost:3000 result on success.

        Args:
            project_dir: The project root directory.
            env: Runtime environment dict. Uses env["nextjs_dir"] if set,
                 otherwise falls back to str(project_dir).

        Returns:
            DeployResult with success=True and url="http://localhost:3000"
            on successful build, or success=False with error in metadata.
        """
        nextjs_dir = env.get("nextjs_dir") or str(project_dir)

        # Pre-flight: check package.json exists
        if not Path(nextjs_dir, "package.json").exists():
            return DeployResult(
                success=False,
                url=None,
                provider="local",
                metadata={"error": f"package.json not found in {nextjs_dir}"},
            )

        logger.info("LocalOnlyProvider: running npm run build in %s", nextjs_dir)

        try:
            proc = subprocess.run(
                ["npm", "run", "build"],
                cwd=nextjs_dir,
                capture_output=True,
                text=True,
                timeout=_NPM_BUILD_TIMEOUT,
                env=_filtered_env(),
            )
        except subprocess.TimeoutExpired:
            return DeployResult(
                success=False,
                url=None,
                provider="local",
                metadata={
                    "error": f"npm run build timed out after {_NPM_BUILD_TIMEOUT} seconds"
                },
            )

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            logger.warning(
                "LocalOnlyProvider: npm run build failed (exit %d): %s",
                proc.returncode,
                stderr[:200],
            )
            return DeployResult(
                success=False,
                url=None,
                provider="local",
                metadata={"error": f"npm run build failed: {stderr[:200]}"},
            )

        logger.info("LocalOnlyProvider: npm run build succeeded")
        return DeployResult(
            success=True,
            url="http://localhost:3000",
            provider="local",
            metadata={
                "note": "Build succeeded. Start dev server with waf_start_dev_server."
            },
        )

    def get_url(self, deploy_result: DeployResult) -> str:
        """Return the URL from a successful deploy result.

        Args:
            deploy_result: The result from a previous deploy() call.

        Returns:
            The URL string (http://localhost:3000 for successful builds).

        Raises:
            ValueError: If url is None (deploy may have failed).
        """
        if deploy_result.url is None:
            raise ValueError("LocalOnlyProvider: no URL (deploy may have failed)")
        return deploy_result.url

    def verify(self, url: str) -> bool:
        """Return True unconditionally — local-only skips HTTP health check.

        Per user decision: deployment_gate is not run for local targets.
        The local provider verifies the build, not a running server.

        Args:
            url: Ignored for local provider.

        Returns:
            Always True.
        """
        # Local-only: skip HTTP check per user decision
        # deployment_gate is not run for local targets
        return True
