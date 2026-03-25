"""Tests for web_app_factory/_supabase_auth_renderer.py.

Verifies that render_auth_templates() correctly renders all 10 auth templates
(6 OAuth + 4 passkey) into the correct output paths within a generated app directory.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from web_app_factory._supabase_auth_renderer import render_auth_templates
from web_app_factory._supabase_template_renderer import add_passkey_deps

# Template directory for integrity checks
TEMPLATES_DIR = Path(__file__).parent.parent / "web_app_factory" / "templates"


class TestRenderAuthTemplatesOutputPaths:
    """Tests that render_auth_templates() creates files in correct locations."""

    def test_renders_middleware_to_src_middleware_ts(self, tmp_path):
        """render_auth_templates must create src/middleware.ts from auth-middleware.ts.tmpl."""
        render_auth_templates(tmp_path)
        expected = tmp_path / "src" / "middleware.ts"
        assert expected.exists(), f"Expected {expected} to exist after rendering"

    def test_renders_login_to_auth_login_page(self, tmp_path):
        """render_auth_templates must create src/app/auth/login/page.tsx."""
        render_auth_templates(tmp_path)
        expected = tmp_path / "src" / "app" / "auth" / "login" / "page.tsx"
        assert expected.exists(), f"Expected {expected} to exist after rendering"

    def test_renders_signup_to_auth_signup_page(self, tmp_path):
        """render_auth_templates must create src/app/auth/signup/page.tsx."""
        render_auth_templates(tmp_path)
        expected = tmp_path / "src" / "app" / "auth" / "signup" / "page.tsx"
        assert expected.exists(), f"Expected {expected} to exist after rendering"

    def test_renders_signout_to_auth_signout_page(self, tmp_path):
        """render_auth_templates must create src/app/auth/signout/page.tsx."""
        render_auth_templates(tmp_path)
        expected = tmp_path / "src" / "app" / "auth" / "signout" / "page.tsx"
        assert expected.exists(), f"Expected {expected} to exist after rendering"

    def test_renders_callback_to_auth_callback_route(self, tmp_path):
        """render_auth_templates must create src/app/auth/callback/route.ts."""
        render_auth_templates(tmp_path)
        expected = tmp_path / "src" / "app" / "auth" / "callback" / "route.ts"
        assert expected.exists(), f"Expected {expected} to exist after rendering"

    def test_renders_auth_setup_md_to_project_root(self, tmp_path):
        """render_auth_templates must create AUTH_SETUP.md at output_dir root (not src/)."""
        render_auth_templates(tmp_path)
        expected = tmp_path / "AUTH_SETUP.md"
        assert expected.exists(), f"Expected {expected} to exist after rendering"

    # --- Passkey template output paths ---

    def test_renders_passkey_register_route(self, tmp_path):
        """render_auth_templates must create src/app/api/auth/passkey/register/route.ts."""
        render_auth_templates(tmp_path)
        expected = tmp_path / "src" / "app" / "api" / "auth" / "passkey" / "register" / "route.ts"
        assert expected.exists(), f"Expected {expected} to exist after rendering"

    def test_renders_passkey_authenticate_route(self, tmp_path):
        """render_auth_templates must create src/app/api/auth/passkey/authenticate/route.ts."""
        render_auth_templates(tmp_path)
        expected = tmp_path / "src" / "app" / "api" / "auth" / "passkey" / "authenticate" / "route.ts"
        assert expected.exists(), f"Expected {expected} to exist after rendering"

    def test_renders_passkey_hooks_lib(self, tmp_path):
        """render_auth_templates must create src/lib/auth/passkey-hooks.ts."""
        render_auth_templates(tmp_path)
        expected = tmp_path / "src" / "lib" / "auth" / "passkey-hooks.ts"
        assert expected.exists(), f"Expected {expected} to exist after rendering"

    def test_renders_passkey_buttons_component(self, tmp_path):
        """render_auth_templates must create src/components/auth/passkey-buttons.tsx."""
        render_auth_templates(tmp_path)
        expected = tmp_path / "src" / "components" / "auth" / "passkey-buttons.tsx"
        assert expected.exists(), f"Expected {expected} to exist after rendering"


class TestRenderAuthTemplatesReturnValue:
    """Tests for the return value of render_auth_templates()."""

    def test_returns_list_of_ten_paths(self, tmp_path):
        """render_auth_templates must return a list of exactly 10 paths (6 OAuth + 4 passkey)."""
        result = render_auth_templates(tmp_path)
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) == 10, f"Expected 10 paths, got {len(result)}: {result}"

    def test_returns_absolute_paths(self, tmp_path):
        """render_auth_templates must return absolute path strings."""
        result = render_auth_templates(tmp_path)
        for path_str in result:
            assert isinstance(path_str, str), f"Expected str, got {type(path_str)}"
            assert Path(path_str).is_absolute(), (
                f"Expected absolute path, got relative: {path_str}"
            )

    def test_returned_paths_exist(self, tmp_path):
        """All paths returned by render_auth_templates must exist on disk."""
        result = render_auth_templates(tmp_path)
        for path_str in result:
            assert Path(path_str).exists(), (
                f"Returned path does not exist: {path_str}"
            )

    def test_all_ten_output_files_in_returned_list(self, tmp_path):
        """All 10 expected output files must appear in the returned list."""
        result = render_auth_templates(tmp_path)
        result_set = set(result)

        expected_files = [
            # Original 6 OAuth templates
            tmp_path / "src" / "middleware.ts",
            tmp_path / "src" / "app" / "auth" / "login" / "page.tsx",
            tmp_path / "src" / "app" / "auth" / "signup" / "page.tsx",
            tmp_path / "src" / "app" / "auth" / "signout" / "page.tsx",
            tmp_path / "src" / "app" / "auth" / "callback" / "route.ts",
            tmp_path / "AUTH_SETUP.md",
            # 4 passkey templates
            tmp_path / "src" / "app" / "api" / "auth" / "passkey" / "register" / "route.ts",
            tmp_path / "src" / "app" / "api" / "auth" / "passkey" / "authenticate" / "route.ts",
            tmp_path / "src" / "lib" / "auth" / "passkey-hooks.ts",
            tmp_path / "src" / "components" / "auth" / "passkey-buttons.tsx",
        ]

        for expected in expected_files:
            assert str(expected) in result_set, (
                f"Expected {expected} in returned list, but it was not found.\n"
                f"Returned: {result}"
            )


class TestRenderAuthTemplatesContentIntegrity:
    """Tests that rendered file content matches the template source."""

    def test_middleware_content_matches_template(self, tmp_path):
        """Rendered middleware.ts must have identical content to auth-middleware.ts.tmpl."""
        render_auth_templates(tmp_path)
        template_content = (TEMPLATES_DIR / "auth-middleware.ts.tmpl").read_text(encoding="utf-8")
        rendered_content = (tmp_path / "src" / "middleware.ts").read_text(encoding="utf-8")
        assert rendered_content == template_content, (
            "Rendered middleware.ts content does not match template source"
        )

    def test_login_content_matches_template(self, tmp_path):
        """Rendered login/page.tsx must have identical content to login-page.tsx.tmpl."""
        render_auth_templates(tmp_path)
        template_content = (TEMPLATES_DIR / "auth" / "login-page.tsx.tmpl").read_text(encoding="utf-8")
        rendered_content = (tmp_path / "src" / "app" / "auth" / "login" / "page.tsx").read_text(encoding="utf-8")
        assert rendered_content == template_content, (
            "Rendered login/page.tsx content does not match template source"
        )

    def test_auth_setup_content_matches_template(self, tmp_path):
        """Rendered AUTH_SETUP.md must have identical content to AUTH_SETUP.md.tmpl."""
        render_auth_templates(tmp_path)
        template_content = (TEMPLATES_DIR / "auth" / "AUTH_SETUP.md.tmpl").read_text(encoding="utf-8")
        rendered_content = (tmp_path / "AUTH_SETUP.md").read_text(encoding="utf-8")
        assert rendered_content == template_content, (
            "Rendered AUTH_SETUP.md content does not match template source"
        )


class TestRenderAuthTemplatesDirectoryCreation:
    """Tests that render_auth_templates() creates parent directories."""

    def test_creates_nested_directories(self, tmp_path):
        """render_auth_templates must create deeply nested directories automatically."""
        # tmp_path is empty — no src/ directory exists yet
        assert not (tmp_path / "src").exists()
        render_auth_templates(tmp_path)
        # All intermediate directories should now exist
        assert (tmp_path / "src" / "app" / "auth" / "callback").is_dir()
        assert (tmp_path / "src" / "app" / "auth" / "login").is_dir()
        assert (tmp_path / "src" / "app" / "auth" / "signup").is_dir()
        assert (tmp_path / "src" / "app" / "auth" / "signout").is_dir()
        # Passkey directories
        assert (tmp_path / "src" / "app" / "api" / "auth" / "passkey" / "register").is_dir()
        assert (tmp_path / "src" / "app" / "api" / "auth" / "passkey" / "authenticate").is_dir()
        assert (tmp_path / "src" / "lib" / "auth").is_dir()
        assert (tmp_path / "src" / "components" / "auth").is_dir()

    def test_works_with_existing_directories(self, tmp_path):
        """render_auth_templates must not fail if output directories already exist."""
        # Pre-create some directories
        (tmp_path / "src" / "app" / "auth").mkdir(parents=True)
        # Should not raise even though directory exists
        render_auth_templates(tmp_path)
        assert (tmp_path / "src" / "middleware.ts").exists()

    def test_accepts_string_output_dir(self, tmp_path):
        """render_auth_templates must accept a string path (not just Path objects)."""
        result = render_auth_templates(str(tmp_path))
        assert len(result) == 10


class TestRenderAuthTemplatesErrorHandling:
    """Tests that render_auth_templates() raises appropriate errors."""

    def test_raises_file_not_found_for_missing_template(self, tmp_path, monkeypatch):
        """render_auth_templates must raise FileNotFoundError if a template is missing."""
        import web_app_factory._supabase_auth_renderer as renderer_module

        # Point TEMPLATE_DIR to an empty directory
        monkeypatch.setattr(renderer_module, "TEMPLATE_DIR", tmp_path)

        with pytest.raises(FileNotFoundError):
            render_auth_templates(tmp_path / "output")


# ---------------------------------------------------------------------------
# Tests for add_passkey_deps()
# ---------------------------------------------------------------------------

class TestAddPasskeyDeps:
    """Tests for add_passkey_deps() in _supabase_template_renderer.py."""

    def _make_package_json(self, tmp_path: Path, extra_deps: dict | None = None) -> Path:
        """Helper: create a minimal package.json and return its path."""
        data = {
            "name": "test-app",
            "version": "0.1.0",
            "dependencies": extra_deps or {},
        }
        p = tmp_path / "package.json"
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return p

    def test_adds_simplewebauthn_browser(self, tmp_path):
        """add_passkey_deps must add @simplewebauthn/browser to dependencies."""
        pkg = self._make_package_json(tmp_path)
        add_passkey_deps(pkg)
        data = json.loads(pkg.read_text(encoding="utf-8"))
        assert "@simplewebauthn/browser" in data["dependencies"], (
            "@simplewebauthn/browser must be added to dependencies"
        )

    def test_adds_simplewebauthn_server(self, tmp_path):
        """add_passkey_deps must add @simplewebauthn/server to dependencies."""
        pkg = self._make_package_json(tmp_path)
        add_passkey_deps(pkg)
        data = json.loads(pkg.read_text(encoding="utf-8"))
        assert "@simplewebauthn/server" in data["dependencies"], (
            "@simplewebauthn/server must be added to dependencies"
        )

    def test_preserves_existing_dependencies(self, tmp_path):
        """add_passkey_deps must not remove existing dependencies."""
        pkg = self._make_package_json(tmp_path, extra_deps={"react": "^18", "next": "14.0.0"})
        add_passkey_deps(pkg)
        data = json.loads(pkg.read_text(encoding="utf-8"))
        assert data["dependencies"]["react"] == "^18"
        assert data["dependencies"]["next"] == "14.0.0"

    def test_does_not_overwrite_existing_version(self, tmp_path):
        """add_passkey_deps must preserve existing @simplewebauthn version if already set."""
        pkg = self._make_package_json(
            tmp_path,
            extra_deps={"@simplewebauthn/browser": "^8.0.0"}
        )
        add_passkey_deps(pkg)
        data = json.loads(pkg.read_text(encoding="utf-8"))
        # Existing version should be preserved (not overwritten)
        assert data["dependencies"]["@simplewebauthn/browser"] == "^8.0.0"

    def test_creates_dependencies_key_if_missing(self, tmp_path):
        """add_passkey_deps must create the dependencies key if it does not exist."""
        data = {"name": "test-app", "version": "0.1.0"}
        pkg = tmp_path / "package.json"
        pkg.write_text(json.dumps(data, indent=2), encoding="utf-8")
        add_passkey_deps(pkg)
        result = json.loads(pkg.read_text(encoding="utf-8"))
        assert "dependencies" in result
        assert "@simplewebauthn/browser" in result["dependencies"]

    def test_accepts_string_path(self, tmp_path):
        """add_passkey_deps must accept a string path (not just Path objects)."""
        pkg = self._make_package_json(tmp_path)
        add_passkey_deps(str(pkg))  # Should not raise
        data = json.loads(pkg.read_text(encoding="utf-8"))
        assert "@simplewebauthn/browser" in data["dependencies"]


# ---------------------------------------------------------------------------
# Tests for login-page.tsx.tmpl including PasskeyButtons
# ---------------------------------------------------------------------------

class TestLoginPagePasskeyIntegration:
    """Tests that login-page.tsx.tmpl includes the PasskeyButtons component."""

    LOGIN_TMPL = TEMPLATES_DIR / "auth" / "login-page.tsx.tmpl"

    def test_login_page_imports_passkey_buttons(self):
        """login-page.tsx.tmpl must import the PasskeyButtons component."""
        content = self.LOGIN_TMPL.read_text(encoding="utf-8")
        assert "PasskeyButtons" in content, (
            "login-page.tsx.tmpl must import or reference the PasskeyButtons component"
        )

    def test_login_page_renders_passkey_buttons(self):
        """login-page.tsx.tmpl must render <PasskeyButtons> in JSX."""
        content = self.LOGIN_TMPL.read_text(encoding="utf-8")
        assert "<PasskeyButtons" in content, (
            "login-page.tsx.tmpl must render <PasskeyButtons in JSX"
        )


# ---------------------------------------------------------------------------
# Tests for signup-page.tsx.tmpl including passkey registration option
# ---------------------------------------------------------------------------

class TestSignupPagePasskeyIntegration:
    """Tests that signup-page.tsx.tmpl includes passkey registration option."""

    SIGNUP_TMPL = TEMPLATES_DIR / "auth" / "signup-page.tsx.tmpl"

    def test_signup_page_includes_passkey_reference(self):
        """signup-page.tsx.tmpl must include PasskeyButtons or passkey registration."""
        content = self.SIGNUP_TMPL.read_text(encoding="utf-8")
        has_passkey_buttons = "PasskeyButtons" in content
        has_passkey_ref = "passkey" in content.lower()
        assert has_passkey_buttons or has_passkey_ref, (
            "signup-page.tsx.tmpl must include passkey registration option"
        )
