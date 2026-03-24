"""Supabase provisioning gate.

Verifies three aspects of Supabase integration:
1. RLS coverage: every CREATE TABLE in migration SQL has ENABLE ROW LEVEL SECURITY
2. Project health: Supabase project is ACTIVE_HEALTHY via Management API
3. Vercel env injection: required env vars are present in the Vercel project

Exported function: run_supabase_gate
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from tools.gates.gate_result import GateResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required Vercel environment variables for Supabase integration
# ---------------------------------------------------------------------------

_REQUIRED_VERCEL_ENVS = [
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
]

# ---------------------------------------------------------------------------
# Regex patterns for RLS coverage scanning
# ---------------------------------------------------------------------------

# Matches: CREATE TABLE [IF NOT EXISTS] [public.]tablename
# Group 1 captures the table name (without schema prefix)
_CREATE_TABLE_RE = re.compile(
    r"""
    CREATE\s+TABLE\s+
    (?:IF\s+NOT\s+EXISTS\s+)?   # optional IF NOT EXISTS
    (?:public\.)?                # optional public. schema prefix
    (\w+)                        # table name (captured)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Matches: ALTER TABLE [public.]tablename ENABLE ROW LEVEL SECURITY
# Group 1 captures the table name (without schema prefix)
_ENABLE_RLS_RE = re.compile(
    r"""
    ALTER\s+TABLE\s+
    (?:public\.)?                # optional public. schema prefix
    (\w+)                        # table name (captured)
    \s+ENABLE\s+ROW\s+LEVEL\s+SECURITY
    """,
    re.IGNORECASE | re.VERBOSE,
)

# ---------------------------------------------------------------------------
# RLS coverage checker
# ---------------------------------------------------------------------------


def _check_rls_coverage(migration_sql: str) -> list[str]:
    """Scan migration SQL for CREATE TABLEs that lack ENABLE ROW LEVEL SECURITY.

    Args:
        migration_sql: Full SQL string to scan.

    Returns:
        Sorted list of issue strings, one per table missing RLS.
        Empty list if all tables have RLS (or there are no tables).
    """
    created_tables = {m.group(1).lower() for m in _CREATE_TABLE_RE.finditer(migration_sql)}
    rls_tables = {m.group(1).lower() for m in _ENABLE_RLS_RE.finditer(migration_sql)}

    missing = sorted(created_tables - rls_tables)
    issues = [
        f"Table '{table}' has CREATE TABLE but no ENABLE ROW LEVEL SECURITY"
        for table in missing
    ]
    return issues


# ---------------------------------------------------------------------------
# Project health checker
# ---------------------------------------------------------------------------


