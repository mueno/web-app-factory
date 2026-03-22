# SPDX-License-Identifier: MIT
"""CRITICAL integration test: MCP phase_reporter -> state.json bridge.

This test verifies that the MCP phase_reporter tool's project_dir bridge
actually updates state.json via pipeline_state functions.

This is the safety net against the HealthStockBoardV30 failure mode
(MEMORY.md: Dual Implementation Divergence) where the MCP server logged
locally but never updated state.json.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from tools.factory_mcp_server import phase_reporter
from tools.pipeline_state import init_run, load_state


class TestMCPBridgeUpdatesStateJson:
    """Verify phase_reporter MCP tool updates state.json via project_dir bridge."""

    def test_phase_reporter_start_sets_phase_running(self, tmp_path: Path) -> None:
        """After phase_reporter 'start', state.json shows phase as running."""
        # Setup: init pipeline run in a temp project dir
        state_obj = init_run("test-app", str(tmp_path), "A test app idea")
        run_id = state_obj.run_id

        # Call phase_reporter with start status — run_id AND project_dir activates bridge
        asyncio.run(
            phase_reporter(
                phase="1a",
                status="start",
                message="Starting idea validation",
                run_id=run_id,
                project_dir=str(tmp_path),
            )
        )

        # Assert: state.json shows phase 1a as running (pipeline_state uses "running")
        state = load_state(run_id, str(tmp_path))
        assert state is not None, "state.json not found or failed to load"
        assert "1a" in state.phases, "Phase 1a not found in state"
        assert state.phases["1a"]["status"] == "running", (
            f"Expected 'running', got: {state.phases['1a']['status']}"
        )

    def test_phase_reporter_complete_sets_phase_completed(self, tmp_path: Path) -> None:
        """After phase_reporter 'complete', state.json shows phase as completed."""
        # Setup: init pipeline run
        state_obj = init_run("test-app-2", str(tmp_path), "Another test app idea")
        run_id = state_obj.run_id

        # Start then complete the phase
        asyncio.run(
            phase_reporter(
                phase="1a",
                status="start",
                message="Starting idea validation",
                run_id=run_id,
                project_dir=str(tmp_path),
            )
        )
        asyncio.run(
            phase_reporter(
                phase="Phase 1a: Idea Validation",  # Test phase name normalization
                status="complete",
                message="Idea validation complete",
                run_id=run_id,
                project_dir=str(tmp_path),
                artifacts=["docs/pipeline/idea-validation.md"],
            )
        )

        # Assert: state.json shows phase 1a as completed
        state = load_state(run_id, str(tmp_path))
        assert state is not None, "state.json not found after complete"
        assert state.phases["1a"]["status"] == "completed", (
            f"Expected 'completed', got: {state.phases['1a']['status']}"
        )

    def test_phase_reporter_without_project_dir_does_not_crash(self) -> None:
        """When project_dir is empty, phase_reporter logs normally without error."""
        # No project_dir — should not crash, just skip the bridge
        result = asyncio.run(
            phase_reporter(
                phase="1a",
                status="info",
                message="Info log entry",
                run_id="test-no-dir-run",
                project_dir="",  # No bridge activated
            )
        )
        assert result is not None  # Should return a string

    def test_phase_reporter_without_run_id_does_not_crash(self) -> None:
        """When run_id is empty, phase_reporter writes to global log without error."""
        # No run_id — should not crash
        result = asyncio.run(
            phase_reporter(
                phase="1a",
                status="info",
                message="Info log entry",
                run_id="",
                project_dir="",
            )
        )
        assert result is not None

    def test_phase_reporter_normalizes_verbose_phase_names(self, tmp_path: Path) -> None:
        """Phase names like 'Phase 1a: Idea Validation' are normalized to '1a'."""
        state_obj = init_run("test-app-4", str(tmp_path), "Normalization test idea")
        run_id = state_obj.run_id

        asyncio.run(
            phase_reporter(
                phase="Phase 1a: Idea Validation",
                status="start",
                message="Starting",
                run_id=run_id,
                project_dir=str(tmp_path),
            )
        )

        state = load_state(run_id, str(tmp_path))
        assert state is not None
        assert "1a" in state.phases, (
            "Phase '1a' not found — normalization from 'Phase 1a: ...' may have failed"
        )
        assert state.phases["1a"]["status"] == "running", (
            f"Expected 'running' after normalized start, got: {state.phases['1a']['status']}"
        )
