"""Tests for factory.py CLI argument parsing."""

from __future__ import annotations

import sys
import pytest


def parse_args_from(argv: list[str]):
    """Import and call parse_args from factory.py with the given argv."""
    import importlib
    if "factory" in sys.modules:
        del sys.modules["factory"]
    sys.path.insert(0, "/Users/masa/Development/web-app-factory")
    import factory as _factory
    return _factory.parse_args(argv)


class TestFactoryCLIFlags:
    """Test CLI flag parsing for factory.py."""

    def test_idea_from_named_flag(self):
        args = parse_args_from(["--idea", "test app"])
        assert args.idea == "test app"

    def test_idea_from_positional(self):
        args = parse_args_from(["my cool app"])
        assert args.idea == "my cool app"

    def test_project_dir_flag(self):
        args = parse_args_from(["--idea", "test app", "--project-dir", "./output/Test"])
        assert args.project_dir == "./output/Test"

    def test_deploy_target_default(self):
        args = parse_args_from(["test"])
        assert args.deploy_target == "vercel"

    def test_deploy_target_flag(self):
        args = parse_args_from(["--deploy-target", "vercel", "test"])
        assert args.deploy_target == "vercel"

    def test_deploy_target_github_pages(self):
        args = parse_args_from(["--deploy-target", "github-pages", "test"])
        assert args.deploy_target == "github-pages"

    def test_framework_default(self):
        args = parse_args_from(["test"])
        assert args.framework == "nextjs"

    def test_framework_flag(self):
        args = parse_args_from(["--framework", "nextjs", "test"])
        assert args.framework == "nextjs"

    def test_dry_run_flag(self):
        args = parse_args_from(["test", "--dry-run"])
        assert args.dry_run is True

    def test_dry_run_default_false(self):
        args = parse_args_from(["test"])
        assert args.dry_run is False

    def test_resume_flag(self):
        args = parse_args_from(["test", "--resume", "20260321-120000-test"])
        assert args.resume == "20260321-120000-test"

    def test_resume_default_none(self):
        args = parse_args_from(["test"])
        assert args.resume is None

    def test_project_dir_derived_from_idea(self):
        """When --project-dir is not provided, project_dir should be derived."""
        import factory as _factory
        args = parse_args_from(["my cool app"])
        project_dir = _factory.resolve_project_dir(args)
        # Should be based on the idea slug
        assert "my" in project_dir.lower() or "cool" in project_dir.lower()
        assert "./output/" in project_dir or "output" in project_dir

    def test_project_dir_not_derived_when_specified(self):
        args = parse_args_from(["--idea", "test", "--project-dir", "./output/Custom"])
        import factory as _factory
        project_dir = _factory.resolve_project_dir(args)
        assert project_dir == "./output/Custom"
