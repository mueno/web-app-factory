"""Static analysis gate executor.

Performs regex-based file scanning for:
- GATE-05: 'use client' misplacement in layout.tsx and page.tsx
- GATE-06: NEXT_PUBLIC_ secret-pattern environment variable exposure
- GATE-08: Plaintext sensitive data storage patterns (passwords, PII in DB schemas)
- BILD-06: error.tsx existence for route segments with async data fetching
- BILD-05: Mobile-first responsive Tailwind pattern usage
- FLOW-01: Form/router.push parameter names match receiving page searchParams

Exported function: run_static_analysis_gate
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from tools.gates.gate_result import GateResult

# --- Regex patterns ---

# GATE-05: Match 'use client' directive (single or double quotes)
_USE_CLIENT_RE = re.compile(r"""['"]use client['"]""")

# GATE-06: Match NEXT_PUBLIC_ followed by variables ending in KEY, SECRET, or TOKEN
# Pattern matches: NEXT_PUBLIC_*KEY, NEXT_PUBLIC_*SECRET, NEXT_PUBLIC_*TOKEN
_NEXT_PUBLIC_SECRET_RE = re.compile(r"NEXT_PUBLIC_(?:\w+?_)?(?:.*KEY|.*SECRET|.*TOKEN)")

# Files scanned for GATE-05 (exactly these two files — not error.tsx or nested routes)
_USE_CLIENT_SCAN_FILES = {"layout.tsx", "page.tsx"}

# File extensions scanned for GATE-06 under src/
_SECRET_SCAN_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".env", ".env.local"}

# Root-level env files scanned for GATE-06 (in addition to src/ files)
_ROOT_ENV_FILES = [".env", ".env.local"]

# BILD-06: Patterns indicating async data fetching in page.tsx
_ASYNC_DATA_RE = re.compile(
    r"async\s+function|await\s+fetch\(|\.json\(\)|getServerSideProps|getStaticProps"
)

# BILD-05: Hardcoded pixel widths that break responsiveness
_HARDCODED_WIDTH_RE = re.compile(r'(?:width:\s*["\']?\d{4,}px|w-\[\d{4,}px\])')

# GATE-08: Plaintext sensitive data storage patterns
# Detect DB schema fields that store sensitive data without encryption/hashing.
# Targets: Prisma schema, SQL, TypeScript/JS ORM model definitions.
_PLAINTEXT_PASSWORD_RE = re.compile(
    r"(?:"
    r"password\s+(?:String|TEXT|VARCHAR|text|string|char)"  # Prisma / SQL schema
    r"|password\s*:\s*(?:string|text)"  # TS/JS object type
    r"|(?:column|field)\s*\(\s*['\"]password['\"]"  # ORM decorator
    r")",
    re.IGNORECASE,
)
# Allowlist: these patterns indicate proper hashing/encryption
_PASSWORD_SAFE_RE = re.compile(
    r"(?:passwordHash|password_hash|hashedPassword|hashed_password|bcrypt|argon2|scrypt)",
    re.IGNORECASE,
)

_PLAINTEXT_PII_SCHEMA_RE = re.compile(
    r"(?:ssn|social_security|credit_card|card_number|cardNumber"
    r"|national_id|my_number|マイナンバー)\s+(?:String|TEXT|VARCHAR|text|string|char)",
    re.IGNORECASE,
)

# Files scanned for GATE-08
_SCHEMA_SCAN_PATTERNS = ["*.prisma", "*.sql", "schema.*"]
_SCHEMA_SCAN_EXTENSIONS = {".prisma", ".sql"}

