"""BackendSpecValidator gate.

Scans generated Next.js API route files for:
- BGEN-03/06: Missing Zod import or missing safeParse call
- BGEN-05:    Missing /api/health/route.ts endpoint
- BGEN-06:    Hardcoded raw secrets (API keys, tokens, passwords)
- SECG-03:    String concatenation in Supabase RPC/SQL calls (SQL injection risk)

All checks are blocking — issues go into GateResult.issues, never into advisories.

Exported function: run_backend_spec_gate
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from tools.gates.gate_result import GateResult

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# BGEN-03/06: Zod import — matches: from 'zod' or from "zod"
_ZOD_IMPORT_RE = re.compile(r"""from\s+['"]zod['"]""")

# BGEN-03/06: Zod safeParse call
_ZOD_SAFE_PARSE_RE = re.compile(r"""\.safeParse\s*\(""")

# SECG-03: SQL injection via string concatenation in supabase query methods.
# Catches:
#   supabase.rpc(`SELECT * FROM ${tableName}`)     — template literal with ${...}
#   supabase.rpc('query' + userInput)              — string concatenation with +
#   supabase.sql(`SELECT * FROM ${tableName}`)
# The pattern matches supabase.rpc(... or supabase.sql(... followed by either
# a string concat (+) or a template literal containing ${...}.
_SQL_INJECTION_RE = re.compile(
    r"""supabase\s*\.\s*(?:rpc|sql)\s*\("""
    r"""(?:[^)]*\+[^)]*|`[^`]*\$\{[^`]*\`)""",
    re.IGNORECASE | re.DOTALL,
)

# BGEN-06: Hardcoded API keys / secrets / tokens / passwords.
# Matches: apiKey = "sk-proj-abc..." / secret = "long-value" / token = "..."
# Requires the value to be at least 20 characters to reduce false positives.
_RAW_SECRET_RE = re.compile(
    r"""(?:apiKey|api_key|secret|token|password)\s*=\s*['"][A-Za-z0-9_\-]{20,}['"]""",
    re.IGNORECASE,
)

# Relative path segment for the health endpoint
_HEALTH_ROUTE_REL = Path("src") / "app" / "api" / "health" / "route.ts"

# Route file extensions to scan
_ROUTE_FILE_NAMES = {"route.ts", "route.js"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_health_route(filepath: Path, project_dir: Path) -> bool:
    """Return True if *filepath* is the health endpoint route file."""
    try:
        rel = filepath.relative_to(project_dir)
        return rel == _HEALTH_ROUTE_REL
    except ValueError:
        return False


def _check_route_zod_validation(filepath: Path, project_dir: Path) -> list[str]:
    """BGEN-03/06: Route files must import Zod AND call safeParse.

    Health endpoint is excluded — it has no user inputs to validate.
    """
    # Health endpoint is intentionally excluded from Zod validation
    if _is_health_route(filepath, project_dir):
        return []

    issues: list[str] = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel = filepath.relative_to(project_dir)
    has_import = bool(_ZOD_IMPORT_RE.search(content))
    has_safe_parse = bool(_ZOD_SAFE_PARSE_RE.search(content))

    if not has_import:
        issues.append(
            f"{rel}: missing Zod import — route lacks input validation (add: import {{ z }} from \"zod\")"
        )
    elif not has_safe_parse:
        issues.append(
            f"{rel}: Zod imported but safeParse not found — inputs may be unvalidated (use schema.safeParse())"
        )

    return issues


def _check_sql_injection(filepath: Path, project_dir: Path) -> list[str]:
    """SECG-03: Detect string concatenation in Supabase RPC/SQL calls."""
    issues: list[str] = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    if _SQL_INJECTION_RE.search(content):
        rel = filepath.relative_to(project_dir)
        issues.append(
            f"{rel}: SQL injection risk — string concatenation in supabase.rpc()/supabase.sql() "
            f"detected; use parameterized queries or supabase.from().select().eq() instead"
        )

    return issues


def _check_raw_secrets(filepath: Path, project_dir: Path) -> list[str]:
    """BGEN-06: Detect hardcoded API keys, tokens, or secrets."""
    issues: list[str] = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    if _RAW_SECRET_RE.search(content):
        rel = filepath.relative_to(project_dir)
        issues.append(
            f"{rel}: raw/hardcoded secret detected — use process.env.VARIABLE_NAME instead of "
            f"hardcoded API keys, tokens, or passwords"
        )

    return issues


def _collect_route_files(api_dir: Path) -> list[Path]:
    """Recursively collect all route.ts and route.js files under *api_dir*."""
    files: list[Path] = []
    for filepath in api_dir.rglob("*"):
        if filepath.is_file() and filepath.name in _ROUTE_FILE_NAMES:
            files.append(filepath)
    return files


# ---------------------------------------------------------------------------
# Public gate function
# ---------------------------------------------------------------------------


def run_backend_spec_gate(project_dir: str, *, phase_id: str = "2b") -> GateResult:
    """Run BackendSpecValidator gate on the generated Next.js project.

    Performs four checks on files under src/app/api/:
    1. BGEN-03/06: Every route (except health) has a Zod import AND safeParse call
    2. BGEN-05:    src/app/api/health/route.ts must exist
    3. BGEN-06:    No hardcoded API keys, tokens, or secrets
    4. SECG-03:    No string concatenation in supabase.rpc() / supabase.sql() calls

    Graceful skip: if src/app/api/ does not exist, returns passed=True (the app
    has no backend routes — nothing to validate).

    All issues are blocking (placed in GateResult.issues, never advisories).

    Args:
        project_dir: Absolute path to the generated Next.js project directory.
        phase_id:    Pipeline phase identifier (default "2b").

    Returns:
        GateResult with gate_type="backend_spec" and passed=True only when no
        issues are found.
    """
    checked_at = _now_iso()
    base = Path(project_dir)
    api_dir = base / "src" / "app" / "api"

    # Graceful skip: no backend routes to validate
    if not api_dir.exists():
        return GateResult(
            gate_type="backend_spec",
            phase_id=phase_id,
            passed=True,
            status="PASS",
            severity="INFO",
            confidence=1.0,
            checked_at=checked_at,
            issues=[],
            advisories=[],
        )

    route_files = _collect_route_files(api_dir)

    # If the api/ directory exists but has no route files — skip gracefully
    if not route_files:
        return GateResult(
            gate_type="backend_spec",
            phase_id=phase_id,
            passed=True,
            status="PASS",
            severity="INFO",
            confidence=1.0,
            checked_at=checked_at,
            issues=[],
            advisories=[],
        )

    issues: list[str] = []

    # Check 1 & 3 & 4: Per-file checks
    for filepath in sorted(route_files):
        issues.extend(_check_route_zod_validation(filepath, base))
        issues.extend(_check_sql_injection(filepath, base))
        issues.extend(_check_raw_secrets(filepath, base))

    # Check 2: Health endpoint existence
    health_route = base / _HEALTH_ROUTE_REL
    if not health_route.exists():
        issues.append(
            "src/app/api/health/route.ts is missing — health endpoint must always be generated; "
            "add GET handler returning { ok: true, service: string, timestamp: string }"
        )

    passed = len(issues) == 0
    status = "PASS" if passed else "BLOCKED"
    severity = "INFO" if passed else "BLOCK"
    confidence = 1.0 if passed else 0.0

    return GateResult(
        gate_type="backend_spec",
        phase_id=phase_id,
        passed=passed,
        status=status,
        severity=severity,
        confidence=confidence,
        checked_at=checked_at,
        issues=issues,
        advisories=[],
    )
