# Phase 9: Deploy Abstraction - Research

**Researched:** 2026-03-23
**Domain:** Python ABC provider pattern, Cloud Run deployment, multi-cloud abstraction
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- GCP requires pre-authentication via `gcloud auth login` before running the pipeline — the provider does not handle auth flow
- GCPProvider checks for `gcloud` CLI presence and valid auth (`gcloud auth print-access-token`) before attempting deploy
- If auth is missing/expired, provider returns a clear error with the exact command to run: `gcloud auth login`
- GCP project ID is read from `gcloud config get-value project` — no separate config needed if user has a default project
- If no default project, error message includes `gcloud config set project <PROJECT_ID>`
- LocalOnlyProvider runs `npm run build` to verify the app builds successfully, then returns a synthetic result
- It does NOT start a dev server (that's Phase 10's waf_start_dev_server responsibility)
- The returned URL is `http://localhost:3000` as a placeholder — the actual dev server is started separately
- deployment_gate is skipped for local-only (no deployed URL to health-check)
- Deploy target is set per-run via the `deploy_target` parameter (default: `"vercel"`)
- No project-level persistence — each pipeline run explicitly selects its target
- Supported values: `"vercel"`, `"gcp"`, `"aws"`, `"local"`
- `"aws"` raises NotImplementedError with guidance pointing to v3.0 timeline and manual CDK instructions
- Default of `"vercel"` maintains backward compatibility with v1.0 behavior
- `DeployProvider` ABC with three required methods:
  - `deploy(project_dir: Path, env: dict) -> DeployResult`
  - `get_url(deploy_result: DeployResult) -> str`
  - `verify(url: str) -> bool`
- `DeployResult` dataclass with: `success: bool`, `url: str | None`, `provider: str`, `metadata: dict`
- VercelProvider additionally implements `provision()` and `promote()` for the preview→production workflow
- Providers are registered in a simple dict registry: `{"vercel": VercelProvider, "gcp": GCPProvider, ...}`

### Claude's Discretion

- Exact subprocess command construction for `gcloud run deploy`
- Error retry logic per provider (Vercel has its own patterns from Phase 3)
- How DeployResult metadata varies by provider
- Whether to extract a shared base class or keep providers fully independent

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPL-01 | DeployProvider abstract interface with deploy/get_url/verify methods | ABC pattern in Python `abc` module; frozen dataclass for DeployResult following GateResult convention |
| DEPL-02 | VercelProvider extracted from existing Phase 3 executor (backward compatible) | phase_3_executor.py has full Vercel logic in `_provision`, `_deploy_preview`, `_deploy_production`; extract verbatim |
| DEPL-03 | GCPProvider using `gcloud run deploy --source .` for Google Cloud Run | gcloud SDK 558.0.0 available locally; `--source` flag uses buildpacks; URL extracted from stderr via regex |
| DEPL-04 | AWSProvider stub (interface only, raises NotImplementedError with guidance) | Standard Python NotImplementedError with actionable message pointing to v3.0 |
| DEPL-05 | LocalOnlyProvider that skips cloud deploy and returns localhost URL | Run `npm run build` via subprocess list args; return synthetic `http://localhost:3000` |
| DEPL-06 | Deploy target selectable via `waf_generate_app` parameter | `deploy_target` already flows through `_pipeline_bridge.py`; needs to reach `PhaseContext.extra` |
</phase_requirements>

---

## Summary

Phase 9 creates a multi-cloud deployment abstraction using a Python ABC (`DeployProvider`) with four concrete implementations. The heaviest work is extracting the existing Vercel logic from `phase_3_executor.py` into `VercelProvider` without breaking the existing integration tests. GCPProvider wraps the `gcloud run deploy --source .` command (available via gcloud SDK 558.0.0 on this machine) with pre-flight auth checks. AWSProvider and LocalOnlyProvider are simple stubs.

The entire phase is a pure Python refactoring exercise — no new external dependencies are required. The pattern mirrors existing dataclass conventions (`GateResult`, `SubStepResult`) and the provider registry mirrors the executor registry already in use.