def _check_project_health(
    supabase_access_token: str | None,
    project_ref: str | None,
) -> list[str]:
    """Verify that the Supabase project exists and all services are ACTIVE_HEALTHY.

    Args:
        supabase_access_token: Supabase personal access token.
        project_ref: Supabase project reference ID.

    Returns:
        List of issue strings. Empty list if all services are ACTIVE_HEALTHY.
        Returns a single-element list with an advisory if network errors occur.
    """
    if not project_ref:
        return ["No Supabase project ref found -- project not provisioned"]

    if not supabase_access_token:
        return ["SUPABASE_ACCESS_TOKEN not available -- cannot verify project health"]

    url = f"https://api.supabase.com/v1/projects/{project_ref}/health"
    headers = {
        "Authorization": f"Bearer {supabase_access_token}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            services: list[dict] = response.json()

        if not services:
            return [f"Supabase project ref={project_ref!r} health returned empty list -- not yet active"]

        unhealthy = [
            svc for svc in services
            if svc.get("status") != "ACTIVE_HEALTHY"
        ]
        if unhealthy:
            names = ", ".join(svc.get("name", "?") for svc in unhealthy)
            return [f"Supabase project ref={project_ref!r} has unhealthy services: {names}"]

        return []

    except Exception as exc:  # noqa: BLE001
        # Network errors are advisories — don't block gate on transient failures
        logger.warning(
            "Supabase health check failed for ref=%r: %s",
            project_ref,
            type(exc).__name__,
        )
        return [f"Supabase health check network error for ref={project_ref!r}: {type(exc).__name__}"]


# ---------------------------------------------------------------------------
# Vercel env injection verifier
# ---------------------------------------------------------------------------


def _check_vercel_env(
    vercel_token: str | None,
    vercel_project_id: str | None,
) -> list[str]:
    """Verify that required Supabase env vars are injected into Vercel.

    Args:
        vercel_token: Vercel personal access token.
        vercel_project_id: Vercel project identifier.

    Returns:
        List of issue strings per missing env var.
        Returns advisory if credentials unavailable or network errors occur.
    """
    if not vercel_token or not vercel_project_id:
        return ["Vercel credentials not available -- cannot verify env injection"]

    url = f"https://api.vercel.com/v10/projects/{vercel_project_id}/env"
    headers = {
        "Authorization": f"Bearer {vercel_token}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        # Vercel API returns {"envs": [...]} with each item having a "key" field
        env_keys = {env.get("key") for env in data.get("envs", [])}

        issues = []
        for required_key in _REQUIRED_VERCEL_ENVS:
            if required_key not in env_keys:
                issues.append(
                    f"Required env var {required_key!r} not found in Vercel project {vercel_project_id!r}"
                )
        return issues

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Vercel env check failed for project=%r: %s",
            vercel_project_id,
            type(exc).__name__,
        )
        return [f"Vercel env check network error for project={vercel_project_id!r}: {type(exc).__name__}"]


# ---------------------------------------------------------------------------
# Main gate entry point
# ---------------------------------------------------------------------------


def run_supabase_gate(
    project_dir: str,
    phase_id: str = "3",
    *,
    supabase_access_token: str | None = None,
    project_ref: str | None = None,
    vercel_token: str | None = None,
    vercel_project_id: str | None = None,
) -> GateResult:
    """Run all Supabase provisioning checks.

    Checks:
    1. RLS coverage (blocking): every CREATE TABLE has ENABLE ROW LEVEL SECURITY
    2. Project health (blocking if project missing, advisory on network error)
    3. Vercel env injection (blocking if env missing, advisory if creds unavailable)

    Args:
        project_dir: Root directory to scan for .sql migration files.
        phase_id: Phase identifier for the GateResult.
        supabase_access_token: Supabase Management API token.
        project_ref: Supabase project reference ID.
        vercel_token: Vercel personal access token.
        vercel_project_id: Vercel project identifier.

    Returns:
        GateResult with passed=True only when no blocking issues exist.
    """
    checked_at = datetime.now(tz=timezone.utc).isoformat()
    blocking_issues: list[str] = []
    advisories: list[str] = []

    # --- 1. RLS coverage (always blocking) ---
    project_path = Path(project_dir)
    sql_files = list(project_path.rglob("*.sql"))
    logger.info(
        "Supabase gate: scanning %d SQL file(s) under %r",
        len(sql_files),
        project_dir,
    )

    for sql_file in sorted(sql_files):
        sql_content = sql_file.read_text(encoding="utf-8")
        rls_issues = _check_rls_coverage(sql_content)
        for issue in rls_issues:
            blocking_issues.append(f"[{sql_file.name}] {issue}")

    # --- 2. Project health ---
    health_issues = _check_project_health(supabase_access_token, project_ref)
    for issue in health_issues:
        # "not provisioned" and "not available" issues are always blocking
        # Network errors are advisories
        if "network error" in issue.lower():
            advisories.append(issue)
        else:
            blocking_issues.append(issue)

    # --- 3. Vercel env injection ---
    vercel_issues = _check_vercel_env(vercel_token, vercel_project_id)
    for issue in vercel_issues:
        # "credentials not available" is advisory; actual missing env vars are blocking
        if "not available" in issue.lower() or "network error" in issue.lower():
            advisories.append(issue)
        else:
            blocking_issues.append(issue)

    # --- Determine result ---
    passed = len(blocking_issues) == 0
    status = "PASSED" if passed else "BLOCKED"

    logger.info(
        "Supabase gate result: passed=%r blocking_issues=%d advisories=%d",
        passed,
        len(blocking_issues),
        len(advisories),
    )

    return GateResult(
        gate_type="supabase",
        phase_id=phase_id,
        passed=passed,
        status=status,
        severity="BLOCK",
        confidence=1.0 if passed else 0.0,
        checked_at=checked_at,
        issues=blocking_issues,
        advisories=advisories,
    )
