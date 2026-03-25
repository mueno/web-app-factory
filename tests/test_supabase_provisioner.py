"""Tests for SupabaseProvisioner and associated methods.

All HTTP calls are mocked via pytest-httpx or unittest.mock.
Credential values are never logged (security contract from 10-security-core.md).
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web_app_factory._supabase_provisioner import SupabaseProvisioner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def provisioner() -> SupabaseProvisioner:
    """Return a SupabaseProvisioner with placeholder credentials."""
    return SupabaseProvisioner(
        access_token="test-access-token",
        org_id="test-org-id",
    )


# ---------------------------------------------------------------------------
# create_project tests
# ---------------------------------------------------------------------------


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_create_project_posts_to_correct_endpoint(self, provisioner):
        """create_project() must POST to /v1/projects."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"ref": "abc123", "name": "my-app"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            result = await provisioner.create_project("my-app")

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "api.supabase.com" in call_args.args[0]
        assert "/v1/projects" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_create_project_sends_correct_payload(self, provisioner):
        """create_project() must include name, organization_slug, db_pass, region."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"ref": "abc123"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            await provisioner.create_project("my-app")

        call_kwargs = mock_client.post.call_args.kwargs
        payload = call_kwargs.get("json") or call_kwargs.get("data") or {}
        # If passed positionally as second arg:
        if not payload and len(mock_client.post.call_args.args) > 1:
            payload = mock_client.post.call_args.args[1]

        assert "name" in payload
        assert "organization_slug" in payload
        assert "db_pass" in payload
        assert "region" in payload

    @pytest.mark.asyncio
    async def test_create_project_returns_ref_and_db_pass(self, provisioner):
        """create_project() must return dict with 'ref' and '_db_pass' keys."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"ref": "abc123", "name": "my-app"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            result = await provisioner.create_project("my-app")

        assert "ref" in result
        assert "_db_pass" in result
        assert result["ref"] == "abc123"

    @pytest.mark.asyncio
    async def test_create_project_generates_strong_db_pass(self, provisioner):
        """create_project() must generate db_pass with secrets.token_urlsafe(32)."""
        generated_passes: list[str] = []

        original_token_urlsafe = __import__("secrets").token_urlsafe

        def capture_token_urlsafe(n):
            result = original_token_urlsafe(n)
            generated_passes.append(result)
            return result

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"ref": "abc123"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            with patch("web_app_factory._supabase_provisioner.secrets.token_urlsafe", side_effect=capture_token_urlsafe):
                result = await provisioner.create_project("my-app")

        # token_urlsafe should be called with 32
        assert len(generated_passes) >= 1
        # db_pass matches the generated value
        assert result["_db_pass"] == generated_passes[0]


# ---------------------------------------------------------------------------
# poll_until_healthy tests
# ---------------------------------------------------------------------------


