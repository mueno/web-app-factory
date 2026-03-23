"""VercelProvider — full Vercel deployment implementation.

Extracted from tools/phase_executors/phase_3_executor.py (Plan 09-02).

Implements the DeployProvider ABC with:
- deploy(): vercel link --yes → vercel --yes (capture URL) → vercel promote
- get_url(): returns url from DeployResult or raises ValueError
- verify(): delegates to run_deployment_gate()

Security: all subprocess calls use explicit arg lists (no shell=True).
This is enforced by tests/test_subprocess_audit.py.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tools.deploy_providers.base import DeployProvider, DeployResult
from tools.gates.deployment_gate import run_deployment_gate

logger = logging.getLogger(__name__)

# Regex to extract Vercel preview URL from CLI output
# Moved from phase_3_executor.py — same pattern, same logic
_VERCEL_URL_RE = re.compile(r"https://[^\s]+\.vercel\.app")

# Deployment JSON output path relative to project_dir
_DEPLOYMENT_JSON_PATH = Path("docs") / "pipeline" / "deployment.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class VercelProvider(DeployProvider):
    """Vercel deployment provider.

    Implements the full provision → deploy_preview → promote lifecycle
    extracted from Phase3ShipExecutor._provision, ._deploy_preview,
    and ._deploy_production.

    Usage:
        provider = VercelProvider()
        result = provider.deploy(project_dir, {"nextjs_dir": "/path/to/nextjs"})
        url = provider.get_url(result)
        healthy = provider.verify(url)
    """

    def deploy(self, project_dir: Path, env: dict) -> DeployResult:
        """Execute full Vercel deployment: provision → preview → promote.

        Args:
            project_dir: The project root directory (used for deployment.json path).
            env: Runtime environment dict. Reads:
                - nextjs_dir: str — path to Next.js project dir (falls back to str(project_dir))
                - app_name: str — application name (optional, for logging)

        Returns:
            DeployResult(success=True, url=preview_url, provider="vercel") on success,
            DeployResult(success=False, url=None, provider="vercel", metadata={"error": ...})
            on any step failure.
        """
        nextjs_dir = env.get("nextjs_dir") or str(project_dir)

        # Step 1: Provision (vercel link --yes)
        provision_error = self._provision(nextjs_dir)
        if provision_error is not None:
            return DeployResult(
                success=False,
                url=None,
                provider="vercel",
                metadata={"error": provision_error, "step": "provision"},
            )

        # Step 2: Deploy preview (vercel --yes) → capture URL → write deployment.json
        preview_url, preview_error = self._deploy_preview(nextjs_dir, project_dir)
        if preview_error is not None:
            return DeployResult(
                success=False,
                url=None,
                provider="vercel",
                metadata={"error": preview_error, "step": "deploy_preview"},
            )

        # Step 3: Promote to production (vercel promote {preview_url} --yes --timeout=5m)
        promote_error = self._promote(preview_url, nextjs_dir)
        if promote_error is not None:
            return DeployResult(
                success=False,
                url=preview_url,  # preview_url is available even if promote failed
                provider="vercel",
                metadata={"error": promote_error, "step": "promote"},
            )

        return DeployResult(
            success=True,
            url=preview_url,
            provider="vercel",
            metadata={"deployed_at": _now_iso()},
        )

    def get_url(self, deploy_result: DeployResult) -> str:
        """Return the URL from a successful DeployResult.

        Args:
            deploy_result: Result from a previous deploy() call.

        Returns:
            The deployment URL.

        Raises:
            ValueError: If deploy_result.url is None (e.g., deploy failed).
        """
        if deploy_result.url is None:
            raise ValueError(
                f"No URL available in DeployResult for provider '{deploy_result.provider}'. "
                "deploy() may have failed — check deploy_result.metadata['error']."
            )
        return deploy_result.url

    def verify(self, url: str) -> bool:
        """Health-check the deployed URL via deployment gate.

        Delegates to run_deployment_gate() which performs an HTTP GET
        and expects HTTP 200 or 401.

        Args:
            url: The deployed Vercel URL to verify.

        Returns:
            True if gate passed, False otherwise.
        """
        gate_result = run_deployment_gate(url)
        return gate_result.passed

    # ── Internal subprocess methods ─────────────────────────────────────────

    def _provision(self, nextjs_dir: str) -> Optional[str]:
        """Run vercel link --yes to auto-provision Vercel project.

        Args:
            nextjs_dir: Working directory for vercel CLI.

        Returns:
            None on success, error string on failure.
        """
        try:
            proc = subprocess.run(
                ["vercel", "link", "--yes"],
                cwd=nextjs_dir,
                timeout=60,
                capture_output=True,
                text=True,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired:
            return "vercel link timed out after 60 seconds"
        except Exception as exc:
            return f"vercel link failed: {type(exc).__name__}"

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            error_msg = stderr or f"vercel link exited with code {proc.returncode}"
            return f"Vercel provisioning failed: {error_msg}"

        return None

    def _deploy_preview(
        self, nextjs_dir: str, project_dir: Path
    ) -> tuple[Optional[str], Optional[str]]:
        """Run vercel --yes, capture preview URL, write deployment.json.

        Parses stdout with _VERCEL_URL_RE to extract the Vercel preview URL
        per RESEARCH.md Pitfall 5: use regex, not just stdout.strip().

        Args:
            nextjs_dir: Working directory for vercel CLI.
            project_dir: Project root — deployment.json is written here.

        Returns:
            (preview_url, None) on success,
            (None, error_string) on failure.
        """
        try:
            proc = subprocess.run(
                ["vercel", "--yes"],
                cwd=nextjs_dir,
                timeout=300,
                capture_output=True,
                text=True,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired:
            return None, "vercel deploy timed out after 300 seconds"
        except Exception as exc:
            return None, f"vercel deploy failed: {type(exc).__name__}"

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            error_msg = stderr or f"vercel exited with code {proc.returncode}"
            return None, f"Vercel preview deploy failed: {error_msg}"

        # Extract preview URL from stdout using regex
        stdout = proc.stdout or ""
        match = _VERCEL_URL_RE.search(stdout)
        if not match:
            return None, (
                "Could not capture Vercel preview URL from CLI output. "
                f"stdout was: {stdout[:200]!r}"
            )

        preview_url = match.group(0)

        # Write deployment.json for downstream gates
        deployment_data = {
            "preview_url": preview_url,
            "deployed_at": _now_iso(),
            "platform": "vercel",
        }
        deployment_json_path = project_dir / _DEPLOYMENT_JSON_PATH
        deployment_json_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            deployment_json_path.write_text(
                json.dumps(deployment_data, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning(
                "VercelProvider: failed to write deployment.json: %s",
                type(exc).__name__,
            )

        return preview_url, None

    def _promote(self, preview_url: str, nextjs_dir: str) -> Optional[str]:
        """Run vercel promote {preview_url} --yes --timeout=5m.

        Args:
            preview_url: The Vercel preview URL to promote to production.
            nextjs_dir: Working directory for vercel CLI.

        Returns:
            None on success, error string on failure.
        """
        try:
            proc = subprocess.run(
                ["vercel", "promote", preview_url, "--yes", "--timeout=5m"],
                cwd=nextjs_dir,
                timeout=360,
                capture_output=True,
                text=True,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired:
            return "vercel promote timed out after 360 seconds"
        except Exception as exc:
            return f"vercel promote failed: {type(exc).__name__}"

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            error_msg = stderr or f"vercel promote exited with code {proc.returncode}"
            return f"Production promotion failed: {error_msg}"

        return None
