"""Task overview widget for the MainScreen sidebar.

Optional panel that surfaces the current project's TaskMD state via the
`task` CLI (https://github.com/niclasedge/cc-task). Shown only when the
`task` binary is on PATH; otherwise the panel is omitted entirely.

Runs `task info --format json` as an async worker on mount, parses the
JSON output, and renders project name, status/phase counts, and the
next recommended task.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static


def task_cli_available() -> bool:
    """True if the `task` CLI from cc-task is installed on PATH."""
    return shutil.which("task") is not None


class TaskOverview(Vertical):
    DEFAULT_CLASSES = "block"
    DEFAULT_CSS = """
    TaskOverview {
        height: auto;
        padding: 0 1 0 1;

        .-info { color: $text-secondary; text-style: italic; }
        .project { color: $text; text-style: bold; }
        .group { color: $text-secondary; }
        .stats { color: $text-secondary; }
        .phase-row { color: $text-secondary; }
        .next-label { color: $text-secondary; margin-top: 1; }
        .next-task { color: $text; }
    }
    """

    data: reactive[dict | None] = reactive(None, recompose=True)
    loading: reactive[bool] = reactive(True, recompose=True)

    def __init__(self, project_path: Path, id: str | None = None) -> None:
        super().__init__(id=id)
        self.project_path = project_path

    def compose(self) -> ComposeResult:
        if self.loading:
            yield Static("Loading…", classes="-info")
            return
        if self.data is None:
            yield Static(
                "No TaskMD project for this directory.", classes="-info"
            )
            return

        project = self.data.get("project") or {}
        stats = self.data.get("stats") or {}
        by_status = stats.get("by_status") or {}
        by_phase = stats.get("by_phase") or {}
        recommended = self.data.get("recommended")

        yield Static(
            project.get("name") or project.get("id") or "—",
            classes="project",
        )
        if group := project.get("group_name"):
            yield Static(group, classes="group")

        total = stats.get("total", 0)
        completed = by_status.get("completed", 0)
        pending = by_status.get("pending", 0)
        in_progress = by_status.get("in-progress", 0)
        blocked = stats.get("blocked_count", 0)

        bits = [f"{completed}/{total} done"]
        if in_progress:
            bits.append(f"{in_progress} in progress")
        if pending:
            bits.append(f"{pending} pending")
        if blocked:
            bits.append(f"{blocked} blocked")
        yield Static("  ·  ".join(bits), classes="stats")

        for phase_id, count in by_phase.items():
            slug = phase_id.split(":", 1)[-1]
            yield Static(f"  {slug}: {count}", classes="phase-row")

        if recommended:
            yield Static("next:", classes="next-label")
            task_id = recommended.get("task_id", "")
            title = recommended.get("title", "")
            yield Static(f"{task_id}  {title}", classes="next-task")

    def on_mount(self) -> None:
        self._load_task_info()

    @work(exclusive=True)
    async def _load_task_info(self) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "task",
                "info",
                "--format",
                "json",
                cwd=str(self.project_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
        except (OSError, FileNotFoundError):
            self.loading = False
            return

        if proc.returncode != 0:
            self.loading = False
            return

        try:
            self.data = json.loads(stdout.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.data = None
        finally:
            self.loading = False