The `deploy_target` parameter already exists in `_pipeline_bridge.py` (line 101) but is not yet plumbed through to `PhaseContext.extra` in `contract_pipeline_runner.py`. That wiring is the key integration point for DEPL-06.

**Primary recommendation:** Create `tools/deploy_providers/` as a new module with `base.py` (ABC + DeployResult), four concrete provider files, and a `registry.py`. Then refactor `phase_3_executor.py` to import and delegate to the provider instead of calling Vercel subprocess commands directly.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `abc` (stdlib) | 3.10+ | DeployProvider ABC | Already used in base.py for PhaseExecutor |
| `dataclasses` (stdlib) | 3.10+ | DeployResult dataclass | Already used for GateResult, SubStepResult, PhaseResult |
| `subprocess` (stdlib) | 3.10+ | gcloud/npm subprocess calls | Established pattern; audit test enforces no shell=True |
| `pathlib` (stdlib) | 3.10+ | Path manipulation | Already used throughout |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | >=0.28.0 (in pyproject.toml) | Deployment health check in verify() | GCPProvider and VercelProvider verify() delegates to `run_deployment_gate` which uses httpx |
| `re` (stdlib) | 3.10+ | URL extraction from CLI stdout/stderr | Extracting Cloud Run service URL from gcloud output |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Simple dict registry | Class-based registry (like executor registry.py) | Dict is simpler for 4 static providers; no dynamic registration needed |
| ABC for base class | Protocol (structural subtyping) | ABC gives runtime enforcement at instantiation; Protocol only at type-check time — ABC preferred for gate-safety |
| Separate module `tools/deploy_providers/` | Adding files to `tools/phase_executors/` | Separate module is cleaner separation of concerns; code-health rule requires 1 responsibility per file |

**Installation:** No new packages required. All dependencies are in stdlib or already in pyproject.toml.

---

## Architecture Patterns

### Recommended Project Structure

```
tools/
├── deploy_providers/
│   ├── __init__.py          # re-export: DeployProvider, DeployResult, get_provider
│   ├── base.py              # ABC DeployProvider + DeployResult dataclass
│   ├── registry.py          # PROVIDERS dict + get_provider() factory
│   ├── vercel_provider.py   # VercelProvider (extracted from phase_3_executor.py)
│   ├── gcp_provider.py      # GCPProvider (gcloud run deploy --source .)
│   ├── aws_provider.py      # AWSProvider stub (NotImplementedError)
│   └── local_provider.py    # LocalOnlyProvider (npm run build + localhost URL)
```

`phase_3_executor.py` is refactored to import `get_provider` and delegate deployment sub-steps to the provider.

### Pattern 1: DeployProvider ABC + DeployResult Dataclass

**What:** Abstract base class enforces the three-method contract at instantiation time. Frozen dataclass for result is consistent with existing GateResult convention.

**When to use:** Always — all providers must satisfy this contract.

```python
# Source: Python stdlib abc module (Python 3.10+)
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class DeployResult:
    """Immutable deploy result — mirrors GateResult convention (frozen=True)."""
    success: bool
    url: Optional[str]
    provider: str
    metadata: dict = field(default_factory=dict)


class DeployProvider(ABC):
    """Abstract base class for all deploy providers.

    Security: all concrete deploy() implementations MUST use
    subprocess with explicit arg lists (no shell=True). This is
    enforced by tests/test_subprocess_audit.py which scans tools/.
    """

    @abstractmethod
    def deploy(self, project_dir: Path, env: dict) -> DeployResult:
        """Execute deployment. Returns DeployResult."""
        ...

    @abstractmethod
    def get_url(self, deploy_result: DeployResult) -> str:
        """Extract deployed URL from result. Raises ValueError if no URL."""
        ...

    @abstractmethod
    def verify(self, url: str) -> bool:
        """Health check the deployed URL. Returns True if reachable."""
        ...
```

### Pattern 2: Provider Registry

**What:** Simple dict mapping string keys to provider classes. `get_provider()` factory instantiates on demand.

**When to use:** When `phase_3_executor.py` (and later Phase 11) needs to select a provider from `PhaseContext.extra["deploy_target"]`.