class TestPollUntilHealthy:
    @pytest.mark.asyncio
    async def test_poll_exits_when_all_active_healthy(self, provisioner):
        """poll_until_healthy() returns when all services are ACTIVE_HEALTHY."""
        healthy_response = MagicMock()
        healthy_response.status_code = 200
        healthy_response.json.return_value = [
            {"name": "db", "status": "ACTIVE_HEALTHY"},
            {"name": "auth", "status": "ACTIVE_HEALTHY"},
        ]
        healthy_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=healthy_response)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            with patch("web_app_factory._supabase_provisioner.asyncio.sleep", new_callable=AsyncMock):
                # Should not raise
                await provisioner.poll_until_healthy("abc123", timeout_s=30, interval_s=1)

        mock_client.get.assert_called()

    @pytest.mark.asyncio
    async def test_poll_raises_timeout_error(self, provisioner):
        """poll_until_healthy() raises TimeoutError after timeout_s seconds."""
        not_ready_response = MagicMock()
        not_ready_response.status_code = 200
        not_ready_response.json.return_value = [
            {"name": "db", "status": "COMING_UP"},
        ]
        not_ready_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=not_ready_response)

        # Fake time: start at 0, then jump past timeout
        times = [0, 0, 5, 10, 15, 20, 25, 30, 35]  # 35 > timeout_s=30
        time_iter = iter(times)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            with patch("web_app_factory._supabase_provisioner.asyncio.sleep", new_callable=AsyncMock):
                with patch("web_app_factory._supabase_provisioner.time.monotonic", side_effect=time_iter):
                    with pytest.raises(TimeoutError):
                        await provisioner.poll_until_healthy("abc123", timeout_s=30, interval_s=1)

    @pytest.mark.asyncio
    async def test_poll_treats_empty_list_as_not_healthy(self, provisioner):
        """poll_until_healthy() treats empty health list [] as not-yet-healthy (Pitfall 5)."""
        responses = [
            # First call: empty list (not healthy)
            MagicMock(status_code=200, json=MagicMock(return_value=[]), raise_for_status=MagicMock()),
            # Second call: all healthy
            MagicMock(
                status_code=200,
                json=MagicMock(return_value=[{"name": "db", "status": "ACTIVE_HEALTHY"}]),
                raise_for_status=MagicMock(),
            ),
        ]
        response_iter = iter(responses)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=lambda url, **kw: next(response_iter))

        times = [0, 0, 2, 4]  # well within timeout
        time_iter = iter(times)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            with patch("web_app_factory._supabase_provisioner.asyncio.sleep", new_callable=AsyncMock):
                with patch("web_app_factory._supabase_provisioner.time.monotonic", side_effect=time_iter):
                    await provisioner.poll_until_healthy("abc123", timeout_s=300, interval_s=1)

        # Called at least twice (once for empty, once for healthy)
        assert mock_client.get.call_count >= 2

    @pytest.mark.asyncio
    async def test_poll_treats_partial_healthy_as_not_ready(self, provisioner):
        """poll_until_healthy() continues polling when only some services are ACTIVE_HEALTHY."""
        responses = [
            # First call: partial (one not healthy)
            MagicMock(
                status_code=200,
                json=MagicMock(return_value=[
                    {"name": "db", "status": "ACTIVE_HEALTHY"},
                    {"name": "auth", "status": "COMING_UP"},
                ]),
                raise_for_status=MagicMock(),
            ),
            # Second call: all healthy
            MagicMock(
                status_code=200,
                json=MagicMock(return_value=[
                    {"name": "db", "status": "ACTIVE_HEALTHY"},
                    {"name": "auth", "status": "ACTIVE_HEALTHY"},
                ]),
                raise_for_status=MagicMock(),
            ),
        ]
        response_iter = iter(responses)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=lambda url, **kw: next(response_iter))

        times = [0, 0, 2, 4]
        time_iter = iter(times)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            with patch("web_app_factory._supabase_provisioner.asyncio.sleep", new_callable=AsyncMock):
                with patch("web_app_factory._supabase_provisioner.time.monotonic", side_effect=time_iter):
                    await provisioner.poll_until_healthy("abc123", timeout_s=300, interval_s=1)

        assert mock_client.get.call_count == 2


# ---------------------------------------------------------------------------
# get_api_keys tests
# ---------------------------------------------------------------------------


class TestGetApiKeys:
    @pytest.mark.asyncio
    async def test_get_api_keys_extracts_anon_and_service_role(self, provisioner):
        """get_api_keys() extracts anon_key and service_role_key from API response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "anon", "api_key": "anon-key-value"},
            {"name": "service_role", "api_key": "service-role-key-value"},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            result = await provisioner.get_api_keys("abc123")

        assert "anon_key" in result
        assert "service_role_key" in result
        assert result["anon_key"] == "anon-key-value"
        assert result["service_role_key"] == "service-role-key-value"

    @pytest.mark.asyncio
    async def test_get_api_keys_calls_correct_endpoint(self, provisioner):
        """get_api_keys() GETs from /v1/projects/{ref}/api-keys."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "anon", "api_key": "anon-key-value"},
            {"name": "service_role", "api_key": "service-role-key-value"},
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            await provisioner.get_api_keys("myref123")

        call_url = mock_client.get.call_args.args[0]
        assert "myref123" in call_url
        assert "api-keys" in call_url


# ---------------------------------------------------------------------------
# inject_vercel_env tests
# ---------------------------------------------------------------------------


