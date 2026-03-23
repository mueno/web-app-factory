from __future__ import annotations

from pathlib import Path

import yaml

from web_app_factory._plan_generator import ExecutionPlan, PhasePlan, generate_plan

CONTRACT_PATH = Path(__file__).parent.parent / "contracts" / "pipeline-contract.web.v1.yaml"


def _load_contract() -> dict:
    with open(CONTRACT_PATH) as f:
        return yaml.safe_load(f)


def test_generate_plan_from_real_contract() -> None:
    contract = _load_contract()
    plan = generate_plan(contract, idea="A todo app", run_id="test-run-001")

    assert isinstance(plan, ExecutionPlan)
    assert plan.total_phases == 5
    phase_ids = [p.phase_id for p in plan.phases]
    assert phase_ids == ["1a", "1b", "2a", "2b", "3"]


def test_phase_names() -> None:
    contract = _load_contract()
    plan = generate_plan(contract, idea="A todo app", run_id="test-run-002")

    for phase in plan.phases:
        assert isinstance(phase.name, str)
        assert len(phase.name) > 0, f"Phase {phase.phase_id} has an empty name"


def test_deliverables_populated() -> None:
    contract = _load_contract()
    plan = generate_plan(contract, idea="A todo app", run_id="test-run-003")

    for phase in plan.phases:
        assert len(phase.deliverables) >= 1, (
            f"Phase {phase.phase_id} has no deliverables"
        )
        for d in phase.deliverables:
            assert isinstance(d, str)
            assert len(d) > 0


def test_complexity_light() -> None:
    """Phases with only artifact/tool_invocation gates should be 'light'."""
    contract = _load_contract()
    plan = generate_plan(contract, idea="A todo app", run_id="test-run-004")

    # Phases 1a and 1b only have artifact and tool_invocation gates
    phase_1a = next(p for p in plan.phases if p.phase_id == "1a")
    phase_1b = next(p for p in plan.phases if p.phase_id == "1b")

    assert phase_1a.complexity == "light", (
        f"Expected 'light', got '{phase_1a.complexity}'. Gates: {phase_1a.gate_types}"
    )
    assert phase_1b.complexity == "light", (
        f"Expected 'light', got '{phase_1b.complexity}'. Gates: {phase_1b.gate_types}"
    )


def test_complexity_medium() -> None:
    """Phases with build gates should be 'medium'."""
    contract = _load_contract()
    plan = generate_plan(contract, idea="A todo app", run_id="test-run-005")

    # Phase 2a has only a build gate
    phase_2a = next(p for p in plan.phases if p.phase_id == "2a")

    assert phase_2a.complexity == "medium", (
        f"Expected 'medium', got '{phase_2a.complexity}'. Gates: {phase_2a.gate_types}"
    )


def test_complexity_heavy() -> None:
    """Phases with deployment + lighthouse gates should be 'heavy'."""
    contract = _load_contract()
    plan = generate_plan(contract, idea="A todo app", run_id="test-run-006")

    # Phase 3 has lighthouse, accessibility, security_headers, link_integrity, and deployment gates
    phase_3 = next(p for p in plan.phases if p.phase_id == "3")

    assert phase_3.complexity == "heavy", (
        f"Expected 'heavy', got '{phase_3.complexity}'. Gates: {phase_3.gate_types}"
    )


def test_plan_metadata() -> None:
    contract = _load_contract()
    idea = "A recipe sharing app"
    run_id = "meta-test-run"
    deploy_target = "vercel"

    plan = generate_plan(contract, idea=idea, run_id=run_id, deploy_target=deploy_target)

    assert plan.run_id == run_id
    assert plan.idea == idea
    assert plan.deploy_target == deploy_target
    assert isinstance(plan.created_at, str)
    assert len(plan.created_at) > 0
    # created_at should be a valid ISO 8601 string
    assert "T" in plan.created_at
    assert "+" in plan.created_at or "Z" in plan.created_at or plan.created_at.endswith("+00:00")


def test_phases_are_frozen() -> None:
    """PhasePlan and ExecutionPlan should be immutable (frozen dataclasses)."""
    contract = _load_contract()
    plan = generate_plan(contract, idea="A todo app", run_id="frozen-test")

    # Attempting to modify should raise AttributeError
    import pytest

    with pytest.raises(AttributeError):
        plan.run_id = "modified"  # type: ignore[misc]

    phase = plan.phases[0]
    with pytest.raises(AttributeError):
        phase.phase_id = "modified"  # type: ignore[misc]


def test_empty_contract() -> None:
    """generate_plan should handle an empty contract gracefully."""
    plan = generate_plan({}, idea="empty", run_id="empty-run")

    assert plan.total_phases == 0
    assert plan.phases == ()


def test_phase_2b_gates() -> None:
    """Phase 2b should have build and static_analysis gates, making it medium."""
    contract = _load_contract()
    plan = generate_plan(contract, idea="A todo app", run_id="2b-test")

    phase_2b = next(p for p in plan.phases if p.phase_id == "2b")
    assert "build" in phase_2b.gate_types
    assert "static_analysis" in phase_2b.gate_types
    assert phase_2b.complexity == "medium"