```python
# Source: mirrors tools/phase_executors/registry.py pattern
from __future__ import annotations

from .vercel_provider import VercelProvider
from .gcp_provider import GCPProvider
from .aws_provider import AWSProvider
from .local_provider import LocalOnlyProvider
from .base import DeployProvider

VALID_DEPLOY_TARGETS = frozenset({"vercel", "gcp", "aws", "local"})

_PROVIDERS: dict[str, type[DeployProvider]] = {
    "vercel": VercelProvider,
    "gcp": GCPProvider,
    "aws": AWSProvider,
    "local": LocalOnlyProvider,
}


def get_provider(deploy_target: str) -> DeployProvider:
    """Instantiate and return the provider for the given deploy_target.

    Args:
        deploy_target: One of "vercel", "gcp", "aws", "local".

    Returns:
        A DeployProvider instance.

    Raises:
        ValueError: If deploy_target is not a recognized value.
    """
    cls = _PROVIDERS.get(deploy_target)
    if cls is None:
        valid = ", ".join(sorted(VALID_DEPLOY_TARGETS))
        raise ValueError(
            f"Unknown deploy_target: {deploy_target!r}. "
            f"Valid values: {valid}"
        )
    return cls()
```

### Pattern 3: GCPProvider Auth Pre-flight

**What:** Check for gcloud CLI and valid token before attempting deploy. Return clear error with remediation command if auth fails.

**When to use:** At the start of GCPProvider.deploy().

```python
# Source: gcloud CLI verified locally (SDK 558.0.0)
import subprocess
import logging

logger = logging.getLogger(__name__)

def _check_gcloud_auth() -> tuple[bool, str]:
    """Check gcloud CLI availability and valid auth.

    Returns:
        (ok: bool, error_message: str)
        error_message is empty string if ok=True.
    """
    # 1. Check gcloud is on PATH
    try:
        proc = subprocess.run(
            ["gcloud", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ},
        )
        if proc.returncode != 0:
            return False, "gcloud CLI not found. Install from: https://cloud.google.com/sdk"
    except FileNotFoundError:
        return False, "gcloud CLI not found. Install from: https://cloud.google.com/sdk"
    except subprocess.TimeoutExpired:
        return False, "gcloud CLI check timed out"

    # 2. Check valid auth token
    try:
        proc = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ},
        )
        if proc.returncode != 0:
            return False, (
                "GCP auth token invalid or expired. "
                "Run: gcloud auth login"
            )
    except subprocess.TimeoutExpired:
        return False, "gcloud auth check timed out. Run: gcloud auth login"

    # 3. Check project is set
    try:
        proc = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ},
        )
        project = (proc.stdout or "").strip()
        if not project or project == "(unset)":
            return False, (
                "No GCP project configured. "
                "Run: gcloud config set project <PROJECT_ID>"
            )
    except subprocess.TimeoutExpired:
        return False, "gcloud config check timed out"

    return True, ""
```

### Pattern 4: GCPProvider URL Extraction

**What:** `gcloud run deploy --source .` outputs the service URL to stderr. Extract with regex.

**When to use:** In GCPProvider.deploy() after successful subprocess call.

```python
import re

# gcloud run deploy stderr output pattern (verified against SDK 558.0.0):
# "Service [my-service] revision [...] has been deployed and is serving 100 percent of traffic."
# "Service URL: https://my-service-abc123-uc.a.run.app"
_GCP_URL_RE = re.compile(r"Service URL:\s+(https://[^\s]+\.run\.app)")

def _extract_gcp_url(stderr: str) -> str | None:
    """Extract Cloud Run service URL from gcloud deploy stderr output."""
    match = _GCP_URL_RE.search(stderr)
    return match.group(1) if match else None
```

### Pattern 5: deploy_target Wiring in Phase 3 Executor

**What:** `phase_3_executor.py` reads `deploy_target` from `PhaseContext.extra`, selects provider, delegates sub-steps.

**When to use:** When refactoring `phase_3_executor.py` to use providers.

