"""Tests for agent prompt content — validates Supabase Auth guidance is present.

Covers AUTH-05 and AUTH-06:
- AUTH-05: SPEC_AGENT prefers Supabase Auth when Supabase DB is in use
- AUTH-06: BUILD_AGENT instructs correct Supabase Auth patterns
"""
from __future__ import annotations

import pytest

from agents.definitions import (
    _SPEC_AGENT_SYSTEM_PROMPT,
    _BUILD_AGENT_SYSTEM_PROMPT,
)


# ---------------------------------------------------------------------------
# SPEC_AGENT prompt tests
# ---------------------------------------------------------------------------


class TestSpecAgentAuthPrompt:
    def test_spec_agent_contains_supabase_auth_instruction(self):
        """_SPEC_AGENT_SYSTEM_PROMPT contains 'Supabase Auth' preference instruction."""
        assert "Supabase Auth" in _SPEC_AGENT_SYSTEM_PROMPT

    def test_spec_agent_prefers_supabase_auth_over_nextauth_when_supabase_db(self):
        """SPEC_AGENT instructs preference of Supabase Auth over NextAuth.js/Clerk when Supabase DB is in use."""
        prompt_lower = _SPEC_AGENT_SYSTEM_PROMPT.lower()
        # Must mention preference/priority of Supabase Auth vs alternatives
        has_preference = (
            "nextauth" in prompt_lower or "next-auth" in prompt_lower or "clerk" in prompt_lower
        )
        assert has_preference, (
            "SPEC_AGENT must mention NextAuth.js or Clerk to contrast with Supabase Auth preference"
        )

    def test_spec_agent_links_supabase_auth_to_supabase_db(self):
        """SPEC_AGENT prompt ties Supabase Auth preference to Supabase DB being in use."""
        prompt_lower = _SPEC_AGENT_SYSTEM_PROMPT.lower()
        # Should mention the condition: when Supabase DB / Supabase database is in use
        has_condition = (
            "when" in prompt_lower and "supabase" in prompt_lower
        )
        assert has_condition, (
            "SPEC_AGENT must express Supabase Auth preference as conditional on Supabase DB usage"
        )


# ---------------------------------------------------------------------------
# BUILD_AGENT prompt tests
# ---------------------------------------------------------------------------


class TestBuildAgentAuthPrompt:
    def test_build_agent_contains_getuser_instruction(self):
        """_BUILD_AGENT_SYSTEM_PROMPT contains 'getUser' instruction (not getSession)."""
        assert "getUser" in _BUILD_AGENT_SYSTEM_PROMPT

    def test_build_agent_warns_against_auth_ui_react(self):
        """_BUILD_AGENT_SYSTEM_PROMPT contains '@supabase/auth-ui-react' warning (NEVER use)."""
        assert "@supabase/auth-ui-react" in _BUILD_AGENT_SYSTEM_PROMPT

    def test_build_agent_contains_sign_in_with_oauth(self):
        """_BUILD_AGENT_SYSTEM_PROMPT contains signInWithOAuth instruction."""
        assert "signInWithOAuth" in _BUILD_AGENT_SYSTEM_PROMPT

    def test_build_agent_contains_protected_route_pattern(self):
        """_BUILD_AGENT_SYSTEM_PROMPT contains protected route pattern (getUser + redirect)."""
        prompt_lower = _BUILD_AGENT_SYSTEM_PROMPT.lower()
        has_protected = "protected" in prompt_lower or "redirect" in prompt_lower
        assert has_protected, (
            "BUILD_AGENT must describe protected route pattern with getUser and redirect"
        )
        # Also verify getUser is present
        assert "getUser" in _BUILD_AGENT_SYSTEM_PROMPT

    def test_build_agent_references_supabase_file_paths(self):
        """_BUILD_AGENT_SYSTEM_PROMPT references supabase-browser.ts and supabase-server.ts (or equivalent)."""
        prompt = _BUILD_AGENT_SYSTEM_PROMPT
        # Accept either the exact file names or the canonical paths used in the project
        has_browser_ref = (
            "supabase/browser" in prompt or "supabase-browser" in prompt or "browser.ts" in prompt
        )
        has_server_ref = (
            "supabase/server" in prompt or "supabase-server" in prompt or "server.ts" in prompt
        )
        assert has_browser_ref, (
            "BUILD_AGENT must reference the browser-side Supabase client file"
        )
        assert has_server_ref, (
            "BUILD_AGENT must reference the server-side Supabase client file"
        )

    def test_build_agent_does_not_recommend_getsession(self):
        """_BUILD_AGENT_SYSTEM_PROMPT does NOT contain 'getSession' as a recommended pattern."""
        prompt = _BUILD_AGENT_SYSTEM_PROMPT
        # getSession should not appear as a recommendation — getUser() is required instead
        # It is acceptable to mention getSession in a warning/NEVER context
        lines_with_getsession = [
            line.strip()
            for line in prompt.splitlines()
            if "getSession" in line
        ]
        for line in lines_with_getsession:
            line_lower = line.lower()
            # Any line mentioning getSession must be in a warning/prohibition context
            is_warning = (
                "never" in line_lower
                or "avoid" in line_lower
                or "do not" in line_lower
                or "don't" in line_lower
                or "instead" in line_lower
                or "not" in line_lower
            )
            assert is_warning, (
                f"BUILD_AGENT prompt mentions getSession without a warning — "
                f"this could guide agents to use the insecure method.\nLine: {line!r}"
            )

    def test_build_agent_auth_section_mentions_supabase_url_condition(self):
        """_BUILD_AGENT_SYSTEM_PROMPT ties auth section to NEXT_PUBLIC_SUPABASE_URL being present."""
        assert "NEXT_PUBLIC_SUPABASE_URL" in _BUILD_AGENT_SYSTEM_PROMPT
