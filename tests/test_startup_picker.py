"""Red tests for the startup session picker (Phase 3).

All three tests are RED until toad-30 (screens/startup_picker.py) and
toad-31 (wire into app launch) land.
"""

import pytest


def test_startup_picker_screen_module_exists():
    """toad-30 creates screens/startup_picker.py with a StartupPickerScreen class."""
    from peach.screens import startup_picker  # noqa: F401
    assert hasattr(startup_picker, "StartupPickerScreen")


@pytest.mark.asyncio
async def test_db_sessions_recent_groups_by_project_path(tmp_path):
    """toad-27 adds project_path column, toad-29 adds the grouped query API."""
    from peach.db import DB

    db = DB()
    db.path = tmp_path / "peach.db"
    await db.create()

    grouped = await db.sessions_recent(limit=10, group_by_project=True)
    assert isinstance(grouped, dict)


@pytest.mark.asyncio
async def test_session_tracker_inserts_row_before_acp_handshake(tmp_path):
    """toad-28: SessionTracker.new_session() must persist a row immediately
    with project_path populated, even if ACP handshake never completes."""
    from peach.db import DB
    from peach.session_tracker import SessionTracker

    db = DB()
    db.path = tmp_path / "peach.db"
    await db.create()

    tracker = SessionTracker(db)
    project_path = str(tmp_path / "my-project")
    session_state = await tracker.new_session(
        title="New Session",
        agent="claude",
        agent_identity="claude.local",
        project_path=project_path,
    )

    rows = await db.sessions_recent(limit=10)
    assert any(r.get("project_path") == project_path for r in rows), (
        f"new_session() did not persist project_path={project_path!r} "
        f"immediately. rows={rows}"
    )
    del session_state
