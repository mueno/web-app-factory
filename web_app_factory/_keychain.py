"""
OS keychain credential module with graceful env-var fallback.

Security contract (from .claude/rules/10-security-core.md):
- Credential VALUES are never logged, printed, or included in any output.
- Only key names and operation status are logged.
- All keyring failures are caught and logged using type(exc).__name__ only.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional keyring import — module must not crash when keyring is unavailable
# (headless Linux / CI environments have no keyring backend).
# ---------------------------------------------------------------------------
try:
    import keyring  # noqa: F401

    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False
    logger.debug("keyring package not installed; credential store disabled, env-var fallback active")

# Service name used for all credentials stored via this module.
_SERVICE_NAME = "web-app-factory"

# Mapping from internal credential key names to environment variable names.
# Used as fallback when keyring is unavailable or returns None.
_ENV_FALLBACKS: dict[str, str] = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "vercel_token": "VERCEL_TOKEN",
    "vercel_org_id": "VERCEL_ORG_ID",
    "vercel_project_id": "VERCEL_PROJECT_ID",
}


def store_credential(key: str, value: str) -> bool:
    """Store *value* in the OS keychain under *key*.

    Returns True on success, False if keyring is unavailable or the operation
    fails for any reason.  The credential value is never logged.

    Args:
        key: Logical credential name (e.g. "anthropic_api_key").
        value: The secret value to store. NEVER logged.

    Returns:
        True if the credential was stored successfully, False otherwise.
    """
    if not _KEYRING_AVAILABLE:
        logger.warning("keyring unavailable — cannot store credential for key=%r", key)
        return False

    try:
        import keyring as _keyring

        _keyring.set_password(_SERVICE_NAME, key, value)
        logger.debug("Stored credential key=%r in keychain service=%r", key, _SERVICE_NAME)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to store credential key=%r: %s",
            key,
            type(exc).__name__,
        )
        return False


def get_credential(key: str) -> Optional[str]:
    """Retrieve the credential for *key*.

    Lookup order:
    1. OS keychain (via keyring) — if available and the key exists.
    2. Environment variable — looked up via ``_ENV_FALLBACKS[key]`` if present.
    3. Returns None if neither source has the credential.

    The credential value is never logged.

    Args:
        key: Logical credential name (e.g. "anthropic_api_key").

    Returns:
        The credential value string, or None if not found.
    """
    if _KEYRING_AVAILABLE:
        try:
            import keyring as _keyring

            value = _keyring.get_password(_SERVICE_NAME, key)
            if value is not None:
                logger.debug("Retrieved credential key=%r from keychain", key)
                return value
            logger.debug("Credential key=%r not found in keychain; trying env-var fallback", key)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Keychain lookup failed for key=%r (%s); trying env-var fallback",
                key,
                type(exc).__name__,
            )
    else:
        logger.debug("keyring unavailable; using env-var fallback for key=%r", key)

    # Env-var fallback
    env_var = _ENV_FALLBACKS.get(key)
    if env_var is not None:
        value = os.environ.get(env_var)
        if value is not None:
            logger.debug("Retrieved credential key=%r from env var %r", key, env_var)
            return value
        logger.debug("Env var %r not set for credential key=%r", env_var, key)

    logger.debug("Credential key=%r not found in keychain or env vars", key)
    return None


def delete_credential(key: str) -> bool:
    """Delete the credential for *key* from the OS keychain.

    Returns True on success, False if keyring is unavailable or the deletion
    fails for any reason.

    Args:
        key: Logical credential name to remove.

    Returns:
        True if the credential was deleted successfully, False otherwise.
    """
    if not _KEYRING_AVAILABLE:
        logger.warning("keyring unavailable — cannot delete credential for key=%r", key)
        return False

    try:
        import keyring as _keyring

        _keyring.delete_password(_SERVICE_NAME, key)
        logger.debug("Deleted credential key=%r from keychain service=%r", key, _SERVICE_NAME)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to delete credential key=%r: %s",
            key,
            type(exc).__name__,
        )
        return False
