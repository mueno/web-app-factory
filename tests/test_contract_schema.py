"""Tests for pipeline contract YAML structure and JSON schema validation.

Tests verify:
1. YAML contract parses without error
2. Contract has exactly 5 phases with correct IDs
3. Every phase has required keys (purpose, deliverables, gates)
4. Every deliverable has required keys (name, path, quality_criteria)
5. Every quality_criteria has >= 1 item and is content-verifying (not existence-only)
6. JSON schema validation passes on the YAML contract
7. JSON schema validation rejects a contract missing required fields
8. JSON schema validation rejects a deliverable with empty quality_criteria
"""
import json
import pytest
import yaml
import jsonschema
from pathlib import Path

CONTRACT_PATH = Path(__file__).parent.parent / "contracts" / "pipeline-contract.web.v1.yaml"
SCHEMA_PATH = Path(__file__).parent.parent / "contracts" / "pipeline-contract.schema.json"

EXPECTED_PHASE_IDS = ["1a", "1b", "2a", "2b", "3"]

# Strings that indicate existence-only checks (not content verification)
EXISTENCE_ONLY_PATTERNS = [
    "file exists",
    "is present",
    "exists in",
    "file is created",
    "path exists",
]


@pytest.fixture(scope="module")
def contract():
    """Load and return the parsed YAML contract."""
    assert CONTRACT_PATH.exists(), f"Contract file not found: {CONTRACT_PATH}"
    with open(CONTRACT_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def schema():
    """Load and return the parsed JSON schema."""
    assert SCHEMA_PATH.exists(), f"Schema file not found: {SCHEMA_PATH}"
    with open(SCHEMA_PATH) as f:
        return json.load(f)


class TestContractParsing:
    def test_contract_file_parses_without_error(self):
        """YAML contract parses without raising an exception."""
        assert CONTRACT_PATH.exists(), f"Contract not found: {CONTRACT_PATH}"
        with open(CONTRACT_PATH) as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert isinstance(data, dict)

    def test_contract_has_exactly_five_phases(self, contract):
        """Contract contains exactly 5 phases."""
        phases = contract.get("phases", [])
        assert len(phases) == 5, f"Expected 5 phases, got {len(phases)}"

    def test_contract_phase_ids_match_expected(self, contract):
        """Phase IDs are exactly ['1a', '1b', '2a', '2b', '3'] in order."""
        phases = contract.get("phases", [])
        phase_ids = [p["id"] for p in phases]
        assert phase_ids == EXPECTED_PHASE_IDS, f"Phase IDs: {phase_ids}"

    def test_every_phase_has_required_keys(self, contract):
        """Every phase has id, name, purpose, deliverables, and gates."""
        required_keys = {"id", "name", "purpose", "deliverables", "gates"}
        for phase in contract.get("phases", []):
            missing = required_keys - set(phase.keys())
            assert not missing, f"Phase '{phase.get('id')}' missing keys: {missing}"

    def test_every_deliverable_has_required_keys(self, contract):
        """Every deliverable has name, path, and quality_criteria."""
        required_keys = {"name", "path", "quality_criteria"}
        for phase in contract.get("phases", []):
            for deliverable in phase.get("deliverables", []):
                missing = required_keys - set(deliverable.keys())
                assert not missing, (
                    f"Phase '{phase['id']}' deliverable '{deliverable.get('name')}' "
                    f"missing keys: {missing}"
                )

    def test_every_deliverable_has_at_least_one_quality_criterion(self, contract):
        """Every deliverable has at least 1 quality_criteria entry."""
        for phase in contract.get("phases", []):
            for deliverable in phase.get("deliverables", []):
                criteria = deliverable.get("quality_criteria", [])
                assert len(criteria) >= 1, (
                    f"Phase '{phase['id']}' deliverable '{deliverable.get('name')}' "
                    f"has no quality_criteria"
                )

    def test_quality_criteria_are_content_verifying(self, contract):
        """No quality_criteria string is a pure file-existence check.

        Must contain content-verifying language, not just existence checks.
        """
        for phase in contract.get("phases", []):
            for deliverable in phase.get("deliverables", []):
                for criterion in deliverable.get("quality_criteria", []):
                    criterion_lower = criterion.lower()
                    for pattern in EXISTENCE_ONLY_PATTERNS:
                        assert pattern not in criterion_lower, (
                            f"Phase '{phase['id']}' deliverable '{deliverable.get('name')}' "
                            f"has existence-only quality_criteria: '{criterion}'"
                        )

    def test_contract_has_top_level_metadata(self, contract):
        """Contract has version, schema, and metadata top-level fields."""
        assert "version" in contract, "Contract missing 'version'"
        assert "schema" in contract, "Contract missing 'schema'"
        assert contract["schema"] == "pipeline-contract", (
            f"Expected schema='pipeline-contract', got '{contract.get('schema')}'"
        )


class TestJsonSchemaValidation:
    def test_schema_validates_valid_contract(self, contract, schema):
        """JSON schema validation passes on the YAML contract."""
        jsonschema.validate(instance=contract, schema=schema)

    def test_schema_rejects_missing_phases(self, schema):
        """JSON schema rejects a contract with no 'phases' field."""
        bad_contract = {
            "version": "1",
            "schema": "pipeline-contract",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=bad_contract, schema=schema)

    def test_schema_rejects_phase_missing_purpose(self, schema):
        """JSON schema rejects a phase missing the 'purpose' field."""
        bad_contract = {
            "version": "1",
            "schema": "pipeline-contract",
            "phases": [
                {
                    "id": "1a",
                    "name": "Idea Validation",
                    # missing 'purpose'
                    "deliverables": [],
                    "gates": [],
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=bad_contract, schema=schema)

    def test_schema_rejects_deliverable_with_empty_quality_criteria(self, schema):
        """JSON schema rejects a deliverable with empty quality_criteria array."""
        bad_contract = {
            "version": "1",
            "schema": "pipeline-contract",
            "phases": [
                {
                    "id": "1a",
                    "name": "Idea Validation",
                    "purpose": "Market validation",
                    "deliverables": [
                        {
                            "name": "Idea Report",
                            "path": "docs/idea.md",
                            "quality_criteria": [],  # empty — should fail
                        }
                    ],
                    "gates": [{"type": "artifact", "description": "Files exist"}],
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=bad_contract, schema=schema)

    def test_schema_rejects_gate_missing_type(self, schema):
        """JSON schema rejects a gate missing the 'type' field."""
        bad_contract = {
            "version": "1",
            "schema": "pipeline-contract",
            "phases": [
                {
                    "id": "1a",
                    "name": "Idea Validation",
                    "purpose": "Market validation",
                    "deliverables": [
                        {
                            "name": "Idea Report",
                            "path": "docs/idea.md",
                            "quality_criteria": ["3+ named competitors analyzed"],
                        }
                    ],
                    "gates": [
                        {
                            # missing 'type'
                            "description": "Files exist",
                        }
                    ],
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=bad_contract, schema=schema)
