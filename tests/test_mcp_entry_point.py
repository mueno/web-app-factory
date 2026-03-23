"""Smoke tests: entry point resolves and server skeleton loads correctly.

Phase 8, Plan 01 — MCP Infrastructure Foundation
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_mcp_server_importable():
    """web_app_factory.mcp_server must be importable."""
    mod = importlib.import_module("web_app_factory.mcp_server")
    assert mod is not None


def test_mcp_instance_exported():
    """mcp_server must export a `mcp` attribute (FastMCP instance)."""
    from web_app_factory.mcp_server import mcp
    assert mcp is not None


def test_mcp_name_is_web_app_factory():
    """FastMCP instance must be named 'web-app-factory'."""
    from web_app_factory.mcp_server import mcp
    assert mcp.name == "web-app-factory"


def test_main_callable():
    """mcp_server must export a callable `main` function."""
    from web_app_factory.mcp_server import main
    assert callable(main)


def test_entry_point_resolves():
    """pyproject.toml entry point 'web-app-factory-mcp' must resolve to web_app_factory.mcp_server:main."""
    import importlib.metadata
    try:
        eps = importlib.metadata.entry_points(group="console_scripts")
        # Filter to web-app-factory-mcp
        matching = [ep for ep in eps if ep.name == "web-app-factory-mcp"]
        assert len(matching) == 1, (
            f"Expected 1 entry point 'web-app-factory-mcp', found {len(matching)}. "
            "Run `uv pip install -e .` to register entry points."
        )
        ep = matching[0]
        assert ep.value == "web_app_factory.mcp_server:main", (
            f"Entry point value mismatch: {ep.value!r}"
        )
    except importlib.metadata.PackageNotFoundError:
        raise AssertionError(
            "Package 'web-app-factory' not installed. Run `uv pip install -e .`"
        )


def test_package_version():
    """web_app_factory package must expose __version__."""
    import web_app_factory
    assert hasattr(web_app_factory, "__version__"), "web_app_factory must define __version__"
    assert web_app_factory.__version__ == "0.1.0"
