"""Tests for Phase1bSpecExecutor (SPEC-02).

Tests use mocked claude_agent_sdk.query via the mock_agent_query fixture
from conftest.py. All tests are deterministic and do not require network
access or a real Claude API key.

Phase 1b produces:
- docs/pipeline/prd.md  (MoSCoW-labeled PRD with component inventory and route structure)
- docs/pipeline/screen-spec.json  (machine-readable screen specification)

The executor cross-validates that every component name in screen-spec.json
appears in prd.md's component inventory section.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import call, patch

import pytest

from tools.phase_executors.base import PhaseContext, PhaseResult
from tools.phase_executors.registry import _clear_registry, get_executor


# ── Test content constants ─────────────────────────────────────────────────────

VALID_PRD_MD = """\
# Product Requirements Document

## Must-Have Requirements

- **Must**: User authentication with email and password
- **Must**: Dashboard showing key metrics
- **Must**: Data export functionality

## Should-Have Requirements

- **Should**: OAuth login via Google
- **Should**: Dark mode toggle

## Could-Have Requirements

- **Could**: Custom report builder

## Won't-Have (This Release)

- **Won't**: Mobile native app

## Component Inventory

The following reusable UI components are required:

### Layout Components
- **AppShell** (root layout container)
  - **Navbar** (top navigation bar)
  - **Sidebar** (collapsible sidebar navigation)
  - **Footer** (site-wide footer)

### Page-Specific Components
- **DashboardWidget** (metric card with trend indicator)
- **DataTable** (sortable/filterable table with pagination)
- **ExportModal** (file format selection dialog)

## Responsive Breakpoint Strategy

| Breakpoint | Width | Layout |
|------------|-------|--------|
| mobile     | < 768px | Single-column, hamburger menu |
| tablet     | 768px – 1023px | Two-column, sidebar collapsed |
| desktop    | >= 1024px | Three-column, sidebar expanded |

## Route Structure

| Route | Page | Description |
|-------|------|-------------|
| /     | Home | Landing page |
| /dashboard | Dashboard | Main metrics view |
| /export | Export | Data export interface |
| /settings | Settings | User preferences |

## Data Flow

