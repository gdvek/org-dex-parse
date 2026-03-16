"""S19: CLI pubblica — test derivati dagli acceptance criteria.

Tests invoke the CLI via subprocess to test the real user experience.
A minimal org fixture is created in tmp_path for each test that needs it.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# Path to the examples directory (relative to project root).
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _write_org(tmp_path: Path, content: str, name: str = "test.org") -> Path:
    """Write a minimal org file and return its path."""
    p = tmp_path / name
    p.write_text(textwrap.dedent(content))
    return p


def _run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run the CLI and return the result."""
    return subprocess.run(
        [sys.executable, "-m", "org_dex_parse", *args],
        capture_output=True,
        text=True,
        check=check,
    )


# -- Fixture: minimal org file with one item ----------------------------------

@pytest.fixture()
def org_file(tmp_path):
    """Org file with two items: one with :Type:, one without."""
    return _write_org(tmp_path, """\
        * Item with Type
          :PROPERTIES:
          :ID: id-001
          :Type: project
          :END:
          Some body text here.

        * Item without Type
          :PROPERTIES:
          :ID: id-002
          :END:
          Another body.
    """)


# -- AC1: bare default --------------------------------------------------------

def test_bare_default(org_file):
    """AC1: without flags, bare config — any heading with :ID: is an item."""
    result = _run_cli(str(org_file))
    # Both items should appear (bare = any :ID:).
    assert "id-001" in result.stdout
    assert "id-002" in result.stdout


# -- AC2: --predicate ----------------------------------------------------------

def test_predicate_flag(org_file):
    """AC2: --predicate filters correctly."""
    result = _run_cli(
        "--predicate", '["property", "Type"]',
        str(org_file),
    )
    # Only the item with :Type: should appear.
    assert "id-001" in result.stdout
    assert "id-002" not in result.stdout


# -- AC3: --todos / --dones ----------------------------------------------------

def test_todos_dones_flags(tmp_path):
    """AC3: --todos and --dones configure keywords."""
    org = _write_org(tmp_path, """\
        * CUSTOM Item
          :PROPERTIES:
          :ID: id-t01
          :END:
    """)
    # Without --todos, CUSTOM is not recognized as a keyword.
    result_bare = _run_cli(str(org))
    assert "todo=CUSTOM" not in result_bare.stdout

    # With --todos, CUSTOM is recognized.
    result_kw = _run_cli("--todos", "CUSTOM", str(org))
    assert "todo=CUSTOM" in result_kw.stdout


# -- AC4: --config loads JSON --------------------------------------------------

def test_config_file(tmp_path, org_file):
    """AC4: --config loads configuration from JSON file."""
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "predicate": ["property", "Type"],
    }))
    result = _run_cli("--config", str(config), str(org_file))
    # Predicate from config: only :Type: items.
    assert "id-001" in result.stdout
    assert "id-002" not in result.stdout


# -- AC5: CLI flags override config file ---------------------------------------

def test_config_file_cli_override(tmp_path, org_file):
    """AC5: CLI flags override config file values."""
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "predicate": ["property", "Type"],
    }))
    # --predicate on CLI overrides the one in config file.
    # None predicate = bare (accept all with :ID:).
    result = _run_cli(
        "--config", str(config),
        "--predicate", "null",
        str(org_file),
    )
    assert "id-001" in result.stdout
    assert "id-002" in result.stdout


# -- AC6: --json produces valid JSON -------------------------------------------

def test_json_output(org_file):
    """AC6: --json produces valid, parseable JSON."""
    result = _run_cli("--json", str(org_file))
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) == 2
    # Each entry has at least the core fields.
    for item in data:
        assert "item_id" in item
        assert "title" in item


# -- AC7: text verbosity levels ------------------------------------------------

def test_verbosity_text_default(org_file):
    """AC7: default text output has no body or raw_text."""
    result = _run_cli(str(org_file))
    assert "body=" not in result.stdout.lower().replace("body text", "")
    assert "raw_text" not in result.stdout


def test_verbosity_text_v(org_file):
    """AC7: -v adds body to text output."""
    result = _run_cli("-v", str(org_file))
    assert "body:" in result.stdout.lower() or "body=" in result.stdout.lower()


def test_verbosity_text_vv(org_file):
    """AC7: -vv adds raw_text to text output."""
    result = _run_cli("-vv", str(org_file))
    assert "raw_text" in result.stdout


# -- AC8: JSON verbosity levels ------------------------------------------------

def test_verbosity_json_default(org_file):
    """AC8: JSON default excludes body and raw_text."""
    result = _run_cli("--json", str(org_file))
    data = json.loads(result.stdout)
    for item in data:
        assert "body" not in item
        assert "raw_text" not in item


def test_verbosity_json_v(org_file):
    """AC8: JSON -v includes body but not raw_text."""
    result = _run_cli("--json", "-v", str(org_file))
    data = json.loads(result.stdout)
    for item in data:
        assert "body" in item
        assert "raw_text" not in item


def test_verbosity_json_vv(org_file):
    """AC8: JSON -vv includes both body and raw_text."""
    result = _run_cli("--json", "-vv", str(org_file))
    data = json.loads(result.stdout)
    for item in data:
        assert "body" in item
        assert "raw_text" in item


# -- AC9: no REMI_CONFIG in distributed code -----------------------------------

def test_no_remi_config():
    """AC9: no trace of REMI_CONFIG in __main__.py."""
    main_path = Path(__file__).parent.parent / "org_dex_parse" / "__main__.py"
    source = main_path.read_text()
    assert "REMI_CONFIG" not in source
    assert "_REMI_" not in source


# -- AC10: --help lists all flags ----------------------------------------------

def test_help_output():
    """AC10: --help describes all available flags."""
    result = _run_cli("--help")
    for flag in [
        "--predicate", "--todos", "--dones", "--tags-exclude",
        "--exclude-drawers", "--exclude-blocks", "--exclude-properties",
        "--created-property", "--extra-tag-chars", "--config", "--json",
    ]:
        assert flag in result.stdout, f"{flag} missing from --help"


# -- AC11: unknown field in config file ----------------------------------------

def test_config_unknown_field(tmp_path, org_file):
    """AC11: unknown field in config file produces a clear error."""
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"bogus_field": True}))
    result = _run_cli("--config", str(config), str(org_file), check=False)
    assert result.returncode != 0
    assert "bogus_field" in result.stderr


# -- AC12: missing config file -------------------------------------------------

def test_config_file_missing(org_file):
    """AC12: missing config file produces a clear error."""
    result = _run_cli("--config", "/nonexistent/config.json",
                       str(org_file), check=False)
    assert result.returncode != 0
    assert "nonexistent" in result.stderr.lower() or "not found" in result.stderr.lower()


# -- AC13: examples/config.json exists and is valid ----------------------------

def test_example_config_valid():
    """AC13: examples/config.json exists and is valid JSON."""
    config_path = EXAMPLES_DIR / "config.json"
    assert config_path.exists(), f"{config_path} does not exist"

    data = json.loads(config_path.read_text())
    assert isinstance(data, dict)

    # All keys should be valid Config field names.
    valid_keys = {
        "predicate", "todos", "dones", "tags_exclude_from_inheritance",
        "exclude_drawers", "exclude_blocks", "exclude_properties",
        "created_property", "extra_tag_chars",
    }
    for key in data:
        assert key in valid_keys, f"unknown key {key!r} in example config"
