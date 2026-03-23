"""Tests for the async pipeline bridge (MCPI-03).

These tests verify:
1. start_pipeline_async() returns a run_id string in under 1 second
2. The pipeline runs in a background thread (not blocking the event loop)
3. run_id format is YYYYMMDD-HHMMSS-slug
4. _ACTIVE_RUNS dict tracks running pipelines
"""
from __future__ import annotations

import asyncio
import re
import threading
import time
from unittest.mock import patch, MagicMock

import pytest


class TestReturnRunIdImmediately:
    """start_pipeline_async() returns run_id in under 1 second even if pipeline is slow."""

    def test_returns_run_id_immediately(self):
        """A mocked run_pipeline that sleeps 5 seconds -- run_id must arrive before sleep ends."""
        pipeline_started = threading.Event()

        def slow_pipeline(**kwargs):
            pipeline_started.set()
            time.sleep(5)
            return {"status": "completed"}

        with patch("web_app_factory._pipeline_bridge._run_pipeline_sync", side_effect=slow_pipeline):
            from web_app_factory._pipeline_bridge import start_pipeline_async

            start = time.monotonic()
            run_id = asyncio.run(start_pipeline_async("a recipe app", "./output/TestApp"))
            elapsed = time.monotonic() - start

        assert isinstance(run_id, str), f"run_id must be a string, got {type(run_id)}"
        assert elapsed < 1.0, f"start_pipeline_async took {elapsed:.2f}s — must return in under 1 second"


class TestPipelineRunsInBackground:
    """After run_id is returned, the mocked run_pipeline function is eventually called."""

    def test_pipeline_runs_in_background(self):
        """Pipeline actually runs, not just gets scheduled."""
        called_event = threading.Event()
        call_args_holder: list = []

        def record_and_return(**kwargs):
            call_args_holder.append(kwargs)
            called_event.set()
            return {"status": "completed"}

        with patch("web_app_factory._pipeline_bridge._run_pipeline_sync", side_effect=record_and_return):
            from web_app_factory import _pipeline_bridge
            # Reload to get fresh _ACTIVE_RUNS
            import importlib
            importlib.reload(_pipeline_bridge)

            with patch("web_app_factory._pipeline_bridge._run_pipeline_sync", side_effect=record_and_return):
                run_id = asyncio.run(_pipeline_bridge.start_pipeline_async("my todo app", "./output/TodoApp"))

                # Wait up to 3 seconds for pipeline to actually execute
                called = called_event.wait(timeout=3.0)

        assert called, "Pipeline function was never called in background thread"
        assert len(call_args_holder) == 1, "Pipeline should have been called exactly once"


class TestRunIdFormat:
    """run_id matches pattern YYYYMMDD-HHMMSS-slug."""

    def test_run_id_format(self):
        """run_id is formatted as YYYYMMDD-HHMMSS-<idea-slug>."""
        def noop_pipeline(**kwargs):
            return {"status": "completed"}

        with patch("web_app_factory._pipeline_bridge._run_pipeline_sync", side_effect=noop_pipeline):
            from web_app_factory import _pipeline_bridge
            import importlib
            importlib.reload(_pipeline_bridge)

            with patch("web_app_factory._pipeline_bridge._run_pipeline_sync", side_effect=noop_pipeline):
                run_id = asyncio.run(_pipeline_bridge.start_pipeline_async("A recipe manager", "./output/RecipeApp"))

        # YYYYMMDD-HHMMSS-slug pattern
        pattern = r"^\d{8}-\d{6}-[a-z0-9-]+$"
        assert re.match(pattern, run_id), (
            f"run_id '{run_id}' does not match YYYYMMDD-HHMMSS-slug pattern"
        )


class TestActiveRunsTracking:
    """After start, run_id appears in _ACTIVE_RUNS dict."""

    def test_active_runs_tracking(self):
        """_ACTIVE_RUNS tracks running pipelines."""
        slow_started = threading.Event()

        def slow_pipeline(**kwargs):
            slow_started.set()
            time.sleep(5)  # Keep it running so we can observe it in _ACTIVE_RUNS
            return {"status": "completed"}

        with patch("web_app_factory._pipeline_bridge._run_pipeline_sync", side_effect=slow_pipeline):
            from web_app_factory import _pipeline_bridge
            import importlib
            importlib.reload(_pipeline_bridge)

            with patch("web_app_factory._pipeline_bridge._run_pipeline_sync", side_effect=slow_pipeline):
                run_id = asyncio.run(_pipeline_bridge.start_pipeline_async("task tracker app", "./output/TaskApp"))

                # run_id should be in _ACTIVE_RUNS immediately after start
                assert run_id in _pipeline_bridge._ACTIVE_RUNS, (
                    f"run_id '{run_id}' not found in _ACTIVE_RUNS after start_pipeline_async"
                )
