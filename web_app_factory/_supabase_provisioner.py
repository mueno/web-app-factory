"""Supabase project provisioner.

Provides SupabaseProvisioner for creating Supabase projects via the Management API,
polling health status, retrieving API keys, and injecting credentials into Vercel.

Security contract (from .claude/rules/10-security-core.md):
- Credential VALUES (tokens, keys, passwords) are NEVER logged, printed, or included in output.
- Only operation names and status codes are logged.
- db_pass is generated with secrets.token_urlsafe(32) and never serialized beyond the
  ephemeral _db_pass key returned by create_project().
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SUPABASE_API_BASE = "https://api.supabase.com/v1"
_VERCEL_API_BASE = "https://api.vercel.com/v10"

# Default region for new Supabase projects (Americas smart group).
_DEFAULT_REGION = "us-east-1"

# Maximum poll timeout to prevent infinite hanging (SUPA-01 requirement).
_DEFAULT_POLL_TIMEOUT_S = 300
_DEFAULT_POLL_INTERVAL_S = 5


# ---------------------------------------------------------------------------
# SupabaseProvisioner
# ---------------------------------------------------------------------------


class SupabaseProvisioner:
    """Handles Supabase project lifecycle via the Management API.

    Args:
        access_token: Supabase personal access token (never logged).
        org_id: Supabase organization slug (never logged).
    """

    def __init__(self, access_token: str, org_id: str) -> None:
        self._access_token = access_token
        self._org_id = org_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """Return auth headers for Supabase Management API calls."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _vercel_headers(self, vercel_token: str) -> dict[str, str]:
        """Return auth headers for Vercel API calls."""
        return {
            "Authorization": f"Bearer {vercel_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_project(self, name: str) -> dict[str, Any]:
        """Create a new Supabase project via the Management API.

        Generates a cryptographically strong db_pass using
        secrets.token_urlsafe(32). The password is returned in the
        ephemeral '_db_pass' key and is never logged.

        Args:
            name: Project name (used as both display name and project slug).

        Returns:
            dict: The API response JSON with '_db_pass' added as an ephemeral key.

        Raises:
            httpx.HTTPStatusError: If the API returns a non-2xx status.
        """
        db_pass = secrets.token_urlsafe(32)
        payload = {
            "name": name,
            "organization_slug": self._org_id,
            "db_pass": db_pass,
            "region": _DEFAULT_REGION,
        }

        url = f"{_SUPABASE_API_BASE}/projects"
        logger.info("Creating Supabase project name=%r", name)

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
            result: dict[str, Any] = response.json()

        logger.info("Supabase project created ref=%r", result.get("ref"))
        # Attach db_pass ephemerally — never serialized, never logged
        result["_db_pass"] = db_pass
        return result

    async def poll_until_healthy(
        self,
        ref: str,
        *,
        timeout_s: int = _DEFAULT_POLL_TIMEOUT_S,
        interval_s: int = _DEFAULT_POLL_INTERVAL_S,
    ) -> None:
        """Poll the project health endpoint until all services are ACTIVE_HEALTHY.

        Treats an empty health list as "not yet healthy" (Pitfall 5 — Management
        API can return [] before services register).

        Args:
            ref: Supabase project reference identifier.
            timeout_s: Maximum seconds to wait before raising TimeoutError.
            interval_s: Seconds to sleep between polls.

        Raises:
            TimeoutError: If all services are not ACTIVE_HEALTHY within timeout_s.
        """
        url = f"{_SUPABASE_API_BASE}/projects/{ref}/health"
        deadline = time.monotonic() + timeout_s
        logger.info("Polling Supabase project health ref=%r timeout_s=%d", ref, timeout_s)

        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(url, headers=self._headers())
                response.raise_for_status()
                services: list[dict] = response.json()

                if services and all(
                    svc.get("status") == "ACTIVE_HEALTHY" for svc in services
                ):
                    logger.info("Supabase project healthy ref=%r services=%d", ref, len(services))
                    return

                elapsed = time.monotonic()
                if elapsed >= deadline:
                    raise TimeoutError(
                        f"Supabase project ref={ref!r} not healthy after {timeout_s}s"
                    )

                logger.debug(
                    "Supabase project ref=%r not yet healthy (services=%d); retrying in %ds",
                    ref,
                    len(services),
                    interval_s,
                )
                await asyncio.sleep(interval_s)

    async def get_api_keys(self, ref: str) -> dict[str, str]:
        """Retrieve the anon and service_role API keys for a project.

        Args:
            ref: Supabase project reference identifier.

        Returns:
            dict: {"anon_key": str, "service_role_key": str}

        Raises:
            httpx.HTTPStatusError: If the API returns a non-2xx status.
            KeyError: If expected key names are absent in the response.
        """
        url = f"{_SUPABASE_API_BASE}/projects/{ref}/api-keys"
        logger.info("Retrieving API keys for ref=%r", ref)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            keys: list[dict] = response.json()

        result: dict[str, str] = {}
        for entry in keys:
            if entry.get("name") == "anon":
                result["anon_key"] = entry["api_key"]
            elif entry.get("name") == "service_role":
                result["service_role_key"] = entry["api_key"]

        # Log key names retrieved, never values
        logger.info("Retrieved key types: %r", list(result.keys()))
        return result

    async def inject_vercel_env(
        self,
        vercel_token: str,
        vercel_project_id: str,
        supabase_url: str,
        anon_key: str,
        service_role_key: str,
    ) -> None:
        """Inject Supabase credentials into a Vercel project as environment variables.

        Injects:
        - NEXT_PUBLIC_SUPABASE_URL (plain, all targets)
        - NEXT_PUBLIC_SUPABASE_ANON_KEY (plain, all targets — intentionally public)
        - SUPABASE_SERVICE_ROLE_KEY (sensitive, production+preview only — NO NEXT_PUBLIC_)

        Args:
            vercel_token: Vercel personal access token (never logged).
            vercel_project_id: Vercel project identifier.
            supabase_url: Public Supabase project URL.
            anon_key: Supabase anon key (public, safe to expose in browser).
            service_role_key: Supabase service role key (sensitive, server-side only).

        Raises:
            httpx.HTTPStatusError: If the Vercel API returns a non-2xx status.
        """
        all_targets = ["production", "preview", "development"]
        server_targets = ["production", "preview"]

        env_vars = [
            {
                "key": "NEXT_PUBLIC_SUPABASE_URL",
                "value": supabase_url,
                "type": "plain",
                "target": all_targets,
            },
            {
                "key": "NEXT_PUBLIC_SUPABASE_ANON_KEY",
                "value": anon_key,
                "type": "plain",
                "target": all_targets,
            },
            {
                "key": "SUPABASE_SERVICE_ROLE_KEY",
                "value": service_role_key,
                "type": "sensitive",
                "target": server_targets,
            },
        ]

        url = f"{_VERCEL_API_BASE}/projects/{vercel_project_id}/env?upsert=true"
        logger.info("Injecting Supabase env vars into Vercel project_id=%r", vercel_project_id)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=env_vars,
                headers=self._vercel_headers(vercel_token),
            )
            response.raise_for_status()

        # Log only key names injected, never values
        logger.info("Injected env vars: %r", [e["key"] for e in env_vars])

    async def configure_oauth_providers(
        self,
        ref: str,
        google_client_id: str | None = None,
        google_secret: str | None = None,
        apple_client_id: str | None = None,
        apple_secret: str | None = None,
    ) -> None:
        """Configure OAuth providers (Google and/or Apple) on a Supabase project.

        Uses the Supabase Management API to PATCH /v1/projects/{ref}/config/auth
        with the enabled OAuth provider credentials.

        Security contract: credential VALUES are never logged — only key names.
        If no providers are supplied (all args None), the API call is skipped.

        Args:
            ref: Supabase project reference identifier.
            google_client_id: Google OAuth client ID, or None to skip Google.
            google_secret: Google OAuth client secret, or None to skip Google.
            apple_client_id: Apple OAuth client ID, or None to skip Apple.
            apple_secret: Apple OAuth client secret, or None to skip Apple.

        Raises:
            httpx.HTTPStatusError: If the Management API returns a non-2xx status.
        """
        payload: dict[str, object] = {}

        if google_client_id is not None and google_secret is not None:
            payload["external_google_enabled"] = True
            payload["external_google_client_id"] = google_client_id
            payload["external_google_secret"] = google_secret

        if apple_client_id is not None and apple_secret is not None:
            payload["external_apple_enabled"] = True
            payload["external_apple_client_id"] = apple_client_id
            payload["external_apple_secret"] = apple_secret

        if not payload:
            logger.info("No OAuth providers configured for ref=%r — skipping PATCH", ref)
            return

        url = f"{_SUPABASE_API_BASE}/projects/{ref}/config/auth"
        # Log only key names configured — NEVER log credential values
        logger.info("OAuth providers configured: %r", list(payload.keys()))

        async with httpx.AsyncClient() as client:
            response = await client.patch(url, json=payload, headers=self._headers())
            response.raise_for_status()
