"""Tests for tools/gates/backend_spec_gate.py — BackendSpecValidator gate.

Covers:
- BGEN-03: Zod import check (missing import)
- BGEN-03: Zod safeParse check (import present but safeParse missing)
- BGEN-05: Health endpoint existence check
- BGEN-06: All issues are blocking (in `issues` list, never `advisories`)
- SECG-03: SQL injection pattern detection (string concatenation in Supabase RPC/SQL)
- Gate type is "backend_spec"
- Graceful skip when no src/app/api/ directory exists
- Template files contain expected TypeScript patterns
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_file(base: Path, rel_path: str, content: str) -> Path:
    """Create a file with given content relative to base directory."""
    target = base / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _make_valid_route(base: Path, rel_path: str) -> Path:
    """Create a valid route.ts that passes all gate checks."""
    content = """\
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";

const CreateTodoSchema = z.object({
  title: z.string().min(1).max(255),
});

export async function POST(request: Request): Promise<Response> {
  const bodyRaw = await request.json();
  const parsed = CreateTodoSchema.safeParse(bodyRaw);

  if (!parsed.success) {
    return Response.json(
      { error: parsed.error.issues[0]?.message ?? "Validation failed", code: "VALIDATION_ERROR" },
      { status: 422 }
    );
  }

  const supabase = await createClient();
  const { data, error } = await supabase
    .from("todos")
    .insert(parsed.data)
    .select()
    .single();

  if (error) {
    return Response.json({ error: "Failed to create", code: "DB_ERROR" }, { status: 500 });
  }

  return Response.json(data, { status: 201 });
}
"""
    return _write_file(base, rel_path, content)


def _make_health_route(base: Path) -> Path:
    """Create a valid health route.ts."""
    content = """\
export async function GET(): Promise<Response> {
  return Response.json({
    ok: true,
    service: "web-app-factory-generated",
    timestamp: new Date().toISOString(),
  });
}
"""
    return _write_file(base, "src/app/api/health/route.ts", content)


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestGateType:
    """Gate metadata tests."""

    def test_gate_type_is_backend_spec(self, tmp_path):
        """run_backend_spec_gate returns GateResult with gate_type='backend_spec'."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        result = run_backend_spec_gate(str(tmp_path))

        assert result.gate_type == "backend_spec"

    def test_gate_type_preserved_when_issues_found(self, tmp_path):
        """gate_type is 'backend_spec' even when there are issues."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _write_file(tmp_path, "src/app/api/todos/route.ts", "// no zod import\nexport async function GET() {}")

        result = run_backend_spec_gate(str(tmp_path))

        assert result.gate_type == "backend_spec"


class TestZodImportCheck:
    """BGEN-03/06: Routes must import Zod."""

    def test_route_without_zod_import_fails(self, tmp_path):
        """A route.ts without 'from \"zod\"' import fails the gate."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        _write_file(
            tmp_path,
            "src/app/api/todos/route.ts",
            "// no zod import\nexport async function GET() { return Response.json([]); }",
        )

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is False
        assert any("missing Zod import" in issue or "zod" in issue.lower() for issue in result.issues)

    def test_issue_mentions_missing_zod_import(self, tmp_path):
        """Issue string explicitly mentions 'missing Zod import'."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        _write_file(
            tmp_path,
            "src/app/api/todos/route.ts",
            "export async function GET() { return Response.json([]); }",
        )

        result = run_backend_spec_gate(str(tmp_path))

        assert any("missing Zod import" in issue for issue in result.issues)

    def test_route_with_zod_import_and_safe_parse_passes_zod_check(self, tmp_path):
        """A route.ts with both zod import and safeParse passes the Zod check."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        _make_valid_route(tmp_path, "src/app/api/todos/route.ts")

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is True
        assert result.issues == []


class TestSafeParseCheck:
    """BGEN-03/06: Routes that import Zod must also call safeParse."""

    def test_route_with_zod_import_but_no_safe_parse_fails(self, tmp_path):
        """A route that imports zod but never calls safeParse fails the gate."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        _write_file(
            tmp_path,
            "src/app/api/todos/route.ts",
            'import { z } from "zod";\n\nexport async function GET() { return Response.json([]); }',
        )

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is False

    def test_issue_mentions_safe_parse_not_found(self, tmp_path):
        """Issue string mentions safeParse not found when zod is imported but not used."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        _write_file(
            tmp_path,
            "src/app/api/todos/route.ts",
            'import { z } from "zod";\n\nexport async function POST(request: Request) { return Response.json({}); }',
        )

        result = run_backend_spec_gate(str(tmp_path))

        assert any("safeParse" in issue for issue in result.issues)


