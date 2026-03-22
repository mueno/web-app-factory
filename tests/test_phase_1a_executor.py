"""Tests for Phase1aSpecExecutor (SPEC-01, SPEC-03).

Tests use mocked claude_agent_sdk.query via the mock_agent_query fixture
from conftest.py, and mock httpx for npm registry validation. All tests
are deterministic and do not require network access or a real Claude API key.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.phase_executors.base import PhaseContext, PhaseResult
from tools.phase_executors.registry import _clear_registry


# ── Helpers ──────────────────────────────────────────────────────────────────

VALID_IDEA_VALIDATION_MD = """\
# Idea Validation Report

## Competitors

1. **CompetitorAlpha** — market leader with basic feature set
2. **CompetitorBeta** — strong UX but no API integration
3. **CompetitorGamma** — enterprise focused, expensive

## Target User

**Persona:** Alex, 28-year-old software developer who wants to automate repetitive tasks.
Pain point: Spending 2+ hours per day on manual data entry.

## Differentiation

Based on competitor gap analysis: none of the existing tools offer real-time collaboration
with AI-assisted field suggestion — a gap identified in CompetitorAlpha and CompetitorBeta.

## Risks

1. **Market saturation risk** — Mitigation: focus on enterprise vertical
2. **Regulatory compliance risk** — Mitigation: GDPR-compliant from day one
3. **Technical complexity risk** — Mitigation: phased rollout starting with MVP

## Market Size

Total addressable market: ~$5B globally (source: industry analyst report, 2025)

## Go/No-Go

go_no_go: Go

Rationale: Strong differentiation identified, sizable market, and technical feasibility confirmed.
"""

VALID_TECH_FEASIBILITY_JSON = {
    "rendering_strategy": {
        "recommendation": "SSR",
        "rationale": "Dynamic user data requires server-side rendering for fresh content",
        "alternatives_considered": ["SSG", "ISR"],
    },
    "packages": [
        {"name": "next", "version": "^14.0.0", "purpose": "Framework"},
        {"name": "react", "version": "^18.0.0", "purpose": "UI library"},
    ],
    "external_apis": [
        {"name": "Stripe", "rate_limit": "100 req/s", "cost": "$0.029 per transaction"},
    ],
    "vercel_constraints": {
        "serverless_timeout": "10s max for API routes",
        "bundle_size": "< 1MB per chunk recommended",
    },
    "browser_apis": [
        {"api": "Clipboard API", "fallback": "execCommand('copy') for older browsers"},
    ],
}

AGENT_OUTPUT_WITH_FILES = (
    "I've completed the analysis. The deliverables have been written to disk.\n"
    "idea-validation.md and tech-feasibility-memo.json are ready in docs/pipeline/."
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_registry_before_after():
    """Clear the executor registry before and after each test to prevent duplicate registration errors."""
    _clear_registry()
    yield
    _clear_registry()


@pytest.fixture
def project_dir_with_deliverables(tmp_project_dir):
    """Create a project dir that already has the expected deliverable files on disk."""
    pipeline_dir = tmp_project_dir / "docs" / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    (pipeline_dir / "idea-validation.md").write_text(
        VALID_IDEA_VALIDATION_MD, encoding="utf-8"
    )
    (pipeline_dir / "tech-feasibility-memo.json").write_text(
        json.dumps(VALID_TECH_FEASIBILITY_JSON, indent=2), encoding="utf-8"
    )
    return tmp_project_dir


@pytest.fixture
def make_ctx(tmp_project_dir, sample_contract_path):
    """Factory for PhaseContext with defaults appropriate for 1a tests."""

    def _make(**overrides):
        defaults = dict(
            run_id="test-run-01",
            phase_id="1a",
            project_dir=tmp_project_dir,
            idea="A web app to help freelancers track invoices and payments",
            app_name="InvoiceTracker",
            extra={"contract_path": str(sample_contract_path)},
        )
        defaults.update(overrides)
        return PhaseContext(**defaults)

    return _make


@pytest.fixture
def mock_npm_ok():
    """Mock httpx.AsyncClient.get to return 200 for all npm registry lookups."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    async def fake_get(url, **kwargs):
        return mock_response

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = fake_get
        mock_client_cls.return_value = mock_instance
        yield mock_client_cls


# ── Import executor (triggers self-registration) ─────────────────────────────


