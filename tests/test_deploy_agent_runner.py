"""Tests for tools/phase_executors/deploy_agent_runner.py and DEPLOY_AGENT system prompt.

Covers:
- agents.definitions.DEPLOY_AGENT: system prompt is not placeholder; contains
  Vercel, Lighthouse, accessibility, legal generation expertise
- deploy_agent_runner.run_deploy_agent: allowed_tools, cwd, max_turns=75, return value
- ClaudeAgentOptions verification via mocked claude_agent_sdk.query
"""

from __future__ import annotations

from unittest.mock import patch

from claude_agent_sdk.types import ResultMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result_message(text: str = "mocked deploy agent output") -> ResultMessage:
    return ResultMessage(
        subtype="result",
        duration_ms=100,
        duration_api_ms=100,
        is_error=False,
        num_turns=3,
        session_id="deploy-test-session",
        result=text,
    )


# ---------------------------------------------------------------------------
# DEPLOY_AGENT system prompt tests
# ---------------------------------------------------------------------------


class TestDeployAgentSystemPrompt:
    """Verify DEPLOY_AGENT.system_prompt has real content, not a placeholder."""

    def setup_method(self):
        from agents.definitions import DEPLOY_AGENT
        self.prompt = DEPLOY_AGENT.system_prompt

    def test_not_placeholder(self):
        """system_prompt must not contain 'Phase 4' placeholder text."""
        assert "System prompt to be defined in Phase 4" not in self.prompt

    def test_contains_vercel(self):
        """system_prompt must mention Vercel deployment."""
        assert "Vercel" in self.prompt

    def test_contains_lighthouse(self):
        """system_prompt must mention Lighthouse for performance gating."""
        assert "Lighthouse" in self.prompt

    def test_contains_accessibility(self):
        """system_prompt must reference accessibility remediation."""
        prompt_lower = self.prompt.lower()
        assert "accessibility" in prompt_lower or "a11y" in prompt_lower

    def test_contains_legal_doc_instructions(self):
        """system_prompt must include legal document generation instructions."""
        prompt_lower = self.prompt.lower()
        assert "privacy" in prompt_lower or "terms" in prompt_lower

    def test_contains_japanese_law_basis(self):
        """system_prompt must mention Japanese law (APPI) as primary basis."""
        assert "APPI" in self.prompt or "Japanese" in self.prompt or "Japan" in self.prompt

    def test_contains_no_placeholder_instruction(self):
        """system_prompt must instruct agent not to use placeholder strings."""
        prompt_lower = self.prompt.lower()
        assert "placeholder" in prompt_lower or "your_app_name" in prompt_lower or "your_company" in prompt_lower

    def test_prompt_under_2000_chars(self):
        """system_prompt must be under 2000 characters to stay in context budget."""
        assert len(self.prompt) < 2000, f"Prompt is {len(self.prompt)} chars (limit: 2000)"


# ---------------------------------------------------------------------------
# run_deploy_agent tests
# ---------------------------------------------------------------------------


class TestRunDeployAgent:
    """Verify run_deploy_agent function via mocked claude_agent_sdk.query."""

    def test_allowed_tools_includes_bash(self):
        """run_deploy_agent must include 'Bash' in allowed_tools."""
        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.deploy_agent_runner.query", side_effect=fake_query) as mock_q:
            from tools.phase_executors.deploy_agent_runner import run_deploy_agent
            run_deploy_agent("test prompt", "sys prompt", "/tmp/project")

        call_options = mock_q.call_args[1]["options"]
        assert "Bash" in call_options.allowed_tools

    def test_allowed_tools_includes_read(self):
        """run_deploy_agent must include 'Read' in allowed_tools."""
        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.deploy_agent_runner.query", side_effect=fake_query) as mock_q:
            from tools.phase_executors.deploy_agent_runner import run_deploy_agent
            run_deploy_agent("test prompt", "sys prompt", "/tmp/project")

        call_options = mock_q.call_args[1]["options"]
        assert "Read" in call_options.allowed_tools

    def test_allowed_tools_includes_write(self):
        """run_deploy_agent must include 'Write' in allowed_tools."""
        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.deploy_agent_runner.query", side_effect=fake_query) as mock_q:
            from tools.phase_executors.deploy_agent_runner import run_deploy_agent
            run_deploy_agent("test prompt", "sys prompt", "/tmp/project")

        call_options = mock_q.call_args[1]["options"]
        assert "Write" in call_options.allowed_tools

    def test_does_not_use_websearch(self):
        """Deploy agent must NOT have WebSearch in allowed_tools."""
        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.deploy_agent_runner.query", side_effect=fake_query) as mock_q:
            from tools.phase_executors.deploy_agent_runner import run_deploy_agent
            run_deploy_agent("test prompt", "sys prompt", "/tmp/project")

        call_options = mock_q.call_args[1]["options"]
        assert "WebSearch" not in call_options.allowed_tools

    def test_passes_cwd_as_project_dir(self):
        """cwd must equal project_dir passed in."""
        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.deploy_agent_runner.query", side_effect=fake_query) as mock_q:
            from tools.phase_executors.deploy_agent_runner import run_deploy_agent
            run_deploy_agent("test prompt", "sys prompt", "/tmp/my_deploy_project")

        call_options = mock_q.call_args[1]["options"]
        assert call_options.cwd == "/tmp/my_deploy_project"

    def test_default_max_turns_is_75(self):
        """Default max_turns should be 75 (higher than build agent's 50)."""
        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.deploy_agent_runner.query", side_effect=fake_query) as mock_q:
            from tools.phase_executors.deploy_agent_runner import run_deploy_agent
            run_deploy_agent("test prompt", "sys prompt", "/tmp/project")

        call_options = mock_q.call_args[1]["options"]
        assert call_options.max_turns == 75

    def test_custom_max_turns_respected(self):
        """max_turns kwarg overrides default."""
        canned = _make_result_message()

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.deploy_agent_runner.query", side_effect=fake_query) as mock_q:
            from tools.phase_executors.deploy_agent_runner import run_deploy_agent
            run_deploy_agent("test prompt", "sys prompt", "/tmp/project", max_turns=10)

        call_options = mock_q.call_args[1]["options"]
        assert call_options.max_turns == 10

    def test_returns_result_text(self):
        """run_deploy_agent returns ResultMessage.result text."""
        canned = _make_result_message("deploy completed successfully")

        async def fake_query(prompt, options=None):
            yield canned

        with patch("tools.phase_executors.deploy_agent_runner.query", side_effect=fake_query):
            from tools.phase_executors.deploy_agent_runner import run_deploy_agent
            result = run_deploy_agent("test prompt", "sys prompt", "/tmp/project")

        assert result == "deploy completed successfully"

    def test_returns_empty_string_when_no_result_message(self):
        """Returns empty string when agent produces no ResultMessage."""
        async def fake_query(prompt, options=None):
            return
            yield  # noqa: unreachable — makes this an async generator

        with patch("tools.phase_executors.deploy_agent_runner.query", side_effect=fake_query):
            from tools.phase_executors.deploy_agent_runner import run_deploy_agent
            result = run_deploy_agent("test prompt", "sys prompt", "/tmp/project")

        assert result == ""
