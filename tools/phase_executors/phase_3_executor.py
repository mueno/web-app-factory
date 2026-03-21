# Copyright 2026 AllNew LLC. All rights reserved.
"""Phase 3 executor: Ship.

Orchestrates the full ship pipeline:
  1. provision     — vercel link --yes (auto-provision Vercel project)
  2. deploy_preview — vercel deploy (get preview URL)
  3. generate_legal — deploy-agent generates /privacy and /terms pages with PRD context
  4. gate_legal    — validate legal doc presence, no placeholders, feature reference
  5. gate_lighthouse — Lighthouse performance/accessibility/SEO gates (max 3 retries)
  6. gate_accessibility — axe-core critical violation gate (max 3 retries)
  7. gate_security_headers — security headers gate (run once — config-level fix)
  8. gate_link_integrity — link integrity BFS crawler (run once — structural fix)
  9. gate_mcp_approval — human sign-off via MCP before production deploy
  10. deploy_production — vercel promote {preview_url} --yes --timeout=5m

Self-registers in the executor registry at module import time.

Retry cycle (for lighthouse and accessibility):
  fix code -> npm run build -> vercel deploy (new preview) -> re-run failing gate

Security note: all file paths are rooted in project_dir which is resolved
and validated by PhaseContext.__post_init__. subprocess calls use explicit
arg lists (no shell=True) and env={**os.environ}.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from agents.definitions import DEPLOY_AGENT
from tools.gates.deployment_gate import run_deployment_gate
from tools.gates.legal_gate import run_legal_gate
from tools.gates.lighthouse_gate import run_lighthouse_gate
from tools.gates.accessibility_gate import run_accessibility_gate
from tools.gates.security_headers_gate import run_security_headers_gate
from tools.gates.link_integrity_gate import run_link_integrity_gate
from tools.gates.mcp_approval_gate import run_mcp_approval_gate
from tools.phase_executors.base import PhaseContext, PhaseExecutor, PhaseResult, SubStepResult
from tools.phase_executors.deploy_agent_runner import run_deploy_agent
from tools.phase_executors.registry import get_executor, register
from tools.quality_self_assessment import generate_quality_self_assessment

logger = logging.getLogger(__name__)

# Default contract path (absolute — resolves relative to this file)
_DEFAULT_CONTRACT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "contracts"
    / "pipeline-contract.web.v1.yaml"
)

# PRD path relative to project_dir
_PRD_PATH = Path("docs") / "pipeline" / "prd.md"

# Deployment JSON output path relative to project_dir
_DEPLOYMENT_JSON_PATH = Path("docs") / "pipeline" / "deployment.json"

# Regex to extract Vercel preview URL from CLI output
_VERCEL_URL_RE = re.compile(r"https://[^\s]+\.vercel\.app")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Phase3ShipExecutor(PhaseExecutor):
    """Executor for Phase 3: Ship.

    Deploys to Vercel preview, generates legal documents, runs quality gates,
    obtains human approval, and promotes to production.
    """

    def __init__(self) -> None:
        # Instance variable to track preview URL across sub-steps
        self._preview_url: str = ""

    @property
    def phase_id(self) -> str:
        """Phase ID for Phase 3 (Ship)."""
        return "3"

    @property
    def sub_steps(self) -> list:
        """Ordered sub-steps for Phase 3."""
        return [
            "provision",
            "deploy_preview",
            "generate_legal",
            "gate_legal",
            "gate_lighthouse",
            "gate_accessibility",
            "gate_security_headers",
            "gate_link_integrity",
            "gate_mcp_approval",
            "deploy_production",
        ]

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        """Execute Phase 3: provision -> deploy -> legal -> gates -> approve -> ship.

        Each sub-step is executed in sequence. Failure in any step stops execution
        (except retryable gates which get max 3 attempts before stopping).

        Args:
            ctx: Phase execution context with project_dir, idea, app_name, extra.

        Returns:
            PhaseResult with success=True and artifacts on success,
            or success=False with error message on any failure.
        """
        sub_step_results: list[SubStepResult] = []
        contract_path = Path(ctx.extra.get("contract_path", str(_DEFAULT_CONTRACT_PATH)))

        # ── Step 1: Provision ──────────────────────────────────────────────
        result = self._provision(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 2: Deploy Preview ─────────────────────────────────────────
        result = self._deploy_preview(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 3: Generate Legal Documents ───────────────────────────────
        result = self._generate_legal(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 4: Legal Gate ─────────────────────────────────────────────
        result = self._gate_legal(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 5: Lighthouse Gate (retryable, max 3 attempts) ────────────
        result = self._run_gate_with_retry(
            gate_fn=lambda url: run_lighthouse_gate(url, phase_id="3"),
            gate_name="gate_lighthouse",
            preview_url=self._preview_url,
            ctx=ctx,
            max_retries=3,
        )
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 6: Accessibility Gate (retryable, max 3 attempts) ─────────
        result = self._run_gate_with_retry(
            gate_fn=lambda url: run_accessibility_gate(url, phase_id="3"),
            gate_name="gate_accessibility",
            preview_url=self._preview_url,
            ctx=ctx,
            max_retries=3,
        )
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 7: Security Headers Gate (no retry — config-level fix) ────
        result = self._gate_security_headers(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 8: Link Integrity Gate (no retry — structural fix) ────────
        result = self._gate_link_integrity(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 9: MCP Human Approval Gate ───────────────────────────────
        result = self._gate_mcp_approval(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Quality self-assessment before production deploy ───────────────
        try:
            generate_quality_self_assessment(
                phase_id="3",
                project_dir=str(ctx.project_dir),
                contract_path=str(contract_path),
            )
        except Exception as exc:
            logger.warning(
                "Quality self-assessment generation failed: %s", type(exc).__name__
            )

        # ── Step 10: Deploy to Production ─────────────────────────────────
        result = self._deploy_production(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        return PhaseResult(
            phase_id="3",
            success=True,
            artifacts=[self._preview_url, str(ctx.project_dir)],
            sub_steps=sub_step_results,
        )

    # ── Sub-step implementations ────────────────────────────────────────────

    def _provision(self, ctx: PhaseContext) -> SubStepResult:
        """Step 1: vercel link --yes to auto-provision Vercel project."""
        try:
            proc = subprocess.run(
                ["vercel", "link", "--yes"],
                cwd=str(ctx.project_dir),
                timeout=60,
                capture_output=True,
                text=True,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired:
            return SubStepResult(
                sub_step_id="provision",
                success=False,
                error="vercel link timed out after 60 seconds",
            )
        except Exception as exc:
            return SubStepResult(
                sub_step_id="provision",
                success=False,
                error=f"vercel link failed: {type(exc).__name__}",
            )

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            error_msg = stderr or f"vercel link exited with code {proc.returncode}"
            return SubStepResult(
                sub_step_id="provision",
                success=False,
                error=f"Vercel provisioning failed: {error_msg}",
            )

        return SubStepResult(
            sub_step_id="provision",
            success=True,
            notes="Vercel project linked (auto-provisioned if new)",
        )

    def _deploy_preview(self, ctx: PhaseContext) -> SubStepResult:
        """Step 2: vercel --yes, capture preview URL, write deployment.json.

        Parses stdout with regex to extract the Vercel preview URL per
        RESEARCH.md Pitfall 5: use regex, not just stdout.strip().
        """
        try:
            proc = subprocess.run(
                ["vercel", "--yes"],
                cwd=str(ctx.project_dir),
                timeout=300,
                capture_output=True,
                text=True,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired:
            return SubStepResult(
                sub_step_id="deploy_preview",
                success=False,
                error="vercel deploy timed out after 300 seconds",
            )
        except Exception as exc:
            return SubStepResult(
                sub_step_id="deploy_preview",
                success=False,
                error=f"vercel deploy failed: {type(exc).__name__}",
            )

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            error_msg = stderr or f"vercel exited with code {proc.returncode}"
            return SubStepResult(
                sub_step_id="deploy_preview",
                success=False,
                error=f"Vercel preview deploy failed: {error_msg}",
            )

        # Extract preview URL from stdout using regex
        stdout = proc.stdout or ""
        match = _VERCEL_URL_RE.search(stdout)
        if not match:
            return SubStepResult(
                sub_step_id="deploy_preview",
                success=False,
                error=(
                    "Could not capture Vercel preview URL from CLI output. "
                    f"stdout was: {stdout[:200]!r}"
                ),
            )

        preview_url = match.group(0)
        self._preview_url = preview_url

        # Write deployment.json for downstream gates
        deployment_data = {
            "preview_url": preview_url,
            "deployed_at": _now_iso(),
            "platform": "vercel",
        }
        deployment_json_path = ctx.project_dir / _DEPLOYMENT_JSON_PATH
        deployment_json_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            deployment_json_path.write_text(
                json.dumps(deployment_data, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning(
                "Failed to write deployment.json: %s", type(exc).__name__
            )

        return SubStepResult(
            sub_step_id="deploy_preview",
            success=True,
            artifacts=[preview_url, str(deployment_json_path)],
            notes=f"Preview deployed at {preview_url}",
        )

    def _generate_legal(self, ctx: PhaseContext) -> SubStepResult:
        """Step 3: Generate Privacy Policy and Terms of Service via deploy-agent.

        Loads PRD content and injects it with company info into the agent prompt.
        The agent creates src/app/privacy/page.tsx and src/app/terms/page.tsx.
        """
        # Load PRD for feature context
        prd_path = ctx.project_dir / _PRD_PATH
        prd_content = ""
        if prd_path.exists():
            try:
                prd_content = prd_path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Could not read PRD for legal generation: %s", type(exc).__name__)

        company_name = ctx.extra.get("company_name") or "[Company Name — update before launch]"
        contact_email = ctx.extra.get("contact_email") or "[contact@example.com — update before launch]"

        prompt = f"""\