User interactions → React state → API calls → Server-side data → DB queries → Response → UI update
"""

VALID_SCREEN_SPEC_JSON = {
    "screens": [
        {
            "route": "/dashboard",
            "layout": "Three-region layout: Navbar top, Sidebar left, main content area",
            "components": ["AppShell", "Navbar", "Sidebar", "DashboardWidget", "DataTable"],
            "states": ["loading", "loaded", "error", "empty"],
            "responsive": {
                "mobile": "Sidebar hidden, hamburger menu in Navbar",
                "tablet": "Sidebar collapsed to icon strip",
                "desktop": "Sidebar fully expanded with labels"
            }
        },
        {
            "route": "/export",
            "layout": "Centered content with modal overlay",
            "components": ["AppShell", "Navbar", "Footer", "ExportModal"],
            "states": ["idle", "selecting", "exporting", "complete", "error"],
            "responsive": {
                "mobile": "Full-screen modal on mobile",
                "tablet": "Standard modal, 80% viewport width",
                "desktop": "Constrained modal, max 600px width"
            }
        }
    ]
}

# Screen spec with a component NOT in the PRD (for mismatch testing)
MISMATCHED_SCREEN_SPEC_JSON = {
    "screens": [
        {
            "route": "/dashboard",
            "layout": "Three-region layout",
            "components": ["AppShell", "Navbar", "UnknownWidgetXYZ"],
            "states": ["loading", "loaded"],
            "responsive": {
                "mobile": "Single column",
                "tablet": "Two column",
                "desktop": "Full layout"
            }
        }
    ]
}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_registry_before_after():
    """Clear registry before and after each test to prevent duplicate registration."""
    _clear_registry()
    yield
    _clear_registry()


@pytest.fixture
def project_dir_with_deliverables(tmp_project_dir):
    """Create a project dir with valid prd.md and screen-spec.json on disk."""
    pipeline_dir = tmp_project_dir / "docs" / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    (pipeline_dir / "prd.md").write_text(VALID_PRD_MD, encoding="utf-8")
    (pipeline_dir / "screen-spec.json").write_text(
        json.dumps(VALID_SCREEN_SPEC_JSON, indent=2), encoding="utf-8"
    )
    return tmp_project_dir


@pytest.fixture
def project_dir_with_phase_1a_context(project_dir_with_deliverables):
    """Extend project_dir_with_deliverables with Phase 1a output files."""
    pipeline_dir = project_dir_with_deliverables / "docs" / "pipeline"

    # idea-validation.md with distinctive content for injection testing
    (pipeline_dir / "idea-validation.md").write_text(
        "# Idea Validation\n\nCompetitorAlpha is the market leader with 40% share.\n"
        "Target user: freelancers aged 25-35.\ngo_no_go: Go\n",
        encoding="utf-8",
    )

    # tech-feasibility-memo.json with rendering_strategy for injection testing
    (pipeline_dir / "tech-feasibility-memo.json").write_text(
        json.dumps({"rendering_strategy": {"recommendation": "ISR"}, "packages": []}),
        encoding="utf-8",
    )

    return project_dir_with_deliverables


@pytest.fixture
def make_ctx(tmp_project_dir, sample_contract_path):
    """Factory for PhaseContext with defaults appropriate for 1b tests."""

    def _make(**overrides):
        defaults = dict(
            run_id="test-run-1b",
            phase_id="1b",
            project_dir=tmp_project_dir,
            idea="A web app to help freelancers track invoices and payments",
            app_name="InvoiceTracker",
            extra={"contract_path": str(sample_contract_path)},
        )
        defaults.update(overrides)
        return PhaseContext(**defaults)

    return _make


# ── Import helper ─────────────────────────────────────────────────────────────


def _import_executor():
    """Import phase_1b_executor and ensure it is registered.

    On the first call, importing the module triggers self-registration.
    On subsequent calls (after clear_registry clears the registry),
    importlib.reload() re-executes the module-level guard which re-registers
    because get_executor('1b') now returns None.
    """
    import tools.phase_executors.phase_1b_executor  # noqa: F401 (ensure in sys.modules)

    mod = sys.modules["tools.phase_executors.phase_1b_executor"]
    importlib.reload(mod)
    return mod


# ── Tests: basic class contract ───────────────────────────────────────────────


def test_phase_id_is_1b():
    """Phase1bSpecExecutor.phase_id returns '1b'."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    assert executor.phase_id == "1b"


def test_sub_steps_returns_expected_list():
    """Phase1bSpecExecutor.sub_steps returns the required ordered list."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    assert executor.sub_steps == [
        "load_context",
        "write_prd",
        "derive_screen_spec",
        "cross_validate",
    ]


# ── Tests: executor self-registration ────────────────────────────────────────


def test_executor_self_registers_for_phase_1b():
    """Phase1bSpecExecutor self-registers in the registry after module import."""
    _import_executor()
    executor = get_executor("1b")
    assert executor is not None
    assert executor.phase_id == "1b"


# ── Tests: successful execute() producing deliverables ───────────────────────


def test_execute_produces_prd_md(
    project_dir_with_deliverables, make_ctx, mock_agent_query, sample_contract_path
):
    """execute() produces prd.md in project_dir/docs/pipeline/."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    result = executor.execute(ctx)

    prd_path = project_dir_with_deliverables / "docs" / "pipeline" / "prd.md"
    assert prd_path.exists(), "prd.md was not found"


