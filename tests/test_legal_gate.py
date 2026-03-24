"""Tests for tools/gates/legal_gate.py.

Verifies that run_legal_gate() correctly:
- Returns passing GateResult when legal files have complete disclosures
- Fails when either legal file is missing
- Fails when placeholder text is found
- Fails when required privacy disclosure sections are missing
- Fails when required terms sections are missing
- Fails when contact email is missing or placeholder
- Advises when data retention is not mentioned
- Advises when third-party services are undisclosed
- Advises when no app-specific features are referenced
"""

from __future__ import annotations

import pytest
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────────────────────

# Compliant privacy text with all required sections
_GOOD_PRIVACY = """
# Privacy Policy

## Data We Collect
We collect your name, email address, and usage data to provide the WeightSnap
weight tracking service.

## How We Use Your Data
Your data is used to operate and improve the application.

## Third-Party Sharing
We share limited data with Vercel for hosting and deployment.

## Data Retention
We retain your personal data for 12 months. You may request deletion at any time.

## Your Rights
You may request access, correction, or deletion of your data.

## Contact
Questions? Email us at support@allnew.jp
"""

# Compliant terms text with all required sections
_GOOD_TERMS = """
# Terms of Service

## Acceptance
By using WeightSnap, you agree to these terms.

## Usage Rules
You must not misuse the service or attempt unauthorized access.

## Intellectual Property
All content and trademarks belong to AllNew LLC.

## Limitation of Liability
The service is provided as-is. We disclaim all warranties to the extent
permitted by law.

## Contact
For questions, email support@allnew.jp
"""


