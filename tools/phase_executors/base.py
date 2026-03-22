# SPDX-License-Identifier: MIT
"""Phase Executor base classes and data types.

Defines the abstract interface that every phase executor must implement,
plus the data classes for passing context and collecting results.

Security design (per 60-security-review.md):
- project_dir is resolved to an absolute real path on construction
- run_id is validated to contain only safe characters
- Error messages never expose raw exception details to callers
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Safe characters for run_id: alphanumeric, hyphen, underscore, dot
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# Phase IDs: 1a, 1b, 2a, 2b, 3 (web phases) — alphanumeric + optional +
_PHASE_ID_PATTERN = re.compile(r"^[0-9][a-z]?\+?$|^[0-9]$")

# Maximum allowed project_dir depth to prevent excessive traversal
_MAX_PROJECT_DIR_DEPTH = 20


def _validate_run_id(run_id: str) -> str:
    """Validate run_id format. Raises ValueError on invalid input."""
    if not isinstance(run_id, str) or not _RUN_ID_PATTERN.match(run_id):
        raise ValueError(
            "run_id must be 1-128 chars of [A-Za-z0-9._-], "
            "starting with alphanumeric"
        )
    return run_id


def _resolve_project_dir(project_dir: Path) -> Path:
    """Resolve and validate project_dir.

    Ensures the path is absolute and canonical (no symlink tricks).
    Raises ValueError if the path is suspicious.
    """
    resolved = Path(os.path.realpath(str(project_dir)))
    if not resolved.is_absolute():
        raise ValueError("project_dir must resolve to an absolute path")
    # Guard against excessively deep paths
    if len(resolved.parts) > _MAX_PROJECT_DIR_DEPTH:
        raise ValueError(
            f"project_dir has {len(resolved.parts)} components, "
            f"exceeding limit of {_MAX_PROJECT_DIR_DEPTH}"
        )
    return resolved


@dataclass(frozen=True)
class PhaseContext:
    """Immutable context passed to a phase executor.

    All fields are validated on construction to enforce security invariants.
    """

    run_id: str
    phase_id: str
    project_dir: Path
    idea: str
    app_name: str
    budget: float = 50.0
    listing_mode: str = "direct"
    backend: str = "contract-runner-v2"
    resume_sub_step: str | None = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Validate run_id format (safe characters only)
        _validate_run_id(self.run_id)
        # Validate phase_id format (defense-in-depth)
        if not isinstance(self.phase_id, str) or not _PHASE_ID_PATTERN.match(
            self.phase_id
        ):
            raise ValueError(
                f"phase_id must match web phase pattern [0-9][a-z]?[+]?, got "
                f"'{self.phase_id}'"
            )
        # Resolve project_dir to canonical absolute path
        resolved = _resolve_project_dir(self.project_dir)
        # frozen=True requires object.__setattr__ for post-init mutation
        object.__setattr__(self, "project_dir", resolved)
        # Validate budget is non-negative
        if self.budget < 0:
            raise ValueError("budget must be non-negative")


@dataclass
class SubStepResult:
    """Result of a single sub-step within a phase."""

    sub_step_id: str
    success: bool
    artifacts: list = field(default_factory=list)
    error: str | None = None
    notes: str = ""

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        result: dict = {
            "sub_step_id": self.sub_step_id,
            "success": self.success,
            "artifacts": list(self.artifacts),
        }
        if self.error is not None:
            result["error"] = self.error
        if self.notes:
            result["notes"] = self.notes
        return result


@dataclass
class PhaseResult:
    """Aggregate result of an entire phase execution."""

    phase_id: str
    success: bool
    artifacts: list = field(default_factory=list)
    sub_steps: list = field(default_factory=list)
    error: str | None = None
    resume_point: str | None = None

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        result: dict = {
            "phase_id": self.phase_id,
            "success": self.success,
            "artifacts": list(self.artifacts),
            "sub_steps": [s.to_dict() for s in self.sub_steps],
        }
        if self.error is not None:
            result["error"] = self.error
        if self.resume_point is not None:
            result["resume_point"] = self.resume_point
        return result


class PhaseExecutor(ABC):
    """Abstract base class for phase executors.

    Each concrete executor implements the logic for one pipeline phase.
    The contract runner v2 calls execute() and uses the result to decide
    whether to proceed to gate checks or mark the phase as failed.
    """

    @property
    @abstractmethod
    def phase_id(self) -> str:
        """The pipeline phase ID this executor handles (e.g., '1a', '2b')."""
        ...

    @property
    @abstractmethod
    def sub_steps(self) -> list:
        """Ordered list of sub-step identifiers within this phase."""
        ...

    @abstractmethod
    def execute(self, ctx: PhaseContext) -> PhaseResult:
        """Execute the phase and return the result.

        Implementations should:
        - Honor ctx.resume_sub_step (dry-run: skip completed; execute: re-validate)
        - Record each sub-step result
        - Return a PhaseResult with resume_point on failure
        - Never raise exceptions for expected failures (return PhaseResult)
        - Raise only for programming errors / invariant violations
        """
        ...

    def can_resume_from(self, sub_step_id: str) -> bool:
        """Check if this executor can resume from the given sub-step."""
        return sub_step_id in self.sub_steps

    def _start_index(self, ctx: PhaseContext) -> int:
        """Determine the starting sub-step index, honoring resume_sub_step."""
        target = ctx.resume_sub_step
        if target is None:
            return 0
        if target not in self.sub_steps:
            return 0
        return self.sub_steps.index(target)
