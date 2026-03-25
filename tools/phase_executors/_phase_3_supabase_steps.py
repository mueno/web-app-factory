# SPDX-License-Identifier: MIT
"""Supabase sub-step functions extracted from phase_3_executor.py.

Extracted per .claude/rules/25-code-health.md (Pattern A: single-responsibility split).
phase_3_executor.py was at 850 lines (DANGER zone: 801+ lines). These methods
are extracted as standalone functions that accept PhaseContext and return SubStepResult.

All Supabase imports are lazy (inside function bodies) so non-Supabase pipelines
never pay the httpx/banto/provisioner import cost.

ctx.extra inter-step state:
  supabase_project_ref — set by supabase_provision, read by supabase_gate and
                         supabase_oauth_config
  supabase_api_keys    — set by supabase_provision (anon/service_role keys)

Sub-steps exposed:
  supabase_provision     — create Supabase project, poll healthy, inject Vercel env
  supabase_oauth_config  — configure Google/Apple OAuth providers (non-blocking)
  supabase_render        — render Supabase client templates into generated app
  supabase_gate          — verify RLS coverage, project health, Vercel env injection
"""

from __future__ import annotations

import logging

from tools.phase_executors.base import PhaseContext, SubStepResult


logger = logging.getLogger(__name__)


def supabase_provision(ctx: PhaseContext) -> SubStepResult:
    """Supabase provision sub-step: create project, poll healthy, get keys, inject env.

    Uses lazy imports to avoid loading httpx/banto unless Supabase is enabled.
    Runs async provisioner methods via asyncio.run() (sync/async bridge).

    Security: credential values are never logged; only operation names and status codes.
    """
    import asyncio  # noqa: PLC0415

    from web_app_factory._keychain import get_credential  # noqa: PLC0415

    supabase_access_token = get_credential("supabase_access_token")
    supabase_org_id = get_credential("supabase_org_id")

    if not supabase_access_token or not supabase_org_id:
        return SubStepResult(
            sub_step_id="supabase_provision",
            success=False,
            error=(
                "Missing Supabase credentials: supabase_access_token and "
                "supabase_org_id must be available via banto or env vars"
            ),
        )

    from web_app_factory._supabase_provisioner import SupabaseProvisioner  # noqa: PLC0415

    try:
        provisioner = SupabaseProvisioner(
            access_token=supabase_access_token,
            org_id=supabase_org_id,
        )

        async def _run() -> dict:
            project_data = await provisioner.create_project(name=ctx.app_name)
            ref = project_data["ref"]
            await provisioner.poll_until_healthy(ref)
            api_keys = await provisioner.get_api_keys(ref)

            # Inject Vercel env vars if credentials are available
            vercel_token = get_credential("vercel_token")
            vercel_project_id = ctx.extra.get("vercel_project_id") or get_credential(
                "vercel_project_id"
            )
            if vercel_token and vercel_project_id:
                supabase_url = f"https://{ref}.supabase.co"
                await provisioner.inject_vercel_env(
                    vercel_token=vercel_token,
                    vercel_project_id=vercel_project_id,
                    supabase_url=supabase_url,
                    anon_key=api_keys.get("anon", ""),
                    service_role_key=api_keys.get("service_role", ""),
                )
            else:
                logger.warning(
                    "Vercel credentials not available — skipping env injection"
                )

            return {"ref": ref, "api_keys": api_keys}

        result_data = asyncio.run(_run())
        # Store project_ref and api_keys in ctx.extra for downstream steps
        ctx.extra["supabase_project_ref"] = result_data["ref"]
        ctx.extra["supabase_api_keys"] = result_data["api_keys"]

    except Exception as exc:
        return SubStepResult(
            sub_step_id="supabase_provision",
            success=False,
            error=f"Supabase provisioning failed: {type(exc).__name__}",
        )

    return SubStepResult(
        sub_step_id="supabase_provision",
        success=True,
        notes=f"Supabase project provisioned (ref: {ctx.extra['supabase_project_ref']})",
    )