class TestInjectVercelEnv:
    @pytest.mark.asyncio
    async def test_inject_vercel_env_posts_all_three_vars(self, provisioner):
        """inject_vercel_env() must inject NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        posted_envs: list[dict] = []

        async def capture_post(url, **kwargs):
            payload = kwargs.get("json", [])
            if isinstance(payload, list):
                posted_envs.extend(payload)
            elif isinstance(payload, dict):
                posted_envs.append(payload)
            return mock_response

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=capture_post)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            await provisioner.inject_vercel_env(
                vercel_token="vercel-tok",
                vercel_project_id="prj_abc",
                supabase_url="https://abc.supabase.co",
                anon_key="anon-key",
                service_role_key="srk",
            )

        env_keys = {e["key"] for e in posted_envs}
        assert "NEXT_PUBLIC_SUPABASE_URL" in env_keys
        assert "NEXT_PUBLIC_SUPABASE_ANON_KEY" in env_keys
        assert "SUPABASE_SERVICE_ROLE_KEY" in env_keys

    @pytest.mark.asyncio
    async def test_inject_vercel_env_service_role_is_sensitive(self, provisioner):
        """SUPABASE_SERVICE_ROLE_KEY must be type 'sensitive' (not 'plain')."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        posted_envs: list[dict] = []

        async def capture_post(url, **kwargs):
            payload = kwargs.get("json", [])
            if isinstance(payload, list):
                posted_envs.extend(payload)
            elif isinstance(payload, dict):
                posted_envs.append(payload)
            return mock_response

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=capture_post)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            await provisioner.inject_vercel_env(
                vercel_token="vercel-tok",
                vercel_project_id="prj_abc",
                supabase_url="https://abc.supabase.co",
                anon_key="anon-key",
                service_role_key="srk",
            )

        srk_envs = [e for e in posted_envs if e.get("key") == "SUPABASE_SERVICE_ROLE_KEY"]
        assert len(srk_envs) >= 1
        for env in srk_envs:
            assert env.get("type") == "sensitive", (
                f"SUPABASE_SERVICE_ROLE_KEY must be 'sensitive', got {env.get('type')!r}"
            )

    @pytest.mark.asyncio
    async def test_inject_vercel_env_anon_key_is_plain(self, provisioner):
        """NEXT_PUBLIC_SUPABASE_ANON_KEY must be type 'plain' (it is the public key)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        posted_envs: list[dict] = []

        async def capture_post(url, **kwargs):
            payload = kwargs.get("json", [])
            if isinstance(payload, list):
                posted_envs.extend(payload)
            elif isinstance(payload, dict):
                posted_envs.append(payload)
            return mock_response

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=capture_post)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            await provisioner.inject_vercel_env(
                vercel_token="vercel-tok",
                vercel_project_id="prj_abc",
                supabase_url="https://abc.supabase.co",
                anon_key="anon-key",
                service_role_key="srk",
            )

        anon_envs = [e for e in posted_envs if e.get("key") == "NEXT_PUBLIC_SUPABASE_ANON_KEY"]
        assert len(anon_envs) >= 1
        for env in anon_envs:
            assert env.get("type") == "plain", (
                f"NEXT_PUBLIC_SUPABASE_ANON_KEY must be 'plain', got {env.get('type')!r}"
            )

    @pytest.mark.asyncio
    async def test_inject_vercel_env_uses_correct_vercel_endpoint(self, provisioner):
        """inject_vercel_env() must POST to api.vercel.com/v10/projects/{id}/env."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            await provisioner.inject_vercel_env(
                vercel_token="vercel-tok",
                vercel_project_id="prj_abc123",
                supabase_url="https://abc.supabase.co",
                anon_key="anon-key",
                service_role_key="srk",
            )

        call_url = mock_client.post.call_args.args[0]
        assert "api.vercel.com" in call_url
        assert "prj_abc123" in call_url
        assert "env" in call_url


# ---------------------------------------------------------------------------
# configure_oauth_providers tests
# ---------------------------------------------------------------------------


