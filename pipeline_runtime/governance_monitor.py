"""Governance Monitor — runtime surveillance for delegated agent tool calls.

Tracks phase_reporter / approve_gate invocations and detects governance
violations (e.g. file writes without prior phase_reporter(start)).

This module is consumed by the live V2 route (`factory.py` / `runner_v2_*`)
and by the codex-backend output parser.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tools.pipeline_state import PHASE_ORDER

logger = logging.getLogger(__name__)

# Tools that produce file-system side effects
_WRITE_TOOLS = frozenset({"Write", "Bash", "Task", "NotebookEdit"})

# Violation kinds that must block pipeline execution (not just log)
_BLOCKING_VIOLATION_KINDS = frozenset({
    "fast_phase_completion",
    "phase_no_writes",
    "write_without_phase_start",
    "no_phase_reporter",
    "excessive_writes_without_phase",
    "canary_without_gate",
    "saas_gate_fail",
    "saas_gate_unreachable",
    "saas_gate_timeout",
    "phase_order_violation",
    "gate_before_phase_violation",
})


class GovernanceViolationError(Exception):
    """Raised when a governance violation requires immediate pipeline halt.

    Previously, violations were only logged but never blocked execution.
    This exception bridges the detection→enforcement gap (A7 measure).
    """

    def __init__(self, kind: str, message: str) -> None:
        self.kind = kind
        super().__init__(message)


@dataclass
class GovernanceMonitor:
    """Monitor delegated agent tool calls for governance compliance.

    Usage::

        monitor = GovernanceMonitor(run_id="abc123", project_dir="/path/to/project")

        # In the SDK stream loop:
        monitor.on_tool_use(tool_name, tool_input)
        violation = monitor.check_violation()
        if violation:
            logger.warning(violation)
    """

    run_id: str
    project_dir: str

    # Counters
    total_tool_calls: int = 0
    phase_reporter_calls: int = 0
    approve_gate_calls: int = 0
    current_phase_reported: bool = False
    write_calls_without_phase: int = 0

    # Phase tracking
    phases_started: list = field(default_factory=list)
    phases_completed: list = field(default_factory=list)
    current_phase: Optional[str] = None
    # Parallel phase support: tracks all concurrently active phases
    # Maps phase_id -> start monotonic time
    _active_phases: dict = field(default_factory=dict)

    # A5: Phase timing — detect suspiciously fast phase completion
    _phase_start_times: dict = field(default_factory=dict)
    _phase_tool_counts: dict = field(default_factory=dict)
    _phase_write_counts: dict = field(default_factory=dict)
    _fast_phase_warnings: list = field(default_factory=list)

    # A5: Live audit log path (set by caller; None = disabled)
    _live_audit_path: Optional[Path] = None

    # Canary tracking — PHASE_COMPLETE_VERIFIED must only appear after gate PASS
    _gate_passed_phases: set = field(default_factory=set)
    _gate_checked_phases: set = field(default_factory=set)
    _canary_verified_phases: set = field(default_factory=set)
    _canary_violations: list = field(default_factory=list)

    # A7: Blocking mode — raise GovernanceViolationError on violations
    # Set to False only for dry-run or testing scenarios
    blocking: bool = True

    # Phase 2: External SaaS gate verification (None = disabled / backward compatible)
    # Set by orchestrator when EG_API_BASE is configured
    evidence_gate_client: object = None  # type: EvidenceGateClient | None
    _saas_evaluations: list = field(default_factory=list)

    # Violation log
    violations: list = field(default_factory=list)
    _start_time: float = field(default_factory=time.monotonic)

    def enable_live_audit(self, output_dir: str) -> None:
        """Enable JSONL live audit log at docs/pipeline/governance-live.jsonl."""
        p = Path(output_dir) / "docs" / "pipeline" / "governance-live.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        self._live_audit_path = p

    def _emit_audit_event(self, event_type: str, **kwargs: object) -> None:
        """Append a single event to the live JSONL audit log."""
        if self._live_audit_path is None:
            return
        entry = {
            "ts": time.time(),
            "event": event_type,
            "phase": self.current_phase,
            "tool_call_num": self.total_tool_calls,
            **kwargs,
        }
        try:
            with open(self._live_audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # non-blocking — audit failure should not halt pipeline

    def on_tool_use(self, tool_name: str, tool_input: dict) -> Optional[str]:
        """Process a tool call and return a violation message if detected."""
        self.total_tool_calls += 1
        self._emit_audit_event("tool_use", tool=tool_name)

        # Track per-phase tool counts for ALL active phases (parallel support)
        for active_phase in self._active_phases:
            self._phase_tool_counts[active_phase] = (
                self._phase_tool_counts.get(active_phase, 0) + 1
            )
            if tool_name in _WRITE_TOOLS:
                self._phase_write_counts[active_phase] = (
                    self._phase_write_counts.get(active_phase, 0) + 1
                )

        if tool_name == "mcp__factory__phase_reporter":
            return self._handle_phase_reporter(tool_input)

        if tool_name == "mcp__factory__approve_gate":
            self.approve_gate_calls += 1
            phase_id = tool_input.get("phase_id", "") or tool_input.get("phase", "")
            if phase_id:
                self.register_gate_pass(phase_id)
            return None

        # B2 support: track check_gates tool calls to validate gate pass
        # Match only tool names ending with "check_gates" (e.g. mcp__poipoi__check_gates)
        # to prevent false positives from unrelated tools containing "check_gates" substring
        if tool_name.endswith("check_gates") or tool_name == "check_gates":
            phase_id = str(tool_input.get("phase_id") or "").strip()
            if phase_id:
                self._gate_checked_phases.add(phase_id)
                self._emit_audit_event("gate_check", gate_phase=phase_id)
            return None

        if tool_name in _WRITE_TOOLS and not self.current_phase_reported:
            self.write_calls_without_phase += 1
            if self.write_calls_without_phase >= 3:
                msg = (
                    f"GOVERNANCE WARNING: {self.write_calls_without_phase} "
                    f"write-class tool calls ({tool_name}) without "
                    f"phase_reporter(start) — file generation before "
                    f"governance registration"
                )
                self._record_violation("write_without_phase_start", msg, tool_name)
                return msg

        return None

    # ── B1: Phase Order Enforcement ──

    def _enforce_phase_order(self, phase_id: str) -> Optional[str]:
        """Validate phase_id respects PHASE_ORDER.

        Rules:
        - phase must be in PHASE_ORDER (or rejection-fix R-phases)
        - all prior phases (in PHASE_ORDER) must be completed
        - Exception: 4a is parallel — only requires 2d completed (not 3)
        - Exception: 4a is not a blocker for phases after it
        """
        if phase_id.startswith("R"):  # rejection-fix phases have own order
            return None
        if phase_id not in PHASE_ORDER:
            msg = f"Unknown phase '{phase_id}' not in PHASE_ORDER"
            self._record_violation("phase_order_violation", msg)
            return msg

        target_idx = PHASE_ORDER.index(phase_id)

        # Check: all prior phases must be completed
        for prior_id in PHASE_ORDER[:target_idx]:
            if prior_id not in self.phases_completed:
                msg = (
                    f"PHASE ORDER VIOLATION: Cannot start '{phase_id}' — "
                    f"prior phase '{prior_id}' not completed"
                )
                self._record_violation("phase_order_violation", msg)
                return msg
        return None

    # ── B2: Gate-Before-Phase Enforcement ──

    def _enforce_gate_before_phase(self, phase_id: str) -> Optional[str]:
        """Verify previous phase's gate passed before allowing next phase start.

        Uses _gate_passed_phases (populated by register_gate_pass()).
        First phase (1a) is exempt. Rejection-fix phases are exempt.
        """
        if phase_id.startswith("R"):
            return None
        if phase_id not in PHASE_ORDER:
            return None

        target_idx = PHASE_ORDER.index(phase_id)
        if target_idx == 0:
            return None  # First phase has no predecessor

        # Find the mandatory predecessor
        for prev_idx in range(target_idx - 1, -1, -1):
            prev_id = PHASE_ORDER[prev_idx]
            if prev_id in self.phases_completed and prev_id not in self._gate_passed_phases:
                msg = (
                    f"GATE VERIFICATION VIOLATION: Cannot start '{phase_id}' — "
                    f"gate for completed phase '{prev_id}' has not passed"
                )
                self._record_violation("gate_before_phase_violation", msg)
                return msg
            break  # Only check immediate predecessor
        return None

    def _handle_phase_reporter(self, tool_input: dict) -> Optional[str]:
        """Track phase_reporter calls with timing and sequence validation."""
        self.phase_reporter_calls += 1
        status = tool_input.get("status", "")
        phase = tool_input.get("phase", "unknown")
        violation_msg = None

        if status == "start":
            # B1: Enforce phase ordering
            order_violation = self._enforce_phase_order(phase)
            if order_violation:
                return order_violation  # GovernanceViolationError raised by _record_violation

            # B2: Enforce gate-before-phase
            gate_violation = self._enforce_gate_before_phase(phase)
            if gate_violation:
                return gate_violation  # GovernanceViolationError raised by _record_violation

            self.current_phase_reported = True
            self._active_phases[phase] = time.monotonic()
            self.current_phase = phase  # backward compat: most recent started
            self.write_calls_without_phase = 0
            self._phase_start_times[phase] = time.monotonic()
            self._phase_tool_counts[phase] = 0
            self._phase_write_counts[phase] = 0
            if phase not in self.phases_started:
                self.phases_started.append(phase)
            self._emit_audit_event("phase_start", status=status)

        elif status == "complete":
            # A5: Check timing and tool count — suspiciously fast completion
            start_t = self._phase_start_times.get(phase)
            tool_count = self._phase_tool_counts.get(phase, 0)
            write_count = self._phase_write_counts.get(phase, 0)
            if start_t is not None:
                elapsed = time.monotonic() - start_t
                if elapsed < 5.0 and tool_count < 2:
                    warning = (
                        f"FAST PHASE WARNING: '{phase}' completed in "
                        f"{elapsed:.1f}s with {tool_count} tool calls — "
                        f"possible fabrication"
                    )
                    self._fast_phase_warnings.append(warning)
                    self._record_violation("fast_phase_completion", warning)
                    violation_msg = warning

            # A5: Sequence validation — complete without any write/bash
            if write_count == 0 and phase not in ("1a",):
                # Phase 1a may not produce files (idea validation only)
                warning = (
                    f"SEQUENCE WARNING: '{phase}' completed without any "
                    f"Write/Bash tool calls — no artifacts were produced"
                )
                self._fast_phase_warnings.append(warning)
                self._record_violation("phase_no_writes", warning)
                if violation_msg is None:
                    violation_msg = warning

            if phase not in self.phases_completed:
                self.phases_completed.append(phase)
            self._emit_audit_event(
                "phase_complete",
                status=status,
                elapsed_s=round(time.monotonic() - start_t, 1) if start_t else None,
                tool_count=tool_count,
                write_count=write_count,
            )
            # Remove only this phase; preserve other active parallel phases
            self._active_phases.pop(phase, None)
            if self._active_phases:
                self.current_phase = max(
                    self._active_phases, key=lambda p: self._active_phases[p]
                )
            else:
                self.current_phase_reported = False
                self.current_phase = None

        elif status == "error":
            self._emit_audit_event("phase_error", status=status)
            self._active_phases.pop(phase, None)
            if self._active_phases:
                self.current_phase = max(
                    self._active_phases, key=lambda p: self._active_phases[p]
                )
            else:
                self.current_phase_reported = False
                self.current_phase = None

        return violation_msg

    def check_violation(self) -> Optional[str]:
        """Periodic check — call after every N tool calls or at end."""
        if self.total_tool_calls > 10 and self.phase_reporter_calls == 0:
            msg = (
                f"GOVERNANCE VIOLATION: {self.total_tool_calls} tool calls "
                f"executed without any phase_reporter call. "
                f"The agent is bypassing governance reporting."
            )
            self._record_violation("no_phase_reporter", msg)
            return msg

        if self.write_calls_without_phase > 5:
            msg = (
                f"GOVERNANCE WARNING: {self.write_calls_without_phase} "
                f"write-class operations without phase_reporter(start). "
                f"Files are being generated outside governance tracking."
            )
            self._record_violation("excessive_writes_without_phase", msg)
            return msg

        return None

    def summary(self) -> dict:
        """Return a summary for postflight reporting."""
        elapsed = time.monotonic() - self._start_time
        saas_advisories = [
            {
                "phase_id": item.get("phase_id", ""),
                "status": item.get("status", ""),
                "confidence": item.get("confidence", 0.0),
                "advisories": item.get("advisories", []),
            }
            for item in self._saas_evaluations
            if item.get("advisories")
        ]
        return {
            "total_tool_calls": self.total_tool_calls,
            "phase_reporter_calls": self.phase_reporter_calls,
            "approve_gate_calls": self.approve_gate_calls,
            "phases_started": list(self.phases_started),
            "phases_completed": list(self.phases_completed),
            "write_calls_without_phase": self.write_calls_without_phase,
            "fast_phase_warnings": list(self._fast_phase_warnings),
            "phase_tool_counts": dict(self._phase_tool_counts),
            "violations": list(self.violations),
            "canary_verified_phases": sorted(self._canary_verified_phases),
            "canary_violations": list(self._canary_violations),
            "saas_enabled": self.evidence_gate_client is not None,
            "saas_evaluations": list(self._saas_evaluations),
            "saas_pending_advisories": saas_advisories,
            "elapsed_seconds": round(elapsed, 1),
            "governance_compliant": len(self.violations) == 0
            and self.phase_reporter_calls > 0
            and len(self._canary_violations) == 0,
        }

    def write_audit_log(self, output_dir: str) -> Optional[Path]:
        """Persist governance audit to disk for postflight inspection."""
        out = Path(output_dir) / "docs" / "pipeline" / "governance-audit.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            out.write_text(
                json.dumps(self.summary(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return out
        except OSError as exc:
            logger.warning("Failed to write governance audit: %s", type(exc).__name__)
            return None

    def register_gate_pass(self, phase_id: str) -> None:
        """Register that a gate has passed for the given phase.

        Called by the orchestrator after check_gates returns PASS,
        or by on_tool_use() when approve_gate is invoked.

        When evidence_gate_client is configured, external SaaS verification
        is performed BEFORE registration. Failure → GovernanceViolationError.
        """
        if self.evidence_gate_client is not None:
            self._verify_gate_externally(phase_id)
        self._gate_passed_phases.add(phase_id)

    def _verify_gate_externally(self, phase_id: str) -> None:
        """Verify gate pass via external Evidence Gate SaaS.

        On success: records evaluation in _saas_evaluations.
        On failure: records violation and raises GovernanceViolationError (blocking).
        """
        from pipeline_runtime.evidence_gate_client import EvidenceGateError

        client = self.evidence_gate_client
        try:
            evidence = client.collect_evidence(self.project_dir, phase_id)
            result = client.evaluate_gate(
                gate_type="governance",
                phase_id=phase_id,
                run_id=self.run_id,
                evidence=evidence,
            )
            self._saas_evaluations.append({
                "phase_id": phase_id,
                "passed": result.passed,
                "evaluation_id": result.evaluation_id,
                "trust_level": result.evidence_trust_level,
                "status": result.status,
                "confidence": result.confidence,
                "advisories": list(result.advisories),
                "timestamp": time.time(),
            })
            self._emit_audit_event(
                "saas_gate_pass",
                saas_phase=phase_id,
                evaluation_id=result.evaluation_id,
                trust_level=result.evidence_trust_level,
                status=result.status,
                confidence=result.confidence,
                advisory_count=len(result.advisories),
            )
        except EvidenceGateError as exc:
            self._saas_evaluations.append({
                "phase_id": phase_id,
                "passed": False,
                "error_kind": exc.kind,
                "error_message": str(exc),
                "timestamp": time.time(),
            })
            self._emit_audit_event(
                "saas_gate_fail",
                saas_phase=phase_id,
                error_kind=exc.kind,
            )
            # Record violation — this will raise GovernanceViolationError
            # if blocking is True and the kind is in _BLOCKING_VIOLATION_KINDS
            self._record_violation(
                exc.kind,
                f"SaaS gate verification failed for '{phase_id}': {exc}",
            )

    def on_text_output(self, text: str) -> None:
        """Process text output for canary detection and gate pass registration.

        Called from both Claude SDK backend (TextBlock) and external backends
        (on_output_line). Does NOT increment total_tool_calls.

        When PHASE_COMPLETE_VERIFIED canary is detected:
        - If check_gates was called for that phase → register gate pass (B2)
        - If check_gates was NOT called → canary violation
        """
        if not text:
            return
        for line in text.splitlines():
            if "PHASE_COMPLETE_VERIFIED:" not in line:
                continue
            parts = line.split("PHASE_COMPLETE_VERIFIED:")
            if len(parts) <= 1:
                continue
            phase_id = parts[1].strip().split()[0] if parts[1].strip() else ""
            if not phase_id:
                continue

            self._canary_verified_phases.add(phase_id)

            if phase_id in self._gate_checked_phases:
                # check_gates was called → register gate pass for B2
                self.register_gate_pass(phase_id)
            elif phase_id not in self._gate_passed_phases:
                msg = (
                    f"CANARY VIOLATION: PHASE_COMPLETE_VERIFIED for "
                    f"'{phase_id}' emitted without gate check"
                )
                self._canary_violations.append(msg)
                self._record_violation("canary_without_gate", msg)
                logger.warning(msg)

    def on_output_line(self, line: str) -> None:
        """Heuristic parsing for codex subprocess text output.

        Detects phase_reporter / approve_gate mentions in unstructured text.
        Less precise than on_tool_use() but provides coverage for non-SDK backends.
        """
        if not line:
            return
        lower = line.lower()

        if "phase_reporter" in lower or "mcp__factory__phase_reporter" in lower:
            self.phase_reporter_calls += 1
            if '"start"' in lower or "status=start" in lower or "'start'" in lower:
                self.current_phase_reported = True
                self.write_calls_without_phase = 0
            elif '"complete"' in lower or "status=complete" in lower:
                self.current_phase_reported = False

        if "approve_gate" in lower or "mcp__factory__approve_gate" in lower:
            self.approve_gate_calls += 1

        # Heuristic: detect check_gates in external backend text output
        if "check_gates" in lower:
            # Try to extract phase_id from text (best-effort)
            for token in line.split():
                cleaned = token.strip("\"',(){}[]")
                if cleaned in PHASE_ORDER:
                    self._gate_checked_phases.add(cleaned)
                    break

        # Delegate canary detection to on_text_output
        self.on_text_output(line)

        self.total_tool_calls += 1

    def _record_violation(
        self, kind: str, message: str, tool_name: str = ""
    ) -> None:
        self.violations.append(
            {
                "kind": kind,
                "message": message,
                "tool_name": tool_name,
                "tool_call_number": self.total_tool_calls,
                "timestamp": time.time(),
            }
        )
        self._emit_audit_event(
            "violation", kind=kind, tool=tool_name, blocking=self.blocking,
        )
        if self.blocking and kind in _BLOCKING_VIOLATION_KINDS:
            logger.error("BLOCKING VIOLATION [%s]: %s", kind, message)
            raise GovernanceViolationError(kind, message)