# FLOW-01: Extract URLSearchParams keys from form/component code
_URL_SEARCH_PARAMS_RE = re.compile(
    r"new\s+URLSearchParams\s*\(\s*\{([^}]+)\}", re.DOTALL
)
# FLOW-01: Extract searchParams field access in page.tsx
_SEARCH_PARAMS_ACCESS_RE = re.compile(
    r"params\.(\w+)"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_use_client(project_dir: Path) -> list[str]:
    """GATE-05: Detect 'use client' in layout.tsx and page.tsx only.

    Scans ONLY src/app/layout.tsx and src/app/page.tsx.
    Returns list of issue strings with file path and line number.
    """
    issues: list[str] = []
    src_app = project_dir / "src" / "app"

    for filename in _USE_CLIENT_SCAN_FILES:
        filepath = src_app / filename
        if not filepath.exists():
            continue

        try:
            lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        for lineno, line in enumerate(lines, start=1):
            if _USE_CLIENT_RE.search(line):
                rel_path = filepath.relative_to(project_dir)
                issues.append(f"{rel_path}:{lineno}: 'use client' directive found in server component file")

    return issues


def _should_skip(path: Path) -> bool:
    """Return True if the path should be skipped during scanning."""
    return "node_modules" in path.parts


def _check_next_public_secrets(project_dir: Path) -> list[str]:
    """GATE-06: Detect NEXT_PUBLIC_ secret-pattern variables.

    Scans:
    - All files under src/ with relevant extensions
    - Root .env and .env.local files
    Returns list of issue strings with file path and line number.
    """
    issues: list[str] = []

    def _scan_file(filepath: Path) -> None:
        if not filepath.exists():
            return
        try:
            lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return

        for lineno, line in enumerate(lines, start=1):
            match = _NEXT_PUBLIC_SECRET_RE.search(line)
            if match:
                rel_path = filepath.relative_to(project_dir)
                matched_var = match.group(0)
                issues.append(
                    f"{rel_path}:{lineno}: secret-pattern variable exposed: {matched_var}"
                )

    # Scan root .env files
    for env_filename in _ROOT_ENV_FILES:
        env_path = project_dir / env_filename
        _scan_file(env_path)

    # Scan all files under src/ recursively
    src_dir = project_dir / "src"
    if src_dir.exists():
        for filepath in src_dir.rglob("*"):
            if not filepath.is_file():
                continue
            if _should_skip(filepath):
                continue
            # Check extension — also match .env and .env.local by name
            name = filepath.name
            suffix = filepath.suffix
            if suffix in _SECRET_SCAN_EXTENSIONS or name in (".env", ".env.local"):
                _scan_file(filepath)

    return issues


def _check_error_boundaries(project_dir: Path) -> list[str]:
    """BILD-06: Verify error.tsx exists for route segments with async data fetching.

    Scans all page.tsx files under src/app/ for async patterns. If found,
    checks that a sibling error.tsx exists with 'use client' directive.
    Returns list of issue strings.
    """
    issues: list[str] = []
    src_app = project_dir / "src" / "app"
    if not src_app.exists():
        return issues

    for page_file in src_app.rglob("page.tsx"):
        if _should_skip(page_file):
            continue

        try:
            content = page_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if not _ASYNC_DATA_RE.search(content):
            continue

        # This page has async data fetching — error.tsx must exist
        error_file = page_file.parent / "error.tsx"
        rel_dir = page_file.parent.relative_to(project_dir)

        if not error_file.exists():
            issues.append(
                f"{rel_dir}/: page.tsx has async data fetching but no error.tsx boundary"
            )
            continue

        # error.tsx must have 'use client'
        try:
            error_content = error_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if not _USE_CLIENT_RE.search(error_content):
            issues.append(
                f"{rel_dir}/error.tsx: missing 'use client' directive (required for error boundaries)"
            )

    return issues


def _check_responsive_patterns(project_dir: Path) -> list[str]:
    """BILD-05: Check for responsive Tailwind usage and flag hardcoded widths.

    Advisory-level: warns on hardcoded large pixel widths that break responsiveness.
    Returns list of issue strings.
    """
    issues: list[str] = []
    src_dir = project_dir / "src"
    if not src_dir.exists():
        return issues

    for filepath in src_dir.rglob("*.tsx"):
        if _should_skip(filepath):
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = content.splitlines()
        for lineno, line in enumerate(lines, start=1):
            if _HARDCODED_WIDTH_RE.search(line):
                rel_path = filepath.relative_to(project_dir)
                issues.append(
                    f"{rel_path}:{lineno}: hardcoded pixel width breaks responsive design"
                )

    return issues


def _check_form_page_params(project_dir: Path) -> list[str]:
    """FLOW-01: Verify form submission parameter names match receiving page searchParams.

    Scans all .tsx files under src/ for URLSearchParams construction, extracts
    the keys, then finds the target route's page.tsx and checks that the same
    keys are read via searchParams access. Reports mismatches.
    """
    issues: list[str] = []
    src_dir = project_dir / "src"
    if not src_dir.exists():
        return issues

    # Phase 1: Collect all URLSearchParams constructions with their target routes
    router_push_re = re.compile(
        r"router\.push\s*\(\s*`([^`]+)\$\{params", re.DOTALL
    )
    # Also match router.push(`/path?${params.toString()}`)
    router_push_path_re = re.compile(
        r"router\.push\s*\(\s*`(/[^?`]+)\?", re.DOTALL
    )

    for filepath in src_dir.rglob("*.tsx"):
        if _should_skip(filepath):
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Find URLSearchParams construction
        params_match = _URL_SEARCH_PARAMS_RE.search(content)
        if not params_match:
            continue

        # Extract parameter keys from the URLSearchParams object literal
        params_body = params_match.group(1)
        sent_keys = set(re.findall(r"(\w+)\s*:", params_body))
        if not sent_keys:
            continue

        # Find the target route from router.push
        route_match = router_push_path_re.search(content)
        if not route_match:
            continue
        target_route = route_match.group(1)

        # Resolve the target page.tsx
        # Convert route like /simulate/results to src/app/simulate/results/page.tsx
        route_parts = target_route.strip("/").split("/")
        page_path = project_dir / "src" / "app" / "/".join(route_parts) / "page.tsx"

        if not page_path.exists():
            continue

        try:
            page_content = page_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Extract searchParams field accesses in the receiving page
        received_keys = set(_SEARCH_PARAMS_ACCESS_RE.findall(page_content))
        if not received_keys:
            continue

        # Compare: keys sent by form but not read by page (or vice versa)
        sent_not_received = sent_keys - received_keys
        received_not_sent = received_keys - sent_keys

        rel_sender = filepath.relative_to(project_dir)
        rel_receiver = page_path.relative_to(project_dir)

        if received_not_sent:
            issues.append(
                f"FLOW-01: {rel_receiver} reads params {sorted(received_not_sent)} "
                f"but {rel_sender} never sends them — form will always show empty state"
            )

    return issues


def _check_plaintext_storage(project_dir: Path) -> list[str]:
    """GATE-08: Detect plaintext sensitive data patterns in DB schemas and models.

    Scans Prisma schemas, SQL files, and TypeScript model definitions for:
    - Password fields without Hash/hashed suffix (should use bcrypt/argon2)
    - Raw PII fields (SSN, credit card, national ID) that should never be plaintext

    Returns list of issue strings.
    """
    issues: list[str] = []

    # Collect files to scan: schema files + all .ts/.tsx under src/lib and src/
    files_to_scan: list[Path] = []

    # Schema files at project root or in prisma/
    for pattern in ("*.prisma", "prisma/*.prisma", "*.sql", "schema.*"):
        files_to_scan.extend(project_dir.glob(pattern))

    # TypeScript model/lib files that may define DB schemas
    src_dir = project_dir / "src"
    if src_dir.exists():
        for ext in (".ts", ".tsx"):
            for filepath in src_dir.rglob(f"*{ext}"):
                if not _should_skip(filepath):
                    files_to_scan.append(filepath)

    for filepath in files_to_scan:
        if not filepath.is_file():
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        rel_path = filepath.relative_to(project_dir)
        lines = content.splitlines()

        for lineno, line in enumerate(lines, start=1):
            # Check plaintext password fields
            if _PLAINTEXT_PASSWORD_RE.search(line) and not _PASSWORD_SAFE_RE.search(content):
                issues.append(
                    f"GATE-08: {rel_path}:{lineno}: plaintext password field detected. "
                    f"Use passwordHash with bcrypt/argon2 — never store plaintext passwords."
                )

            # Check raw PII fields (SSN, credit card, etc.)
            if _PLAINTEXT_PII_SCHEMA_RE.search(line):
                issues.append(
                    f"GATE-08: {rel_path}:{lineno}: sensitive PII field stored as plaintext. "
                    f"Credit cards must use tokenization (Stripe); government IDs must be encrypted at rest."
                )

    return issues


def run_static_analysis_gate(project_dir: str, phase_id: str = "2b") -> GateResult:
    """Run static analysis gate checks on the generated project.

    Performs six checks:
    1. GATE-05: No 'use client' in layout.tsx or page.tsx
    2. GATE-06: No NEXT_PUBLIC_ secret-pattern environment variables exposed
    3. GATE-08: No plaintext password or PII fields in DB schemas
    4. BILD-06: error.tsx exists for route segments with async data fetching
    5. BILD-05: No hardcoded pixel widths that break responsive design
    6. FLOW-01: Form submission params match receiving page searchParams

    Args:
        project_dir: Absolute path to the generated Next.js project directory.
        phase_id: Pipeline phase identifier (default "2b").

    Returns:
        GateResult with passed=True only when no issues are found.
    """
    checked_at = _now_iso()
    base = Path(project_dir)

    issues: list[str] = []

    # Run all checks
    issues.extend(_check_use_client(base))
    issues.extend(_check_next_public_secrets(base))
    issues.extend(_check_plaintext_storage(base))
    issues.extend(_check_error_boundaries(base))
    issues.extend(_check_responsive_patterns(base))
    issues.extend(_check_form_page_params(base))

    passed = len(issues) == 0
    status = "PASS" if passed else "BLOCKED"
    severity = "INFO" if passed else "BLOCK"
    confidence = 1.0 if passed else 0.0

    return GateResult(
        gate_type="static_analysis",
        phase_id=phase_id,
        passed=passed,
        status=status,
        severity=severity,
        confidence=confidence,
        checked_at=checked_at,
        issues=issues,
    )
