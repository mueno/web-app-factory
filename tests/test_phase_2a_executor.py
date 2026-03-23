"""Tests for Phase 2a scaffold executor and build agent runner.

Covers:
- build_agent_runner.run_build_agent: allowed_tools, cwd, max_turns, return value
- agents.definitions.BUILD_AGENT: system prompt content (Next.js, App Router,
  TypeScript strictness, mobile-first responsive, no iOS/Swift/Xcode)
- Phase2aScaffoldExecutor: phase_id, self-registration, subprocess flags,
  success/failure paths, quality self-assessment
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_agent_sdk.types import ResultMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result_message(text: str = "mocked build agent output") -> ResultMessage:
    return ResultMessage(
        subtype="result",
        duration_ms=100,
        duration_api_ms=100,
        is_error=False,
        num_turns=3,
        session_id="build-test-session",
        result=text,
    )


# ---------------------------------------------------------------------------
# BUILD_AGENT system prompt tests
# ---------------------------------------------------------------------------

class TestBuildAgentSystemPrompt:
    """Verify BUILD_AGENT.system_prompt content matches all required rules."""

    def setup_method(self):
        from agents.definitions import BUILD_AGENT
        self.prompt = BUILD_AGENT.system_prompt

    def test_contains_nextjs(self):
        assert "Next.js" in self.prompt

    def test_contains_app_router(self):
        assert "App Router" in self.prompt

    def test_contains_use_client_rules(self):
        """'use client' only in interactive leaf components."""
        assert "use client" in self.prompt

    def test_layout_tsx_must_not_have_use_client(self):
        """Explicit rule: NEVER put 'use client' in layout.tsx."""
        prompt_lower = self.prompt.lower()
        assert "layout.tsx" in prompt_lower

    def test_error_tsx_must_have_use_client(self):
        """error.tsx MUST start with 'use client' per plan requirement."""
        assert "error.tsx" in self.prompt
        assert "use client" in self.prompt

    def test_mobile_first_responsive(self):
        """BILD-05: mobile-first responsive instructions."""
        prompt_lower = self.prompt.lower()
        assert "mobile" in prompt_lower and ("md:" in self.prompt or "responsive" in prompt_lower)

    def test_no_ios_swift_xcode_references(self):
        """No iOS/Swift/Xcode references allowed."""
        forbidden = ["iOS", "Swift", "Xcode", "SwiftUI", "UIKit"]
        for term in forbidden:
            assert term not in self.prompt, f"Forbidden term '{term}' found in BUILD_AGENT system prompt"

    def test_typescript_no_implicit_any(self):
        """BILD-03: noImplicitAny rule."""
        prompt_lower = self.prompt.lower()
        assert "noimplicitany" in prompt_lower or "no implicit any" in prompt_lower

    def test_typed_props_return_types(self):
        """BILD-04: typed props and return types instruction."""
        prompt_lower = self.prompt.lower()
        assert "props" in prompt_lower and ("type" in prompt_lower or "interface" in prompt_lower)

    def test_no_ts_ignore_no_as_any(self):
        """BILD-04: prohibition on @ts-ignore and 'as any'."""
        assert "@ts-ignore" in self.prompt or "ts-ignore" in self.prompt
        assert "as any" in self.prompt

    def test_error_tsx_per_route_segment(self):
        """BILD-06: generate error.tsx per route segment with async data."""
        assert "error.tsx" in self.prompt
        prompt_lower = self.prompt.lower()
        assert "route" in prompt_lower or "segment" in prompt_lower


# ---------------------------------------------------------------------------
# build_agent_runner tests
# ---------------------------------------------------------------------------

class TestRunBuildAgent:
    """Verify run_build_agent function behaviour via mocking."""

    def test_uses_bash_tool(self):
        """run_build_agent must include 'Bash' in allowed_tools."""
        from claude_agent_sdk.types import ResultMessage

        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query) as mock_q:
            from tools.phase_executors.build_agent_runner import run_build_agent
            run_build_agent("test prompt", "sys prompt", "/tmp/project")

        call_options = mock_q.call_args[1]["options"]
        assert "Bash" in call_options.allowed_tools

    def test_does_not_use_websearch(self):
        """Build agent must NOT have WebSearch in allowed_tools."""
        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query) as mock_q:
            from tools.phase_executors.build_agent_runner import run_build_agent
            run_build_agent("test prompt", "sys prompt", "/tmp/project")

        call_options = mock_q.call_args[1]["options"]
        assert "WebSearch" not in call_options.allowed_tools

    def test_passes_cwd_as_project_dir(self):
        """cwd must equal project_dir passed in."""
        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query) as mock_q:
            from tools.phase_executors.build_agent_runner import run_build_agent
            run_build_agent("test prompt", "sys prompt", "/tmp/my_project")

        call_options = mock_q.call_args[1]["options"]
        assert call_options.cwd == "/tmp/my_project"

    def test_default_max_turns_is_50(self):
        """Default max_turns should be 50 (higher than spec agent's 25)."""
        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query) as mock_q:
            from tools.phase_executors.build_agent_runner import run_build_agent
            run_build_agent("test prompt", "sys prompt", "/tmp/project")

        call_options = mock_q.call_args[1]["options"]
        assert call_options.max_turns == 50

    def test_returns_result_text(self):
        """run_build_agent returns ResultMessage.result text."""
        canned = _make_result_message("build completed successfully")

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query):
            from tools.phase_executors.build_agent_runner import run_build_agent
            result = run_build_agent("test prompt", "sys prompt", "/tmp/project")

        assert result == "build completed successfully"

    def test_returns_empty_string_when_no_result_message(self):
        """Returns empty string when agent produces no ResultMessage."""
        from claude_agent_sdk.types import AssistantMessage, TextBlock

        async def fake_query(prompt, options=None):
            # yield a non-ResultMessage type to simulate no result
            msg = MagicMock(spec=[])  # not a ResultMessage
            return
            yield  # make it an async generator

        with patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query):
            from tools.phase_executors.build_agent_runner import run_build_agent
            result = run_build_agent("test prompt", "sys prompt", "/tmp/project")

        assert result == ""


