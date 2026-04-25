from datetime import datetime, timezone
import json
from typing import cast, TypedDict
from peach import paths

import aiosqlite


class Session(TypedDict, total=False):
    """Agent session fields."""

    id: int
    agent: str
    agent_identity: str
    agent_session_id: str | None
    title: str
    protocol: str
    prompt_count: int
    created_at: str
    last_used: str
    meta_json: str
    project_path: str | None
    last_user_prompt: str | None
    last_reply: str | None
    turn_ended_at: str | None


class DB:
    """Peach's database, for anything that isn't strictly configuration."""

    def __init__(self):
        self.path = paths.get_state() / "peach.db"

    def open(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self.path)

    async def create(self) -> bool:
        """Create / migrate the tables."""
        try:
            async with self.open() as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent TEXT NOT NULL,
                        agent_identity TEXT NOT NULL,
                        agent_session_id TEXT,
                        title TEXT NOT NULL,
                        protocol TEXT NOT NULL,
                        prompt_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        meta_json TEXT DEFAULT '{}',
                        project_path TEXT
                    )
                    """
                )
                await db.commit()
                await self._migrate_project_path(db)
                await self._migrate_chat_preview(db)
        except aiosqlite.Error:
            return False
        return True

    async def _migrate_project_path(self, db: aiosqlite.Connection) -> None:
        """Add project_path column on old-schema DBs and backfill from meta_json.cwd."""
        cursor = await db.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in await cursor.fetchall()}
        if "project_path" not in cols:
            await db.execute("ALTER TABLE sessions ADD COLUMN project_path TEXT")
        # Backfill where possible (idempotent — only sets NULL rows)
        await db.execute(
            """
            UPDATE sessions
            SET project_path = json_extract(meta_json, '$.cwd')
            WHERE project_path IS NULL
              AND json_valid(meta_json)
              AND json_extract(meta_json, '$.cwd') IS NOT NULL
            """
        )
        await db.commit()

    async def _migrate_chat_preview(self, db: aiosqlite.Connection) -> None:
        """Add last_user_prompt / last_reply / turn_ended_at columns."""
        cursor = await db.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in await cursor.fetchall()}
        if "last_user_prompt" not in cols:
            await db.execute(
                "ALTER TABLE sessions ADD COLUMN last_user_prompt TEXT"
            )
        if "last_reply" not in cols:
            await db.execute("ALTER TABLE sessions ADD COLUMN last_reply TEXT")
        if "turn_ended_at" not in cols:
            await db.execute(
                "ALTER TABLE sessions ADD COLUMN turn_ended_at TIMESTAMP"
            )
        await db.commit()

    async def session_new(
        self,
        title: str,
        agent: str,
        agent_identity: str,
        agent_session_id: str,
        protocol: str = "acp",
        meta: dict[str, object] | None = None,
    ) -> int | None:
        meta_json = json.dumps(meta or {})
        try:
            async with self.open() as db:
                cursor = await db.execute(
                    """
                    INSERT INTO sessions (title, agent, agent_identity, agent_session_id, protocol, meta_json) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title,
                        agent,
                        agent_identity,
                        agent_session_id,
                        protocol,
                        meta_json,
                    ),
                )
                await db.commit()
                return cursor.lastrowid
        except aiosqlite.Error:
            return None

    async def session_update_last_used(self, id: int) -> bool:
        """Update the last used timestamp.

        Args:
            id: Session ID.

        Returns:
            Boolenan that indicates success.
        """
        now_utc = datetime.now(timezone.utc)
        try:
            async with self.open() as db:
                await db.execute(
                    "UPDATE sessions SET last_used = ? WHERE id = ?",
                    (
                        now_utc.isoformat(),
                        id,
                    ),
                )
                await db.commit()
        except aiosqlite.Error:
            return False
        return True

    async def session_set_last_user_prompt(self, id: int, prompt: str) -> bool:
        """Persist a truncated copy of the latest user prompt and bump
        `last_used` so the picker shows fresh activity right away.

        Atomic so the active-session card's age never lags behind the
        prompt the user just sent.
        """
        snippet = (prompt or "").strip()[:240]
        now_utc = datetime.now(timezone.utc).isoformat()
        try:
            async with self.open() as db:
                await db.execute(
                    """
                    UPDATE sessions
                       SET last_user_prompt = ?, last_used = ?
                     WHERE id = ?
                    """,
                    (snippet, now_utc, id),
                )
                await db.commit()
        except aiosqlite.Error:
            return False
        return True

    async def session_set_last_reply(self, id: int, reply: str) -> bool:
        """Persist a truncated copy of the latest agent reply, stamp
        `turn_ended_at` to mark the turn as completed, and bump
        `last_used` so the card stays fresh after the reply lands.

        Atomic so the picker can never see a reply without its turn-end
        timestamp (or with stale activity).
        """
        snippet = (reply or "").strip()[:240]
        now_utc = datetime.now(timezone.utc).isoformat()
        try:
            async with self.open() as db:
                await db.execute(
                    """
                    UPDATE sessions
                       SET last_reply = ?, turn_ended_at = ?, last_used = ?
                     WHERE id = ?
                    """,
                    (snippet, now_utc, now_utc, id),
                )
                await db.commit()
        except aiosqlite.Error:
            return False
        return True

    async def session_update_title(self, id: int, title: str) -> bool:
        """Update the last used timestamp.

        Args:
            id: Session ID.
            title: New title.

        Returns:
            Boolenan that indicates success.
        """
        try:
            async with self.open() as db:
                await db.execute(
                    "UPDATE sessions SET title = ? WHERE id = ?",
                    (
                        title,
                        id,
                    ),
                )
                await db.commit()
        except aiosqlite.Error:
            return False
        return True

    async def session_get(self, id: int) -> Session | None:
        """Get a sesison from its ID (PK).

        Args:
            session_id: The ID field (PK, not the agent_session_id)

        Returns:
            A Session if one is found, or `None`.
        """
        try:
            async with self.open() as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * from sessions WHERE id = ?", (id,))
                row = await cursor.fetchone()
        except aiosqlite.Error:
            return None
        if row is None:
            return None
        session = cast(Session, dict(row))
        return session

    async def session_get_recent(self, max_results: int = 100) -> list[Session] | None:
        """Get the most recent sessions."""
        try:
            async with self.open() as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """SELECT * from sessions
                    ORDER BY last_used DESC
                    LIMIT ?""",
                    (max_results,),
                )
                rows = await cursor.fetchall()
        except aiosqlite.Error:
            return None
        sessions = [cast(Session, dict(row)) for row in rows]
        return sessions

    async def sessions_recent(
        self,
        limit: int = 100,
        project_path: str | None = None,
        group_by_project: bool = False,
    ) -> list[Session] | dict[str, list[Session]]:
        """Recent sessions, optionally filtered or grouped by project_path.

        Returns a flat list ordered by `last_used DESC` (newest first), or a
        dict keyed by project_path when group_by_project=True.
        """
        query = "SELECT * FROM sessions"
        params: list[object] = []
        if project_path is not None:
            query += " WHERE project_path = ?"
            params.append(project_path)
        query += " ORDER BY last_used DESC LIMIT ?"
        params.append(limit)

        try:
            async with self.open() as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(query, tuple(params))
                rows = await cursor.fetchall()
        except aiosqlite.Error:
            return {} if group_by_project else []

        sessions = [cast(Session, dict(row)) for row in rows]

        if not group_by_project:
            return sessions

        grouped: dict[str, list[Session]] = {}
        for session in sessions:
            key = (session.get("project_path") or "")
            grouped.setdefault(key, []).append(session)
        return grouped

    async def session_set_project_path(self, id: int, project_path: str) -> bool:
        """Set the project_path for a session (used by early-persist flow)."""
        try:
            async with self.open() as db:
                await db.execute(
                    "UPDATE sessions SET project_path = ? WHERE id = ?",
                    (project_path, id),
                )
                await db.commit()
        except aiosqlite.Error:
            return False
        return True

    async def session_set_agent_session_id(
        self, id: int, agent_session_id: str
    ) -> bool:
        """Set the ACP agent_session_id once the handshake completes."""
        try:
            async with self.open() as db:
                await db.execute(
                    "UPDATE sessions SET agent_session_id = ? WHERE id = ?",
                    (agent_session_id, id),
                )
                await db.commit()
        except aiosqlite.Error:
            return False
        return True

    async def session_delete(self, id: int) -> bool:
        """Hard-delete a session row. Returns True if a row was removed."""
        try:
            async with self.open() as db:
                cursor = await db.execute(
                    "DELETE FROM sessions WHERE id = ?", (id,)
                )
                await db.commit()
                return cursor.rowcount > 0
        except aiosqlite.Error:
            return False

    async def session_insert_early(
        self,
        title: str,
        agent: str,
        agent_identity: str,
        project_path: str,
        protocol: str = "acp",
        meta: dict[str, object] | None = None,
    ) -> int | None:
        """Insert a session row before the ACP handshake completes."""
        meta_json = json.dumps(meta or {})
        try:
            async with self.open() as db:
                cursor = await db.execute(
                    """
                    INSERT INTO sessions
                    (title, agent, agent_identity, agent_session_id, protocol,
                     meta_json, project_path)
                    VALUES (?, ?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        title,
                        agent,
                        agent_identity,
                        protocol,
                        meta_json,
                        project_path,
                    ),
                )
                await db.commit()
                return cursor.lastrowid
        except aiosqlite.Error:
            return None
