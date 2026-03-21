"""Error Router — classifies gate failures and routes to specialist agents.

A4: When a gate fails, instead of letting the orchestrator LLM self-fix
(which leads to bypass attempts), this module classifies the failure
and delegates to the appropriate specialist agent.

Design principle: Fail-closed + escalation. Gate failure → specialist → if
specialist can't fix → escalate to human (ANDON).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpecialistRecommendation:
    """Structured response from a specialist agent or error classification."""

    agent_name: str
    severity: str  # "critical" | "warning" | "info"
    root_cause: str
    recommended_actions: list[str]
    requires_human_approval: bool
    confidence: float  # 0.0-1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "severity": self.severity,
            "root_cause": self.root_cause,
            "recommended_actions": self.recommended_actions,
            "requires_human_approval": self.requires_human_approval,
            "confidence": self.confidence,
        }


# ── Failure Classification Rules ──

_FAILURE_PATTERNS: list[dict[str, Any]] = [
    {
        "gate_types": {"build"},
        "issue_patterns": ["next build", "Build failed", "build error", "compile error", "tsc error", "TypeScript"],
        "agent": "build-agent",
        "severity": "critical",
        "description": "Build failure — delegate to build specialist",
    },
    {
        "gate_types": {"test"},
        "issue_patterns": ["test failure", "jest", "vitest", "build output", "test evidence", "assertion failed"],
        "agent": "test-agent",
        "severity": "critical",
        "description": "Test failure — delegate to test specialist",
    },
    {
        "gate_types": {"legal", "legal_quality", "text_quality", "content_assertion"},
        "issue_patterns": ["legal", "privacy", "placeholder", "terms of service", "gdpr", "disclosure", "YOUR_APP_NAME"],
        "agent": "legal-agent",
        "severity": "warning",
        "description": "Legal/privacy docs issue — delegate to legal specialist",
    },
    {
        "gate_types": {"deployment", "lighthouse", "accessibility", "seo"},
        "issue_patterns": ["vercel", "deployment", "lighthouse", "performance score", "accessibility score", "link integrity"],
        "agent": "deploy-agent",
        "severity": "warning",
        "description": "Deployment or quality gate issue — delegate to deploy specialist",
    },
    {
        "gate_types": {"static_analysis"},
        "issue_patterns": ["use client", "NEXT_PUBLIC", "secret", "env variable", "boundary violation"],
        "agent": "build-agent",
        "severity": "critical",
        "description": "Static analysis violation — delegate to build specialist",
    },
    {
        "gate_types": {"security_headers"},
        "issue_patterns": ["security header", "X-Frame-Options", "Content-Security-Policy", "CSP", "CORS"],
        "agent": "deploy-agent",
        "severity": "critical",
        "description": "Missing security headers — delegate to deploy specialist",
    },
    {
        "gate_types": {"security"},
        "issue_patterns": ["security", "vulnerability", "SAST", "secrets", "dependency", "CVE"],
        "agent": "build-agent",
        "severity": "critical",
        "description": "Security baseline issue — delegate to build specialist",
    },
    {
        "gate_types": {"ux_ui", "ux_quality", "product_experience"},
        "issue_patterns": ["contrast", "tap target", "accessibility", "UX", "UI", "responsive", "mobile"],
        "agent": "build-agent",
        "severity": "warning",
        "description": "UX/UI quality issue — delegate to build specialist",
    },
]

# Actions that are NEVER acceptable from specialists
_FORBIDDEN_ACTIONS = frozenset({
    "disable gate",
    "skip gate",
    "remove gate",
    "bypass gate",
    "delete gate",
    "modify contract.yaml",
    "edit contract.yaml",
    "write to state.json",
    "edit state.json",
    "mark as passed",
    "force pass",
    "ignore failure",
})


def classify_failure(
    *,
    gate_types: list[str],
    issues: list[str],
) -> SpecialistRecommendation:
    """Classify a gate failure and return the recommended specialist agent.

    Args:
        gate_types: List of failed gate type strings.
        issues: List of issue description strings from the gate.

    Returns:
        SpecialistRecommendation with the best-matching agent.
    """
    gate_set = set(gate_types)
    issues_lower = " ".join(issues).lower()

    best_match: dict[str, Any] | None = None
    best_score = 0

    for pattern in _FAILURE_PATTERNS:
        score = 0

        # Gate type match
        if gate_set & pattern["gate_types"]:
            score += 10

        # Issue text pattern match
        for kw in pattern["issue_patterns"]:
            if kw.lower() in issues_lower:
                score += 2

        if score > best_score:
            best_score = score
            best_match = pattern

    if best_match is None:
        # Default: escalate to human
        return SpecialistRecommendation(
            agent_name="human-escalation",
            severity="critical",
            root_cause="Unclassified gate failure — no matching specialist",
            recommended_actions=[
                "Review gate failure details manually",
                "Determine root cause before retrying",
            ],
            requires_human_approval=True,
            confidence=0.0,
        )

    return SpecialistRecommendation(
        agent_name=best_match["agent"],
        severity=best_match["severity"],
        root_cause=best_match["description"],
        recommended_actions=[
            f"Delegate to {best_match['agent']} for diagnosis",
            "Review specialist recommendations before applying",
        ],
        requires_human_approval=best_match["severity"] == "critical",
        confidence=min(1.0, best_score / 14.0),  # Normalize: 14 = gate match + 2 keywords
    )


def validate_recommendation(
    recommendation: SpecialistRecommendation,
) -> tuple[bool, list[str]]:
    """Validate that a specialist recommendation doesn't bypass gates.

    Returns:
        (is_valid, list_of_violations)
    """
    violations: list[str] = []

    for action in recommendation.recommended_actions:
        action_lower = action.lower()
        for forbidden in _FORBIDDEN_ACTIONS:
            if forbidden in action_lower:
                violations.append(
                    f"Forbidden action detected: '{action}' matches "
                    f"forbidden pattern '{forbidden}'"
                )

    # Low confidence requires human approval
    if recommendation.confidence < 0.7 and not recommendation.requires_human_approval:
        violations.append(
            f"Low confidence ({recommendation.confidence:.2f}) recommendation "
            f"must require human approval"
        )

    return len(violations) == 0, violations


def should_escalate_to_human(recommendation: SpecialistRecommendation) -> bool:
    """Determine if the recommendation requires human intervention."""
    if recommendation.requires_human_approval:
        return True
    if recommendation.confidence < 0.7:
        return True
    if recommendation.severity == "critical":
        return True
    if recommendation.agent_name == "human-escalation":
        return True
    return False


@dataclass
class ErrorRouterState:
    """Tracks error routing decisions within a pipeline run."""

    classifications: list[dict[str, Any]] = field(default_factory=list)
    escalation_count: int = 0
    delegation_count: int = 0

    def record_classification(
        self,
        *,
        gate_types: list[str],
        issues: list[str],
        recommendation: SpecialistRecommendation,
        escalated: bool,
    ) -> None:
        self.classifications.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "gate_types": gate_types,
            "issues_count": len(issues),
            "agent": recommendation.agent_name,
            "severity": recommendation.severity,
            "confidence": recommendation.confidence,
            "escalated": escalated,
        })
        if escalated:
            self.escalation_count += 1
        else:
            self.delegation_count += 1

    def summary(self) -> dict[str, Any]:
        return {
            "total_classifications": len(self.classifications),
            "escalations": self.escalation_count,
            "delegations": self.delegation_count,
            "classifications": self.classifications,
        }
