"""Tests for web_app_factory/_supabase_auth_renderer.py.

Verifies that render_auth_templates() correctly renders all 6 auth templates
into the correct output paths within a generated app directory.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from web_app_factory._supabase_auth_renderer import render_auth_templates

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


class TestRenderAuthTemplatesReturnValue:
    """Tests for the return value of render_auth_templates()."""

    def test_returns_list_of_six_paths(self, tmp_path):
        """render_auth_templates must return a list of exactly 6 paths."""
        result = render_auth_templates(tmp_path)
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) == 6, f"Expected 6 paths, got {len(result)}: {result}"

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

    def test_all_six_output_files_in_returned_list(self, tmp_path):
        """All 6 expected output files must appear in the returned list."""
        result = render_auth_templates(tmp_path)
        result_set = set(result)

        expected_files = [
            tmp_path / "src" / "middleware.ts",
            tmp_path / "src" / "app" / "auth" / "login" / "page.tsx",
            tmp_path / "src" / "app" / "auth" / "signup" / "page.tsx",
            tmp_path / "src" / "app" / "auth" / "signout" / "page.tsx",
            tmp_path / "src" / "app" / "auth" / "callback" / "route.ts",
            tmp_path / "AUTH_SETUP.md",
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
        assert len(result) == 6


class TestRenderAuthTemplatesErrorHandling:
    """Tests that render_auth_templates() raises appropriate errors."""

    def test_raises_file_not_found_for_missing_template(self, tmp_path, monkeypatch):
        """render_auth_templates must raise FileNotFoundError if a template is missing."""
        import web_app_factory._supabase_auth_renderer as renderer_module

        # Point TEMPLATE_DIR to an empty directory
        monkeypatch.setattr(renderer_module, "TEMPLATE_DIR", tmp_path)

        with pytest.raises(FileNotFoundError):
            render_auth_templates(tmp_path / "output")
