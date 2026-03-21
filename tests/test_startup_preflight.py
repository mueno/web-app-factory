"""Tests for pipeline_runtime/startup_preflight.py — web checks."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock


import pytest


def _make_which(found: dict[str, Optional[str]]):
    """Create a mock which() that returns tool paths from the dict."""
    def which(name: str) -> Optional[str]:
        return found.get(name, None)
    return which


def _make_run_subprocess(outputs: dict[str, tuple[int, str]]):
    """Create a mock run_subprocess that returns (returncode, stdout) for cmd[0]."""
    def run_subprocess(cmd, **kwargs):
        key = cmd[0] if isinstance(cmd, list) else cmd
        rc, stdout = outputs.get(key, (0, ""))
        result = MagicMock()
        result.returncode = rc
        result.stdout = stdout
        result.stderr = ""
        return result
    return run_subprocess


class TestCheckNodejs:
    def test_passes_with_valid_version(self):
        from pipeline_runtime.startup_preflight import _check_nodejs
        which = _make_which({"node": "/usr/local/bin/node"})
        run_sub = _make_run_subprocess({"/usr/local/bin/node": (0, "v20.11.0\n")})
        result = _check_nodejs(which, run_sub)
        assert result["passed"] is True
        assert result["check"] == "nodejs"

    def test_passes_with_minimum_version(self):
        from pipeline_runtime.startup_preflight import _check_nodejs
        which = _make_which({"node": "/usr/bin/node"})
        run_sub = _make_run_subprocess({"/usr/bin/node": (0, "v20.9.0\n")})
        result = _check_nodejs(which, run_sub)
        assert result["passed"] is True

    def test_fails_with_old_version(self):
        from pipeline_runtime.startup_preflight import _check_nodejs
        which = _make_which({"node": "/usr/local/bin/node"})
        run_sub = _make_run_subprocess({"/usr/local/bin/node": (0, "v18.0.0\n")})
        result = _check_nodejs(which, run_sub)
        assert result["passed"] is False
        assert "20.9" in result["reason"]

    def test_fails_when_not_found(self):
        from pipeline_runtime.startup_preflight import _check_nodejs
        which = _make_which({})  # node not in PATH
        run_sub = _make_run_subprocess({})
        result = _check_nodejs(which, run_sub)
        assert result["passed"] is False
        assert "not found" in result["reason"].lower()


class TestCheckNpm:
    def test_passes_when_present(self):
        from pipeline_runtime.startup_preflight import _check_npm
        which = _make_which({"npm": "/usr/local/bin/npm"})
        run_sub = _make_run_subprocess({"/usr/local/bin/npm": (0, "10.2.0\n")})
        result = _check_npm(which, run_sub)
        assert result["passed"] is True
        assert result["check"] == "npm"

    def test_fails_when_not_found(self):
        from pipeline_runtime.startup_preflight import _check_npm
        which = _make_which({})
        run_sub = _make_run_subprocess({})
        result = _check_npm(which, run_sub)
        assert result["passed"] is False


class TestCheckVercelCli:
    def test_passes_when_present(self):
        from pipeline_runtime.startup_preflight import _check_vercel_cli
        which = _make_which({"vercel": "/usr/local/bin/vercel"})
        run_sub = _make_run_subprocess({"/usr/local/bin/vercel": (0, "Vercel CLI 33.0.0\n")})
        result = _check_vercel_cli(which, run_sub)
        assert result["passed"] is True
        assert result["check"] == "vercel_cli"

    def test_fails_when_not_found(self):
        from pipeline_runtime.startup_preflight import _check_vercel_cli
        which = _make_which({})
        run_sub = _make_run_subprocess({})
        result = _check_vercel_cli(which, run_sub)
        assert result["passed"] is False


class TestCheckClaudeCli:
    def test_passes_when_claude_found_and_responds(self):
        from pipeline_runtime.startup_preflight import _check_claude_cli
        which = _make_which({"claude": "/usr/local/bin/claude"})
        run_sub = _make_run_subprocess({"/usr/local/bin/claude": (0, "claude 2.1.0\n")})
        result = _check_claude_cli(which, run_sub)
        assert result["passed"] is True
        assert result["check"] == "claude_cli"

    def test_fails_when_claude_not_found(self):
        from pipeline_runtime.startup_preflight import _check_claude_cli
        which = _make_which({})
        run_sub = _make_run_subprocess({})
        result = _check_claude_cli(which, run_sub)
        assert result["passed"] is False
        assert "not found" in result["reason"].lower()

    def test_fails_when_claude_returns_nonzero(self):
        from pipeline_runtime.startup_preflight import _check_claude_cli
        which = _make_which({"claude": "/usr/local/bin/claude"})
        run_sub = _make_run_subprocess({"/usr/local/bin/claude": (1, "")})
        result = _check_claude_cli(which, run_sub)
        assert result["passed"] is False
        assert "not responding" in result["reason"].lower() or "exited" in result["reason"].lower()

    def test_fails_when_claude_subprocess_raises(self):
        from pipeline_runtime.startup_preflight import _check_claude_cli

        which = _make_which({"claude": "/usr/local/bin/claude"})

        def raising_subprocess(cmd, **kwargs):
            raise OSError("Cannot execute")

        result = _check_claude_cli(which, raising_subprocess)
        assert result["passed"] is False
        assert "not responding" in result["reason"].lower() or "failed" in result["reason"].lower()


class TestRunStartupPreflight:
    def _all_ok_mocks(self):
        which = _make_which({
            "node": "/usr/local/bin/node",
            "npm": "/usr/local/bin/npm",
            "vercel": "/usr/local/bin/vercel",
            "claude": "/usr/local/bin/claude",
        })
        run_sub = _make_run_subprocess({
            "/usr/local/bin/node": (0, "v20.11.0\n"),
            "/usr/local/bin/npm": (0, "10.2.0\n"),
            "/usr/local/bin/vercel": (0, "Vercel CLI 33.0.0\n"),
            "/usr/local/bin/claude": (0, "claude 2.1.0\n"),
        })
        return which, run_sub

    def test_all_pass(self, tmp_path):
        from pipeline_runtime.startup_preflight import run_startup_preflight
        which, run_sub = self._all_ok_mocks()
        result = run_startup_preflight(
            project_dir=str(tmp_path),
            which=which,
            run_subprocess=run_sub,
        )
        assert result["passed"] is True
        assert result["issues"] == []

    def test_fails_when_node_missing(self, tmp_path):
        from pipeline_runtime.startup_preflight import run_startup_preflight
        which, run_sub = self._all_ok_mocks()
        # Overwrite which to exclude node
        which_no_node = _make_which({
            "npm": "/usr/local/bin/npm",
            "vercel": "/usr/local/bin/vercel",
            "claude": "/usr/local/bin/claude",
        })
        result = run_startup_preflight(
            project_dir=str(tmp_path),
            which=which_no_node,
            run_subprocess=run_sub,
        )
        assert result["passed"] is False
        assert len(result["issues"]) > 0

    def test_fails_when_claude_missing(self, tmp_path):
        from pipeline_runtime.startup_preflight import run_startup_preflight
        which_no_claude = _make_which({
            "node": "/usr/local/bin/node",
            "npm": "/usr/local/bin/npm",
            "vercel": "/usr/local/bin/vercel",
        })
        run_sub = _make_run_subprocess({
            "/usr/local/bin/node": (0, "v20.11.0\n"),
            "/usr/local/bin/npm": (0, "10.2.0\n"),
            "/usr/local/bin/vercel": (0, "Vercel CLI 33.0.0\n"),
        })
        result = run_startup_preflight(
            project_dir=str(tmp_path),
            which=which_no_claude,
            run_subprocess=run_sub,
        )
        assert result["passed"] is False

    def test_report_is_written(self, tmp_path):
        from pipeline_runtime.startup_preflight import run_startup_preflight
        which, run_sub = self._all_ok_mocks()
        result = run_startup_preflight(
            project_dir=str(tmp_path),
            which=which,
            run_subprocess=run_sub,
        )
        report_path = tmp_path / "docs" / "pipeline" / "startup-preflight.json"
        assert report_path.exists()
