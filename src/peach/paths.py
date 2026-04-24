from contextlib import suppress
from pathlib import Path
from typing import Final

from platformdirs import user_config_dir, user_data_dir, user_state_dir


APP_NAME: Final[str] = "peach"


def path_to_name(path: Path) -> str:
    """Convert a path to a filesystem-safe component name.

    Works on POSIX (`/a/b/c` -> `a-b-c`) and Windows (`C:\\a\\b` -> `C-a-b`)
    by normalising separators and stripping leading slashes or drive colons.
    """
    as_posix = Path(path).resolve().as_posix()
    return as_posix.lstrip("/").replace(":", "-").replace("/", "-")


def get_data() -> Path:
    """Return (possibly creating) the application data directory."""
    path = Path(user_data_dir(APP_NAME, appauthor=False))
    with suppress(OSError):
        path.mkdir(0o700, exist_ok=True, parents=True)
    return path


def get_config() -> Path:
    """Return (possibly creating) the application config directory."""
    path = Path(user_config_dir(APP_NAME, appauthor=False))
    with suppress(OSError):
        path.mkdir(0o700, exist_ok=True, parents=True)
    return path


def get_state() -> Path:
    """Return (possibly creating) the application state directory."""
    path = Path(user_state_dir(APP_NAME, appauthor=False))
    with suppress(OSError):
        path.mkdir(0o700, exist_ok=True, parents=True)
    return path


def get_project_data(project_path: Path) -> Path:
    """Get a directory for per-project data."""
    project_data_path = get_data() / path_to_name(project_path)
    with suppress(OSError):
        project_data_path.mkdir(0o700, exist_ok=True, parents=True)
    return project_data_path


def get_log() -> Path:
    """Get a directory for logs."""
    path = get_state() / "logs"
    with suppress(OSError):
        path.mkdir(0o700, exist_ok=True, parents=True)
    return path
