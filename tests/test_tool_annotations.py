"""Tests for ToolAnnotations on the stdio MCP server.

Phase 16, Plan 01 — MCP Infrastructure Hardening

Verifies that every tool on the stdio `mcp` instance has ToolAnnotations
with required safety hint fields set to non-None values, and spot-checks
specific annotation values for key tools.

FastMCP version: >=3.1.0
API pattern: asyncio.run(mcp.list_tools()) → list[FunctionTool]
Each FunctionTool has .name and .annotations attributes.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# All 7 expected tool names
EXPECTED_TOOLS = [
    "waf_generate_app",
    "waf_get_status",
    "waf_approve_gate",
    "waf_list_runs",
    "waf_start_dev_server",
    "waf_stop_dev_server",
    "waf_check_env",
]

# Expected specific annotation values (from safety classification table)
EXPECTED_ANNOTATION_VALUES = {
    "waf_get_status": {"readOnlyHint": True},
    "waf_stop_dev_server": {"destructiveHint": True},
    "waf_generate_app": {"openWorldHint": True},
}


@pytest.fixture(scope="module")
def tool_map():
    """Return a dict of tool_name → tool object from the stdio mcp instance."""
    from web_app_factory.mcp_server import mcp
    tools = asyncio.run(mcp.list_tools())
    return {t.name: t for t in tools}


def test_all_expected_tools_present(tool_map):
    """All 7 waf_* tools must be registered on the stdio server."""
    missing = set(EXPECTED_TOOLS) - set(tool_map.keys())
    assert not missing, f"Missing tools: {missing}"


def test_all_tools_have_annotations(tool_map):
    """Every tool must have annotations (not None)."""
    failures = []
    for name in EXPECTED_TOOLS:
        tool = tool_map.get(name)
        if tool is None:
            failures.append(f"{name}: tool not found")
            continue
        if not hasattr(tool, "annotations") or tool.annotations is None:
            failures.append(f"{name}: annotations is None")
    assert not failures, "Tools missing annotations:\n" + "\n".join(failures)


def test_all_tools_have_required_hint_fields(tool_map):
    """Every tool must have readOnlyHint, destructiveHint, openWorldHint set to non-None."""
    required_fields = ["readOnlyHint", "destructiveHint", "openWorldHint"]
    failures = []
    for name in EXPECTED_TOOLS:
        tool = tool_map.get(name)
        if tool is None:
            failures.append(f"{name}: tool not found")
            continue
        ann = getattr(tool, "annotations", None)
        if ann is None:
            failures.append(f"{name}: annotations is None")
            continue
        for field in required_fields:
            value = getattr(ann, field, None)
            if value is None:
                failures.append(f"{name}.{field} is None (must be True or False)")
    assert not failures, "Tools with missing annotation fields:\n" + "\n".join(failures)


def test_get_status_is_readonly(tool_map):
    """waf_get_status must have readOnlyHint=True."""
    tool = tool_map.get("waf_get_status")
    assert tool is not None, "waf_get_status not found"
    ann = tool.annotations
    assert ann is not None, "waf_get_status annotations is None"
    assert ann.readOnlyHint is True, (
        f"waf_get_status.readOnlyHint expected True, got {ann.readOnlyHint!r}"
    )


def test_stop_dev_server_is_destructive(tool_map):
    """waf_stop_dev_server must have destructiveHint=True."""
    tool = tool_map.get("waf_stop_dev_server")
    assert tool is not None, "waf_stop_dev_server not found"
    ann = tool.annotations
    assert ann is not None, "waf_stop_dev_server annotations is None"
    assert ann.destructiveHint is True, (
        f"waf_stop_dev_server.destructiveHint expected True, got {ann.destructiveHint!r}"
    )


def test_generate_app_is_open_world(tool_map):
    """waf_generate_app must have openWorldHint=True."""
    tool = tool_map.get("waf_generate_app")
    assert tool is not None, "waf_generate_app not found"
    ann = tool.annotations
    assert ann is not None, "waf_generate_app annotations is None"
    assert ann.openWorldHint is True, (
        f"waf_generate_app.openWorldHint expected True, got {ann.openWorldHint!r}"
    )
