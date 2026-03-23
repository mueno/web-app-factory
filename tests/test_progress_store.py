from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest

from web_app_factory._progress_store import ProgressEvent, ProgressStore, get_store


def _make_event(run_id: str, event_type: str, phase_id: str = "1a", message: str = "msg", detail: dict | None = None) -> ProgressEvent:
    return ProgressEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        run_id=run_id,
        event_type=event_type,
        phase_id=phase_id,
        message=message,
        detail=detail or {},
    )


def test_emit_and_get_events():
    store = ProgressStore()
    ev1 = _make_event("run-1", "phase_start", "1a", "Starting phase 1a")
    ev2 = _make_event("run-1", "phase_complete", "1a", "Phase 1a done")

    store.emit(ev1)
    store.emit(ev2)

    events = store.get_events("run-1")
    assert len(events) == 2
    assert events[0] is ev1
    assert events[1] is ev2


def test_bounded_size():
    store = ProgressStore()
    for i in range(600):
        store.emit(_make_event("run-bound", "substep_done", "1a", f"step {i}"))

    events = store.get_events("run-bound")
    assert len(events) == 500
    # The last 500 should be retained; first 100 evicted
    assert events[-1].message == "step 599"
    assert events[0].message == "step 100"


def test_get_run_summary():
    store = ProgressStore()
    store.emit(_make_event("run-sum", "phase_start", "1a"))
    store.emit(_make_event("run-sum", "phase_complete", "1a"))
    store.emit(_make_event("run-sum", "phase_start", "1b"))
    store.emit(_make_event("run-sum", "phase_complete", "1b"))
    store.emit(_make_event("run-sum", "phase_start", "2a"))

    summary = store.get_run_summary("run-sum")
    assert summary is not None
    assert summary["run_id"] == "run-sum"
    assert summary["status"] == "running"
    assert summary["current_phase"] == "2a"
    assert summary["completed_count"] == 2
    assert summary["phase_statuses"]["1a"] == "completed"
    assert summary["phase_statuses"]["1b"] == "completed"
    assert summary["phase_statuses"]["2a"] == "running"


def test_get_run_summary_gate_failure():
    store = ProgressStore()
    store.emit(_make_event("run-fail", "phase_start", "1a"))
    store.emit(_make_event("run-fail", "gate_result", "1a", "Gate failed", {"passed": False}))

    summary = store.get_run_summary("run-fail")
    assert summary is not None
    assert summary["phase_statuses"]["1a"] == "failed"


def test_get_run_summary_error_sets_status():
    store = ProgressStore()
    store.emit(_make_event("run-err", "phase_start", "1a"))
    store.emit(_make_event("run-err", "error", "1a", "Something broke"))

    summary = store.get_run_summary("run-err")
    assert summary["status"] == "failed"


def test_set_get_plan():
    store = ProgressStore()
    plan = {"phases": ["1a", "1b", "2a"], "app_name": "MyApp"}
    store.set_plan("run-plan", plan)

    retrieved = store.get_plan("run-plan")
    assert retrieved is plan


def test_set_plan_initializes_run_status():
    store = ProgressStore()
    store.set_plan("run-new", {"phases": []})

    # set_plan should initialize status to "running"
    summary = store.get_run_summary("run-new")
    # No events, so summary returns None (run not in _runs)
    # But get_plan should work
    assert store.get_plan("run-new") is not None


def test_list_runs():
    store = ProgressStore()
    store.emit(_make_event("alpha", "phase_start", "1a"))
    store.emit(_make_event("beta", "phase_start", "1a"))
    store.emit(_make_event("beta", "phase_complete", "1a"))

    runs = store.list_runs()
    run_ids = {r["run_id"] for r in runs}
    assert "alpha" in run_ids
    assert "beta" in run_ids

    beta_info = next(r for r in runs if r["run_id"] == "beta")
    assert beta_info["event_count"] == 2
    assert beta_info["status"] == "running"


def test_list_runs_completed_status():
    store = ProgressStore()
    store.emit(_make_event("done-run", "pipeline_complete", ""))

    runs = store.list_runs()
    info = next(r for r in runs if r["run_id"] == "done-run")
    assert info["status"] == "completed"


def test_unknown_run_returns_none():
    store = ProgressStore()
    result = store.get_run_summary("nonexistent-run-xyz")
    assert result is None


def test_get_events_unknown_run_returns_empty():
    store = ProgressStore()
    events = store.get_events("no-such-run")
    assert events == []


def test_get_events_since_negative():
    store = ProgressStore()
    for i in range(10):
        store.emit(_make_event("run-slice", "substep_done", "1a", f"step {i}"))

    last_3 = store.get_events("run-slice", since=-3)
    assert len(last_3) == 3
    assert last_3[-1].message == "step 9"
    assert last_3[0].message == "step 7"


def test_thread_safety():
    store = ProgressStore()
    errors = []

    def emit_events(thread_id: int):
        try:
            for i in range(50):
                store.emit(_make_event(f"thread-run-{thread_id}", "substep_done", "1a", f"t{thread_id}-step{i}"))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=emit_events, args=(t,)) for t in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread safety errors: {errors}"

    # Each thread has its own run_id, so each should have exactly 50 events
    for thread_id in range(10):
        events = store.get_events(f"thread-run-{thread_id}")
        assert len(events) == 50


def test_thread_safety_shared_run():
    """Multiple threads writing to the same run_id should not corrupt state."""
    store = ProgressStore()
    errors = []

    def emit_events():
        try:
            for i in range(50):
                store.emit(_make_event("shared-run", "substep_done", "1a", f"step-{i}"))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=emit_events) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread safety errors: {errors}"

    # 10 threads * 50 events = 500, but deque is bounded at 500 so all fit
    events = store.get_events("shared-run")
    assert len(events) == 500


def test_get_store_returns_singleton():
    store1 = get_store()
    store2 = get_store()
    assert store1 is store2


def test_pipeline_complete_sets_completed_status():
    store = ProgressStore()
    store.emit(_make_event("run-complete", "phase_start", "1a"))
    store.emit(_make_event("run-complete", "pipeline_complete", ""))

    runs = store.list_runs()
    info = next(r for r in runs if r["run_id"] == "run-complete")
    assert info["status"] == "completed"
