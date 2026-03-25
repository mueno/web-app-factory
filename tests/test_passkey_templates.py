"""Tests for passkey (WebAuthn) auth template files.

Verifies that all 4 passkey template files exist and contain the required
@simplewebauthn imports and patterns per the WebAuthn bridge design.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Template directory under the package
TEMPLATES_AUTH_DIR = (
    Path(__file__).parent.parent / "web_app_factory" / "templates" / "auth"
)

# Paths to the 4 passkey templates
PASSKEY_REGISTER_API = TEMPLATES_AUTH_DIR / "passkey-register-api.ts.tmpl"
PASSKEY_AUTH_API = TEMPLATES_AUTH_DIR / "passkey-auth-api.ts.tmpl"
PASSKEY_CLIENT = TEMPLATES_AUTH_DIR / "passkey-client.tsx.tmpl"
PASSKEY_HOOKS = TEMPLATES_AUTH_DIR / "passkey-hooks.ts.tmpl"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# passkey-register-api.ts.tmpl
# ---------------------------------------------------------------------------

class TestPasskeyRegisterApiTemplate:
    """Tests for the WebAuthn registration ceremony server endpoint template."""

    def test_file_exists(self):
        """passkey-register-api.ts.tmpl must exist under templates/auth/."""
        assert PASSKEY_REGISTER_API.exists(), (
            f"Expected {PASSKEY_REGISTER_API} to exist"
        )

    def test_imports_simplewebauthn_server(self):
        """Template must import from @simplewebauthn/server."""
        content = _read(PASSKEY_REGISTER_API)
        assert "@simplewebauthn/server" in content, (
            "passkey-register-api.ts.tmpl must import @simplewebauthn/server"
        )

    def test_uses_generate_registration_options(self):
        """Template must use generateRegistrationOptions from @simplewebauthn/server."""
        content = _read(PASSKEY_REGISTER_API)
        assert "generateRegistrationOptions" in content, (
            "passkey-register-api.ts.tmpl must call generateRegistrationOptions"
        )

    def test_uses_verify_registration_response(self):
        """Template must use verifyRegistrationResponse from @simplewebauthn/server."""
        content = _read(PASSKEY_REGISTER_API)
        assert "verifyRegistrationResponse" in content, (
            "passkey-register-api.ts.tmpl must call verifyRegistrationResponse"
        )

    def test_contains_rp_name(self):
        """Template must include rpName in registration options."""
        content = _read(PASSKEY_REGISTER_API)
        assert "rpName" in content, (
            "passkey-register-api.ts.tmpl must include rpName in registration options"
        )

    def test_contains_rp_id(self):
        """Template must include rpID in registration options."""
        content = _read(PASSKEY_REGISTER_API)
        assert "rpID" in content, (
            "passkey-register-api.ts.tmpl must include rpID in registration options"
        )

    def test_contains_user_id(self):
        """Template must include userID in registration options."""
        content = _read(PASSKEY_REGISTER_API)
        assert "userID" in content, (
            "passkey-register-api.ts.tmpl must include userID in registration options"
        )

    def test_contains_user_name(self):
        """Template must include userName in registration options."""
        content = _read(PASSKEY_REGISTER_API)
        assert "userName" in content, (
            "passkey-register-api.ts.tmpl must include userName in registration options"
        )

    def test_contains_supabase_client(self):
        """Template must reference Supabase client for credential storage."""
        content = _read(PASSKEY_REGISTER_API)
        assert "supabase" in content, (
            "passkey-register-api.ts.tmpl must reference supabase for credential storage"
        )

    def test_does_not_use_get_session(self):
        """Template must not use getSession (use getUser instead)."""
        content = _read(PASSKEY_REGISTER_API)
        assert "getSession" not in content, (
            "passkey-register-api.ts.tmpl must not use getSession; use getUser instead"
        )

    def test_does_not_use_auth_ui_react(self):
        """Template must not import from @supabase/auth-ui-react (archived)."""
        content = _read(PASSKEY_REGISTER_API)
        assert "auth-ui-react" not in content, (
            "passkey-register-api.ts.tmpl must not use @supabase/auth-ui-react (archived Feb 2024)"
        )


# ---------------------------------------------------------------------------
# passkey-auth-api.ts.tmpl
# ---------------------------------------------------------------------------

class TestPasskeyAuthApiTemplate:
    """Tests for the WebAuthn authentication ceremony server endpoint template."""

    def test_file_exists(self):
        """passkey-auth-api.ts.tmpl must exist under templates/auth/."""
        assert PASSKEY_AUTH_API.exists(), (
            f"Expected {PASSKEY_AUTH_API} to exist"
        )

    def test_imports_simplewebauthn_server(self):
        """Template must import from @simplewebauthn/server."""
        content = _read(PASSKEY_AUTH_API)
        assert "@simplewebauthn/server" in content, (
            "passkey-auth-api.ts.tmpl must import @simplewebauthn/server"
        )

    def test_uses_generate_authentication_options(self):
        """Template must use generateAuthenticationOptions from @simplewebauthn/server."""
        content = _read(PASSKEY_AUTH_API)
        assert "generateAuthenticationOptions" in content, (
            "passkey-auth-api.ts.tmpl must call generateAuthenticationOptions"
        )

    def test_uses_verify_authentication_response(self):
        """Template must use verifyAuthenticationResponse from @simplewebauthn/server."""
        content = _read(PASSKEY_AUTH_API)
        assert "verifyAuthenticationResponse" in content, (
            "passkey-auth-api.ts.tmpl must call verifyAuthenticationResponse"
        )

    def test_contains_allow_credentials(self):
        """Template must include allowCredentials for filtering registered credentials."""
        content = _read(PASSKEY_AUTH_API)
        assert "allowCredentials" in content, (
            "passkey-auth-api.ts.tmpl must include allowCredentials"
        )

    def test_does_not_use_get_session(self):
        """Template must not use getSession (use getUser instead)."""
        content = _read(PASSKEY_AUTH_API)
        assert "getSession" not in content, (
            "passkey-auth-api.ts.tmpl must not use getSession; use getUser instead"
        )

    def test_does_not_use_auth_ui_react(self):
        """Template must not import from @supabase/auth-ui-react (archived)."""
        content = _read(PASSKEY_AUTH_API)
        assert "auth-ui-react" not in content, (
            "passkey-auth-api.ts.tmpl must not use @supabase/auth-ui-react (archived Feb 2024)"
        )


# ---------------------------------------------------------------------------
# passkey-client.tsx.tmpl
# ---------------------------------------------------------------------------

class TestPasskeyClientTemplate:
    """Tests for the client-side passkey UI component template."""

    def test_file_exists(self):
        """passkey-client.tsx.tmpl must exist under templates/auth/."""
        assert PASSKEY_CLIENT.exists(), (
            f"Expected {PASSKEY_CLIENT} to exist"
        )

    def test_is_use_client(self):
        """Template must declare 'use client' (Next.js client component)."""
        content = _read(PASSKEY_CLIENT)
        assert "'use client'" in content, (
            "passkey-client.tsx.tmpl must declare 'use client'"
        )

    def test_imports_simplewebauthn_browser(self):
        """Template must import from @simplewebauthn/browser."""
        content = _read(PASSKEY_CLIENT)
        assert "@simplewebauthn/browser" in content, (
            "passkey-client.tsx.tmpl must import @simplewebauthn/browser"
        )

    def test_uses_start_registration(self):
        """Template must use startRegistration from @simplewebauthn/browser."""
        content = _read(PASSKEY_CLIENT)
        assert "startRegistration" in content, (
            "passkey-client.tsx.tmpl must use startRegistration"
        )

    def test_uses_start_authentication(self):
        """Template must use startAuthentication from @simplewebauthn/browser."""
        content = _read(PASSKEY_CLIENT)
        assert "startAuthentication" in content, (
            "passkey-client.tsx.tmpl must use startAuthentication"
        )

    def test_has_registration_or_authentication_handler(self):
        """Template must have a handler function for registration and authentication flows."""
        content = _read(PASSKEY_CLIENT)
        has_use_callback = "useCallback" in content
        has_handler_fn = "handleRegister" in content or "handleAuthenticate" in content or "handlePasskey" in content
        assert has_use_callback or has_handler_fn, (
            "passkey-client.tsx.tmpl must have handler function(s) for registration/authentication"
        )

    def test_does_not_use_get_session(self):
        """Template must not use getSession."""
        content = _read(PASSKEY_CLIENT)
        assert "getSession" not in content, (
            "passkey-client.tsx.tmpl must not use getSession; use getUser instead"
        )

    def test_does_not_use_auth_ui_react(self):
        """Template must not import from @supabase/auth-ui-react (archived)."""
        content = _read(PASSKEY_CLIENT)
        assert "auth-ui-react" not in content, (
            "passkey-client.tsx.tmpl must not use @supabase/auth-ui-react (archived Feb 2024)"
        )


# ---------------------------------------------------------------------------
# passkey-hooks.ts.tmpl
# ---------------------------------------------------------------------------

class TestPasskeyHooksTemplate:
    """Tests for the Supabase session bridge hook template."""

    def test_file_exists(self):
        """passkey-hooks.ts.tmpl must exist under templates/auth/."""
        assert PASSKEY_HOOKS.exists(), (
            f"Expected {PASSKEY_HOOKS} to exist"
        )

    def test_contains_generate_link_or_sign_in_with_password(self):
        """Template must reference generateLink or signInWithPassword for Supabase session creation."""
        content = _read(PASSKEY_HOOKS)
        has_generate_link = "generateLink" in content
        has_sign_in = "signInWithPassword" in content
        assert has_generate_link or has_sign_in, (
            "passkey-hooks.ts.tmpl must reference generateLink or signInWithPassword "
            "for Supabase session creation after passkey verification"
        )

    def test_contains_service_role_key(self):
        """Template must reference SUPABASE_SERVICE_ROLE_KEY (admin API required)."""
        content = _read(PASSKEY_HOOKS)
        assert "SUPABASE_SERVICE_ROLE_KEY" in content, (
            "passkey-hooks.ts.tmpl must reference SUPABASE_SERVICE_ROLE_KEY "
            "for admin API operations (session creation after passkey verification)"
        )

    def test_does_not_use_get_session(self):
        """Template must not use getSession."""
        content = _read(PASSKEY_HOOKS)
        assert "getSession" not in content, (
            "passkey-hooks.ts.tmpl must not use getSession; use getUser instead"
        )

    def test_does_not_use_auth_ui_react(self):
        """Template must not import from @supabase/auth-ui-react (archived)."""
        content = _read(PASSKEY_HOOKS)
        assert "auth-ui-react" not in content, (
            "passkey-hooks.ts.tmpl must not use @supabase/auth-ui-react (archived Feb 2024)"
        )
