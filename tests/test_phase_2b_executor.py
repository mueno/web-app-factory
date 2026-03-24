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
    # Use "pipeline-root" as project_dir name so it differs from app_name "myapp".
    # This lets tests distinguish between ctx.project_dir (pipeline root) and
    # ctx.project_dir.parent / ctx.app_name (the actual Next.js project).
    project_dir = tmp_path / "pipeline-root"
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
        assert sub_steps == [
            "load_spec",
            "generate_shared_components",
            "generate_pages",
            "generate_integration",
            "validate_packages",
        ]


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

    def _capture_all_prompts(self, tmp_path) -> list[str]:
        """Run executor and return all prompts passed to run_build_agent."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        captured: list[str] = []

        def fake_run_build_agent(prompt: str, system_prompt: str, project_dir: str, **kwargs) -> str:
            captured.append(prompt)
            return "mocked build agent output"

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", side_effect=fake_run_build_agent), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
            mod.Phase2bBuildExecutor().execute(ctx)

        return captured

    def test_prompt_contains_prd_content(self, tmp_path):
        """execute() injects PRD file content into an agent prompt (not just path).

        With three-sub-step decomposition, PRD content is in the first prompt
        (shared components). Check that at least one prompt contains it.
        """
        prompts = self._capture_all_prompts(tmp_path)
        # At least one prompt must inject PRD content
        combined = " ".join(prompts)
        assert "Component Inventory" in combined or "NavBar" in combined

    def test_prompt_contains_screen_spec_content(self, tmp_path):
        """execute() injects screen-spec.json content into an agent prompt (not just path).

        With three-sub-step decomposition, screen-spec content is in the pages prompt.
        Check that at least one prompt contains it.
        """
        prompts = self._capture_all_prompts(tmp_path)
        combined = " ".join(prompts)
        # screen-spec.json content (as JSON text) should be in at least one prompt
        assert "DashboardCard" in combined or "/dashboard" in combined or "screen" in combined.lower()

    def test_prompt_instructs_error_tsx_per_route_segment(self, tmp_path):
        """execute() prompt must instruct error.tsx generation per route segment (BILD-06).

        With three-sub-step decomposition, error.tsx instruction is in the pages prompt.
        """
        prompts = self._capture_all_prompts(tmp_path)
        # error.tsx instruction must appear in at least one prompt (pages prompt)
        combined = " ".join(prompts)
        assert "error.tsx" in combined
        # Must mention route segment or async data dependencies
        combined_lower = combined.lower()
        assert "route" in combined_lower or "segment" in combined_lower or "async" in combined_lower

    def test_prompt_instructs_generation_order_shared_components_first(self, tmp_path):
        """execute() uses separate prompts for shared components and pages.

        With three-sub-step decomposition, the FIRST prompt targets components only
        and the SECOND prompt targets pages — enforcing ordering by structure.
        """
        prompts = self._capture_all_prompts(tmp_path)
        assert len(prompts) == 3
        first_prompt_lower = prompts[0].lower()
        # First prompt must mention components
        assert "component" in first_prompt_lower
        # Second prompt must mention pages or routes
        second_prompt_lower = prompts[1].lower()
        assert "page" in second_prompt_lower or "route" in second_prompt_lower

    def test_prompt_instructs_mobile_first_responsive(self, tmp_path):
        """execute() prompt instructs mobile-first Tailwind responsive classes.

        With three-sub-step decomposition, this instruction is in the pages prompt.
        """
        prompts = self._capture_all_prompts(tmp_path)
        combined = " ".join(prompts)
        combined_lower = combined.lower()
        assert "mobile" in combined_lower
        # Should mention md: or lg: Tailwind breakpoints, or responsive
        assert "md:" in combined or "lg:" in combined or "responsive" in combined_lower


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

        # Create a package.json in the Next.js project directory (nextjs_dir),
        # which is ctx.project_dir.parent / ctx.app_name — NOT the pipeline root.
        # The executor reads package.json from nextjs_dir after the fix.
        nextjs_dir = ctx.project_dir.parent / ctx.app_name
        nextjs_dir.mkdir(parents=True, exist_ok=True)
        package_json = {
            "name": "myapp",
            "dependencies": {
                "next": "^14.0.0",
                "react": "^18.0.0",
                "react-dom": "^18.0.0",
                "zod": "^3.22.0",
            }
        }
        (nextjs_dir / "package.json").write_text(
            json.dumps(package_json), encoding="utf-8"
        )

        validate_mock = MagicMock(return_value={"zod": True})

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", return_value="build output"), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", validate_mock):
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
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", validate_mock):
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
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
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
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        assert result.success is True

    # Quality self-assessment is now generated by contract_pipeline_runner (CONT-04).

    def test_execute_passes_nextjs_dir_to_run_build_agent(self, tmp_path):
        """execute() passes the Next.js project dir (not pipeline root) to run_build_agent.

        BILD-02: ctx.project_dir is the pipeline root ("pipeline-root").
        The Next.js project lives at ctx.project_dir.parent / ctx.app_name ("myapp").
        The executor must pass str(nextjs_dir), NOT str(ctx.project_dir).
        """
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx(tmp_path)
        _create_spec_files(ctx.project_dir)

        run_agent_mock = MagicMock(return_value="build done")

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", run_agent_mock), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        call_kwargs = run_agent_mock.call_args
        assert call_kwargs is not None

        args, kwargs = call_kwargs
        # project_dir should be passed as keyword argument
        actual_project_dir = kwargs.get("project_dir")

        # Expected: the Next.js project dir (sibling of pipeline root, named after app_name)
        expected_nextjs_dir = str(ctx.project_dir.parent / ctx.app_name)
        # The pipeline root is different from the nextjs dir
        pipeline_root = str(ctx.project_dir)

        assert actual_project_dir == expected_nextjs_dir, (
            f"run_build_agent should receive the Next.js project dir ({expected_nextjs_dir!r}), "
            f"not the pipeline root ({pipeline_root!r}). Got: {actual_project_dir!r}"
        )

    def test_execute_uses_error_tsx_instruction_for_async_data_routes(self, tmp_path):
        """BILD-06: agent prompt must mention 'use client' for error.tsx.

        With three-sub-step decomposition, error.tsx + 'use client' instruction
        is in the pages prompt (second call). Check across all prompts.
        """
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
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
            mod.Phase2bBuildExecutor().execute(ctx)

        # Per BILD-06: error.tsx must have 'use client' — check across all prompts
        combined = " ".join(captured_prompts)
        assert "use client" in combined or '"use client"' in combined or "'use client'" in combined


# ---------------------------------------------------------------------------
# TestPhase2bSubStepCheckpoints
# ---------------------------------------------------------------------------


def _make_ctx_with_resume(tmp_path: Path, resume_sub_step: str | None = None) -> "PhaseContext":
    """Create a PhaseContext with spec files and optional resume_sub_step."""
    from tools.phase_executors.base import PhaseContext
    project_dir = tmp_path / "pipeline-root"
    (project_dir / "docs" / "pipeline").mkdir(parents=True)
    _create_spec_files(project_dir)
    return PhaseContext(
        run_id="test-run-2b",
        phase_id="2b",
        project_dir=project_dir,
        idea="A project management web app",
        app_name="myapp",
        resume_sub_step=resume_sub_step,
    )


class TestPhase2bSubStepCheckpoints:
    """Tests that failure at each generation sub-step sets the correct resume_point."""

    def setup_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def test_sub_steps_is_five_elements(self):
        """executor.sub_steps must be the exact 5-element list."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)
        executor = mod.Phase2bBuildExecutor()
        assert executor.sub_steps == [
            "load_spec",
            "generate_shared_components",
            "generate_pages",
            "generate_integration",
            "validate_packages",
        ]

    def test_shared_components_failure_sets_resume_point(self, tmp_path):
        """When run_build_agent returns empty on first generation call, resume_point == 'generate_shared_components'."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx_with_resume(tmp_path)

        # First call (shared components) returns empty → failure
        # Other calls would not be reached
        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", side_effect=["", "success", "success"]), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        assert result.success is False
        assert result.resume_point == "generate_shared_components"

    def test_pages_failure_sets_resume_point(self, tmp_path):
        """When run_build_agent returns empty on the second call (pages), resume_point == 'generate_pages'."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx_with_resume(tmp_path)

        # First call succeeds, second (pages) fails
        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", side_effect=["components output", "", "success"]), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        assert result.success is False
        assert result.resume_point == "generate_pages"

    def test_integration_failure_sets_resume_point(self, tmp_path):
        """When run_build_agent returns empty on the third call (integration), resume_point == 'generate_integration'."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx_with_resume(tmp_path)

        # First two calls succeed, third (integration) fails
        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", side_effect=["components output", "pages output", ""]), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        assert result.success is False
        assert result.resume_point == "generate_integration"

    def test_three_agent_calls_on_full_run(self, tmp_path):
        """When no resume_sub_step, run_build_agent is called exactly 3 times."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx_with_resume(tmp_path)

        run_agent_mock = MagicMock(side_effect=["components output", "pages output", "integration output"])

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", run_agent_mock), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        assert result.success is True
        assert run_agent_mock.call_count == 3