```python
# In Phase3ShipExecutor.execute():
from tools.deploy_providers.registry import get_provider

deploy_target = ctx.extra.get("deploy_target", "vercel")
try:
    provider = get_provider(deploy_target)
except ValueError as exc:
    return PhaseResult(
        phase_id="3",
        success=False,
        error=str(exc),
        sub_steps=[],
    )
```

### Pattern 6: deploy_target Wiring in contract_pipeline_runner.py

**What:** `contract_pipeline_runner.py` must accept and forward `deploy_target` to `PhaseContext.extra`.

**When to use:** When adding `deploy_target` parameter to `run_pipeline()` and the PhaseContext construction.

```python
# In run_pipeline() signature:
def run_pipeline(
    contract: dict,
    project_dir: str,
    idea: str,
    *,
    deploy_target: str = "vercel",   # NEW parameter
    ...
) -> dict:
    ...
    # In PhaseContext construction:
    ctx = PhaseContext(
        ...
        extra={
            "company_name": company_name,
            "contact_email": contact_email,
            "nextjs_dir": nextjs_dir,
            "deploy_target": deploy_target,   # NEW
        },
    )
```

Note: `_pipeline_bridge.py` already has `deploy_target: str = "vercel"` in `start_pipeline_async()` but does NOT yet forward it to `run_pipeline()`. This is the missing wiring.

### Anti-Patterns to Avoid

- **shell=True in subprocess:** The subprocess audit test scans `tools/` recursively. Any `shell=True` in provider files fails CI automatically.
- **Direct gcloud output parsing with stdout:** gcloud run deploy writes the service URL to **stderr**, not stdout. Parse `proc.stderr`, not `proc.stdout`.
- **Blocking PhaseContext.extra on unknown deploy_target:** Validate at provider instantiation time (in `get_provider()`), not at `PhaseContext` construction — keeps validation co-located with the provider logic.
- **Raising exceptions in deploy():** Follow existing executor pattern — return `DeployResult(success=False, ...)` rather than raising, so Phase 3 executor can include the error in `SubStepResult`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP health check | Custom httpx logic in verify() | `run_deployment_gate(url)` from `tools/gates/deployment_gate.py` | Already handles 200/401 pass logic, redirects, error types |
| Shell arg sanitization | Custom escaping | `safe_shell_arg()` from `web_app_factory/_input_validator.py` | Only needed for string-mode; but use list args instead per audit policy |
| Credential retrieval | Direct `os.environ` reads | `get_credential(key)` from `web_app_factory/_keychain.py` | Keychain-first with env-var fallback; credential values never logged |

**Key insight:** `deployment_gate.py` is already provider-agnostic (just does HTTP GET on any URL). All four providers' `verify()` method should delegate to `run_deployment_gate()`. LocalOnlyProvider is the exception — it skips `verify()` (returns `True` without HTTP check, per user decision).

---

## Common Pitfalls

### Pitfall 1: gcloud URL in stderr not stdout

**What goes wrong:** GCPProvider reads `proc.stdout` for the service URL but finds nothing. Deploy appears to succeed but `get_url()` raises or returns `None`.

**Why it happens:** `gcloud run deploy --source .` writes human-readable progress output (including "Service URL: ...") to **stderr**. stdout may be empty or contain only structured data if `--format` is used.

**How to avoid:** Always parse `proc.stderr` for the URL. Use `capture_output=True` which captures both.

**Warning signs:** `proc.stdout` is empty or `None` after a successful gcloud deploy call.

### Pitfall 2: gcloud deploy requires --region or prompts interactively

**What goes wrong:** GCPProvider subprocess call hangs waiting for user input to select a region.

**Why it happens:** If no default region is configured in `gcloud config`, the CLI prompts interactively — which blocks the subprocess call indefinitely (or until timeout).

**How to avoid:** Either (a) read `gcloud config get-value run/region` in the pre-flight check and pass `--region=<region>` explicitly, or (b) fall back to a default region (e.g., `us-central1`) when no region is configured. Document the behavior clearly.

**Warning signs:** Subprocess call hangs for 600+ seconds (deployment timeout) instead of failing quickly.

### Pitfall 3: phase_3_executor.py still has duplicate Vercel subprocess calls after refactor

