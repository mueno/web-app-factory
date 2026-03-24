"""Legal compliance gate executor.

Validates that legal documents (Privacy Policy and Terms of Service) in the
generated Next.js project meet disclosure completeness standards, not just
existence. Upgraded from existence-only check per Codex audit finding L-1.

Checks (in order of severity):
  1. BLOCK: Required legal files must exist
  2. BLOCK: No template placeholder strings
  3. BLOCK: Privacy policy must contain required disclosure sections
  4. BLOCK: Terms of service must contain required sections
  5. BLOCK: Contact information must be present and non-placeholder
  6. BLOCK (conditional): Data retention must be mentioned when PRD indicates user data collection
  7. BLOCK (conditional): Third-party services must be disclosed when PRD explicitly references them
  8. ADVISORY: App-specific features from PRD should be referenced

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
    r"\[EMAIL\]",
    r"\[CONTACT\]",
    r"\[INSERT",
    r"TODO:",
    r"FIXME:",
]

# Required disclosure sections in privacy policy (case-insensitive heading search)
_PRIVACY_REQUIRED_SECTIONS = [
    (r"(?:data|information)\s+(?:we\s+)?collect", "Data Collection"),
    (r"(?:how\s+we\s+)?use\s+(?:your\s+)?(?:data|information)", "Data Usage"),
    (r"(?:third[- ]part|share|disclos)", "Third-Party Sharing / Disclosure"),
    (r"(?:contact|reach|inquir)", "Contact Information"),
]

# Required sections in terms of service (case-insensitive heading search)
_TERMS_REQUIRED_SECTIONS = [
    (r"(?:accept|agree|consent)", "Acceptance / Agreement"),
    (r"(?:limit|disclaim|liabil|warrant)", "Limitation of Liability / Disclaimer"),
    (r"(?:contact|reach|inquir)", "Contact Information"),
]

# Patterns indicating a real email address (not placeholder)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Common third-party services that should be disclosed if used
_THIRD_PARTY_KEYWORDS = {
    "vercel": "Vercel (hosting/deployment)",
    "google analytics": "Google Analytics",
    "firebase": "Firebase",
    "stripe": "Stripe (payments)",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "sentry": "Sentry (error tracking)",
    "cloudflare": "Cloudflare",
    "supabase": "Supabase",
}

# PRD path relative to project_dir
_PRD_PATH = Path("docs") / "pipeline" / "prd.md"

# Patterns in PRD that indicate the app collects user data (triggers retention BLOCK)
_DATA_COLLECTION_INDICATORS = re.compile(
    r"(?:user\s+data|sign[- ]?up|log[- ]?in|account|profile|form\s+submission"
    r"|collect|store|database|auth|registration|personal\s+info)",
    re.IGNORECASE,
)


def _extract_feature_names(prd_content: str) -> list[str]:
    """Extract feature names from PRD's bold-name patterns."""
    features: list[str] = []
    bold_pattern = re.compile(r"\*\*([^*]+)\*\*")
    for match in bold_pattern.finditer(prd_content):
        name = match.group(1).strip()
        if len(name) >= 3:
            features.append(name)
    return features


def _check_required_sections(
    content: str,
    section_patterns: list[tuple[str, str]],
    doc_type: str,
) -> list[str]:
    """Check that required disclosure sections exist in a legal document.

    Returns list of issue strings for missing sections.
    """
    issues = []
    content_lower = content.lower()
    for pattern, section_name in section_patterns:
        if not re.search(pattern, content_lower):
            issues.append(
                f"{doc_type}: missing required section — {section_name}. "
                f"Legal documents must address this topic for compliance."
            )
    return issues


def _check_contact_info(content: str, doc_type: str) -> list[str]:
    """Verify document contains a real contact email (not placeholder)."""
    emails = _EMAIL_RE.findall(content)
    if not emails:
        return [
            f"{doc_type}: no contact email address found. "
            f"Legal documents must include a valid contact email."
        ]
    # Check if the email looks like a placeholder
    placeholder_domains = {"example.com", "example.org", "test.com", "placeholder.com"}
    real_emails = [e for e in emails if e.split("@")[1].lower() not in placeholder_domains]
    if not real_emails:
        return [
            f"{doc_type}: only placeholder email addresses found ({', '.join(emails)}). "
            f"Replace with a real contact email."
        ]
    return []


def _check_third_party_disclosure(
    legal_content: str,
    prd_content: str,
) -> tuple[list[str], list[str]]:
    """Check if third-party services mentioned in PRD are disclosed in legal docs.

    Returns (blocking_issues, advisories).
    Services explicitly named in the PRD are BLOCK-level; fuzzy matches are advisory.
    """
    issues = []
    legal_lower = legal_content.lower()
    prd_lower = prd_content.lower()

    for keyword, service_name in _THIRD_PARTY_KEYWORDS.items():
        if keyword in prd_lower and keyword not in legal_lower:
            issues.append(
                f"Third-party service '{service_name}' is referenced in PRD but not "
                f"disclosed in legal documents. Privacy policy must disclose data "
                f"shared with third-party services."
            )
    return issues, []