# ---------------------------------------------------------------------------
# TestPhase2bBuildExecutorResume
# ---------------------------------------------------------------------------


class TestPhase2bBuildExecutorResume:
    """Tests that ctx.resume_sub_step correctly skips earlier sub-steps."""

    def setup_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def test_resume_from_generate_pages_skips_shared_components(self, tmp_path):
        """When ctx.resume_sub_step='generate_pages', run_build_agent is called 2 times (pages + integration), not 3."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx_with_resume(tmp_path, resume_sub_step="generate_pages")

        run_agent_mock = MagicMock(side_effect=["pages output", "integration output"])

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", run_agent_mock), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        assert result.success is True
        assert run_agent_mock.call_count == 2

    def test_resume_from_generate_integration_skips_pages(self, tmp_path):
        """When ctx.resume_sub_step='generate_integration', run_build_agent is called exactly 1 time."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx_with_resume(tmp_path, resume_sub_step="generate_integration")

        run_agent_mock = MagicMock(side_effect=["integration output"])

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", run_agent_mock), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
            result = mod.Phase2bBuildExecutor().execute(ctx)

        assert result.success is True
        assert run_agent_mock.call_count == 1


# ---------------------------------------------------------------------------
# TestPhase2bSubStepPrompts
# ---------------------------------------------------------------------------