class TestConfigureOAuthProviders:
    @pytest.mark.asyncio
    async def test_google_only_sends_correct_patch(self, provisioner):
        """configure_oauth_providers with Google credentials PATCHes with external_google_* fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        patched_payloads: list[dict] = []

        async def capture_patch(url, **kwargs):
            patched_payloads.append(kwargs.get("json", {}))
            return mock_response

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.patch = AsyncMock(side_effect=capture_patch)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            await provisioner.configure_oauth_providers(
                ref="proj123",
                google_client_id="gid",
                google_secret="gsecret",
                apple_client_id=None,
                apple_secret=None,
            )

        assert len(patched_payloads) == 1
        payload = patched_payloads[0]
        assert payload.get("external_google_enabled") is True
        assert payload.get("external_google_client_id") == "gid"
        assert payload.get("external_google_secret") == "gsecret"
        assert "external_apple_enabled" not in payload

    @pytest.mark.asyncio
    async def test_apple_only_sends_correct_patch(self, provisioner):
        """configure_oauth_providers with Apple credentials PATCHes with external_apple_* fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        patched_payloads: list[dict] = []

        async def capture_patch(url, **kwargs):
            patched_payloads.append(kwargs.get("json", {}))
            return mock_response

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.patch = AsyncMock(side_effect=capture_patch)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            await provisioner.configure_oauth_providers(
                ref="proj123",
                google_client_id=None,
                google_secret=None,
                apple_client_id="aid",
                apple_secret="asecret",
            )

        assert len(patched_payloads) == 1
        payload = patched_payloads[0]
        assert payload.get("external_apple_enabled") is True
        assert payload.get("external_apple_client_id") == "aid"
        assert payload.get("external_apple_secret") == "asecret"
        assert "external_google_enabled" not in payload

    @pytest.mark.asyncio
    async def test_both_providers_in_one_patch(self, provisioner):
        """configure_oauth_providers with both Google and Apple sends all fields in one PATCH."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        patched_payloads: list[dict] = []

        async def capture_patch(url, **kwargs):
            patched_payloads.append(kwargs.get("json", {}))
            return mock_response

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.patch = AsyncMock(side_effect=capture_patch)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            await provisioner.configure_oauth_providers(
                ref="proj123",
                google_client_id="gid",
                google_secret="gsecret",
                apple_client_id="aid",
                apple_secret="asecret",
            )

        # Only one PATCH call with both providers
        assert len(patched_payloads) == 1
        payload = patched_payloads[0]
        assert payload.get("external_google_enabled") is True
        assert payload.get("external_google_client_id") == "gid"
        assert payload.get("external_apple_enabled") is True
        assert payload.get("external_apple_client_id") == "aid"

    @pytest.mark.asyncio
    async def test_no_credentials_skips_api_call(self, provisioner):
        """configure_oauth_providers with all None skips the API call entirely."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.patch = AsyncMock()

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            await provisioner.configure_oauth_providers(
                ref="proj123",
                google_client_id=None,
                google_secret=None,
                apple_client_id=None,
                apple_secret=None,
            )

        mock_client.patch.assert_not_called()

    @pytest.mark.asyncio
    async def test_credential_values_not_logged(self, provisioner, caplog):
        """configure_oauth_providers must never log credential values — only key names."""
        import logging
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.patch = AsyncMock(return_value=mock_response)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            with caplog.at_level(logging.DEBUG, logger="web_app_factory._supabase_provisioner"):
                await provisioner.configure_oauth_providers(
                    ref="proj123",
                    google_client_id="super-secret-gid",
                    google_secret="super-secret-gsecret",
                    apple_client_id="super-secret-aid",
                    apple_secret="super-secret-asecret",
                )

        # Credential values must NOT appear in any log record
        all_log_text = " ".join(r.getMessage() for r in caplog.records)
        assert "super-secret-gid" not in all_log_text
        assert "super-secret-gsecret" not in all_log_text
        assert "super-secret-aid" not in all_log_text
        assert "super-secret-asecret" not in all_log_text

    @pytest.mark.asyncio
    async def test_patch_uses_correct_endpoint(self, provisioner):
        """configure_oauth_providers PATCHes /v1/projects/{ref}/config/auth."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.patch = AsyncMock(return_value=mock_response)

        with patch("web_app_factory._supabase_provisioner.httpx.AsyncClient", return_value=mock_client):
            await provisioner.configure_oauth_providers(
                ref="myref456",
                google_client_id="gid",
                google_secret="gsecret",
                apple_client_id=None,
                apple_secret=None,
            )

        call_url = mock_client.patch.call_args.args[0]
        assert "myref456" in call_url
        assert "config/auth" in call_url
