"""Tests for web_app_factory._env_checker.

Covers ENVS-01, ENVS-02, ENVS-03:
- ENVS-01: check_env returns ToolStatus dicts per deploy target
- ENVS-02: Missing tools include platform-aware install commands; Vercel auth warning
- ENVS-03: install_tool uses allowlist and list-form subprocess args (no shell=True)
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from web_app_factory._env_checker import (
    check_env,
    format_env_report,
    install_tool,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node_result(passed: bool, version: str | None = "v22.0.0") -> dict[str, Any]:
    return {
        "check": "nodejs",
        "passed": passed,
        "reason": None if passed else f"Node.js {version} is too old",
        "version": version,
    }


def _make_npm_result(passed: bool, version: str | None = "10.0.0") -> dict[str, Any]:
    return {
        "check": "npm",
        "passed": passed,
        "reason": None if passed else "npm not found in PATH",
        "version": version if passed else None,
    }


def _make_python_result(passed: bool = True) -> dict[str, Any]:
    return {
        "check": "python",
        "passed": passed,
        "reason": None,
        "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }


def _make_vercel_result(passed: bool, version: str | None = "32.0.0") -> dict[str, Any]:
    return {
        "check": "vercel_cli",
        "passed": passed,
        "reason": None if passed else "Vercel CLI not found",
        "version": version if passed else None,
    }


# ---------------------------------------------------------------------------
# TestCheckEnv
# ---------------------------------------------------------------------------

class TestCheckEnv:
    def test_all_present(self):
        """check_env('vercel') returns ToolStatus dicts for node/npm/python/vercel, all present."""
        with (
            patch("web_app_factory._env_checker._check_nodejs", return_value=_make_node_result(True)),
            patch("web_app_factory._env_checker._check_npm", return_value=_make_npm_result(True)),
            patch("web_app_factory._env_checker._check_python_version", return_value=_make_python_result(True)),
            patch("web_app_factory._env_checker._check_vercel_cli", return_value=_make_vercel_result(True)),
            patch("os.environ.get", return_value="tok123"),
        ):
            statuses = check_env("vercel")

        tools = {s["tool"] for s in statuses}
        assert "node" in tools
        assert "npm" in tools
        assert "python" in tools
        assert "vercel" in tools

        for s in statuses:
            assert "tool" in s
            assert "status" in s
            assert "version_found" in s
            assert "version_required" in s
            assert "install_command" in s
            assert "note" in s

        node_s = next(s for s in statuses if s["tool"] == "node")
        assert node_s["status"] == "present"

    def test_node_missing(self):
        """When shutil.which('node') returns None, node entry has status='missing' with install_command."""
        node_missing = {
            "check": "nodejs",
            "passed": False,
            "reason": "Node.js not found in PATH",
            "version": None,
        }
        with (
            patch("web_app_factory._env_checker._check_nodejs", return_value=node_missing),
            patch("web_app_factory._env_checker._check_npm", return_value=_make_npm_result(True)),
            patch("web_app_factory._env_checker._check_python_version", return_value=_make_python_result()),
            patch("web_app_factory._env_checker._check_vercel_cli", return_value=_make_vercel_result(True)),
            patch("os.environ.get", return_value=None),
        ):
            statuses = check_env("vercel")

        node_s = next(s for s in statuses if s["tool"] == "node")
        assert node_s["status"] == "missing"
        assert node_s["install_command"] is not None
        assert len(node_s["install_command"]) > 0

    def test_node_outdated(self):
        """When node version is v16.0.0, node entry has status='outdated' with version details."""
        node_old = {
            "check": "nodejs",
            "passed": False,
            "reason": "Node.js v16.0.0 is too old — require >= 20.9",
            "version": "v16.0.0",
        }
        with (
            patch("web_app_factory._env_checker._check_nodejs", return_value=node_old),
            patch("web_app_factory._env_checker._check_npm", return_value=_make_npm_result(True)),
            patch("web_app_factory._env_checker._check_python_version", return_value=_make_python_result()),
            patch("web_app_factory._env_checker._check_vercel_cli", return_value=_make_vercel_result(True)),
            patch("os.environ.get", return_value=None),
        ):
            statuses = check_env("vercel")

        node_s = next(s for s in statuses if s["tool"] == "node")
        assert node_s["status"] == "outdated"
        assert node_s["version_found"] == "v16.0.0"
        assert node_s["version_required"] is not None
        assert "20" in node_s["version_required"]

    def test_gcloud_included_for_gcp(self):
        """check_env('gcp') returns an entry for gcloud."""
        with (
            patch("web_app_factory._env_checker._check_nodejs", return_value=_make_node_result(True)),
            patch("web_app_factory._env_checker._check_npm", return_value=_make_npm_result(True)),
            patch("web_app_factory._env_checker._check_python_version", return_value=_make_python_result()),
            patch("web_app_factory._env_checker._check_gcloud", return_value={
                "tool": "gcloud",
                "status": "present",
                "version_found": "420.0.0",
                "version_required": None,
                "install_command": None,
                "note": None,
            }),
        ):
            statuses = check_env("gcp")

        tools = {s["tool"] for s in statuses}
        assert "gcloud" in tools

    def test_gcloud_skipped_for_vercel(self):
        """check_env('vercel') does not include a gcloud entry."""
        with (
            patch("web_app_factory._env_checker._check_nodejs", return_value=_make_node_result(True)),
            patch("web_app_factory._env_checker._check_npm", return_value=_make_npm_result(True)),
            patch("web_app_factory._env_checker._check_python_version", return_value=_make_python_result()),
            patch("web_app_factory._env_checker._check_vercel_cli", return_value=_make_vercel_result(True)),
            patch("os.environ.get", return_value=None),
        ):
            statuses = check_env("vercel")

        tools = {s["tool"] for s in statuses}
        assert "gcloud" not in tools

    def test_local_deploy_target(self):
        """check_env('local') returns only node, npm, python — no vercel or gcloud."""
        with (
            patch("web_app_factory._env_checker._check_nodejs", return_value=_make_node_result(True)),
            patch("web_app_factory._env_checker._check_npm", return_value=_make_npm_result(True)),
            patch("web_app_factory._env_checker._check_python_version", return_value=_make_python_result()),
        ):
            statuses = check_env("local")

        tools = {s["tool"] for s in statuses}
        assert "node" in tools
        assert "npm" in tools
        assert "python" in tools
        assert "vercel" not in tools
        assert "gcloud" not in tools


# ---------------------------------------------------------------------------
# TestVercelAuthStatus
# ---------------------------------------------------------------------------

class TestVercelAuthStatus:
    def test_scope_warning_when_token_set(self):
        """When VERCEL_TOKEN env var is set, vercel status='present' with org-scoped note."""
        with (
            patch("web_app_factory._env_checker._check_nodejs", return_value=_make_node_result(True)),
            patch("web_app_factory._env_checker._check_npm", return_value=_make_npm_result(True)),
            patch("web_app_factory._env_checker._check_python_version", return_value=_make_python_result()),
            patch("web_app_factory._env_checker._check_vercel_cli", return_value=_make_vercel_result(True)),
            patch("os.environ.get", return_value="tok123"),
        ):
            statuses = check_env("vercel")

        vercel_s = next(s for s in statuses if s["tool"] == "vercel")
        assert vercel_s["status"] == "present"
        assert "org" in vercel_s["note"].lower() or "scoped" in vercel_s["note"].lower()

    def test_unauth_when_no_token(self):
        """When vercel CLI present but no VERCEL_TOKEN and keychain returns None, status='present_unauth'."""
        with (
            patch("web_app_factory._env_checker._check_nodejs", return_value=_make_node_result(True)),
            patch("web_app_factory._env_checker._check_npm", return_value=_make_npm_result(True)),
            patch("web_app_factory._env_checker._check_python_version", return_value=_make_python_result()),
            patch("web_app_factory._env_checker._check_vercel_cli", return_value=_make_vercel_result(True)),
            patch("web_app_factory._env_checker.os.environ.get", return_value=None),
            patch("web_app_factory._env_checker.get_credential", return_value=None),
        ):
            statuses = check_env("vercel")

        vercel_s = next(s for s in statuses if s["tool"] == "vercel")
        assert vercel_s["status"] == "present_unauth"
        assert "VERCEL_TOKEN" in vercel_s["note"]


# ---------------------------------------------------------------------------
# TestInstallCommands
# ---------------------------------------------------------------------------

class TestInstallCommands:
    def test_darwin_command(self):
        """On darwin platform, node install_command contains 'brew install node'."""
        node_missing = {
            "check": "nodejs",
            "passed": False,
            "reason": "Node.js not found in PATH",
            "version": None,
        }
        with (
            patch("web_app_factory._env_checker._check_nodejs", return_value=node_missing),
            patch("web_app_factory._env_checker._check_npm", return_value=_make_npm_result(True)),
            patch("web_app_factory._env_checker._check_python_version", return_value=_make_python_result()),
            patch("web_app_factory._env_checker._check_vercel_cli", return_value=_make_vercel_result(True)),
            patch("os.environ.get", return_value=None),
            patch("web_app_factory._env_checker.sys.platform", "darwin"),
        ):
            statuses = check_env("vercel")

        node_s = next(s for s in statuses if s["tool"] == "node")
        assert "brew" in node_s["install_command"].lower()
        assert "node" in node_s["install_command"].lower()

    def test_linux_command(self):
        """On linux platform, node install_command contains 'apt' or 'nodesource'."""
        node_missing = {
            "check": "nodejs",
            "passed": False,
            "reason": "Node.js not found in PATH",
            "version": None,
        }
        with (
            patch("web_app_factory._env_checker._check_nodejs", return_value=node_missing),
            patch("web_app_factory._env_checker._check_npm", return_value=_make_npm_result(True)),
            patch("web_app_factory._env_checker._check_python_version", return_value=_make_python_result()),
            patch("web_app_factory._env_checker._check_vercel_cli", return_value=_make_vercel_result(True)),
            patch("os.environ.get", return_value=None),
            patch("web_app_factory._env_checker.sys.platform", "linux"),
        ):
            statuses = check_env("vercel")

        node_s = next(s for s in statuses if s["tool"] == "node")
        cmd_lower = node_s["install_command"].lower()
        assert "apt" in cmd_lower or "nodesource" in cmd_lower or "nvm" in cmd_lower

    def test_npm_references_nodejs(self):
        """npm install_command mentions installing Node.js first."""
        npm_missing = {
            "check": "npm",
            "passed": False,
            "reason": "npm not found in PATH",
            "version": None,
        }
        with (
            patch("web_app_factory._env_checker._check_nodejs", return_value=_make_node_result(True)),
            patch("web_app_factory._env_checker._check_npm", return_value=npm_missing),
            patch("web_app_factory._env_checker._check_python_version", return_value=_make_python_result()),
            patch("web_app_factory._env_checker._check_vercel_cli", return_value=_make_vercel_result(True)),
            patch("os.environ.get", return_value=None),
        ):
            statuses = check_env("vercel")

        npm_s = next(s for s in statuses if s["tool"] == "npm")
        cmd_lower = npm_s["install_command"].lower()
        assert "node" in cmd_lower or "nodejs" in cmd_lower


# ---------------------------------------------------------------------------
# TestInstallTool
# ---------------------------------------------------------------------------

class TestInstallTool:
    def test_unknown_tool_rejected(self):
        """install_tool('evil_tool') returns error without calling subprocess."""
        with patch("subprocess.run") as mock_run:
            result = install_tool("evil_tool")
        mock_run.assert_not_called()
        assert "error" in result.lower() or "unknown" in result.lower() or "not allowed" in result.lower()

    def test_execute_installs(self):
        """install_tool('vercel') calls subprocess.run with ['npm', 'install', '-g', 'vercel']."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "added 1 package"
        mock_proc.stderr = ""
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            result = install_tool("vercel")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # First positional arg must be a list (not a string)
        cmd = call_args[0][0]
        assert isinstance(cmd, list)
        assert cmd == ["npm", "install", "-g", "vercel"]

    def test_no_shell_true(self):
        """install_tool never passes shell=True to subprocess.run."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "ok"
        mock_proc.stderr = ""
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            install_tool("vercel")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("shell") is not True

    def test_install_not_available_returns_manual(self):
        """install_tool('node') on linux (no single-command install) returns manual instruction."""
        with patch("web_app_factory._env_checker.sys.platform", "linux"):
            result = install_tool("node")
        # On linux, node has no simple single-command install via list args
        # Should return a manual install instruction, not try subprocess
        assert isinstance(result, str)
        assert len(result) > 0
        # Should mention nodesource or nvm or apt
        result_lower = result.lower()
        assert any(word in result_lower for word in ["node", "install", "https", "nvm", "apt", "nodesource"])


# ---------------------------------------------------------------------------
# TestFormatEnvReport
# ---------------------------------------------------------------------------

class TestFormatEnvReport:
    def _all_present_statuses(self) -> list[dict]:
        return [
            {
                "tool": "node",
                "status": "present",
                "version_found": "v22.0.0",
                "version_required": ">= 20.9",
                "install_command": None,
                "note": None,
            },
            {
                "tool": "npm",
                "status": "present",
                "version_found": "10.0.0",
                "version_required": None,
                "install_command": None,
                "note": None,
            },
            {
                "tool": "python",
                "status": "present",
                "version_found": "3.12.0",
                "version_required": ">= 3.10",
                "install_command": None,
                "note": None,
            },
            {
                "tool": "vercel",
                "status": "present",
                "version_found": "32.0.0",
                "version_required": None,
                "install_command": None,
                "note": None,
            },
        ]

    def test_produces_markdown_table(self):
        """format_env_report returns string with '| Tool | Status |' header."""
        report = format_env_report(self._all_present_statuses())
        assert "| Tool" in report or "| tool" in report.lower()
        assert "| Status" in report or "| status" in report.lower()

    def test_all_ok_message(self):
        """When all statuses are 'present', report contains 'Environment is ready'."""
        report = format_env_report(self._all_present_statuses())
        assert "ready" in report.lower() or "environment is ready" in report.lower()

    def test_missing_tool_message(self):
        """When any status is 'missing', report contains instruction to use waf_check_env with execute_install."""
        statuses = self._all_present_statuses()
        statuses[0] = {
            "tool": "node",
            "status": "missing",
            "version_found": None,
            "version_required": ">= 20.9",
            "install_command": "brew install node",
            "note": None,
        }
        report = format_env_report(statuses)
        assert "execute_install" in report or "waf_check_env" in report or "install" in report.lower()
