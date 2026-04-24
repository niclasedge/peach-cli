import subprocess
import sys


def test_version():
    result = subprocess.run(
        [sys.executable, "-m", "peach", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip()


def test_help_lists_commands():
    result = subprocess.run(
        [sys.executable, "-m", "peach", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    for command in ("run", "acp", "replay", "serve", "about", "settings"):
        assert command in result.stdout, f"missing command in --help: {command}"


def test_import_peach():
    import peach

    assert peach is not None
