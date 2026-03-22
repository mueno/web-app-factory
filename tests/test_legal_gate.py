"""Tests for tools/gates/legal_gate.py.

Verifies that run_legal_gate() correctly:
- Returns passing GateResult when both legal files exist with no placeholders
- Fails when either legal file is missing
- Fails when placeholder text is found in legal files
- Warns (advisory) when no app-specific feature from PRD is referenced
- Fails when both files are missing (two issues)
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch


class TestLegalGate:
    """Tests for run_legal_gate()."""

    def _create_legal_files(
        self,
        tmp_path: Path,
        *,
        privacy_content: str | None = None,
        terms_content: str | None = None,
    ) -> None:
        """Create the legal file directory structure and files."""
        privacy_dir = tmp_path / "src" / "app" / "privacy"
        privacy_dir.mkdir(parents=True, exist_ok=True)
        terms_dir = tmp_path / "src" / "app" / "terms"
        terms_dir.mkdir(parents=True, exist_ok=True)

        if privacy_content is not None:
            (privacy_dir / "page.tsx").write_text(privacy_content, encoding="utf-8")
        if terms_content is not None:
            (terms_dir / "page.tsx").write_text(terms_content, encoding="utf-8")

    def _create_prd(self, tmp_path: Path, content: str = "") -> None:
        """Create docs/pipeline/prd.md with given content."""
        prd_dir = tmp_path / "docs" / "pipeline"
        prd_dir.mkdir(parents=True, exist_ok=True)
        (prd_dir / "prd.md").write_text(content, encoding="utf-8")

    # ── Happy path ──────────────────────────────────────────────────────────

    def test_both_files_present_no_placeholders_pass(self, tmp_path):
        """Both legal files exist with no placeholders -> GateResult passed=True."""
        privacy_text = (
            "# Privacy Policy\n\nAcme Corp collects your health data to provide "
            "the WeightSnap weight tracking feature. Contact: hello@example.com"
        )
        terms_text = (
            "# Terms of Service\n\nThese terms govern your use of the WeightSnap "
            "application operated by Acme Corp."
        )
        self._create_legal_files(
            tmp_path, privacy_content=privacy_text, terms_content=terms_text
        )
        self._create_prd(
            tmp_path,
            "## Features\n\n- **WeightSnap**: Core weight tracking feature\n",
        )

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        assert result.gate_type == "legal"
        assert result.passed is True
        assert result.issues == []

    # ── Missing file tests ──────────────────────────────────────────────────

    def test_missing_privacy_file_fail(self, tmp_path):
        """Privacy page missing -> GateResult passed=False with issue."""
        terms_text = "# Terms\n\nAcme Corp terms for the app."
        self._create_legal_files(tmp_path, terms_content=terms_text)
        self._create_prd(tmp_path)

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        assert result.gate_type == "legal"
        assert result.passed is False
        assert len(result.issues) >= 1
        assert any("privacy" in issue.lower() for issue in result.issues)

    def test_missing_terms_file_fail(self, tmp_path):
        """Terms page missing -> GateResult passed=False with issue."""
        privacy_text = "# Privacy\n\nAcme Corp privacy policy."
        self._create_legal_files(tmp_path, privacy_content=privacy_text)
        self._create_prd(tmp_path)

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        assert result.gate_type == "legal"
        assert result.passed is False
        assert len(result.issues) >= 1
        assert any("terms" in issue.lower() for issue in result.issues)

    def test_both_files_missing_fail(self, tmp_path):
        """Neither legal file exists -> fail with 2 issues (one per missing file)."""
        # Create directory structure but no files
        (tmp_path / "src" / "app").mkdir(parents=True, exist_ok=True)
        self._create_prd(tmp_path)

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        assert result.gate_type == "legal"
        assert result.passed is False
        # Two issues: one for each missing file
        assert len(result.issues) >= 2

    # ── Placeholder tests ───────────────────────────────────────────────────

    def test_placeholder_your_app_name_detected_fail(self, tmp_path):
        """YOUR_APP_NAME in terms file -> GateResult passed=False with issue."""
        privacy_text = "# Privacy Policy\n\nAcme Corp collects data for the app."
        terms_text = (
            "# Terms of Service\n\nWelcome to YOUR_APP_NAME, operated by Acme Corp."
        )
        self._create_legal_files(
            tmp_path, privacy_content=privacy_text, terms_content=terms_text
        )
        self._create_prd(tmp_path)

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        assert result.gate_type == "legal"
        assert result.passed is False
        assert any("YOUR_APP_NAME" in issue or "placeholder" in issue.lower() for issue in result.issues)

    def test_placeholder_your_company_detected_fail(self, tmp_path):
        """YOUR_COMPANY in privacy file -> fail."""
        privacy_text = "# Privacy\n\nYOUR_COMPANY processes your personal data."
        terms_text = "# Terms\n\nAcme Corp terms."
        self._create_legal_files(
            tmp_path, privacy_content=privacy_text, terms_content=terms_text
        )
        self._create_prd(tmp_path)

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        assert result.passed is False
        assert any("YOUR_COMPANY" in issue or "placeholder" in issue.lower() for issue in result.issues)

    def test_placeholder_bracket_company_detected_fail(self, tmp_path):
        """[COMPANY] placeholder detected -> fail."""
        privacy_text = "# Privacy\n\n[COMPANY] Privacy Policy."
        terms_text = "# Terms\n\nAcme Corp terms."
        self._create_legal_files(
            tmp_path, privacy_content=privacy_text, terms_content=terms_text
        )
        self._create_prd(tmp_path)

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        assert result.passed is False

    def test_placeholder_bracket_date_detected_fail(self, tmp_path):
        """[DATE] placeholder detected -> fail."""
        privacy_text = "# Privacy\n\nEffective [DATE]."
        terms_text = "# Terms\n\nAcme Corp terms."
        self._create_legal_files(
            tmp_path, privacy_content=privacy_text, terms_content=terms_text
        )
        self._create_prd(tmp_path)

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        assert result.passed is False

    def test_placeholder_bracket_app_name_detected_fail(self, tmp_path):
        """[APP_NAME] placeholder detected -> fail."""
        privacy_text = "# Privacy\n\n[APP_NAME] collects your data."
        terms_text = "# Terms\n\nAcme Corp terms."
        self._create_legal_files(
            tmp_path, privacy_content=privacy_text, terms_content=terms_text
        )
        self._create_prd(tmp_path)

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        assert result.passed is False

    def test_placeholder_your_email_detected_fail(self, tmp_path):
        """YOUR_EMAIL placeholder detected -> fail."""
        privacy_text = "# Privacy\n\nContact us at YOUR_EMAIL."
        terms_text = "# Terms\n\nAcme Corp terms."
        self._create_legal_files(
            tmp_path, privacy_content=privacy_text, terms_content=terms_text
        )
        self._create_prd(tmp_path)

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        assert result.passed is False

    # ── Feature reference advisory ──────────────────────────────────────────

    def test_no_feature_reference_advisory(self, tmp_path):
        """Legal files exist but no PRD feature referenced -> pass with advisory."""
        privacy_text = "# Privacy\n\nAcme Corp processes personal data. Contact: hi@example.com"
        terms_text = "# Terms\n\nAcme Corp terms of service. Last updated 2026."
        self._create_legal_files(
            tmp_path, privacy_content=privacy_text, terms_content=terms_text
        )
        # PRD with features that don't appear in legal docs
        self._create_prd(
            tmp_path,
            "## Features\n\n- **UniquePlatformFeatureXYZ**: Core tracking\n",
        )

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        # Advisory: passes but with advisory message
        assert result.passed is True
        assert len(result.advisories) >= 1
        assert any("feature" in adv.lower() or "reference" in adv.lower() for adv in result.advisories)

    def test_feature_referenced_no_advisory(self, tmp_path):
        """PRD feature name appears in legal docs -> no advisory."""
        feature_name = "WeightTracker"
        privacy_text = f"# Privacy\n\nAcme Corp processes data for {feature_name}."
        terms_text = f"# Terms\n\nAcme Corp terms for the {feature_name} application."
        self._create_legal_files(
            tmp_path, privacy_content=privacy_text, terms_content=terms_text
        )
        self._create_prd(
            tmp_path,
            f"## Features\n\n- **{feature_name}**: Core tracking feature\n",
        )

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        assert result.passed is True
        # Feature was referenced, so no advisory about missing feature reference
        feature_advisories = [
            adv for adv in result.advisories
            if "feature" in adv.lower() or "reference" in adv.lower()
        ]
        assert len(feature_advisories) == 0

    # ── phase_id propagation ────────────────────────────────────────────────

    def test_phase_id_propagated(self, tmp_path):
        """phase_id parameter is reflected in GateResult.phase_id."""
        privacy_text = "# Privacy\n\nAcme Corp."
        terms_text = "# Terms\n\nAcme Corp."
        self._create_legal_files(
            tmp_path, privacy_content=privacy_text, terms_content=terms_text
        )
        self._create_prd(tmp_path)

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path), phase_id="3")
        assert result.phase_id == "3"

    # ── No PRD file ─────────────────────────────────────────────────────────

    def test_no_prd_file_still_checks_files(self, tmp_path):
        """Missing prd.md -> legal gate still checks file presence and placeholders."""
        privacy_text = "# Privacy\n\nAcme Corp collects data."
        terms_text = "# Terms\n\nAcme Corp terms."
        self._create_legal_files(
            tmp_path, privacy_content=privacy_text, terms_content=terms_text
        )
        # No prd.md created

        from tools.gates.legal_gate import run_legal_gate

        result = run_legal_gate(str(tmp_path))

        # Files present, no placeholders -> should pass (no PRD = skip feature check)
        assert result.gate_type == "legal"
        assert result.passed is True
