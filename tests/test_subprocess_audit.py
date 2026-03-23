"""Static audit: no shell=True in production code (MCPI-04).

This test scans all Python files under web_app_factory/ and tools/ for
shell=True usage in subprocess calls and os.system() calls, which are
vulnerable to shell injection attacks.

Any production code added with shell=True will fail CI.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path


# ── Paths to scan ─────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
_SCAN_DIRS = [
    _PROJECT_ROOT / "web_app_factory",
    _PROJECT_ROOT / "tools",
]

# ── Regex patterns for dangerous subprocess usage ─────────────────────────────
# Matches subprocess.run(... shell=True ...) or subprocess.Popen(... shell=True ...)
_SHELL_TRUE_PATTERN = re.compile(
    r"subprocess\s*\.\s*(?:run|Popen|call|check_call|check_output)\s*\(",
)
_SHELL_TRUE_KEYWORD = re.compile(r"\bshell\s*=\s*True\b")
_OS_SYSTEM_PATTERN = re.compile(r"\bos\s*\.\s*system\s*\(")


def _is_comment_line(line: str) -> bool:
    """Return True if the line is a comment (after stripping whitespace)."""
    stripped = line.strip()
    return stripped.startswith("#")


def _collect_violations() -> list[str]:
    """Scan production Python files for dangerous subprocess usage.

    Returns:
        List of "file:line: snippet" strings for each violation found.
    """
    violations: list[str] = []

    for scan_dir in _SCAN_DIRS:
        if not scan_dir.exists():
            continue

        for py_file in sorted(scan_dir.rglob("*.py")):
            # Skip test files
            if py_file.name.startswith("test_") or "test" in py_file.parent.name:
                continue
            # Skip __pycache__
            if "__pycache__" in str(py_file):
                continue

            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()

            for lineno, line in enumerate(lines, start=1):
                # Skip comment lines
                if _is_comment_line(line):
                    continue

                # Check for shell=True in subprocess calls
                # We match the keyword on the same line for simplicity;
                # multi-line calls would require AST — but shell=True is
                # virtually always on the same line as the function call.
                if _SHELL_TRUE_KEYWORD.search(line) and _SHELL_TRUE_PATTERN.search(line):
                    violations.append(
                        f"{py_file.relative_to(_PROJECT_ROOT)}:{lineno}: {line.strip()}"
                    )

                # Check for os.system() — inherently shell-injection-prone
                if _OS_SYSTEM_PATTERN.search(line):
                    violations.append(
                        f"{py_file.relative_to(_PROJECT_ROOT)}:{lineno}: {line.strip()}"
                    )

    return violations


def test_no_shell_true_in_production_code():
    """Production code must not use subprocess with shell=True or os.system()."""
    violations = _collect_violations()

    if violations:
        violation_list = "\n".join(f"  - {v}" for v in violations)
        raise AssertionError(
            f"Found {len(violations)} shell injection risk(s) in production code:\n"
            f"{violation_list}\n\n"
            "Fix: Replace shell=True with list arguments.\n"
            "  Bad:  subprocess.run('cmd arg', shell=True)\n"
            "  Good: subprocess.run(['cmd', 'arg'])\n"
            "Replace os.system() with subprocess.run()."
        )
