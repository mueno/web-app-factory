"""Tests for project skeleton — RED phase.

Tests that verify:
1. Required packages are importable
2. conftest fixtures work
"""
import pytest
from pathlib import Path


def test_yaml_importable():
    import yaml
    assert yaml is not None


def test_jsonschema_importable():
    import jsonschema
    assert jsonschema is not None


def test_httpx_importable():
    import httpx
    assert httpx is not None


def test_tmp_project_dir_fixture(tmp_project_dir):
    """conftest fixture creates temp dir with docs/pipeline/ subdirectory."""
    assert tmp_project_dir.exists()
    assert (tmp_project_dir / "docs" / "pipeline").exists()
    assert (tmp_project_dir / "docs" / "pipeline" / "runs").exists()


def test_sample_contract_path_fixture(sample_contract_path):
    """conftest fixture returns path pointing to expected location."""
    assert sample_contract_path.name == "pipeline-contract.web.v1.yaml"
    assert "contracts" in str(sample_contract_path)
