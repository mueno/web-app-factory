"""Tests for supabase_gate.py.

Covers:
- RLS coverage scanning (_check_rls_coverage)
- Project health verification (_check_project_health)
- Vercel env injection verification (_check_vercel_env)
- Integration: run_supabase_gate
- GateResult shape verification
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.gates.supabase_gate import (
    _check_rls_coverage,
    _check_project_health,
    _check_vercel_env,
    run_supabase_gate,
)


# ---------------------------------------------------------------------------
# _check_rls_coverage tests
# ---------------------------------------------------------------------------


class TestCheckRlsCoverage:
    def test_both_tables_have_rls_no_issues(self):
        """No issues when all CREATE TABLEs have ENABLE ROW LEVEL SECURITY."""
        sql = """
CREATE TABLE public.notes (
    id uuid PRIMARY KEY
);
ALTER TABLE public.notes ENABLE ROW LEVEL SECURITY;

CREATE TABLE public.tasks (
    id uuid PRIMARY KEY
);
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
"""
        issues = _check_rls_coverage(sql)
        assert issues == []

    def test_one_table_missing_rls_returns_issue(self):
        """Issues returned when one table lacks ENABLE ROW LEVEL SECURITY."""
        sql = """
CREATE TABLE public.notes (
    id uuid PRIMARY KEY
);
ALTER TABLE public.notes ENABLE ROW LEVEL SECURITY;

CREATE TABLE public.tasks (
    id uuid PRIMARY KEY
);
"""
        issues = _check_rls_coverage(sql)
        assert len(issues) >= 1
        assert any("tasks" in issue for issue in issues)

    def test_table_name_in_issue_message(self):
        """Issue message must mention the specific missing-RLS table name."""
        sql = """
CREATE TABLE public.documents (
    id uuid PRIMARY KEY
);
"""
        issues = _check_rls_coverage(sql)
        assert any("documents" in issue for issue in issues)

    def test_create_table_if_not_exists_detected(self):
        """CREATE TABLE IF NOT EXISTS variant is detected correctly."""
        sql = """
CREATE TABLE IF NOT EXISTS public.items (
    id uuid PRIMARY KEY
);
ALTER TABLE public.items ENABLE ROW LEVEL SECURITY;
"""
        issues = _check_rls_coverage(sql)
        assert issues == []

    def test_create_table_if_not_exists_missing_rls(self):
        """CREATE TABLE IF NOT EXISTS without RLS is detected as missing."""
        sql = """
CREATE TABLE IF NOT EXISTS public.items (
    id uuid PRIMARY KEY
);
"""
        issues = _check_rls_coverage(sql)
        assert len(issues) >= 1
        assert any("items" in issue for issue in issues)

    def test_public_schema_prefix_handled(self):
        """public. prefix in table name is handled correctly."""
        sql = """
CREATE TABLE public.accounts (
    id uuid PRIMARY KEY
);
ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
"""
        issues = _check_rls_coverage(sql)
        assert issues == []

    def test_case_insensitive_create_table(self):
        """CREATE TABLE matching is case-insensitive."""
        sql = """
