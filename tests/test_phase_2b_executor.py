"""Tests for Phase 2b code generation executor.

Covers:
- Phase2bBuildExecutor: phase_id, self-registration
- execute(): PRD content injection, screen-spec content injection
- execute(): calls run_build_agent with both PRD and screen-spec content
- execute(): calls validate_npm_packages with extracted packages
- execute(): returns PhaseResult(success=False) when PRD missing
- execute(): returns PhaseResult(success=False) when screen-spec missing
- execute(): generates quality self-assessment on success
- Agent prompt: generation order instruction (shared components first)
- Agent prompt: error.tsx instruction per route segment (BILD-06)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(tmp_path: Path) -> "PhaseContext":
    from tools.phase_executors.base import PhaseContext
    project_dir = tmp_path / "myapp"
    (project_dir / "docs" / "pipeline").mkdir(parents=True)
    return PhaseContext(
        run_id="test-run-2b",
        phase_id="2b",
        project_dir=project_dir,
        idea="A project management web app",
        app_name="myapp",
    )


def _create_spec_files(project_dir: Path) -> None:
    """Create minimal PRD and screen-spec.json files for testing."""
    docs_pipeline = project_dir / "docs" / "pipeline"
    docs_pipeline.mkdir(parents=True, exist_ok=True)

    prd_content = """\
## Component Inventory

- **NavBar**: Top navigation component
- **DashboardCard**: Card for displaying project stats

## Route Structure

- / (Home)
- /dashboard
- /projects/[id]
"""
    (docs_pipeline / "prd.md").write_text(prd_content, encoding="utf-8")

    screen_spec = {
        "screens": [
            {
                "route": "/",
                "layout": "Landing layout",
                "components": ["NavBar"],
                "states": ["loaded"],
                "responsive": {"mobile": "stack", "tablet": "side", "desktop": "wide"},
            },
            {
                "route": "/dashboard",
                "layout": "Dashboard layout with data",
                "components": ["NavBar", "DashboardCard"],
                "states": ["loading", "loaded", "error"],
                "responsive": {"mobile": "stack", "tablet": "grid", "desktop": "grid"},
            },
        ]
    }
    (docs_pipeline / "screen-spec.json").write_text(
        json.dumps(screen_spec, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Phase2bBuildExecutor: basic properties
# ---------------------------------------------------------------------------

class TestPhase2bBuildExecutorBasic:
    def setup_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def test_phase_id_is_2b(self):
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)
        executor = mod.Phase2bBuildExecutor()
        assert executor.phase_id == "2b"

    def test_self_registers_on_import(self):
        """Importing the module should register Phase2bBuildExecutor for '2b'."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)
        from tools.phase_executors.registry import get_executor
        assert get_executor("2b") is not None

    def test_sub_steps_contains_expected_steps(self):
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)
        executor = mod.Phase2bBuildExecutor()
        sub_steps = executor.sub_steps
        assert "load_spec" in sub_steps
        assert "generate_code" in sub_steps
        assert "validate_packages" in sub_steps
        assert "self_assess" in sub_steps


# ---------------------------------------------------------------------------
# Phase2bBuildExecutor: failure paths
# ---------------------------------------------------------------------------

