"""Startup preflight checks for web-app-factory.

Validates the environment (Node.js, npm, Vercel CLI, Claude CLI) before
pipeline execution. All checks use dependency injection for testability.

Lock file name: .web-factory-run.lock (prevents concurrent pipeline runs).
"""

from __future__ import annotations

import json
import os
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - non-posix platforms
    fcntl = None  # type: ignore[assignment]


STARTUP_PREFLIGHT_PATH = Path("docs/pipeline/startup-preflight.json")
PIPELINE_SINGLE_FLIGHT_LOCK_PATH = Path("docs/pipeline/.web-factory-run.lock")

# Minimum required Node.js version
_NODE_MIN_MAJOR = 20
_NODE_MIN_MINOR = 9


def _parse_node_version(version_str: str) -> tuple[int, int, int]:
    """Parse 'v20.9.0' -> (20, 9, 0). Returns (0, 0, 0) on parse error."""
    clean = version_str.strip().lstrip("v")
    parts = clean.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return major, minor, patch
    except (ValueError, IndexError):
        return 0, 0, 0


def _check_nodejs(
    which: Callable[[str], Optional[str]],
    run_subprocess: Callable[..., Any],
) -> dict[str, Any]:
    """Check that Node.js >= 20.9.0 is available."""
    result: dict[str, Any] = {
        "check": "nodejs",
        "passed": False,
        "reason": None,
        "version": None,
    }
    node_path = which("node")
    if node_path is None:
        result["reason"] = "Node.js not found in PATH — install Node.js >= 20.9"
        return result

    try:
        proc = run_subprocess(
            [node_path, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["reason"] = f"node --version failed: {exc}"
        return result

    raw_version = (proc.stdout or "").strip()
    result["version"] = raw_version
    major, minor, patch = _parse_node_version(raw_version)

    if (major, minor) < (_NODE_MIN_MAJOR, _NODE_MIN_MINOR):
        result["reason"] = (
            f"Node.js {raw_version} is too old — require >= 20.9. "
            "Install a newer version."
        )
        return result

    result["passed"] = True
    return result


def _check_npm(
    which: Callable[[str], Optional[str]],
    run_subprocess: Callable[..., Any],
) -> dict[str, Any]:
    """Check that npm is available."""
    result: dict[str, Any] = {
        "check": "npm",
        "passed": False,
        "reason": None,
        "version": None,
    }
    npm_path = which("npm")
    if npm_path is None:
        result["reason"] = "npm not found in PATH — install Node.js (includes npm)"
        return result

    try:
        proc = run_subprocess(
            [npm_path, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["reason"] = f"npm --version failed: {exc}"
        return result

    result["version"] = (proc.stdout or "").strip()
    result["passed"] = True
    return result


def _check_vercel_cli(
    which: Callable[[str], Optional[str]],
    run_subprocess: Callable[..., Any],
) -> dict[str, Any]:
    """Check that the Vercel CLI is available."""
    result: dict[str, Any] = {
        "check": "vercel_cli",
        "passed": False,
        "reason": None,
        "version": None,
    }
    vercel_path = which("vercel")
    if vercel_path is None:
        result["reason"] = "Vercel CLI not found — run: npm install -g vercel"
        return result

    try:
        proc = run_subprocess(
            [vercel_path, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["reason"] = f"vercel --version failed: {exc}"
        return result

    result["version"] = (proc.stdout or "").strip()
    result["passed"] = True
    return result


def _check_python_version() -> dict[str, Any]:
    """Check that Python >= 3.10 is available (checked at import time)."""
    import sys
    result: dict[str, Any] = {
        "check": "python",
        "passed": False,
        "reason": None,
        "version": None,
    }
    version_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    result["version"] = version_str
    if sys.version_info < (3, 10):
        result["reason"] = f"Python {version_str} is too old — require >= 3.10"
        return result
    result["passed"] = True
    return result


def _check_claude_cli(
    which: Callable[[str], Optional[str]],
    run_subprocess: Callable[..., Any],
) -> dict[str, Any]:
    """Check that Claude CLI is reachable.

    Per CONTEXT.md locked decision: Claude CLI is a mandatory preflight check.
    Uses `claude --version` (not `claude -p`) because `claude -p` hangs via
    subprocess (known bug: github.com/anthropics/claude-code/issues/24481).
    """
    result: dict[str, Any] = {
        "check": "claude_cli",
        "passed": False,
        "reason": None,
        "version": None,
    }
    claude_path = which("claude")
    if claude_path is None:
        result["reason"] = "Claude CLI not found — required for LLM orchestration. Run: npm install -g @anthropic-ai/claude-code"
        return result

    try:
        proc = run_subprocess(
            [claude_path, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["reason"] = f"Claude CLI found but not responding: {exc}"
        return result

    if proc.returncode != 0:
        result["reason"] = (
            f"Claude CLI found but not responding — "
            f"claude --version exited with code {proc.returncode}"
        )
        return result

    result["version"] = (proc.stdout or "").strip()
    result["passed"] = True
    return result


def write_startup_preflight_report(project_dir: str, payload: dict[str, Any]) -> Path:
    """Write startup preflight result to docs/pipeline/startup-preflight.json."""
    report_path = Path(project_dir).resolve() / STARTUP_PREFLIGHT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path


def acquire_pipeline_singleflight_lock(
    project_dir: str,
    *,
    lock_relative_path: Path = PIPELINE_SINGLE_FLIGHT_LOCK_PATH,
    fcntl_module: Any = fcntl,
) -> tuple[Any | None, Path, str]:
    """Acquire an exclusive lock to prevent concurrent pipeline runs."""
    lock_path = Path(project_dir).resolve() / lock_relative_path
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if fcntl_module is None:
        return None, lock_path, ""

    handle = None
    try:
        handle = lock_path.open("w", encoding="utf-8")
        fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_EX | fcntl_module.LOCK_NB)
        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "locked_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
            )
        )
        handle.flush()
        return handle, lock_path, ""
    except BlockingIOError:
        if handle is not None:
            handle.close()
        return None, lock_path, f"single-flight lock busy: {lock_path}"
    except OSError as exc:
        if handle is not None:
            handle.close()
        return None, lock_path, f"failed to acquire single-flight lock: {exc}"


def release_pipeline_singleflight_lock(handle: Any, *, fcntl_module: Any = fcntl) -> None:
    """Release the singleflight lock."""
    if handle is None:
        return
    if fcntl_module is not None:
        try:
            fcntl_module.flock(handle.fileno(), fcntl_module.LOCK_UN)
        except OSError:
            pass
    try:
        handle.close()
    except OSError:
        pass


def run_startup_preflight(
    *,
    project_dir: str,
    which: Callable[[str], Optional[str]] = shutil.which,
    run_subprocess: Callable[..., Any] = subprocess.run,
    write_report: Callable[[str, dict[str, Any]], Path] = write_startup_preflight_report,
) -> dict[str, Any]:
    """Run all preflight checks and return aggregated result.

    Returns a dict with:
        passed (bool): True only when all checks pass.
        issues (list[str]): Failure reason strings for each failing check.
        checks (list[dict]): Full per-check results.
        report_path (str): Path to the written JSON report.
    """
    checks = [
        _check_nodejs(which, run_subprocess),
        _check_npm(which, run_subprocess),
        _check_vercel_cli(which, run_subprocess),
        _check_python_version(),
        _check_claude_cli(which, run_subprocess),
    ]

    passed = all(bool(c.get("passed")) for c in checks)
    issues = [
        str(c.get("reason") or "").strip()
        for c in checks
        if not c.get("passed")
    ]
    issues = [i for i in issues if i]

    payload = {
        "gate": "startup_preflight",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_dir": str(Path(project_dir).resolve()),
        "status": "PASS" if passed else "BLOCKED",
        "checks": checks,
        "issues": issues,
    }
    report_path = write_report(project_dir, payload)

    return {
        "passed": passed,
        "issues": issues,
        "checks": checks,
        "report_path": str(report_path),
    }
