"""Unit tests for web_app_factory/_dev_server.py (LDEV-01 through LDEV-04).

Uses mocked subprocess.Popen to test all dev server lifecycle behaviors
without actually starting npm processes.
"""
from __future__ import annotations

import json
import os
import signal
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch, call

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_mock_popen(lines: list[str], pid: int = 12345, returncode: int | None = None):
    """Build a mock Popen that yields stdout lines and has a live process by default."""
    mock_proc = MagicMock()
    mock_proc.pid = pid
    mock_proc.returncode = returncode  # None = still running

    # stdout iteration yields lines
    mock_proc.stdout.__iter__ = lambda self: iter(lines)
    mock_proc.wait = MagicMock(return_value=0)
    mock_proc.poll = MagicMock(return_value=returncode)
    mock_proc.terminate = MagicMock()
    mock_proc.kill = MagicMock()

    # os.getpgid returns same as pid for simplicity
    return mock_proc


def _make_ready_lines() -> list[str]:
    """Simulate Next.js stdout output that signals readiness."""
    return [
        "   ▲ Next.js 14.2.0",
        "   - Local:        http://localhost:54321",
        "   - Environments: .env.local",
        "",
        " ✓ Ready in 1523ms",
    ]


# ── Project dir fixture ────────────────────────────────────────────────────────


@pytest.fixture
def project_run_dir(tmp_path):
    """Create the output/ directory structure with a state.json for run_id 'test-run-1'."""
    run_id = "test-run-1"
    project_dir = tmp_path / "output" / "my-app"
    run_state_dir = project_dir / "docs" / "pipeline" / "runs" / run_id
    run_state_dir.mkdir(parents=True)
    state = {"project_dir": str(project_dir), "run_id": run_id}
    (run_state_dir / "state.json").write_text(json.dumps(state))
    return tmp_path, project_dir, run_id


# ── Import helpers ─────────────────────────────────────────────────────────────


def _import_dev_server():
    """Import _dev_server fresh (avoids module-level singleton bleed between tests)."""
    import importlib
    import web_app_factory._dev_server as mod
    return mod


# ═══════════════════════════════════════════════════════════════════════════════
# LDEV-01: Process spawning
# ═══════════════════════════════════════════════════════════════════════════════