class TestPhase2bBuildExecutorFailurePaths:
    def setup_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def test_returns_failure_when_prd_missing(self, tmp_path):
        """execute() returns PhaseResult(success=False) when docs/pipeline/prd.md is missing."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        # Create only screen-spec.json, no prd.md
        docs = ctx.project_dir / "docs" / "pipeline"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "screen-spec.json").write_text('{"screens": []}', encoding="utf-8")

        result = mod.Phase2bBuildExecutor().execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "prd" in result.error.lower() or "missing" in result.error.lower()

    def test_returns_failure_when_screen_spec_missing(self, tmp_path):
        """execute() returns PhaseResult(success=False) when screen-spec.json is missing."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        # Create only prd.md, no screen-spec.json
        docs = ctx.project_dir / "docs" / "pipeline"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "prd.md").write_text("# PRD content", encoding="utf-8")

        result = mod.Phase2bBuildExecutor().execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "screen-spec" in result.error.lower() or "missing" in result.error.lower()

    def test_error_message_mentions_prd_path(self, tmp_path):
        """Error when PRD is missing should mention the expected path."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        # No files at all
        result = mod.Phase2bBuildExecutor().execute(ctx)

        assert result.success is False
        # Should mention prd.md or docs/pipeline
        assert "prd" in result.error.lower() or "pipeline" in result.error.lower()


# ---------------------------------------------------------------------------
# Phase2bBuildExecutor: agent prompt content
# ---------------------------------------------------------------------------

class TestPhase2bBuildExecutorAgentPrompt:
    """Verify the agent prompt contains required content per BILD-06 and plan spec."""

    def setup_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def test_prompt_contains_prd_content(self, tmp_path):
        """execute() injects PRD file content into agent prompt (not just path)."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        captured_prompts: list[str] = []

        def fake_run_build_agent(prompt: str, system_prompt: str, project_dir: str, **kwargs) -> str:
            captured_prompts.append(prompt)
            return "mocked build agent output"

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", side_effect=fake_run_build_agent), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment"):
            mod.Phase2bBuildExecutor().execute(ctx)

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        # PRD content should be injected (not just the path)
        assert "Component Inventory" in prompt or "NavBar" in prompt

    def test_prompt_contains_screen_spec_content(self, tmp_path):
        """execute() injects screen-spec.json content into agent prompt (not just path)."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        captured_prompts: list[str] = []

        def fake_run_build_agent(prompt: str, system_prompt: str, project_dir: str, **kwargs) -> str:
            captured_prompts.append(prompt)
            return "mocked build agent output"

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", side_effect=fake_run_build_agent), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment"):
            mod.Phase2bBuildExecutor().execute(ctx)

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        # screen-spec.json content (as JSON text) should be in the prompt
        assert "DashboardCard" in prompt or "/dashboard" in prompt or "screen" in prompt.lower()

    def test_prompt_instructs_error_tsx_per_route_segment(self, tmp_path):
        """execute() prompt must instruct error.tsx generation per route segment (BILD-06)."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        captured_prompts: list[str] = []

        def fake_run_build_agent(prompt: str, system_prompt: str, project_dir: str, **kwargs) -> str:
            captured_prompts.append(prompt)
            return "mocked build agent output"

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", side_effect=fake_run_build_agent), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment"):
            mod.Phase2bBuildExecutor().execute(ctx)

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        assert "error.tsx" in prompt
        # Must mention route segment or async data dependencies
        prompt_lower = prompt.lower()
        assert "route" in prompt_lower or "segment" in prompt_lower or "async" in prompt_lower

    def test_prompt_instructs_generation_order_shared_components_first(self, tmp_path):
        """execute() prompt instructs generating shared components before pages."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        captured_prompts: list[str] = []

        def fake_run_build_agent(prompt: str, system_prompt: str, project_dir: str, **kwargs) -> str:
            captured_prompts.append(prompt)
            return "mocked build agent output"

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", side_effect=fake_run_build_agent), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment"):
            mod.Phase2bBuildExecutor().execute(ctx)

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        prompt_lower = prompt.lower()
        # Should instruct shared components first, then pages
        assert "component" in prompt_lower
        assert "page" in prompt_lower
        # Check ordering language
        assert "first" in prompt_lower or "then" in prompt_lower or "before" in prompt_lower

    def test_prompt_instructs_mobile_first_responsive(self, tmp_path):
        """execute() prompt instructs mobile-first Tailwind responsive classes."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        captured_prompts: list[str] = []

        def fake_run_build_agent(prompt: str, system_prompt: str, project_dir: str, **kwargs) -> str:
            captured_prompts.append(prompt)
            return "mocked build agent output"

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", side_effect=fake_run_build_agent), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment"):
            mod.Phase2bBuildExecutor().execute(ctx)

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        prompt_lower = prompt.lower()
        assert "mobile" in prompt_lower
        # Should mention md: or lg: Tailwind breakpoints, or responsive
        assert "md:" in prompt or "lg:" in prompt or "responsive" in prompt_lower


