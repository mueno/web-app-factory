# Phase 3: Build - Research

**Researched:** 2026-03-21
**Domain:** Next.js App Router scaffolding, code generation, build gates, static analysis gates
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Build agent uses Claude Agent SDK multi-turn tool-use loop (`run_agent` generalization of `run_spec_agent`)
- Allowed tools for build agent: `Read`, `Write`, `Bash` — no `WebSearch`
- `Bash` tool restricted by `cwd` set to the generated project directory (not the pipeline root)
- Max turns: 50 (higher than spec agent's 25)
- Phase 2a executor runs `npx create-next-app@latest` as deterministic subprocess (NOT through the agent) with flags: `--typescript --tailwind --app --src-dir --disable-git --use-npm`
- After subprocess: agent customizes scaffold (replace boilerplate page.tsx, configure next.config.ts, set strict TypeScript mode)
- Phase 2b build agent receives full PRD text + screen-spec.json in prompt
- Generation order: shared components first, then page-by-page following screen-spec.json route order
- Error boundaries: agent generates `error.tsx` and `not-found.tsx` for every route segment with async data dependencies
- Responsive: mobile-first Tailwind classes — base styles for mobile, `md:` and `lg:` prefixes for larger screens
- Build gate: `subprocess.run(["npm", "run", "build"], cwd=project_dir)` and `subprocess.run(["npx", "tsc", "--noEmit"], cwd=project_dir)` — `capture_output=True`, `timeout=120`
- Static analysis gate: regex-based file scanning (not AST)
- Check 1: scan `src/app/layout.tsx` and `src/app/page.tsx` for `"use client"` — fail if found
- Check 2: scan all files under `src/` for `NEXT_PUBLIC_.*KEY|NEXT_PUBLIC_.*SECRET|NEXT_PUBLIC_.*TOKEN` — fail if found
- New gate files: `tools/gates/build_gate.py`, `tools/gates/static_analysis_gate.py`
- `validate_npm_packages()` reused in Phase 2b for any additional dependencies

### Claude's Discretion

- Exact build agent system prompt wording
- Sub-step breakdown within Phase 2a and 2b executors
- Whether to generalize `run_spec_agent` or create a parallel `run_build_agent`
- Tailwind CSS v4 configuration details (PostCSS setup)
- Error handling for `create-next-app` subprocess failures
- Exact timeout values for gate subprocess calls

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BILD-01 | Phase 2a scaffolds Next.js project via `create-next-app` with TypeScript, Tailwind v4, App Router | Exact flag set verified: `--typescript --tailwind --app --src-dir --disable-git --use-npm` (note: `--no-git` is invalid; use `--disable-git`) |
| BILD-02 | Phase 2b generates pages, components, and API routes from PRD specification | Build agent pattern with `run_agent()` function, allowed_tools=["Read","Write","Bash"], cwd=project_dir |
| BILD-03 | Generated app passes `next build` production build without errors | subprocess.run with capture_output=True, timeout=120, NEXT_TELEMETRY_DISABLED=1 env var |
| BILD-04 | Generated app passes `tsc --noEmit` type-check without errors | `subprocess.run(["npx", "tsc", "--noEmit"], cwd=project_dir)` — runs standalone, does NOT require prior `next build`; needs `next-env.d.ts` to exist first |
| BILD-05 | Generated app is responsive (mobile-first Tailwind classes) | Base styles for mobile, `md:` prefix for tablet (≥768px), `lg:` for desktop (≥1024px) |
| BILD-06 | Generated app includes error boundaries (`error.tsx`, `not-found.tsx`) | `error.tsx` MUST have `"use client"` directive (it is a React error boundary); `not-found.tsx` is a server component by default |
| BILD-07 | npm packages validated against registry before install (hallucination prevention) | Reuse `validate_npm_packages()` from `phase_1a_executor.py`; call before any `npm install` bash command |
| GATE-01 | Build gate fails pipeline if `next build` or `tsc --noEmit` returns non-zero | `build_gate.py` returns `GateResult(passed=False)` on non-zero exit; stderr in `issues` list |
| GATE-05 | Static analysis gate flags `"use client"` in `layout.tsx` or `page.tsx` | `static_analysis_gate.py` — regex scan of specific files, fail if matched |
| GATE-06 | Static analysis gate fails on `NEXT_PUBLIC_` + secret-pattern env vars | `static_analysis_gate.py` — scan `src/**` with `NEXT_PUBLIC_.*KEY\|NEXT_PUBLIC_.*SECRET\|NEXT_PUBLIC_.*TOKEN` |
</phase_requirements>

## Summary

Phase 3 implements the build subsystem of the web-app-factory pipeline. It replaces two stub executors (`Phase2aStubExecutor`, `Phase2bStubExecutor`) with real implementations and adds two new gate executors (`build_gate.py`, `static_analysis_gate.py`).

The scaffold step (Phase 2a) runs `npx create-next-app@latest` as a deterministic subprocess — the key research finding is that the correct flag for suppressing git init is `--disable-git` (not `--no-git`, which does not exist). After scaffolding, the build agent customizes the scaffold via the Claude Agent SDK with `Bash` tool access. Phase 2b runs the same build agent (or a parallel variant) to generate full app code from the PRD and screen-spec.

The build gate pattern is straightforward: `subprocess.run` with `capture_output=True` and `timeout=120`. The critical risk is `next build` telemetry hanging — pass `NEXT_TELEMETRY_DISABLED=1` as an environment variable to avoid post-build telemetry flush delays. The `tsc --noEmit` check requires `next-env.d.ts` to exist; this file is generated by `next build`, so always run build gate before tsc gate, or call `next typegen` first.

The static analysis gate is regex-only. One important nuance: `error.tsx` files MUST contain `"use client"` (React error boundaries are required to be client components), so the `no_use_client_in_layout` gate must scan only `layout.tsx` and `page.tsx`, not error boundaries.

**Primary recommendation:** Build the `run_build_agent()` function as a new module (`build_agent_runner.py`) parallel to `spec_agent_runner.py` — this avoids entangling the two agents' tool sets and makes the pattern explicit. The shared helpers (`load_phase_quality_criteria`, `build_phase_system_prompt`) are already generic and reusable as-is.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 16.x (create-next-app@latest) | App framework | Locked decision — only supported framework |
| TypeScript | 5.x (bundled with create-next-app) | Type safety | Locked via `--typescript` flag |
| Tailwind CSS | v4 (installed by create-next-app) | Styling | Locked via `--tailwind` flag |
| @tailwindcss/postcss | v4 (installed with Tailwind v4) | PostCSS integration | Required for Tailwind v4 PostCSS pipeline |
| claude-agent-sdk | >=0.1.50 (already in pyproject.toml) | Build agent runtime | Established pattern from Phase 2 |
| httpx | >=0.28.0 (already in pyproject.toml) | npm registry validation | Established pattern from Phase 1a |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| subprocess (stdlib) | Python 3.10+ | Run build commands in gate executors | Build gate and tsc gate only |
| re (stdlib) | Python 3.10+ | Regex-based static analysis | Static analysis gate checks |
| asyncio (stdlib) | Python 3.10+ | sync/async bridge for agent calls | Same pattern as spec_agent_runner.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `build_agent_runner.py` (new file) | Generalize `spec_agent_runner.py` | New file is simpler: different tool set, different cwd semantics, different max_turns — no risk of breaking spec agent |
| Regex-based static analysis | AST-based TypeScript parsing | AST requires ts-morph or similar npm dependency; regex is sufficient for the two specific checks needed |
| `capture_output=True` | `stdout=PIPE, stderr=PIPE` separately | `capture_output=True` is shorthand for both; no deadlock risk with `subprocess.run` (uses `communicate()` internally) |

**Installation:**
```bash
# No new Python deps needed — all are already in pyproject.toml
# create-next-app installs its own packages into the generated project
npx create-next-app@latest project-name --typescript --tailwind --app --src-dir --disable-git --use-npm
```

## Architecture Patterns

### Recommended Project Structure (generated Next.js app)
```
{project_dir}/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout — NO "use client"
│   │   ├── page.tsx            # Root page — NO "use client"
│   │   ├── globals.css         # @import "tailwindcss"
│   │   ├── error.tsx           # Root error boundary — MUST have "use client"
│   │   ├── not-found.tsx       # 404 page — server component (no "use client")
│   │   └── [route]/
│   │       ├── page.tsx        # Route page — server component by default
│   │       ├── error.tsx       # Route error boundary — MUST have "use client"
│   │       └── not-found.tsx   # Route 404
│   └── components/
│       ├── ui/                 # Primitive components (Button, Card, etc.)
│       ├── layout/             # Layout components (Header, Footer, Sidebar)
│       └── [feature]/          # Feature-specific components
├── public/                     # Static assets
├── next.config.ts              # NextConfig type, TypeScript format
├── tsconfig.json               # strict: true (generated by create-next-app)
├── postcss.config.mjs          # @tailwindcss/postcss plugin
└── package.json
```

### Pattern 1: Phase 2a — Two-Step Scaffold
**What:** Run `npx create-next-app@latest` as a deterministic subprocess, then run build agent for customization.
**When to use:** Always for Phase 2a — reproducible scaffold before agent customization.
**Example:**
```python
# Source: CONTEXT.md locked decision + verified create-next-app docs
import subprocess
from pathlib import Path

def run_scaffold_subprocess(project_dir: Path, app_name: str) -> subprocess.CompletedProcess:
    """Run create-next-app deterministically (no prompts, no git, npm)."""
    result = subprocess.run(
        [
            "npx", "create-next-app@latest", app_name,
            "--typescript",
            "--tailwind",
            "--app",
            "--src-dir",
            "--disable-git",   # CRITICAL: not --no-git (that flag does not exist)
            "--use-npm",
            "--yes",           # Suppress any remaining prompts
        ],
        cwd=str(project_dir.parent),
        capture_output=True,
        text=True,
        timeout=180,           # create-next-app installs packages; allow 3 minutes
    )
    return result
```

### Pattern 2: Build Agent Runner
**What:** Parallel module to `spec_agent_runner.py` — same async/sync bridge, different tool set.
**When to use:** Phase 2a customization and Phase 2b code generation.
**Example:**
```python
# Source: spec_agent_runner.py pattern (existing) + CONTEXT.md locked decision
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import ResultMessage
import asyncio

def run_build_agent(
    prompt: str,
    system_prompt: str,
    project_dir: str,
    max_turns: int = 50,  # Higher than spec agent's 25
) -> str:
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        allowed_tools=["Read", "Write", "Bash"],  # Bash allowed; no WebSearch
        max_turns=max_turns,
        cwd=project_dir,  # Agent cwd = generated project dir (sandboxed)
    )

    async def _run() -> str:
        async for message in query(prompt, options=options):
            if isinstance(message, ResultMessage):
                return message.result or ""
        return ""

    return asyncio.run(_run())
```

### Pattern 3: Build Gate Subprocess
**What:** Run `npm run build` and `npx tsc --noEmit` as subprocess calls, return `GateResult`.
**When to use:** Phase 2a gate (build only) and Phase 2b gate (build + tsc).
**Example:**
```python
# Source: CONTEXT.md locked decision + python subprocess docs
import subprocess
from datetime import datetime, timezone
from tools.gates.gate_result import GateResult

_TIMEOUT_SECONDS = 120  # 2-minute cap per command

def run_build_command(cmd: list[str], project_dir: str) -> tuple[bool, str]:
    """Run a build command; return (passed, stderr_or_stdout)."""
    env = {**os.environ, "NEXT_TELEMETRY_DISABLED": "1"}  # Prevent hang on telemetry flush
    result = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        env=env,
    )
    passed = result.returncode == 0
    output = result.stderr if result.stderr else result.stdout
    return passed, output
```

### Pattern 4: Static Analysis Gate (Regex)
**What:** File-based regex scan; produce structured `GateResult` with file path + line number.
**When to use:** Phase 2b static analysis gate only.
**Example:**
```python
# Source: CONTEXT.md locked decision
import re
from pathlib import Path

def check_no_use_client_in_layout(project_dir: Path) -> list[dict]:
    """Scan layout.tsx and page.tsx for 'use client' directive."""
    issues = []
    targets = [
        project_dir / "src" / "app" / "layout.tsx",
        project_dir / "src" / "app" / "page.tsx",
    ]
    pattern = re.compile(r"""['"]use client['"]""")
    for filepath in targets:
        if not filepath.exists():
            continue
        for lineno, line in enumerate(filepath.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                issues.append({
                    "file": str(filepath.relative_to(project_dir)),
                    "line": lineno,
                    "message": f"'use client' found in {filepath.name} (server component boundary violation)",
                })
    return issues

def check_no_next_public_secrets(project_dir: Path) -> list[dict]:
    """Scan src/ for NEXT_PUBLIC_ secret-pattern variables."""
    issues = []
    pattern = re.compile(r"NEXT_PUBLIC_(?:.*KEY|.*SECRET|.*TOKEN)")
    src_dir = project_dir / "src"
    if not src_dir.exists():
        return issues
    for filepath in src_dir.rglob("*"):
        if not filepath.is_file():
            continue
        if filepath.suffix not in {".ts", ".tsx", ".js", ".jsx", ".env", ".env.local"}:
            continue
        for lineno, line in enumerate(filepath.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if pattern.search(line):
                issues.append({
                    "file": str(filepath.relative_to(project_dir)),
                    "line": lineno,
                    "message": f"Secret-pattern env var detected in {filepath.name}",
                })
    return issues
```

### Pattern 5: error.tsx (MUST have "use client")
**What:** Every async route segment needs an error boundary. error.tsx is a React error boundary, which MUST be a client component.
**When to use:** Build agent generates this for every route with async data deps.
**Example:**
```typescript
// Source: https://nextjs.org/docs/app/getting-started/error-handling (official docs, 2026-03-20)
'use client' // Error boundaries MUST be Client Components

import { useEffect } from 'react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={() => reset()}>Try again</button>
    </div>
  )
}
```

### Pattern 6: not-found.tsx (Server Component — no "use client")
**What:** 404 UI for a route segment. Server component by default (no "use client").
**When to use:** Build agent generates this for every route with dynamic data lookups.
**Example:**
```typescript
// Source: https://nextjs.org/docs/app/api-reference/file-conventions/not-found (official docs)
// NOT a client component — no "use client" directive
export default function NotFound() {
  return (
    <div>
      <h2>Not Found</h2>
      <p>Could not find requested resource.</p>
    </div>
  )
}
```

### Pattern 7: Tailwind v4 PostCSS Config
**What:** Tailwind v4 requires `@tailwindcss/postcss` (not `tailwindcss` directly in PostCSS). No `tailwind.config.js` needed.
**Example:**
```javascript
// postcss.config.mjs — Source: https://tailwindcss.com/docs/guides/nextjs (official docs)
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
export default config;
```
```css
/* globals.css */
@import "tailwindcss";
```

### Pattern 8: next.config.ts TypeScript Format
**What:** `next.config.ts` (TypeScript) uses `NextConfig` import type.
**Example:**
```typescript
// Source: https://nextjs.org/docs/app/api-reference/config/next-config-js (official docs)
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // strict TypeScript checking enabled by default (ignoreBuildErrors: false)
  reactStrictMode: true,
}

export default nextConfig
```

### Anti-Patterns to Avoid
- **`--no-git` flag**: Does not exist in create-next-app. The correct flag is `--disable-git`. Using `--no-git` causes the CLI to prompt interactively.
- **`"use client"` in layout.tsx or page.tsx**: Root layout and root page must be server components. Marking them as client components disables React Server Component benefits for the entire subtree.
- **`"use client"` omitted from error.tsx**: React error boundaries MUST be client components. Omitting `"use client"` from error.tsx causes a build error.
- **Running `tsc --noEmit` before `next build`**: `next-env.d.ts` is generated by `next build` (or `next dev`). Running `tsc --noEmit` on a fresh scaffold without `next-env.d.ts` will produce type errors. Always run build gate first, or include `next typegen` step.
- **No `NEXT_TELEMETRY_DISABLED=1`**: Without this env var, `next build` makes a telemetry flush network request after completion. Known bug (issue #70758) causes hang. Always pass this env var.
- **`validate_npm_packages` inside the agent**: The build agent should call `validate_npm_packages()` from Python before executing `npm install` commands, not leave validation to the agent's discretion. The executor intercepts and validates before the bash tool runs the install.
- **Gate scanning `.env` files without extension filter**: The `NEXT_PUBLIC_` scan should target `.ts`, `.tsx`, `.js`, `.jsx`, `.env`, `.env.local` files only — not binary files or `node_modules/`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Project scaffolding | Custom file generation | `npx create-next-app@latest` subprocess | create-next-app handles package.json, tsconfig, next.config, postcss, node_modules install atomically |
| Build command execution | Custom Node.js bridge | `subprocess.run(["npm", "run", "build"])` | Direct subprocess is simpler; no intermediate layer needed |
| npm package existence check | Custom npm API client | `validate_npm_packages()` (already in phase_1a_executor.py) | Pattern already validated and tested; extract to shared module if needed |
| TypeScript strict mode config | Custom tsconfig generator | create-next-app default (already sets `strict: true`) | create-next-app sets strict mode in tsconfig.json by default in recent versions |
| Error boundary components | Custom error handling | `error.tsx` convention (Next.js built-in) | Framework convention; all tooling understands it |

**Key insight:** The build agent's job is to generate domain code (pages, components), not to configure the build toolchain. The scaffold subprocess handles toolchain setup deterministically; the agent should never modify tsconfig.json, postcss.config.mjs, or package.json scripts.

## Common Pitfalls

### Pitfall 1: create-next-app `--no-git` vs `--disable-git`
**What goes wrong:** The subprocess fails or prompts interactively because `--no-git` is not a valid flag.
**Why it happens:** Historical search results show old examples using `--no-git`; the actual documented flag changed to `--disable-git`.
**How to avoid:** Use `--disable-git` as confirmed in current official docs (version 16.2.1, last updated 2026-03-03).
**Warning signs:** create-next-app subprocess exits non-zero or hangs waiting for interactive input.

### Pitfall 2: `tsc --noEmit` fails on fresh scaffold (missing next-env.d.ts)
**What goes wrong:** `npx tsc --noEmit` reports "Cannot find module 'next'" or missing type references.
**Why it happens:** `next-env.d.ts` is generated by `next build` or `next dev`. Fresh scaffold doesn't have it until first build.
**How to avoid:** Always run the build gate (`npm run build`) before running the tsc gate (`npx tsc --noEmit`). The YAML contract already orders them correctly: `npm run build` then `npx tsc --noEmit`.
**Warning signs:** TypeScript errors referencing `next/image`, `next/font`, or `next/navigation` that don't appear in editor.

### Pitfall 3: `next build` hangs on telemetry flush
**What goes wrong:** `next build` completes successfully but the subprocess never exits; timeout triggers.
**Why it happens:** Known Next.js bug (issues #70755, #70758) — telemetry flush after build hangs in some environments.
**How to avoid:** Pass `env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1"}` to the `subprocess.run` call.
**Warning signs:** Build shows "Compiled successfully" in stdout but subprocess never returns; timeout after 120s.

### Pitfall 4: error.tsx missing `"use client"` — build failure
**What goes wrong:** `next build` fails with "error.tsx must be a Client Component".
**Why it happens:** React error boundaries (which error.tsx implements) must be client components to use React lifecycle methods.
**How to avoid:** Build agent system prompt must include the explicit rule: "error.tsx MUST start with `'use client'` — it is a React error boundary and must be a Client Component".
**Warning signs:** Build fails with message "error.tsx is missing the `'use client'` directive".

### Pitfall 5: Static analysis gate scans error.tsx and finds `"use client"` incorrectly
**What goes wrong:** The `no_use_client_in_layout` check matches `error.tsx` files by mistake.
**Why it happens:** Overly broad file scan or misunderstanding that "use client" is required in error.tsx.
**How to avoid:** The gate checks ONLY `src/app/layout.tsx` and `src/app/page.tsx` — not `error.tsx`, not nested pages, not components. Scope is exactly two files.
**Warning signs:** Gate fails on a well-formed project because it's checking wrong files.

### Pitfall 6: npm hallucination — installing non-existent packages
**What goes wrong:** Build agent generates code importing packages that don't exist on npm; `npm install` fails or installs a squatted package.
**Why it happens:** LLMs hallucinate plausible-sounding npm package names.
**How to avoid:** The Phase 2b executor must intercept any `npm install` command the agent wants to run and pre-validate packages via `validate_npm_packages()` before execution. This is architecturally enforced, not just instructed in the prompt.
**Warning signs:** `npm install` completes but `npm run build` fails with "Module not found".

### Pitfall 7: Agent escapes project sandbox via Bash `cwd`
**What goes wrong:** Build agent runs shell commands in the pipeline root directory instead of the generated project.
**Why it happens:** Claude Agent SDK `cwd` sets the working directory for Bash commands; if not set correctly, the agent can traverse upward.
**How to avoid:** `ClaudeAgentOptions(cwd=project_dir)` where `project_dir` is the resolved absolute path of the generated project (not the pipeline root). The `PhaseContext.project_dir` is already validated and resolved.
**Warning signs:** Agent creates files outside `{project_dir}/` or modifies pipeline Python files.

### Pitfall 8: `subprocess.run` timeout with `capture_output=True` — is it safe?
**What goes wrong:** Pipe deadlock if child process generates enormous output.
**Why it happens:** `stdout=PIPE, stderr=PIPE` can deadlock if buffer fills; however `subprocess.run` uses `communicate()` internally which avoids deadlock.
**How to avoid:** `subprocess.run` with `capture_output=True` is safe for use here (uses `communicate()` under the hood). `timeout=120` is sufficient. `next build` output fits comfortably in pipe buffers.
**Warning signs:** Not a real risk with `subprocess.run`; only arises with `Popen` + manual reads.

## Code Examples

Verified patterns from official sources:

### create-next-app Deterministic Scaffold Command
```bash
# Source: https://nextjs.org/docs/app/api-reference/cli/create-next-app (version 16.2.1, 2026-03-03)
npx create-next-app@latest my-app \
  --typescript \
  --tailwind \
  --app \
  --src-dir \
  --disable-git \
  --use-npm \
  --yes
```

### Build Gate subprocess Call (Python)
```python
# Source: Python docs + CONTEXT.md locked decision
import subprocess
import os
from datetime import datetime, timezone

result = subprocess.run(
    ["npm", "run", "build"],
    cwd=str(project_dir),
    capture_output=True,
    text=True,
    timeout=120,
    env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1"},
)
passed = result.returncode == 0
issues = [result.stderr] if not passed and result.stderr else []
```

### tsc --noEmit Gate subprocess Call (Python)
```python
# Source: https://nextjs.org/docs/app/api-reference/config/typescript (official docs)
# NOTE: Run AFTER npm run build to ensure next-env.d.ts exists
result = subprocess.run(
    ["npx", "tsc", "--noEmit"],
    cwd=str(project_dir),
    capture_output=True,
    text=True,
    timeout=120,
)
passed = result.returncode == 0
```

### GateResult Construction for Build Gate
```python
# Source: GateResult dataclass (gate_result.py) + gate_policy.py patterns
from datetime import datetime, timezone
from tools.gates.gate_result import GateResult

def make_gate_result(passed: bool, issues: list[str], gate_type: str, phase_id: str) -> GateResult:
    return GateResult(
        gate_type=gate_type,
        phase_id=phase_id,
        passed=passed,
        status="PASS" if passed else "BLOCKED",
        severity="INFO" if passed else "BLOCK",
        confidence=1.0 if passed else 0.0,
        checked_at=datetime.now(timezone.utc).isoformat(),
        issues=issues,
    )
```

### Tailwind v4 postcss.config.mjs
```javascript
// Source: https://tailwindcss.com/docs/guides/nextjs (official Tailwind v4 docs)
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
export default config;
```

### next.config.ts TypeScript Format
```typescript
// Source: https://nextjs.org/docs/app/api-reference/config/next-config-js (official docs)
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactStrictMode: true,
}

export default nextConfig
```

### error.tsx (Route Error Boundary)
```typescript
// Source: https://nextjs.org/docs/app/getting-started/error-handling (official docs, 2026-03-20)
// MUST have "use client" — React error boundaries must be client components
'use client'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-4">
      <h2 className="text-xl font-bold mb-4">Something went wrong</h2>
      <button
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        onClick={() => reset()}
      >
        Try again
      </button>
    </div>
  )
}
```

### not-found.tsx (Route 404)
```typescript
// Source: https://nextjs.org/docs/app/api-reference/file-conventions/not-found (official docs)
// Server component — NO "use client" directive
export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-4">
      <h2 className="text-xl font-bold mb-4">404 - Page Not Found</h2>
      <p className="text-gray-500">The resource you requested does not exist.</p>
    </div>
  )
}
```

### Mobile-First Tailwind Responsive Pattern
```typescript
// Source: Tailwind CSS v4 docs — mobile-first breakpoints
// Base styles = mobile; md: = tablet (≥768px); lg: = desktop (≥1024px)
export default function HeroSection() {
  return (
    <section className="px-4 py-8 md:px-8 md:py-16 lg:px-16 lg:py-24">
      <h1 className="text-2xl font-bold md:text-4xl lg:text-5xl">
        App Title
      </h1>
      <div className="grid grid-cols-1 gap-4 mt-8 md:grid-cols-2 lg:grid-cols-3">
        {/* cards */}
      </div>
    </section>
  )
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `--no-git` flag | `--disable-git` flag | create-next-app CLI refactor | Old flag causes interactive prompt or error |
| `tailwind.config.js` + `@tailwind` directives | No config file + `@import "tailwindcss"` | Tailwind v4 (2024) | Simpler setup; no purge config needed |
| `tailwindcss` in PostCSS plugins | `@tailwindcss/postcss` in PostCSS plugins | Tailwind v4 (2024) | Breaking change in PostCSS integration |
| `reset()` in error.tsx | `unstable_retry()` in error.tsx (Next.js 16) | Next.js 16 | CONTEXT.md locked decision doesn't specify; use `reset` for broader compat |
| `next build` runs full type check | `next build` runs type check; `tsc --noEmit` for CI | Always separate | `next build` type errors = fail; `tsc --noEmit` = standalone check |

**Deprecated/outdated:**
- `tailwind.config.js`: No longer needed for Tailwind v4; create-next-app with `--tailwind` already configures v4 correctly.
- `@tailwind base; @tailwind components; @tailwind utilities` in CSS: Replaced by `@import "tailwindcss"` in Tailwind v4.
- `--no-git` flag: Non-existent in current create-next-app; replaced by `--disable-git`.

## Open Questions

1. **`unstable_retry` vs `reset` in error.tsx prop name**
   - What we know: Official Next.js docs (version 16.2.1) show `unstable_retry` as the prop name
   - What's unclear: Is `reset` still accepted (backward compat)? Some examples still show `reset`.
   - Recommendation: Use `reset` in generated code since it is more broadly documented and stable; the build agent system prompt can specify either form.

2. **create-next-app with `--yes` flag: exactly what defaults are selected?**
   - What we know: `--yes` uses previous preferences or defaults; TypeScript and Tailwind are "defaults"
   - What's unclear: Does `--yes` set ESLint, import alias, React compiler, AGENTS.md? These may produce prompts or extra config files.
   - Recommendation: Explicitly pass all desired flags (`--typescript --tailwind --app --src-dir --disable-git --use-npm --no-eslint`) rather than relying on `--yes` for non-default behavior. Avoids unexpected files like AGENTS.md or .eslintrc.

3. **`validate_npm_packages()` placement in Phase 2b**
   - What we know: CONTEXT.md says "reuse in Phase 2b for any additional dependencies the build agent wants to install"
   - What's unclear: How does the executor intercept the agent's npm install commands before the Bash tool executes them?
   - Recommendation: Use a pre-validation step in the Phase 2b executor prompt that instructs the agent to call a Python-defined tool (or via a two-step: agent writes a package list file, executor validates, then agent installs). Alternatively, document the design as "agent proposes packages in a JSON file; executor validates; executor runs npm install." This is cleaner than intercepting Bash tool calls.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` testpaths = ["tests"]) |
| Quick run command | `uv run pytest tests/test_phase_2a_executor.py tests/test_phase_2b_executor.py tests/test_build_gate.py tests/test_static_analysis_gate.py -x -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BILD-01 | Phase 2a subprocess calls create-next-app with correct flags | unit | `uv run pytest tests/test_phase_2a_executor.py::test_scaffold_subprocess_flags -x` | ❌ Wave 0 |
| BILD-01 | Phase 2a executor self-registers in registry | unit | `uv run pytest tests/test_phase_2a_executor.py::test_self_registration -x` | ❌ Wave 0 |
| BILD-02 | Phase 2b executor calls run_build_agent with correct args | unit | `uv run pytest tests/test_phase_2b_executor.py::test_agent_called -x` | ❌ Wave 0 |
| BILD-02 | Phase 2b executor injects PRD and screen-spec content in prompt | unit | `uv run pytest tests/test_phase_2b_executor.py::test_prompt_contains_prd -x` | ❌ Wave 0 |
| BILD-03 | Build gate passes on exit code 0, fails on non-zero | unit | `uv run pytest tests/test_build_gate.py::test_build_gate_pass_fail -x` | ❌ Wave 0 |
| BILD-04 | tsc gate passes on exit code 0, fails on non-zero | unit | `uv run pytest tests/test_build_gate.py::test_tsc_gate_pass_fail -x` | ❌ Wave 0 |
| BILD-07 | validate_npm_packages called before npm install | unit | `uv run pytest tests/test_phase_2b_executor.py::test_npm_validation -x` | ❌ Wave 0 |
| GATE-01 | Build gate returns GateResult with correct fields | unit | `uv run pytest tests/test_build_gate.py::test_gate_result_structure -x` | ❌ Wave 0 |
| GATE-05 | Static analysis gate detects "use client" in layout.tsx | unit | `uv run pytest tests/test_static_analysis_gate.py::test_use_client_in_layout -x` | ❌ Wave 0 |
| GATE-05 | Static analysis gate passes when "use client" only in error.tsx | unit | `uv run pytest tests/test_static_analysis_gate.py::test_use_client_in_error_is_ok -x` | ❌ Wave 0 |
| GATE-06 | Static analysis gate detects NEXT_PUBLIC_ secret patterns | unit | `uv run pytest tests/test_static_analysis_gate.py::test_next_public_secret -x` | ❌ Wave 0 |
| GATE-06 | Static analysis gate passes on NEXT_PUBLIC_ non-secret names | unit | `uv run pytest tests/test_static_analysis_gate.py::test_next_public_safe -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_phase_2a_executor.py tests/test_phase_2b_executor.py tests/test_build_gate.py tests/test_static_analysis_gate.py -x -q`
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase_2a_executor.py` — covers BILD-01
- [ ] `tests/test_phase_2b_executor.py` — covers BILD-02, BILD-07
- [ ] `tests/test_build_gate.py` — covers BILD-03, BILD-04, GATE-01
- [ ] `tests/test_static_analysis_gate.py` — covers GATE-05, GATE-06
- [ ] `tools/phase_executors/build_agent_runner.py` — new module (parallel to spec_agent_runner.py)
- [ ] `tools/phase_executors/phase_2a_executor.py` — replaces Phase2aStubExecutor
- [ ] `tools/phase_executors/phase_2b_executor.py` — replaces Phase2bStubExecutor
- [ ] `tools/gates/build_gate.py` — new gate executor
- [ ] `tools/gates/static_analysis_gate.py` — new gate executor
- [ ] `agents/definitions.py` — update BUILD_AGENT with real system prompt

## Sources

### Primary (HIGH confidence)
- https://nextjs.org/docs/app/api-reference/cli/create-next-app (version 16.2.1, 2026-03-03) — exact flag list including `--disable-git`
- https://tailwindcss.com/docs/guides/nextjs — Tailwind v4 Next.js setup: `@tailwindcss/postcss`, `postcss.config.mjs`, no config.js
- https://nextjs.org/docs/app/getting-started/error-handling (version 16.2.1, 2026-03-20) — error.tsx must be `"use client"`, not-found.tsx is server component
- https://nextjs.org/docs/app/api-reference/config/next-config-js/typescript — `ignoreBuildErrors` flag, `tsconfigPath` option
- Codebase: `tools/phase_executors/spec_agent_runner.py` — confirmed `ClaudeAgentOptions` interface
- Codebase: `tools/gates/gate_result.py` — confirmed `GateResult` frozen dataclass structure
- Codebase: `tools/phase_executors/phase_1a_executor.py` — confirmed `validate_npm_packages()` pattern

### Secondary (MEDIUM confidence)
- Multiple community sources confirming Tailwind v4 setup — `@tailwindcss/postcss`, single `@import "tailwindcss"` directive
- GitHub issue #70758 confirming `NEXT_TELEMETRY_DISABLED=1` for `next build` hang prevention
- https://nextjs.org/docs/app/api-reference/config/next-config-js — `NextConfig` import type confirmed
- Python subprocess docs confirming `subprocess.run` with `capture_output=True` uses `communicate()` internally (no deadlock)

### Tertiary (LOW confidence)
- Community sources on `tsc --noEmit` needing `next-env.d.ts` — verified logically from official docs but not a single definitive source

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — create-next-app flags verified against current official docs (v16.2.1)
- Architecture: HIGH — code patterns derived from existing codebase (spec_agent_runner.py, gate_result.py)
- Pitfalls: HIGH for `--disable-git` and `"use client"` in error.tsx (official docs); MEDIUM for telemetry hang (GitHub issues)
- Gate implementation: HIGH — direct pattern extension of existing GateResult/GatePolicy infrastructure

**Research date:** 2026-03-21
**Valid until:** 2026-06-21 (stable APIs; Next.js 16 released but no breaking changes to App Router conventions)
