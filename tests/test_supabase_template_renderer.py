"""Tests for web_app_factory/_supabase_template_renderer.py.

Verifies:
- render_supabase_templates(output_dir) creates src/lib/supabase/ directory
- render_supabase_templates copies supabase-browser.ts.tmpl as supabase-browser.ts
- render_supabase_templates copies supabase-server.ts.tmpl as supabase-server.ts
- Rendered supabase-browser.ts contains NEXT_PUBLIC_SUPABASE_ANON_KEY (not service_role)
- Rendered supabase-server.ts contains SUPABASE_SERVICE_ROLE_KEY (no NEXT_PUBLIC_ prefix)
- add_supabase_deps adds @supabase/ssr and @supabase/supabase-js to package.json
- add_supabase_deps preserves existing dependencies
- render_supabase_templates raises FileNotFoundError if templates do not exist
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# render_supabase_templates tests
# ---------------------------------------------------------------------------


def test_render_creates_supabase_directory(tmp_path: Path) -> None:
    """render_supabase_templates creates src/lib/supabase/ directory."""
    from web_app_factory._supabase_template_renderer import render_supabase_templates

    render_supabase_templates(tmp_path)

    supabase_dir = tmp_path / "src" / "lib" / "supabase"
    assert supabase_dir.is_dir(), "src/lib/supabase/ directory should be created"


def test_render_creates_browser_client(tmp_path: Path) -> None:
    """render_supabase_templates creates supabase-browser.ts from template."""
    from web_app_factory._supabase_template_renderer import render_supabase_templates

    created = render_supabase_templates(tmp_path)

    browser_ts = tmp_path / "src" / "lib" / "supabase" / "supabase-browser.ts"
    assert browser_ts.exists(), "supabase-browser.ts should be created"
    # Returned list should include the browser file path
    browser_paths = [p for p in created if "supabase-browser" in p]
    assert len(browser_paths) == 1


def test_render_creates_server_client(tmp_path: Path) -> None:
    """render_supabase_templates creates supabase-server.ts from template."""
    from web_app_factory._supabase_template_renderer import render_supabase_templates

    created = render_supabase_templates(tmp_path)

    server_ts = tmp_path / "src" / "lib" / "supabase" / "supabase-server.ts"
    assert server_ts.exists(), "supabase-server.ts should be created"
    # Returned list should include the server file path
    server_paths = [p for p in created if "supabase-server" in p]
    assert len(server_paths) == 1


def test_render_returns_list_of_created_paths(tmp_path: Path) -> None:
    """render_supabase_templates returns a list with 2 file paths."""
    from web_app_factory._supabase_template_renderer import render_supabase_templates

    created = render_supabase_templates(tmp_path)

    assert isinstance(created, list)
    assert len(created) == 2


def test_browser_ts_contains_anon_key_env(tmp_path: Path) -> None:
    """Rendered supabase-browser.ts uses NEXT_PUBLIC_SUPABASE_ANON_KEY."""
    from web_app_factory._supabase_template_renderer import render_supabase_templates

    render_supabase_templates(tmp_path)

    browser_ts = tmp_path / "src" / "lib" / "supabase" / "supabase-browser.ts"
    content = browser_ts.read_text(encoding="utf-8")

    assert "NEXT_PUBLIC_SUPABASE_ANON_KEY" in content, (
        "Browser client must use NEXT_PUBLIC_SUPABASE_ANON_KEY"
    )
    # Must NOT use service role key in browser client
    assert "SERVICE_ROLE" not in content, (
        "Browser client must not reference service_role key"
    )


def test_server_ts_contains_service_role_key_env(tmp_path: Path) -> None:
    """Rendered supabase-server.ts uses SUPABASE_SERVICE_ROLE_KEY (no NEXT_PUBLIC_)."""
    from web_app_factory._supabase_template_renderer import render_supabase_templates

    render_supabase_templates(tmp_path)

    server_ts = tmp_path / "src" / "lib" / "supabase" / "supabase-server.ts"
    content = server_ts.read_text(encoding="utf-8")

    assert "SUPABASE_SERVICE_ROLE_KEY" in content, (
        "Server client must use SUPABASE_SERVICE_ROLE_KEY"
    )
    # Must NOT have NEXT_PUBLIC_ prefix on service role key (SECG-01)
    assert "NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY" not in content, (
        "Service role key must never have NEXT_PUBLIC_ prefix (SECG-01)"
    )


def test_render_strips_tmpl_extension(tmp_path: Path) -> None:
    """Output files have .ts extension (not .ts.tmpl)."""
    from web_app_factory._supabase_template_renderer import render_supabase_templates

    created = render_supabase_templates(tmp_path)

    for path_str in created:
        assert not path_str.endswith(".tmpl"), (
            f"Output file should not have .tmpl extension: {path_str}"
        )
        assert path_str.endswith(".ts"), (
            f"Output file should have .ts extension: {path_str}"
        )


def test_render_raises_on_missing_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """render_supabase_templates raises FileNotFoundError if templates do not exist."""
    from web_app_factory import _supabase_template_renderer as renderer

    # Redirect TEMPLATE_DIR to a nonexistent directory
    monkeypatch.setattr(renderer, "TEMPLATE_DIR", tmp_path / "nonexistent_templates")

    with pytest.raises(FileNotFoundError):
        renderer.render_supabase_templates(tmp_path / "output")


# ---------------------------------------------------------------------------
# add_supabase_deps tests
# ---------------------------------------------------------------------------


def test_add_supabase_deps_adds_ssr_package(tmp_path: Path) -> None:
    """add_supabase_deps adds @supabase/ssr to dependencies."""
    from web_app_factory._supabase_template_renderer import add_supabase_deps

    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(json.dumps({"name": "test-app", "dependencies": {}}), encoding="utf-8")

    add_supabase_deps(pkg_json)

    data = json.loads(pkg_json.read_text(encoding="utf-8"))
    assert "@supabase/ssr" in data["dependencies"], (
        "@supabase/ssr should be added to dependencies"
    )


def test_add_supabase_deps_adds_supabase_js_package(tmp_path: Path) -> None:
    """add_supabase_deps adds @supabase/supabase-js to dependencies."""
    from web_app_factory._supabase_template_renderer import add_supabase_deps

    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(json.dumps({"name": "test-app", "dependencies": {}}), encoding="utf-8")

    add_supabase_deps(pkg_json)

    data = json.loads(pkg_json.read_text(encoding="utf-8"))
    assert "@supabase/supabase-js" in data["dependencies"], (
        "@supabase/supabase-js should be added to dependencies"
    )


def test_add_supabase_deps_preserves_existing_deps(tmp_path: Path) -> None:
    """add_supabase_deps preserves existing dependencies."""
    from web_app_factory._supabase_template_renderer import add_supabase_deps

    existing_deps = {"react": "^18", "next": "^14", "typescript": "^5"}
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(
        json.dumps({"name": "test-app", "dependencies": existing_deps}),
        encoding="utf-8",
    )

    add_supabase_deps(pkg_json)

    data = json.loads(pkg_json.read_text(encoding="utf-8"))
    for dep, version in existing_deps.items():
        assert data["dependencies"].get(dep) == version, (
            f"Existing dependency {dep} should be preserved"
        )


def test_add_supabase_deps_creates_dependencies_key_if_missing(tmp_path: Path) -> None:
    """add_supabase_deps creates dependencies key if package.json lacks it."""
    from web_app_factory._supabase_template_renderer import add_supabase_deps

    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(json.dumps({"name": "test-app"}), encoding="utf-8")

    add_supabase_deps(pkg_json)

    data = json.loads(pkg_json.read_text(encoding="utf-8"))
    assert "dependencies" in data
    assert "@supabase/ssr" in data["dependencies"]
    assert "@supabase/supabase-js" in data["dependencies"]


def test_add_supabase_deps_writes_valid_json(tmp_path: Path) -> None:
    """add_supabase_deps writes valid, formatted JSON with indent=2."""
    from web_app_factory._supabase_template_renderer import add_supabase_deps

    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(json.dumps({"name": "test-app", "dependencies": {}}), encoding="utf-8")

    add_supabase_deps(pkg_json)

    # Should be valid JSON (no parse error)
    content = pkg_json.read_text(encoding="utf-8")
    data = json.loads(content)
    assert isinstance(data, dict)
    # Should be indented (pretty-printed)
    assert "\n" in content, "JSON should be formatted with newlines"
