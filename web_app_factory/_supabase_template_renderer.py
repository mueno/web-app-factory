# SPDX-License-Identifier: MIT
"""Supabase template renderer.

Renders supabase-browser.ts.tmpl and supabase-server.ts.tmpl into the
generated app output directory, and adds Supabase npm dependencies to
package.json.

Security note: Template files are read from a fixed TEMPLATE_DIR inside the
package. Output is written to paths under output_dir which is provided by the
caller (validated by PhaseContext in the phase executor).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)

# Templates live alongside this module in web_app_factory/templates/
TEMPLATE_DIR = Path(__file__).parent / "templates"

# Template filenames
_BROWSER_TMPL = "supabase-browser.ts.tmpl"
_SERVER_TMPL = "supabase-server.ts.tmpl"

# Supabase npm packages to inject into generated app's package.json
_SUPABASE_DEPS: dict[str, str] = {
    "@supabase/ssr": "latest",
    "@supabase/supabase-js": "^2",
}

# Output directory within the generated app (relative to output_dir)
_SUPABASE_LIB_DIR = Path("src") / "lib" / "supabase"


def render_supabase_templates(output_dir: Union[str, Path]) -> list[str]:
    """Render Supabase client templates into the generated app output directory.

    Reads supabase-browser.ts.tmpl and supabase-server.ts.tmpl from
    TEMPLATE_DIR and writes them as supabase-browser.ts and supabase-server.ts
    under {output_dir}/src/lib/supabase/.

    Args:
        output_dir: Root of the generated app (e.g., output/{app-name}/nextjs/).

    Returns:
        List of absolute path strings for the two created files.

    Raises:
        FileNotFoundError: If either template file does not exist in TEMPLATE_DIR.
    """
    output_dir = Path(output_dir)

    browser_tmpl_path = TEMPLATE_DIR / _BROWSER_TMPL
    server_tmpl_path = TEMPLATE_DIR / _SERVER_TMPL

    # Validate both templates exist before creating any output
    if not browser_tmpl_path.exists():
        raise FileNotFoundError(
            f"Supabase browser template not found: {browser_tmpl_path}"
        )
    if not server_tmpl_path.exists():
        raise FileNotFoundError(
            f"Supabase server template not found: {server_tmpl_path}"
        )

    # Create output directory (mkdir -p equivalent)
    supabase_lib_dir = output_dir / _SUPABASE_LIB_DIR
    supabase_lib_dir.mkdir(parents=True, exist_ok=True)

    created_paths: list[str] = []

    # Render browser client: strip .tmpl extension
    browser_content = browser_tmpl_path.read_text(encoding="utf-8")
    browser_out = supabase_lib_dir / "supabase-browser.ts"
    browser_out.write_text(browser_content, encoding="utf-8")
    created_paths.append(str(browser_out))
    logger.info("Rendered supabase-browser.ts -> %s", browser_out)

    # Render server client: strip .tmpl extension
    server_content = server_tmpl_path.read_text(encoding="utf-8")
    server_out = supabase_lib_dir / "supabase-server.ts"
    server_out.write_text(server_content, encoding="utf-8")
    created_paths.append(str(server_out))
    logger.info("Rendered supabase-server.ts -> %s", server_out)

    return created_paths


def add_supabase_deps(package_json_path: Union[str, Path]) -> None:
    """Add Supabase npm packages to the generated app's package.json.

    Adds @supabase/ssr and @supabase/supabase-js to the dependencies dict.
    Preserves all existing dependencies.

    Args:
        package_json_path: Path to the generated app's package.json file.
    """
    package_json_path = Path(package_json_path)

    # Read existing package.json
    content = package_json_path.read_text(encoding="utf-8")
    data: dict = json.loads(content)

    # Ensure dependencies key exists
    if "dependencies" not in data:
        data["dependencies"] = {}

    # Add Supabase packages (preserve existing versions if already present)
    for package, version in _SUPABASE_DEPS.items():
        if package not in data["dependencies"]:
            data["dependencies"][package] = version
            logger.info("Added %s@%s to package.json dependencies", package, version)
        else:
            logger.debug("Package %s already in dependencies, skipping", package)

    # Write back with consistent formatting (indent=2)
    package_json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
