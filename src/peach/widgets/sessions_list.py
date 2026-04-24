"""Sessions list widget for the MainScreen sidebar.

Renders recent sessions grouped by project (basename only), with a
human-friendly timestamp: today → `HH:MM`, otherwise `dd.mm. HH:MM`.
Enter on a session leaf resumes it via ToadApp.launch_agent.

Auto-refresh:
- Subscribes to `session_update_signal` → instant refresh on in-app
  rename / state change.
- `set_interval(10)` → picks up cross-instance DB changes (e.g. another
  peach-tab renamed a session).
- Polling pauses while the sidebar is hidden (`-hide-sidebar` class).
- Sessions currently tracked in memory are marked with a `● ` prefix.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from textual import on, widgets
from textual.app import ComposeResult
from textual.containers import VerticalScroll

from peach.db import DB, Session

if TYPE_CHECKING:
    from peach.app import ToadApp
    from peach.session_tracker import SessionDetails


ACTIVE_MARKER = "● "
REFRESH_INTERVAL_SECONDS = 10.0


def _fmt_timestamp(iso_or_sqlite: str | None) -> str:
    if not iso_or_sqlite:
        return ""
    text = iso_or_sqlite.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return text
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone()
    today = datetime.now().astimezone().date()
    if local.date() == today:
        return local.strftime("%H:%M")
    return local.strftime("%d.%m. %H:%M")


class SessionsList(VerticalScroll):
    """Compact, grouped recent-sessions list for the sidebar."""

    DEFAULT_CSS = """
    SessionsList {
        height: auto;
        padding: 0 1;
    }
    SessionsList Tree {
        background: transparent;
        height: auto;
    }
    """

    def __init__(self, *, limit: int = 50) -> None:
        super().__init__()
        self._limit = limit

    def compose(self) -> ComposeResult:
        yield widgets.Tree[Session | None]("Sessions", id="sidebar-sessions-tree")

    async def on_mount(self) -> None:
        app: "ToadApp" = self.app  # type: ignore[assignment]
        app.session_update_signal.subscribe(self, self._on_session_update_signal)
        self.set_interval(
            REFRESH_INTERVAL_SECONDS, self._periodic_refresh, pause=False
        )
        await self.refresh_sessions()

    async def _on_session_update_signal(
        self, update: "tuple[str, SessionDetails | None]"
    ) -> None:
        await self.refresh_sessions()

    async def _periodic_refresh(self) -> None:
        if self.app.has_class("-hide-sidebar"):
            return
        await self.refresh_sessions()

    def _active_db_ids(self) -> set[int]:
        app: "ToadApp" = self.app  # type: ignore[assignment]
        tracker = getattr(app, "session_tracker", None)
        if tracker is None:
            return set()
        return {
            s.db_id for s in tracker.ordered_sessions if s.db_id is not None
        }

    async def refresh_sessions(self) -> None:
        tree = self.query_one("#sidebar-sessions-tree", widgets.Tree)
        tree.root.remove_children()
        tree.root.expand()
        tree.show_root = False

        db = DB()
        await db.create()
        grouped = await db.sessions_recent(
            limit=self._limit, group_by_project=True
        )

        if not grouped:
            tree.root.add_leaf("(no sessions yet)")
            return

        active_ids = self._active_db_ids()

        for project_path, sessions in sorted(
            grouped.items(),
            key=lambda kv: (kv[1][0].get("last_used") or ""),
            reverse=True,
        ):
            basename = Path(project_path).name if project_path else "(no project)"
            node = tree.root.add(basename, expand=True)
            for session in sessions:
                title = session.get("title") or "(untitled)"
                ts = _fmt_timestamp(session.get("last_used"))
                prefix = ACTIVE_MARKER if session.get("id") in active_ids else ""
                label = f"{prefix}{title}  [dim]{ts}[/]" if ts else f"{prefix}{title}"
                node.add_leaf(label, data=session)

    @on(widgets.Tree.NodeSelected)
    async def _on_node_selected(
        self, event: widgets.Tree.NodeSelected[Session | None]
    ) -> None:
        session = event.node.data
        if session is None:
            return
        app: "ToadApp" = self.app  # type: ignore[assignment]
        project_path_str = session.get("project_path") or ""
        app.launch_agent(
            agent_identity=session.get("agent_identity") or "claude.com",
            agent_session_id=session.get("agent_session_id"),
            session_pk=session.get("id"),
            project_path=Path(project_path_str) if project_path_str else None,
        )
