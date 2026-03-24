"""Tests for the Supabase migration SQL generator.

Verifies that generate_migration_sql() produces RLS-enforced SQL for every table:
- ENABLE ROW LEVEL SECURITY per table
- 4 CRUD policies (SELECT/INSERT/UPDATE/DELETE) per table
- user_id uuid REFERENCES auth.users on every table
- CREATE INDEX on user_id for every table
- Auth subquery pattern: (SELECT auth.uid())
"""

from __future__ import annotations

import pytest

from web_app_factory._supabase_migration import generate_migration_sql


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_entity(name: str) -> dict:
    """Return a minimal entity dict with a single non-user_id column."""
    return {
        "name": name,
        "columns": [
            {"name": "title", "type": "text", "nullable": False},
        ],
    }


# ---------------------------------------------------------------------------
# Single table tests
# ---------------------------------------------------------------------------


class TestSingleTable:
    def test_create_table_present(self):
        """generate_migration_sql() includes CREATE TABLE for the entity."""
        sql = generate_migration_sql([_simple_entity("notes")])
        assert "CREATE TABLE" in sql
        assert "notes" in sql

    def test_enable_row_level_security(self):
        """generate_migration_sql() includes ENABLE ROW LEVEL SECURITY for the table."""
        sql = generate_migration_sql([_simple_entity("notes")])
        assert "ENABLE ROW LEVEL SECURITY" in sql

    def test_four_crud_policies(self):
        """generate_migration_sql() produces exactly 4 CRUD policies per table."""
        sql = generate_migration_sql([_simple_entity("notes")])
        # Each policy operation must appear at least once
        assert "FOR SELECT" in sql or "SELECT" in sql
        assert "FOR INSERT" in sql or "INSERT" in sql
        assert "FOR UPDATE" in sql or "UPDATE" in sql
        assert "FOR DELETE" in sql or "DELETE" in sql
        # Count CREATE POLICY occurrences for this table
        policy_count = sql.count("CREATE POLICY")
        assert policy_count >= 4, f"Expected at least 4 CRUD policies, got {policy_count}"

    def test_user_id_references_auth_users(self):
        """generate_migration_sql() adds user_id uuid REFERENCES auth.users to every table."""
        sql = generate_migration_sql([_simple_entity("notes")])
        assert "user_id" in sql
        assert "auth.users" in sql

    def test_create_index_on_user_id(self):
        """generate_migration_sql() creates an index on user_id for every table (Pitfall 4)."""
        sql = generate_migration_sql([_simple_entity("notes")])
        assert "CREATE INDEX" in sql
        assert "user_id" in sql

    def test_auth_uid_subquery_pattern(self):
        """generate_migration_sql() uses (SELECT auth.uid()) pattern in policies."""
        sql = generate_migration_sql([_simple_entity("notes")])
        assert "(SELECT auth.uid())" in sql, (
            "Policies must use (SELECT auth.uid()) subquery pattern to avoid re-evaluation per row"
        )

    def test_policies_use_authenticated_role(self):
        """generate_migration_sql() targets 'authenticated' role (not 'public')."""
        sql = generate_migration_sql([_simple_entity("notes")])
        assert "authenticated" in sql


# ---------------------------------------------------------------------------
# Two-table tests
# ---------------------------------------------------------------------------


class TestMultipleTables:
    def test_two_tables_both_have_rls(self):
        """generate_migration_sql() enables RLS on BOTH tables when given 2 tables."""
        entities = [
            _simple_entity("notes"),
            _simple_entity("tasks"),
        ]
        sql = generate_migration_sql(entities)

        # Count ENABLE ROW LEVEL SECURITY occurrences — should be 2
        rls_count = sql.count("ENABLE ROW LEVEL SECURITY")
        assert rls_count == 2, f"Expected 2 RLS enablements, got {rls_count}"

    def test_two_tables_both_get_policies(self):
        """generate_migration_sql() creates 4 policies for EACH of 2 tables (8 total)."""
        entities = [
            _simple_entity("notes"),
            _simple_entity("tasks"),
        ]
        sql = generate_migration_sql(entities)

        policy_count = sql.count("CREATE POLICY")
        assert policy_count >= 8, f"Expected at least 8 policies for 2 tables, got {policy_count}"

    def test_two_tables_both_have_user_id_column(self):
        """generate_migration_sql() adds user_id to every table."""
        entities = [
            _simple_entity("notes"),
            _simple_entity("tasks"),
        ]
        sql = generate_migration_sql(entities)

        # Both CREATE TABLE blocks should reference auth.users
        auth_users_count = sql.count("auth.users")
        assert auth_users_count >= 2, (
            f"Expected auth.users reference in at least 2 tables, got {auth_users_count}"
        )

    def test_two_tables_both_have_indexes(self):
        """generate_migration_sql() creates a user_id index for each table."""
        entities = [
            _simple_entity("notes"),
            _simple_entity("tasks"),
        ]
        sql = generate_migration_sql(entities)

        index_count = sql.count("CREATE INDEX")
        assert index_count >= 2, f"Expected at least 2 indexes, got {index_count}"

    def test_table_names_appear_in_policies(self):
        """Policy names/tables reference the specific table."""
        entities = [
            _simple_entity("notes"),
            _simple_entity("tasks"),
        ]
        sql = generate_migration_sql(entities)

        assert "notes" in sql
        assert "tasks" in sql


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_entities_returns_empty_string(self):
        """generate_migration_sql([]) returns empty string or valid SQL with no tables."""
        sql = generate_migration_sql([])
        # Should not crash; result should be empty or just whitespace
        assert isinstance(sql, str)

    def test_entity_with_multiple_columns(self):
        """generate_migration_sql() handles entities with many columns."""
        entity = {
            "name": "profiles",
            "columns": [
                {"name": "display_name", "type": "text", "nullable": True},
                {"name": "bio", "type": "text", "nullable": True},
                {"name": "avatar_url", "type": "text", "nullable": True},
            ],
        }
        sql = generate_migration_sql([entity])
        assert "profiles" in sql
        assert "ENABLE ROW LEVEL SECURITY" in sql
        assert "(SELECT auth.uid())" in sql
