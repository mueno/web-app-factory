"""Tests for _tool_impls.py — shared business logic layer.

Phase 16, Plan 01 — MCP Infrastructure Hardening

Verifies:
1. The _tool_impls module is importable.
2. All 7 impl_* functions exist as async callables.
3. No module-level singletons (_STORE, _EXECUTOR, _REGISTRY) exist in _tool_impls.
"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import pytest

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_IMPL_FUNCTIONS = [
    "impl_generate_app",
    "impl_get_status",
    "impl_approve_gate",
    "impl_list_runs",
    "impl_start_dev_server",
    "impl_stop_dev_server",
    "impl_check_env",
]

MODULE_LEVEL_SINGLETONS = ["_STORE", "_EXECUTOR", "_REGISTRY"]


def test_tool_impls_importable():
    """_tool_impls module must be importable without errors."""
    import importlib
    mod = importlib.import_module("web_app_factory._tool_impls")
    assert mod is not None


def test_all_impl_functions_exist():
    """All 7 impl_* functions must exist in _tool_impls."""
    from web_app_factory import _tool_impls
    for name in EXPECTED_IMPL_FUNCTIONS:
        assert hasattr(_tool_impls, name), (
            f"Missing impl function: {name}. "
            f"_tool_impls must export all 7 impl_* functions."
        )


def test_all_impl_functions_are_async():
    """All 7 impl_* functions must be async callables (coroutine functions)."""
    from web_app_factory import _tool_impls
    for name in EXPECTED_IMPL_FUNCTIONS:
        fn = getattr(_tool_impls, name, None)
        assert fn is not None, f"Missing: {name}"
        assert inspect.iscoroutinefunction(fn), (
            f"{name} must be an async function (coroutine function). "
            f"Got: {fn!r}"
        )


def test_no_module_level_singletons():
    """_tool_impls.py must NOT define module-level singletons.

    Singletons (_STORE, _EXECUTOR, _REGISTRY) must remain in their
    existing homes (_progress_store, _pipeline_bridge).
    """
    impl_path = PROJECT_ROOT / "web_app_factory" / "_tool_impls.py"
    assert impl_path.exists(), "_tool_impls.py does not exist yet"

    source = impl_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find module-level assignments
    module_level_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module):
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            module_level_names.add(target.id)
                elif isinstance(stmt, ast.AnnAssign):
                    if isinstance(stmt.target, ast.Name):
                        module_level_names.add(stmt.target.id)

    violations = module_level_names & set(MODULE_LEVEL_SINGLETONS)
    assert not violations, (
        f"_tool_impls.py has forbidden module-level singletons: {violations}. "
        "These must remain in their existing homes (_progress_store, _pipeline_bridge)."
    )