def _import_executor():
    """Import phase_1a_executor and ensure it is registered.

    On the first call, importing the module triggers self-registration.
    On subsequent calls (after clear_registry_before_after clears the registry),
    importlib.reload() re-executes the module-level guard which re-registers
    because get_executor('1a') now returns None.
    """
    import importlib
    import sys
    import tools.phase_executors.phase_1a_executor  # noqa: F401 (ensure in sys.modules)

    mod = sys.modules["tools.phase_executors.phase_1a_executor"]
    importlib.reload(mod)
    return mod


# ── Tests: basic class contract ───────────────────────────────────────────────


def test_phase_id_is_1a():
    """Phase1aSpecExecutor.phase_id returns '1a'."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    assert executor.phase_id == "1a"


def test_sub_steps_returns_expected_list():
    """Phase1aSpecExecutor.sub_steps returns the required ordered list."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    assert executor.sub_steps == [
        "research",
        "analyze",
        "write_validation",
        "write_feasibility",
        "self_assess",
    ]


# ── Tests: executor self-registration ────────────────────────────────────────


def test_executor_self_registers_for_phase_1a():
    """Phase1aSpecExecutor self-registers in the registry after module import."""
    from tools.phase_executors.registry import get_executor

    _import_executor()
    executor = get_executor("1a")
    assert executor is not None
    assert executor.phase_id == "1a"


# ── Tests: successful execute() producing deliverables ───────────────────────


def test_execute_produces_idea_validation_md(
    project_dir_with_deliverables, make_ctx, mock_agent_query, mock_npm_ok, sample_contract_path
):
    """execute() produces idea-validation.md in project_dir/docs/pipeline/."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    result = executor.execute(ctx)

    validation_path = project_dir_with_deliverables / "docs" / "pipeline" / "idea-validation.md"
    assert validation_path.exists(), "idea-validation.md was not found"


def test_execute_produces_tech_feasibility_memo_json(
    project_dir_with_deliverables, make_ctx, mock_agent_query, mock_npm_ok
):
    """execute() produces tech-feasibility-memo.json in project_dir/docs/pipeline/."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    result = executor.execute(ctx)

    feasibility_path = (
        project_dir_with_deliverables / "docs" / "pipeline" / "tech-feasibility-memo.json"
    )
    assert feasibility_path.exists(), "tech-feasibility-memo.json was not found"


def test_idea_validation_md_has_required_sections(
    project_dir_with_deliverables, make_ctx, mock_agent_query, mock_npm_ok
):
    """idea-validation.md contains all required section headers."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    executor.execute(ctx)

    content = (
        project_dir_with_deliverables / "docs" / "pipeline" / "idea-validation.md"
    ).read_text()

    for section in ["## Competitors", "## Target User", "## Differentiation", "## Risks"]:
        assert section in content, f"Missing required section: {section}"


def test_idea_validation_md_has_parseable_go_no_go(
    project_dir_with_deliverables, make_ctx, mock_agent_query, mock_npm_ok
):
    """idea-validation.md contains a machine-parseable go_no_go field."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    executor.execute(ctx)

    content = (
        project_dir_with_deliverables / "docs" / "pipeline" / "idea-validation.md"
    ).read_text()

    match = re.search(r"go_no_go:\s*(Go|No-Go)", content)
    assert match is not None, "go_no_go field not found or not parseable"
    assert match.group(1) in ("Go", "No-Go")


def test_tech_feasibility_memo_is_valid_json_with_rendering_strategy(
    project_dir_with_deliverables, make_ctx, mock_agent_query, mock_npm_ok
):
    """tech-feasibility-memo.json is valid JSON containing 'rendering_strategy' key."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    executor.execute(ctx)

    memo_path = (
        project_dir_with_deliverables / "docs" / "pipeline" / "tech-feasibility-memo.json"
    )
    content = json.loads(memo_path.read_text())
    assert "rendering_strategy" in content, "rendering_strategy key missing from feasibility memo"


def test_tech_feasibility_memo_has_packages_list(
    project_dir_with_deliverables, make_ctx, mock_agent_query, mock_npm_ok
):
    """tech-feasibility-memo.json contains 'packages' key with list entries."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    executor.execute(ctx)

    memo_path = (
        project_dir_with_deliverables / "docs" / "pipeline" / "tech-feasibility-memo.json"
    )
    content = json.loads(memo_path.read_text())
    assert "packages" in content, "packages key missing from feasibility memo"
    assert isinstance(content["packages"], list), "packages must be a list"


