"""GCPProvider — Google Cloud Run deployment using 'gcloud run deploy --source .'.

Auth preflight checks ensure gcloud is installed, authenticated, and a project
is configured before attempting deployment. URL is extracted from stderr.

Security notes:
- All subprocess calls use list args (no shell=True) — audited by test_subprocess_audit.py
- env={**os.environ} passes host environment to gcloud subprocess
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from .base import DeployProvider, DeployResult
from tools.gates.deployment_gate import run_deployment_gate

logger = logging.getLogger(__name__)

# Regex to extract Cloud Run service URL from gcloud stderr output.
# gcloud outputs: "Service URL: https://my-service-abc123-uc.a.run.app"
_GCP_URL_RE = re.compile(r"Service URL:\s+(https://[^\s]+\.run\.app)")


def _check_gcloud_auth() -> tuple[bool, str]:
    """Run preflight checks for gcloud CLI, auth, and project config.

    Checks in order:
    1. gcloud CLI is on PATH (FileNotFoundError → not installed)
    2. Valid auth token exists
    3. A GCP project is configured

    Returns:
        (True, "") on success.
        (False, error_message) on the first failing check.
    """
    # 1. Check gcloud CLI on PATH
    try:
        result = subprocess.run(
            ["gcloud", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return (
                False,
                "gcloud CLI not found. Install from: https://cloud.google.com/sdk",
            )
    except FileNotFoundError:
        return (
            False,
            "gcloud CLI not found. Install from: https://cloud.google.com/sdk",
        )

    # 2. Check valid auth token
    auth_result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if auth_result.returncode != 0:
        return (
            False,
            "GCP auth token invalid or expired. Run: gcloud auth login",
        )

    # 3. Check project configured
    project_result = subprocess.run(
        ["gcloud", "config", "get-value", "project"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    project_value = (project_result.stdout or "").strip()
    if not project_value or project_value == "(unset)":
        return (
            False,
            "No GCP project configured. Run: gcloud config set project <PROJECT_ID>",
        )

    return (True, "")


def _get_gcloud_region() -> Optional[str]:
    """Read the configured Cloud Run region from gcloud config.

    Returns the region string if set, or None if empty/unset.
    Not blocking — missing region falls back to us-central1 in deploy().
    """
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "run/region"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        region = (result.stdout or "").strip()
        if region and region != "(unset)":
            return region
    except Exception:
        pass
    return None


def _extract_gcp_url(stderr: str) -> Optional[str]:
    """Search stderr output for the Cloud Run service URL pattern.

    Args:
        stderr: Full stderr string from 'gcloud run deploy'.

    Returns:
        URL string (https://...run.app) if found, else None.
    """
    match = _GCP_URL_RE.search(stderr)
    if match:
        return match.group(1)
    return None


class GCPProvider(DeployProvider):
    """Deploy to Google Cloud Run using 'gcloud run deploy --source .'.

    Performs auth preflight checks before deploying and extracts the
    service URL from gcloud stderr output.

    Requirements: DEPL-03, DEPL-06
    """

    def deploy(self, project_dir: Path, env: dict) -> DeployResult:
        """Deploy to Cloud Run using 'gcloud run deploy --source .'.

        Args:
            project_dir: Root directory for the project.
            env: Environment dict with optional keys:
                 - nextjs_dir: Path to the Next.js project dir (defaults to str(project_dir))
                 - app_name: Cloud Run service name (defaults to 'web-app-factory-app')

        Returns:
            DeployResult with success/url/provider/metadata.
        """
        # Pre-flight: gcloud CLI, auth, project
        auth_ok, auth_error = _check_gcloud_auth()
        if not auth_ok:
            return DeployResult(
                success=False,
                url=None,
                provider="gcp",
                metadata={"error": auth_error},
            )

        # Determine deploy directory
        deploy_dir = env.get("nextjs_dir") or str(project_dir)

        # Derive Cloud Run service name from app_name
        service_name = env.get("app_name", "web-app-factory-app")

        # Build deploy command
        cmd = [
            "gcloud",
            "run",
            "deploy",
            service_name,
            "--source",
            ".",
            "--allow-unauthenticated",
            "--quiet",
        ]

        # Append region (use configured region or default us-central1)
        region = _get_gcloud_region()
        if region:
            cmd += ["--region", region]
        else:
            logger.warning(
                "No Cloud Run region configured. Defaulting to us-central1. "
                "Set with: gcloud config set run/region <REGION>"
            )
            cmd += ["--region", "us-central1"]

        # Execute deployment
        try:
            deploy_result = subprocess.run(
                cmd,
                cwd=deploy_dir,
                capture_output=True,
                text=True,
                timeout=600,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired:
            return DeployResult(
                success=False,
                url=None,
                provider="gcp",
                metadata={"error": "gcloud run deploy timed out after 600 seconds"},
            )

        # Extract service URL from stderr (gcloud outputs URL to stderr, not stdout)
        url = _extract_gcp_url(deploy_result.stderr)

        if deploy_result.returncode != 0 or url is None:
            error_detail = deploy_result.stderr or deploy_result.stdout or ""
            logger.error(
                "gcloud run deploy failed (exit %d): %s",
                deploy_result.returncode,
                error_detail[:500],
            )
            return DeployResult(
                success=False,
                url=None,
                provider="gcp",
                metadata={
                    "error": f"gcloud run deploy failed (exit code {deploy_result.returncode})",
                },
            )

        return DeployResult(
            success=True,
            url=url,
            provider="gcp",
            metadata={
                "service_name": service_name,
                "deploy_dir": str(deploy_dir),
            },
        )

    def get_url(self, deploy_result: DeployResult) -> str:
        """Return the deployed Cloud Run URL.

        Args:
            deploy_result: Result from a successful deploy() call.

        Returns:
            URL string.

        Raises:
            ValueError: If deploy_result.url is None (deployment failed).
        """
        if deploy_result.url is None:
            raise ValueError(
                "GCPProvider: deploy_result.url is None — deployment did not produce a URL. "
                "Check deploy_result.metadata['error'] for details."
            )
        return deploy_result.url

    def verify(self, url: str) -> bool:
        """Verify the deployed Cloud Run service via HTTP health check.

        Delegates to run_deployment_gate() which performs an HTTP GET
        and returns passed=True only when status is 200 or 401.

        Args:
            url: The Cloud Run service URL (https://...run.app).

        Returns:
            True if the deployment gate passes, False otherwise.
        """
        gate_result = run_deployment_gate(url)
        return gate_result.passed
