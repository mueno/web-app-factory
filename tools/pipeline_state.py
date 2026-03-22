"""
パイプライン状態管理 — git-tracked な状態・活動ログ・引き継ぎ書を管理する。

ファイル配置 (git-tracked):
    {project_dir}/
      docs/pipeline/
        runs/{run_id}/
          state.json       ← 機械可読な状態
          handoff.md        ← 人間可読な引き継ぎ書
        activity-log.jsonl  ← 全 run 横断の構造化ログ
"""

import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# Phase の正規順序（再開ポイント算出に使用）
PHASE_ORDER = ["1a", "1b", "2a", "2b", "3"]

PHASE_LABELS = {
    "1a": "Idea Validation",
    "1b": "Spec & Design",
    "2a": "Scaffold",
    "2b": "Build",
    "3": "Ship",
}


@dataclass
class PhaseRecord:
    phase_id: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    status: str = "pending"  # pending | running | completed | skipped | failed
    artifacts: list = field(default_factory=list)
    notes: str = ""


@dataclass
class PipelineState:
    run_id: str
    app_name: str
    project_dir: str
    idea: str
    started_at: str
    current_phase: Optional[str] = None
    phases: dict = field(default_factory=dict)
    status: str = "running"  # running | interrupted | completed | failed

    def get_factory_run_id(self) -> Optional[str]:
        # This method was added but its implementation was not provided.
        # Returning None for now, or it could be implemented based on context.
        return None


_PIPELINE_STATE_FIELD_NAMES = {item.name for item in fields(PipelineState)}


def _coerce_pipeline_state(data: dict) -> PipelineState:
    """Construct PipelineState while ignoring forward-compatible extra keys."""
    normalized = {
        key: value
        for key, value in data.items()
        if key in _PIPELINE_STATE_FIELD_NAMES
    }
    return PipelineState(**normalized)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pipeline_dir(project_dir: str) -> Path:
    return Path(project_dir) / "docs" / "pipeline"


def _run_dir(project_dir: str, run_id: str) -> Path:
    return _pipeline_dir(project_dir) / "runs" / run_id


def _state_path(project_dir: str, run_id: str) -> Path:
    return _run_dir(project_dir, run_id) / "state.json"


def _handoff_path(project_dir: str, run_id: str) -> Path:
    return _run_dir(project_dir, run_id) / "handoff.md"


def _activity_log_path(project_dir: str) -> Path:
    return _pipeline_dir(project_dir) / "activity-log.jsonl"


def _safe_slug(name: str) -> str:
    return "".join(c if (c.isascii() and c.isalnum()) or c in "-_" else "-" for c in name[:30]).strip("-").lower() or "app"


