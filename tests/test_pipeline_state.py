"""Tests for tools/pipeline_state.py.

Verifies:
1. PHASE_ORDER equals the 5 web phase IDs
2. init_run creates state.json with correct structure
3. phase_start marks phase as "running" in state.json
4. phase_complete marks phase as "completed" in state.json
5. activity-log.jsonl receives entries for init, start, complete events
6. get_resume_phase returns correct phase after interruption
"""

import json
import pytest
from pathlib import Path

from tools.pipeline_state import (
    PHASE_ORDER,
    init_run,
    load_state,
    phase_start,
    phase_complete,
    get_resume_phase,
)


# ── Constants ──────────────────────────────────────────────────────────────


def test_phase_order_is_web_phases():
    """PHASE_ORDER must be exactly the 5 web phases in pipeline order."""
    assert PHASE_ORDER == ["1a", "1b", "2a", "2b", "3"], (
        f"Expected ['1a', '1b', '2a', '2b', '3'], got {PHASE_ORDER}"
    )


def test_phase_order_has_exactly_5_entries():
    assert len(PHASE_ORDER) == 5


# ── init_run ───────────────────────────────────────────────────────────────


def test_init_run_creates_state_json(tmp_project_dir):
    """init_run must create state.json under docs/pipeline/runs/{run_id}/."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="A test web application",
    )
    state_path = (
        tmp_project_dir
        / "docs"
        / "pipeline"
        / "runs"
        / state.run_id
        / "state.json"
    )
    assert state_path.exists(), f"state.json not found at {state_path}"


def test_init_run_state_has_run_id(tmp_project_dir):
    """state.json must contain a non-empty run_id."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test",
    )
    data = json.loads(
        (
            tmp_project_dir
            / "docs"
            / "pipeline"
            / "runs"
            / state.run_id
            / "state.json"
        ).read_text()
    )
    assert data["run_id"] == state.run_id
    assert data["run_id"]  # non-empty


def test_init_run_state_has_all_5_phase_ids(tmp_project_dir):
    """state.json phases dict must contain all 5 web phases as keys."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test idea",
    )
    data = json.loads(
        (
            tmp_project_dir
            / "docs"
            / "pipeline"
            / "runs"
            / state.run_id
            / "state.json"
        ).read_text()
    )
    phases = data.get("phases", {})
    for pid in PHASE_ORDER:
        assert pid in phases, f"Phase '{pid}' missing from state.json phases"


def test_init_run_phases_are_pending(tmp_project_dir):
    """All phase records should start as 'pending' status."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test",
    )
    for pid, record in state.phases.items():
        if pid in PHASE_ORDER:
            assert record.get("status") == "pending", (
                f"Phase {pid} expected 'pending', got {record.get('status')}"
            )


# ── slug / run_id safety ───────────────────────────────────────────────────


def test_init_run_non_ascii_idea_produces_valid_run_id(tmp_project_dir):
    """Non-ASCII app names (e.g. Japanese) must produce ASCII-only run_id.

    Regression: Japanese characters passed str.isalnum() but failed
    _validate_run_id's [A-Za-z0-9._-] pattern, crashing PhaseContext.
    """
    state = init_run(
        app_name="温泉旅館に特化したAirBnBみたいな旅行予約サイト",
        project_dir=str(tmp_project_dir),
        idea="温泉旅館に特化したAirBnBみたいな旅行予約サイト",
    )
    assert state.run_id.isascii(), f"run_id contains non-ASCII: {state.run_id}"
    # Must also survive PhaseContext validation
    from tools.phase_executors.base import _validate_run_id
    _validate_run_id(state.run_id)


def test_init_run_all_non_ascii_idea_still_works(tmp_project_dir):
    """Purely non-ASCII input should produce a fallback slug, not empty."""
    state = init_run(
        app_name="日本語のみ",
        project_dir=str(tmp_project_dir),
        idea="日本語のみ",
    )
    assert state.run_id.isascii()
    assert len(state.run_id) > 0
    from tools.phase_executors.base import _validate_run_id
    _validate_run_id(state.run_id)


