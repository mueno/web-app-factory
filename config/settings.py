"""Centralized runtime settings for web-app-factory.

All paths can be overridden by environment variables to keep the project
portable across local machines and CI.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    """Return an env-overridden path with `~` expansion."""
    value = os.environ.get(name)
    if value:
        return Path(value).expanduser()
    return default.expanduser()


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Approval gate ──────────────────────────────────────────────
# Used by MCP server for file-based polling approval flow.
APPROVAL_TMP_DIR = _env_path("WEB_FACTORY_APPROVAL_DIR", Path("/tmp"))

# Directory where waf_approve_gate writes gate-response JSON files and
# mcp_approval_gate reads them. Single source of truth shared by both.
# Override with WEB_FACTORY_GATE_RESPONSES_DIR for custom paths in CI/tests.
GATE_RESPONSES_DIR = _env_path(
    "WEB_FACTORY_GATE_RESPONSES_DIR",
    PROJECT_ROOT / "output" / ".gate-responses",
)

# ── Web deployment defaults ────────────────────────────────────
DEFAULT_FRAMEWORK = os.environ.get("WEB_FACTORY_FRAMEWORK", "nextjs")
DEFAULT_DEPLOY_TARGET = os.environ.get("WEB_FACTORY_DEPLOY_TARGET", "vercel")

VERCEL_CONFIG_DIR = _env_path(
    "WEB_FACTORY_VERCEL_CONFIG_DIR",
    Path.home() / ".config" / "vercel",
)

# ── MCP server script ──────────────────────────────────────────
FACTORY_MCP_SCRIPT = PROJECT_ROOT / "tools" / "run-factory-mcp.sh"