def _write_state(project_dir: str, run_id: str, state: PipelineState) -> None:
    path = _state_path(project_dir, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n")


def _append_activity_log(project_dir: str, entry: dict) -> None:
    path = _activity_log_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _render_handoff(state: PipelineState) -> str:
    """人間可読な引き継ぎ書を生成。"""
    lines = [
        f"# Pipeline Handoff: {state.app_name}",
        "",
        f"- **Run ID**: `{state.run_id}`",
        f"- **Status**: {state.status}",
        f"- **Started**: {state.started_at}",
        f"- **Current Phase**: {state.current_phase or '(none)'}",
        f"- **Project Dir**: `{state.project_dir}`",
        "",
        "## Idea",
        "",
        state.idea[:500],
        "",
        "## Phase Progress",
        "",
        "| Phase | Status | Started | Completed | Artifacts |",
        "|-------|--------|---------|-----------|-----------|",
    ]
    for pid in PHASE_ORDER:
        pr = state.phases.get(pid)
        if pr is None:
            label = PHASE_LABELS.get(pid, pid)
            lines.append(f"| {pid}: {label} | pending | - | - | - |")
            continue
        label = PHASE_LABELS.get(pid, pid)
        started = pr.get("started_at", "-") or "-"
        completed = pr.get("completed_at", "-") or "-"
        artifacts = ", ".join(pr.get("artifacts", [])) or "-"
        status = pr.get("status", "pending")
        lines.append(f"| {pid}: {label} | {status} | {started} | {completed} | {artifacts} |")

    notes_section = []
    for pid in PHASE_ORDER:
        pr = state.phases.get(pid)
        if pr and pr.get("notes"):
            label = PHASE_LABELS.get(pid, pid)
            notes_section.append(f"### Phase {pid}: {label}")
            notes_section.append("")
            notes_section.append(pr["notes"])
            notes_section.append("")

    if notes_section:
        lines.append("")
        lines.append("## Notes")
        lines.append("")
        lines.extend(notes_section)

    if state.status == "interrupted":
        lines.append("")
        lines.append("## Resume Instructions")
        lines.append("")
        next_phase = get_resume_phase(state.run_id, state.project_dir)
        lines.append(f"Pipeline was interrupted. Resume from **Phase {next_phase}**:")
        lines.append(f"```bash")
        lines.append(f"python factory.py --resume {state.run_id} --project-dir {state.project_dir}")
        lines.append(f"```")

    lines.append("")
    return "\n".join(lines)


def _write_handoff(project_dir: str, run_id: str, state: PipelineState) -> None:
    path = _handoff_path(project_dir, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_handoff(state))


def _git_commit(project_dir: str, message: str) -> bool:
    """docs/pipeline/ 配下をコミット。失敗しても例外を投げない。"""
    try:
        pipeline_dir = str(_pipeline_dir(project_dir))
        add_result = subprocess.run(
            ["git", "add", pipeline_dir],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if add_result.returncode != 0:
            stderr = (add_result.stderr or "").strip()
            print(f"warning: git add failed (non-fatal): {stderr}", file=sys.stderr)
            return False

        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Nothing staged
            return False
        if result.returncode != 1:
            stderr = (result.stderr or "").strip()
            print(f"warning: git diff --cached failed (non-fatal): {stderr}", file=sys.stderr)
            return False

        commit_result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if commit_result.returncode != 0:
            stderr = (commit_result.stderr or "").strip()
            print(f"warning: git commit failed (non-fatal): {stderr}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"warning: git commit failed (non-fatal): {e}", file=sys.stderr)
        return False


# ─── Public API ───────────────────────────────────


def init_run(app_name: str, project_dir: str, idea: str) -> PipelineState:
    """新しい run を初期化。state.json + handoff.md + activity-log を作成し git commit。"""
    now = _now_iso()
    slug = _safe_slug(app_name)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + f"-{slug}"

    phases = {}
    for pid in PHASE_ORDER:
        phases[pid] = asdict(PhaseRecord(phase_id=pid))

    state = PipelineState(
        run_id=run_id,
        app_name=app_name,
        project_dir=project_dir,
        idea=idea[:2000],
        started_at=now,
        phases=phases,
    )

    _write_state(project_dir, run_id, state)
    _write_handoff(project_dir, run_id, state)
    _append_activity_log(project_dir, {
        "timestamp": now,
        "run_id": run_id,
        "event": "run_init",
        "app_name": app_name,
    })

    _git_commit(project_dir, f"pipeline({run_id}): init run for {app_name}")

    print(f"Pipeline run initialized: {run_id}", file=sys.stderr)
    return state


def phase_start(run_id: str, phase_id: str, project_dir: str) -> None:
    """フェーズ開始を記録。"""
    state = load_state(run_id, project_dir)
    if state is None:
        print(f"warning: State not found for {run_id}", file=sys.stderr)
        return

    now = _now_iso()
    if phase_id not in state.phases:
        state.phases[phase_id] = asdict(PhaseRecord(phase_id=phase_id))

    state.phases[phase_id]["started_at"] = now
    state.phases[phase_id]["status"] = "running"
    state.current_phase = phase_id
    state.status = "running"

    _write_state(project_dir, run_id, state)
    _write_handoff(project_dir, run_id, state)
    _append_activity_log(project_dir, {
        "timestamp": now,
        "run_id": run_id,
        "event": "phase_start",
        "phase": phase_id,
    })


def phase_complete(
    run_id: str,
    phase_id: str,
    project_dir: str,
    artifacts: Optional[List[str]] = None,
    notes: str = "",
) -> None:
    """フェーズ完了を記録し、handoff を更新、git commit。"""
    state = load_state(run_id, project_dir)
    if state is None:
        print(f"warning: State not found for {run_id}", file=sys.stderr)
        return

    now = _now_iso()
    if phase_id not in state.phases:
        state.phases[phase_id] = asdict(PhaseRecord(phase_id=phase_id))

    state.phases[phase_id]["completed_at"] = now
    state.phases[phase_id]["status"] = "completed"
    state.phases[phase_id]["artifacts"] = artifacts or []
    state.phases[phase_id]["notes"] = notes

    _write_state(project_dir, run_id, state)
    _write_handoff(project_dir, run_id, state)
    _append_activity_log(project_dir, {
        "timestamp": now,
        "run_id": run_id,
        "event": "phase_complete",
        "phase": phase_id,
        "artifacts": artifacts or [],
    })

    label = PHASE_LABELS.get(phase_id, phase_id)
    _git_commit(
        project_dir,
        f"pipeline({run_id}): Phase {phase_id} ({label}) complete\n\n{notes[:200]}",
    )


def mark_interrupted(run_id: str, project_dir: str) -> None:
    """中断を記録。SIGTERM / KeyboardInterrupt 時に呼ぶ。"""
    state = load_state(run_id, project_dir)
    if state is None:
        return

    now = _now_iso()
    state.status = "interrupted"

    # 実行中のフェーズがあれば中断状態にする
    if state.current_phase and state.current_phase in state.phases:
        pr = state.phases[state.current_phase]
        if pr.get("status") == "running":
            pr["status"] = "interrupted"

    _write_state(project_dir, run_id, state)
    _write_handoff(project_dir, run_id, state)
    _append_activity_log(project_dir, {
        "timestamp": now,
        "run_id": run_id,
        "event": "interrupted",
        "current_phase": state.current_phase,
    })

    _git_commit(project_dir, f"pipeline({run_id}): interrupted at Phase {state.current_phase}")
    print(f"Pipeline state saved (interrupted at Phase {state.current_phase})", file=sys.stderr)


def mark_completed(run_id: str, project_dir: str) -> None:
    """パイプライン正常完了を記録。"""
    state = load_state(run_id, project_dir)
    if state is None:
        return

    now = _now_iso()
    state.status = "completed"

    _write_state(project_dir, run_id, state)
    _write_handoff(project_dir, run_id, state)
    _append_activity_log(project_dir, {
        "timestamp": now,
        "run_id": run_id,
        "event": "completed",
    })

    _git_commit(project_dir, f"pipeline({run_id}): all phases completed")


def mark_failed(run_id: str, project_dir: str, error: str) -> None:
    """パイプライン失敗を記録。"""
    state = load_state(run_id, project_dir)
    if state is None:
        return

    now = _now_iso()
    state.status = "failed"
    failure_note = f"FAILED: {error[:500]}"

    # 実行中フェーズを failed に遷移させる（running のまま残さない）。
    failed_any_phase = False
    if state.current_phase and state.current_phase in state.phases:
        phase_record = state.phases[state.current_phase]
        if phase_record.get("status") in {"pending", "running", "interrupted"}:
            phase_record["status"] = "failed"
            if not phase_record.get("completed_at"):
                phase_record["completed_at"] = now
            notes = (phase_record.get("notes") or "").strip()
            phase_record["notes"] = f"{notes}\n{failure_note}".strip() if notes else failure_note
            failed_any_phase = True

    if not failed_any_phase:
        for phase_record in state.phases.values():
            if phase_record.get("status") == "running":
                phase_record["status"] = "failed"
                if not phase_record.get("completed_at"):
                    phase_record["completed_at"] = now
                notes = (phase_record.get("notes") or "").strip()
                phase_record["notes"] = f"{notes}\n{failure_note}".strip() if notes else failure_note
                failed_any_phase = True

    _write_state(project_dir, run_id, state)
    _write_handoff(project_dir, run_id, state)
    _append_activity_log(project_dir, {
        "timestamp": now,
        "run_id": run_id,
        "event": "failed",
        "error": error[:500],
    })

    _git_commit(project_dir, f"pipeline({run_id}): failed — {error[:80]}")


def load_state(run_id: str, project_dir: str) -> Optional[PipelineState]:
    """state.json を読み込み PipelineState を返す。"""
    path = _state_path(project_dir, run_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return None
        return _coerce_pipeline_state(data)
    except Exception as e:
        print(f"warning: Failed to load state {path}: {e}", file=sys.stderr)
        return None


def find_latest_run(project_dir: str) -> Optional[PipelineState]:
    """プロジェクト配下の最新 run を探す。"""
    runs_dir = _pipeline_dir(project_dir) / "runs"
    if not runs_dir.exists():
        return None

    run_dirs = sorted(runs_dir.iterdir(), reverse=True)
    for d in run_dirs:
        state_file = d / "state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                if not isinstance(data, dict):
                    continue
                return _coerce_pipeline_state(data)
            except Exception:
                continue
    return None


def get_resume_phase(run_id: str, project_dir: str) -> Optional[str]:
    """中断/最後の完了 phase から次の phase_id を返す。全完了なら None。"""
    state = load_state(run_id, project_dir)
    if state is None:
        return PHASE_ORDER[0]

    terminal_statuses = {"completed", "skipped"}

    # Fail-closed: 最初に未完了のフェーズから再開する。
    # 途中フェーズが pending のまま後続が completed でも、ギャップを優先して埋める。
    for pid in PHASE_ORDER:
        phase_record = state.phases.get(pid, {})
        if phase_record.get("status") not in terminal_statuses:
            return pid

    # 全フェーズ完了済み
    return None


def reset_phase_for_resume(run_id: str, phase_id: str, project_dir: str) -> None:
    """Reset a failed phase to pending so the executor can re-run it cleanly.

    Only resets phases with status == "failed". Completed phases are left
    unchanged. Strips accumulated "FAILED: ..." lines from notes while
    preserving any other notes. Also resets pipeline-level status from
    "failed" to "running" when the phase is reset.
    """
    state = load_state(run_id, project_dir)
    if state is None:
        return

    if phase_id not in state.phases:
        return

    phase_record = state.phases[phase_id]
    if phase_record.get("status") != "failed":
        return

    # Reset phase record fields
    phase_record["status"] = "pending"
    phase_record["error"] = None
    phase_record["completed_at"] = None

    # Strip FAILED: lines from notes, preserve everything else
    raw_notes = phase_record.get("notes") or ""
    cleaned_lines = [line for line in raw_notes.split("\n") if not line.startswith("FAILED: ")]
    phase_record["notes"] = "\n".join(cleaned_lines).strip()

    # Reset pipeline-level status
    if state.status == "failed":
        state.status = "running"

    _write_state(project_dir, run_id, state)
    _write_handoff(project_dir, run_id, state)

    now = _now_iso()
    _append_activity_log(project_dir, {
        "timestamp": now,
        "run_id": run_id,
        "event": "phase_reset_for_resume",
        "phase": phase_id,
    })


def build_resume_note(run_id: str, project_dir: str) -> str:
    """orchestrator_prompt に注入する再開指示文を生成。"""
    state = load_state(run_id, project_dir)
    if state is None:
        return ""

    resume_phase = get_resume_phase(run_id, project_dir)
    completed = [
        pid for pid, pr in state.phases.items()
        if pr.get("status") == "completed"
    ]

    if not completed:
        return ""

    completed_labels = ", ".join(
        f"Phase {pid}" for pid in PHASE_ORDER if pid in completed
    )
    label = PHASE_LABELS.get(resume_phase, resume_phase) if resume_phase else "None"

    return (
        f"\n\nNote: Resuming run `{run_id}`."
        f"\nCompleted: {completed_labels}"
        f"\n**Start from Phase {resume_phase} ({label}).**"
        f"\nCompleted phase artifacts already exist in docs/. Do not regenerate them.\n"
    )
