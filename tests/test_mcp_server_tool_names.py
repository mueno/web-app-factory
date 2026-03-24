"""CI assertion tests for MCP tool namespace conventions.

Phase 8, Plan 01 — MCP Infrastructure Foundation
Updated Phase 16, Plan 02 — HTTP transport coverage added

These tests enforce invariants that must hold for the lifetime of the project:

1. All public stdio tools (web_app_factory.mcp_server) use the ``waf_`` prefix.
2. No tool name collision exists between the internal and public servers.
3. Internal tools (tools.factory_mcp_server) do NOT use the ``waf_`` prefix
   (that namespace is reserved exclusively for the public API).
4. All HTTP server tools (web_app_factory.openai_mcp_server) use the ``waf_`` prefix.
5. No tool name collision between the HTTP and internal servers.
6. HTTP and stdio servers expose the exact same set of tools.

With zero tools registered in Phase 8 the first and third tests pass
vacuously; the assertions become meaningful as tools are added in
Phases 9-12.

FastMCP version used during verification: >=3.1.0
Verified API: asyncio.run(mcp.list_tools()) → list[FunctionTool]
Each FunctionTool has a `.name` attribute containing the tool name string.
The older _tool_manager._tools dict path does not exist in fastmcp >=3.x.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path so that `tools.*` can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _get_tool_names(mcp_instance) -> set[str]:
    """Extract registered tool names from a FastMCP instance.

    FastMCP >=3.1.0 API (verified 2026-03-23):
      mcp.list_tools() is an async method returning list[FunctionTool].
      Each FunctionTool has a .name attribute.

    This uses asyncio.run() which works in non-async test contexts.
    If tests run inside an already-running event loop (e.g. pytest-asyncio),
    switch to ``await mcp.list_tools()`` in an async test instead.
    """
    list_fn = getattr(mcp_instance, "list_tools", None)
    if list_fn is None:
        raise AttributeError(
            f"FastMCP instance {mcp_instance!r} has no list_tools() method. "
            "Check the fastmcp version and update _get_tool_names()."
        )
    tools = asyncio.run(list_fn())
    return {t.name for t in tools}


class TestToolNameConventions:
    """Enforce waf_ namespace and no inter-server collisions."""

    @pytest.fixture(scope="class")
    def public_mcp(self):
        """Load the public stdio MCP server instance."""
        from web_app_factory.mcp_server import mcp as _pub
        return _pub

    @pytest.fixture(scope="class")
    def internal_mcp(self):
        """Load the internal factory MCP server instance."""
        from tools.factory_mcp_server import mcp as _int
        return _int

    @pytest.fixture(scope="class")
    def http_mcp(self):
        """Load the HTTP MCP server instance."""
        from web_app_factory.openai_mcp_server import mcp as _http
        return _http

    def test_public_tools_have_waf_prefix(self, public_mcp):
        """Every tool registered on the public stdio server must use the waf_ prefix.

        In Phase 8 there are zero tools — the test passes vacuously and acts as
        a sentinel: any future tool registered without waf_ will fail CI here.
        """
        tool_names = _get_tool_names(public_mcp)
        violations = {name for name in tool_names if not name.startswith("waf_")}
        assert not violations, (
            f"Public MCP tools without 'waf_' prefix: {violations!r}. "
            "All public tools MUST use the waf_ namespace."
        )

    def test_no_tool_name_collision_between_servers(self, public_mcp, internal_mcp):
        """No tool name must appear in both the public and internal servers."""
        public_names = _get_tool_names(public_mcp)
        internal_names = _get_tool_names(internal_mcp)
        collision = public_names & internal_names
        assert not collision, (
            f"Tool name collision between servers: {collision!r}. "
            "Tool names must be unique across internal and public MCP servers."
        )

    def test_internal_tools_have_distinct_namespace(self, internal_mcp):
        """Internal tools must NOT use the waf_ prefix (reserved for public API).

        This guards against accidentally registering a public-style tool on the
        internal server, which would pollute the internal server's namespace.
        """
        internal_names = _get_tool_names(internal_mcp)
        violations = {name for name in internal_names if name.startswith("waf_")}
        assert not violations, (
            f"Internal MCP tools using reserved 'waf_' prefix: {violations!r}. "
            "The waf_ namespace is reserved for the public web_app_factory MCP server."
        )

    def test_http_tools_have_waf_prefix(self, http_mcp):
        """Every tool on the HTTP server must use the waf_ prefix."""
        tool_names = _get_tool_names(http_mcp)
        violations = {name for name in tool_names if not name.startswith("waf_")}
        assert not violations, (
            f"HTTP MCP tools without 'waf_' prefix: {violations!r}. "
            "All public tools MUST use the waf_ namespace."
        )

    def test_no_tool_name_collision_http_internal(self, http_mcp, internal_mcp):
        """No tool name must appear in both the HTTP and internal servers."""
        http_names = _get_tool_names(http_mcp)
        internal_names = _get_tool_names(internal_mcp)
        collision = http_names & internal_names
        assert not collision, (
            f"Tool name collision between HTTP and internal servers: {collision!r}."
        )

    def test_http_stdio_tool_parity(self, public_mcp, http_mcp):
        """HTTP and stdio servers must expose the exact same set of tools."""
        stdio_names = _get_tool_names(public_mcp)
        http_names = _get_tool_names(http_mcp)
        assert stdio_names == http_names, (
            f"Tool set mismatch. stdio-only: {stdio_names - http_names}, "
            f"http-only: {http_names - stdio_names}"
        )
