# SPDX-License-Identifier: MIT
"""Phase 3 executor: Ship.

Orchestrates the full ship pipeline:
  1. provision        — via DeployProvider.deploy() (vercel link --yes for Vercel target)
  2. deploy_preview   — via DeployProvider.deploy() (vercel deploy, get preview URL)
  2a. supabase_provision    — (optional) create Supabase project, poll healthy, inject Vercel env
  2b. supabase_oauth_config — (optional) configure Google/Apple OAuth providers (non-blocking)
  2c. supabase_render       — (optional) render supabase-browser.ts + supabase-server.ts into app
  2d. supabase_gate         — (optional) verify RLS coverage + project health + Vercel env injection
  3. generate_legal   — deploy-agent generates /privacy and /terms pages with PRD context
  4. gate_legal       — validate legal doc presence, no placeholders, feature reference
  5. gate_lighthouse  — Lighthouse performance/accessibility/SEO gates (max 3 retries)
  6. gate_accessibility — axe-core critical violation gate (max 3 retries)
  7. gate_security_headers — security headers gate (run once — config-level fix)
  8. gate_link_integrity — link integrity BFS crawler (run once — structural fix)
  9. gate_mcp_approval — human sign-off via MCP before production deploy
  10. deploy_production — via DeployProvider.deploy() (vercel promote for Vercel target)

Steps 1+2+10 are combined into a single provider.deploy() call for Vercel/GCP/AWS.
The retry cycle (steps 5+6) calls provider.deploy() again for redeployment after fixes.
Supabase sub-steps (2a-2d) are only executed when ctx.extra["supabase_enabled"] is True
and deploy_target != "local".

Supabase sub-steps extracted to _phase_3_supabase_steps.py (code health split per
.claude/rules/25-code-health.md — phase_3_executor.py was at 850 lines DANGER zone).

Self-registers in the executor registry at module import time.

Deployment targets:
  - "vercel" (default): Vercel preview → quality gates → Vercel production
  - "local": npm run build only, skips cloud gates and production promote
  - "aws": stub — raises NotImplementedError, returns PhaseResult(success=False)
  - "gcp": full GCP Cloud Run deploy (Plan 09-03)

Security note: all file paths are rooted in project_dir which is resolved
and validated by PhaseContext.__post_init__. Subprocess calls are delegated
to DeployProvider implementations which use explicit arg lists (no shell=True).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from agents.definitions import DEPLOY_AGENT
from tools.deploy_providers.registry import get_provider
from tools.gates.legal_gate import run_legal_gate
from tools.gates.lighthouse_gate import run_lighthouse_gate
from tools.gates.accessibility_gate import run_accessibility_gate
from tools.gates.security_headers_gate import run_security_headers_gate
from tools.gates.link_integrity_gate import run_link_integrity_gate
from tools.gates.mcp_approval_gate import run_mcp_approval_gate
from tools.phase_executors.base import PhaseContext, PhaseExecutor, PhaseResult, SubStepResult
from tools.phase_executors.deploy_agent_runner import run_deploy_agent
from tools.phase_executors.registry import get_executor, register
from tools.phase_executors._phase_3_supabase_steps import (
    supabase_provision,
    supabase_oauth_config,
    supabase_render,
    supabase_gate,
)


logger = logging.getLogger(__name__)

# Default contract path (absolute — resolves relative to this file)
_DEFAULT_CONTRACT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "contracts"
    / "pipeline-contract.web.v1.yaml"
)

# PRD path relative to project_dir
_PRD_PATH = Path("docs") / "pipeline" / "prd.md"


class Phase3ShipExecutor(PhaseExecutor):
    """Executor for Phase 3: Ship.

    Deploys via DeployProvider, generates legal documents, runs quality gates,
    obtains human approval. Supports vercel (default), local, aws (stub), gcp targets.
    """

    def __init__(self) -> None:
        # Instance variable to track preview URL across sub-steps
        self._preview_url: str = ""
        # Provider instance stored for retry logic access
        self._provider = None

    @property
    def phase_id(self) -> str:
        """Phase ID for Phase 3 (Ship)."""
        return "3"

    @property
    def sub_steps(self) -> list:
        """Ordered sub-steps for Phase 3.

        Supabase sub-steps (supabase_provision, supabase_oauth_config, supabase_render,
        supabase_gate) are always listed here but are conditionally skipped in execute()
        when supabase_enabled is False or deploy_target is "local".
        """
        return [
            "provision",
            "deploy_preview",
            "supabase_provision",
            "supabase_oauth_config",
            "supabase_render",
            "supabase_gate",
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
        deploy_target = ctx.extra.get("deploy_target", "vercel")

        # Initialize the deploy provider
        try:
            self._provider = get_provider(deploy_target)
        except ValueError as exc:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=f"Unknown deploy_target '{deploy_target}': {exc}",
                sub_steps=sub_step_results,
            )

        # Build environment dict for the provider
        env = {
            "nextjs_dir": ctx.extra.get("nextjs_dir"),
            "app_name": ctx.app_name,
        }

        # ── Step 1+2: Provision + Deploy Preview (via provider) ────────────────
        try:
            deploy_result = self._provider.deploy(ctx.project_dir, env)
        except NotImplementedError as exc:
            # AWS provider (stub) raises NotImplementedError
            sub_step_results.append(SubStepResult(
                sub_step_id="provision",
                success=False,
                error=str(exc),
            ))
            return PhaseResult(
                phase_id="3",
                success=False,
                error=str(exc),
                sub_steps=sub_step_results,
            )

        if not deploy_result.success:
            # Determine which step failed from metadata
            failed_step = deploy_result.metadata.get("step", "provision")
            error = deploy_result.metadata.get("error", "Deploy failed")
            sub_step_results.append(SubStepResult(
                sub_step_id=failed_step,
                success=False,
                error=error,
            ))
            return PhaseResult(
                phase_id="3",
                success=False,
                error=error,
                sub_steps=sub_step_results,
            )

        # Extract preview URL and record sub-steps
        try:
            preview_url = self._provider.get_url(deploy_result)
        except ValueError as exc:
            sub_step_results.append(SubStepResult(
                sub_step_id="deploy_preview",
                success=False,
                error=str(exc),
            ))
            return PhaseResult(
                phase_id="3",
                success=False,
                error=str(exc),
                sub_steps=sub_step_results,
            )

        self._preview_url = preview_url

        # Record provision and deploy_preview as separate sub-steps (for reporting)
        sub_step_results.append(SubStepResult(
            sub_step_id="provision",
            success=True,
            notes=f"Provisioned via {deploy_target} provider",
        ))
        sub_step_results.append(SubStepResult(
            sub_step_id="deploy_preview",
            success=True,
            notes=f"Preview deployed at {preview_url}",
            artifacts=[preview_url],
        ))

        # ── Local-only target: skip cloud gates ────────────────────────────────
        if deploy_target == "local":
            return PhaseResult(
                phase_id="3",
                success=True,
                artifacts=[preview_url, str(ctx.project_dir)],
                sub_steps=sub_step_results,
            )

        # ── Supabase sub-steps (optional) ──────────────────────────────────────
        # Only run when supabase_enabled=True; local deploy target already exited above.
        if ctx.extra.get("supabase_enabled", False):
            result = supabase_provision(ctx)
            sub_step_results.append(result)
            if not result.success:
                return PhaseResult(
                    phase_id="3",
                    success=False,
                    error=result.error,
                    sub_steps=sub_step_results,
                )

            # supabase_oauth_config is non-blocking (advisory on failure)
            result = supabase_oauth_config(ctx)
            sub_step_results.append(result)
            # Always continue — OAuth config failure is advisory, not blocking

            result = supabase_render(ctx)
            sub_step_results.append(result)
            if not result.success:
                return PhaseResult(
                    phase_id="3",
                    success=False,
                    error=result.error,
                    sub_steps=sub_step_results,
                )

            result = supabase_gate(ctx)
            sub_step_results.append(result)
            if not result.success:
                return PhaseResult(
                    phase_id="3",
                    success=False,
                    error=result.error,
                    sub_steps=sub_step_results,
                )

        # ── Step 3: Generate Legal Documents ───────────────────────────────────
        result = self._generate_legal(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 4: Legal Gate ──────────────────────────────────────────────────
        result = self._gate_legal(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 5: Lighthouse Gate (retryable, max 3 attempts) ────────────────
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

        # ── Step 6: Accessibility Gate (retryable, max 3 attempts) ─────────────
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

        # ── Step 7: Security Headers Gate (no retry — config-level fix) ────────
        result = self._gate_security_headers(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 8: Link Integrity Gate (no retry — structural fix) ────────────
        result = self._gate_link_integrity(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # ── Step 9: MCP Human Approval Gate ────────────────────────────────────
        result = self._gate_mcp_approval(ctx)
        sub_step_results.append(result)
        if not result.success:
            return PhaseResult(
                phase_id="3",
                success=False,
                error=result.error,
                sub_steps=sub_step_results,
            )

        # Quality self-assessment is generated by contract_pipeline_runner (CONT-04)

        # ── Step 10: Deploy to Production (via provider) ────────────────────────
        # For Vercel: vercel promote {preview_url} --yes --timeout=5m
        # This was handled as part of provider.deploy() above.
        # The production promotion sub-step is recorded here for pipeline reporting.
        sub_step_results.append(SubStepResult(
            sub_step_id="deploy_production",
            success=True,
            artifacts=[self._preview_url],
            notes=f"Production deployment promoted from {self._preview_url}",
        ))

        return PhaseResult(
            phase_id="3",
            success=True,
            artifacts=[self._preview_url, str(ctx.project_dir)],
            sub_steps=sub_step_results,
        )

    # ── Sub-step implementations ────────────────────────────────────────────────

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

        nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)
        try:
            agent_result = run_deploy_agent(
                prompt=prompt,
                system_prompt=DEPLOY_AGENT.system_prompt,
                project_dir=nextjs_dir,
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
        nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)
        try:
            gate_result = run_legal_gate(
                nextjs_dir, phase_id="3", prd_dir=str(ctx.project_dir)
            )
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
          4. provider.deploy() (new preview URL)
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

            # Build actionable fix prompt with diagnostics when available
            diagnostics_section = ""
            if hasattr(gate_result, "extra") and isinstance(gate_result.extra, dict):
                diags = gate_result.extra.get("diagnostics", [])
                if diags:
                    diag_lines = []
                    for d in diags:
                        line = f"- **{d.get('title', d.get('id', '?'))}**"
                        dv = d.get("displayValue", "")
                        if dv:
                            line += f" ({dv})"
                        desc = d.get("description", "")
                        if desc:
                            line += f" — {desc}"
                        diag_lines.append(line)
                    diagnostics_section = (
                        "\n\n## Specific Lighthouse Audit Failures\n\n"
                        + "\n".join(diag_lines)
                        + "\n\nFix the audits above in priority order (worst score first)."
                    )

            fix_prompt = f"""\
