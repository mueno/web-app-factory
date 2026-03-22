"""Lighthouse gate executor.

Runs npx lighthouse against a deployed URL, parses JSON scores for
performance, accessibility, and SEO categories, and compares them
against configurable thresholds.

Exported function: run_lighthouse_gate
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import os
from datetime import datetime, timezone
from typing import Optional

from tools.gates.gate_result import GateResult


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_DEFAULT_THRESHOLDS: dict = {"performance": 85, "accessibility": 90, "seo": 85}

# Tolerance (points) to absorb normal Lighthouse variability (±2-3 between runs).
# A score within tolerance triggers an advisory instead of a hard BLOCK.
_SCORE_TOLERANCE: float = 2.0

_LIGHTHOUSE_CATEGORIES = ["performance", "accessibility", "seo"]

# Maximum number of failing audits to include in diagnostics
_MAX_DIAGNOSTICS = 8


def _extract_failing_audits(lh_data: dict) -> list[dict]:
    """Extract top failing audits from Lighthouse JSON for actionable fix guidance.

    Returns a list of dicts with keys: id, title, score, displayValue, description.
    Only includes audits with score < 1.0 (not perfect), sorted by score ascending
    (worst first). Capped at _MAX_DIAGNOSTICS entries.
    """
    audits = lh_data.get("audits", {})
    failing: list[dict] = []

    for audit_id, audit_data in audits.items():
        if not isinstance(audit_data, dict):
            continue
        score = audit_data.get("score")
        # Skip informational audits (score=None) and perfect audits (score=1.0)
        if score is None or score >= 1.0:
            continue
        # Skip audits that are not actionable (e.g. metrics, not opportunities)
        score_display_mode = audit_data.get("scoreDisplayMode", "")
        if score_display_mode in ("notApplicable", "manual", "informative"):
            continue

        failing.append({
            "id": audit_id,
            "title": audit_data.get("title", audit_id),
            "score": score,
            "displayValue": audit_data.get("displayValue", ""),
            "description": (audit_data.get("description") or "")[:200],
        })

    # Sort by score ascending (worst audits first)
    failing.sort(key=lambda a: (a["score"], a["id"]))
    return failing[:_MAX_DIAGNOSTICS]


def run_lighthouse_gate(
    url: str,
    thresholds: Optional[dict] = None,
    phase_id: str = "3",
) -> GateResult:
    """Run Lighthouse gate against a deployed URL.

    Invokes npx lighthouse with --runs=3 to obtain median scores,
    parses the JSON output, and compares each category score to its
    configured threshold.

    Args:
        url: Full URL of the deployed application (e.g. https://myapp.vercel.app).
        thresholds: Dict of category -> minimum score (0-100). Defaults to
            {"performance": 85, "accessibility": 90, "seo": 85}.
        phase_id: Pipeline phase identifier (default "3").

    Returns:
        GateResult with gate_type="lighthouse". passed=True only when all
        category scores meet or exceed their thresholds.
        extra["scores"] contains the actual scores as percentages.
    """
    checked_at = _now_iso()
    effective_thresholds = dict(_DEFAULT_THRESHOLDS)
    if thresholds is not None:
        effective_thresholds.update(thresholds)

    # Write JSON to a temp file; lighthouse writes to --output-path
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json")
    os.close(tmp_fd)

    try:
        cmd = [
            "npx",
            "lighthouse",
            url,
            "--output=json",
            f"--output-path={tmp_path}",
            "--chrome-flags=--headless --no-sandbox",
            "--only-categories=performance,accessibility,seo",
            "--quiet",
            "--runs=3",
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            return GateResult(
                gate_type="lighthouse",
                phase_id=phase_id,
                passed=False,
                status="BLOCKED",
                severity="BLOCK",
                confidence=0.0,
                checked_at=checked_at,
                issues=["Lighthouse timeout after 180 seconds"],
            )

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            error_msg = stderr if stderr else f"Lighthouse exited with code {proc.returncode}"
            return GateResult(
                gate_type="lighthouse",
                phase_id=phase_id,
                passed=False,
                status="BLOCKED",
                severity="BLOCK",
                confidence=0.0,
                checked_at=checked_at,
                issues=[error_msg],
            )

        # Parse the JSON output file
        try:
            with open(tmp_path, "r") as f:
                lh_data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            return GateResult(
                gate_type="lighthouse",
                phase_id=phase_id,
                passed=False,
                status="BLOCKED",
                severity="BLOCK",
                confidence=0.0,
                checked_at=checked_at,
                issues=[f"Failed to parse Lighthouse JSON output: {exc}"],
            )

        categories = lh_data.get("categories", {})
        scores: dict = {}
        issues: list = []
        advisories: list = []

        for category in _LIGHTHOUSE_CATEGORIES:
            cat_data = categories.get(category, {})
            raw_score = cat_data.get("score")
            if raw_score is None:
                issues.append(f"Lighthouse did not return a score for '{category}'")
                scores[category] = 0.0
                continue

            score_pct = raw_score * 100
            scores[category] = score_pct
            threshold = effective_thresholds.get(category, 0)

            if score_pct < threshold:
                gap = threshold - score_pct
                if gap <= _SCORE_TOLERANCE:
                    # Within tolerance — advisory, not a hard block
                    advisories.append(
                        f"Lighthouse {category} score {score_pct:.1f} is within "
                        f"tolerance of threshold {threshold} (gap {gap:.1f})"
                    )
                else:
                    issues.append(
                        f"Lighthouse {category} score {score_pct:.1f} is below threshold {threshold}"
                    )

        # Extract top failing audits for actionable diagnostics
        diagnostics = _extract_failing_audits(lh_data)

        passed = len(issues) == 0

        return GateResult(
            gate_type="lighthouse",
            phase_id=phase_id,
            passed=passed,
            status="PASS" if passed else "BLOCKED",
            severity="INFO" if passed else "BLOCK",
            confidence=1.0 if passed else max(0.0, 1.0 - sum(
                (threshold - scores.get(c, 0)) / 100
                for c in _LIGHTHOUSE_CATEGORIES
                if scores.get(c, 0) < effective_thresholds.get(c, 0)
            )),
            checked_at=checked_at,
            issues=issues,
            advisories=advisories,
            extra={
                "scores": scores,
                "tolerance": _SCORE_TOLERANCE,
                "diagnostics": diagnostics,
            },
        )

    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
