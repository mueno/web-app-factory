"""Environment detection and install module for web-app-factory.

Provides the business logic for the `waf_check_env` MCP tool (Plan 02).
All detection logic is decoupled from MCP concerns for testability.

Security notes:
- install_tool validates against an allowlist before any subprocess call (ENVS-03).
- All subprocess calls use list args (no shell=True) — audited by test_subprocess_audit.py.
- Credential values are never logged — only key names per security-core.md contract.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Any

from pipeline_runtime.startup_preflight import (
    _check_nodejs,
    _check_npm,
    _check_python_version,
    _check_vercel_cli,
)
from web_app_factory._keychain import get_credential

import shutil

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ToolStatus type alias
# ---------------------------------------------------------------------------
# Each ToolStatus dict has these keys:
#   tool:             str — logical tool name ("node", "npm", "python", "vercel", "gcloud")
#   status:           str — one of "present", "outdated", "missing", "present_unauth"
#   version_found:    str | None
#   version_required: str | None
#   install_command:  str | None — human-readable install instruction
#   note:             str | None — optional informational message


# ---------------------------------------------------------------------------
# Version requirements
# ---------------------------------------------------------------------------
_NODE_VERSION_REQUIRED = ">= 20.9.0"
_PYTHON_VERSION_REQUIRED = ">= 3.10"


# ---------------------------------------------------------------------------
# Platform-aware install command tables
# ---------------------------------------------------------------------------
# Human-readable install instructions (for display). Keyed by (tool, platform).
_INSTALL_COMMANDS: dict[tuple[str, str], str] = {
    # node — macOS
    ("node", "darwin"): "brew install node  # installs Node.js >= LTS",
    # node — Linux
    ("node", "linux"): (
        "# Use NodeSource for a specific version:\n"
        "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -\n"
        "sudo apt-get install -y nodejs\n"
        "# OR use nvm: https://github.com/nvm-sh/nvm"
    ),
    # npm comes bundled with Node.js
    ("npm", "darwin"): "npm comes with Node.js — install Node.js first: brew install node",
    ("npm", "linux"): (
        "npm comes with Node.js — install Node.js first via NodeSource:\n"
        "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -\n"
        "sudo apt-get install -y nodejs"
    ),
    # vercel CLI
    ("vercel", "darwin"): "npm install -g vercel",
    ("vercel", "linux"): "npm install -g vercel",
    # gcloud CLI
    ("gcloud", "darwin"): "brew install --cask google-cloud-sdk",
    ("gcloud", "linux"): (
        "# Follow official guide: https://cloud.google.com/sdk/docs/install\n"
        "curl https://sdk.cloud.google.com | bash"
    ),
}

# Subprocess-safe list-form args for tools that support single-command auto-install.
# Missing entries mean "no automated install — show manual instructions".
_INSTALL_ARGS: dict[tuple[str, str], list[str]] = {
    # vercel: auto-installable on both platforms via npm
    ("vercel", "darwin"): ["npm", "install", "-g", "vercel"],
    ("vercel", "linux"): ["npm", "install", "-g", "vercel"],
    # node on macOS: auto-installable via Homebrew
    ("node", "darwin"): ["brew", "install", "node"],
    # node on Linux: no simple single-command install; show manual instructions
    # gcloud on macOS: Homebrew cask
    ("gcloud", "darwin"): ["brew", "install", "--cask", "google-cloud-sdk"],
    # gcloud on Linux: no simple single-command install
}

# ---------------------------------------------------------------------------
# Allowlist for install_tool — prevents injection via tool_to_install parameter
# ---------------------------------------------------------------------------
_INSTALLABLE_TOOLS: frozenset[str] = frozenset({"node", "npm", "vercel", "gcloud"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _platform_key() -> str:
    """Return 'darwin' or 'linux' based on sys.platform. Defaults to 'linux'."""
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def _build_tool_status(
    tool: str,
    raw: dict[str, Any],
    *,
    version_required: str | None = None,
    extra_note: str | None = None,
) -> dict[str, Any]:
    """Convert a raw preflight check dict into a ToolStatus dict.

    Args:
        tool: Logical tool name (e.g. "node", "npm").
        raw: Dict from _check_nodejs/_check_npm/_check_python_version/_check_vercel_cli.
        version_required: Human-readable minimum version string for display.
        extra_note: Optional informational note (e.g. Vercel scope warning).

    Returns:
        ToolStatus dict with keys: tool, status, version_found, version_required,
        install_command, note.
    """
    passed = bool(raw.get("passed"))
    version_found = raw.get("version")
    reason = raw.get("reason") or ""
    platform = _platform_key()

    if passed:
        status = "present"
        install_command = None
    elif version_found is not None and "too old" in reason.lower():
        # Tool is present but outdated
        status = "outdated"
        install_command = _INSTALL_COMMANDS.get((tool, platform))
    else:
        # Tool is absent
        status = "missing"
        install_command = _INSTALL_COMMANDS.get((tool, platform))

    return {
        "tool": tool,
        "status": status,
        "version_found": version_found,
        "version_required": version_required,
        "install_command": install_command,
        "note": extra_note,
    }


def _check_gcloud() -> dict[str, Any]:
    """Detect gcloud CLI presence, version, and auth status.

    Returns a ToolStatus dict for gcloud.
    """
    platform = _platform_key()
    tool = "gcloud"

    # Check presence via shutil.which
    gcloud_path = shutil.which("gcloud")
    if gcloud_path is None:
        return {
            "tool": tool,
            "status": "missing",
            "version_found": None,
            "version_required": None,
            "install_command": _INSTALL_COMMANDS.get((tool, platform)),
            "note": None,
        }

    # Check version
    version_found: str | None = None
    try:
        proc = subprocess.run(
            ["gcloud", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode == 0:
            # Extract first line: "Google Cloud SDK 420.0.0"
            first_line = (proc.stdout or "").strip().splitlines()[0] if proc.stdout else ""
            version_found = first_line or None
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("gcloud --version failed: %s", type(exc).__name__)

    # Check auth via imported function
    note: str | None = None
    status = "present"
    try:
        from tools.deploy_providers.gcp_provider import _check_gcloud_auth

        ok, err_msg = _check_gcloud_auth()
        if not ok:
            note = f"Auth issue: {err_msg}"
            status = "present_unauth"
    except Exception as exc:  # noqa: BLE001
        logger.debug("gcloud auth check failed: %s", type(exc).__name__)

    return {
        "tool": tool,
        "status": status,
        "version_found": version_found,
        "version_required": None,
        "install_command": None,
        "note": note,
    }


def _check_supabase_credentials() -> list[dict[str, Any]]:
    """Check for required Supabase API credentials.

    Checks two credentials:
    - supabase_access_token (SUPABASE_ACCESS_TOKEN)
    - supabase_org_id (SUPABASE_ORG_ID)

    Uses get_credential() which implements 3-tier lookup: banto -> keyring -> env var.

    Returns:
        List of 2 ToolStatus dicts, one per credential.
    """
    statuses: list[dict[str, Any]] = []

    creds = [
        {
            "key": "supabase_access_token",
            "tool": "supabase-access-token",
            "env_var": "SUPABASE_ACCESS_TOKEN",
            "banto_cmd": "banto store supabase-access-token",
        },
        {
            "key": "supabase_org_id",
            "tool": "supabase-org-id",
            "env_var": "SUPABASE_ORG_ID",
            "banto_cmd": "banto store supabase-org-id",
        },
    ]

    for cred in creds:
        value = get_credential(cred["key"])
        if value is not None:
            statuses.append({
                "tool": cred["tool"],
                "status": "present",
                "version_found": None,
                "version_required": None,
                "install_command": None,
                "note": None,
            })
        else:
            statuses.append({
                "tool": cred["tool"],
                "status": "missing",
                "version_found": None,
                "version_required": None,
                "install_command": None,
                "note": (
                    f"{cred['tool']} not set. "
                    f"Run: {cred['banto_cmd']}  "
                    f"OR  export {cred['env_var']}=<your-value>"
                ),
            })

    return statuses


def _check_oauth_credentials() -> list[dict[str, Any]]:
    """Check for optional OAuth credentials (Google and Apple).

    These are advisory checks — OAuth is optional. Users can add OAuth later.
    Checks 4 env vars: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, APPLE_CLIENT_ID,
    APPLE_CLIENT_SECRET.

    Returns:
        List of 4 ToolStatus dicts, one per OAuth credential. Missing credentials
        have status="missing" with advisory note (not blocking).
    """
    statuses: list[dict[str, Any]] = []

    creds = [
        {
            "tool": "google-client-id",
            "env_var": "GOOGLE_CLIENT_ID",
            "note_if_missing": (
                "Advisory: GOOGLE_CLIENT_ID not set. "
                "Set from Google Cloud Console > APIs & Services > Credentials. "
                "OAuth sign-in will be unavailable until configured."
            ),
        },
        {
            "tool": "google-client-secret",
            "env_var": "GOOGLE_CLIENT_SECRET",
            "note_if_missing": (
                "Advisory: GOOGLE_CLIENT_SECRET not set. "
                "Set from Google Cloud Console > APIs & Services > Credentials. "
                "OAuth sign-in will be unavailable until configured."
            ),
        },
        {
            "tool": "apple-client-id",
            "env_var": "APPLE_CLIENT_ID",
            "note_if_missing": (
                "Advisory: APPLE_CLIENT_ID not set. "
                "Set from Apple Developer Console > Certificates, Identifiers & Profiles. "
                "Sign in with Apple will be unavailable until configured."
            ),
        },
        {
            "tool": "apple-client-secret",
            "env_var": "APPLE_CLIENT_SECRET",
            "note_if_missing": (
                "Advisory: APPLE_CLIENT_SECRET not set. "
                "Set from Apple Developer Console. "
                "Sign in with Apple will be unavailable until configured."
            ),
        },
    ]

    for cred in creds:
        value = os.environ.get(cred["env_var"])
        if value:
            statuses.append({
                "tool": cred["tool"],
                "status": "present",
                "version_found": None,
                "version_required": None,
                "install_command": None,
                "note": None,
            })
        else:
            statuses.append({
                "tool": cred["tool"],
                "status": "missing",
                "version_found": None,
                "version_required": None,
                "install_command": None,
                "note": cred["note_if_missing"],
            })

    return statuses


def _check_vercel_auth() -> str:
    """Determine Vercel auth status.

    Returns:
        "present" if VERCEL_TOKEN is set (env var or keychain).
        "present_unauth" if no token is found.
    """
    # Check env var first (os.environ.get checks VERCEL_TOKEN)
    token = os.environ.get("VERCEL_TOKEN")
    if token:
        return "present"

    # Fall back to keychain
    keychain_token = get_credential("vercel_token")
    if keychain_token:
        return "present"

    return "present_unauth"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_env(deploy_target: str) -> list[dict[str, Any]]:
    """Check the current environment for required tools based on deploy target.

    Always checks: node, npm, python.
    For deploy_target='vercel': also checks vercel CLI + auth.
    For deploy_target='gcp': also checks gcloud CLI + auth.
    For deploy_target='supabase': also checks Supabase credentials (access token + org ID).
    For deploy_target='local': only node, npm, python.

    Args:
        deploy_target: One of "vercel", "gcp", "supabase", "local".

    Returns:
        List of ToolStatus dicts, one per checked tool.
    """
    statuses: list[dict[str, Any]] = []

    # Always-required checks
    node_raw = _check_nodejs(shutil.which, subprocess.run)
    statuses.append(_build_tool_status("node", node_raw, version_required=_NODE_VERSION_REQUIRED))

    npm_raw = _check_npm(shutil.which, subprocess.run)
    statuses.append(_build_tool_status("npm", npm_raw))

    python_raw = _check_python_version()
    # Python is always "present" when the MCP server is running (Pitfall 6 in RESEARCH.md)
    statuses.append({
        "tool": "python",
        "status": "present",
        "version_found": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "version_required": _PYTHON_VERSION_REQUIRED,
        "install_command": None,
        "note": None,
    })

    # Deploy-target-specific checks
    if deploy_target == "vercel":
        vercel_raw = _check_vercel_cli(shutil.which, subprocess.run)
        vercel_passed = bool(vercel_raw.get("passed"))

        if vercel_passed:
            # Check auth status
            auth_status = _check_vercel_auth()
            if auth_status == "present":
                note = (
                    "Warning: Vercel tokens cannot be project-scoped — "
                    "all projects in your org are accessible."
                )
            else:
                note = (
                    "VERCEL_TOKEN not set. "
                    "Run: vercel login  OR  set VERCEL_TOKEN env var."
                )
            statuses.append({
                "tool": "vercel",
                "status": auth_status,
                "version_found": vercel_raw.get("version"),
                "version_required": None,
                "install_command": None,
                "note": note,
            })
        else:
            # Not installed
            platform = _platform_key()
            statuses.append({
                "tool": "vercel",
                "status": "missing",
                "version_found": None,
                "version_required": None,
                "install_command": _INSTALL_COMMANDS.get(("vercel", platform)),
                "note": None,
            })

    elif deploy_target == "gcp":
        statuses.append(_check_gcloud())

    elif deploy_target == "supabase":
        statuses.extend(_check_supabase_credentials())
        statuses.extend(_check_oauth_credentials())

    # local: no extra checks needed

    return statuses


def install_tool(tool_to_install: str) -> str:
    """Attempt to install a tool using its registered install command.

    Validates the tool name against an allowlist BEFORE any subprocess call
    to prevent shell injection via the tool_to_install parameter (ENVS-03).

    For tools with a known single-command install (via _INSTALL_ARGS), runs
    `subprocess.run` with list-form args (no shell=True).

    For tools without a known single-command install (e.g., node on Linux),
    returns human-readable manual install instructions.

    Args:
        tool_to_install: Logical tool name. Must be in _INSTALLABLE_TOOLS.

    Returns:
        Human-readable result string (success, failure, or manual instructions).
    """
    # Security: validate allowlist BEFORE any subprocess call
    if tool_to_install not in _INSTALLABLE_TOOLS:
        return (
            f"Error: '{tool_to_install}' is not an allowed tool name. "
            f"Allowed tools: {sorted(_INSTALLABLE_TOOLS)}"
        )

    platform = _platform_key()
    install_args = _INSTALL_ARGS.get((tool_to_install, platform))

    if install_args is None:
        # No automated install available — return manual instructions
        manual_cmd = _INSTALL_COMMANDS.get((tool_to_install, platform)) or (
            f"No automated install available for '{tool_to_install}' on this platform. "
            "Please install manually."
        )
        return (
            f"Automated install not available for '{tool_to_install}' on {platform}.\n"
            f"Manual install instructions:\n{manual_cmd}"
        )

    # Run the install command with list-form args (no shell=True)
    try:
        proc = subprocess.run(
            install_args,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"Install failed: {type(exc).__name__} — {exc}"

    if proc.returncode == 0:
        return (
            f"Successfully installed '{tool_to_install}'.\n"
            f"Output: {(proc.stdout or '').strip()}"
        )

    return (
        f"Install of '{tool_to_install}' failed (exit code {proc.returncode}).\n"
        f"stdout: {(proc.stdout or '').strip()}\n"
        f"stderr: {(proc.stderr or '').strip()}"
    )


def format_env_report(
    statuses: list[dict[str, Any]],
    install_result: str | None = None,
) -> str:
    """Render a markdown environment status report.

    Produces a table with columns: Tool, Status, Version Found, Required, Install Command.
    Appends "Environment is ready" if all statuses are "present", otherwise
    includes instructions to use waf_check_env with execute_install.
    Appends any per-tool notes below the table.
    Optionally appends an install_result section.

    Args:
        statuses: List of ToolStatus dicts from check_env().
        install_result: Optional output from a prior install_tool() call.

    Returns:
        Formatted markdown string.
    """
    lines: list[str] = []

    # Table header
    lines.append("| Tool | Status | Version Found | Required | Install Command |")
    lines.append("|------|--------|---------------|----------|-----------------|")

    notes: list[str] = []

    for s in statuses:
        tool = s.get("tool", "")
        status = s.get("status", "")
        version_found = s.get("version_found") or "—"
        version_required = s.get("version_required") or "—"
        install_command = s.get("install_command") or "—"
        note = s.get("note")

        # Truncate long install commands in table (full command shown in notes)
        display_install = install_command
        if len(display_install) > 50:
            display_install = display_install[:47] + "..."

        # Status icon
        if status == "present":
            status_display = "OK"
        elif status == "present_unauth":
            status_display = "WARN (unauthenticated)"
        elif status == "outdated":
            status_display = "OUTDATED"
        else:
            status_display = "MISSING"

        lines.append(
            f"| {tool} | {status_display} | {version_found} | {version_required} | {display_install} |"
        )

        if note:
            notes.append(f"**{tool}**: {note}")

    lines.append("")

    # Summary
    all_ok = all(s.get("status") == "present" for s in statuses)
    if all_ok:
        lines.append("Environment is ready. All required tools are installed and configured.")
    else:
        has_missing = any(s.get("status") in ("missing", "outdated") for s in statuses)
        if has_missing:
            lines.append(
                "Some tools are missing or outdated. "
                "Use `waf_check_env` with `execute_install=true` to install them automatically, "
                "or follow the install commands above."
            )
        else:
            # present_unauth only
            lines.append(
                "Tools are installed but authentication may be required. "
                "See notes below."
            )

    # Notes section
    if notes:
        lines.append("")
        lines.append("### Notes")
        for note in notes:
            lines.append(f"- {note}")

    # Install result section
    if install_result is not None:
        lines.append("")
        lines.append("### Install Result")
        lines.append(install_result)

    return "\n".join(lines)
