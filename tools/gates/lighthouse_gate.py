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

_LIGHTHOUSE_CATEGORIES = ["performance", "accessibility", "seo"]


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
                issues.append(
                    f"Lighthouse {category} score {score_pct:.1f} is below threshold {threshold}"
                )

        passed = len(issues) == 0

        return GateResult(
            gate_type="lighthouse",
            phase_id=phase_id,
            passed=passed,
            status="PASS" if passed else "BLOCKED",
            severity="INFO" if passed else "BLOCK",
            confidence=1.0 if passed else 0.0,
            checked_at=checked_at,
            issues=issues,
            extra={"scores": scores},
        )

    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
