"""Shared test fixtures for all test files."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def tmp_project_dir(tmp_path):
    """Create a temporary project directory with docs/pipeline/runs/ subdirectory."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "docs" / "pipeline" / "runs").mkdir(parents=True)
    return project_dir


@pytest.fixture
def sample_contract_path():
    """Return the path to the pipeline contract YAML file."""
    return Path(__file__).parent.parent / "contracts" / "pipeline-contract.web.v1.yaml"


@pytest.fixture
def mock_agent_query():
    """Patch claude_agent_sdk.query in spec_agent_runner to return a canned ResultMessage.

    Returns a ResultMessage with result="mocked agent output" as a single-item
    async iterator. Available for all Phase 2+ executor tests that need to run
    spec agent logic without hitting the real Claude API.
    """
    from claude_agent_sdk.types import ResultMessage

    canned_result = ResultMessage(
        subtype="result",
        duration_ms=100,
        duration_api_ms=100,
        is_error=False,
        num_turns=1,
        session_id="test-session-id",
        result="mocked agent output",
    )

    async def fake_query(*args, **kwargs):
        yield canned_result

    with patch(
        "tools.phase_executors.spec_agent_runner.query",
        side_effect=fake_query,
    ) as mock:
        yield mock
