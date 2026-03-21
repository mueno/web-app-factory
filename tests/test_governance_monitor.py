"""Tests for pipeline_runtime/governance_monitor.py and tools/gates/gate_result.py.

Verifies:
1. GovernanceViolationError can be instantiated with a violation kind
2. GovernanceMonitor raises GovernanceViolationError for phase_order_violation
3. GovernanceMonitor raises GovernanceViolationError for write_without_phase_start
4. GateResult defaults to passed=False
5. GateResult(passed=True) has passed=True
"""

import pytest

from pipeline_runtime.governance_monitor import (
    GovernanceViolationError,
    GovernanceMonitor,
)
from tools.gates.gate_result import GateResult


# ── GovernanceViolationError ──────────────────────────────────────────────


def test_governance_violation_error_instantiation():
    """GovernanceViolationError should be instantiatable with kind and message."""
    err = GovernanceViolationError("phase_order_violation", "test message")
    assert err.kind == "phase_order_violation"
    assert str(err) == "test message"


def test_governance_violation_error_is_exception():
    """GovernanceViolationError must be an Exception subclass."""
    with pytest.raises(GovernanceViolationError):
        raise GovernanceViolationError("phase_order_violation", "test")


# ── GovernanceMonitor — phase order enforcement ───────────────────────────


def test_governance_monitor_phase_order_violation(tmp_path):
    """Starting '2a' before '1b' is complete must raise GovernanceViolationError."""
    monitor = GovernanceMonitor(run_id="test-run-001", project_dir=str(tmp_path))

    # Complete 1a only, then try to start 2a (skipping 1b)
    monitor.on_tool_use(
        "mcp__factory__phase_reporter",
        {"phase": "1a", "status": "start"},
    )
    monitor.on_tool_use(
        "mcp__factory__phase_reporter",
        {"phase": "1a", "status": "complete"},
    )

    with pytest.raises(GovernanceViolationError) as exc_info:
        monitor.on_tool_use(
            "mcp__factory__phase_reporter",
            {"phase": "2a", "status": "start"},
        )
    assert exc_info.value.kind == "phase_order_violation"


def test_governance_monitor_valid_phase_order_does_not_raise(tmp_path):
    """Executing phases in valid order must not raise."""
    monitor = GovernanceMonitor(run_id="test-run-002", project_dir=str(tmp_path))

    # 1a start -> complete -> 1b start: this is valid
    monitor.on_tool_use(
        "mcp__factory__phase_reporter",
        {"phase": "1a", "status": "start"},
    )
    monitor.on_tool_use(
        "mcp__factory__phase_reporter",
        {"phase": "1a", "status": "complete"},
    )
    # Should not raise
    monitor.on_tool_use(
        "mcp__factory__phase_reporter",
        {"phase": "1b", "status": "start"},
    )


def test_governance_monitor_first_phase_does_not_require_predecessor(tmp_path):
    """Starting '1a' (first phase) must not raise even with empty history."""
    monitor = GovernanceMonitor(run_id="test-run-003", project_dir=str(tmp_path))
    # Should not raise
    monitor.on_tool_use(
        "mcp__factory__phase_reporter",
        {"phase": "1a", "status": "start"},
    )


# ── GovernanceMonitor — write without phase start ─────────────────────────


def test_governance_monitor_write_without_phase_start_raises(tmp_path):
    """3+ write-class tool calls without phase_reporter start should raise."""
    monitor = GovernanceMonitor(run_id="test-run-004", project_dir=str(tmp_path))

    with pytest.raises(GovernanceViolationError) as exc_info:
        for _ in range(3):
            monitor.on_tool_use("Write", {"path": "/tmp/test.txt", "content": "x"})
    assert exc_info.value.kind == "write_without_phase_start"


# ── GateResult ────────────────────────────────────────────────────────────


def test_gate_result_default_passed_is_false():
    """Default GateResult must have passed=False."""
    result = GateResult()
    assert result.passed is False


def test_gate_result_explicit_true():
    """GateResult(passed=True) must have passed=True."""
    result = GateResult(passed=True)
    assert result.passed is True


def test_gate_result_is_frozen():
    """GateResult is frozen — direct attribute assignment must raise."""
    result = GateResult()
    with pytest.raises(Exception):
        result.passed = True  # type: ignore[misc]


def test_gate_result_dict_access():
    """GateResult supports dict-like key access for backward compatibility."""
    result = GateResult(passed=True, phase_id="1a")
    assert result["passed"] is True
    assert result["phase_id"] == "1a"
    assert result.get("missing_key", "default") == "default"
