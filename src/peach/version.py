from typing import NamedTuple


class VersionMeta(NamedTuple):
    """Information about the current version of Peach."""

    version: str
    upgrade_message: str
    visit_url: str


class VersionCheckFailed(Exception):
    """Something went wrong in the version check."""


async def check_version() -> tuple[bool, VersionMeta]:
    """Check for a new version of Peach.

    Disabled in the fork: upstream Toad's batrachian.ai endpoint is not
    relevant, and Peach has no equivalent release-announce endpoint yet.
    """
    raise VersionCheckFailed("Version check disabled in Peach fork")
