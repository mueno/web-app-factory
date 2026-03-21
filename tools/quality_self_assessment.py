# Copyright 2026 AllNew LLC. All rights reserved.
"""Quality self-assessment generator.

Reads quality_criteria from the pipeline contract YAML and generates a
structured JSON assessment template for a given phase.

Purpose (CONT-04, 45-quality-driven-execution.md):
  Gate-gaming prevention requires quality self-assessment to happen BEFORE
  gate submission. This module generates the initial "pending" assessment so
  the executor can fill in evidence before submitting to the gate.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def generate_quality_self_assessment(
    phase_id: str,
    project_dir: str,
    contract_path: str,
) -> dict[str, Any]:
    """Generate a quality self-assessment JSON for a pipeline phase.

    Reads quality_criteria from the YAML contract for the given phase_id
    and produces a JSON structure with all criteria marked 'pending'.
    Writes the JSON to {project_dir}/docs/pipeline/quality-self-assessment-{phase_id}.json.

    Args:
        phase_id: Pipeline phase identifier, e.g. "1a", "2b".
        project_dir: Root of the project being built (output directory).
        contract_path: Path to the pipeline contract YAML file.

    Returns:
        dict with keys: phase_id, timestamp, deliverables (list of
        {name, path, criteria: [{criterion, status, evidence}]}).
    """
    contract = _load_contract(contract_path)
    deliverables = _extract_deliverables(contract, phase_id)

    now = datetime.now(timezone.utc).isoformat()
    result: dict[str, Any] = {
        "phase_id": phase_id,
        "timestamp": now,
        "deliverables": deliverables,
    }

    _write_assessment(result, project_dir, phase_id)
    return result


# ── Internal helpers ──────────────────────────────────────────


def _load_contract(contract_path: str) -> dict[str, Any]:
    """Load and parse the YAML contract."""
    path = Path(contract_path)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _extract_deliverables(
    contract: dict[str, Any], phase_id: str
) -> list[dict[str, Any]]:
    """Extract deliverables and quality_criteria for the given phase_id.

    Returns an empty list if the phase is not found in the contract.
    """
    phases = contract.get("phases", [])
    for phase in phases:
        if phase.get("id") == phase_id:
            return _build_deliverable_list(phase.get("deliverables", []))
    return []


def _build_deliverable_list(
    deliverables: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the deliverables list with pending criteria from the contract."""
    result = []
    for deliverable in deliverables:
        criteria = [
            {
                "criterion": criterion_text,
                "status": "pending",
                "evidence": None,
            }
            for criterion_text in deliverable.get("quality_criteria", [])
        ]
        result.append(
            {
                "name": deliverable.get("name", ""),
                "path": deliverable.get("path", ""),
                "criteria": criteria,
            }
        )
    return result


def _write_assessment(
    assessment: dict[str, Any],
    project_dir: str,
    phase_id: str,
) -> None:
    """Write the assessment JSON to the expected path."""
    output_dir = Path(project_dir) / "docs" / "pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"quality-self-assessment-{phase_id}.json"
    output_path.write_text(
        json.dumps(assessment, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
