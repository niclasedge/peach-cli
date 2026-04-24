"""Snapshot test for the Peach app main screen."""

from pathlib import Path

from peach.app import ToadApp


def test_main_screen_snapshot(snap_compare):
    """Snapshot the app's main screen at a fixed terminal size.

    On first run (no baseline), pytest-textual-snapshot requires --snapshot-update
    to create the baseline SVG. Subsequent runs compare against that baseline.
    """
    app = ToadApp(agent_data=None, project_dir=str(Path.cwd()))
    assert snap_compare(app, terminal_size=(100, 30))
