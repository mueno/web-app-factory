"""Tests for auth template files under web_app_factory/templates/auth/.

Verifies auth template content and security constraints:
- Middleware uses getUser() (NOT getSession), anon key (NOT service_role)
- Login page uses signInWithOAuth with Google and Apple providers
- Callback route uses exchangeCodeForSession with open-redirect prevention
- Signout page uses signOut({ scope: 'global' }) with redirect('/')
- No archived library @supabase/auth-ui-react is imported
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Template directory paths
TEMPLATES_DIR = Path(__file__).parent.parent / "web_app_factory" / "templates"
AUTH_TEMPLATES_DIR = TEMPLATES_DIR / "auth"

MIDDLEWARE_TEMPLATE = TEMPLATES_DIR / "auth-middleware.ts.tmpl"
LOGIN_TEMPLATE = AUTH_TEMPLATES_DIR / "login-page.tsx.tmpl"
SIGNUP_TEMPLATE = AUTH_TEMPLATES_DIR / "signup-page.tsx.tmpl"
SIGNOUT_TEMPLATE = AUTH_TEMPLATES_DIR / "signout-page.tsx.tmpl"
CALLBACK_TEMPLATE = AUTH_TEMPLATES_DIR / "callback-route.ts.tmpl"
AUTH_SETUP_TEMPLATE = AUTH_TEMPLATES_DIR / "AUTH_SETUP.md.tmpl"


class TestAuthMiddlewareTemplate:
    """Tests for auth-middleware.ts.tmpl — session refresh on every request."""

    def test_middleware_template_file_exists(self):
        """auth-middleware.ts.tmpl must exist in templates directory."""
        assert MIDDLEWARE_TEMPLATE.exists(), (
            f"auth-middleware.ts.tmpl not found at {MIDDLEWARE_TEMPLATE}"
        )

    def test_middleware_uses_create_server_client(self):
        """Middleware must import createServerClient from @supabase/ssr."""
        content = MIDDLEWARE_TEMPLATE.read_text(encoding="utf-8")
        assert "createServerClient" in content
        assert "@supabase/ssr" in content

    def test_middleware_uses_get_user(self):
        """Middleware must call getUser() for session validation (not getSession)."""
        content = MIDDLEWARE_TEMPLATE.read_text(encoding="utf-8")
        assert "getUser" in content

    def test_middleware_uses_anon_key(self):
        """Middleware must use NEXT_PUBLIC_SUPABASE_ANON_KEY (NOT service_role)."""
        content = MIDDLEWARE_TEMPLATE.read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_SUPABASE_ANON_KEY" in content

    def test_middleware_cookie_get_all(self):
        """Middleware must implement cookies.getAll() for request cookies."""
        content = MIDDLEWARE_TEMPLATE.read_text(encoding="utf-8")
        assert "getAll" in content

    def test_middleware_cookie_set_all(self):
        """Middleware must implement cookies.setAll() for response cookies."""
        content = MIDDLEWARE_TEMPLATE.read_text(encoding="utf-8")
        assert "setAll" in content

    def test_middleware_excludes_auth_paths(self):
        """Middleware must exclude /auth paths from redirect logic."""
        content = MIDDLEWARE_TEMPLATE.read_text(encoding="utf-8")
        assert "/auth" in content

    def test_middleware_has_return_to_param(self):
        """Middleware redirect to login must include returnTo search param."""
        content = MIDDLEWARE_TEMPLATE.read_text(encoding="utf-8")
        assert "returnTo" in content

    def test_middleware_does_not_use_get_session(self):
        """Middleware must NOT use getSession() — deprecated in server context."""
        content = MIDDLEWARE_TEMPLATE.read_text(encoding="utf-8")
        assert "getSession" not in content, (
            "Middleware must not use getSession() — use getUser() instead "
            "(getSession is not guaranteed to revalidate in server context)"
        )

    def test_middleware_does_not_use_service_role(self):
        """Middleware must NOT use service_role key — anon key only."""
        content = MIDDLEWARE_TEMPLATE.read_text(encoding="utf-8").lower()
        assert "service_role" not in content, (
            "Middleware must not use service_role key — "
            "middleware only refreshes sessions, never accesses privileged data"
        )

    def test_middleware_imports_from_supabase_ssr(self):
        """Middleware must import from @supabase/ssr (not auth-helpers-nextjs)."""
        content = MIDDLEWARE_TEMPLATE.read_text(encoding="utf-8")
        assert "from '@supabase/ssr'" in content or 'from "@supabase/ssr"' in content

    def test_middleware_has_matcher_config(self):
        """Middleware must export a config with matcher to exclude static assets."""
        content = MIDDLEWARE_TEMPLATE.read_text(encoding="utf-8")
        assert "matcher" in content
        assert "config" in content


class TestLoginPageTemplate:
    """Tests for auth/login-page.tsx.tmpl — OAuth sign-in with Google and Apple."""

    def test_login_template_file_exists(self):
        """login-page.tsx.tmpl must exist in auth templates directory."""
        assert LOGIN_TEMPLATE.exists(), (
            f"login-page.tsx.tmpl not found at {LOGIN_TEMPLATE}"
        )

    def test_login_template_is_client_component(self):
        """Login page must be a client component (needs browser API for OAuth)."""
        content = LOGIN_TEMPLATE.read_text(encoding="utf-8")
        assert "'use client'" in content or '"use client"' in content

    def test_login_template_uses_sign_in_with_oauth(self):
        """Login page must use signInWithOAuth() for authentication."""
        content = LOGIN_TEMPLATE.read_text(encoding="utf-8")
        assert "signInWithOAuth" in content

    def test_login_template_has_google_provider(self):
        """Login page must include Google OAuth provider."""
        content = LOGIN_TEMPLATE.read_text(encoding="utf-8")
        assert "provider: 'google'" in content or "provider: \"google\"" in content

    def test_login_template_has_apple_provider(self):
        """Login page must include Apple OAuth provider."""
        content = LOGIN_TEMPLATE.read_text(encoding="utf-8")
        assert "provider: 'apple'" in content or "provider: \"apple\"" in content

    def test_login_template_has_return_to_param(self):
        """Login page must read and pass returnTo parameter for post-auth redirect."""
        content = LOGIN_TEMPLATE.read_text(encoding="utf-8")
        assert "returnTo" in content

    def test_login_template_uses_auth_callback_path(self):
        """Login page must redirect to /auth/callback after OAuth."""
        content = LOGIN_TEMPLATE.read_text(encoding="utf-8")
        assert "/auth/callback" in content

    def test_login_template_does_not_use_auth_ui_react(self):
        """Login page must NOT import @supabase/auth-ui-react — it is archived."""
        content = LOGIN_TEMPLATE.read_text(encoding="utf-8")
        assert "auth-ui-react" not in content, (
            "Login page must not use @supabase/auth-ui-react — "
            "it is archived (Feb 2024) and has no passkey support"
        )

    def test_login_template_does_not_use_get_session(self):
        """Login page must NOT call getSession()."""
        content = LOGIN_TEMPLATE.read_text(encoding="utf-8")
        assert "getSession" not in content

    def test_login_template_imports_from_supabase_ssr(self):
        """Login page must use @supabase/ssr (not deprecated auth-helpers-nextjs)."""
        content = LOGIN_TEMPLATE.read_text(encoding="utf-8")
        # Must not use the deprecated auth-helpers package
        assert "auth-helpers-nextjs" not in content, (
            "Login page must not use deprecated @supabase/auth-helpers-nextjs; "
            "use @supabase/ssr instead"
        )
        # Must use either @supabase/ssr directly or the browser client wrapper
        assert (
            "supabase/browser" in content
            or "createBrowserClient" in content
            or "@supabase/ssr" in content
        ), "Login page must import from @supabase/ssr or a browser client wrapper"


class TestSignupPageTemplate:
    """Tests for auth/signup-page.tsx.tmpl — OAuth-only signup."""

    def test_signup_template_file_exists(self):
        """signup-page.tsx.tmpl must exist in auth templates directory."""
        assert SIGNUP_TEMPLATE.exists(), (
            f"signup-page.tsx.tmpl not found at {SIGNUP_TEMPLATE}"
        )

    def test_signup_template_has_content(self):
        """signup-page.tsx.tmpl must have non-trivial content."""
        content = SIGNUP_TEMPLATE.read_text(encoding="utf-8")
        assert len(content.strip()) > 50, (
            "signup-page.tsx.tmpl appears empty or trivial"
        )


class TestSignoutPageTemplate:
    """Tests for auth/signout-page.tsx.tmpl — global signout with redirect."""

    def test_signout_template_file_exists(self):
        """signout-page.tsx.tmpl must exist in auth templates directory."""
        assert SIGNOUT_TEMPLATE.exists(), (
            f"signout-page.tsx.tmpl not found at {SIGNOUT_TEMPLATE}"
        )

    def test_signout_template_uses_sign_out(self):
        """Signout page must call signOut()."""
        content = SIGNOUT_TEMPLATE.read_text(encoding="utf-8")
        assert "signOut" in content

    def test_signout_template_uses_global_scope(self):
        """Signout must use scope: 'global' (per locked decision)."""
        content = SIGNOUT_TEMPLATE.read_text(encoding="utf-8")
        assert "scope" in content
        assert "global" in content

    def test_signout_template_redirects_to_root(self):
        """Signout page must redirect to / after sign out."""
        content = SIGNOUT_TEMPLATE.read_text(encoding="utf-8")
        assert "redirect('/')" in content or 'redirect("/")' in content


class TestCallbackRouteTemplate:
    """Tests for auth/callback-route.ts.tmpl — PKCE code exchange."""

    def test_callback_template_file_exists(self):
        """callback-route.ts.tmpl must exist in auth templates directory."""
        assert CALLBACK_TEMPLATE.exists(), (
            f"callback-route.ts.tmpl not found at {CALLBACK_TEMPLATE}"
        )

    def test_callback_template_uses_exchange_code_for_session(self):
        """Callback route must use exchangeCodeForSession for PKCE exchange."""
        content = CALLBACK_TEMPLATE.read_text(encoding="utf-8")
        assert "exchangeCodeForSession" in content

    def test_callback_template_extracts_code_param(self):
        """Callback route must extract the 'code' parameter from URL."""
        content = CALLBACK_TEMPLATE.read_text(encoding="utf-8")
        assert "code" in content

    def test_callback_template_has_return_to_param(self):
        """Callback route must support returnTo parameter for post-auth redirect."""
        content = CALLBACK_TEMPLATE.read_text(encoding="utf-8")
        assert "returnTo" in content

    def test_callback_template_validates_return_to(self):
        """Callback route must validate returnTo starts with '/' to prevent open redirect."""
        content = CALLBACK_TEMPLATE.read_text(encoding="utf-8")
        assert "startsWith('/')" in content or 'startsWith("/")' in content, (
            "Callback route must validate returnTo starts with '/' to prevent open redirect attacks"
        )

    def test_callback_template_imports_from_supabase_ssr(self):
        """Callback route must import from @supabase/ssr."""
        content = CALLBACK_TEMPLATE.read_text(encoding="utf-8")
        assert "@supabase/ssr" in content


class TestAuthSetupTemplate:
    """Tests for auth/AUTH_SETUP.md.tmpl — manual OAuth setup README."""

    def test_auth_setup_template_file_exists(self):
        """AUTH_SETUP.md.tmpl must exist in auth templates directory."""
        assert AUTH_SETUP_TEMPLATE.exists(), (
            f"AUTH_SETUP.md.tmpl not found at {AUTH_SETUP_TEMPLATE}"
        )

    def test_auth_setup_covers_google_cloud_console(self):
        """AUTH_SETUP.md.tmpl must cover Google Cloud Console setup steps."""
        content = AUTH_SETUP_TEMPLATE.read_text(encoding="utf-8")
        assert "Google Cloud Console" in content

    def test_auth_setup_covers_google_apis_and_services(self):
        """AUTH_SETUP.md.tmpl must mention APIs & Services > Credentials navigation."""
        content = AUTH_SETUP_TEMPLATE.read_text(encoding="utf-8")
        assert "APIs & Services" in content
        assert "Credentials" in content

    def test_auth_setup_covers_apple_developer_portal(self):
        """AUTH_SETUP.md.tmpl must cover Apple Developer Portal setup steps."""
        content = AUTH_SETUP_TEMPLATE.read_text(encoding="utf-8")
        assert "Apple Developer Portal" in content

    def test_auth_setup_covers_p8_key(self):
        """AUTH_SETUP.md.tmpl must mention .p8 key file for Apple Sign-In."""
        content = AUTH_SETUP_TEMPLATE.read_text(encoding="utf-8")
        assert ".p8" in content

    def test_auth_setup_covers_apple_key_rotation(self):
        """AUTH_SETUP.md.tmpl must include 6-month rotation reminder for Apple .p8 key."""
        content = AUTH_SETUP_TEMPLATE.read_text(encoding="utf-8")
        # Accept "6 months" or "6-month" or "6month"
        assert "6 month" in content or "6-month" in content, (
            "AUTH_SETUP.md.tmpl must include prominent 6-month rotation reminder for Apple .p8 key"
        )

    def test_auth_setup_covers_redirect_url_allowlist(self):
        """AUTH_SETUP.md.tmpl must explain Supabase redirect URL allowlist setup."""
        content = AUTH_SETUP_TEMPLATE.read_text(encoding="utf-8")
        assert "Redirect URL" in content or "redirect_url" in content

    def test_auth_setup_covers_localhost_allowlist(self):
        """AUTH_SETUP.md.tmpl must include localhost:3000 in allowlist guidance."""
        content = AUTH_SETUP_TEMPLATE.read_text(encoding="utf-8")
        assert "localhost:3000" in content

    def test_auth_setup_has_google_env_vars(self):
        """AUTH_SETUP.md.tmpl must list GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET env vars."""
        content = AUTH_SETUP_TEMPLATE.read_text(encoding="utf-8")
        assert "GOOGLE_CLIENT_ID" in content
        assert "GOOGLE_CLIENT_SECRET" in content

    def test_auth_setup_has_apple_env_vars(self):
        """AUTH_SETUP.md.tmpl must list APPLE_CLIENT_ID and APPLE_CLIENT_SECRET env vars."""
        content = AUTH_SETUP_TEMPLATE.read_text(encoding="utf-8")
        assert "APPLE_CLIENT_ID" in content
        assert "APPLE_CLIENT_SECRET" in content


class TestAllAuthTemplatesUseSupabaseSSR:
    """Cross-cutting test: all TypeScript templates must use @supabase/ssr."""

    @pytest.mark.parametrize("template_path", [
        MIDDLEWARE_TEMPLATE,
        LOGIN_TEMPLATE,
        CALLBACK_TEMPLATE,
    ])
    def test_template_uses_supabase_ssr_not_auth_helpers(self, template_path):
        """TypeScript auth templates must not import @supabase/auth-helpers-nextjs."""
        content = template_path.read_text(encoding="utf-8")
        assert "auth-helpers-nextjs" not in content, (
            f"{template_path.name} must not use deprecated auth-helpers-nextjs; "
            "use @supabase/ssr instead"
        )