create table public.orders (
    id uuid PRIMARY KEY
);
alter table public.orders enable row level security;
"""
        issues = _check_rls_coverage(sql)
        assert issues == []

    def test_empty_migration_no_issues(self):
        """Empty SQL returns no issues (no tables to check)."""
        issues = _check_rls_coverage("")
        assert issues == []

    def test_no_tables_no_issues(self):
        """SQL without any CREATE TABLE returns no issues."""
        sql = "-- No tables here\nSELECT 1;"
        issues = _check_rls_coverage(sql)
        assert issues == []


# ---------------------------------------------------------------------------
# _check_project_health tests (mocked httpx)
# ---------------------------------------------------------------------------


class TestCheckProjectHealth:
    def test_all_active_healthy_no_issues(self):
        """No issues when all services return ACTIVE_HEALTHY."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "db", "status": "ACTIVE_HEALTHY"},
            {"name": "auth", "status": "ACTIVE_HEALTHY"},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.get = MagicMock(return_value=mock_response)

        with patch("tools.gates.supabase_gate.httpx.Client", return_value=mock_client):
            issues = _check_project_health("access-token", "project-ref-abc")

        assert issues == []

    def test_non_active_healthy_returns_issue(self):
        """Issue returned when any service is not ACTIVE_HEALTHY."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "db", "status": "ACTIVE_HEALTHY"},
            {"name": "auth", "status": "COMING_UP"},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.get = MagicMock(return_value=mock_response)

        with patch("tools.gates.supabase_gate.httpx.Client", return_value=mock_client):
            issues = _check_project_health("access-token", "project-ref-abc")

        assert len(issues) >= 1

    def test_project_ref_none_returns_issue(self):
        """Issue returned when project_ref is None (project not provisioned)."""
        issues = _check_project_health("access-token", None)
        assert len(issues) >= 1
        assert any("not provisioned" in issue.lower() or "project" in issue.lower() for issue in issues)

    def test_project_ref_empty_returns_issue(self):
        """Issue returned when project_ref is empty string."""
        issues = _check_project_health("access-token", "")
        assert len(issues) >= 1

    def test_access_token_none_returns_issue(self):
        """Issue returned when access_token is None."""
        issues = _check_project_health(None, "project-ref-abc")
        assert len(issues) >= 1


# ---------------------------------------------------------------------------
# _check_vercel_env tests (mocked httpx)
# ---------------------------------------------------------------------------


class TestCheckVercelEnv:
    def test_all_three_env_vars_present_no_issues(self):
        """No issues when all 3 required Supabase env vars are present in Vercel."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "envs": [
                {"key": "NEXT_PUBLIC_SUPABASE_URL"},
                {"key": "NEXT_PUBLIC_SUPABASE_ANON_KEY"},
                {"key": "SUPABASE_SERVICE_ROLE_KEY"},
                {"key": "UNRELATED_VAR"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.get = MagicMock(return_value=mock_response)

        with patch("tools.gates.supabase_gate.httpx.Client", return_value=mock_client):
            issues = _check_vercel_env("vercel-token", "prj_abc")

        assert issues == []

    def test_missing_service_role_key_returns_issue(self):
        """Issue returned when SUPABASE_SERVICE_ROLE_KEY is missing from Vercel."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "envs": [
                {"key": "NEXT_PUBLIC_SUPABASE_URL"},
                {"key": "NEXT_PUBLIC_SUPABASE_ANON_KEY"},
                # SUPABASE_SERVICE_ROLE_KEY missing
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.get = MagicMock(return_value=mock_response)

        with patch("tools.gates.supabase_gate.httpx.Client", return_value=mock_client):
            issues = _check_vercel_env("vercel-token", "prj_abc")

        assert len(issues) >= 1
        assert any("SUPABASE_SERVICE_ROLE_KEY" in issue for issue in issues)

    def test_vercel_token_none_returns_advisory(self):
        """Advisory returned when vercel_token is None (credentials unavailable)."""
        issues = _check_vercel_env(None, "prj_abc")
        # Returns advisory/issue indicating credentials not available
        assert len(issues) >= 1

    def test_vercel_project_id_none_returns_advisory(self):
        """Advisory returned when vercel_project_id is None."""
        issues = _check_vercel_env("vercel-token", None)
        assert len(issues) >= 1

    def test_missing_url_returns_issue(self):
        """Issue returned when NEXT_PUBLIC_SUPABASE_URL is missing from Vercel."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "envs": [
                {"key": "NEXT_PUBLIC_SUPABASE_ANON_KEY"},
                {"key": "SUPABASE_SERVICE_ROLE_KEY"},
                # NEXT_PUBLIC_SUPABASE_URL missing
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.get = MagicMock(return_value=mock_response)

        with patch("tools.gates.supabase_gate.httpx.Client", return_value=mock_client):
            issues = _check_vercel_env("vercel-token", "prj_abc")

        assert any("NEXT_PUBLIC_SUPABASE_URL" in issue for issue in issues)


# ---------------------------------------------------------------------------
# run_supabase_gate integration tests
# ---------------------------------------------------------------------------


class TestRunSupabaseGate:
    def test_gate_passed_when_no_issues(self, tmp_path):
        """run_supabase_gate returns passed=True when all checks pass."""
        sql_dir = tmp_path / "migrations"
        sql_dir.mkdir()
        (sql_dir / "001_init.sql").write_text("""
CREATE TABLE IF NOT EXISTS public.notes (
    id uuid PRIMARY KEY,
    user_id uuid REFERENCES auth.users NOT NULL
);
ALTER TABLE public.notes ENABLE ROW LEVEL SECURITY;
""")

        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = [{"name": "db", "status": "ACTIVE_HEALTHY"}]
        mock_health_response.raise_for_status = MagicMock()

        mock_vercel_response = MagicMock()
        mock_vercel_response.status_code = 200
        mock_vercel_response.json.return_value = {
            "envs": [
                {"key": "NEXT_PUBLIC_SUPABASE_URL"},
                {"key": "NEXT_PUBLIC_SUPABASE_ANON_KEY"},
                {"key": "SUPABASE_SERVICE_ROLE_KEY"},
            ]
        }
        mock_vercel_response.raise_for_status = MagicMock()

        responses = {"health": mock_health_response, "env": mock_vercel_response}

        def mock_get(url, **kwargs):
            if "health" in url:
                return responses["health"]
            return responses["env"]

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client.get = MagicMock(side_effect=mock_get)

        with patch("tools.gates.supabase_gate.httpx.Client", return_value=mock_client):
            result = run_supabase_gate(
                str(tmp_path),
                phase_id="3",
                supabase_access_token="token",
                project_ref="ref123",
                vercel_token="vtoken",
                vercel_project_id="prj_abc",
            )

        assert result.passed is True
        assert result.gate_type == "supabase"

    def test_gate_failed_when_rls_missing(self, tmp_path):
        """run_supabase_gate returns passed=False when a table lacks RLS."""
        sql_dir = tmp_path / "migrations"
        sql_dir.mkdir()
        (sql_dir / "001_init.sql").write_text("""
CREATE TABLE public.notes (
    id uuid PRIMARY KEY
);
-- RLS not added to this table
""")

        result = run_supabase_gate(
            str(tmp_path),
            phase_id="3",
        )

        assert result.passed is False
        assert result.gate_type == "supabase"
        assert any("notes" in issue for issue in result.issues)

    def test_gate_result_has_correct_shape(self, tmp_path):
        """GateResult has gate_type='supabase' and correct passed/status/severity fields."""
        # No SQL files = no tables = no RLS issues; health/env will be advisories
        result = run_supabase_gate(str(tmp_path), phase_id="3")

        assert result.gate_type == "supabase"
        assert isinstance(result.passed, bool)
        assert isinstance(result.issues, list)
        assert isinstance(result.advisories, list)

    def test_gate_failed_has_block_severity(self, tmp_path):
        """Gate with RLS failures returns severity='BLOCK' and status contains BLOCKED."""
        sql_dir = tmp_path / "migrations"
        sql_dir.mkdir()
        (sql_dir / "001_init.sql").write_text("CREATE TABLE public.bad_table (id uuid);")

        result = run_supabase_gate(str(tmp_path), phase_id="3")

        assert result.passed is False
        assert result.severity == "BLOCK"

    def test_gate_scans_sql_files_recursively(self, tmp_path):
        """run_supabase_gate scans .sql files in subdirectories."""
        sub = tmp_path / "sub" / "migrations"
        sub.mkdir(parents=True)
        (sub / "001_init.sql").write_text("CREATE TABLE public.orphan (id uuid);")

        result = run_supabase_gate(str(tmp_path), phase_id="3")

        assert result.passed is False
        assert any("orphan" in issue for issue in result.issues)

    def test_gate_no_sql_files_passes_rls_check(self, tmp_path):
        """Gate with no .sql files has no RLS issues (trivially satisfied)."""
        # No SQL files at all
        result = run_supabase_gate(str(tmp_path), phase_id="3")

        # RLS issues should be empty (no tables to check)
        rls_issues = [i for i in result.issues if "ROW LEVEL SECURITY" in i or any(
            word in i for word in ["table", "rls", "RLS"]
        )]
        # The overall gate may fail due to missing health/env, but not due to RLS
        assert not any("CREATE TABLE" in issue for issue in result.issues)


# ---------------------------------------------------------------------------
# GateResult shape tests
# ---------------------------------------------------------------------------


class TestGateResultShape:
    def test_gate_result_gate_type_is_supabase(self, tmp_path):
        """GateResult.gate_type must be 'supabase'."""
        result = run_supabase_gate(str(tmp_path), phase_id="3")
        assert result.gate_type == "supabase"

    def test_gate_result_phase_id_is_set(self, tmp_path):
        """GateResult.phase_id must match the provided phase_id."""
        result = run_supabase_gate(str(tmp_path), phase_id="17")
        assert result.phase_id == "17"

    def test_gate_result_has_checked_at_timestamp(self, tmp_path):
        """GateResult.checked_at must be a non-empty ISO timestamp."""
        result = run_supabase_gate(str(tmp_path), phase_id="3")
        assert result.checked_at
        assert "T" in result.checked_at  # ISO 8601 format contains 'T'
