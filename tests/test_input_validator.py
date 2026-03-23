"""Tests for input validation and injection rejection (MCPI-04).

These tests verify:
1. TestValidateSlug: valid slugs pass; injection characters, empty, too-long, traversal chars fail
2. TestValidateIdea: normal text passes; empty, too-long, null bytes fail
3. TestValidateProjectDir: valid path under output/ passes; path traversal raises ValueError
4. TestSafeShellArg: special characters are properly quoted
"""
from __future__ import annotations

import pytest


class TestValidateSlug:
    """validate_slug rejects shell injection characters and path traversal."""

    def test_valid_slug_passes(self):
        from web_app_factory._input_validator import validate_slug
        assert validate_slug("my-app") == "my-app"

    def test_single_char_valid(self):
        from web_app_factory._input_validator import validate_slug
        assert validate_slug("a") == "a"

    def test_alphanumeric_valid(self):
        from web_app_factory._input_validator import validate_slug
        assert validate_slug("MyApp123") == "MyApp123"

    def test_slug_with_underscores_valid(self):
        from web_app_factory._input_validator import validate_slug
        assert validate_slug("my_app") == "my_app"

    def test_injection_semicolon_rejected(self):
        from web_app_factory._input_validator import validate_slug
        with pytest.raises(ValueError):
            validate_slug("my;app")

    def test_injection_pipe_rejected(self):
        from web_app_factory._input_validator import validate_slug
        with pytest.raises(ValueError):
            validate_slug("my|app")

    def test_injection_ampersand_rejected(self):
        from web_app_factory._input_validator import validate_slug
        with pytest.raises(ValueError):
            validate_slug("my&app")

    def test_injection_backtick_rejected(self):
        from web_app_factory._input_validator import validate_slug
        with pytest.raises(ValueError):
            validate_slug("my`app")

    def test_injection_dollar_rejected(self):
        from web_app_factory._input_validator import validate_slug
        with pytest.raises(ValueError):
            validate_slug("my$app")

    def test_empty_slug_rejected(self):
        from web_app_factory._input_validator import validate_slug
        with pytest.raises(ValueError):
            validate_slug("")

    def test_too_long_rejected(self):
        from web_app_factory._input_validator import validate_slug
        with pytest.raises(ValueError):
            validate_slug("a" * 51)

    def test_max_length_passes(self):
        from web_app_factory._input_validator import validate_slug
        # 50 chars exactly — should pass
        result = validate_slug("a" * 50)
        assert result == "a" * 50

    def test_path_traversal_rejected(self):
        from web_app_factory._input_validator import validate_slug
        with pytest.raises(ValueError):
            validate_slug("../etc")

    def test_null_bytes_rejected(self):
        from web_app_factory._input_validator import validate_slug
        with pytest.raises(ValueError):
            validate_slug("app\x00name")

    def test_custom_field_name_in_error(self):
        from web_app_factory._input_validator import validate_slug
        with pytest.raises(ValueError, match="project_name"):
            validate_slug("", field_name="project_name")


class TestValidateIdea:
    """validate_idea accepts normal text, rejects null bytes and over-length."""

    def test_normal_text_passes(self):
        from web_app_factory._input_validator import validate_idea
        result = validate_idea("A recipe app")
        assert result == "A recipe app"

    def test_strips_whitespace(self):
        from web_app_factory._input_validator import validate_idea
        result = validate_idea("  trim me  ")
        assert result == "trim me"

    def test_empty_rejected(self):
        from web_app_factory._input_validator import validate_idea
        with pytest.raises(ValueError):
            validate_idea("")

    def test_whitespace_only_rejected(self):
        from web_app_factory._input_validator import validate_idea
        with pytest.raises(ValueError):
            validate_idea("   ")

    def test_too_long_rejected(self):
        from web_app_factory._input_validator import validate_idea
        with pytest.raises(ValueError):
            validate_idea("x" * 501)

    def test_max_length_passes(self):
        from web_app_factory._input_validator import validate_idea
        result = validate_idea("x" * 500)
        assert len(result) == 500

    def test_null_bytes_rejected(self):
        from web_app_factory._input_validator import validate_idea
        with pytest.raises(ValueError):
            validate_idea("has\x00null")

    def test_multiline_allowed(self):
        from web_app_factory._input_validator import validate_idea
        result = validate_idea("A todo app\nthat syncs with calendar")
        assert "todo" in result


class TestValidateProjectDir:
    """validate_project_dir blocks path traversal."""

    def test_valid_path_under_output(self, tmp_path):
        from web_app_factory._input_validator import validate_project_dir
        output_base = tmp_path / "output"
        output_base.mkdir()
        result = validate_project_dir("output/MyApp", output_base=output_base)
        assert "MyApp" in str(result)

    def test_path_traversal_rejected(self, tmp_path):
        from web_app_factory._input_validator import validate_project_dir
        output_base = tmp_path / "output"
        output_base.mkdir()
        with pytest.raises(ValueError):
            validate_project_dir("../../etc/passwd", output_base=output_base)

    def test_absolute_traversal_rejected(self, tmp_path):
        from web_app_factory._input_validator import validate_project_dir
        output_base = tmp_path / "output"
        output_base.mkdir()
        with pytest.raises(ValueError):
            validate_project_dir("/etc/passwd", output_base=output_base)

    def test_relative_path_is_allowed(self, tmp_path):
        from web_app_factory._input_validator import validate_project_dir
        output_base = tmp_path / "output"
        output_base.mkdir()
        # Should normalize and succeed
        result = validate_project_dir("output/./MyApp", output_base=output_base)
        assert result is not None


class TestSafeShellArg:
    """safe_shell_arg properly quotes special characters."""

    def test_simple_string_unchanged(self):
        from web_app_factory._input_validator import safe_shell_arg
        result = safe_shell_arg("hello")
        # shlex.quote wraps in single quotes for safety: 'hello'
        assert "hello" in result

    def test_spaces_are_quoted(self):
        from web_app_factory._input_validator import safe_shell_arg
        result = safe_shell_arg("hello world")
        # Must be quoted so shell treats it as single argument
        assert " " not in result or result.startswith("'") or result.startswith('"')

    def test_special_chars_are_quoted(self):
        from web_app_factory._input_validator import safe_shell_arg
        result = safe_shell_arg("my;app&name")
        # Result should be a quoted string containing the original
        assert ";" not in result.strip("'\"") or result.startswith("'")

    def test_empty_string_is_quoted(self):
        from web_app_factory._input_validator import safe_shell_arg
        result = safe_shell_arg("")
        # shlex.quote("") returns "''" (two single quotes)
        assert result == "''"
