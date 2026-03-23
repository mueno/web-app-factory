"""Tests for tools/gates/static_analysis_gate.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.gates.gate_result import GateResult


def _write_file(base: Path, rel_path: str, content: str) -> Path:
    """Create a file with given content relative to base directory."""
    target = base / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


class TestUseClientCheck:
    """Tests for the no_use_client_in_layout check (GATE-05)."""

    def test_detects_use_client_in_layout_tsx(self, tmp_path):
        """'use client' in src/app/layout.tsx is flagged as an issue."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/app/layout.tsx", '"use client"\n\nexport default function RootLayout() {}')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False
        assert any("layout.tsx" in issue for issue in result.issues)

    def test_detects_use_client_in_page_tsx(self, tmp_path):
        """'use client' in src/app/page.tsx is flagged as an issue."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/app/page.tsx", "'use client'\n\nexport default function Home() {}")

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False
        assert any("page.tsx" in issue for issue in result.issues)

    def test_does_not_flag_use_client_in_error_tsx(self, tmp_path):
        """'use client' in src/app/error.tsx is NOT flagged (correct usage for error boundaries)."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/app/error.tsx", '"use client"\n\nexport default function Error() {}')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is True
        assert result.issues == []

    def test_does_not_flag_use_client_in_components(self, tmp_path):
        """'use client' in src/components/Button.tsx is NOT flagged (correct usage for interactive components)."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/components/Button.tsx", '"use client"\n\nexport default function Button() {}')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is True
        assert result.issues == []

    def test_issue_includes_line_number_for_layout(self, tmp_path):
        """Issue for layout.tsx includes a line number."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/app/layout.tsx", "// header\n\"use client\"\n\nexport default function Layout() {}")

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False
        # Issue should mention line 2 (second line)
        assert any("2" in issue for issue in result.issues)

    def test_issue_includes_line_number_for_page(self, tmp_path):
        """Issue for page.tsx includes a line number."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/app/page.tsx", "'use client'\n\nexport default function Page() {}")

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        # Issue should mention line 1
        assert any("1" in issue for issue in result.issues)

    def test_no_issue_when_layout_tsx_missing(self, tmp_path):
        """No issue if layout.tsx does not exist (file might not be scaffolded yet)."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        # No layout.tsx created
        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is True
        assert result.issues == []

    def test_no_issue_when_layout_tsx_has_no_use_client(self, tmp_path):
        """No issue when layout.tsx exists but has no 'use client'."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/app/layout.tsx", "export default function RootLayout({ children }) {\n  return <html>{children}</html>\n}")

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is True
        assert result.issues == []


class TestNextPublicSecretsCheck:
    """Tests for the no_next_public_secrets check (GATE-06)."""

    def test_detects_next_public_api_key_in_tsx(self, tmp_path):
        """NEXT_PUBLIC_API_KEY in a .tsx file is flagged."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/lib/config.tsx", 'const key = process.env.NEXT_PUBLIC_API_KEY\n')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False
        assert any("NEXT_PUBLIC_API_KEY" in issue or "config.tsx" in issue for issue in result.issues)

    def test_detects_next_public_stripe_secret_in_ts(self, tmp_path):
        """NEXT_PUBLIC_STRIPE_SECRET in a .ts file is flagged."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/lib/stripe.ts", 'const secret = process.env.NEXT_PUBLIC_STRIPE_SECRET\n')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False
        assert any("NEXT_PUBLIC_STRIPE_SECRET" in issue or "stripe.ts" in issue for issue in result.issues)

    def test_detects_next_public_auth_token_in_env_file(self, tmp_path):
        """NEXT_PUBLIC_AUTH_TOKEN in a .env file is flagged."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, ".env", 'NEXT_PUBLIC_AUTH_TOKEN=supersecretvalue\n')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False
        assert any("NEXT_PUBLIC_AUTH_TOKEN" in issue or ".env" in issue for issue in result.issues)

    def test_passes_on_next_public_app_name(self, tmp_path):
        """NEXT_PUBLIC_APP_NAME is safe (no secret-pattern suffix) — should NOT be flagged."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/lib/config.ts", 'const name = process.env.NEXT_PUBLIC_APP_NAME\n')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is True
        assert result.issues == []

    def test_passes_on_next_public_base_url(self, tmp_path):
        """NEXT_PUBLIC_BASE_URL is safe — should NOT be flagged."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/lib/config.ts", 'const url = process.env.NEXT_PUBLIC_BASE_URL\n')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is True
        assert result.issues == []

    def test_detects_secret_in_env_local(self, tmp_path):
        """NEXT_PUBLIC_SECRET_KEY in .env.local is flagged."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, ".env.local", 'NEXT_PUBLIC_API_KEY=value\n')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False

    def test_detects_secret_in_src_env_local(self, tmp_path):
        """NEXT_PUBLIC_SECRET_KEY in src/.env.local is also flagged."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/.env.local", 'NEXT_PUBLIC_TOKEN=abc\n')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False

    def test_skips_node_modules(self, tmp_path):
        """Files under node_modules/ are skipped entirely."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "node_modules/some-pkg/index.ts", 'const x = process.env.NEXT_PUBLIC_API_KEY\n')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        # node_modules should be skipped → no issues
        assert result.passed is True
        assert result.issues == []

    def test_issue_includes_line_number_for_secret(self, tmp_path):
        """Issue for secret detection includes a line number."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/lib/config.ts", "// config\nconst x = process.env.NEXT_PUBLIC_API_KEY\n")

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        # Should mention line 2
        assert any("2" in issue for issue in result.issues)