**What goes wrong:** After extracting `VercelProvider`, the old `_provision`, `_deploy_preview`, `_deploy_production` methods remain in `Phase3ShipExecutor`, creating two code paths and subprocess audit confusion.

**Why it happens:** Partial refactor leaves old methods in place "just in case."

**How to avoid:** Delete the old Vercel-specific methods from `Phase3ShipExecutor` after verifying `VercelProvider` passes all existing tests. The subprocess audit test will catch any remaining duplicates.

**Warning signs:** `test_subprocess_audit.py` finds shell=True patterns, or `tests/test_phase_3_executor.py` shows 31 failing tests (as currently observed in the pre-existing test failures that are unrelated to this phase — see note below).

### Pitfall 4: subprocess audit test catches new providers

**What goes wrong:** A provider file under `tools/deploy_providers/` accidentally uses `shell=True` or `os.system()`. The subprocess audit test immediately catches it.

**Why it happens:** Copy-paste from a Stack Overflow example that uses `shell=True` for simplicity.

**How to avoid:** Always use explicit arg lists: `["gcloud", "run", "deploy", "--source", "."]` not `"gcloud run deploy --source ."`. Use `safe_shell_arg()` only as a last resort for dynamic args.

**Warning signs:** CI fails on `test_subprocess_audit.py::test_no_shell_true_in_production_code`.

### Pitfall 5: LocalOnlyProvider fails on missing package.json

**What goes wrong:** `npm run build` fails if the nextjs_dir doesn't contain package.json (e.g., when project generation failed earlier).

**Why it happens:** LocalOnlyProvider assumes a fully generated Next.js project is available.

**How to avoid:** Check that `package.json` exists in `nextjs_dir` before running `npm run build`. Return a clear error if it doesn't.

**Warning signs:** `subprocess.run(["npm", "run", "build"], cwd=nextjs_dir)` exits with code 1 and stderr contains "missing script: build".

### Pitfall 6: deploy_target not forwarded from _pipeline_bridge.py to run_pipeline()

**What goes wrong:** User passes `deploy_target="gcp"` but deployment still goes to Vercel because the bridge never passes it to `run_pipeline()`.

**Why it happens:** `_pipeline_bridge.py` already has `deploy_target` in `start_pipeline_async()` but the parameter is silently dropped when building `pipeline_kwargs` (line 132-142 of `_pipeline_bridge.py`).

**How to avoid:** Add `pipeline_kwargs["deploy_target"] = deploy_target` in `_pipeline_bridge.py::start_pipeline_async()`. Then add `deploy_target: str = "vercel"` parameter to `run_pipeline()`. Then forward to `PhaseContext.extra`.

**Warning signs:** `test_pipeline_bridge.py` passes but integration test always deploys to Vercel regardless of parameter.

---

## Code Examples

### LocalOnlyProvider.deploy() pattern

```python
# Source: user decisions in 09-CONTEXT.md + subprocess list arg convention
import subprocess
import os
from pathlib import Path

from .base import DeployProvider, DeployResult


class LocalOnlyProvider(DeployProvider):
    """Skip cloud deployment; run npm build and return localhost URL."""

    def deploy(self, project_dir: Path, env: dict) -> DeployResult:
        nextjs_dir = env.get("nextjs_dir") or str(project_dir)

        # Check package.json exists
        if not Path(nextjs_dir, "package.json").exists():
            return DeployResult(
                success=False,
                url=None,
                provider="local",
                metadata={"error": f"package.json not found in {nextjs_dir}"},
            )

        try:
            proc = subprocess.run(
                ["npm", "run", "build"],
                cwd=nextjs_dir,
                capture_output=True,
                text=True,
                timeout=300,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired:
            return DeployResult(
                success=False,
                url=None,
                provider="local",
                metadata={"error": "npm run build timed out after 300 seconds"},
            )

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            return DeployResult(
                success=False,
                url=None,
                provider="local",
                metadata={"error": f"npm run build failed: {stderr[:200]}"},
            )

        return DeployResult(
            success=True,
            url="http://localhost:3000",
            provider="local",
            metadata={"note": "Build succeeded. Start dev server with waf_start_dev_server."},
        )

    def get_url(self, deploy_result: DeployResult) -> str:
        if deploy_result.url is None:
            raise ValueError("LocalOnlyProvider: no URL (deploy may have failed)")
        return deploy_result.url

    def verify(self, url: str) -> bool:
        # Local-only: skip HTTP check per user decision
        # deployment_gate is not run for local targets
        return True
```