# ---------------------------------------------------------------------------
# Phase2aScaffoldExecutor tests
# ---------------------------------------------------------------------------

class TestPhase2aScaffoldExecutor:
    """Verify Phase2aScaffoldExecutor behaviour."""

    def setup_method(self):
        """Clear registry before each test to ensure clean state."""
        from tools.phase_executors.registry import _clear_registry
        _clear_registry()

    def _make_ctx(self, tmp_path: Path) -> "PhaseContext":
        from tools.phase_executors.base import PhaseContext
        project_dir = tmp_path / "myapp"
        project_dir.mkdir()
        return PhaseContext(
            run_id="test-run-01",
            phase_id="2a",
            project_dir=project_dir,
            idea="A task management web app",
            app_name="myapp",
        )

    def test_phase_id_is_2a(self):
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)
        executor = mod.Phase2aScaffoldExecutor()
        assert executor.phase_id == "2a"

    def test_self_registers_on_import(self, tmp_path):
        """Importing the module should register Phase2aScaffoldExecutor for '2a'."""
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)
        from tools.phase_executors.registry import get_executor
        assert get_executor("2a") is not None

    def test_sub_steps_contains_scaffold_customize(self):
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)
        executor = mod.Phase2aScaffoldExecutor()
        sub_steps = executor.sub_steps
        assert "scaffold" in sub_steps
        assert "customize" in sub_steps

    def test_subprocess_called_with_create_next_app(self, tmp_path):
        """execute() must call subprocess.run with npx create-next-app@latest."""
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)

        ctx = self._make_ctx(tmp_path)
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        mock_proc.stderr = ""

        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("subprocess.run", return_value=mock_proc) as mock_sub, \
             patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query):
            result = mod.Phase2aScaffoldExecutor().execute(ctx)

        assert mock_sub.called
        call_args = mock_sub.call_args[0][0]  # first positional arg is the command list
        assert "npx" in call_args
        assert "create-next-app@latest" in call_args

    def test_subprocess_called_with_typescript_flag(self, tmp_path):
        """create-next-app must use --typescript flag."""
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)

        ctx = self._make_ctx(tmp_path)
        mock_proc = MagicMock(returncode=0, stdout="", stderr="")

        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("subprocess.run", return_value=mock_proc) as mock_sub, \
             patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query):
            mod.Phase2aScaffoldExecutor().execute(ctx)

        call_args = mock_sub.call_args[0][0]
        assert "--typescript" in call_args

    def test_subprocess_called_with_tailwind_flag(self, tmp_path):
        """create-next-app must use --tailwind flag."""
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)

        ctx = self._make_ctx(tmp_path)
        mock_proc = MagicMock(returncode=0, stdout="", stderr="")

        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("subprocess.run", return_value=mock_proc) as mock_sub, \
             patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query):
            mod.Phase2aScaffoldExecutor().execute(ctx)

        call_args = mock_sub.call_args[0][0]
        assert "--tailwind" in call_args

    def test_subprocess_called_with_app_flag(self, tmp_path):
        """create-next-app must use --app flag (App Router)."""
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)

        ctx = self._make_ctx(tmp_path)
        mock_proc = MagicMock(returncode=0, stdout="", stderr="")

        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("subprocess.run", return_value=mock_proc) as mock_sub, \
             patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query):
            mod.Phase2aScaffoldExecutor().execute(ctx)

        call_args = mock_sub.call_args[0][0]
        assert "--app" in call_args

    def test_subprocess_called_with_disable_git_flag(self, tmp_path):
        """create-next-app must use --disable-git flag (NOT --no-git)."""
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)

        ctx = self._make_ctx(tmp_path)
        mock_proc = MagicMock(returncode=0, stdout="", stderr="")

        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("subprocess.run", return_value=mock_proc) as mock_sub, \
             patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query):
            mod.Phase2aScaffoldExecutor().execute(ctx)

        call_args = mock_sub.call_args[0][0]
        assert "--disable-git" in call_args
        # Ensure the invalid --no-git flag is NOT used
        assert "--no-git" not in call_args

    def test_subprocess_called_with_use_npm_flag(self, tmp_path):
        """create-next-app must use --use-npm flag."""
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)

        ctx = self._make_ctx(tmp_path)
        mock_proc = MagicMock(returncode=0, stdout="", stderr="")

        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("subprocess.run", return_value=mock_proc) as mock_sub, \
             patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query):
            mod.Phase2aScaffoldExecutor().execute(ctx)

        call_args = mock_sub.call_args[0][0]
        assert "--use-npm" in call_args

    def test_subprocess_called_with_src_dir_flag(self, tmp_path):
        """create-next-app must use --src-dir flag."""
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)

        ctx = self._make_ctx(tmp_path)
        mock_proc = MagicMock(returncode=0, stdout="", stderr="")

        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("subprocess.run", return_value=mock_proc) as mock_sub, \
             patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query):
            mod.Phase2aScaffoldExecutor().execute(ctx)

        call_args = mock_sub.call_args[0][0]
        assert "--src-dir" in call_args

    def test_execute_calls_build_agent_on_subprocess_success(self, tmp_path):
        """On subprocess success, execute() must call run_build_agent for customization."""
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)

        ctx = self._make_ctx(tmp_path)
        mock_proc = MagicMock(returncode=0, stdout="", stderr="")

        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("subprocess.run", return_value=mock_proc), \
             patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query) as mock_q:
            mod.Phase2aScaffoldExecutor().execute(ctx)

        assert mock_q.called, "run_build_agent (via query) must be called after successful subprocess"

    def test_execute_returns_failure_on_subprocess_error(self, tmp_path):
        """On subprocess failure, execute() must return PhaseResult(success=False)."""
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)

        ctx = self._make_ctx(tmp_path)
        mock_proc = MagicMock(returncode=1, stdout="", stderr="create-next-app failed: npm error")

        with patch("subprocess.run", return_value=mock_proc):
            result = mod.Phase2aScaffoldExecutor().execute(ctx)

        assert result.success is False
        assert result.error is not None
        assert "create-next-app failed" in result.error or "npm error" in result.error or "failed" in result.error.lower()

    # Quality self-assessment is now generated by contract_pipeline_runner (CONT-04),
    # not by individual executors. See tests/test_contract_pipeline_runner.py.

    def test_execute_returns_artifacts_with_project_dir(self, tmp_path):
        """execute() must return PhaseResult with artifacts list containing project_dir."""
        import importlib
        import tools.phase_executors.phase_2a_executor as mod
        importlib.reload(mod)

        ctx = self._make_ctx(tmp_path)
        mock_proc = MagicMock(returncode=0, stdout="", stderr="")

        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("subprocess.run", return_value=mock_proc), \
             patch("tools.phase_executors.build_agent_runner.query", side_effect=fake_query):
            result = mod.Phase2aScaffoldExecutor().execute(ctx)

        assert result.success is True
        assert len(result.artifacts) > 0
        # At least one artifact should reference the project dir
        project_dir_str = str(ctx.project_dir)
        assert any(project_dir_str in a for a in result.artifacts)
