# Copyright 2026 AllNew LLC. All rights reserved.
"""Tests for quality self-assessment module.

Tests verify that generate_quality_self_assessment:
1. Reads quality_criteria from the YAML contract
2. Produces a JSON structure with correct shape
3. Writes the JSON file to the expected path
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# The module under test — will fail until tools/quality_self_assessment.py exists
from tools.quality_self_assessment import generate_quality_self_assessment

CONTRACT_PATH = Path(__file__).parent.parent / "contracts" / "pipeline-contract.web.v1.yaml"


class TestGenerateQualitySelfAssessment:
    """Tests for generate_quality_self_assessment function."""

    def test_returns_dict_with_required_keys(self, tmp_path: Path) -> None:
        """Generated assessment dict has phase_id, timestamp, deliverables."""
        result = generate_quality_self_assessment(
            phase_id="1a",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        assert isinstance(result, dict)
        assert "phase_id" in result
        assert "timestamp" in result
        assert "deliverables" in result

    def test_phase_id_in_result(self, tmp_path: Path) -> None:
        """Returned dict has the correct phase_id."""
        result = generate_quality_self_assessment(
            phase_id="1a",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        assert result["phase_id"] == "1a"

    def test_deliverables_list_not_empty(self, tmp_path: Path) -> None:
        """Phase 1a has deliverables in the contract, so deliverables list must be non-empty."""
        result = generate_quality_self_assessment(
            phase_id="1a",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        assert isinstance(result["deliverables"], list)
        assert len(result["deliverables"]) > 0

    def test_deliverable_has_name_path_criteria(self, tmp_path: Path) -> None:
        """Each deliverable has name, path, and criteria keys."""
        result = generate_quality_self_assessment(
            phase_id="1a",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        for deliverable in result["deliverables"]:
            assert "name" in deliverable, f"Missing 'name' in {deliverable}"
            assert "path" in deliverable, f"Missing 'path' in {deliverable}"
            assert "criteria" in deliverable, f"Missing 'criteria' in {deliverable}"

    def test_each_criterion_has_status_pending(self, tmp_path: Path) -> None:
        """Every criterion starts with status 'pending' and evidence null."""
        result = generate_quality_self_assessment(
            phase_id="1a",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        for deliverable in result["deliverables"]:
            for criterion in deliverable["criteria"]:
                assert "criterion" in criterion
                assert criterion["status"] == "pending"
                assert criterion["evidence"] is None

    def test_criteria_count_matches_contract(self, tmp_path: Path) -> None:
        """Phase 1a has 5 criteria for first deliverable (Idea Validation Report)."""
        result = generate_quality_self_assessment(
            phase_id="1a",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        # The first deliverable (Idea Validation Report) has 5 criteria in the contract
        first_deliverable = result["deliverables"][0]
        assert len(first_deliverable["criteria"]) == 5

    def test_writes_json_file_to_expected_path(self, tmp_path: Path) -> None:
        """JSON file is written to docs/pipeline/quality-self-assessment-{phase_id}.json."""
        generate_quality_self_assessment(
            phase_id="1a",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        expected_path = tmp_path / "docs" / "pipeline" / "quality-self-assessment-1a.json"
        assert expected_path.exists(), f"Expected file not created at {expected_path}"

    def test_written_json_is_valid_and_matches_returned_dict(self, tmp_path: Path) -> None:
        """The JSON file content matches the returned dict."""
        result = generate_quality_self_assessment(
            phase_id="1a",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        expected_path = tmp_path / "docs" / "pipeline" / "quality-self-assessment-1a.json"
        written = json.loads(expected_path.read_text(encoding="utf-8"))
        assert written["phase_id"] == result["phase_id"]
        assert written["timestamp"] == result["timestamp"]
        assert len(written["deliverables"]) == len(result["deliverables"])

    def test_works_for_phase_1b(self, tmp_path: Path) -> None:
        """Assessment generation works for phase 1b as well."""
        result = generate_quality_self_assessment(
            phase_id="1b",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        assert result["phase_id"] == "1b"
        expected_path = tmp_path / "docs" / "pipeline" / "quality-self-assessment-1b.json"
        assert expected_path.exists()

    def test_unknown_phase_returns_empty_deliverables(self, tmp_path: Path) -> None:
        """Unknown phase_id produces a result with empty deliverables (graceful)."""
        result = generate_quality_self_assessment(
            phase_id="99",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        assert result["phase_id"] == "99"
        assert result["deliverables"] == []

    def test_phase_3_deliverable_paths_match_executor(self, tmp_path: Path) -> None:
        """Phase 3 deliverables in self-assessment use the paths the executor actually writes.

        Regression guard for CONT-04: deliverable paths in the YAML contract must match
        what phase_3_executor.py and legal_gate.py produce on disk.
        """
        result = generate_quality_self_assessment(
            phase_id="3",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        assert len(result["deliverables"]) == 3, (
            f"Expected 3 Phase 3 deliverables, got {len(result['deliverables'])}: "
            f"{[d['path'] for d in result['deliverables']]}"
        )
        paths = {d["path"] for d in result["deliverables"]}
        expected_paths = {
            "docs/pipeline/deployment.json",
            "src/app/privacy/page.tsx",
            "src/app/terms/page.tsx",
        }
        assert paths == expected_paths, (
            f"Phase 3 deliverable paths do not match executor output.\n"
            f"  Expected: {expected_paths}\n"
            f"  Got:      {paths}"
        )

    def test_phase_3_no_old_legal_paths(self, tmp_path: Path) -> None:
        """Phase 3 assessment output does NOT contain old docs/pipeline/legal/ paths.

        Regression guard: prevents reversion to the pre-fix paths that caused
        quality self-assessment to always report legal deliverables as missing.
        """
        result = generate_quality_self_assessment(
            phase_id="3",
            project_dir=str(tmp_path),
            contract_path=str(CONTRACT_PATH),
        )
        for deliverable in result["deliverables"]:
            assert "docs/pipeline/legal/" not in deliverable["path"], (
                f"Old legal path found in Phase 3 deliverable: {deliverable['path']!r}. "
                "Contract must use src/app/privacy/page.tsx and src/app/terms/page.tsx."
            )
