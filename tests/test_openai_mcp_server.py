"""Smoke tests for the HTTP transport MCP server (openai_mcp_server).

Phase 16, Plan 02 — HTTP Transport for OpenAI Apps distribution

Verifies:
- openai_mcp_server module is importable
- mcp attribute exists (FastMCP instance named 'web-app-factory')
- main function exists and is callable
- HTTP server has exactly 7 tools
- All 7 tool names match the stdio server tool names (same set)
- All 7 HTTP tools have non-None readOnlyHint, destructiveHint, openWorldHint
- HTTP tool annotations match stdio tool annotations (same values per tool)
- Entry point 'web-app-factory-mcp-http' resolves to openai_mcp_server:main
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_TOOL_COUNT = 7


# ── Module-level fixtures ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def http_tool_map():
    """Return dict of tool_name → tool object from the HTTP mcp instance."""
    from web_app_factory.openai_mcp_server import mcp as http_mcp
    tools = asyncio.run(http_mcp.list_tools())
    return {t.name: t for t in tools}


@pytest.fixture(scope="module")
def stdio_tool_map():
    """Return dict of tool_name → tool object from the stdio mcp instance."""
    from web_app_factory.mcp_server import mcp as stdio_mcp
    tools = asyncio.run(stdio_mcp.list_tools())
    return {t.name: t for t in tools}


# ── Importability and structure ───────────────────────────────────────────────

def test_openai_mcp_server_importable():
    """web_app_factory.openai_mcp_server must be importable."""
    mod = importlib.import_module("web_app_factory.openai_mcp_server")
    assert mod is not None


def test_mcp_attribute_exists():
    """openai_mcp_server must export a `mcp` attribute (FastMCP instance)."""
    from web_app_factory.openai_mcp_server import mcp
    assert mcp is not None


def test_mcp_name_is_web_app_factory():
    """FastMCP instance must be named 'web-app-factory'."""
    from web_app_factory.openai_mcp_server import mcp
    assert mcp.name == "web-app-factory"


def test_main_function_exists_and_callable():
    """openai_mcp_server must export a callable `main` function."""
    from web_app_factory.openai_mcp_server import main
    assert callable(main)


# ── Tool count and names ──────────────────────────────────────────────────────

def test_http_server_has_exactly_7_tools(http_tool_map):
    """HTTP server must have exactly 7 tools."""
    assert len(http_tool_map) == EXPECTED_TOOL_COUNT, (
        f"Expected {EXPECTED_TOOL_COUNT} tools, found {len(http_tool_map)}: "
        f"{sorted(http_tool_map.keys())}"
    )


def test_all_http_tool_names_have_waf_prefix(http_tool_map):
    """Every tool on the HTTP server must use the waf_ prefix."""
    violations = {name for name in http_tool_map if not name.startswith("waf_")}
    assert not violations, (
        f"HTTP MCP tools without 'waf_' prefix: {violations!r}. "
        "All public tools MUST use the waf_ namespace."
    )


def test_http_tool_names_match_stdio(http_tool_map, stdio_tool_map):
    """HTTP server must expose exactly the same set of tools as the stdio server."""
    stdio_names = set(stdio_tool_map.keys())
    http_names = set(http_tool_map.keys())
    assert stdio_names == http_names, (
        f"Tool set mismatch.\n"
        f"stdio-only: {stdio_names - http_names}\n"
        f"http-only: {http_names - stdio_names}"
    )


# ── Annotation completeness ───────────────────────────────────────────────────

def test_all_http_tools_have_annotations(http_tool_map):
    """Every HTTP tool must have non-None annotations."""
    failures = []
    for name, tool in http_tool_map.items():
        if not hasattr(tool, "annotations") or tool.annotations is None:
            failures.append(f"{name}: annotations is None")
    assert not failures, "HTTP tools missing annotations:\n" + "\n".join(failures)


def test_all_http_tools_have_required_hint_fields(http_tool_map):
    """Every HTTP tool must have readOnlyHint, destructiveHint, openWorldHint set to non-None."""
    required_fields = ["readOnlyHint", "destructiveHint", "openWorldHint"]
    failures = []
    for name, tool in http_tool_map.items():
        ann = getattr(tool, "annotations", None)
        if ann is None:
            failures.append(f"{name}: annotations is None")
            continue
        for field in required_fields:
            value = getattr(ann, field, None)
            if value is None:
                failures.append(f"{name}.{field} is None (must be True or False)")
    assert not failures, "HTTP tools with missing annotation fields:\n" + "\n".join(failures)


# ── Annotation parity with stdio ─────────────────────────────────────────────

def test_http_annotation_values_match_stdio(http_tool_map, stdio_tool_map):
    """HTTP tool annotations must match stdio tool annotations for each tool."""
    hint_fields = ["readOnlyHint", "destructiveHint", "openWorldHint"]
    mismatches = []
    for name in stdio_tool_map:
        http_tool = http_tool_map.get(name)
        stdio_tool = stdio_tool_map[name]
        if http_tool is None:
            mismatches.append(f"{name}: missing from HTTP server")
            continue
        http_ann = getattr(http_tool, "annotations", None)
        stdio_ann = getattr(stdio_tool, "annotations", None)
        if http_ann is None:
            mismatches.append(f"{name}: HTTP annotations is None")
            continue
        if stdio_ann is None:
            mismatches.append(f"{name}: stdio annotations is None")
            continue
        for field in hint_fields:
            http_val = getattr(http_ann, field, None)
            stdio_val = getattr(stdio_ann, field, None)
            if http_val != stdio_val:
                mismatches.append(
                    f"{name}.{field}: HTTP={http_val!r}, stdio={stdio_val!r}"
                )
    assert not mismatches, "Annotation parity failures:\n" + "\n".join(mismatches)


# ── Entry point ───────────────────────────────────────────────────────────────

def test_http_entry_point_resolves():
    """pyproject.toml entry point 'web-app-factory-mcp-http' must resolve to openai_mcp_server:main."""
    import importlib.metadata
    try:
        eps = importlib.metadata.entry_points(group="console_scripts")
        matching = [ep for ep in eps if ep.name == "web-app-factory-mcp-http"]
        assert len(matching) == 1, (
            f"Expected 1 entry point 'web-app-factory-mcp-http', found {len(matching)}. "
            "Run `uv pip install -e .` to register entry points."
        )
        ep = matching[0]
        assert ep.value == "web_app_factory.openai_mcp_server:main", (
            f"Entry point value mismatch: {ep.value!r}. "
            "Expected 'web_app_factory.openai_mcp_server:main'."
        )
    except importlib.metadata.PackageNotFoundError:
        raise AssertionError(
            "Package 'web-app-factory' not installed. Run `uv pip install -e .`"
        )