You are executing Phase 3 legal document generation.

App name: {ctx.app_name}
App idea: {ctx.idea}
Company: {company_name}
Contact email: {contact_email}
Preview URL: {self._preview_url}

## PRD Context

{prd_content if prd_content else "(PRD not available — use general app description above)"}

## Legal Document Requirements

Create two legally compliant documents for this web application:

1. **`src/app/privacy/page.tsx`** — Privacy Policy page
   - Primary jurisdiction: Japanese law (Personal Information Protection Act / APPI)
   - Include GDPR/CCPA mentions for international coverage
   - Reference actual app features from the PRD above (data types collected, functionality)
   - Include: data collected, purpose, third-party sharing, user rights, contact info
   - Company name: {company_name}
   - Contact: {contact_email}
   - NEVER use placeholder strings like YOUR_APP_NAME, [Company], [DATE], etc.

2. **`src/app/terms/page.tsx`** — Terms of Service page
   - Reference actual app functionality from the PRD above
   - Cover: service description, user obligations, prohibited uses, disclaimers, governing law (Japan)
   - Company name: {company_name}
   - Contact: {contact_email}
   - NEVER use placeholder strings like YOUR_APP_NAME, [Company], [DATE], etc.

3. **Footer links** — Add `/privacy` and `/terms` links to `src/app/layout.tsx` footer