def test_execute_returns_success_phase_result(
    project_dir_with_deliverables, make_ctx, mock_agent_query, mock_npm_ok
):
    """execute() returns PhaseResult(success=True) with artifacts list on success."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    result = executor.execute(ctx)

    assert isinstance(result, PhaseResult)
    assert result.success is True
    assert isinstance(result.artifacts, list)
    assert len(result.artifacts) >= 1


def test_execute_returns_artifacts_containing_deliverable_paths(
    project_dir_with_deliverables, make_ctx, mock_agent_query, mock_npm_ok
):
    """execute() artifacts list contains paths to both deliverable files."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    result = executor.execute(ctx)

    artifact_str = " ".join(str(a) for a in result.artifacts)
    assert "idea-validation.md" in artifact_str
    assert "tech-feasibility-memo.json" in artifact_str


# ── Tests: npm package validation ────────────────────────────────────────────


def test_execute_calls_npm_validation_for_packages(
    project_dir_with_deliverables, make_ctx, mock_agent_query, mock_npm_ok
):
    """execute() calls validate_npm_packages for packages listed in feasibility memo."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    with patch.object(mod, "validate_npm_packages", wraps=mod.validate_npm_packages) as mock_validate:
        executor.execute(ctx)
        mock_validate.assert_called_once()


def test_validate_npm_packages_returns_dict(mock_npm_ok):
    """validate_npm_packages returns a dict mapping package names to bool."""
    mod = _import_executor()
    result = mod.validate_npm_packages(["react", "next"])
    assert isinstance(result, dict)
    assert set(result.keys()) == {"react", "next"}


def test_validate_npm_packages_returns_true_for_existing_packages(mock_npm_ok):
    """validate_npm_packages returns True for packages that exist in the registry."""
    mod = _import_executor()
    result = mod.validate_npm_packages(["react"])
    assert result["react"] is True


def test_validate_npm_packages_returns_false_for_missing_packages():
    """validate_npm_packages returns False for packages that return 404."""
    mock_response = MagicMock()
    mock_response.status_code = 404

    async def fake_get(url, **kwargs):
        return mock_response

    mod = _import_executor()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get = fake_get
        mock_client_cls.return_value = mock_instance

        result = mod.validate_npm_packages(["totally-fake-package-xyz-99999"])
        assert result["totally-fake-package-xyz-99999"] is False


# ── Tests: failure handling ───────────────────────────────────────────────────


def test_execute_returns_failure_when_agent_returns_empty(
    tmp_project_dir, make_ctx, sample_contract_path
):
    """execute() returns PhaseResult(success=False) with error when agent returns empty result and files are absent."""
    from claude_agent_sdk.types import ResultMessage

    empty_result = ResultMessage(
        subtype="result",
        duration_ms=100,
        duration_api_ms=100,
        is_error=False,
        num_turns=1,
        session_id="test-empty",
        result="",
    )

    async def fake_empty_query(*args, **kwargs):
        yield empty_result

    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=tmp_project_dir)

    with patch("tools.phase_executors.spec_agent_runner.query", side_effect=fake_empty_query):
        result = executor.execute(ctx)

    assert isinstance(result, PhaseResult)
    assert result.success is False
    assert result.error is not None


def test_execute_returns_failure_when_deliverables_missing_after_agent_run(
    tmp_project_dir, make_ctx
):
    """execute() returns PhaseResult(success=False) when agent runs but files are not produced."""
    from claude_agent_sdk.types import ResultMessage

    nofile_result = ResultMessage(
        subtype="result",
        duration_ms=100,
        duration_api_ms=100,
        is_error=False,
        num_turns=1,
        session_id="test-no-files",
        result="I thought about it but didn't write any files.",
    )

    async def fake_nofile_query(*args, **kwargs):
        yield nofile_result

    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=tmp_project_dir)

    with patch("tools.phase_executors.spec_agent_runner.query", side_effect=fake_nofile_query):
        result = executor.execute(ctx)

    assert isinstance(result, PhaseResult)
    assert result.success is False


# ── Tests: quality self-assessment ────────────────────────────────────────────


def test_quality_self_assessment_generated_after_execute(
    project_dir_with_deliverables, make_ctx, mock_agent_query, mock_npm_ok
):
    """Quality self-assessment JSON is written to docs/pipeline/quality-self-assessment-1a.json."""
    mod = _import_executor()
    executor = mod.Phase1aSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    executor.execute(ctx)

    assessment_path = (
        project_dir_with_deliverables
        / "docs"
        / "pipeline"
        / "quality-self-assessment-1a.json"
    )
    assert assessment_path.exists(), "quality-self-assessment-1a.json was not generated"
    content = json.loads(assessment_path.read_text())
    assert content["phase_id"] == "1a"
