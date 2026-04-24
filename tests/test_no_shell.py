import pytest


def test_peach_shell_module_is_gone():
    with pytest.raises(ImportError):
        import peach.shell  # noqa: F401


def test_schema_has_no_shell_section():
    from peach.settings_schema import SCHEMA

    top_level_keys = {entry["key"] for entry in SCHEMA}
    assert "shell" not in top_level_keys, (
        f"shell section still present in SCHEMA: {sorted(top_level_keys)}"
    )
