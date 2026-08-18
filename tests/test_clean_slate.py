"""Guard the clean slate: the distribution must carry only org_cube_parse.

The rename to org-cube exists to stop colliding with the third-party
org-dex Emacs package.  A build that still shipped org_dex_parse -- because
a stray directory survived, or because the build backend inferred the
package set and inferred it wrong -- would quietly recreate the very
collision the rename removes, and it would do so in an artifact that
cannot be unpublished once it reaches PyPI.

These tests check the two places the old name could survive: the source
tree that the build backend packages, and the import system of the
environment the wheel was installed into.
"""

import importlib.util
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_old_namespace_not_in_source_tree():
    """No org_dex_parse directory is left for the backend to pick up."""
    assert not (REPO / "org_dex_parse").exists()


def test_old_namespace_not_importable():
    """The installed environment exposes no org_dex_parse."""
    assert importlib.util.find_spec("org_dex_parse") is None


def test_new_namespace_is_importable():
    """The counterpart assertion: the new name really is there."""
    assert importlib.util.find_spec("org_cube_parse") is not None


def test_wheel_is_pinned_to_the_new_namespace():
    """The wheel's package list is declared, not inferred.

    An inferred package set is not something a release gate can rest on:
    it can change with the layout without anyone editing a line.
    """
    cfg = tomllib.loads((REPO / "pyproject.toml").read_text())
    packages = cfg["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert packages == ["org_cube_parse"]


def test_distribution_name_and_version_agree_with_the_package():
    """pyproject and __init__ must not drift apart across the rename."""
    from org_cube_parse import __version__

    cfg = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert cfg["project"]["name"] == "org-cube-parse"
    assert cfg["project"]["version"] == __version__
