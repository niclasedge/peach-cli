"""Startup picker: shown as the first screen when peach launches without
an explicit session flag.

Groups recent sessions by project_path. Enter resumes the highlighted
session; `n` starts a new session in the current cwd; `d` deletes the
highlighted session from the DB (after confirmation); `esc` quits.

Result: "new" (str) to start a fresh session, or a Session dict to resume.
"""

from __future__ import annotations

from typing import Any

from textual import getters, on, widgets, containers, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from peach.db import DB, Session
from peach.screens.confirm_modal import ConfirmModal

EMPTY_MESSAGE = "No recent sessions. Press `n` or `enter` to start one."
ACTIVE_MARKER = "● "


class StartupPickerScreen(Screen[Any]):
    """First screen on peach launch — pick new or a recent session."""

    BINDINGS = [
        Binding("enter", "select", "Select"),
        Binding("n", "new", "New"),
        Binding("d", "delete", "Delete"),
        Binding("escape", "quit", "Quit"),
    ]

    tree = getters.query_one("#sessions-tree", widgets.Tree)

    def __init__(self, cwd: str, db: DB | None = None) -> None:
        super().__init__()
        self.cwd = cwd
        self._db = db or DB()

    def compose(self) -> ComposeResult:
        with containers.VerticalGroup(id="picker-container"):
            yield widgets.Static(
                f"🍑 [b]New Session in[/b] {self.cwd}", id="new-session-row"
            )
            yield widgets.Static("Recent sessions", classes="section-header")
            yield widgets.Tree[Session | str](
                "Sessions", id="sessions-tree"
            )
            yield widgets.Footer()

    async def on_mount(self) -> None:
        await self._db.create()
        await self._reload_tree()

    def _active_db_ids(self) -> set[int]:
        """DB ids of sessions currently tracked in memory."""
        tracker = getattr(self.app, "session_tracker", None)
        if tracker is None:
            return set()
        return {
            s.db_id for s in tracker.ordered_sessions if s.db_id is not None
        }

    async def _reload_tree(self) -> None:
        tree = self.tree
        tree.clear()
        tree.root.expand()
        grouped = await self._db.sessions_recent(
            limit=50, group_by_project=True
        )
        if not grouped:
            tree.root.add_leaf(EMPTY_MESSAGE)
            return

        active_ids = self._active_db_ids()
        for project_path, sessions in sorted(grouped.items()):
            label = project_path or "(no project)"
            project_node = tree.root.add(label, expand=True)
            for session in sessions:
                title = session.get("title") or "(untitled)"
                last_used = session.get("last_used") or ""
                prefix = ACTIVE_MARKER if session.get("id") in active_ids else ""
                leaf_label = f"{prefix}{title} — {last_used}"
                project_node.add_leaf(leaf_label, data=session)

    def _cursor_project_path(self) -> str:
        """Project path of the highlighted node. Falls back to cwd."""
        node = self.tree.cursor_node
        if node is None:
            return self.cwd
        data = node.data
        if isinstance(data, dict):
            return data.get("project_path") or self.cwd
        if node.parent is self.tree.root:
            label = str(node.label)
            if label and label != "(no project)":
                return label
        return self.cwd

    def action_new(self) -> None:
        self.dismiss({"__new__": True, "project_path": self._cursor_project_path()})

    def action_quit(self) -> None:
        self.app.exit()

    async def action_select(self) -> None:
        node = self.tree.cursor_node
        if node is None or node.data is None:
            self.dismiss("new")
            return
        self.dismiss(node.data)

    def action_delete(self) -> None:
        node = self.tree.cursor_node
        if node is None or node.data is None or isinstance(node.data, str):
            return
        session: Session = node.data
        session_id = session.get("id")
        if session_id is None:
            return

        if session_id in self._active_db_ids():
            self.app.notify(
                "Cannot delete an active session.",
                severity="warning",
            )
            return

        title = session.get("title") or "(untitled)"

        def on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._delete_and_reload(session_id)

        self.app.push_screen(
            ConfirmModal(f"Delete session '{title}'? This cannot be undone."),
            on_confirm,
        )

    @work
    async def _delete_and_reload(self, session_id: int) -> None:
        ok = await self._db.session_delete(session_id)
        if not ok:
            self.app.notify("Delete failed.", severity="error")
            return
        await self._reload_tree()

    @on(widgets.Tree.NodeSelected)
    async def on_node_selected(
        self, event: widgets.Tree.NodeSelected[Session | str]
    ) -> None:
        if event.node.data is None:
            return
        self.dismiss(event.node.data)
