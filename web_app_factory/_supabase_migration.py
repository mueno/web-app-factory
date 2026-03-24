"""Supabase migration SQL generator with RLS-default security.

Generates CREATE TABLE + ENABLE ROW LEVEL SECURITY + 4 CRUD policies
for every table in the given entity list.

Security design:
- Every table gets ENABLE ROW LEVEL SECURITY by default
- Every table gets user_id uuid REFERENCES auth.users NOT NULL (multi-tenant isolation)
- Policies use (SELECT auth.uid()) subquery to avoid per-row re-evaluation (performance)
- Policies target the 'authenticated' role (not 'public')
- A CREATE INDEX on user_id is added per table to support efficient row-level scans (Pitfall 4)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_migration_sql(entities: list[dict[str, Any]]) -> str:
    """Generate secure migration SQL for the given entity list.

    Every table receives:
    - CREATE TABLE with user_id uuid REFERENCES auth.users NOT NULL
    - ALTER TABLE ... ENABLE ROW LEVEL SECURITY
    - 4 CRUD policies (SELECT/INSERT/UPDATE/DELETE) using (SELECT auth.uid())
    - CREATE INDEX on user_id

    Args:
        entities: List of entity dicts, each with:
            - name (str): table name
            - columns (list[dict]): columns without user_id (added automatically)

    Returns:
        str: Complete PostgreSQL migration SQL string.
    """
    if not entities:
        return ""

    parts: list[str] = []
    for entity in entities:
        parts.append(_generate_table_sql(entity))

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_table_sql(entity: dict[str, Any]) -> str:
    """Generate full SQL block for a single entity table.

    Args:
        entity: dict with 'name' and 'columns'.

    Returns:
        str: SQL for CREATE TABLE + RLS + policies + index.
    """
    table_name = entity["name"]
    columns: list[dict] = entity.get("columns", [])

    # Build column definitions
    col_defs = ["    id uuid PRIMARY KEY DEFAULT gen_random_uuid()"]
    col_defs.append("    user_id uuid REFERENCES auth.users NOT NULL")
    for col in columns:
        col_name = col["name"]
        col_type = col.get("type", "text")
        nullable = col.get("nullable", True)
        null_clause = "" if nullable else " NOT NULL"
        col_defs.append(f"    {col_name} {col_type}{null_clause}")
    col_defs.append("    created_at timestamptz DEFAULT now()")

    col_block = ",\n".join(col_defs)

    create_table = (
        f"CREATE TABLE IF NOT EXISTS public.{table_name} (\n"
        f"{col_block}\n"
        ");"
    )

    enable_rls = f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY;"

    rls_policies = _generate_rls_policies(table_name)

    index = f"CREATE INDEX ON public.{table_name} (user_id);"

    return "\n\n".join([create_table, enable_rls, rls_policies, index])


def _generate_rls_policies(table_name: str) -> str:
    """Generate 4 CRUD RLS policies for a table.

    Uses (SELECT auth.uid()) subquery pattern to avoid per-row re-evaluation.
    All policies target the 'authenticated' role.

    Args:
        table_name: PostgreSQL table name.

    Returns:
        str: SQL for SELECT, INSERT, UPDATE, DELETE policies.
    """
    # Use (SELECT auth.uid()) subquery as recommended to prevent planner
    # from re-evaluating auth.uid() for every row in a scan.
    uid_expr = "(SELECT auth.uid())"

    select_policy = (
        f"CREATE POLICY \"{table_name}_select_own\"\n"
        f"  ON public.{table_name}\n"
        f"  FOR SELECT\n"
        f"  TO authenticated\n"
        f"  USING ({uid_expr} = user_id);"
    )

    insert_policy = (
        f"CREATE POLICY \"{table_name}_insert_own\"\n"
        f"  ON public.{table_name}\n"
        f"  FOR INSERT\n"
        f"  TO authenticated\n"
        f"  WITH CHECK ({uid_expr} = user_id);"
    )

    update_policy = (
        f"CREATE POLICY \"{table_name}_update_own\"\n"
        f"  ON public.{table_name}\n"
        f"  FOR UPDATE\n"
        f"  TO authenticated\n"
        f"  USING ({uid_expr} = user_id)\n"
        f"  WITH CHECK ({uid_expr} = user_id);"
    )

    delete_policy = (
        f"CREATE POLICY \"{table_name}_delete_own\"\n"
        f"  ON public.{table_name}\n"
        f"  FOR DELETE\n"
        f"  TO authenticated\n"
        f"  USING ({uid_expr} = user_id);"
    )

    return "\n\n".join([select_policy, insert_policy, update_policy, delete_policy])
