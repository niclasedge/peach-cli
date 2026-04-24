"""Task overview widget for the MainScreen sidebar.

Optional panel that surfaces the current project's TaskMD state via the
`task` CLI (https://github.com/niclasedge/cc-task). Shown only when the
`task` binary is on PATH; otherwise the panel is omitted entirely.

Runs `task info --format json` as an async worker on mount and renders
the same sections as `task info`: project header, stats, then Termine /
In Arbeit / Waiting / Next task lists.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.content import Content
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static


def task_cli_available() -> bool:
    """True if the `task` CLI from cc-task is installed on PATH."""
    return shutil.which("task") is not None


_PRIO_CHAR = {"high": "H", "medium": "M", "low": "L"}
_PRIO_COLOR = {
    "high": "$text-error",
    "medium": "$text-warning",
    "low": "$text-primary",
}
_STATUS_ORDER = ("in-progress", "in-review", "pending", "blocked", "cancelled")
_STATUS_LABEL = {
    "in-progress": "in progress",
    "in-review": "in review",
    "pending": "pending",
    "blocked": "blocked",
    "cancelled": "cancelled",
}


def _task_row(task: dict) -> Content:
    """One-line task row: `id  P  title` with colored prio letter."""
    task_id = task.get("id") or task.get("task_id") or ""
    title = task.get("title", "")
    prio = task.get("priority") or ""
    prio_char = _PRIO_CHAR.get(prio, " ")
    prio_color = _PRIO_COLOR.get(prio, "$text-secondary")
    return Content.from_markup(
        f"[$text-secondary]$task_id[/]  [{prio_color}]$prio[/]  $title",
        task_id=task_id,
        prio=prio_char,
        title=title,
    )


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
        .section-header {
            color: $text-secondary;
            text-style: bold;
            margin-top: 1;
        }
        .section-empty { color: $text-secondary; text-style: italic; }
        .task-row { color: $text; }
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

        yield Static(
            project.get("name") or project.get("id") or "—",
            classes="project",
        )
        if group := project.get("group_name"):
            yield Static(group, classes="group")

        total = stats.get("total", 0)
        completed = by_status.get("completed", 0)
        bits = [f"{completed}/{total} done"]
        for key in _STATUS_ORDER:
            if n := by_status.get(key, 0):
                bits.append(f"{n} {_STATUS_LABEL[key]}")
        blocked_count = stats.get("blocked_count", 0)
        if blocked_count and not by_status.get("blocked"):
            bits.append(f"{blocked_count} blocked")
        yield Static("  ·  ".join(bits), classes="stats")

        for section_key, label in (
            ("termine", "Termine"),
            ("in_arbeit", "In Arbeit"),
            ("waiting", "Waiting"),
            ("next", "Next"),
        ):
            items = self.data.get(section_key) or []
            yield Static(f"{label} [{len(items)}]", classes="section-header")
            if not items:
                yield Static("(none)", classes="section-empty")
                continue
            for task in items:
                yield Static(_task_row(task), classes="task-row")

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