# ---------------------------------------------------------------------------
# Phase2bBuildExecutor: npm package validation
# ---------------------------------------------------------------------------

class TestPhase2bBuildExecutorNpmValidation:
    def setup_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def test_calls_validate_npm_packages_after_agent(self, tmp_path):
        """execute() calls validate_npm_packages with packages from package.json after agent completes."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        # Create a package.json with extra dependencies to simulate what build agent adds
        package_json = {
            "name": "myapp",
            "dependencies": {
                "next": "^14.0.0",
                "react": "^18.0.0",
                "react-dom": "^18.0.0",
                "zod": "^3.22.0",
            }
        }
        (ctx.project_dir / "package.json").write_text(
            json.dumps(package_json), encoding="utf-8"
        )

        validate_mock = MagicMock(return_value={"zod": True})

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", return_value="build output"), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", validate_mock), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment"):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        assert validate_mock.called

    def test_validate_npm_packages_does_not_fail_result(self, tmp_path):
        """validate_npm_packages failure does NOT cause PhaseResult(success=False).

        The build gate will catch actual failures; npm validation is informational.
        """
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        # Simulate a hallucinated package that doesn't exist
        validate_mock = MagicMock(return_value={"fake-nonexistent-pkg": False})

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", return_value="build output"), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", validate_mock), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment"):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        # Should still succeed even if a package doesn't exist
        assert result.success is True


# ---------------------------------------------------------------------------
# Phase2bBuildExecutor: success path
# ---------------------------------------------------------------------------

class TestPhase2bBuildExecutorSuccess:
    def setup_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def test_execute_calls_run_build_agent(self, tmp_path):
        """execute() calls run_build_agent after loading spec files."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        run_agent_mock = MagicMock(return_value="mocked build agent output")

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", run_agent_mock), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment"):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        assert run_agent_mock.called

    def test_execute_returns_success_on_agent_completion(self, tmp_path):
        """execute() returns PhaseResult(success=True) when agent returns non-empty output."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", return_value="build completed"), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment"):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        assert result.success is True

    def test_execute_generates_quality_self_assessment_on_success(self, tmp_path):
        """execute() calls generate_quality_self_assessment after successful code generation."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        assess_mock = MagicMock()

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", return_value="build done"), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment", assess_mock):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        assert assess_mock.called

    def test_execute_passes_project_dir_to_run_build_agent(self, tmp_path):
        """execute() passes project_dir to run_build_agent."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        run_agent_mock = MagicMock(return_value="build done")

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", run_agent_mock), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment"):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        call_kwargs = run_agent_mock.call_args
        # project_dir should be passed
        assert call_kwargs is not None
        # Check that project_dir argument was included (positional or keyword)
        args, kwargs = call_kwargs
        all_args = list(args) + list(kwargs.values())
        assert any(str(ctx.project_dir) in str(a) for a in all_args)

    def test_execute_uses_error_tsx_instruction_for_async_data_routes(self, tmp_path):
        """BILD-06: agent prompt must mention 'use client' for error.tsx."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        captured_prompts: list[str] = []

        def fake_run_build_agent(prompt: str, system_prompt: str, project_dir: str, **kwargs) -> str:
            captured_prompts.append(prompt)
            return "mocked output"

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", side_effect=fake_run_build_agent), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}), \
             patch("tools.phase_executors.phase_2b_executor.generate_quality_self_assessment"):
            mod.Phase2bBuildExecutor().execute(ctx)

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        # Per BILD-06: error.tsx must have 'use client'
        assert "use client" in prompt or '"use client"' in prompt or "'use client'" in prompt
