"""Task overview widget for the MainScreen sidebar.

Optional panel that surfaces the current project's TaskMD state via the
`task` CLI (https://github.com/niclasedge/cc-task). Shown only when the
`task` binary is on PATH; otherwise the panel is omitted entirely.

Runs `task info --format json` as an async worker on mount and renders
the project header plus any non-empty Termine / In Arbeit / Waiting /
Next task lists. Empty sections are omitted.
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
        .section-header {
            color: $text-secondary;
            text-style: bold;
            margin-top: 1;
        }
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

        yield Static(
            project.get("name") or project.get("id") or "—",
            classes="project",
        )
        if group := project.get("group_name"):
            yield Static(group, classes="group")

        seen_ids: set[str] = set()
        for section_key, label in (
            ("termine", "Termine"),
            ("in_arbeit", "In Arbeit"),
            ("waiting", "Waiting"),
            ("next", "Next"),
        ):
            items = self.data.get(section_key) or []
            deduped = []
            for task in items:
                tid = task.get("id") or task.get("task_id")
                if tid and tid in seen_ids:
                    continue
                if tid:
                    seen_ids.add(tid)
                deduped.append(task)
            if not deduped:
                continue
            yield Static(f"{label} [{len(deduped)}]", classes="section-header")
            for task in deduped:
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
