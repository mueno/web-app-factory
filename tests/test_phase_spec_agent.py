"""Tests for SPEC-04: spec agent definition and shared runner utility.

Validates:
- SPEC_AGENT system prompt is web-specific with no iOS references
- spec_agent_runner utility functions work correctly
- mock_agent_query fixture is available for downstream tests
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.definitions import SPEC_AGENT


# ---------------------------------------------------------------------------
# SPEC_AGENT system prompt content tests (SPEC-04)
# ---------------------------------------------------------------------------


def test_spec_agent_system_prompt_is_nonempty():
    """System prompt must be a real string longer than 100 chars (no stub)."""
    assert isinstance(SPEC_AGENT.system_prompt, str)
    assert len(SPEC_AGENT.system_prompt) > 100


def test_spec_agent_system_prompt_contains_web_references():
    """System prompt must reference web technologies (Next.js or 'web')."""
    prompt_lower = SPEC_AGENT.system_prompt.lower()
    assert "next.js" in prompt_lower or "web" in prompt_lower, (
        "SPEC_AGENT.system_prompt must reference web technologies (Next.js or web)"
    )


def test_spec_agent_no_ios_references():
    """SPEC-04: system prompt must contain zero iOS/mobile native references."""
    prompt_lower = SPEC_AGENT.system_prompt.lower()
    forbidden = ["ios", "swift", "xcode", "app store", "healthkit", "uikit"]
    found = [term for term in forbidden if term in prompt_lower]
    assert not found, (
        f"SPEC-04 violation: system_prompt contains iOS references: {found}"
    )


def test_spec_agent_name_and_description():
    """Agent name and description must be set correctly."""
    assert SPEC_AGENT.name == "spec-agent"
    assert len(SPEC_AGENT.description) > 0


# ---------------------------------------------------------------------------
# load_phase_quality_criteria tests
# ---------------------------------------------------------------------------


@pytest.fixture
def contract_path():
    """Return the path to the pipeline contract YAML file."""
    return Path(__file__).parent.parent / "contracts" / "pipeline-contract.web.v1.yaml"


def test_load_quality_criteria_1a_returns_nonempty(contract_path):
    """Phase 1a quality criteria must be non-empty list of strings."""
    from tools.phase_executors.spec_agent_runner import load_phase_quality_criteria

    criteria = load_phase_quality_criteria("1a", contract_path)
    assert isinstance(criteria, list)
    assert len(criteria) > 0
    assert all(isinstance(c, str) for c in criteria)


def test_load_quality_criteria_1b_returns_nonempty(contract_path):
    """Phase 1b quality criteria must be non-empty list of strings."""
    from tools.phase_executors.spec_agent_runner import load_phase_quality_criteria

    criteria = load_phase_quality_criteria("1b", contract_path)
    assert isinstance(criteria, list)
    assert len(criteria) > 0


def test_load_quality_criteria_nonexistent_phase_returns_empty(contract_path):
    """Non-existent phase_id must return an empty list (no crash)."""
    from tools.phase_executors.spec_agent_runner import load_phase_quality_criteria

    criteria = load_phase_quality_criteria("nonexistent", contract_path)
    assert criteria == []


def test_load_quality_criteria_1a_content(contract_path):
    """Phase 1a criteria should include competitor analysis requirement."""
    from tools.phase_executors.spec_agent_runner import load_phase_quality_criteria

    criteria = load_phase_quality_criteria("1a", contract_path)
    combined = " ".join(criteria).lower()
    assert "competitor" in combined, "Phase 1a criteria must mention competitors"


# ---------------------------------------------------------------------------
# build_phase_system_prompt tests
# ---------------------------------------------------------------------------


def test_build_phase_system_prompt_appends_criteria():
    """build_phase_system_prompt must append a Quality Criteria section."""
    from tools.phase_executors.spec_agent_runner import build_phase_system_prompt

    base = "You are a helpful agent."
    criteria = ["Criterion A", "Criterion B", "Criterion C"]
    result = build_phase_system_prompt(base, criteria)

    assert base in result
    assert "Quality Criteria" in result
    for criterion in criteria:
        assert criterion in result


def test_build_phase_system_prompt_contains_anti_gaming_instruction():
    """Prompt must include instruction not to optimize for gate markers."""
    from tools.phase_executors.spec_agent_runner import build_phase_system_prompt

    result = build_phase_system_prompt("Base prompt", ["Criterion X"])
    assert "gate" in result.lower() or "gate markers" in result.lower(), (
        "Prompt must contain anti-gate-gaming instruction"
    )


def test_build_phase_system_prompt_empty_criteria():
    """Empty criteria list returns base prompt with Quality Criteria section or just base."""
    from tools.phase_executors.spec_agent_runner import build_phase_system_prompt

    base = "Base prompt text."
    result = build_phase_system_prompt(base, [])
    assert base in result


# ---------------------------------------------------------------------------
# run_spec_agent tests (using mock_agent_query fixture)
# ---------------------------------------------------------------------------


def test_run_spec_agent_calls_sdk_query(mock_agent_query):
    """run_spec_agent must call claude_agent_sdk.query with ClaudeAgentOptions."""
    from tools.phase_executors.spec_agent_runner import run_spec_agent

    result = run_spec_agent(
        prompt="Test prompt",
        system_prompt="System prompt",
        project_dir="/tmp/test",
    )
    assert mock_agent_query.called


def test_run_spec_agent_returns_result_text(mock_agent_query):
    """run_spec_agent must return the ResultMessage.result text."""
    from tools.phase_executors.spec_agent_runner import run_spec_agent

    result = run_spec_agent(
        prompt="Test prompt",
        system_prompt="System prompt",
        project_dir="/tmp/test",
    )
    assert result == "mocked agent output"


def test_run_spec_agent_returns_empty_when_no_result(tmp_path):
    """run_spec_agent returns empty string when agent produces no ResultMessage."""
    from tools.phase_executors.spec_agent_runner import run_spec_agent

    async def empty_gen(*args, **kwargs):
        return
        yield  # make it an async generator

    with patch(
        "tools.phase_executors.spec_agent_runner.query",
        side_effect=empty_gen,
    ):
        result = run_spec_agent(
            prompt="Test prompt",
            system_prompt="System prompt",
            project_dir=str(tmp_path),
        )
    assert result == ""


def test_run_spec_agent_drains_entire_generator(tmp_path):
    """run_spec_agent must consume ALL messages, not break early on ResultMessage.

    Regression test for: RuntimeError: Attempted to exit cancel scope in a
    different task than it was entered in.

    The SDK's process_query() uses anyio TaskGroups internally. If the caller
    breaks out of the async generator early (via `return` inside `async for`),
    Python sends GeneratorExit into the generator, causing its finally block to
    run query.close() in a different task context than query.start() was called
    in. anyio detects this as a cancel scope cross-task violation.

    Fix: collect the first ResultMessage but continue iterating to generator
    exhaustion so cleanup happens in the same task context.
    """
    from claude_agent_sdk.types import ResultMessage
    from tools.phase_executors.spec_agent_runner import run_spec_agent

    messages_yielded: list[int] = []
    cleanup_ran: list[bool] = []

    async def multi_message_gen(*args, **kwargs):
        """Generator that yields a ResultMessage then more messages, tracks full drain."""
        messages_yielded.append(1)
        yield ResultMessage(
            subtype="result",
            duration_ms=100,
            duration_api_ms=100,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            result="first result",
        )
        # These messages come AFTER ResultMessage — must be consumed without breaking
        messages_yielded.append(2)
        messages_yielded.append(3)
        cleanup_ran.append(True)

    with patch(
        "tools.phase_executors.spec_agent_runner.query",
        side_effect=multi_message_gen,
    ):
        result = run_spec_agent(
            prompt="Test prompt",
            system_prompt="System prompt",
            project_dir=str(tmp_path),
        )

    assert result == "first result", "Should return first ResultMessage text"
    assert len(messages_yielded) == 3, (
        f"Generator was not fully drained — only {len(messages_yielded)} of 3 "
        "items were yielded. Early break from async for will cause anyio "
        "cancel scope cross-task RuntimeError in the real SDK."
    )
    assert cleanup_ran, "Generator cleanup (final statements) must execute"