class TestSqlInjectionCheck:
    """SECG-03: String concatenation in Supabase RPC/SQL calls must be blocked."""

    def test_template_literal_with_variable_in_rpc_fails(self, tmp_path):
        """supabase.rpc(`SELECT * FROM ${tableName}`) fails the gate."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        content = """\
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";

const schema = z.object({ tableName: z.string() });

export async function POST(request: Request): Promise<Response> {
  const { tableName } = schema.safeParse(await request.json()).data!;
  const supabase = await createClient();
  const { data } = await supabase.rpc(`SELECT * FROM ${tableName}`);
  return Response.json(data);
}
"""
        _write_file(tmp_path, "src/app/api/query/route.ts", content)

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is False
        assert any("sql injection" in issue.lower() or "string concat" in issue.lower() or "injection" in issue.lower() for issue in result.issues)

    def test_string_concatenation_in_rpc_fails(self, tmp_path):
        """supabase.rpc('query' + userInput) fails the gate."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        content = """\
import { z } from "zod";
import { createClient } from "@/lib/supabase/server";

const schema = z.object({ userInput: z.string() });

export async function POST(request: Request): Promise<Response> {
  const { userInput } = schema.safeParse(await request.json()).data!;
  const supabase = await createClient();
  const { data } = await supabase.rpc('query' + userInput);
  return Response.json(data);
}
"""
        _write_file(tmp_path, "src/app/api/query/route.ts", content)

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is False
        assert any("sql injection" in issue.lower() or "string concat" in issue.lower() or "injection" in issue.lower() for issue in result.issues)

    def test_safe_supabase_query_passes(self, tmp_path):
        """supabase.from('todos').select() passes the SQL injection check."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        _make_valid_route(tmp_path, "src/app/api/todos/route.ts")

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is True
        assert result.issues == []


class TestRawSecretCheck:
    """BGEN-06: Hardcoded secrets must be blocked."""

    def test_hardcoded_api_key_fails(self, tmp_path):
        """A route with apiKey = 'sk-proj-abc...' fails the gate."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        content = """\
import { z } from "zod";

const schema = z.object({ q: z.string() });
const apiKey = "sk-proj-abc1234567890abcdefghijk";

export async function POST(request: Request): Promise<Response> {
  const parsed = schema.safeParse(await request.json());
  if (!parsed.success) return Response.json({ error: "bad", code: "ERR" }, { status: 422 });
  return Response.json({ key: apiKey });
}
"""
        _write_file(tmp_path, "src/app/api/secret/route.ts", content)

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is False
        assert any("secret" in issue.lower() or "hardcoded" in issue.lower() or "raw" in issue.lower() for issue in result.issues)

    def test_env_var_reference_passes(self, tmp_path):
        """A route that uses process.env for secrets passes the secret check."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        content = """\
import { z } from "zod";

const schema = z.object({ q: z.string() });
const apiKey = process.env.OPENAI_API_KEY;

export async function POST(request: Request): Promise<Response> {
  const parsed = schema.safeParse(await request.json());
  if (!parsed.success) return Response.json({ error: "bad", code: "ERR" }, { status: 422 });
  return Response.json({ ok: true });
}
"""
        _write_file(tmp_path, "src/app/api/ai/route.ts", content)

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is True
        assert result.issues == []


class TestHealthEndpointCheck:
    """BGEN-05: Health endpoint must exist."""

    def test_missing_health_route_fails(self, tmp_path):
        """Gate fails when src/app/api/health/route.ts does not exist."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        # Create an API directory but no health route
        _make_valid_route(tmp_path, "src/app/api/todos/route.ts")

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is False
        assert any("health" in issue.lower() for issue in result.issues)

    def test_present_health_route_passes_health_check(self, tmp_path):
        """Gate passes the health check when src/app/api/health/route.ts exists."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        _make_valid_route(tmp_path, "src/app/api/todos/route.ts")

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is True


class TestBlockingIssues:
    """BGEN-06: All issues must be blocking (in `issues` list, never `advisories`)."""

    def test_zod_issue_is_blocking_not_advisory(self, tmp_path):
        """Missing Zod import is in `issues` list, not `advisories`."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        _write_file(tmp_path, "src/app/api/todos/route.ts", "export async function GET() {}")

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is False
        assert len(result.issues) > 0
        assert result.advisories == []

    def test_sql_injection_issue_is_blocking(self, tmp_path):
        """SQL injection pattern is in `issues` list, not `advisories`."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        content = """\
