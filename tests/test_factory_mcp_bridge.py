# Copyright 2026 AllNew LLC. All rights reserved.
"""CRITICAL integration test: MCP phase_reporter -> state.json bridge.

This test verifies that the MCP phase_reporter tool's project_dir bridge
actually updates state.json via pipeline_state functions.

This is the safety net against the HealthStockBoardV30 failure mode
(MEMORY.md: Dual Implementation Divergence) where the MCP server logged
locally but never updated state.json.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tools.factory_mcp_server import phase_reporter
from tools.pipeline_state import init_run, load_state


class TestMCPBridgeUpdatessStateJson:
    """Verify phase_reporter MCP tool updates state.json via project_dir bridge."""

    def test_phase_reporter_start_sets_phase_in_progress(self, tmp_path: Path) -> None:
        """After phase_reporter 'start', state.json shows phase as in_progress."""
        run_id = "test-bridge-001"

        # Setup: init pipeline run in a temp project dir
        init_run(run_id, str(tmp_path))

        # Import asyncio to call the async function
        import asyncio

        # Call phase_reporter with start action — using run_id AND project_dir activates bridge
        asyncio.run(
            phase_reporter(
                phase="1a",
                status="start",
                message="Starting idea validation",
                run_id=run_id,
                project_dir=str(tmp_path),
            )
        )

        # Assert: state.json shows phase 1a as in_progress
        state = load_state(run_id, str(tmp_path))
        assert "1a" in state["phases"], "Phase 1a not found in state"
        assert state["phases"]["1a"]["status"] == "in_progress", (
            f"Expected 'in_progress', got: {state['phases']['1a']['status']}"
        )

    def test_phase_reporter_complete_sets_phase_completed(self, tmp_path: Path) -> None:
        """After phase_reporter 'complete', state.json shows phase as completed."""
        run_id = "test-bridge-002"
        import asyncio

        # Setup: init pipeline run
        init_run(run_id, str(tmp_path))

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
        assert state["phases"]["1a"]["status"] == "completed", (
            f"Expected 'completed', got: {state['phases']['1a']['status']}"
        )

    def test_phase_reporter_without_project_dir_does_not_crash(self, tmp_path: Path) -> None:
        """When project_dir is empty, phase_reporter logs normally without error."""
        import asyncio

        # No project_dir — should not crash, just skip the bridge
        result = asyncio.run(
            phase_reporter(
                phase="1a",
                status="info",
                message="Info log entry",
                run_id="test-bridge-003",
                project_dir="",  # No bridge activated
            )
        )
        assert result is not None  # Should return a string

    def test_phase_reporter_without_run_id_does_not_crash(self) -> None:
        """When run_id is empty, phase_reporter writes to global log without error."""
        import asyncio

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
        run_id = "test-bridge-004"
        import asyncio

        init_run(run_id, str(tmp_path))

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
        assert "1a" in state["phases"], (
            "Phase '1a' not found — normalization from 'Phase 1a: ...' may have failed"
        )