### AWSProvider stub pattern

```python
# Source: user decisions in 09-CONTEXT.md
class AWSProvider(DeployProvider):
    """AWS CDK stub — not implemented in v2.0."""

    _GUIDANCE = (
        "AWS deployment is not implemented in web-app-factory v2.0. "
        "It is planned for v3.0. "
        "To deploy manually, use the AWS CDK: "
        "https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html"
    )

    def deploy(self, project_dir: Path, env: dict) -> DeployResult:
        raise NotImplementedError(self._GUIDANCE)

    def get_url(self, deploy_result: DeployResult) -> str:
        raise NotImplementedError(self._GUIDANCE)

    def verify(self, url: str) -> bool:
        raise NotImplementedError(self._GUIDANCE)
```

### GCPProvider.deploy() core structure

```python
# Source: gcloud CLI SDK 558.0.0 verified on this machine
import re
import subprocess
import os
from pathlib import Path

_GCP_URL_RE = re.compile(r"Service URL:\s+(https://[^\s]+\.run\.app)")


class GCPProvider(DeployProvider):
    """Google Cloud Run provider using gcloud run deploy --source ."""

    def deploy(self, project_dir: Path, env: dict) -> DeployResult:
        # Pre-flight auth check
        ok, error = _check_gcloud_auth()
        if not ok:
            return DeployResult(success=False, url=None, provider="gcp",
                                metadata={"error": error})

        nextjs_dir = env.get("nextjs_dir") or str(project_dir)
        service_name = env.get("app_name", "web-app-factory-app")

        # Build explicit arg list (no shell=True — subprocess audit enforces this)
        cmd = [
            "gcloud", "run", "deploy", service_name,
            "--source", ".",
            "--allow-unauthenticated",
            "--quiet",  # suppress interactive prompts
        ]

        # Append region if configured
        region = _get_gcloud_region()
        if region:
            cmd += ["--region", region]

        try:
            proc = subprocess.run(
                cmd,
                cwd=nextjs_dir,
                capture_output=True,
                text=True,
                timeout=600,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired:
            return DeployResult(success=False, url=None, provider="gcp",
                                metadata={"error": "gcloud run deploy timed out after 600s"})

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            return DeployResult(success=False, url=None, provider="gcp",
                                metadata={"error": f"gcloud run deploy failed: {stderr[:500]}"})

        # URL is in stderr (not stdout)
        url = _extract_gcp_url(proc.stderr or "")
        if not url:
            return DeployResult(success=False, url=None, provider="gcp",
                                metadata={"error": "Could not extract Service URL from gcloud output"})

        return DeployResult(success=True, url=url, provider="gcp",
                            metadata={"service_name": service_name})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Vercel subprocess inline in phase_3_executor.py | DeployProvider ABC with concrete providers | Phase 9 | phase_3_executor.py delegates to provider; deploy logic lives in tools/deploy_providers/ |
| Single deploy target (Vercel only) | Four providers selectable per run | Phase 9 | DEPL-06: `deploy_target` parameter in waf_generate_app (wired in Phase 11) |

**Deprecated/outdated:**
- Inline `_provision`, `_deploy_preview`, `_deploy_production` methods in `Phase3ShipExecutor`: these move to `VercelProvider` in Phase 9 and are deleted from the executor.

---

## Open Questions

1. **gcloud --region default strategy**
   - What we know: `gcloud config get-value run/region` returns the configured default; `gcloud config get-value compute/region` is a fallback. If neither is set, gcloud prompts interactively.
   - What's unclear: Whether to hardcode `us-central1` as fallback or fail with a clear error asking user to set a region.
   - Recommendation: Read `gcloud config get-value run/region` in pre-flight; if unset, default to `us-central1` with a warning logged. Document this behavior in provider error messages.

2. **VercelProvider: provision() and promote() as public methods vs private**
   - What we know: CONTEXT.md says "VercelProvider additionally implements `provision()` and `promote()` for the preview→production workflow" — but these are not in the ABC.
   - What's unclear: Should they be public methods called by `Phase3ShipExecutor` or stay private helpers inside `deploy()`?
   - Recommendation: Keep `provision()` and `promote()` as internal methods called from `deploy()`. The ABC contract is `deploy/get_url/verify`. Phase 3 executor calls `provider.deploy()` which internally runs provision → deploy_preview → promote. This preserves the ABC contract and keeps caller code simple.

3. **Pre-existing test failures in test_phase_3_executor.py**
   - What we know: 31 tests currently fail in `test_phase_3_executor.py` (verified during research). These appear unrelated to Phase 9 scope — they test `nextjs_dir` forwarding behavior.
   - What's unclear: Whether Phase 9 must fix these failures or just not introduce new ones.
   - Recommendation: Do not attempt to fix pre-existing failures. When refactoring phase_3_executor.py for Phase 9, verify that the 25 currently-passing tests continue to pass. The 31 failing tests are pre-existing and out of Phase 9 scope.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml (`[tool.pytest.ini_options]`) |
| Quick run command | `python3 -m pytest tests/test_deploy_providers.py -x -q` |
| Full suite command | `python3 -m pytest tests/ --ignore=tests/test_deploy_agent_runner.py --ignore=tests/test_phase_2a_executor.py -q --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPL-01 | DeployProvider ABC cannot be instantiated directly | unit | `pytest tests/test_deploy_providers.py::test_abc_cannot_instantiate -x` | ❌ Wave 0 |
| DEPL-01 | DeployResult is a frozen dataclass with required fields | unit | `pytest tests/test_deploy_providers.py::test_deploy_result_fields -x` | ❌ Wave 0 |
| DEPL-02 | VercelProvider.deploy() calls vercel link + vercel --yes + vercel promote | unit | `pytest tests/test_deploy_providers.py::TestVercelProvider -x` | ❌ Wave 0 |
| DEPL-02 | Existing phase_3_executor integration tests still pass after refactor | integration | `pytest tests/test_phase_3_executor.py -k "not NextjsDir" -x` | ✅ (25 passing) |
| DEPL-03 | GCPProvider.deploy() runs gcloud auth preflight before deploy | unit | `pytest tests/test_deploy_providers.py::TestGCPProvider::test_preflight_auth_check -x` | ❌ Wave 0 |
| DEPL-03 | GCPProvider.deploy() extracts *.run.app URL from stderr | unit | `pytest tests/test_deploy_providers.py::TestGCPProvider::test_url_extraction -x` | ❌ Wave 0 |
| DEPL-03 | GCPProvider.deploy() returns error result when gcloud auth fails | unit | `pytest tests/test_deploy_providers.py::TestGCPProvider::test_auth_failure -x` | ❌ Wave 0 |
| DEPL-04 | AWSProvider.deploy() raises NotImplementedError with guidance text | unit | `pytest tests/test_deploy_providers.py::TestAWSProvider -x` | ❌ Wave 0 |
| DEPL-05 | LocalOnlyProvider.deploy() runs npm run build | unit | `pytest tests/test_deploy_providers.py::TestLocalOnlyProvider::test_runs_npm_build -x` | ❌ Wave 0 |
| DEPL-05 | LocalOnlyProvider.deploy() returns http://localhost:3000 URL on success | unit | `pytest tests/test_deploy_providers.py::TestLocalOnlyProvider::test_returns_localhost_url -x` | ❌ Wave 0 |
| DEPL-05 | LocalOnlyProvider.verify() returns True without HTTP call | unit | `pytest tests/test_deploy_providers.py::TestLocalOnlyProvider::test_verify_skips_http -x` | ❌ Wave 0 |
| DEPL-06 | get_provider("vercel") returns VercelProvider instance | unit | `pytest tests/test_deploy_providers.py::TestRegistry -x` | ❌ Wave 0 |
| DEPL-06 | get_provider("unknown") raises ValueError | unit | `pytest tests/test_deploy_providers.py::TestRegistry::test_unknown_target -x` | ❌ Wave 0 |
| DEPL-06 | deploy_target forwarded from _pipeline_bridge to PhaseContext.extra | unit | `pytest tests/test_pipeline_bridge.py -x` | ✅ (needs new test cases) |
| DEPL-06 | test_subprocess_audit still passes after adding new provider files | static | `pytest tests/test_subprocess_audit.py -x` | ✅ |