import { z } from "zod";
const schema = z.object({ t: z.string() });
export async function GET(req: Request) {
  const parsed = schema.safeParse({});
  if (!parsed.success) return Response.json({error:"e",code:"E"},{status:422});
  const supabase = {rpc: async (q: string) => ({data: null})};
  return Response.json(await supabase.rpc('SELECT * FROM ' + 'todos'));
}
"""
        _write_file(tmp_path, "src/app/api/query/route.ts", content)

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is False
        assert result.advisories == []

    def test_secret_issue_is_blocking(self, tmp_path):
        """Hardcoded secret is in `issues` list, not `advisories`."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_health_route(tmp_path)
        content = """\
import { z } from "zod";
const schema = z.object({ x: z.string() });
const token = "ghp_1234567890abcdefghij1234567890";
export async function GET() {
  const parsed = schema.safeParse({});
  if (!parsed.success) return Response.json({error:"e",code:"E"},{status:422});
  return Response.json({ ok: true });
}
"""
        _write_file(tmp_path, "src/app/api/token/route.ts", content)

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is False
        assert result.advisories == []

    def test_health_missing_is_blocking(self, tmp_path):
        """Missing health endpoint is in `issues` list, not `advisories`."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        _make_valid_route(tmp_path, "src/app/api/todos/route.ts")

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is False
        assert result.advisories == []


class TestGracefulSkip:
    """Gate should pass gracefully when no API routes exist."""

    def test_empty_project_no_api_dir_returns_passed(self, tmp_path):
        """Empty project directory (no src/app/api/) returns passed=True."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is True
        assert result.issues == []
        assert result.gate_type == "backend_spec"

    def test_project_with_src_but_no_api_dir_returns_passed(self, tmp_path):
        """Project with src/ but no src/app/api/ returns passed=True."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        (tmp_path / "src" / "app").mkdir(parents=True)

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is True
        assert result.issues == []

    def test_project_with_api_dir_but_no_routes_returns_passed(self, tmp_path):
        """Project with src/app/api/ directory but no route.ts files returns passed=True.

        Note: health endpoint check requires routes to exist first (no-route projects
        skip gracefully), but an api/ directory with no routes is unusual.
        Gate passes since there are no route files to validate.
        """
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        (tmp_path / "src" / "app" / "api").mkdir(parents=True)

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is True


class TestHealthRouteExcluded:
    """Health route is excluded from Zod validation checks (no input to validate)."""

    def test_health_route_not_checked_for_zod(self, tmp_path):
        """Health route.ts without Zod import does NOT trigger Zod check."""
        from tools.gates.backend_spec_gate import run_backend_spec_gate

        # Health route without Zod (correct — health endpoint has no inputs)
        _write_file(
            tmp_path,
            "src/app/api/health/route.ts",
            "export async function GET(): Promise<Response> { return Response.json({ ok: true }); }",
        )
        # Non-health route with valid Zod
        _make_valid_route(tmp_path, "src/app/api/todos/route.ts")

        result = run_backend_spec_gate(str(tmp_path))

        assert result.passed is True
        assert result.issues == []


class TestTemplateFiles:
    """BGEN-07: Template files exist and contain expected TypeScript patterns."""

    @pytest.fixture
    def templates_dir(self) -> Path:
        """Return the backend templates directory path."""
        return Path(__file__).parent.parent / "web_app_factory" / "templates" / "backend"

    def test_error_helpers_template_exists(self, templates_dir):
        """error-helpers.ts.tmpl exists."""
        assert (templates_dir / "error-helpers.ts.tmpl").exists()

    def test_health_route_template_exists(self, templates_dir):
        """health-route.ts.tmpl exists."""
        assert (templates_dir / "health-route.ts.tmpl").exists()

    def test_with_validation_template_exists(self, templates_dir):
        """with-validation.ts.tmpl exists."""
        assert (templates_dir / "with-validation.ts.tmpl").exists()

    def test_error_helpers_contains_api_error_function(self, templates_dir):
        """error-helpers.ts.tmpl exports apiError function."""
        content = (templates_dir / "error-helpers.ts.tmpl").read_text(encoding="utf-8")
        assert "apiError" in content

    def test_health_route_contains_get_handler(self, templates_dir):
        """health-route.ts.tmpl exports a GET handler function."""
        content = (templates_dir / "health-route.ts.tmpl").read_text(encoding="utf-8")
        assert "GET" in content

    def test_with_validation_template_contains_safe_parse(self, templates_dir):
        """with-validation.ts.tmpl demonstrates safeParse usage."""
        content = (templates_dir / "with-validation.ts.tmpl").read_text(encoding="utf-8")
        assert "safeParse" in content
