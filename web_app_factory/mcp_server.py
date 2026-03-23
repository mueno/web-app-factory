"""Public MCP server for Web App Factory.

Entry point: ``web-app-factory-mcp`` (declared in pyproject.toml).
Transport: stdio (compatible with Claude Desktop and uvx invocation).

Tool namespace convention:
  ALL tools registered on this server MUST use the ``waf_`` prefix.
  This is enforced by tests/test_mcp_server_tool_names.py — any tool
  registered without the prefix will cause CI to fail.

Phase 8 (MCP Infrastructure Foundation):
  Only the server skeleton is created here.  Tools are added in
  Phase 9 (waf_generate_app, waf_get_status, waf_list_runs).
"""

from __future__ import annotations

from fastmcp import FastMCP

# Public server — all tools must use waf_ prefix.
# Name must stay "web-app-factory" (used in entry-point tests and collision checks).
mcp = FastMCP(
    "web-app-factory",
    instructions=(
        "Web App Factory: generate full-stack Next.js apps from ideas. "
        "All tools prefixed waf_. Start with waf_generate_app."
    ),
)

# ── No tools registered in Phase 8 ────────────────────────────
# Tools are added in later phases.  The namespace constraint test
# (test_mcp_server_tool_names.py) passes vacuously with zero tools
# and will catch any future tool registered without the waf_ prefix.


def main() -> None:
    """Entry point for the ``web-app-factory-mcp`` console script."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
