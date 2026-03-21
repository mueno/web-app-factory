"""GateResult dataclass -- typed return type for all gate functions.

Provides backward-compatible dict access via __getitem__/.get()/__contains__
so that existing callers using result['passed'] or result.get('details')
continue to work unchanged.

Post-normalization mutation uses ``dataclasses.replace()`` to produce a
new GateResult instance (copy-on-write).  Direct attribute assignment is
blocked by ``frozen=True``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class GateResult:
    """Type-safe gate result with backward-compatible dict access.

    Frozen: mutation after construction requires ``dataclasses.replace()``.
    All mutation sites in runner_v2_gates.py and contract_pipeline_runner.py
    have been refactored to use ``replace(result, passed=False, ...)``.
    """

    schema_version: str = "gate-result.v2"
    gate_type: str = ""
    phase_id: str = ""
    passed: bool = False
    skipped: bool = False
    skip_allowed: bool = False
    status: str = "BLOCKED"
    severity: str = "BLOCK"
    confidence: float = 0.0
    checked_at: str = ""
    issues: list = field(default_factory=list)
    advisories: list = field(default_factory=list)
    issue_records: list = field(default_factory=list)
    advisory_records: list = field(default_factory=list)
    independent_verification: dict = field(default_factory=dict)
    containment_policy: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    # -- Dict-like access bridge (read-only) ----------------------------

    def __getitem__(self, key: str) -> Any:
        """Dict-like read access for backward compatibility."""
        if key != "extra" and key in _KNOWN_FIELDS:
            return getattr(self, key)
        if key in self.extra:
            return self.extra[key]
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like .get() for backward compatibility."""
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        """Support ``'key' in result`` checks."""
        if not isinstance(key, str):
            return False
        if key in _KNOWN_FIELDS:
            return True
        return key in self.extra

    def to_dict(self) -> dict:
        """Serialize to flat dict for JSON output and backward compat.

        Flattens ``extra`` into top-level keys so downstream consumers
        see the same dict shape as the pre-migration code.
        """
        d = asdict(self)
        extra = d.pop("extra", {})
        d.update(extra)
        return d

    # -- Hash support (frozen provides __hash__ automatically) ----------
    # frozen=True gives us __hash__ based on all fields, which is fine
    # for our use case (GateResult instances are not typically stored in
    # sets or used as dict keys, but having it doesn't hurt).


# Set of field names that belong to the dataclass itself (not extra).
_KNOWN_FIELDS: frozenset = frozenset(
    {
        "schema_version",
        "gate_type",
        "phase_id",
        "passed",
        "skipped",
        "skip_allowed",
        "status",
        "severity",
        "confidence",
        "checked_at",
        "issues",
        "advisories",
        "issue_records",
        "advisory_records",
        "independent_verification",
        "containment_policy",
        "extra",
    }
)