Both pages must be React Server Components (no "use client") with TypeScript.
Use the exact company name and email provided above — never use placeholders.
"""

        try:
            agent_result = run_deploy_agent(
                prompt=prompt,
                system_prompt=DEPLOY_AGENT.system_prompt,
                project_dir=str(ctx.project_dir),
            )
        except Exception as exc:
            return SubStepResult(
                sub_step_id="generate_legal",
                success=False,
                error=f"Deploy agent failed during legal generation: {type(exc).__name__}",
            )

        return SubStepResult(
            sub_step_id="generate_legal",
            success=True,
            notes=f"Legal documents generated (agent result length: {len(agent_result)} chars)",
        )

    def _gate_legal(self, ctx: PhaseContext) -> SubStepResult:
        """Step 4: Validate legal documents (no retry — requires regeneration on failure)."""
        try:
            gate_result = run_legal_gate(str(ctx.project_dir), phase_id="3")
        except Exception as exc:
            return SubStepResult(
                sub_step_id="gate_legal",
                success=False,
                error=f"Legal gate raised exception: {type(exc).__name__}",
            )

        if gate_result.passed:
            advisories_note = ""
            if gate_result.advisories:
                advisories_note = f" Advisories: {'; '.join(gate_result.advisories)}"
            return SubStepResult(
                sub_step_id="gate_legal",
                success=True,
                notes=f"Legal gate passed.{advisories_note}",
            )

        return SubStepResult(
            sub_step_id="gate_legal",
            success=False,
            error=f"Legal gate failed: {'; '.join(gate_result.issues)}",
        )

    def _run_gate_with_retry(
        self,
        gate_fn: Callable[[str], object],
        gate_name: str,
        preview_url: str,
        ctx: PhaseContext,
        max_retries: int = 3,
    ) -> SubStepResult:
        """Run a quality gate with auto-fix + retry on failure.

        Retry cycle (per CONTEXT.md):
          1. Run gate against preview_url
          2. If fail: call deploy-agent with fix prompt
          3. npm run build (rebuild project)
          4. vercel deploy (new preview URL)
          5. Re-run gate against new preview URL

        Args:
            gate_fn: Gate function taking url -> GateResult.
            gate_name: Sub-step ID string (e.g., "gate_lighthouse").
            preview_url: Initial preview URL to test.
            ctx: Phase context.
            max_retries: Maximum retry attempts (default 3).

        Returns:
            SubStepResult with success based on final gate outcome.
        """
        current_url = preview_url
        attempt = 0
        last_issues: list[str] = []

        while attempt < max_retries:
            gate_result = gate_fn(current_url)

            if gate_result.passed:  # type: ignore[attr-defined]
                notes = f"Passed on attempt {attempt + 1}"
                if attempt > 0:
                    notes = f"Passed after {attempt} retry(s) on attempt {attempt + 1}"
                return SubStepResult(
                    sub_step_id=gate_name,
                    success=True,
                    notes=notes,
                )

            last_issues = gate_result.issues  # type: ignore[attr-defined]
            attempt += 1

            if attempt >= max_retries:
                break

            # Auto-fix cycle: deploy-agent fix -> rebuild -> redeploy
            logger.info(
                "%s failed (attempt %d/%d): %s — running auto-fix",
                gate_name,
                attempt,
                max_retries,
                "; ".join(last_issues[:3]),
            )

            fix_prompt = f"""\