class TestPhase2bSubStepPrompts:
    """Tests prompt isolation — each sub-step uses a focused prompt."""

    def setup_method(self):
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def _capture_prompts(self, tmp_path, resume_sub_step=None):
        """Helper: run executor and return list of prompts passed to run_build_agent."""
        import importlib
        import tools.phase_executors.phase_2b_executor as mod
        importlib.reload(mod)

        ctx = _make_ctx_with_resume(tmp_path, resume_sub_step=resume_sub_step)

        captured: list[str] = []

        def fake_agent(prompt: str, system_prompt: str, project_dir: str, **kwargs) -> str:
            captured.append(prompt)
            return f"output for call {len(captured)}"

        with patch("tools.phase_executors.phase_2b_executor.run_build_agent", side_effect=fake_agent), \
             patch("tools.phase_executors.phase_2b_executor.validate_npm_packages", return_value={}):
            mod.Phase2bBuildExecutor().execute(ctx)

        return captured

    def test_shared_components_prompt_does_not_contain_page_instruction(self, tmp_path):
        """First run_build_agent call prompt contains 'component' but NOT page-by-page generation language."""
        prompts = self._capture_prompts(tmp_path)

        assert len(prompts) == 3
        first_prompt = prompts[0].lower()

        # Must mention components
        assert "component" in first_prompt

        # Must NOT contain page-by-page or route-order generation language
        assert "page-by-page" not in first_prompt
        assert "route order" not in first_prompt

    def test_pages_prompt_references_existing_components(self, tmp_path):
        """Second run_build_agent call prompt mentions that shared components already exist."""
        prompts = self._capture_prompts(tmp_path)

        assert len(prompts) == 3
        second_prompt = prompts[1].lower()

        # Must mention page or route generation
        assert "page" in second_prompt or "route" in second_prompt

        # Must reference already-generated components
        assert "already" in second_prompt or "exist" in second_prompt or "generated" in second_prompt

    def test_integration_prompt_does_not_embed_prd(self, tmp_path):
        """Third run_build_agent call prompt does NOT contain the full PRD text."""
        prompts = self._capture_prompts(tmp_path)

        assert len(prompts) == 3
        third_prompt = prompts[2]

        # The PRD fixture contains '## Component Inventory' — must NOT be in integration prompt
        assert "## Component Inventory" not in third_prompt

        # Integration prompt must reference types.ts or cross-page contracts
        assert "types.ts" in third_prompt or "parameter" in third_prompt.lower() or "URLSearchParams" in third_prompt
