"""Legal quality gate executor.

Validates that legal documents (Privacy Policy and Terms of Service) exist
in the generated Next.js project, are free of template placeholders, and
reference at least one app-specific feature from the PRD.

Exported function: run_legal_gate
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from tools.gates.gate_result import GateResult


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Legal pages that must exist in the project
LEGAL_FILES = [
    "src/app/privacy/page.tsx",
    "src/app/terms/page.tsx",
]

# Placeholder patterns that must NOT appear in legal documents
PLACEHOLDER_PATTERNS = [
    r"YOUR_APP_NAME",
    r"YOUR_COMPANY",
    r"\[COMPANY\]",
    r"\[DATE\]",
    r"\[APP_NAME\]",
    r"YOUR_EMAIL",
]

# PRD path relative to project_dir
_PRD_PATH = Path("docs") / "pipeline" / "prd.md"


def _extract_feature_names(prd_content: str) -> list[str]:
    """Extract feature names from PRD's ## Features section.

    Looks for **BoldName** patterns in lines within the features section.
    Returns a list of feature name strings.
    """
    features: list[str] = []
    # Find all bold names anywhere in the PRD (## Component Inventory pattern)
    bold_pattern = re.compile(r"\*\*([^*]+)\*\*")
    for match in bold_pattern.finditer(prd_content):
        name = match.group(1).strip()
        # Skip short names that are likely formatting, not features
        if len(name) >= 3:
            features.append(name)
    return features


def run_legal_gate(
    project_dir: str,
    phase_id: str = "3",
) -> GateResult:
    """Run legal quality gate against the generated project.

    Checks:
    1. Both legal page files exist (privacy/page.tsx, terms/page.tsx)
    2. No template placeholder strings appear in any legal file
    3. At least one app-specific feature name from docs/pipeline/prd.md
       appears in the legal files (advisory if not found)

    Args:
        project_dir: Root directory of the generated Next.js project.
        phase_id: Pipeline phase identifier (default "3" — ship phase).

    Returns:
        GateResult with gate_type="legal".
        - passed=False if any required file is missing or any placeholder is found.
        - passed=True with advisory if feature names not referenced (advisory only).
        - passed=True with no issues/advisories if all checks pass.
    """
    checked_at = _now_iso()
    project_path = Path(project_dir)

    issues: list[str] = []
    advisories: list[str] = []

    # ── Check 1: Legal files must exist ────────────────────────────────────
    existing_files: list[Path] = []
    for rel_path in LEGAL_FILES:
        full_path = project_path / rel_path
        if not full_path.exists():
            page_type = "privacy" if "privacy" in rel_path else "terms"
            issues.append(
                f"Missing legal file: {rel_path} "
                f"({page_type.capitalize()} page not found)"
            )
        else:
            existing_files.append(full_path)

    # ── Check 2: No placeholder patterns in existing legal files ───────────
    placeholder_re = re.compile("|".join(PLACEHOLDER_PATTERNS))

    for file_path in existing_files:
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(
                f"Failed to read {file_path.relative_to(project_path)}: "
                f"{type(exc).__name__}"
            )
            continue

        matches = placeholder_re.findall(content)
        if matches:
            unique_matches = sorted(set(matches))
            issues.append(
                f"Placeholder text found in {file_path.relative_to(project_path)}: "
                f"{', '.join(unique_matches)}"
            )

    # ── Check 3: Feature reference check (advisory) ────────────────────────
    prd_path = project_path / _PRD_PATH
    if prd_path.exists() and existing_files:
        try:
            prd_content = prd_path.read_text(encoding="utf-8")
            feature_names = _extract_feature_names(prd_content)

            if feature_names:
                # Combine legal file contents for search
                combined_legal = ""
                for file_path in existing_files:
                    try:
                        combined_legal += file_path.read_text(encoding="utf-8") + "\n"
                    except OSError:
                        pass

                # Check if at least one feature name appears in legal docs
                feature_found = any(
                    feature.lower() in combined_legal.lower()
                    for feature in feature_names
                )

                if not feature_found:
                    advisories.append(
                        "No app-specific feature names from the PRD were referenced in "
                        "legal documents. Consider referencing actual app features "
                        f"(e.g., {feature_names[0]!r}) for better legal specificity."
                    )
        except OSError:
            pass  # PRD read failure is non-fatal for this advisory check

    passed = len(issues) == 0

    return GateResult(
        gate_type="legal",
        phase_id=phase_id,
        passed=passed,
        status="PASS" if passed else "BLOCKED",
        severity="INFO" if passed else "BLOCK",
        confidence=1.0 if passed else 0.0,
        checked_at=checked_at,
        issues=issues,
        advisories=advisories,
    )