def supabase_oauth_config(ctx: PhaseContext) -> SubStepResult:
    """Configure OAuth providers on the Supabase project if credentials are available.

    Reads Google and Apple OAuth credentials from environment variables.
    Skips gracefully (advisory) when no credentials are present.
    Failure is non-blocking — users can configure OAuth later via Supabase Dashboard.

    Security: credential values are never passed to logger; only type(exc).__name__
    is logged on failure to avoid leaking secrets in logs.
    """
    import asyncio  # noqa: PLC0415
    import os  # noqa: PLC0415

    project_ref = ctx.extra.get("supabase_project_ref")
    if not project_ref:
        return SubStepResult(
            sub_step_id="supabase_oauth_config",
            success=True,
            notes="Skipped — no project_ref (provisioning may have been skipped)",
        )

    google_id = os.environ.get("GOOGLE_CLIENT_ID")
    google_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    apple_id = os.environ.get("APPLE_CLIENT_ID")
    apple_secret = os.environ.get("APPLE_CLIENT_SECRET")

    if not any([google_id, google_secret, apple_id, apple_secret]):
        return SubStepResult(
            sub_step_id="supabase_oauth_config",
            success=True,
            notes="Skipped — no OAuth credentials configured (advisory)",
        )

    try:
        from web_app_factory._keychain import get_credential  # noqa: PLC0415
        from web_app_factory._supabase_provisioner import SupabaseProvisioner  # noqa: PLC0415

        provisioner = SupabaseProvisioner(
            access_token=get_credential("supabase_access_token"),
            org_id=get_credential("supabase_org_id"),
        )
        asyncio.run(
            provisioner.configure_oauth_providers(
                ref=project_ref,
                google_client_id=google_id,
                google_secret=google_secret,
                apple_client_id=apple_id,
                apple_secret=apple_secret,
            )
        )
        return SubStepResult(
            sub_step_id="supabase_oauth_config",
            success=True,
            notes="OAuth providers configured",
        )
    except Exception as exc:
        logger.warning(
            "OAuth provider config failed (non-blocking): %s", type(exc).__name__
        )
        return SubStepResult(
            sub_step_id="supabase_oauth_config",
            success=True,
            notes=f"Advisory: OAuth config failed ({type(exc).__name__})",
        )


def supabase_render(ctx: PhaseContext) -> SubStepResult:
    """Supabase render sub-step: copy .tmpl client files into generated app.

    Renders supabase-browser.ts and supabase-server.ts into the generated
    app's src/lib/supabase/ directory, and adds npm deps to package.json.
    """
    from pathlib import Path  # noqa: PLC0415

    from web_app_factory._supabase_template_renderer import (  # noqa: PLC0415
        add_supabase_deps,
        render_supabase_templates,
    )

    nextjs_dir = Path(ctx.extra.get("nextjs_dir") or str(ctx.project_dir))
    pkg_json_path = nextjs_dir / "package.json"

    try:
        created_files = render_supabase_templates(nextjs_dir)

        if pkg_json_path.exists():
            add_supabase_deps(pkg_json_path)
        else:
            logger.warning(
                "package.json not found at %s — skipping dep injection", pkg_json_path
            )

    except Exception as exc:
        return SubStepResult(
            sub_step_id="supabase_render",
            success=False,
            error=f"Supabase template rendering failed: {type(exc).__name__}",
        )

    return SubStepResult(
        sub_step_id="supabase_render",
        success=True,
        artifacts=created_files,
        notes=f"Rendered {len(created_files)} Supabase client files",
    )


def supabase_gate(ctx: PhaseContext) -> SubStepResult:
    """Supabase gate sub-step: verify RLS coverage, project health, Vercel env.

    Calls run_supabase_gate with project_ref and credentials stored in ctx.extra
    by supabase_provision.
    """
    from tools.gates.supabase_gate import run_supabase_gate  # noqa: PLC0415
    from web_app_factory._keychain import get_credential  # noqa: PLC0415

    project_ref = ctx.extra.get("supabase_project_ref")
    supabase_access_token = get_credential("supabase_access_token")
    vercel_token = get_credential("vercel_token")
    vercel_project_id = ctx.extra.get("vercel_project_id") or get_credential(
        "vercel_project_id"
    )

    try:
        gate_result = run_supabase_gate(
            project_dir=str(ctx.project_dir),
            phase_id="3",
            supabase_access_token=supabase_access_token,
            project_ref=project_ref,
            vercel_token=vercel_token,
            vercel_project_id=vercel_project_id,
        )
    except Exception as exc:
        return SubStepResult(
            sub_step_id="supabase_gate",
            success=False,
            error=f"Supabase gate raised exception: {type(exc).__name__}",
        )

    if gate_result.passed:
        advisories_note = ""
        if gate_result.advisories:
            advisories_note = f" Advisories: {'; '.join(gate_result.advisories)}"
        return SubStepResult(
            sub_step_id="supabase_gate",
            success=True,
            notes=f"Supabase gate passed.{advisories_note}",
        )

    return SubStepResult(
        sub_step_id="supabase_gate",
        success=False,
        error=f"Supabase gate failed: {'; '.join(gate_result.issues)}",
    )
