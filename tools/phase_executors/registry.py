# SPDX-License-Identifier: MIT
"""Phase Executor Registry — maps phase IDs to their executor instances.

The registry is the single lookup point used by the pipeline runner
to find the executor for a given phase.  Unregistered phases return None,
which signals the runner to skip execution (verify-only mode).

Security notes:
- Registry is populated at module load time with known executors only.
- No dynamic imports or user-supplied executor paths.
- Phase IDs are validated by PhaseContext before reaching executors.
"""

from __future__ import annotations

import os

from tools.phase_executors.base import PhaseExecutor

# ---------------------------------------------------------------------------
# Internal registry: phase_id -> executor instance
# Populated by register() at module level; no dynamic imports.
# ---------------------------------------------------------------------------
_REGISTRY: dict = {}

# ---------------------------------------------------------------------------
# Override registry: phase_id -> (env_var_name, executor)
# Allows env-var-activated executor swaps for gradual rollout.
# ---------------------------------------------------------------------------
_OVERRIDES: dict = {}


def register(executor: PhaseExecutor) -> PhaseExecutor:
    """Register a phase executor instance.

    Args:
        executor: A concrete PhaseExecutor whose phase_id is used as key.

    Returns:
        The same executor (allows use as a decorator-style call).

    Raises:
        ValueError: If an executor for the same phase_id is already registered.
        TypeError: If executor is not a PhaseExecutor instance.
    """
    if not isinstance(executor, PhaseExecutor):
        raise TypeError(
            f"Expected PhaseExecutor instance, got {type(executor).__name__}"
        )
    pid = executor.phase_id
    if pid in _REGISTRY:
        raise ValueError(
            f"Duplicate executor registration for phase '{pid}'"
        )
    _REGISTRY[pid] = executor
    return executor


def register_override(
    executor: PhaseExecutor, *, env_var: str
) -> PhaseExecutor:
    """Register an override executor activated by an environment variable.

    When get_executor() is called for the phase_id and the env var is "1",
    the override executor is returned instead of the default.

    Args:
        executor: A concrete PhaseExecutor to use as override.
        env_var: Environment variable name that activates this override.

    Returns:
        The same executor.

    Raises:
        TypeError: If executor is not a PhaseExecutor instance.
    """
    if not isinstance(executor, PhaseExecutor):
        raise TypeError(
            f"Expected PhaseExecutor instance, got {type(executor).__name__}"
        )
    _OVERRIDES[executor.phase_id] = (env_var, executor)
    return executor


def get_executor(phase_id: str) -> PhaseExecutor | None:
    """Look up the executor for a given phase ID.

    Checks override registry first: if an override is registered for the
    phase_id and its activation env var is "1", returns the override.
    Otherwise, falls through to the default registry.

    Args:
        phase_id: Pipeline phase identifier (e.g., '2a', '1b').

    Returns:
        The registered PhaseExecutor, or None if no executor is registered
        for the given phase.  None signals the runner to use verify-only mode.
    """
    # Check for env-var-activated override
    override = _OVERRIDES.get(phase_id)
    if override is not None:
        env_var, executor = override
        if os.environ.get(env_var) == "1":
            return executor

    return _REGISTRY.get(phase_id)


def registered_phase_ids() -> list:
    """Return a sorted list of all registered phase IDs.

    Useful for diagnostics and test assertions.
    """
    return sorted(_REGISTRY.keys())


def _clear_registry() -> None:
    """Clear all registrations. FOR TESTING ONLY.

    This function should never be called in production code.
    """
    _REGISTRY.clear()
    _OVERRIDES.clear()


# ---------------------------------------------------------------------------
# Auto-registration of built-in executors
# ---------------------------------------------------------------------------
# Web phase executors will be registered here as they are implemented in
# Phase 2+. The registry starts empty and fills as executors are added.
# ---------------------------------------------------------------------------
