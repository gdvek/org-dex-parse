"""S01: verify package scaffolding is functional."""

import re


def test_import():
    """AC2: package imports without errors."""
    import org_dex_parse  # noqa: F401


def test_version_exists():
    """AC2: __version__ exists and is a string."""
    from org_dex_parse import __version__

    assert isinstance(__version__, str)


def test_version_format():
    """AC2: __version__ follows X.Y.Z format."""
    from org_dex_parse import __version__

    assert re.match(r"^\d+\.\d+\.\d+$", __version__)
