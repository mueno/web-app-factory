"""Shared gate policy helpers.

Provides:
  - cross-gate result normalization (schema v2)
  - independent verification checks for high-risk gates
  - SPC-style quality event recording
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.gates.gate_result import GateResult

_GATE_RESULT_SCHEMA_VERSION = "gate-result.v2"
_QUALITY_SPC_SCHEMA_VERSION = "quality-spc.v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_issue_text(raw: Any) -> str:
    if isinstance(raw, str):
        text = raw.strip()
        if text:
            return text
    if isinstance(raw, dict):
        message = raw.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        code = raw.get("code")
        if isinstance(code, str) and code.strip():
            return code.strip()
        return json.dumps(raw, ensure_ascii=False, sort_keys=True)
    return str(raw).strip()


def _normalize_issues(raw_issues: Any) -> list:
    if not isinstance(raw_issues, list):
        return []
    normalized = []
    for issue in raw_issues:
        text = _safe_issue_text(issue)
        if text:
            normalized.append(text)
    return normalized


def _normalize_confidence(
    raw_confidence: Any,
    *,
    status: str,
    issues: list,
    advisories: list,
) -> float:
    if isinstance(raw_confidence, (int, float)):
        return max(0.0, min(1.0, float(raw_confidence)))

    score_map = {
        "PASS": 10.0,
        "PASS_WITH_ADVISORY": 9.0,
        "BLOCKED": 10.0,
        "SKIPPED": 8.0,
    }
    score = score_map.get(status, 8.0)
    if status == "BLOCKED":
        score += min(4.0, float(len(issues)))
    if advisories:
        score -= min(2.0, float(len(advisories)))
    return max(0.0, min(1.0, score / 14.0))


def _is_valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value.lower())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _has_role_evidence(
    phase_entry: dict,
    role: str,
    *,
    require_path_hash: bool,
) -> bool:
    role_key = role.strip()
    if not role_key:
        return False

    loaded_key = f"{role_key}_loaded"
    evidence_key = f"{role_key}_evidence"

    loaded = phase_entry.get(loaded_key, [])
    if isinstance(loaded, list) and any(str(item).strip() for item in loaded):
        if not require_path_hash:
            return True

    evidence_records = phase_entry.get(evidence_key, [])
    if not isinstance(evidence_records, list):
        return False

    for record in evidence_records:
        if not isinstance(record, dict):
            continue
        ref = record.get("ref")
        path = record.get("path")
        exists = record.get("exists")
        sha256 = record.get("sha256")
        if not isinstance(ref, str) or not ref.strip():
            continue
        if not isinstance(path, str) or not path.strip():
            continue
        if exists is not True:
            continue
        if require_path_hash and not _is_valid_sha256(sha256):
            continue
        return True
    return False


def _evaluate_independent_verification(
    *,
    project_dir: Path,
    phase_id: str,
    gate_type: str,
    checks: dict,
) -> dict:
    required = bool(checks.get("require_independent_verification", False))
    source = str(checks.get("independent_verification_source", "skill_evidence")).strip() or "skill_evidence"
    roles_raw = checks.get("independent_verifier_roles", ["auditor"])
    roles = [str(role).strip() for role in roles_raw if str(role).strip()]
    if not roles:
        roles = ["auditor"]
    require_path_hash = bool(checks.get("independent_verification_require_path_hash", True))
    path_rel = str(
        checks.get("independent_verification_path", "docs/pipeline/skill-evidence.json")
    ).strip() or "docs/pipeline/skill-evidence.json"

    result: dict = {
        "required": required,
        "source": source,
        "roles": roles,
        "path": path_rel,
        "passed": True,
        "details": [],
    }
    if not required:
        return result

    if source != "skill_evidence":
        result["passed"] = False
        result["details"] = [f"unsupported independent verification source: {source}"]
        return result

    evidence_path = project_dir / path_rel
    if not evidence_path.exists():
        result["passed"] = False
        result["details"] = [f"independent verification file missing: {path_rel}"]
        return result

    try:
        evidence = _read_json(evidence_path)
    except Exception as exc:  # noqa: BLE001
        result["passed"] = False
        result["details"] = [f"independent verification JSON parse failed: {exc}"]
        return result

    phases = evidence.get("phases", {}) if isinstance(evidence, dict) else {}
    phase_entry = phases.get(phase_id, {}) if isinstance(phases, dict) else {}
    if not isinstance(phase_entry, dict):
        phase_entry = {}

    missing_roles = []
    for role in roles:
        if not _has_role_evidence(
            phase_entry,
            role,
            require_path_hash=require_path_hash,
        ):
            missing_roles.append(role)

    if missing_roles:
        result["passed"] = False
        result["details"] = [
            "missing independent verifier evidence for role(s): " + ", ".join(sorted(set(missing_roles))),
            f"phase={phase_id}",
            f"gate={gate_type}",
        ]
    return result


def _default_containment_policy(
    *,
    gate_type: str,
    phase_id: str,
    checks: dict,
    passed: bool,
    has_advisories: bool = False,
) -> dict:
    default_sla = 4 if gate_type in {"legal_quality", "content_assertion", "security", "asc_live"} else 24
    owner = str(checks.get("containment_owner", "web-factory-operator")).strip() or "web-factory-operator"
    try:
        sla_hours = int(checks.get("containment_sla_hours", default_sla))
    except (TypeError, ValueError):
        sla_hours = default_sla
    rollback = str(
        checks.get(
            "containment_rollback_recipe",
            f"Re-run phase {phase_id} after fixing failing evidence artifacts",
        )
    ).strip()
    if not rollback:
        rollback = f"Re-run phase {phase_id} after fixing failing evidence artifacts"
    escalation = str(
        checks.get(
            "containment_escalation",
            "Run /tps-kaizen five-whys and generate autorework fix proposal",
        )
    ).strip()
    if not escalation:
        escalation = "Run /tps-kaizen five-whys and generate autorework fix proposal"
    return {
        "owner": owner,
        "sla_hours": max(sla_hours, 1),
        "rollback_recipe": rollback,
        "escalation": escalation,
        "next_action": (
            "proceed_with_advisory"
            if passed and has_advisories
            else "proceed" if passed else "block-and-rework"
        ),
    }


def normalize_gate_result(
    *,
    result: dict,
    gate_type: str,
    phase_id: str,
    project_dir: Path,
    checks: dict | None = None,
) -> GateResult:
    """Normalize gate result into shared schema v2.

    Returns a GateResult dataclass instance.  Dict-style access
    (result['passed'], result.get('details')) is supported via the
    backward-compatible bridge on GateResult.
    """
    checks = checks or {}
    normalized = dict(result)

    issues = _normalize_issues(normalized.get("issues", []))
    advisories = _normalize_issues(normalized.get("advisories", []))
    raw_passed = bool(normalized.get("passed", False))
    raw_skipped = bool(normalized.get("skipped", False))
    raw_skip_allowed = bool(normalized.get("skip_allowed", False))
    effective_skipped = raw_skipped and raw_skip_allowed
    invalid_skip = raw_skipped and not raw_skip_allowed

    independent: dict
    if effective_skipped:
        independent = {
            "required": False,
            "source": "skipped",
            "roles": [],
            "path": "",
            "passed": True,
            "details": [],
        }
    else:
        independent = _evaluate_independent_verification(
            project_dir=project_dir,
            phase_id=phase_id,
            gate_type=gate_type,
            checks=checks,
        )
        if independent.get("required") and not independent.get("passed"):
            details = independent.get("details", [])
            if isinstance(details, list):
                for item in details:
                    text = _safe_issue_text(item)
                    if text:
                        issues.append(f"independent_verification: {text}")
            else:
                issues.append("independent_verification: verification failed")
    if invalid_skip:
        issues.append("gate returned skipped without explicit skip allowance")

    passed = raw_passed and not issues
    if effective_skipped:
        passed = True
    status = (
        "SKIPPED"
        if effective_skipped
        else "PASS_WITH_ADVISORY" if passed and advisories
        else "PASS" if passed else "BLOCKED"
    )
    severity = "INFO" if (passed or effective_skipped) else "BLOCK"
    confidence = _normalize_confidence(
        normalized.get("confidence"),
        status=status,
        issues=issues,
        advisories=advisories,
    )
    containment = _default_containment_policy(
        gate_type=gate_type,
        phase_id=phase_id,
        checks=checks,
        passed=passed or effective_skipped,
        has_advisories=bool(advisories),
    )

    issue_records = []
    if not effective_skipped:
        issue_records = [
            {
                "code": "GATE_ISSUE",
                "severity": "BLOCK",
                "message": issue,
            }
            for issue in issues
        ]
    advisory_records = [
        {
            "code": "GATE_ADVISORY",
            "severity": "ADVISORY",
            "message": advisory,
        }
        for advisory in advisories
    ]

    checked_at = normalized.get("checked_at")
    if not isinstance(checked_at, str) or not checked_at.strip():
        checked_at = _now_iso()

    # Separate gate-specific extra fields from known GateResult fields.
    # The original ``normalized = dict(result)`` preserves all raw gate output
    # (evidence, winner, winner_score, note, etc.).  Known schema v2 keys are
    # promoted to typed fields; everything else goes into ``extra``.
    from tools.gates.gate_result import _KNOWN_FIELDS

    extra: dict = {}
    for key, value in normalized.items():
        if key not in _KNOWN_FIELDS:
            extra[key] = value

    return GateResult(
        schema_version=_GATE_RESULT_SCHEMA_VERSION,
        gate_type=gate_type,
        phase_id=phase_id,
        passed=passed,
        skipped=raw_skipped,
        skip_allowed=raw_skip_allowed,
        status=status,
        severity=severity,
        confidence=confidence,
        checked_at=checked_at,
        issues=issues,
        advisories=advisories,
        issue_records=issue_records,
        advisory_records=advisory_records,
        independent_verification=independent,
        containment_policy=containment,
        extra=extra,
    )


def record_quality_spc_event(
    *,
    project_dir: Path,
    run_id: str,
    phase_id: str,
    gate_result: dict,
    rolling_window: int = 20,
) -> str | None:
    """Append SPC event and refresh summary.

    Returns None on success, error message on failure.
    """
    try:
        docs_dir = project_dir / "docs" / "pipeline"
        docs_dir.mkdir(parents=True, exist_ok=True)
        events_path = docs_dir / "quality-spc-events.jsonl"
        summary_path = docs_dir / "quality-spc.json"

        gate_type = str(gate_result.get("gate_type") or "").strip() or "unknown"
        status = str(gate_result.get("status") or "").strip() or ("PASS" if gate_result.get("passed", False) else "BLOCKED")
        severity = str(gate_result.get("severity") or "").strip() or ("INFO" if gate_result.get("passed", False) else "BLOCK")
        issues = _normalize_issues(gate_result.get("issues", []))
        advisories = _normalize_issues(gate_result.get("advisories", []))
        iv = gate_result.get("independent_verification", {})
        if not isinstance(iv, dict):
            iv = {}

        event = {
            "schema_version": _QUALITY_SPC_SCHEMA_VERSION,
            "recorded_at": _now_iso(),
            "run_id": run_id,
            "phase_id": phase_id,
            "gate_type": gate_type,
            "status": status,
            "severity": severity,
            "passed": bool(gate_result.get("passed", False)),
            "issues_count": len(issues),
            "advisory_count": len(advisories),
            "independent_verification_required": bool(iv.get("required", False)),
            "independent_verification_passed": bool(iv.get("passed", True)),
        }
        with events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

        events = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(payload, dict):
                events.append(payload)

        by_gate: dict = {}
        for item in events:
            gate = str(item.get("gate_type") or "").strip() or "unknown"
            bucket = by_gate.setdefault(
                gate,
                {
                    "total": 0,
                    "pass": 0,
                    "fail": 0,
                    "advisory": 0,
                    "last_status": "",
                    "last_recorded_at": "",
                    "last_run_id": "",
                },
            )
            bucket["total"] += 1
            if bool(item.get("passed", False)):
                bucket["pass"] += 1
            else:
                bucket["fail"] += 1
            bucket["advisory"] += int(item.get("advisory_count", 0) or 0)
            bucket["last_status"] = str(item.get("status") or "")
            bucket["last_recorded_at"] = str(item.get("recorded_at") or "")
            bucket["last_run_id"] = str(item.get("run_id") or "")

        for gate, bucket in by_gate.items():
            total = int(bucket["total"])
            passed_count = int(bucket["pass"])
            gate_events = [evt for evt in events if str(evt.get("gate_type") or "").strip() == gate]
            rolling_events = gate_events[-rolling_window:] if rolling_window > 0 else gate_events
            rolling_total = len(rolling_events)
            rolling_pass = sum(1 for evt in rolling_events if bool(evt.get("passed", False)))
            bucket["pass_rate"] = round((passed_count / total) if total else 0.0, 4)
            bucket["rolling_window"] = rolling_window
            bucket["rolling_pass_rate"] = round((rolling_pass / rolling_total) if rolling_total else 0.0, 4)

        summary = {
            "schema_version": _QUALITY_SPC_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "events_path": str(events_path),
            "total_events": len(events),
            "by_gate": by_gate,
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return None
    except Exception as exc:  # noqa: BLE001
        return f"quality-spc recording failed: {exc}"
