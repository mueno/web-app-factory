# Phase 4: Ship - Research

**Researched:** 2026-03-22
**Domain:** Vercel deployment, Lighthouse quality gates, axe-core accessibility, security headers, legal document generation, link integrity checking
**Confidence:** HIGH (architecture patterns verified against codebase; tool invocation patterns verified against official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Deploy-then-gate flow**
- Deploy first: Vercel preview deploy → get preview URL → run all quality gates against live URL → MCP human approval → production promote
- Auto-provisioning: `vercel link --yes` auto-creates a new Vercel project if none is linked; no manual pre-setup required
- Preview → Approval → Production: Pipeline deploys to preview first, runs all gates against the preview URL, then requires MCP `approve_gate` sign-off before promoting to production via `vercel --prod` (or `vercel promote <url>`)
- MCP approval timing: After all quality gates pass, before production deploy. Human sees Lighthouse scores, security results, and legal docs before deciding

**Security headers configuration**
- Set in next.config.ts headers(): The build agent (Phase 2b) should include security headers in the generated next.config.ts — they are part of the app, not deployment config
- Basic CSP: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'` — allows Next.js inline scripts while blocking external scripts
- Other required headers: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`
- HSTS: Vercel provides HSTS automatically; the security headers gate verifies its presence but does not inject it
- Verification method: httpx GET request to deployed URL → check response headers contain all required headers

**Legal document generation**
- LLM-generated with PRD context: Deploy-agent reads PRD and build output to generate Privacy Policy and Terms of Service that reference actual app features
- Jurisdiction: Japanese law (APPI) as primary basis, with basic GDPR/CCPA mentions for international coverage. AllNew LLC is a Japanese entity
- Company information source: CLI flags `--company-name` and `--contact-email`. If not provided, legal docs contain placeholder text and the legal quality gate fails
- Link placement: Footer links on all pages — /privacy and /terms routes with Privacy Policy and Terms of Service content
- Quality gate: Legal docs must not contain template placeholders (YOUR_APP_NAME, YOUR_COMPANY, etc.) and must reference at least one app-specific feature by name

**Gate failure remediation**
- Auto-fix + retry: When Lighthouse or axe-core gates fail, deploy-agent reads the diagnostic report, applies code fixes, re-deploys, and re-runs the failing gate
- Retry limit: Maximum 3 attempts per gate. After 3 failures, pipeline stops and escalates to human with full diagnostic history
- Fix scope: Performance optimization (image optimization, JS removal, CSS minification) AND accessibility fixes (alt text, contrast, ARIA attributes) are both permitted
- axe-core critical violations: Same auto-fix + retry pattern
- Retry cycle: fix code → npm run build → vercel deploy (new preview) → re-run failing gate only (not all gates)

### Claude's Discretion
- Deploy-agent system prompt wording (web deployment expertise, Lighthouse optimization knowledge)
- Exact Lighthouse CI invocation method (lighthouse-ci CLI or programmatic API)
- axe-core invocation method (Playwright + @axe-core/playwright or standalone CLI)
- Link integrity checker implementation (custom httpx crawler or existing tool)
- Sub-step breakdown within Phase 3 executor
- Exact retry backoff timing between attempts
- Whether to generate legal docs before or after quality gates (order within the phase)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GATE-02 | Lighthouse gate runs against deployed preview URL with thresholds (perf ≥85, a11y ≥90, SEO ≥85) | Lighthouse CLI via `npx lighthouse <url> --output=json` + subprocess parsing; lhci autorun for CI-ready invocation |
| GATE-03 | Security headers gate verifies CSP, HSTS, X-Frame-Options, X-Content-Type-Options | httpx GET → response.headers dict check; headers set in next.config.ts (Phase 2b concern) |
| GATE-04 | Link integrity gate verifies no internal 404s in deployed app | Custom httpx BFS crawler over the deployed URL |
| GATE-07 | axe-core accessibility check runs in addition to Lighthouse a11y score | axe-playwright-python via sync_playwright; subprocess node script invoking @axe-core/playwright; filter impact == "critical" |
| LEGL-01 | Legal phase generates Privacy Policy from web-adapted template | Deploy-agent LLM generation with PRD content injection; APPI-primary with GDPR/CCPA mentions |
| LEGL-02 | Legal phase generates Terms of Service from web-adapted template | Same LLM generation pattern with feature-specific content |
| LEGL-03 | Legal documents reference actual app features from build output | Quality gate: scan for placeholder strings; verify at least one feature noun from PRD is present |
| DEPL-01 | Pipeline deploys to Vercel via CLI (`vercel pull → build → deploy --prebuilt`) | Verified: `vercel build` → `.vercel/output` → `vercel deploy --prebuilt --yes`; stdout = deployment URL |
| DEPL-02 | Preview URL captured in `docs/pipeline/deployment.json` after deploy | Capture subprocess stdout from `vercel deploy`; write to deployment.json |
| DEPL-03 | Deploy gate verifies HTTP 200 on deployed URL within 30 seconds | httpx.get(url, timeout=30) → response.status_code == 200; poll with backoff |
| DEPL-04 | MCP approval gate wraps deployment (human sign-off before production deploy) | `approve_gate` already implemented in `factory_mcp_server.py`; dispatch `mcp_approval` gate type → call approve_gate MCP tool |
</phase_requirements>

---

## Summary

Phase 4 (Ship) adds a Phase 3 executor (`phase_3_executor.py`) plus 6 new gate type dispatchers to `_run_gate_checks()`. The executor orchestrates: (1) Vercel preview deploy, (2) legal doc generation, (3) 4 quality gates (Lighthouse, axe-core, security headers, link integrity), (4) MCP approval, (5) Vercel production deploy. It follows the same `PhaseExecutor` ABC + self-registration pattern as Phases 1a/1b/2a/2b.

The deploy-agent is cloned from `build_agent_runner.py` with `cwd=project_dir`, `allowed_tools=["Read", "Write", "Bash"]`, and a domain-specific system prompt emphasizing Vercel CLI, Lighthouse optimization, and accessibility remediation. The agent prompt injects the full PRD + quality gate results so the agent can generate contextual legal documents and fix gate failures.

The 6 gate types — `lighthouse`, `accessibility`, `security_headers`, `link_integrity`, `deployment`, `mcp_approval` — each have a standalone Python function in `tools/gates/` that returns `GateResult`. `_run_gate_checks()` switches on `gate.type` and delegates, following the existing `build`/`static_analysis` dispatch pattern exactly.

**Primary recommendation:** Implement Phase 3 executor with 7 ordered sub-steps: `provision`, `deploy_preview`, `generate_legal`, `gate_lighthouse`, `gate_accessibility`, `gate_security_headers`, `gate_link_integrity`, `gate_mcp_approval`, `deploy_production`. Each sub-step maps to one of the new gate functions or agent calls. Gate failures with retry use a counter tracked in `SubStepResult.extra`.

---

## Standard Stack

### Core (already in pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | ≥0.28.0 | HTTP requests for security headers, link integrity, deployment health check | Already used; async-capable |
| claude-agent-sdk | ≥0.1.50 | Deploy-agent LLM calls | Same as build-agent pattern |
| subprocess (stdlib) | — | Invoke vercel CLI, lighthouse CLI, node scripts | Pattern established by build_gate.py |

### New Tools (external, invoked via subprocess)
| Tool | Install | Purpose | Invocation Method |
|------|---------|---------|------------------|
| lighthouse (npm) | `npm install -g lighthouse` OR `npx lighthouse` | Lighthouse scores | `npx lighthouse <url> --output=json --output-path=stdout --chrome-flags="--headless"` |
| @lhci/cli (npm) | `npm install -g @lhci/cli` OR `npx @lhci/cli` | Lighthouse CI with threshold assertions | `npx lhci autorun --collect.url=<url>` |
| @axe-core/playwright (npm) | `npm install @axe-core/playwright playwright` | Accessibility critical violations | Node.js script via subprocess |
| vercel (npm) | `npm install -g vercel` OR env-based install | Deploy, promote, link | subprocess with `--yes` for non-interactive |

### Python Accessibility Alternative
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| axe-playwright-python | ≥0.5.0 | Run axe-core from Python directly | If avoiding node subprocess complexity |
| playwright (Python) | ≥1.50 | Browser automation for axe | Required by axe-playwright-python |

**Installation (new external tools):**
```bash
# Node tools (run once during pipeline setup or in Phase 3 executor)
npm install -g lighthouse @lhci/cli vercel
# OR use npx for zero-install (recommended for subprocess invocation)

# Python tools (add to pyproject.toml)
uv add axe-playwright-python playwright
playwright install chromium
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `npx lighthouse` via subprocess | Node.js programmatic API (`import lighthouse from 'lighthouse'`) | Programmatic API requires a separate Node.js runner script; subprocess is simpler to integrate with Python pipeline |
| axe-playwright-python | Node script with @axe-core/playwright | Python approach avoids spawning extra Node process; same axe-core engine under the hood |
| Custom httpx link crawler | pylinkvalidator CLI | Custom crawler has no extra deps; follows existing httpx pattern in codebase |

---

## Architecture Patterns

### Recommended Project Structure (new files)
```
tools/
├── gates/
│   ├── build_gate.py              # existing
│   ├── static_analysis_gate.py    # existing
│   ├── lighthouse_gate.py         # NEW: run lighthouse CLI, parse JSON
│   ├── accessibility_gate.py      # NEW: axe-core via subprocess node script
│   ├── security_headers_gate.py   # NEW: httpx header check
│   ├── link_integrity_gate.py     # NEW: httpx BFS crawler
│   ├── deployment_gate.py         # NEW: httpx health check + URL capture
│   └── mcp_approval_gate.py       # NEW: calls approve_gate MCP tool
├── phase_executors/
│   ├── phase_3_executor.py        # NEW: Phase 3 (Ship) executor
│   ├── deploy_agent_runner.py     # NEW: clone of build_agent_runner.py
│   ...

agents/
└── definitions.py    # fill in DEPLOY_AGENT system prompt

factory.py            # add --company-name, --contact-email flags
```

### Pattern 1: Gate Function Signature (follow existing gates exactly)
**What:** Every gate function returns `GateResult`, takes `project_dir` and contextual args.
**When to use:** All 6 new gate types.
```python
# Source: tools/gates/build_gate.py (verified pattern)
def run_lighthouse_gate(url: str, phase_id: str = "3") -> GateResult:
    checked_at = _now_iso()
    # ... subprocess call to lighthouse CLI ...
    # ... parse JSON result ...
    return GateResult(
        gate_type="lighthouse",
        phase_id=phase_id,
        passed=passed,
        status="PASS" if passed else "BLOCKED",
        severity="INFO" if passed else "BLOCK",
        confidence=1.0 if passed else 0.0,
        checked_at=checked_at,
        issues=issues,
    )
```

### Pattern 2: Gate Dispatcher in _run_gate_checks (extend existing)
**What:** Add elif branches for the 6 new gate types.
**When to use:** In `tools/contract_pipeline_runner.py _run_gate_checks()`.
```python
# Source: tools/contract_pipeline_runner.py (verified dispatch pattern)
elif gate_type == "lighthouse":
    from tools.gates.lighthouse_gate import run_lighthouse_gate
    deployment_url = _read_deployment_url(project_dir)
    gate_result = run_lighthouse_gate(
        url=deployment_url,
        thresholds=conditions.get("thresholds", {}),
        phase_id=phase_id,
    )
    if not gate_result.passed:
        issues.extend(gate_result.issues)

elif gate_type == "mcp_approval":
    from tools.gates.mcp_approval_gate import run_mcp_approval_gate
    gate_result = run_mcp_approval_gate(phase_id=phase_id, project_dir=project_dir)
    if not gate_result.passed:
        issues.extend(gate_result.issues)
```

### Pattern 3: Phase 3 Executor (follow Phase2bBuildExecutor exactly)
**What:** `Phase3ShipExecutor(PhaseExecutor)` with `phase_id = "3"`, self-registers at import.
**When to use:** For the Phase 3 ship executor.
```python
# Source: tools/phase_executors/phase_2b_executor.py (verified pattern)
class Phase3ShipExecutor(PhaseExecutor):
    @property
    def phase_id(self) -> str:
        return "3"

    @property
    def sub_steps(self) -> list:
        return [
            "provision",
            "deploy_preview",
            "generate_legal",
            "gate_lighthouse",
            "gate_accessibility",
            "gate_security_headers",
            "gate_link_integrity",
            "gate_mcp_approval",
            "deploy_production",
        ]

    def execute(self, ctx: PhaseContext) -> PhaseResult:
        ...

# Self-registration guard (same as 2b pattern)
if get_executor("3") is None:
    register(Phase3ShipExecutor())
```

### Pattern 4: Deploy-Agent Runner (clone of build_agent_runner.py)
**What:** `run_deploy_agent()` with `allowed_tools=["Read", "Write", "Bash"]` and `cwd=project_dir`.
**When to use:** For LLM-driven legal doc generation and gate failure remediation.
```python
# Source: tools/phase_executors/build_agent_runner.py (verified pattern)
def run_deploy_agent(
    prompt: str,
    system_prompt: str,
    project_dir: str,
    max_turns: int = 75,  # ship phase needs more turns: deploy + legal + fix iterations
) -> str:
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        allowed_tools=["Read", "Write", "Bash"],
        max_turns=max_turns,
        cwd=project_dir,
    )
    # ... asyncio.run() bridge (identical to build_agent_runner) ...
```

### Pattern 5: Vercel CLI Invocation (subprocess, stdout = URL)
**What:** Deploy to Vercel preview; capture deployment URL from stdout.
**When to use:** In `deploy_preview` sub-step of Phase 3 executor.
```python
# Source: https://vercel.com/docs/cli/deploy (verified)
# stdout is ALWAYS the deployment URL when deploying
result = subprocess.run(
    ["vercel", "--yes"],  # preview deploy (no --prod flag)
    cwd=project_dir,
    capture_output=True,
    text=True,
    timeout=300,
)
if result.returncode == 0:
    preview_url = result.stdout.strip()  # e.g. "https://myapp-abc123.vercel.app"
```

### Pattern 6: Vercel Production Promote
**What:** After MCP approval, promote preview to production.
**When to use:** In `deploy_production` sub-step after `gate_mcp_approval` passes.
```python
# Source: https://vercel.com/docs/cli/promote (verified)
# "vercel promote <url>" promotes a preview deployment to current production
result = subprocess.run(
    ["vercel", "promote", preview_url, "--yes", "--timeout=5m"],
    cwd=project_dir,
    capture_output=True,
    text=True,
    timeout=360,
)
```

### Anti-Patterns to Avoid
- **Calling vercel --prod directly (no preview stage):** Violates locked decision of preview-first flow; run gates on preview before production.
- **Running all gates sequentially without caching the preview URL:** The URL must be written to `deployment.json` before gate checks so each gate can read it independently.
- **Injecting Gate conditions into the deploy-agent prompt:** Violates `45-quality-driven-execution.md`; the agent should see deliverable quality criteria, not gate markers.
- **Skipping self-assessment for Phase 3:** CONT-04 is mandatory — call `generate_quality_self_assessment("3", ...)` before gate submission.
- **Lighthouse with non-headless Chrome in subprocess:** Will steal window focus on macOS (per `50-ios-development.md`); always pass `--chrome-flags="--headless"`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Lighthouse scoring | Custom performance metric crawler | `npx lighthouse <url> --output=json` CLI | Lighthouse handles throttling, emulation, Chromium management; hand-rolling gives wrong scores |
| Accessibility critical violations | Custom HTML parser | axe-core (via axe-playwright-python or node subprocess) | axe-core contains 100+ WCAG rules; detecting "critical" impact requires the axe rule engine |
| HSTS injection | Custom header setting code | Vercel automatic HSTS | Vercel injects Strict-Transport-Security on production domains automatically; inject it yourself and you create a conflict |
| Link crawling with JS-rendered content | Scraping raw HTML | Playwright headless + link extraction | Next.js pages may have client-side routing; playwright renders the full JS before extracting hrefs |
| Legal document templates | Hand-written APPI-compliant boilerplate | LLM generation with PRD context injection | Every app has different data types and features; static templates cannot pass the "references actual features" quality gate |

**Key insight:** Lighthouse, axe-core, and Vercel CLI are production-grade tools maintained by Google and Vercel respectively. Replacing them with custom implementations introduces measurement divergence and is explicitly out of scope for this pipeline's verification goals.

---

## Common Pitfalls

### Pitfall 1: Vercel CLI token not available in subprocess environment
**What goes wrong:** `vercel` CLI returns `Error: No token found` when called via `subprocess.run()`.
**Why it happens:** `VERCEL_TOKEN` environment variable not passed to subprocess env; or `~/.local/share/com.vercel.cli` auth file exists but subprocess has different HOME.
**How to avoid:** Pass `env={**os.environ}` explicitly to `subprocess.run()`. Ensure `VERCEL_TOKEN` env var is set (checked in startup preflight). Add `vercel --version` to `startup_preflight.py` checks.
**Warning signs:** Exit code non-zero + stderr contains "No token found" or "Not authenticated".

### Pitfall 2: Lighthouse requires Chromium; headless mode needed on macOS
**What goes wrong:** `lighthouse` CLI hangs or steals window focus on macOS.
**Why it happens:** Lighthouse launches real Chrome by default unless `--chrome-flags="--headless"` is passed.
**How to avoid:** Always include `--chrome-flags="--headless"` (or `--headless=new` for newer Chromium). Add `--no-sandbox` for CI environments.
**Warning signs:** Subprocess timeout (Lighthouse hanging waiting for Chrome window) or chrome window appearing.

### Pitfall 3: Lighthouse scores are non-deterministic (run variance)
**What goes wrong:** Gate passes on one run, fails the next for the same app.
**Why it happens:** Lighthouse performance scores vary with CPU load, network simulation, and test ordering.
**How to avoid:** Run Lighthouse 3 times via `--runs=3` (or lhci's `numberOfRuns: 3`) and use the median score. Accept scores within 5 points of threshold — or set threshold 5 points below the required value to absorb variance.
**Warning signs:** Scores fluctuating ±10 points between runs.

### Pitfall 4: axe-core blocks on `asyncio.run()` if already in async context
**What goes wrong:** `RuntimeError: This event loop is already running` when calling axe-playwright-python from an async context.
**Why it happens:** The executor calls `asyncio.run()` (sync/async bridge) which conflicts with any existing event loop.
**How to avoid:** Use `sync_playwright` (not async) — same pattern as `build_agent_runner.py`. Or invoke axe via a node subprocess script to sidestep Python async entirely.
**Warning signs:** `RuntimeError` in axe gate; the build-agent runner uses `asyncio.run()` successfully because it's called from synchronous executor code.

### Pitfall 5: `vercel deploy` preview URL captures extra lines from stderr
**What goes wrong:** Parsing `result.stdout.strip()` returns multi-line output instead of just the URL.
**Why it happens:** Vercel occasionally writes additional messages to stdout (deployment progress, warnings).
**How to avoid:** Parse stdout for a line matching `https://.*\.vercel\.app` using regex instead of assuming it's the only line.
**Warning signs:** `deployment.json` URL field contains text like "Vercel CLI 39.x" prefix.

### Pitfall 6: `vercel link --yes` creates project under wrong team/scope
**What goes wrong:** Project is linked to wrong Vercel team when multiple teams exist.
**Why it happens:** `--yes` uses the default scope which may be a personal account or wrong team.
**How to avoid:** If `VERCEL_ORG_ID` env var is set, pass it. Otherwise document that default scope behavior is acceptable for v1. Add scope to preflight warning if multiple teams detected.
**Warning signs:** Deployment URL belongs to wrong team subdomain.

### Pitfall 7: Legal quality gate false-positive on placeholder detection
**What goes wrong:** Legal gate fails on docs that contain legitimate text like "YOUR RIGHTS" in legal boilerplate.
**Why it happens:** Placeholder detection regex is too broad.
**How to avoid:** Check specifically for `YOUR_APP_NAME`, `YOUR_COMPANY`, `[COMPANY]`, `[DATE]` — exact template marker patterns, not generic `YOUR_` prefix. The legal-agent should know to avoid these exact strings.
**Warning signs:** Legal gate fails on valid docs due to false positive regex match.

---

## Code Examples

Verified patterns from official sources and existing codebase:

### Lighthouse CLI invocation (subprocess, parse JSON)
```python
# Invocation: npx lighthouse + --output=json
# Scores are floats 0.0-1.0; multiply by 100 for percentage
# Source: https://developer.chrome.com/docs/lighthouse (verified)
import json, subprocess, tempfile, os

def _run_lighthouse(url: str) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        output_path = f.name
    try:
        result = subprocess.run(
            [
                "npx", "lighthouse", url,
                "--output=json",
                f"--output-path={output_path}",
                "--chrome-flags=--headless --no-sandbox",
                "--only-categories=performance,accessibility,seo",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            return {}
        with open(output_path, encoding="utf-8") as f:
            return json.load(f)
    finally:
        try:
            os.unlink(output_path)
        except OSError:
            pass

# Score extraction (multiply by 100; scores are 0.0-1.0 floats)
lhr = _run_lighthouse(url)
categories = lhr.get("categories", {})
performance = round((categories.get("performance", {}).get("score") or 0) * 100)
accessibility = round((categories.get("accessibility", {}).get("score") or 0) * 100)
seo = round((categories.get("seo", {}).get("score") or 0) * 100)
```

### axe-core accessibility check (axe-playwright-python)
```python
# Source: https://github.com/pamelafox/axe-playwright-python (verified)
# and https://playwright.dev/docs/accessibility-testing
from playwright.sync_api import sync_playwright
from axe_playwright_python.sync_playwright import Axe

def _run_axe(url: str) -> list[dict]:
    """Return list of critical violations. Empty list = gate passes."""
    axe = Axe()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        results = axe.run(page)
        browser.close()
    # Filter to critical impact only (per GATE-07 requirement)
    return [
        v for v in results.response.get("violations", [])
        if v.get("impact") == "critical"
    ]
```

### Security headers check (httpx, verified pattern)
```python
# Source: existing httpx pattern in validate_npm_packages (tools/phase_executors/phase_1a_executor.py)
import httpx

REQUIRED_HEADERS = [
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Content-Security-Policy",
    # Note: Vercel injects Strict-Transport-Security; we check it but don't require the app to set it
]

def _check_security_headers(url: str) -> list[str]:
    """Return list of missing required headers."""
    try:
        response = httpx.get(url, timeout=30, follow_redirects=True)
        response_headers_lower = {k.lower(): v for k, v in response.headers.items()}
        missing = []
        for hdr in REQUIRED_HEADERS:
            if hdr.lower() not in response_headers_lower:
                missing.append(f"Missing security header: {hdr}")
        return missing
    except httpx.RequestError as exc:
        return [f"HTTP request failed: {type(exc).__name__}"]
```

### Vercel deployment and URL capture
```python
# Source: https://vercel.com/docs/cli/deploy — "stdout is always the Deployment URL"
import re, subprocess

def _deploy_to_vercel_preview(project_dir: str) -> tuple[bool, str]:
    """Deploy to Vercel preview. Returns (success, url)."""
    result = subprocess.run(
        ["vercel", "--yes"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ},
    )
    if result.returncode != 0:
        return False, result.stderr.strip()

    # Extract URL from stdout (may contain extra lines)
    stdout = result.stdout.strip()
    url_match = re.search(r"https://[^\s]+\.vercel\.app", stdout)
    url = url_match.group(0) if url_match else stdout.split("\n")[-1].strip()
    return True, url

def _promote_to_production(preview_url: str, project_dir: str) -> bool:
    """Promote a preview deployment to production."""
    # Source: https://vercel.com/docs/cli/promote (verified)
    result = subprocess.run(
        ["vercel", "promote", preview_url, "--yes", "--timeout=5m"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=360,
        env={**os.environ},
    )
    return result.returncode == 0
```

### Vercel auto-provisioning
```python
# Source: https://vercel.com/docs/cli/link (verified)
# --yes: skip questions, use defaults (current directory name as project name)
# Creates new project if .vercel/project.json does not exist
result = subprocess.run(
    ["vercel", "link", "--yes"],
    cwd=project_dir,
    capture_output=True,
    text=True,
    timeout=60,
    env={**os.environ},
)
# After this, .vercel/project.json contains orgId and projectId
```

### security headers in next.config.ts (generated by Phase 2b agent)
```typescript
// Source: https://nextjs.org/docs/app/guides/content-security-policy (verified 2026-03-20)
// Place in next.config.ts (generated by build agent in Phase 2b)
const cspHeader = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data:",
  "font-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: cspHeader },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};
```

### deployment.json schema (written after preview deploy)
```json
{
  "preview_url": "https://myapp-abc123.vercel.app",
  "production_url": "https://myapp.vercel.app",
  "deployed_at": "2026-03-22T10:00:00Z",
  "platform": "vercel",
  "http_status": 200
}
```
Path: `{project_dir}/docs/pipeline/deployment.json`

### legal-quality gate check (placeholder detection)
```python
# Placeholder patterns that must NOT appear in generated legal docs
_PLACEHOLDER_PATTERNS = [
    "YOUR_APP_NAME", "YOUR_COMPANY", "[COMPANY]", "[DATE]",
    "[APP_NAME]", "[YOUR_EMAIL]", "[CONTACT_EMAIL]",
    "INSERT_APP_NAME", "INSERT_COMPANY",
]

def _check_legal_quality(doc_path: str, app_features: list[str]) -> list[str]:
    """Return list of quality issues in a legal document."""
    try:
        content = Path(doc_path).read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Cannot read legal doc: {type(exc).__name__}"]
    issues = []
    for placeholder in _PLACEHOLDER_PATTERNS:
        if placeholder in content:
            issues.append(f"Legal doc contains placeholder: {placeholder!r}")
    # Must reference at least one app-specific feature name
    if app_features and not any(feat in content for feat in app_features):
        issues.append("Legal doc does not reference any app-specific features")
    return issues
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Nonce-based CSP (required dynamic rendering) | Static CSP in next.config.ts with `'unsafe-inline'` (for Next.js without nonces) | Always valid; nonces add complexity | Static CSP sufficient for v1; no dynamic rendering overhead |
| `vercel --prod` directly | `vercel` (preview) → gates → `vercel promote <url>` | Vercel CLI added `promote` in 2023 | Cleaner separation of preview testing from production promotion |
| `lighthouse` global install required | `npx lighthouse` (zero-install) | npm 5.2+ (2017) | No global install step; subprocess call with npx just works |
| Separate test framework for a11y | axe-core embedded in playwright | 2020-present | Single browser instance runs both navigation and accessibility scan |

**Deprecated/outdated:**
- `vercel --name` flag: Deprecated in favor of `vercel link` for project association
- Lighthouse JSON output to file (old): `--output-path=stdout` now supported for piped output; use temp file for reliability
- `middleware.js` for security headers: Works but `next.config.ts headers()` is simpler for static headers without dynamic logic

---

## Open Questions

1. **Playwright/Chromium availability in the pipeline environment**
   - What we know: `startup_preflight.py` checks Node.js, Python, Vercel CLI; does NOT check Chrome/Chromium
   - What's unclear: Whether Chromium is installed in the environment where Lighthouse and axe-core run
   - Recommendation: Add `chromium` or `chrome` check to startup preflight; or use `@lhci/cli` which bundles Chromium via Puppeteer

2. **axe-playwright-python async conflict with agent runner**
   - What we know: The build-agent runner uses `asyncio.run()` as sync/async bridge; axe-playwright-python uses sync_playwright
   - What's unclear: Whether the executor's synchronous execution context is safe for sync_playwright (it should be, since executors are called synchronously)
   - Recommendation: Use sync_playwright in accessibility_gate.py; test explicitly with `pytest` to confirm no event loop conflict

3. **MCP approval gate blocking mechanism**
   - What we know: `approve_gate` in `factory_mcp_server.py` uses file-based polling (2-second intervals, indefinite wait)
   - What's unclear: How the gate runner calls the MCP tool from within `_run_gate_checks()` — the MCP server runs as a separate process
   - Recommendation: The `mcp_approval` gate dispatcher should invoke `approve_gate` directly as a function import (not via MCP transport), following the pattern in `test_factory_mcp_bridge.py`. The MCP transport is for IDE integration; the gate runner can call the function directly.

4. **Retry counter state between sub-steps**
   - What we know: Phase 3 executor has a max 3 retry loop per gate failure; retry cycle = fix code → build → deploy → re-run gate
   - What's unclear: Where to store the retry counter (in-memory per gate, or in SubStepResult.extra)
   - Recommendation: Track retry count as a local variable within the executor's gate retry loop; record total attempts in SubStepResult.notes. No need for persistence since the full loop runs within one execute() call.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x (uv run pytest) |
| Config file | `[tool.pytest.ini_options]` in pyproject.toml — `testpaths = ["tests"]` |
| Quick run command | `uv run pytest tests/test_phase_3_executor.py -x` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GATE-02 | Lighthouse gate parses scores, fails below threshold | unit (mocked subprocess) | `uv run pytest tests/test_lighthouse_gate.py -x` | ❌ Wave 0 |
| GATE-03 | Security headers gate reports missing headers | unit (mocked httpx) | `uv run pytest tests/test_security_headers_gate.py -x` | ❌ Wave 0 |
| GATE-04 | Link integrity gate reports 404 links | unit (mocked httpx) | `uv run pytest tests/test_link_integrity_gate.py -x` | ❌ Wave 0 |
| GATE-07 | axe-core gate reports zero critical violations | unit (mocked axe) | `uv run pytest tests/test_accessibility_gate.py -x` | ❌ Wave 0 |
| LEGL-01/02 | Legal docs generated without placeholders | unit (mocked agent) | `uv run pytest tests/test_phase_3_executor.py::test_legal_generation -x` | ❌ Wave 0 |
| LEGL-03 | Legal quality gate rejects placeholder-containing docs | unit | `uv run pytest tests/test_legal_quality_gate.py -x` | ❌ Wave 0 |
| DEPL-01 | Vercel deploy subprocess called with --yes | unit (mocked subprocess) | `uv run pytest tests/test_phase_3_executor.py::test_deploy_preview -x` | ❌ Wave 0 |
| DEPL-02 | Deployment URL written to deployment.json | unit | `uv run pytest tests/test_phase_3_executor.py::test_deployment_json -x` | ❌ Wave 0 |
| DEPL-03 | Deployment gate checks HTTP 200 within 30s | unit (mocked httpx) | `uv run pytest tests/test_deployment_gate.py -x` | ❌ Wave 0 |
| DEPL-04 | MCP approval gate blocks production deploy | unit (mocked approve_gate) | `uv run pytest tests/test_phase_3_executor.py::test_mcp_approval -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_phase_3_executor.py tests/test_lighthouse_gate.py tests/test_accessibility_gate.py tests/test_security_headers_gate.py tests/test_link_integrity_gate.py tests/test_deployment_gate.py -x -q`
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase_3_executor.py` — Phase 3 executor tests (sub-step flow, retry logic, self-assessment)
- [ ] `tests/test_lighthouse_gate.py` — Lighthouse gate (score parsing, threshold failure, subprocess timeout)
- [ ] `tests/test_accessibility_gate.py` — axe-core gate (critical violations filter, zero violations pass)
- [ ] `tests/test_security_headers_gate.py` — Security headers gate (missing header detection, all-present pass)
- [ ] `tests/test_link_integrity_gate.py` — Link integrity gate (404 detection, 200/301 pass)
- [ ] `tests/test_deployment_gate.py` — Deployment gate (HTTP 200 check, URL capture)
- [ ] `tools/gates/lighthouse_gate.py` — Lighthouse gate implementation
- [ ] `tools/gates/accessibility_gate.py` — axe-core gate implementation
- [ ] `tools/gates/security_headers_gate.py` — Security headers gate implementation
- [ ] `tools/gates/link_integrity_gate.py` — Link integrity gate implementation
- [ ] `tools/gates/deployment_gate.py` — Deployment health check + URL capture gate
- [ ] `tools/gates/mcp_approval_gate.py` — MCP approval gate dispatcher
- [ ] `tools/phase_executors/phase_3_executor.py` — Phase 3 Ship executor
- [ ] `tools/phase_executors/deploy_agent_runner.py` — Deploy-agent runner (clone of build_agent_runner.py)
- [ ] `agents/definitions.py` DEPLOY_AGENT — Replace placeholder system prompt

---

## Sources

### Primary (HIGH confidence)
- Vercel CLI deploy docs (`https://vercel.com/docs/cli/deploy`) — verified stdout=URL, `--prebuilt`, `--yes`, `--prod` flags
- Vercel CLI promote docs (`https://vercel.com/docs/cli/promote`) — verified `vercel promote <url> --yes --timeout=5m`
- Vercel CLI link docs (`https://vercel.com/docs/cli/link`) — verified `vercel link --yes` auto-provisions new project
- Next.js CSP docs (`https://nextjs.org/docs/app/guides/content-security-policy`) — verified `unsafe-inline` CSP pattern in `next.config.ts headers()`; last updated 2026-03-20
- Playwright accessibility testing docs (`https://playwright.dev/docs/accessibility-testing`) — verified @axe-core/playwright API, impact filtering
- Existing codebase patterns (`tools/gates/build_gate.py`, `tools/phase_executors/build_agent_runner.py`, `tools/phase_executors/phase_2b_executor.py`) — verified gate function signature, executor pattern, agent runner pattern

### Secondary (MEDIUM confidence)
- axe-playwright-python GitHub (`https://github.com/pamelafox/axe-playwright-python`) — sync_playwright usage pattern; confirmed PyPI package exists
- Lighthouse CLI JSON output structure — multiple sources confirm `categories.performance.score` is 0.0-1.0 float; multiply by 100

### Tertiary (LOW confidence)
- Lighthouse score variance (±5-10 points) — community reports; exact variance depends on environment
- `vercel promote` promoting preview deployments behavior — docs say confirmation required; `--yes` bypasses; untested in actual pipeline

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against official Vercel, Next.js, and Playwright docs
- Architecture: HIGH — patterns derived from verified existing codebase (Phase 2b executor, build gate)
- Pitfalls: MEDIUM — Vercel token/scope pitfalls from community; Lighthouse headless from official Playwright docs
- Gate implementations: MEDIUM — code examples are accurate patterns but untested end-to-end in this pipeline

**Research date:** 2026-03-22
**Valid until:** 2026-06-22 (90 days — Vercel CLI and Lighthouse are relatively stable; Next.js CSP docs updated 2026-03-20)
