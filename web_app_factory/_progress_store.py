from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class ProgressEvent:
    timestamp: str          # ISO 8601
    run_id: str
    event_type: str         # phase_start | substep_done | gate_start | gate_result | phase_complete | error
    phase_id: str
    message: str
    detail: dict = field(default_factory=dict)


class ProgressStore:
    """Thread-safe in-memory progress event store.

    Pipeline thread writes via emit(). MCP tools read via get_events()/get_run_summary().
    Each run has a bounded deque (maxlen=500) to prevent memory leaks.
    """

    _MAX_EVENTS_PER_RUN = 500
    _MAX_RUNS = 50  # evict oldest completed runs beyond this

    def __init__(self):
        self._lock = threading.Lock()
        self._runs: dict[str, deque[ProgressEvent]] = {}
        self._plans: dict[str, Any] = {}  # run_id -> ExecutionPlan or dict
        self._run_status: dict[str, str] = {}  # run_id -> "running"|"completed"|"failed"

    def emit(self, event: ProgressEvent) -> None:
        """Thread-safe: append event to run's deque."""
        with self._lock:
            if event.run_id not in self._runs:
                self._runs[event.run_id] = deque(maxlen=self._MAX_EVENTS_PER_RUN)
                self._run_status[event.run_id] = "running"
            self._runs[event.run_id].append(event)
            # Track status from events
            if event.event_type == "error":
                self._run_status[event.run_id] = "failed"
            elif event.event_type == "pipeline_complete":
                self._run_status[event.run_id] = "completed"

    def get_events(self, run_id: str, since: int = 0) -> list[ProgressEvent]:
        """Thread-safe: get events for a run. since=0 means all, since=-N means last N."""
        with self._lock:
            events = self._runs.get(run_id)
            if events is None:
                return []
            if since < 0:
                return list(events)[since:]
            return list(events)[since:]

    def set_plan(self, run_id: str, plan: Any) -> None:
        """Store the execution plan for a run."""
        with self._lock:
            self._plans[run_id] = plan
            if run_id not in self._run_status:
                self._run_status[run_id] = "running"

    def get_plan(self, run_id: str) -> Any:
        """Retrieve stored execution plan."""
        with self._lock:
            return self._plans.get(run_id)

    def get_run_summary(self, run_id: str) -> dict | None:
        """Build a summary dict from events: current phase, phase statuses, counts."""
        with self._lock:
            events = self._runs.get(run_id)
            if events is None:
                return None
            plan = self._plans.get(run_id)
            status = self._run_status.get(run_id, "unknown")
            snapshot = list(events)

        # Build summary from events (outside lock for safety)
        phase_statuses = {}  # phase_id -> status
        current_phase = None
        started_at = None

        for ev in snapshot:
            if started_at is None:
                started_at = ev.timestamp
            if ev.event_type == "phase_start":
                phase_statuses[ev.phase_id] = "running"
                current_phase = ev.phase_id
            elif ev.event_type == "phase_complete":
                phase_statuses[ev.phase_id] = "completed"
            elif ev.event_type in ("error", "gate_result") and ev.detail.get("passed") is False:
                phase_statuses[ev.phase_id] = "failed"

        completed_count = sum(1 for s in phase_statuses.values() if s == "completed")
        total_phases = plan.total_phases if plan and hasattr(plan, "total_phases") else len(phase_statuses)

        return {
            "run_id": run_id,
            "status": status,
            "current_phase": current_phase,
            "phase_statuses": phase_statuses,
            "completed_count": completed_count,
            "total_phases": total_phases,
            "started_at": started_at,
            "plan": plan,
        }

    def list_runs(self) -> list[dict]:
        """List all tracked runs with basic info."""
        with self._lock:
            result = []
            for run_id in self._runs:
                events = self._runs[run_id]
                status = self._run_status.get(run_id, "unknown")
                started_at = events[0].timestamp if events else None
                result.append({
                    "run_id": run_id,
                    "status": status,
                    "started_at": started_at,
                    "event_count": len(events),
                })
            return result


# Module-level singleton
_STORE = ProgressStore()


def get_store() -> ProgressStore:
    return _STORE
