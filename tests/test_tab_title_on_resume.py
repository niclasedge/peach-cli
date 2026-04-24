"""Regression test: resuming a renamed session must show the persisted
title in the SessionTracker (and therefore in the tab label), not
"New Session".
"""

from pathlib import Path

import pytest

from peach.db import DB


@pytest.mark.asyncio
async def test_launch_agent_propagates_persisted_title(tmp_path, monkeypatch):
    # Seed a renamed session in the DB.
    db = DB()
    db.path = tmp_path / "peach.db"
    await db.create()
    pk = await db.session_insert_early(
        title="pkm test",
        agent="claude",
        agent_identity="claude.com",
        project_path=str(tmp_path / "proj"),
    )
    assert pk is not None
    await db.session_set_agent_session_id(pk, "acp-id-xyz")

    # Point the app's DB at tmp_path (paths.get_state() is used by DB()).
    import peach.paths
    monkeypatch.setattr(peach.paths, "get_state", lambda: tmp_path)

    from peach.app import ToadApp
    import peach

    peach_dir = Path(peach.__file__).parent

    class _HostApp(ToadApp):
        CSS_PATH = str(peach_dir / "peach.tcss")

        async def on_mount(self) -> None:
            # Skip the normal bootstrap (StartupPicker) — call launch_agent
            # directly, then exit once the tracker has seen the new session.
            self.launch_agent(
                agent_identity="claude.com",
                agent_session_id="acp-id-xyz",
                session_pk=pk,
                project_path=Path(str(tmp_path / "proj")),
            )

    app = _HostApp(agent_data=None, project_dir=str(tmp_path / "proj"))
    async with app.run_test() as pilot:
        # launch_agent is @work; pump events until the tracker sees the session.
        for _ in range(20):
            await pilot.pause()
            sessions = list(app.session_tracker.ordered_sessions)
            if sessions:
                break
        assert sessions, "launch_agent did not register a session"
        first = sessions[0]
        assert first.title == "pkm test", (
            f"tab title regression: expected 'pkm test', got {first.title!r}"
        )
