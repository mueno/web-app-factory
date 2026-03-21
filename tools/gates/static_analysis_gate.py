"""Static analysis gate executor.

Performs regex-based file scanning for:
- GATE-05: 'use client' misplacement in layout.tsx and page.tsx
- GATE-06: NEXT_PUBLIC_ secret-pattern environment variable exposure

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


def _should_skip(path: Path, project_dir: Path) -> bool:
    """Return True if the path should be skipped during scanning."""
    # Skip node_modules anywhere in the path
    parts = path.parts
    if "node_modules" in parts:
        return True
    return False


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
            if _should_skip(filepath, project_dir):
                continue
            # Check extension — also match .env and .env.local by name
            name = filepath.name
            suffix = filepath.suffix
            if suffix in _SECRET_SCAN_EXTENSIONS or name in (".env", ".env.local"):
                _scan_file(filepath)

    return issues


def run_static_analysis_gate(project_dir: str, phase_id: str = "2b") -> GateResult:
    """Run static analysis gate checks on the generated project.

    Performs two checks:
    1. GATE-05: No 'use client' in layout.tsx or page.tsx
    2. GATE-06: No NEXT_PUBLIC_ secret-pattern environment variables exposed

    Args:
        project_dir: Absolute path to the generated Next.js project directory.
        phase_id: Pipeline phase identifier (default "2b").

    Returns:
        GateResult with passed=True only when no issues are found.
    """
    checked_at = _now_iso()
    base = Path(project_dir)

    issues: list[str] = []

    # Run both checks
    issues.extend(_check_use_client(base))
    issues.extend(_check_next_public_secrets(base))

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