def test_execute_produces_screen_spec_json(
    project_dir_with_deliverables, make_ctx, mock_agent_query
):
    """execute() produces screen-spec.json in project_dir/docs/pipeline/."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    result = executor.execute(ctx)

    spec_path = project_dir_with_deliverables / "docs" / "pipeline" / "screen-spec.json"
    assert spec_path.exists(), "screen-spec.json was not found"


def test_prd_md_has_moscow_labels(
    project_dir_with_deliverables, make_ctx, mock_agent_query
):
    """prd.md contains MoSCoW labels: Must, Should, Could, Won't."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    executor.execute(ctx)

    content = (project_dir_with_deliverables / "docs" / "pipeline" / "prd.md").read_text()
    for label in ["Must", "Should", "Could", "Won't"]:
        assert label in content, f"MoSCoW label '{label}' not found in prd.md"


def test_prd_md_has_component_inventory_section(
    project_dir_with_deliverables, make_ctx, mock_agent_query
):
    """prd.md contains '## Component Inventory' section."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    executor.execute(ctx)

    content = (project_dir_with_deliverables / "docs" / "pipeline" / "prd.md").read_text()
    assert "## Component Inventory" in content, "## Component Inventory section missing from prd.md"


def test_prd_md_has_route_structure_section(
    project_dir_with_deliverables, make_ctx, mock_agent_query
):
    """prd.md contains '## Route Structure' section."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    executor.execute(ctx)

    content = (project_dir_with_deliverables / "docs" / "pipeline" / "prd.md").read_text()
    assert "## Route Structure" in content, "## Route Structure section missing from prd.md"


def test_prd_md_has_responsive_breakpoint_info(
    project_dir_with_deliverables, make_ctx, mock_agent_query
):
    """prd.md contains responsive breakpoint keywords: mobile, tablet, desktop."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    executor.execute(ctx)

    content = (project_dir_with_deliverables / "docs" / "pipeline" / "prd.md").read_text()
    for keyword in ["mobile", "tablet", "desktop"]:
        assert keyword in content.lower(), f"Responsive breakpoint keyword '{keyword}' missing"


# ── Tests: screen-spec.json structure ────────────────────────────────────────


def test_screen_spec_is_valid_json_with_screens_list(
    project_dir_with_deliverables, make_ctx, mock_agent_query
):
    """screen-spec.json is valid JSON with a 'screens' key containing a list."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    executor.execute(ctx)

    spec_path = project_dir_with_deliverables / "docs" / "pipeline" / "screen-spec.json"
    content = json.loads(spec_path.read_text())
    assert "screens" in content, "'screens' key missing from screen-spec.json"
    assert isinstance(content["screens"], list), "'screens' must be a list"
    assert len(content["screens"]) >= 1, "'screens' list must not be empty"


def test_each_screen_has_required_keys(
    project_dir_with_deliverables, make_ctx, mock_agent_query
):
    """Each screen in screen-spec.json has route, layout, components, states, responsive keys."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    executor.execute(ctx)

    spec_path = project_dir_with_deliverables / "docs" / "pipeline" / "screen-spec.json"
    content = json.loads(spec_path.read_text())
    required_keys = {"route", "layout", "components", "states", "responsive"}
    for screen in content["screens"]:
        missing = required_keys - set(screen.keys())
        assert not missing, f"Screen missing keys: {missing}"


# ── Tests: component cross-validation ────────────────────────────────────────


def test_component_names_in_screen_spec_present_in_prd(
    project_dir_with_deliverables, make_ctx, mock_agent_query
):
    """Component names in screen-spec.json screens are present in prd.md component inventory."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    result = executor.execute(ctx)

    assert result.success is True, f"execute() failed: {result.error}"


def test_execute_returns_failure_when_component_names_mismatch(
    tmp_project_dir, make_ctx, mock_agent_query
):
    """execute() returns PhaseResult(success=False) when screen-spec.json has components not in prd.md."""
    pipeline_dir = tmp_project_dir / "docs" / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    # Write PRD without UnknownWidgetXYZ in the component inventory
    (pipeline_dir / "prd.md").write_text(VALID_PRD_MD, encoding="utf-8")

    # Write screen-spec.json with a component NOT in the PRD
    (pipeline_dir / "screen-spec.json").write_text(
        json.dumps(MISMATCHED_SCREEN_SPEC_JSON, indent=2), encoding="utf-8"
    )

    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=tmp_project_dir)

    result = executor.execute(ctx)

    assert isinstance(result, PhaseResult)
    assert result.success is False
    assert result.error is not None