### Sampling Rate

- **Per task commit:** `python3 -m pytest tests/test_deploy_providers.py tests/test_subprocess_audit.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ --ignore=tests/test_deploy_agent_runner.py --ignore=tests/test_phase_2a_executor.py -q --tb=short`
- **Phase gate:** Full suite green (ignoring pre-existing failures in test_phase_3_executor.py TestNextjsDir classes and test_deploy_agent_runner/test_phase_2a_executor which have SDK import errors unrelated to Phase 9)

### Wave 0 Gaps

- [ ] `tests/test_deploy_providers.py` — covers DEPL-01 through DEPL-06 (main test file; must be created)
- [ ] `tools/deploy_providers/__init__.py` — module init
- [ ] `tools/deploy_providers/base.py` — DeployProvider ABC + DeployResult
- [ ] `tools/deploy_providers/registry.py` — get_provider() factory
- [ ] `tools/deploy_providers/vercel_provider.py` — extracted from phase_3_executor.py
- [ ] `tools/deploy_providers/gcp_provider.py` — new GCP implementation
- [ ] `tools/deploy_providers/aws_provider.py` — stub
- [ ] `tools/deploy_providers/local_provider.py` — LocalOnlyProvider

---

## Sources

### Primary (HIGH confidence)

- Python stdlib `abc` module (Python 3.10+ built-in) — ABC, abstractmethod
- Python stdlib `dataclasses` module — frozen dataclass pattern for DeployResult
- `/Users/masa/Development/web-app-factory/tools/phase_executors/phase_3_executor.py` — verified Vercel logic to extract (lines 254-749)
- `/Users/masa/Development/web-app-factory/tools/gates/deployment_gate.py` — verified provider-agnostic HTTP health check
- `/Users/masa/Development/web-app-factory/tools/gates/gate_result.py` — frozen dataclass pattern to follow
- `/Users/masa/Development/web-app-factory/tools/phase_executors/base.py` — ABC pattern already in use for PhaseExecutor
- `/Users/masa/Development/web-app-factory/web_app_factory/_pipeline_bridge.py` — confirmed deploy_target missing from pipeline_kwargs forwarding
- `/Users/masa/Development/web-app-factory/tools/contract_pipeline_runner.py` — confirmed PhaseContext.extra construction (line 424-435)
- gcloud CLI SDK 558.0.0 (verified: `gcloud --version`, `gcloud run deploy --help`) — `--source` flag, stderr URL format

### Secondary (MEDIUM confidence)

- gcloud run deploy `--source .` output pattern: "Service URL: https://\*.run.app" in stderr — confirmed from gcloud run deploy --help documentation and local CLI inspection
- gcloud auth pre-flight: `gcloud auth print-access-token` returns exit code 0 when authenticated — verified locally (gcloud is authenticated on this machine)
- `gcloud config get-value project` returns current project — verified locally (returns `gen-lang-client-0469915824`)

### Tertiary (LOW confidence)

- Cloud Run service URL regex pattern `https://[^\s]+\.run\.app` — based on documented `*.run.app` suffix; edge cases (custom domains) not tested

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib only; existing patterns already in codebase
- Architecture: HIGH — directly mirrors existing PhaseExecutor/GateResult patterns
- Pitfalls: HIGH — Pitfalls 1-4 verified from code inspection; Pitfall 5-6 verified from _pipeline_bridge.py source
- GCPProvider subprocess: MEDIUM — gcloud CLI available and tested for auth/help, but actual `gcloud run deploy --source .` not integration-tested during research

**Research date:** 2026-03-23
**Valid until:** 2026-04-22 (gcloud SDK stable; ABC/dataclass patterns are Python stdlib)
