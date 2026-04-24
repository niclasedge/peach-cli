"""toad-27: project_path column migration + backfill tests."""

import json

import aiosqlite
import pytest

from peach.db import DB


async def _old_schema(path):
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            """
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent TEXT NOT NULL,
                agent_identity TEXT NOT NULL,
                agent_session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                protocol TEXT NOT NULL,
                prompt_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                meta_json TEXT DEFAULT '{}'
            )
            """
        )
        await conn.execute(
            """
            INSERT INTO sessions
            (agent, agent_identity, agent_session_id, title, protocol, meta_json)
            VALUES
            ('claude', 'claude.local', 'sess-1', 'T1', 'acp',
             ?)
            """,
            (json.dumps({"cwd": "/tmp/project-a"}),),
        )
        await conn.execute(
            """
            INSERT INTO sessions
            (agent, agent_identity, agent_session_id, title, protocol, meta_json)
            VALUES
            ('claude', 'claude.local', 'sess-2', 'T2', 'acp', '{}')
            """
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_migration_adds_project_path_column(tmp_path):
    db_path = tmp_path / "peach.db"
    await _old_schema(db_path)

    db = DB()
    db.path = db_path
    await db.create()

    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in await cursor.fetchall()}

    assert "project_path" in cols


@pytest.mark.asyncio
async def test_migration_backfills_project_path_from_meta_json_cwd(tmp_path):
    db_path = tmp_path / "peach.db"
    await _old_schema(db_path)

    db = DB()
    db.path = db_path
    await db.create()

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT title, project_path FROM sessions ORDER BY id"
        )
        rows = await cursor.fetchall()

    by_title = {r["title"]: r["project_path"] for r in rows}
    assert by_title["T1"] == "/tmp/project-a"
    assert by_title["T2"] in (None, "")
