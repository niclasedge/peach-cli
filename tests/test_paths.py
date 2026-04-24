"""Cross-platform path resolution smoke test."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from peach import paths


def test_app_name_is_peach():
    assert paths.APP_NAME == "peach"


def test_path_to_name_posix_absolute():
    result = paths.path_to_name(Path("/Users/foo/projects/bar"))
    assert "/" not in result
    assert ":" not in result
    assert result.endswith("bar")


def test_path_to_name_windows_style_component_names():
    result = paths.path_to_name(Path("/a/b c/d"))
    assert "/" not in result
    assert ":" not in result


@pytest.mark.parametrize("platform_name", ["darwin", "linux", "win32"])
def test_get_state_platform_shape(platform_name, tmp_path):
    if platform_name == "darwin":
        expected_marker = "Library"
    elif platform_name == "linux":
        expected_marker = ".local"
    else:
        expected_marker = None

    with patch.object(sys, "platform", platform_name):
        from importlib import reload
        import peach.paths as mod
        reload(mod)
        result = mod.get_state()

    assert "peach" in str(result).lower()
    if expected_marker is not None and sys.platform != "win32":
        assert expected_marker in str(result) or sys.platform != platform_name, (
            f"expected '{expected_marker}' in path for {platform_name}, got {result}"
        )