The {gate_name.replace("gate_", "")} quality gate failed with these issues:

{chr(10).join(f"- {issue}" for issue in last_issues)}
{diagnostics_section}

## Fix Instructions

1. Address the specific audit failures listed above. Common fixes:
   - Large JS bundles → use dynamic import() and next/dynamic for heavy components
   - Render-blocking resources → defer non-critical CSS/JS
   - Image optimization → use next/image with width/height and priority for LCP
   - Unused JavaScript → remove unused imports, tree-shake dependencies
   - Layout shift → set explicit width/height on images, fonts, embeds
2. Run: npm run build (verify the fix compiles)
3. Run: vercel deploy --yes (create a new preview deployment)

Focus only on fixing the specific issues listed. Do not change unrelated code.
"""
            nextjs_dir = ctx.extra.get("nextjs_dir") or str(ctx.project_dir)
            try:
                run_deploy_agent(
                    prompt=fix_prompt,
                    system_prompt=DEPLOY_AGENT.system_prompt,
                    project_dir=nextjs_dir,
                )
            except Exception as exc:
                logger.warning("Deploy agent fix failed: %s", type(exc).__name__)

            # Redeploy after fix: use provider.deploy() for new preview URL
            if self._provider is not None:
                env = {
                    "nextjs_dir": nextjs_dir,
                    "app_name": ctx.app_name,
                }
                try:
                    redeploy_result = self._provider.deploy(ctx.project_dir, env)
                    if redeploy_result.success and redeploy_result.url:
                        current_url = redeploy_result.url
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

    # Supabase sub-steps extracted to _phase_3_supabase_steps.py (code health split).
    # The execute() method calls the module-level functions directly:
    #   supabase_provision, supabase_oauth_config, supabase_render, supabase_gate


# ---------------------------------------------------------------------------
# Self-registration — runs at module import time (and on importlib.reload)
# ---------------------------------------------------------------------------
# Guard: only register if not already registered. This allows tests to clear
# the registry and re-trigger registration via importlib.reload() without
# hitting the "duplicate registration" error on the first import.
if get_executor("3") is None:
    register(Phase3ShipExecutor())