# ── phase lifecycle ────────────────────────────────────────────────────────


def test_phase_start_marks_running(tmp_project_dir):
    """phase_start must set phase status to 'running'."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test",
    )
    phase_start(state.run_id, "1a", str(tmp_project_dir))
    updated = load_state(state.run_id, str(tmp_project_dir))
    assert updated.phases["1a"]["status"] == "running"


def test_phase_complete_marks_completed(tmp_project_dir):
    """phase_complete must set phase status to 'completed'."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test",
    )
    phase_start(state.run_id, "1a", str(tmp_project_dir))
    phase_complete(state.run_id, "1a", str(tmp_project_dir))
    updated = load_state(state.run_id, str(tmp_project_dir))
    assert updated.phases["1a"]["status"] == "completed"


def test_phase_complete_sets_completed_at(tmp_project_dir):
    """phase_complete must set completed_at timestamp."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test",
    )
    phase_start(state.run_id, "1a", str(tmp_project_dir))
    phase_complete(state.run_id, "1a", str(tmp_project_dir))
    updated = load_state(state.run_id, str(tmp_project_dir))
    assert updated.phases["1a"].get("completed_at") is not None


# ── activity log ──────────────────────────────────────────────────────────


def test_activity_log_created_after_init(tmp_project_dir):
    """activity-log.jsonl must exist after init_run."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test",
    )
    log_path = tmp_project_dir / "docs" / "pipeline" / "activity-log.jsonl"
    assert log_path.exists(), "activity-log.jsonl not found"


def test_activity_log_has_init_entry(tmp_project_dir):
    """activity-log.jsonl must have a run_init event after init_run."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test",
    )
    log_path = tmp_project_dir / "docs" / "pipeline" / "activity-log.jsonl"
    entries = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    events = [e["event"] for e in entries]
    assert "run_init" in events, f"run_init not found in events: {events}"


def test_activity_log_has_start_and_complete_entries(tmp_project_dir):
    """activity-log.jsonl must have phase_start and phase_complete entries."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test",
    )
    phase_start(state.run_id, "1a", str(tmp_project_dir))
    phase_complete(state.run_id, "1a", str(tmp_project_dir))
    log_path = tmp_project_dir / "docs" / "pipeline" / "activity-log.jsonl"
    entries = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    events = [e["event"] for e in entries]
    assert "phase_start" in events, f"phase_start not in events: {events}"
    assert "phase_complete" in events, f"phase_complete not in events: {events}"


# ── get_resume_phase ──────────────────────────────────────────────────────


def test_get_resume_phase_fresh_state_returns_first(tmp_project_dir):
    """Fresh pipeline should resume from first phase '1a'."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test",
    )
    resume = get_resume_phase(state.run_id, str(tmp_project_dir))
    assert resume == "1a", f"Expected '1a', got '{resume}'"


def test_get_resume_phase_after_first_complete_returns_second(tmp_project_dir):
    """After completing '1a', resume should return '1b'."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test",
    )
    phase_start(state.run_id, "1a", str(tmp_project_dir))
    phase_complete(state.run_id, "1a", str(tmp_project_dir))
    resume = get_resume_phase(state.run_id, str(tmp_project_dir))
    assert resume == "1b", f"Expected '1b', got '{resume}'"


def test_get_resume_phase_all_complete_returns_none(tmp_project_dir):
    """When all phases are complete, get_resume_phase should return None."""
    state = init_run(
        app_name="test-app",
        project_dir=str(tmp_project_dir),
        idea="test",
    )
    for pid in PHASE_ORDER:
        phase_start(state.run_id, pid, str(tmp_project_dir))
        phase_complete(state.run_id, pid, str(tmp_project_dir))
    resume = get_resume_phase(state.run_id, str(tmp_project_dir))
    assert resume is None, f"Expected None when all phases complete, got '{resume}'"