The {gate_name.replace("gate_", "")} quality gate failed with these issues:

{chr(10).join(f"- {issue}" for issue in last_issues)}

Please:
1. Fix the code issues described above in src/
2. Run: npm run build (to verify the fix compiles)
3. Run: vercel deploy --yes (to create a new preview deployment)

Focus only on fixing the specific issues listed. Do not change unrelated code.
"""
            try:
                run_deploy_agent(
                    prompt=fix_prompt,
                    system_prompt=DEPLOY_AGENT.system_prompt,
                    project_dir=str(ctx.project_dir),
                )
            except Exception as exc:
                logger.warning("Deploy agent fix failed: %s", type(exc).__name__)

            # Get new preview URL after redeploy
            try:
                proc = subprocess.run(
                    ["vercel", "--yes"],
                    cwd=str(ctx.project_dir),
                    timeout=300,
                    capture_output=True,
                    text=True,
                    env={**os.environ},
                )
                if proc.returncode == 0:
                    stdout = proc.stdout or ""
                    url_match = _VERCEL_URL_RE.search(stdout)
                    if url_match:
                        current_url = url_match.group(0)
                        self._preview_url = current_url
            except Exception as exc:
                logger.warning("Re-deploy after fix failed: %s", type(exc).__name__)

        return SubStepResult(
            sub_step_id=gate_name,
            success=False,
            error=(
                f"{gate_name} failed after {max_retries} attempt(s). "
                f"Last issues: {'; '.join(last_issues[:3])}"
            ),
            notes=f"Attempted {max_retries} times with auto-fix; all failed",
        )

    def _gate_security_headers(self, ctx: PhaseContext) -> SubStepResult:
        """Step 7: Security headers gate (no retry — config-level fix required)."""
        try:
            gate_result = run_security_headers_gate(self._preview_url, phase_id="3")
        except Exception as exc:
            return SubStepResult(
                sub_step_id="gate_security_headers",
                success=False,
                error=f"Security headers gate raised exception: {type(exc).__name__}",
            )

        if gate_result.passed:
            return SubStepResult(
                sub_step_id="gate_security_headers",
                success=True,
                notes="Security headers gate passed",
            )

        return SubStepResult(
            sub_step_id="gate_security_headers",
            success=False,
            error=f"Security headers gate failed: {'; '.join(gate_result.issues)}",
        )

    def _gate_link_integrity(self, ctx: PhaseContext) -> SubStepResult:
        """Step 8: Link integrity gate (no retry — 404s indicate missing pages)."""
        try:
            gate_result = run_link_integrity_gate(self._preview_url, phase_id="3")
        except Exception as exc:
            return SubStepResult(
                sub_step_id="gate_link_integrity",
                success=False,
                error=f"Link integrity gate raised exception: {type(exc).__name__}",
            )

        if gate_result.passed:
            return SubStepResult(
                sub_step_id="gate_link_integrity",
                success=True,
                notes="Link integrity gate passed",
            )

        return SubStepResult(
            sub_step_id="gate_link_integrity",
            success=False,
            error=f"Link integrity gate failed: {'; '.join(gate_result.issues)}",
        )

    def _gate_mcp_approval(self, ctx: PhaseContext) -> SubStepResult:
        """Step 9: MCP human approval gate — blocks until human approves."""
        try:
            gate_result = run_mcp_approval_gate(
                phase_id="3",
                project_dir=str(ctx.project_dir),
            )
        except Exception as exc:
            return SubStepResult(
                sub_step_id="gate_mcp_approval",
                success=False,
                error=f"MCP approval gate raised exception: {type(exc).__name__}",
            )

        if gate_result.passed:
            return SubStepResult(
                sub_step_id="gate_mcp_approval",
                success=True,
                notes="Human approved production deployment",
            )

        return SubStepResult(
            sub_step_id="gate_mcp_approval",
            success=False,
            error=f"Production deploy not approved: {'; '.join(gate_result.issues)}",
        )

    def _deploy_production(self, ctx: PhaseContext) -> SubStepResult:
        """Step 10: vercel promote {preview_url} --yes --timeout=5m to production."""
        preview_url = self._preview_url

        try:
            proc = subprocess.run(
                ["vercel", "promote", preview_url, "--yes", "--timeout=5m"],
                cwd=str(ctx.project_dir),
                timeout=360,
                capture_output=True,
                text=True,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired:
            return SubStepResult(
                sub_step_id="deploy_production",
                success=False,
                error="vercel promote timed out after 360 seconds",
            )
        except Exception as exc:
            return SubStepResult(
                sub_step_id="deploy_production",
                success=False,
                error=f"vercel promote failed: {type(exc).__name__}",
            )

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            error_msg = stderr or f"vercel promote exited with code {proc.returncode}"
            return SubStepResult(
                sub_step_id="deploy_production",
                success=False,
                error=f"Production promotion failed: {error_msg}",
            )

        # Update deployment.json with production info
        deployment_json_path = ctx.project_dir / _DEPLOYMENT_JSON_PATH
        if deployment_json_path.exists():
            try:
                data = json.loads(deployment_json_path.read_text(encoding="utf-8"))
                data["production_promoted_at"] = _now_iso()
                data["production_url"] = preview_url  # promoted preview becomes production
                deployment_json_path.write_text(
                    json.dumps(data, indent=2), encoding="utf-8"
                )
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(
                    "Failed to update deployment.json with production info: %s",
                    type(exc).__name__,
                )

        return SubStepResult(
            sub_step_id="deploy_production",
            success=True,
            artifacts=[preview_url],
            notes=f"Production deployment promoted from {preview_url}",
        )


# ---------------------------------------------------------------------------
# Self-registration — runs at module import time (and on importlib.reload)
# ---------------------------------------------------------------------------
# Guard: only register if not already registered. This allows tests to clear
# the registry and re-trigger registration via importlib.reload() without
# hitting the "duplicate registration" error on the first import.
if get_executor("3") is None:
    register(Phase3ShipExecutor())
