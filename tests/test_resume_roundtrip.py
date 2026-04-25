"""toad-32: end-to-end resume roundtrip test.

Pragmatic E2E: seed a session directly in the DB, render the
StartupPickerScreen, programmatically trigger the 'resume this session'
dismiss, assert the app's launch_agent path is invoked with the
expected sessionId.

We don't spin up a real ACP subprocess — the plan allows mocking.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from peach.db import DB
from peach.screens.startup_picker import StartupPickerScreen


@pytest.mark.asyncio
async def test_startup_picker_dismiss_returns_session(tmp_path):
    """Seed DB with a session, open picker, dismiss with the session dict."""
    db_path = tmp_path / "peach.db"
    db = DB()
    db.path = db_path
    await db.create()

    project_path = str(tmp_path / "proj")
    session_pk = await db.session_insert_early(
        title="Prev session",
        agent="claude",
        agent_identity="claude.com",
        project_path=project_path,
    )
    assert session_pk is not None
    await db.session_set_agent_session_id(session_pk, "acp-sess-xyz")

    from textual.app import App

    class _HostApp(App):
        captured: object = None

        async def on_mount(self) -> None:
            picker = StartupPickerScreen(cwd=str(tmp_path), db=db)

            def _on_dismiss(result):
                type(self).captured = result
                self.exit()

            self.push_screen(picker, _on_dismiss)

    app = _HostApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, StartupPickerScreen)
        tree = picker.tree
        node = None
        for child in tree.root.children:
            if child.children:
                node = child.children[0]
                break
        assert node is not None, "no session leaf found in picker tree"
        picker.dismiss(node.data)
        await pilot.pause()

    result = _HostApp.captured
    assert isinstance(result, dict)
    assert result["agent_session_id"] == "acp-sess-xyz"
    assert result["project_path"] == project_path


@pytest.mark.asyncio
async def test_app_bootstrap_invokes_launch_agent_on_resume(tmp_path, monkeypatch):
    """Verify the app's bootstrap path calls launch_agent with the
    persisted agent_session_id when a session is selected."""
    db_path = tmp_path / "peach.db"
    db = DB()
    db.path = db_path
    await db.create()

    project_path = str(tmp_path / "myproj")
    Path(project_path).mkdir(parents=True, exist_ok=True)
    session_pk = await db.session_insert_early(
        title="Old",
        agent="claude",
        agent_identity="claude.com",
        project_path=project_path,
    )
    await db.session_set_agent_session_id(session_pk, "expected-acp-id")

    import peach.paths
    monkeypatch.setattr(peach.paths, "get_state", lambda: tmp_path)

    from peach.app import ToadApp
    import peach

    launch_calls: list[dict] = []
    peach_dir = Path(peach.__file__).parent

    class _CapturedApp(ToadApp):
        CSS_PATH = str(peach_dir / "peach.tcss")

        def launch_agent(self, agent_identity, **kwargs):
            launch_calls.append({"agent_identity": agent_identity, **kwargs})
            self.exit()

    app = _CapturedApp(agent_data=None, project_dir=project_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, StartupPickerScreen)
        tree = picker.tree
        leaf = None
        for child in tree.root.children:
            if child.children:
                leaf = child.children[0]
                break
        assert leaf is not None
        picker.dismiss(leaf.data)
        await pilot.pause()

    assert launch_calls, "launch_agent was not invoked on resume"
    call = launch_calls[0]
    assert call["agent_session_id"] == "expected-acp-id"
    assert call["session_pk"] == session_pk
