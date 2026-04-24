import pytest
import aiosqlite
from peach.db import DB

EXPECTED_COLUMNS = {
    "id", "agent", "agent_identity", "agent_session_id",
    "title", "protocol", "prompt_count", "created_at", "last_used", "meta_json",
    "project_path",
}


@pytest.mark.asyncio
async def test_db_create_returns_true(tmp_path):
    db = DB()
    db.path = tmp_path / "peach.db"
    result = await db.create()
    assert result is True


@pytest.mark.asyncio
async def test_sessions_table_has_expected_columns(tmp_path):
    db = DB()
    db.path = tmp_path / "peach.db"
    await db.create()

    async with aiosqlite.connect(db.path) as conn:
        cursor = await conn.execute("PRAGMA table_info(sessions)")
        rows = await cursor.fetchall()

    assert rows, "sessions table does not exist"
    actual_columns = {row[1] for row in rows}
    assert actual_columns == EXPECTED_COLUMNS


@pytest.mark.asyncio
async def test_session_delete_removes_row_and_leaves_others(tmp_path):
    db = DB()
    db.path = tmp_path / "peach.db"
    await db.create()

    ids: list[int] = []
    for i in range(3):
        sid = await db.session_insert_early(
            title=f"Session {i}",
            agent="claude",
            agent_identity="claude.local",
            project_path=str(tmp_path / f"p{i}"),
        )
        assert sid is not None
        ids.append(sid)

    middle = ids[1]
    ok = await db.session_delete(middle)
    assert ok is True

    remaining = await db.sessions_recent(limit=10)
    assert isinstance(remaining, list)
    remaining_ids = {row["id"] for row in remaining}
    assert remaining_ids == {ids[0], ids[2]}
    assert await db.session_get(middle) is None


@pytest.mark.asyncio
async def test_session_delete_returns_false_for_unknown_id(tmp_path):
    db = DB()
    db.path = tmp_path / "peach.db"
    await db.create()
    assert await db.session_delete(9999) is False