# ── Tests: successful return value ────────────────────────────────────────────


def test_execute_returns_success_phase_result(
    project_dir_with_deliverables, make_ctx, mock_agent_query
):
    """execute() returns PhaseResult(success=True) with artifacts list on success."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    result = executor.execute(ctx)

    assert isinstance(result, PhaseResult)
    assert result.success is True
    assert isinstance(result.artifacts, list)
    assert len(result.artifacts) >= 1


def test_execute_returns_artifacts_containing_deliverable_paths(
    project_dir_with_deliverables, make_ctx, mock_agent_query
):
    """execute() artifacts list contains paths to both deliverable files."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_deliverables)

    result = executor.execute(ctx)

    artifact_str = " ".join(str(a) for a in result.artifacts)
    assert "prd.md" in artifact_str
    assert "screen-spec.json" in artifact_str


# ── Tests: failure handling ───────────────────────────────────────────────────


def test_execute_returns_failure_when_agent_returns_empty(
    tmp_project_dir, make_ctx
):
    """execute() returns PhaseResult(success=False) when agent returns empty result and files absent."""
    from claude_agent_sdk.types import ResultMessage

    empty_result = ResultMessage(
        subtype="result",
        duration_ms=100,
        duration_api_ms=100,
        is_error=False,
        num_turns=1,
        session_id="test-empty-1b",
        result="",
    )

    async def fake_empty_query(*args, **kwargs):
        yield empty_result

    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=tmp_project_dir)

    with patch("tools.phase_executors.spec_agent_runner.query", side_effect=fake_empty_query):
        result = executor.execute(ctx)

    assert isinstance(result, PhaseResult)
    assert result.success is False
    assert result.error is not None


# ── Tests: quality self-assessment ────────────────────────────────────────────
# Quality self-assessment is now generated by contract_pipeline_runner (CONT-04),
# not by individual executors. See tests/test_contract_pipeline_runner.py.


# ── Tests: Phase 1a context injection ────────────────────────────────────────


def test_phase_1a_idea_validation_content_injected_into_prompt(
    project_dir_with_phase_1a_context, make_ctx, mock_agent_query, sample_contract_path
):
    """When idea-validation.md exists, its content appears in the run_spec_agent() prompt argument."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_phase_1a_context)

    captured_prompts = []

    original_run = mod.run_spec_agent

    def capture_run_spec_agent(prompt, system_prompt, project_dir, **kwargs):
        captured_prompts.append(prompt)
        return "mocked result"

    with patch.object(mod, "run_spec_agent", side_effect=capture_run_spec_agent):
        executor.execute(ctx)

    assert captured_prompts, "run_spec_agent was not called"
    assert "CompetitorAlpha" in captured_prompts[0], (
        "idea-validation.md content ('CompetitorAlpha') not found in run_spec_agent prompt"
    )


def test_phase_1a_tech_feasibility_rendering_strategy_injected_into_prompt(
    project_dir_with_phase_1a_context, make_ctx, mock_agent_query, sample_contract_path
):
    """When tech-feasibility-memo.json exists, its rendering_strategy value appears in the prompt."""
    mod = _import_executor()
    executor = mod.Phase1bSpecExecutor()
    ctx = make_ctx(project_dir=project_dir_with_phase_1a_context)

    captured_prompts = []

    def capture_run_spec_agent(prompt, system_prompt, project_dir, **kwargs):
        captured_prompts.append(prompt)
        return "mocked result"

    with patch.object(mod, "run_spec_agent", side_effect=capture_run_spec_agent):
        executor.execute(ctx)

    assert captured_prompts, "run_spec_agent was not called"
    assert "ISR" in captured_prompts[0], (
        "tech-feasibility-memo.json rendering_strategy ('ISR') not found in run_spec_agent prompt"
    )