def _check_retention(content: str, prd_content: str | None = None) -> tuple[list[str], list[str]]:
    """Check if privacy policy mentions data retention/deletion.

    Returns (blocking_issues, advisories).
    BLOCK when the PRD indicates user data collection; advisory otherwise.
    """
    retention_patterns = [
        r"retain",
        r"retention",
        r"delet(?:e|ion)",
        r"(?:how\s+long|period|duration)",
        r"remov(?:e|al)",
    ]
    content_lower = content.lower()
    for pattern in retention_patterns:
        if re.search(pattern, content_lower):
            return [], []

    msg = (
        "Privacy Policy: no mention of data retention or deletion policy. "
        "Must specify how long user data is retained and how users can "
        "request deletion."
    )

    # Conditional: BLOCK if PRD indicates data collection, advisory otherwise
    if prd_content and _DATA_COLLECTION_INDICATORS.search(prd_content):
        return [msg], []
    return [], [msg]


def run_legal_gate(
    project_dir: str,
    phase_id: str = "3",
    prd_dir: str | None = None,
) -> GateResult:
    """Run legal compliance gate against the generated project.

    Checks (upgraded from existence-only to completeness):
    1. Both legal page files exist (privacy/page.tsx, terms/page.tsx)
    2. No template placeholder strings appear in any legal file
    3. Privacy policy contains required disclosure sections
    4. Terms of service contains required sections
    5. Real contact information is present (not placeholder emails)
    6. Data retention is mentioned (BLOCK if PRD indicates data collection)
    7. Third-party services from PRD are disclosed (BLOCK if PRD references them)
    8. At least one app-specific feature from PRD is referenced (advisory)

    Args:
        project_dir: Root directory of the generated Next.js project.
        phase_id: Pipeline phase identifier (default "3" — ship phase).
        prd_dir: Directory containing docs/pipeline/prd.md.

    Returns:
        GateResult with gate_type="legal".
    """
    checked_at = _now_iso()
    project_path = Path(project_dir)

    issues: list[str] = []
    advisories: list[str] = []

    # ── Check 1: Legal files must exist ──────────────────────────────────
    file_contents: dict[str, str] = {}  # rel_path -> content
    for rel_path in LEGAL_FILES:
        full_path = project_path / rel_path
        if not full_path.exists():
            page_type = "privacy" if "privacy" in rel_path else "terms"
            issues.append(
                f"Missing legal file: {rel_path} "
                f"({page_type.capitalize()} page not found)"
            )
        else:
            try:
                file_contents[rel_path] = full_path.read_text(encoding="utf-8")
            except OSError as exc:
                issues.append(
                    f"Failed to read {rel_path}: {type(exc).__name__}"
                )

    # ── Check 2: No placeholder patterns ─────────────────────────────────
    placeholder_re = re.compile("|".join(PLACEHOLDER_PATTERNS), re.IGNORECASE)

    for rel_path, content in file_contents.items():
        matches = placeholder_re.findall(content)
        if matches:
            unique_matches = sorted(set(matches))
            issues.append(
                f"Placeholder text found in {rel_path}: "
                f"{', '.join(unique_matches)}"
            )

    # ── Check 3: Privacy disclosure completeness ─────────────────────────
    privacy_content = ""
    for rel_path, content in file_contents.items():
        if "privacy" in rel_path:
            privacy_content = content
            issues.extend(
                _check_required_sections(content, _PRIVACY_REQUIRED_SECTIONS, "Privacy Policy")
            )
            # Check 5a: contact info in privacy
            issues.extend(_check_contact_info(content, "Privacy Policy"))
            # Check 6: retention (BLOCK if PRD indicates data collection)
            # prd_content loaded later; defer retention check

    # ── Check 4: Terms completeness ──────────────────────────────────────
    terms_content = ""
    for rel_path, content in file_contents.items():
        if "terms" in rel_path:
            terms_content = content
            issues.extend(
                _check_required_sections(content, _TERMS_REQUIRED_SECTIONS, "Terms of Service")
            )
            # Check 5b: contact info in terms
            issues.extend(_check_contact_info(content, "Terms of Service"))

    # ── Check 6, 7, 8: PRD-based checks ─────────────────────────────────
    prd_base = Path(prd_dir) if prd_dir else project_path
    prd_path = prd_base / _PRD_PATH
    prd_content: str | None = None
    if prd_path.exists() and file_contents:
        try:
            prd_content = prd_path.read_text(encoding="utf-8")
            combined_legal = privacy_content + "\n" + terms_content

            # Check 7: third-party disclosure (BLOCK if PRD references services)
            tp_issues, tp_advisories = _check_third_party_disclosure(combined_legal, prd_content)
            issues.extend(tp_issues)
            advisories.extend(tp_advisories)

            # Check 8: feature reference (advisory)
            feature_names = _extract_feature_names(prd_content)
            if feature_names:
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
            pass

    # Check 6: retention (deferred to here so prd_content is available)
    if privacy_content:
        ret_issues, ret_advisories = _check_retention(privacy_content, prd_content)
        issues.extend(ret_issues)
        advisories.extend(ret_advisories)

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
