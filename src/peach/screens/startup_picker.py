"""Startup picker: shown as the first screen when peach launches without
an explicit session flag.

Groups recent sessions by project_path. Enter resumes the highlighted
session; `n` starts a new session in the current cwd; `d` deletes the
highlighted session from the DB (after confirmation); `esc` quits.

Result: "new" (str) to start a fresh session, or a Session dict to resume.

Auto-refresh:
- Subscribes to `session_update_signal` → instant refresh on in-app
  rename / state change.
- `set_interval(10)` → picks up cross-process DB changes (e.g. another
  browser tab on the same `peach serve` instance deleted a session).
- Cursor position is preserved across reloads by re-selecting the leaf
  for the previously highlighted session id when it still exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual import getters, on, widgets, containers, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from peach.db import DB, Session
from peach.screens.confirm_modal import ConfirmModal
from peach.widgets.active_session_cards import ActiveSessionCards, filter_active
from peach.widgets.sessions_list import _fmt_timestamp

if TYPE_CHECKING:
    from peach.app import ToadApp
    from peach.session_tracker import SessionDetails

EMPTY_MESSAGE = "No recent sessions. Press `n` or `enter` to start one."
ACTIVE_MARKER = "● "
REFRESH_INTERVAL_SECONDS = 5.0


class StartupPickerScreen(Screen[Any]):
    """First screen on peach launch — pick new or a recent session."""

    BINDINGS = [
        Binding("enter", "select", "Select"),
        Binding("n", "new", "New"),
        Binding("d", "delete", "Delete"),
        Binding("escape", "quit", "Quit"),
    ]

    tree = getters.query_one("#sessions-tree", widgets.Tree)
    active_cards = getters.query_one("#active-session-cards", ActiveSessionCards)

    def __init__(self, cwd: str, db: DB | None = None) -> None:
        super().__init__()
        self.cwd = cwd
        self._db = db or DB()

    def compose(self) -> ComposeResult:
        with containers.VerticalGroup(id="picker-container"):
            yield widgets.Static(
                f"🍑 [b]New Session in[/b] {self.cwd}", id="new-session-row"
            )
            yield ActiveSessionCards(id="active-session-cards")
            yield widgets.Static("Recent sessions", classes="section-header")
            yield widgets.Tree[Session | str](
                "Sessions", id="sessions-tree"
            )
            yield widgets.Footer()

    async def on_mount(self) -> None:
        await self._db.create()
        await self._reload_tree()
        signal = getattr(self.app, "session_update_signal", None)
        if signal is not None:
            signal.subscribe(self, self._on_session_update_signal)
        self.set_interval(REFRESH_INTERVAL_SECONDS, self._reload_tree)

    async def _on_session_update_signal(
        self, update: "tuple[str, SessionDetails | None]"
    ) -> None:
        await self._reload_tree()

    def _active_db_ids(self) -> set[int]:
        """DB ids of sessions currently tracked in memory."""
        tracker = getattr(self.app, "session_tracker", None)
        if tracker is None:
            return set()
        return {
            s.db_id for s in tracker.ordered_sessions if s.db_id is not None
        }

    def _remembered_session_id(self) -> int | None:
        """DB id of the currently highlighted session leaf, if any."""
        node = self.tree.cursor_node
        if node is None or not isinstance(node.data, dict):
            return None
        return node.data.get("id")

    async def _reload_tree(self) -> None:
        tree = self.tree
        remembered = self._remembered_session_id()
        tree.clear()
        tree.root.expand()
        grouped = await self._db.sessions_recent(
            limit=50, group_by_project=True
        )
        flat: list[Session] = []
        for sessions in grouped.values():
            flat.extend(sessions)
        self.active_cards.sessions = filter_active(flat)
        if not grouped:
            tree.root.add_leaf(EMPTY_MESSAGE)
            return

        active_ids = self._active_db_ids()
        target_leaf = None
        for project_path, sessions in sorted(grouped.items()):
            label = project_path or "(no project)"
            project_node = tree.root.add(label, expand=True)
            for session in sessions:
                title = session.get("title") or "(untitled)"
                ts = _fmt_timestamp(session.get("last_used"))
                prefix = ACTIVE_MARKER if session.get("id") in active_ids else ""
                leaf_label = f"{prefix}{title}  [dim]{ts}[/]" if ts else f"{prefix}{title}"
                leaf = project_node.add_leaf(leaf_label, data=session)
                if remembered is not None and session.get("id") == remembered:
                    target_leaf = leaf
        if target_leaf is not None:
            tree.move_cursor(target_leaf)

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

    @on(ActiveSessionCards.Resume)
    def on_active_card_resume(self, event: ActiveSessionCards.Resume) -> None:
        event.stop()
        self.dismiss(event.session)