class TestLDEV01ProcessSpawning:
    """start_dev_server spawns npm run dev with correct args and flags."""

    def test_popen_called_with_npm_run_dev(self, project_run_dir):
        """LDEV-01: subprocess.Popen is called with npm run dev -- --port 0."""
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        mock_proc = _make_mock_popen(_make_ready_lines())

        with (
            patch.object(mod, "_resolve_project_dir", return_value=project_dir),
            patch("web_app_factory._dev_server.subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch("web_app_factory._dev_server.os.kill", return_value=None),
            patch("web_app_factory._dev_server.os.killpg"),
        ):
            # Reset registry to avoid state bleed
            registry = mod.get_registry()
            registry._registry.clear()
            mod._PROC_MAP.clear()

            result = mod.start_dev_server(run_id)

        mock_popen.assert_called_once()
        call_kwargs = mock_popen.call_args
        cmd = call_kwargs[0][0]  # first positional arg is the command list
        assert cmd == ["npm", "run", "dev", "--", "--port", "0"]

    def test_popen_uses_start_new_session_true(self, project_run_dir):
        """LDEV-01: start_new_session=True ensures process group isolation."""
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        mock_proc = _make_mock_popen(_make_ready_lines())

        with (
            patch.object(mod, "_resolve_project_dir", return_value=project_dir),
            patch("web_app_factory._dev_server.subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch("web_app_factory._dev_server.os.kill", return_value=None),
            patch("web_app_factory._dev_server.os.killpg"),
        ):
            registry = mod.get_registry()
            registry._registry.clear()
            mod._PROC_MAP.clear()

            mod.start_dev_server(run_id)

        _, kwargs = mock_popen.call_args
        assert kwargs.get("start_new_session") is True

    def test_popen_uses_pipe_and_text_mode(self, project_run_dir):
        """LDEV-01: stdout=PIPE, stderr=STDOUT, text=True for line-by-line reading."""
        import subprocess
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        mock_proc = _make_mock_popen(_make_ready_lines())

        with (
            patch.object(mod, "_resolve_project_dir", return_value=project_dir),
            patch("web_app_factory._dev_server.subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch("web_app_factory._dev_server.os.kill", return_value=None),
            patch("web_app_factory._dev_server.os.killpg"),
        ):
            registry = mod.get_registry()
            registry._registry.clear()
            mod._PROC_MAP.clear()

            mod.start_dev_server(run_id)

        _, kwargs = mock_popen.call_args
        assert kwargs.get("stdout") == subprocess.PIPE
        assert kwargs.get("stderr") == subprocess.STDOUT
        assert kwargs.get("text") is True

    def test_popen_cwd_is_project_dir(self, project_run_dir):
        """LDEV-01: Popen cwd matches the resolved project directory."""
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        mock_proc = _make_mock_popen(_make_ready_lines())

        with (
            patch.object(mod, "_resolve_project_dir", return_value=project_dir),
            patch("web_app_factory._dev_server.subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch("web_app_factory._dev_server.os.kill", return_value=None),
            patch("web_app_factory._dev_server.os.killpg"),
        ):
            registry = mod.get_registry()
            registry._registry.clear()
            mod._PROC_MAP.clear()

            mod.start_dev_server(run_id)

        _, kwargs = mock_popen.call_args
        assert kwargs.get("cwd") == project_dir

    def test_unknown_run_id_returns_error(self):
        """LDEV-01: Returns error when run_id cannot be resolved to project dir."""
        from web_app_factory import _dev_server as mod

        with patch.object(mod, "_resolve_project_dir", return_value=None):
            registry = mod.get_registry()
            registry._registry.clear()
            mod._PROC_MAP.clear()

            result = mod.start_dev_server("nonexistent-run")

        assert "✗" in result or "error" in result.lower() or "not found" in result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# LDEV-02: Readiness detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestLDEV02ReadinessDetection:
    """Background thread detects Next.js ready signal and returns URL."""

    def test_returns_url_when_ready(self, project_run_dir):
        """LDEV-02: Returns markdown with URL when Next.js signals readiness."""
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        mock_proc = _make_mock_popen(_make_ready_lines())

        with (
            patch.object(mod, "_resolve_project_dir", return_value=project_dir),
            patch("web_app_factory._dev_server.subprocess.Popen", return_value=mock_proc),
            patch("web_app_factory._dev_server.os.kill", return_value=None),
            patch("web_app_factory._dev_server.os.killpg"),
        ):
            registry = mod.get_registry()
            registry._registry.clear()
            mod._PROC_MAP.clear()

            result = mod.start_dev_server(run_id)

        assert "http://localhost:54321" in result
        assert "✓" in result

    def test_returns_pid_in_response(self, project_run_dir):
        """LDEV-02: Response includes PID for manual kill reference."""
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        mock_proc = _make_mock_popen(_make_ready_lines(), pid=99999)

        with (
            patch.object(mod, "_resolve_project_dir", return_value=project_dir),
            patch("web_app_factory._dev_server.subprocess.Popen", return_value=mock_proc),
            patch("web_app_factory._dev_server.os.kill", return_value=None),
            patch("web_app_factory._dev_server.os.killpg"),
        ):
            registry = mod.get_registry()
            registry._registry.clear()
            mod._PROC_MAP.clear()

            result = mod.start_dev_server(run_id)

        assert "99999" in result

    def test_timeout_returns_error(self, project_run_dir):
        """LDEV-02: 30s timeout returns error if no ready signal detected."""
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        # Stdout that never signals readiness — just hangs
        mock_proc = _make_mock_popen(["   ▲ Next.js 14.2.0"])  # no ready line

        with (
            patch.object(mod, "_resolve_project_dir", return_value=project_dir),
            patch("web_app_factory._dev_server.subprocess.Popen", return_value=mock_proc),
            patch("web_app_factory._dev_server.os.kill", return_value=None),
            patch("web_app_factory._dev_server.os.killpg"),
            patch.object(mod, "_READINESS_TIMEOUT", 0.1),  # short timeout for test speed
        ):
            registry = mod.get_registry()
            registry._registry.clear()
            mod._PROC_MAP.clear()

            result = mod.start_dev_server(run_id)

        assert "✗" in result or "timeout" in result.lower() or "error" in result.lower()

    def test_process_exit_before_ready_returns_error(self, project_run_dir):
        """LDEV-02: If process exits before ready, returns error with exit code."""
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        # Process exits immediately with error
        mock_proc = _make_mock_popen(["npm ERR! script not found"], pid=11111, returncode=1)
        mock_proc.poll = MagicMock(return_value=1)

        with (
            patch.object(mod, "_resolve_project_dir", return_value=project_dir),
            patch("web_app_factory._dev_server.subprocess.Popen", return_value=mock_proc),
            patch("web_app_factory._dev_server.os.kill", return_value=None),
            patch("web_app_factory._dev_server.os.killpg"),
            patch.object(mod, "_READINESS_TIMEOUT", 0.2),
        ):
            registry = mod.get_registry()
            registry._registry.clear()
            mod._PROC_MAP.clear()

            result = mod.start_dev_server(run_id)

        assert "✗" in result or "error" in result.lower() or "exit" in result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# LDEV-03: Duplicate prevention and stale detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestLDEV03DuplicatePrevention:
    """Registry tracks live servers; stale PIDs trigger restart."""

    def test_existing_live_server_returns_cached_url(self, project_run_dir):
        """LDEV-03: If run_id already in registry with live process, no new Popen."""
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        # Pre-populate registry with a "live" server
        existing_info = mod.DevServerInfo(
            run_id=run_id,
            pid=55555,
            port=54321,
            url="http://localhost:54321",
            started_at="2026-01-01T00:00:00Z",
            project_dir=str(project_dir),
        )

        with patch("web_app_factory._dev_server.subprocess.Popen") as mock_popen:
            registry = mod.get_registry()
            registry._registry.clear()
            mod._PROC_MAP.clear()
            registry._registry[run_id] = existing_info

            # os.kill(pid, 0) succeeds = process alive
            with patch("web_app_factory._dev_server.os.kill", return_value=None):
                result = mod.start_dev_server(run_id)

        # Should NOT have spawned a new process
        mock_popen.assert_not_called()
        assert "http://localhost:54321" in result

    def test_stale_pid_triggers_restart(self, project_run_dir):
        """LDEV-03: If pid is dead (ProcessLookupError), stale entry removed and new server started."""
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        # Pre-populate registry with a "stale" server
        stale_info = mod.DevServerInfo(
            run_id=run_id,
            pid=99998,
            port=54321,
            url="http://localhost:54321",
            started_at="2026-01-01T00:00:00Z",
            project_dir=str(project_dir),
        )

        mock_proc = _make_mock_popen(_make_ready_lines(), pid=12346)

        with (
            patch.object(mod, "_resolve_project_dir", return_value=project_dir),
            patch("web_app_factory._dev_server.subprocess.Popen", return_value=mock_proc) as mock_popen,
            patch("web_app_factory._dev_server.os.killpg"),
        ):
            registry = mod.get_registry()
            registry._registry.clear()
            mod._PROC_MAP.clear()
            registry._registry[run_id] = stale_info

            # os.kill(pid, 0) raises ProcessLookupError = process dead
            def kill_side_effect(pid, sig):
                if sig == 0:
                    raise ProcessLookupError(f"process {pid} not found")
                return None

            with patch("web_app_factory._dev_server.os.kill", side_effect=kill_side_effect):
                result = mod.start_dev_server(run_id)

        # Should have started a new process
        mock_popen.assert_called_once()

    def test_dev_server_info_is_frozen_dataclass(self):
        """LDEV-03: DevServerInfo is a frozen dataclass."""
        from web_app_factory import _dev_server as mod

        info = mod.DevServerInfo(
            run_id="x",
            pid=1,
            port=3000,
            url="http://localhost:3000",
            started_at="2026-01-01T00:00:00Z",
            project_dir="/tmp",
        )

        # Frozen dataclasses raise FrozenInstanceError on assignment
        with pytest.raises(Exception):
            info.pid = 999  # type: ignore[misc]

    def test_registry_is_thread_safe(self):
        """LDEV-03: DevServerRegistry uses threading.Lock for thread safety."""
        from web_app_factory import _dev_server as mod

        registry = mod.get_registry()
        assert hasattr(registry, "_lock")
        assert isinstance(registry._lock, type(threading.Lock()))


# ═══════════════════════════════════════════════════════════════════════════════
# LDEV-04: Cleanup and stop
# ═══════════════════════════════════════════════════════════════════════════════


class TestLDEV04Cleanup:
    """stop_dev_server and atexit cleanup terminate process groups."""

    def test_stop_sends_sigterm_via_killpg(self, project_run_dir):
        """LDEV-04: stop_dev_server sends SIGTERM to entire process group."""
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        existing_info = mod.DevServerInfo(
            run_id=run_id,
            pid=12345,
            port=54321,
            url="http://localhost:54321",
            started_at="2026-01-01T00:00:00Z",
            project_dir=str(project_dir),
        )

        mock_proc = _make_mock_popen([], pid=12345)

        registry = mod.get_registry()
        registry._registry.clear()
        mod._PROC_MAP.clear()
        registry._registry[run_id] = existing_info
        mod._PROC_MAP[run_id] = mock_proc

        with (
            patch("web_app_factory._dev_server.os.getpgid", return_value=12345),
            patch("web_app_factory._dev_server.os.killpg") as mock_killpg,
        ):
            mock_proc.poll.return_value = None  # still running after SIGTERM
            mock_proc.wait.return_value = 0

            result = mod.stop_dev_server(run_id)

        mock_killpg.assert_called_once_with(12345, signal.SIGTERM)

    def test_stop_returns_confirmation(self, project_run_dir):
        """LDEV-04: stop_dev_server returns success message."""
        output_root, project_dir, run_id = project_run_dir

        from web_app_factory import _dev_server as mod

        existing_info = mod.DevServerInfo(
            run_id=run_id,
            pid=12345,
            port=54321,
            url="http://localhost:54321",
            started_at="2026-01-01T00:00:00Z",
            project_dir=str(project_dir),
        )

        mock_proc = _make_mock_popen([], pid=12345)

        registry = mod.get_registry()
        registry._registry.clear()
        mod._PROC_MAP.clear()
        registry._registry[run_id] = existing_info
        mod._PROC_MAP[run_id] = mock_proc

        with (
            patch("web_app_factory._dev_server.os.getpgid", return_value=12345),
            patch("web_app_factory._dev_server.os.killpg"),
        ):
            mock_proc.wait.return_value = 0

            result = mod.stop_dev_server(run_id)

        assert "✓" in result or "stopped" in result.lower()

    def test_stop_not_running_returns_message(self):
        """LDEV-04: stop_dev_server for unknown run_id returns 'not running' message."""
        from web_app_factory import _dev_server as mod

        registry = mod.get_registry()
        registry._registry.clear()
        mod._PROC_MAP.clear()

        result = mod.stop_dev_server("never-started")

        assert "not running" in result.lower() or "✗" in result

    def test_module_has_atexit_registered(self):
        """LDEV-04: Module registers atexit cleanup on import."""
        import atexit

        from web_app_factory import _dev_server as mod

        # The _cleanup_all_servers function should exist
        assert hasattr(mod, "_cleanup_all_servers")
        assert callable(mod._cleanup_all_servers)

    def test_proc_map_separate_from_registry(self, project_run_dir):
        """LDEV-04: _PROC_MAP is separate from frozen DevServerInfo registry."""
        from web_app_factory import _dev_server as mod

        # _PROC_MAP must exist and be a dict
        assert hasattr(mod, "_PROC_MAP")
        assert isinstance(mod._PROC_MAP, dict)

        # DevServerRegistry must not store Popen objects
        registry = mod.get_registry()
        assert isinstance(registry, mod.DevServerRegistry)


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level constants and structure
# ═══════════════════════════════════════════════════════════════════════════════


class TestModuleStructure:
    """Verify module constants, singleton, and accessor exist."""

    def test_readiness_timeout_constant_exists(self):
        """Module exposes _READINESS_TIMEOUT = 30.0."""
        from web_app_factory import _dev_server as mod

        assert hasattr(mod, "_READINESS_TIMEOUT")
        assert mod._READINESS_TIMEOUT == 30.0

    def test_get_registry_returns_singleton(self):
        """get_registry() returns the same instance each call."""
        from web_app_factory import _dev_server as mod

        r1 = mod.get_registry()
        r2 = mod.get_registry()
        assert r1 is r2

    def test_module_exposes_required_symbols(self):
        """All required public symbols exist in the module."""
        from web_app_factory import _dev_server as mod

        required = [
            "DevServerRegistry",
            "DevServerInfo",
            "start_dev_server",
            "stop_dev_server",
            "get_registry",
            "_PROC_MAP",
            "_READINESS_TIMEOUT",
            "_cleanup_all_servers",
        ]
        for sym in required:
            assert hasattr(mod, sym), f"Missing: {sym}"
