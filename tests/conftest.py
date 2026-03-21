"""Shared test fixtures for all test files."""
import pytest
from pathlib import Path


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
