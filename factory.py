#!/usr/bin/env python3
"""
Web App Factory — CLI entry point.

Usage:
    # New app (positional idea)
    python factory.py "A recipe sharing app for home cooks"

    # Named flag
    python factory.py --idea "A recipe sharing app" --project-dir ./output/RecipeApp

    # Dry-run: validate contract and preflight without executing phases
    python factory.py --idea "test app" --project-dir ./output/Test --dry-run

    # Resume from a previous run
    python factory.py --idea "test app" --resume 20260321-120000-test

    # Custom deploy target / framework
    python factory.py --idea "portfolio site" --deploy-target vercel --framework nextjs
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    """Convert an idea string to a filesystem-safe slug."""
    # Keep alphanumeric and hyphens, replace everything else with hyphens
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name[:40]).strip("-").lower()
    return slug or "web-app"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. Accepts either argv list or defaults to sys.argv[1:].

    Supports:
        - Positional idea OR --idea flag (both set args.idea)
        - --project-dir   path to output directory
        - --deploy-target vercel | github-pages (default: vercel)
        - --framework     nextjs (default: nextjs)
        - --dry-run       validate contract/preflight without executing
        - --resume        run ID to resume from
        - --unsafe-no-gates  debug: skip gate checks
        - --output-json   path for structured output JSON
    """
    parser = argparse.ArgumentParser(
        prog="factory.py",
        description="Web App Factory — generate and deploy a web application from an idea.",
    )

    # Positional + named idea (one or the other)
    parser.add_argument(
        "idea_positional",
        nargs="?",
        metavar="IDEA",
        default=None,
        help="Brief description of the web app to build (positional)",
    )
    parser.add_argument(
        "--idea",
        dest="idea_flag",
        metavar="IDEA",
        default=None,
        help="Brief description of the web app to build (named flag)",
    )

    parser.add_argument(
        "--project-dir",
        dest="project_dir",
        metavar="DIR",
        default=None,
        help="Output directory for the generated project (default: derived from idea)",
    )
    parser.add_argument(
        "--deploy-target",
        dest="deploy_target",
        choices=["vercel", "github-pages"],
        default="vercel",
        help="Deployment target (default: vercel)",
    )
    parser.add_argument(
        "--framework",
        dest="framework",
        choices=["nextjs"],
        default="nextjs",
        help="Web framework to use (default: nextjs)",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="Validate contract and preflight without executing phases",
    )
    parser.add_argument(
        "--resume",
        dest="resume",
        metavar="RUN_ID",
        default=None,
        help="Run ID to resume from (uses existing state.json)",
    )
    parser.add_argument(
        "--unsafe-no-gates",
        dest="unsafe_no_gates",
        action="store_true",
        default=False,
        help="[DEBUG] Skip gate checks — unsafe, for development only",
    )
    parser.add_argument(
        "--output-json",
        dest="output_json",
        metavar="PATH",
        default=None,
        help="Write structured pipeline result JSON to this path",
    )

    ns = parser.parse_args(argv)

    # Resolve idea: named flag takes precedence over positional
    ns.idea = ns.idea_flag or ns.idea_positional

    return ns


def resolve_project_dir(args: argparse.Namespace) -> str:
    """Return the project directory: explicit --project-dir or derived from idea."""
    if args.project_dir:
        return args.project_dir
    idea = args.idea or "web-app"
    slug = _slugify(idea)
    return f"./output/{slug}"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point. Returns exit code (0 = success, 1 = failure)."""
    args = parse_args(argv)

    if args.idea is None and args.resume is None:
        print("error: provide an idea (positional or --idea) or --resume RUN_ID", file=sys.stderr)
        return 1

    project_dir = resolve_project_dir(args)

    # ── Lazy imports (fast --help without importing the full pipeline) ──────
    from pipeline_runtime.startup_preflight import run_startup_preflight
    from tools.contract_pipeline_runner import load_contract, run_pipeline

    # ── Startup preflight ───────────────────────────────────────────────────
    print("[factory] Running startup preflight...", file=sys.stderr)
    preflight_result = run_startup_preflight(project_dir=project_dir)
    if not preflight_result["passed"]:
        print("[factory] Startup preflight FAILED:", file=sys.stderr)
        for issue in preflight_result["issues"]:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    print("[factory] Preflight OK.", file=sys.stderr)

    # ── Load and validate contract ──────────────────────────────────────────
    contract_path = str(
        Path(__file__).resolve().parent
        / "contracts"
        / "pipeline-contract.web.v1.yaml"
    )
    print("[factory] Loading pipeline contract...", file=sys.stderr)
    try:
        contract = load_contract(contract_path)
    except Exception as exc:
        print(f"[factory] Contract load failed: {exc}", file=sys.stderr)
        return 1
    print(f"[factory] Contract loaded ({len(contract.get('phases', []))} phases).", file=sys.stderr)

    # ── Dry-run mode ────────────────────────────────────────────────────────
    if args.dry_run:
        print("[factory] --dry-run: validation complete. Pipeline would execute phases:", file=sys.stderr)
        for phase in contract.get("phases", []):
            print(f"  - {phase.get('id')}: {phase.get('name', '')}", file=sys.stderr)
        result = {
            "status": "dry-run",
            "project_dir": project_dir,
            "phases": [p.get("id") for p in contract.get("phases", [])],
        }
        if args.output_json:
            _write_output_json(result, args.output_json)
        return 0

    # ── Execute pipeline ────────────────────────────────────────────────────
    idea = args.idea or ""
    print(f"[factory] Starting pipeline for: {idea!r}", file=sys.stderr)
    print(f"[factory] Project dir: {project_dir}", file=sys.stderr)

    result = run_pipeline(
        contract=contract,
        project_dir=project_dir,
        idea=idea,
        resume_run_id=args.resume,
        dry_run=False,
        skip_gates=args.unsafe_no_gates,
        contract_path=contract_path,
    )

    if args.output_json:
        _write_output_json(result, args.output_json)

    status = result.get("status", "unknown")
    if status == "completed":
        print(f"[factory] Pipeline complete. Run ID: {result.get('run_id')}", file=sys.stderr)
        return 0
    elif status == "failed":
        print(f"[factory] Pipeline FAILED: {result.get('error', 'unknown error')}", file=sys.stderr)
        return 1
    else:
        print(f"[factory] Pipeline ended with status: {status}", file=sys.stderr)
        return 0


def _write_output_json(result: dict, output_path: str) -> None:
    """Write pipeline result dict to JSON for cross-process consumption."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    sys.exit(main())