class TestStaticAnalysisGateResult:
    """Tests for gate result structure."""

    def test_returns_gate_result_instance(self, tmp_path):
        """run_static_analysis_gate returns a GateResult instance."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert isinstance(result, GateResult)

    def test_gate_type_is_static_analysis(self, tmp_path):
        """gate_type field is 'static_analysis'."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.gate_type == "static_analysis"

    def test_phase_id_is_preserved(self, tmp_path):
        """phase_id passed to function is reflected in result."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.phase_id == "2b"

    def test_passed_true_when_no_issues_found(self, tmp_path):
        """gate returns passed=True when no issues found in clean project."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/app/layout.tsx", "export default function Layout() {}")
        _write_file(tmp_path, "src/lib/config.ts", "const name = process.env.NEXT_PUBLIC_APP_NAME\n")

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is True
        assert result.issues == []

    def test_passed_false_when_multiple_issues_found(self, tmp_path):
        """gate returns passed=False and all issues when multiple problems exist."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/app/layout.tsx", '"use client"\nexport default function Layout() {}')
        _write_file(tmp_path, "src/app/page.tsx", '"use client"\nexport default function Page() {}')
        _write_file(tmp_path, "src/lib/config.ts", "const x = process.env.NEXT_PUBLIC_API_KEY\n")

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False
        # Should have at least 3 issues (layout, page, and secret)
        assert len(result.issues) >= 3

    def test_checked_at_is_non_empty_string(self, tmp_path):
        """checked_at field is populated."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert isinstance(result.checked_at, str)
        assert len(result.checked_at) > 0

    def test_status_pass_when_no_issues(self, tmp_path):
        """status='PASS' when no issues found."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.status == "PASS"

    def test_status_blocked_when_issues_found(self, tmp_path):
        """status='BLOCKED' when issues found."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(tmp_path, "src/app/layout.tsx", '"use client"\nexport default function Layout() {}')

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.status == "BLOCKED"


class TestErrorBoundaryCheck:
    """Tests for the error boundary check (BILD-06)."""

    def test_detects_missing_error_tsx_for_async_page(self, tmp_path):
        """page.tsx with async fetch but no error.tsx is flagged."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(
            tmp_path,
            "src/app/dashboard/page.tsx",
            "export default async function Dashboard() {\n  const res = await fetch('/api/data');\n}",
        )

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False
        assert any("error.tsx" in issue for issue in result.issues)

    def test_passes_when_error_tsx_exists_with_use_client(self, tmp_path):
        """page.tsx with async fetch AND proper error.tsx passes."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(
            tmp_path,
            "src/app/dashboard/page.tsx",
            "export default async function Dashboard() {\n  const res = await fetch('/api/data');\n}",
        )
        _write_file(
            tmp_path,
            "src/app/dashboard/error.tsx",
            '"use client"\n\nexport default function Error() { return <div>Error</div> }',
        )

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is True

    def test_detects_error_tsx_missing_use_client(self, tmp_path):
        """error.tsx without 'use client' directive is flagged."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(
            tmp_path,
            "src/app/dashboard/page.tsx",
            "export default async function Dashboard() {\n  const res = await fetch('/api/data');\n}",
        )
        _write_file(
            tmp_path,
            "src/app/dashboard/error.tsx",
            "export default function Error() { return <div>Error</div> }",
        )

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False
        assert any("use client" in issue.lower() for issue in result.issues)

    def test_no_issue_for_sync_page(self, tmp_path):
        """page.tsx without async data fetching does not require error.tsx."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(
            tmp_path,
            "src/app/about/page.tsx",
            "export default function About() { return <div>About</div> }",
        )

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is True


class TestResponsivePatternCheck:
    """Tests for the responsive design check (BILD-05)."""

    def test_detects_hardcoded_large_pixel_width(self, tmp_path):
        """Hardcoded pixel widths >= 1000px are flagged."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(
            tmp_path,
            "src/components/Hero.tsx",
            'export default function Hero() { return <div style={{width: "1200px"}}>Hero</div> }',
        )

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is False
        assert any("pixel width" in issue.lower() or "responsive" in issue.lower() for issue in result.issues)

    def test_passes_on_responsive_tailwind(self, tmp_path):
        """Normal Tailwind responsive classes pass without issues."""
        from tools.gates.static_analysis_gate import run_static_analysis_gate

        _write_file(
            tmp_path,
            "src/components/Card.tsx",
            'export default function Card() { return <div className="w-full md:w-1/2 lg:w-1/3">Card</div> }',
        )

        result = run_static_analysis_gate(str(tmp_path), phase_id="2b")

        assert result.passed is True
