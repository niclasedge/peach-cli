from dataclasses import dataclass
from operator import attrgetter
from typing import TYPE_CHECKING, Iterable, Literal, Sequence

from textual.signal import Signal

if TYPE_CHECKING:
    from peach.db import DB

type SessionState = Literal["notready", "busy", "asking", "idle"]


@dataclass
class SessionDetails:
    """Tracks a concurrent session."""

    index: int
    mode_name: str
    title: str = ""
    subtitle: str = ""
    path: str = ""
    state: SessionState = "notready"
    summary: str = ""
    updates: int = 0
    db_id: int | None = None


class SessionTracker:
    """Tracks concurrent agent settings"""

    def __init__(
        self,
        signal_or_db: "Signal[tuple[str, SessionDetails | None]] | DB | None" = None,
        db: "DB | None" = None,
    ) -> None:
        from peach.db import DB as _DB

        self.sessions: dict[str, SessionDetails] = {}
        self._session_index = 0
        if isinstance(signal_or_db, _DB):
            self.signal = None
            self._db = signal_or_db
        else:
            self.signal = signal_or_db
            self._db = db

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    async def new_session(
        self,
        *,
        title: str = "New Session",
        agent: str = "claude",
        agent_identity: str = "claude.local",
        project_path: str | None = None,
        db_id: int | None = None,
    ) -> SessionDetails:
        """Register a new session.

        For fresh sessions (`db_id is None`): persists a DB row up-front via
        `session_insert_early` so mid-handshake crashes don't lose the session.
        ACP's agent_session_id is filled in later via `set_agent_session_id`.

        For resumed sessions (`db_id is given`): reuses the existing DB row;
        no insert. This avoids duplicate rows when the user picks an existing
        session from the startup picker or sidebar.
        """
        self._session_index += 1
        mode_name = f"session-{self._session_index}"
        session_meta = SessionDetails(
            index=self._session_index,
            mode_name=mode_name,
            title=title,
            path=project_path or "",
        )
        self.sessions[mode_name] = session_meta

        if db_id is not None:
            session_meta.db_id = db_id
        elif self._db is not None and project_path is not None:
            new_id = await self._db.session_insert_early(
                title=title,
                agent=agent,
                agent_identity=agent_identity,
                project_path=project_path,
            )
            session_meta.db_id = new_id

        return session_meta

    async def set_agent_session_id(
        self, mode_name: str, agent_session_id: str
    ) -> None:
        """Update the persisted row once ACP's session/new response arrives."""
        session_meta = self.sessions.get(mode_name)
        if session_meta is None or session_meta.db_id is None or self._db is None:
            return
        await self._db.session_set_agent_session_id(
            session_meta.db_id, agent_session_id
        )

    def close_session(self, mode_name: str) -> None:
        if mode_name in self.sessions:
            del self.sessions[mode_name]
            if self.signal is not None:
                self.signal.publish((mode_name, None))

    def get_session(self, mode_name: str) -> SessionDetails | None:
        return self.sessions.get(mode_name, None)

    def update_session(
        self,
        mode_name: str,
        title: str | None = None,
        subtitle: str | None = None,
        path: str | None = None,
        state: SessionState | None = None,
    ) -> SessionDetails:
        session_details = self.sessions[mode_name]
        if title is not None:
            session_details.title = title
        if subtitle is not None:
            session_details.subtitle = subtitle
        if path is not None:
            session_details.path = path
        if state is not None:
            session_details.state = state
        if self.signal is not None:
            self.signal.publish((mode_name, session_details))
        return session_details

    @property
    def ordered_sessions(self) -> Sequence[SessionDetails]:
        return sorted(self.sessions.values(), key=attrgetter("index"))

    def __iter__(self) -> Iterable[SessionDetails]:
        return iter(self.ordered_sessions)

    def session_cursor_move(
        self, mode_name: str, direction: Literal[-1, +1]
    ) -> str | None:
        mode_names = [session.mode_name for session in self.ordered_sessions]
        try:
            mode_index = mode_names.index(mode_name)
        except ValueError:
            return None
        mode_index = (mode_index + direction) % len(mode_names)
        new_mode_name = mode_names[mode_index]
        return new_mode_name