class TestLegalGate:
    """Tests for run_legal_gate()."""

    def _create_legal_files(
        self,
        tmp_path: Path,
        *,
        privacy_content: str | None = None,
        terms_content: str | None = None,
    ) -> None:
        privacy_dir = tmp_path / "src" / "app" / "privacy"
        privacy_dir.mkdir(parents=True, exist_ok=True)
        terms_dir = tmp_path / "src" / "app" / "terms"
        terms_dir.mkdir(parents=True, exist_ok=True)

        if privacy_content is not None:
            (privacy_dir / "page.tsx").write_text(privacy_content, encoding="utf-8")
        if terms_content is not None:
            (terms_dir / "page.tsx").write_text(terms_content, encoding="utf-8")

    def _create_prd(self, tmp_path: Path, content: str = "") -> None:
        prd_dir = tmp_path / "docs" / "pipeline"
        prd_dir.mkdir(parents=True, exist_ok=True)
        (prd_dir / "prd.md").write_text(content, encoding="utf-8")

    # ── Happy path ────────────────────────────────────────────────────────

    def test_complete_legal_docs_pass(self, tmp_path):
        """Complete legal docs with all required sections pass."""
        self._create_legal_files(
            tmp_path, privacy_content=_GOOD_PRIVACY, terms_content=_GOOD_TERMS
        )
        self._create_prd(
            tmp_path, "## Features\n\n- **WeightSnap**: Core tracking\n"
        )

        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))

        assert result.gate_type == "legal"
        assert result.passed is True
        assert result.issues == []

    # ── Missing file tests ────────────────────────────────────────────────

    def test_missing_privacy_file_fail(self, tmp_path):
        self._create_legal_files(tmp_path, terms_content=_GOOD_TERMS)
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is False
        assert any("privacy" in i.lower() for i in result.issues)

    def test_missing_terms_file_fail(self, tmp_path):
        self._create_legal_files(tmp_path, privacy_content=_GOOD_PRIVACY)
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is False
        assert any("terms" in i.lower() for i in result.issues)

    def test_both_files_missing_fail(self, tmp_path):
        (tmp_path / "src" / "app").mkdir(parents=True, exist_ok=True)
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is False
        assert len(result.issues) >= 2

    # ── Placeholder tests ─────────────────────────────────────────────────

    def test_placeholder_your_app_name_fail(self, tmp_path):
        self._create_legal_files(
            tmp_path,
            privacy_content=_GOOD_PRIVACY,
            terms_content="# Terms\n\nWelcome to YOUR_APP_NAME. By accepting these terms...\nContact: support@allnew.jp\nLimitation of liability: as-is.",
        )
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is False
        assert any("YOUR_APP_NAME" in i for i in result.issues)

    def test_placeholder_your_company_fail(self, tmp_path):
        self._create_legal_files(
            tmp_path,
            privacy_content="# Privacy\n\nYOUR_COMPANY collects data.\nContact: support@allnew.jp\nThird-party: none.\nWe use your data to operate.",
            terms_content=_GOOD_TERMS,
        )
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is False
        assert any("YOUR_COMPANY" in i for i in result.issues)

    def test_placeholder_bracket_patterns_fail(self, tmp_path):
        for pattern in ["[COMPANY]", "[DATE]", "[APP_NAME]", "[EMAIL]"]:
            self._create_legal_files(
                tmp_path,
                privacy_content=f"# Privacy\n\n{pattern} collects data.\nContact: support@allnew.jp\nThird-party sharing: none.\nWe use your data.",
                terms_content=_GOOD_TERMS,
            )
            from tools.gates.legal_gate import run_legal_gate
            result = run_legal_gate(str(tmp_path))
            assert result.passed is False, f"Expected fail for placeholder {pattern}"

    # ── Disclosure completeness tests (NEW — L-1 audit fix) ───────────────

    def test_privacy_missing_data_collection_section_fail(self, tmp_path):
        """Privacy policy without 'data collection' section fails."""
        incomplete = "# Privacy\n\nWe use your data. Third-party: Vercel.\nContact: support@allnew.jp\nRetention: 12 months.\nLimitation of liability."
        self._create_legal_files(tmp_path, privacy_content=incomplete, terms_content=_GOOD_TERMS)
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is False
        assert any("Data Collection" in i for i in result.issues)

    def test_privacy_missing_third_party_section_fail(self, tmp_path):
        """Privacy policy without third-party/sharing section fails."""
        incomplete = "# Privacy\n\nData we collect: name, email.\nHow we use your data: to operate.\nContact: support@allnew.jp\nRetention: 12 months."
        self._create_legal_files(tmp_path, privacy_content=incomplete, terms_content=_GOOD_TERMS)
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is False
        assert any("Third-Party" in i for i in result.issues)

    def test_terms_missing_liability_section_fail(self, tmp_path):
        """Terms without limitation of liability section fails."""
        incomplete = "# Terms\n\nBy accepting you agree.\nContact: support@allnew.jp"
        self._create_legal_files(tmp_path, privacy_content=_GOOD_PRIVACY, terms_content=incomplete)
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is False
        assert any("Limitation" in i or "Liability" in i or "Disclaimer" in i for i in result.issues)

    def test_terms_missing_acceptance_section_fail(self, tmp_path):
        """Terms without acceptance/agreement section fails."""
        incomplete = "# Terms\n\nLimitation of liability: as-is.\nContact: support@allnew.jp"
        self._create_legal_files(tmp_path, privacy_content=_GOOD_PRIVACY, terms_content=incomplete)
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is False
        assert any("Acceptance" in i or "Agreement" in i for i in result.issues)

    # ── Contact information tests (NEW — L-1 audit fix) ───────────────────

    def test_no_contact_email_fail(self, tmp_path):
        """Legal docs without any email address fail."""
        no_email_privacy = _GOOD_PRIVACY.replace("support@allnew.jp", "our support team")
        no_email_terms = _GOOD_TERMS.replace("support@allnew.jp", "our support team")
        self._create_legal_files(
            tmp_path, privacy_content=no_email_privacy, terms_content=no_email_terms
        )
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is False
        assert any("email" in i.lower() for i in result.issues)

    def test_placeholder_email_domain_fail(self, tmp_path):
        """Legal docs with only example.com email fail."""
        placeholder_privacy = _GOOD_PRIVACY.replace("support@allnew.jp", "info@example.com")
        placeholder_terms = _GOOD_TERMS.replace("support@allnew.jp", "info@example.com")
        self._create_legal_files(
            tmp_path, privacy_content=placeholder_privacy, terms_content=placeholder_terms
        )
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is False
        assert any("placeholder" in i.lower() for i in result.issues)

    # ── Retention advisory (NEW — L-1 audit fix) ──────────────────────────

    def test_no_retention_mention_advisory(self, tmp_path):
        """Privacy without retention mention gets advisory."""
        no_retention = _GOOD_PRIVACY.replace(
            "## Data Retention\nWe retain your personal data for 12 months. You may request deletion at any time.\n",
            ""
        ).replace("deletion", "correction")
        self._create_legal_files(
            tmp_path, privacy_content=no_retention, terms_content=_GOOD_TERMS
        )
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        # May still pass (advisory only) but should have retention advisory
        assert any("retention" in a.lower() or "deletion" in a.lower() for a in result.advisories)

    # ── Third-party disclosure advisory (NEW — L-1 audit fix) ─────────────

    def test_third_party_in_prd_but_not_legal_blocks(self, tmp_path):
        """PRD mentions OpenAI but legal docs don't → BLOCK (not advisory)."""
        self._create_legal_files(
            tmp_path, privacy_content=_GOOD_PRIVACY, terms_content=_GOOD_TERMS
        )
        self._create_prd(
            tmp_path,
            "## Features\n\n- **AI Chat**: Uses OpenAI GPT for responses\n",
        )
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert not result.passed
        assert any("OpenAI" in i for i in result.issues)

    def test_third_party_disclosed_no_block(self, tmp_path):
        """PRD mentions Vercel, legal docs mention Vercel → no block."""
        self._create_legal_files(
            tmp_path, privacy_content=_GOOD_PRIVACY, terms_content=_GOOD_TERMS
        )
        self._create_prd(
            tmp_path,
            "## Features\n\n- **Deploy**: Deployed on Vercel\n",
        )
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        vercel_issues = [i for i in result.issues if "Vercel" in i]
        assert len(vercel_issues) == 0

    def test_retention_blocks_when_prd_collects_data(self, tmp_path):
        """PRD indicates user data collection + no retention mention → BLOCK."""
        no_retention = _GOOD_PRIVACY.replace(
            "## Data Retention\nWe retain your personal data for 12 months. You may request deletion at any time.\n",
            ""
        ).replace("deletion", "correction")
        self._create_legal_files(
            tmp_path, privacy_content=no_retention, terms_content=_GOOD_TERMS
        )
        self._create_prd(
            tmp_path,
            "## Features\n\n- **User Profile**: Sign-up and account management\n",
        )
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert not result.passed
        assert any("retention" in i.lower() for i in result.issues)

    # ── Feature reference advisory ────────────────────────────────────────

    def test_no_feature_reference_advisory(self, tmp_path):
        self._create_legal_files(
            tmp_path, privacy_content=_GOOD_PRIVACY, terms_content=_GOOD_TERMS
        )
        self._create_prd(
            tmp_path,
            "## Features\n\n- **UniquePlatformFeatureXYZ**: Core tracking\n",
        )
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.passed is True
        assert any("feature" in a.lower() for a in result.advisories)

    # ── Metadata propagation ──────────────────────────────────────────────

    def test_phase_id_propagated(self, tmp_path):
        self._create_legal_files(
            tmp_path, privacy_content=_GOOD_PRIVACY, terms_content=_GOOD_TERMS
        )
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path), phase_id="3")
        assert result.phase_id == "3"

    def test_no_prd_file_still_checks_completeness(self, tmp_path):
        """Missing prd.md → still checks file presence, placeholders, and sections."""
        self._create_legal_files(
            tmp_path, privacy_content=_GOOD_PRIVACY, terms_content=_GOOD_TERMS
        )
        from tools.gates.legal_gate import run_legal_gate
        result = run_legal_gate(str(tmp_path))
        assert result.gate_type == "legal"
        assert result.passed is True
