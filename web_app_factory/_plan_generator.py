from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# Gate types that indicate higher complexity
_HEAVY_GATES = frozenset(
    {"deployment", "lighthouse", "accessibility", "security_headers", "link_integrity", "mcp_approval"}
)
_MEDIUM_GATES = frozenset({"build", "static_analysis"})


@dataclass(frozen=True)
class PhasePlan:
    phase_id: str
    name: str
    purpose: str
    deliverables: list[str]  # deliverable names
    gate_types: list[str]  # gate type strings
    complexity: str  # "light" | "medium" | "heavy"


@dataclass(frozen=True)
class ExecutionPlan:
    run_id: str
    idea: str
    deploy_target: str
    phases: tuple[PhasePlan, ...]  # tuple for frozen
    total_phases: int
    created_at: str


def _assess_complexity(gate_types: list[str]) -> str:
    """Determine phase complexity from its gate types."""
    gate_set = set(gate_types)
    if gate_set & _HEAVY_GATES:
        return "heavy"
    if gate_set & _MEDIUM_GATES:
        return "medium"
    return "light"


def generate_plan(
    contract: dict[str, Any],
    idea: str,
    run_id: str,
    deploy_target: str = "vercel",
) -> ExecutionPlan:
    """Generate an execution plan from the pipeline contract.

    Reads the contract phases, extracts deliverables and gates,
    and produces a structured plan showing what will happen.
    """
    phases = []
    for phase_def in contract.get("phases", []):
        phase_id = phase_def.get("id", "unknown")
        name = phase_def.get("name", f"Phase {phase_id}")
        purpose = phase_def.get("purpose", "")

        deliverables = [
            d.get("name", d.get("path", "unnamed"))
            for d in phase_def.get("deliverables", [])
        ]

        gate_types = [
            g.get("type", "unknown")
            for g in phase_def.get("gates", [])
        ]

        complexity = _assess_complexity(gate_types)

        phases.append(
            PhasePlan(
                phase_id=phase_id,
                name=name,
                purpose=purpose,
                deliverables=deliverables,
                gate_types=gate_types,
                complexity=complexity,
            )
        )

    return ExecutionPlan(
        run_id=run_id,
        idea=idea,
        deploy_target=deploy_target,
        phases=tuple(phases),
        total_phases=len(phases),
        created_at=datetime.now(tz=timezone.utc).isoformat(),
    )
