# SPDX-License-Identifier: MIT
"""Supabase auth template renderer.

Renders the ten auth template files (middleware, login, signup, signout,
callback, AUTH_SETUP.md, and four passkey/WebAuthn templates) into the
generated app output directory.

Template-to-output mapping:
  auth-middleware.ts.tmpl                  -> src/middleware.ts
  auth/login-page.tsx.tmpl                 -> src/app/auth/login/page.tsx
  auth/signup-page.tsx.tmpl                -> src/app/auth/signup/page.tsx
  auth/signout-page.tsx.tmpl               -> src/app/auth/signout/page.tsx
  auth/callback-route.ts.tmpl              -> src/app/auth/callback/route.ts
  auth/AUTH_SETUP.md.tmpl                  -> AUTH_SETUP.md  (project root, not src/)
  auth/passkey-register-api.ts.tmpl        -> src/app/api/auth/passkey/register/route.ts
  auth/passkey-auth-api.ts.tmpl            -> src/app/api/auth/passkey/authenticate/route.ts
  auth/passkey-hooks.ts.tmpl               -> src/lib/auth/passkey-hooks.ts
  auth/passkey-client.tsx.tmpl             -> src/components/auth/passkey-buttons.tsx

Security note: Template files are read from a fixed TEMPLATE_DIR inside the
package. Output is written to paths under output_dir which is provided by the
caller (validated by PhaseContext in the phase executor).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)

# Templates live alongside this module in web_app_factory/templates/
TEMPLATE_DIR = Path(__file__).parent / "templates"

# Ordered list of (template_relative_path, output_relative_path) mappings.
# Template paths are relative to TEMPLATE_DIR.
# Output paths are relative to output_dir.
_AUTH_TEMPLATE_MAPPINGS: list[tuple[str, str]] = [
    # Original 6 OAuth/session templates
    ("auth-middleware.ts.tmpl", "src/middleware.ts"),
    ("auth/login-page.tsx.tmpl", "src/app/auth/login/page.tsx"),
    ("auth/signup-page.tsx.tmpl", "src/app/auth/signup/page.tsx"),
    ("auth/signout-page.tsx.tmpl", "src/app/auth/signout/page.tsx"),
    ("auth/callback-route.ts.tmpl", "src/app/auth/callback/route.ts"),
    ("auth/AUTH_SETUP.md.tmpl", "AUTH_SETUP.md"),
    # 4 passkey (WebAuthn) templates — passkey is the primary auth method
    ("auth/passkey-register-api.ts.tmpl", "src/app/api/auth/passkey/register/route.ts"),
    ("auth/passkey-auth-api.ts.tmpl", "src/app/api/auth/passkey/authenticate/route.ts"),
    ("auth/passkey-hooks.ts.tmpl", "src/lib/auth/passkey-hooks.ts"),
    ("auth/passkey-client.tsx.tmpl", "src/components/auth/passkey-buttons.tsx"),
]


def render_auth_templates(output_dir: Union[str, Path]) -> list[str]:
    """Render Supabase auth templates into the generated app output directory.

    Reads all ten auth template files from TEMPLATE_DIR and writes them to
    their target paths under output_dir. Parent directories are created
    automatically (equivalent to mkdir -p).

    The ten templates comprise six OAuth/session templates (middleware, login,
    signup, signout, callback, AUTH_SETUP.md) and four passkey (WebAuthn)
    templates (register API route, authenticate API route, session hooks, and
    the client PasskeyButtons component).

    Args:
        output_dir: Root of the generated app (e.g., output/{app-name}/nextjs/).

    Returns:
        List of absolute path strings for the ten created files, in the same
        order as _AUTH_TEMPLATE_MAPPINGS.

    Raises:
        FileNotFoundError: If any auth template file does not exist in TEMPLATE_DIR.
    """
    output_dir = Path(output_dir)

    # Build full template paths and validate all exist before writing any output
    template_paths = [
        (TEMPLATE_DIR / tmpl_rel, output_dir / out_rel)
        for tmpl_rel, out_rel in _AUTH_TEMPLATE_MAPPINGS
    ]

    for tmpl_path, _ in template_paths:
        if not tmpl_path.exists():
            raise FileNotFoundError(
                f"Auth template not found: {tmpl_path}"
            )

    # All templates exist — now render them
    created_paths: list[str] = []

    for tmpl_path, out_path in template_paths:
        # Create parent directories (mkdir -p equivalent)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy template content to output (no variable substitution — raw copy)
        content = tmpl_path.read_text(encoding="utf-8")
        out_path.write_text(content, encoding="utf-8")
        created_paths.append(str(out_path))
        logger.info("Rendered %s -> %s", tmpl_path.name, out_path)

    return created_paths
