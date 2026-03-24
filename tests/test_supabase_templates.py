"""Tests for web_app_factory/templates/supabase-browser.ts.tmpl and supabase-server.ts.tmpl.

Verifies dual Supabase client template content and security constraints:
- Browser template uses anon key only (safe for client-side)
- Server template uses service_role key without NEXT_PUBLIC_ prefix
- Neither template leaks service_role to client side
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Template directory path
TEMPLATES_DIR = Path(__file__).parent.parent / "web_app_factory" / "templates"
BROWSER_TEMPLATE = TEMPLATES_DIR / "supabase-browser.ts.tmpl"
SERVER_TEMPLATE = TEMPLATES_DIR / "supabase-server.ts.tmpl"


class TestSupabaseBrowserTemplate:
    """Tests for supabase-browser.ts.tmpl — browser-side client (anon key only)."""

    def test_browser_template_file_exists(self):
        """supabase-browser.ts.tmpl must exist in templates directory."""
        assert BROWSER_TEMPLATE.exists(), (
            f"supabase-browser.ts.tmpl not found at {BROWSER_TEMPLATE}"
        )

    def test_browser_template_imports_create_browser_client(self):
        """Browser template must import createBrowserClient from @supabase/ssr."""
        content = BROWSER_TEMPLATE.read_text(encoding="utf-8")
        assert "createBrowserClient" in content
        assert "@supabase/ssr" in content

    def test_browser_template_uses_anon_key(self):
        """Browser template must reference NEXT_PUBLIC_SUPABASE_ANON_KEY."""
        content = BROWSER_TEMPLATE.read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_SUPABASE_ANON_KEY" in content

    def test_browser_template_uses_public_url(self):
        """Browser template must reference NEXT_PUBLIC_SUPABASE_URL."""
        content = BROWSER_TEMPLATE.read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_SUPABASE_URL" in content

    def test_browser_template_exports_create_client(self):
        """Browser template must export a createClient function."""
        content = BROWSER_TEMPLATE.read_text(encoding="utf-8")
        assert "export" in content
        assert "createClient" in content

    def test_browser_template_does_not_contain_service_role_key(self):
        """Browser template must NOT reference SUPABASE_SERVICE_ROLE_KEY."""
        content = BROWSER_TEMPLATE.read_text(encoding="utf-8")
        assert "SERVICE_ROLE_KEY" not in content, (
            "Browser template must not reference SERVICE_ROLE_KEY — "
            "service_role key must NEVER be used client-side"
        )

    def test_browser_template_does_not_contain_service_role_ref(self):
        """Browser template must NOT contain any service_role reference."""
        content = BROWSER_TEMPLATE.read_text(encoding="utf-8").lower()
        assert "service_role" not in content, (
            "Browser template must not contain any service_role reference"
        )

    def test_browser_template_does_not_contain_next_public_service_role(self):
        """Browser template must NOT use NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY."""
        content = BROWSER_TEMPLATE.read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY" not in content

    def test_browser_template_imports_from_supabase_ssr(self):
        """Browser template import statement must use @supabase/ssr package."""
        content = BROWSER_TEMPLATE.read_text(encoding="utf-8")
        # Should have: from '@supabase/ssr' or from "@supabase/ssr"
        assert "from '@supabase/ssr'" in content or 'from "@supabase/ssr"' in content


class TestSupabaseServerTemplate:
    """Tests for supabase-server.ts.tmpl — server-side client (service_role, no NEXT_PUBLIC_)."""

    def test_server_template_file_exists(self):
        """supabase-server.ts.tmpl must exist in templates directory."""
        assert SERVER_TEMPLATE.exists(), (
            f"supabase-server.ts.tmpl not found at {SERVER_TEMPLATE}"
        )

    def test_server_template_imports_create_server_client(self):
        """Server template must import createServerClient from @supabase/ssr."""
        content = SERVER_TEMPLATE.read_text(encoding="utf-8")
        assert "createServerClient" in content
        assert "@supabase/ssr" in content

    def test_server_template_imports_cookies_from_next_headers(self):
        """Server template must import cookies from next/headers."""
        content = SERVER_TEMPLATE.read_text(encoding="utf-8")
        assert "cookies" in content
        assert "next/headers" in content

    def test_server_template_uses_service_role_key(self):
        """Server template must reference SUPABASE_SERVICE_ROLE_KEY."""
        content = SERVER_TEMPLATE.read_text(encoding="utf-8")
        assert "SUPABASE_SERVICE_ROLE_KEY" in content

    def test_server_template_uses_public_url(self):
        """Server template must reference NEXT_PUBLIC_SUPABASE_URL."""
        content = SERVER_TEMPLATE.read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_SUPABASE_URL" in content

    def test_server_template_exports_create_client(self):
        """Server template must export a createClient function."""
        content = SERVER_TEMPLATE.read_text(encoding="utf-8")
        assert "export" in content
        assert "createClient" in content

    def test_server_template_service_role_has_no_next_public_prefix(self):
        """SUPABASE_SERVICE_ROLE_KEY must NOT have NEXT_PUBLIC_ prefix in server template."""
        content = SERVER_TEMPLATE.read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY" not in content, (
            "CRITICAL: service_role key must NEVER use NEXT_PUBLIC_ prefix — "
            "this would expose it to the browser (SECG-01)"
        )

    def test_server_template_does_not_expose_service_role_via_next_public(self):
        """Server template must not have any NEXT_PUBLIC_ variant of service_role."""
        content = SERVER_TEMPLATE.read_text(encoding="utf-8")
        import re
        # Match NEXT_PUBLIC_ followed by anything containing SERVICE and ROLE
        pattern = re.compile(r"NEXT_PUBLIC_\w*SERVICE\w*ROLE", re.IGNORECASE)
        matches = pattern.findall(content)
        assert len(matches) == 0, (
            f"Found NEXT_PUBLIC_ service_role exposure in server template: {matches}"
        )

    def test_server_template_service_role_accessed_via_process_env(self):
        """Server template must access service_role via process.env (server-side only)."""
        content = SERVER_TEMPLATE.read_text(encoding="utf-8")
        assert "process.env.SUPABASE_SERVICE_ROLE_KEY" in content

    def test_server_template_imports_from_supabase_ssr(self):
        """Server template import statement must use @supabase/ssr package."""
        content = SERVER_TEMPLATE.read_text(encoding="utf-8")
        assert "from '@supabase/ssr'" in content or 'from "@supabase/ssr"' in content

    def test_server_template_has_secg01_comment(self):
        """Server template must contain SECG-01 comment warning against NEXT_PUBLIC_ prefix."""
        content = SERVER_TEMPLATE.read_text(encoding="utf-8")
        assert "SECG-01" in content, (
            "Server template must contain SECG-01 comment to document security requirement"
        )


class TestSupabaseTemplateSeparation:
    """Tests verifying clear separation between browser and server templates."""

    def test_both_templates_import_from_supabase_ssr(self):
        """Both templates must import from @supabase/ssr."""
        for template_path in (BROWSER_TEMPLATE, SERVER_TEMPLATE):
            content = template_path.read_text(encoding="utf-8")
            assert "@supabase/ssr" in content, (
                f"{template_path.name} must import from @supabase/ssr"
            )

    def test_both_templates_export_create_client(self):
        """Both templates must export a createClient function."""
        for template_path in (BROWSER_TEMPLATE, SERVER_TEMPLATE):
            content = template_path.read_text(encoding="utf-8")
            assert "createClient" in content, (
                f"{template_path.name} must export createClient"
            )

    def test_browser_uses_browser_client_server_uses_server_client(self):
        """Browser uses createBrowserClient; server uses createServerClient."""
        browser_content = BROWSER_TEMPLATE.read_text(encoding="utf-8")
        server_content = SERVER_TEMPLATE.read_text(encoding="utf-8")

        assert "createBrowserClient" in browser_content
        assert "createServerClient" in server_content
        # Cross-check: each should NOT use the other's client type
        assert "createServerClient" not in browser_content, (
            "Browser template should not use createServerClient"
        )
        assert "createBrowserClient" not in server_content, (
            "Server template should not use createBrowserClient"
        )

    def test_only_server_template_references_service_role(self):
        """service_role key must only appear in server template, never in browser template."""
        browser_content = BROWSER_TEMPLATE.read_text(encoding="utf-8").lower()
        server_content = SERVER_TEMPLATE.read_text(encoding="utf-8")

        assert "service_role" not in browser_content, (
            "Browser template must never reference service_role"
        )
        assert "SUPABASE_SERVICE_ROLE_KEY" in server_content, (
            "Server template must reference SUPABASE_SERVICE_ROLE_KEY"
        )

    def test_server_template_has_cookie_handling(self):
        """Server template must implement cookie handling for auth session management."""
        content = SERVER_TEMPLATE.read_text(encoding="utf-8")
        assert "cookies" in content, (
            "Server template needs cookie handling for Supabase auth session"
        )
