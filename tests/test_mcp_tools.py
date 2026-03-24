"""Tests for waf_ MCP tools (TOOL-01 through TOOL-04).

Verifies tool behavior with mocked pipeline bridge — no real pipeline runs.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from web_app_factory._plan_generator import ExecutionPlan, PhasePlan
from web_app_factory._progress_store import ProgressStore, ProgressEvent
import web_app_factory._progress_store as _ps_module


def _make_test_plan(run_id: str = "20260323-143000-test-app") -> ExecutionPlan:
    """Create a minimal ExecutionPlan for testing."""
    return ExecutionPlan(
        run_id=run_id,
        idea="test app",
        deploy_target="vercel",
        phases=(
            PhasePlan("1a", "Idea Validation", "Validate", ["Report"], ["artifact"], "light"),
            PhasePlan("1b", "Spec", "Write spec", ["PRD"], ["artifact"], "light"),
        ),
        total_phases=2,
        created_at="2026-03-23T14:30:00+00:00",
    )


@pytest.fixture(autouse=True)
def _fresh_store(monkeypatch):
    """Replace the module-level singleton with a fresh store for each test."""
    fresh = ProgressStore()
    monkeypatch.setattr(_ps_module, "_STORE", fresh)
    return fresh


class TestWafGenerateApp:
    """TOOL-01: waf_generate_app starts pipeline and returns execution plan."""

    def test_returns_execution_plan(self):
        test_plan = _make_test_plan()
        with patch(
            "web_app_factory._pipeline_bridge.start_pipeline_async",
            new_callable=AsyncMock,
            return_value=("20260323-143000-test-app", test_plan),
        ):
            from web_app_factory.mcp_server import waf_generate_app
            result = asyncio.run(waf_generate_app("test app"))

        assert "20260323-143000-test-app" in result
        assert "Execution Plan" in result
        assert "Idea Validation" in result
        assert "waf_get_status" in result

    def test_validates_empty_idea(self):
        from web_app_factory.mcp_server import waf_generate_app
        with pytest.raises(ValueError, match="must not be empty"):
            asyncio.run(waf_generate_app(""))

    def test_passes_deploy_target(self):
        test_plan = _make_test_plan()
        with patch(
            "web_app_factory._pipeline_bridge.start_pipeline_async",
            new_callable=AsyncMock,
            return_value=("20260323-143000-test-app", test_plan),
        ) as mock_bridge:
            from web_app_factory.mcp_server import waf_generate_app
            asyncio.run(waf_generate_app("test app", deploy_target="gcp"))

        mock_bridge.assert_called_once()
        assert mock_bridge.call_args.kwargs.get("deploy_target") == "gcp"

    def test_passes_resume_run_id(self):
        test_plan = _make_test_plan()
        with patch(
            "web_app_factory._pipeline_bridge.start_pipeline_async",
            new_callable=AsyncMock,
            return_value=("existing-run-id", test_plan),
        ) as mock_bridge:
            from web_app_factory.mcp_server import waf_generate_app
            asyncio.run(waf_generate_app("test app", resume_run_id="existing-run-id"))

        mock_bridge.assert_called_once()
        assert mock_bridge.call_args.kwargs.get("resume_run_id") == "existing-run-id"


class TestWafGetStatus:
    """TOOL-02: waf_get_status returns current pipeline progress."""

    def test_returns_status_from_store(self, _fresh_store):
        store = _fresh_store
        plan = _make_test_plan("run-123")
        store.set_plan("run-123", plan)
        store.emit(ProgressEvent(
            timestamp="2026-03-23T14:30:00Z",
            run_id="run-123",
            event_type="phase_start",
            phase_id="1a",
            message="Starting Idea Validation",
        ))

        from web_app_factory.mcp_server import waf_get_status
        result = asyncio.run(waf_get_status("run-123"))

        assert "Pipeline Progress" in result
        assert "Idea Validation" in result

    def test_unknown_run_returns_not_found(self):
        from web_app_factory.mcp_server import waf_get_status
        result = asyncio.run(waf_get_status("nonexistent-run"))
        assert "not found" in result.lower()


class TestWafApproveGate:
    """TOOL-03: waf_approve_gate approves/rejects gates."""

    def test_approve(self, tmp_path):
        with patch("web_app_factory.mcp_server._PROJECT_ROOT", tmp_path):
            from web_app_factory.mcp_server import waf_approve_gate
            result = asyncio.run(waf_approve_gate("run-123", "approve"))
        assert "approved" in result.lower()

    def test_reject(self, tmp_path):
        with patch("web_app_factory.mcp_server._PROJECT_ROOT", tmp_path):
            from web_app_factory.mcp_server import waf_approve_gate
            result = asyncio.run(waf_approve_gate("run-123", "reject", "Build failed"))
        assert "rejected" in result.lower()
        assert "Build failed" in result

    def test_invalid_decision(self):
        from web_app_factory.mcp_server import waf_approve_gate
        result = asyncio.run(waf_approve_gate("run-123", "maybe"))
        assert "Invalid decision" in result

    def test_auto_mode_returns_error(self, _fresh_store):
        """TOOL-03: auto mode runs should reject manual gate approval."""
        store = _fresh_store
        plan = _make_test_plan("run-auto")
        store.set_plan("run-auto", plan, mode="auto")

        from web_app_factory.mcp_server import waf_approve_gate
        result = asyncio.run(waf_approve_gate("run-auto", "approve"))
        assert "auto" in result.lower()
        assert "interactive" in result.lower()

    def test_interactive_mode_allows_approval(self, _fresh_store, tmp_path):
        """TOOL-03: interactive mode runs should allow manual gate approval."""
        store = _fresh_store
        plan = _make_test_plan("run-int")
        store.set_plan("run-int", plan, mode="interactive")

        with patch("web_app_factory.mcp_server._PROJECT_ROOT", tmp_path):
            from web_app_factory.mcp_server import waf_approve_gate
            result = asyncio.run(waf_approve_gate("run-int", "approve"))
        assert "approved" in result.lower()


class TestWafListRuns:
    """TOOL-04: waf_list_runs lists all pipeline runs."""

    def test_empty_list(self):
        with patch("web_app_factory.mcp_server._scan_disk_runs", return_value=[]):
            from web_app_factory.mcp_server import waf_list_runs
            result = asyncio.run(waf_list_runs())
        assert "No pipeline runs found" in result

    def test_lists_active_runs(self, _fresh_store):
        store = _fresh_store
        store.emit(ProgressEvent(
            timestamp="2026-03-23T14:30:00Z",
            run_id="run-abc",
            event_type="phase_start",
            phase_id="1a",
            message="Starting",
        ))

        with patch("web_app_factory.mcp_server._scan_disk_runs", return_value=[]):
            from web_app_factory.mcp_server import waf_list_runs
            result = asyncio.run(waf_list_runs())

        assert "run-abc" in result
        assert "Pipeline Runs" in result

    def test_shows_output_url_from_disk(self):
        """TOOL-04: completed runs should include output URL."""
        disk_runs = [
            {
                "run_id": "run-deployed",
                "status": "completed",
                "started_at": "2026-03-23T10:00:00Z",
                "url": "https://my-app.vercel.app",
            },
        ]
        with patch("web_app_factory.mcp_server._scan_disk_runs", return_value=disk_runs):
            from web_app_factory.mcp_server import waf_list_runs
            result = asyncio.run(waf_list_runs())

        assert "https://my-app.vercel.app" in result
        assert "run-deployed" in result
