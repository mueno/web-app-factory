# SPDX-License-Identifier: MIT
"""Stub phase executors for all 5 web pipeline phases.

These stubs satisfy the PhaseExecutor interface so the pipeline runner
can load all phases without crashing. Each returns a not-yet-implemented
PhaseResult, signaling that Phase 2+ will replace them with real executors.

Registration is NOT done at module load here (registry starts empty in Phase 1).
Call register_all_stubs() explicitly if you need stubs in the registry.
"""

from __future__ import annotations

from tools.phase_executors.base import PhaseContext, PhaseExecutor, PhaseResult


class Phase1aStubExecutor(PhaseExecutor):
    """Stub for Phase 1a: Idea Validation."""

    @property
    def phase_id(self) -> str:
        return "1a"

    @property
    def sub_steps(self) -> list:
        return []

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        return PhaseResult(
            phase_id=self.phase_id,
            success=False,
            error="Phase 1a executor not yet implemented",
        )


class Phase1bStubExecutor(PhaseExecutor):
    """Stub for Phase 1b: Spec and Design."""

    @property
    def phase_id(self) -> str:
        return "1b"

    @property
    def sub_steps(self) -> list:
        return []

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        return PhaseResult(
            phase_id=self.phase_id,
            success=False,
            error="Phase 1b executor not yet implemented",
        )


class Phase2aStubExecutor(PhaseExecutor):
    """Stub for Phase 2a: Scaffold."""

    @property
    def phase_id(self) -> str:
        return "2a"

    @property
    def sub_steps(self) -> list:
        return []

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        return PhaseResult(
            phase_id=self.phase_id,
            success=False,
            error="Phase 2a executor not yet implemented",
        )


class Phase2bStubExecutor(PhaseExecutor):
    """Stub for Phase 2b: Build."""

    @property
    def phase_id(self) -> str:
        return "2b"

    @property
    def sub_steps(self) -> list:
        return []

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        return PhaseResult(
            phase_id=self.phase_id,
            success=False,
            error="Phase 2b executor not yet implemented",
        )


class Phase3StubExecutor(PhaseExecutor):
    """Stub for Phase 3: Ship."""

    @property
    def phase_id(self) -> str:
        return "3"

    @property
    def sub_steps(self) -> list:
        return []

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        return PhaseResult(
            phase_id=self.phase_id,
            success=False,
            error="Phase 3 executor not yet implemented",
        )


# ── All stub instances ────────────────────────────────────────

ALL_STUBS: list[PhaseExecutor] = [
    Phase1aStubExecutor(),
    Phase1bStubExecutor(),
    Phase2aStubExecutor(),
    Phase2bStubExecutor(),
    Phase3StubExecutor(),
]


def register_all_stubs() -> None:
    """Register all stub executors into the global registry.

    Call this only when you want the pipeline runner to use stubs
    (e.g., integration tests or early-phase pipeline runs).
    Raises ValueError if a real executor for the same phase is already registered.
    """
    from tools.phase_executors.registry import register

    for stub in ALL_STUBS:
        register(stub)
