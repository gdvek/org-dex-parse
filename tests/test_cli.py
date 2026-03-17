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


# -- S32: malformed JSON in config file ----------------------------------------

def test_config_malformed_json(tmp_path, org_file):
    """S32-AC1/AC2/AC3: malformed JSON config produces a clear error, no traceback."""
    config = tmp_path / "bad.json"
    config.write_text('{"predicate": [}')  # invalid JSON
    result = _run_cli("--config", str(config), str(org_file), check=False)
    assert result.returncode != 0
    # AC1: error message mentions invalid JSON.
    assert "invalid json" in result.stderr.lower()
    # AC2: error message includes the file path.
    assert "bad.json" in result.stderr
    # AC3: no Python traceback visible.
    assert "Traceback" not in result.stderr


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


# -- S25: CLI input validation and normalization -------------------------------

# AC1: CLI split strips whitespace and filters empty tokens.
def test_cli_todos_strip_and_filter(tmp_path):
    """S25-AC1: --todos 'TODO, NEXT,' strips spaces and drops empty tokens."""
    org = _write_org(tmp_path, """\
        * TODO First
          :PROPERTIES:
          :ID: id-s25-01
          :END:
        * NEXT Second
          :PROPERTIES:
          :ID: id-s25-02
          :END:
    """)
    # Spaces around tokens and trailing comma — both should be handled.
    result = _run_cli("--json", "--todos", "TODO, NEXT,", str(org))
    data = json.loads(result.stdout)
    todos = {item["item_id"]: item["todo"] for item in data}
    # Both keywords recognized correctly (no " NEXT" with leading space).
    assert todos["id-s25-01"] == "TODO"
    assert todos["id-s25-02"] == "NEXT"


# AC2: CLI frozenset split strips whitespace and filters empty tokens.
# exclude_drawers is lowercased by Config.__post_init__, so we verify
# the drawer content is excluded from body (end-to-end).
def test_cli_exclude_drawers_strip_and_filter(tmp_path):
    """S25-AC2: --exclude-drawers 'LOGBOOK, NOTES' strips and filters."""
    org = _write_org(tmp_path, """\
        * Item
          :PROPERTIES:
          :ID: id-s25-03
          :END:
          Visible body text.
          :LOGBOOK:
          logbook secret content
          :END:
          :NOTES:
          notes secret content
          :END:
    """)
    result = _run_cli(
        "--json", "-v",
        "--exclude-drawers", "LOGBOOK, NOTES,",
        str(org),
    )
    data = json.loads(result.stdout)
    assert len(data) == 1
    body = data[0]["body"]
    # Drawer content excluded despite spaces in CLI flag.
    assert "logbook secret content" not in body
    assert "notes secret content" not in body
    assert "Visible body text." in body


# AC3: JSON scalar where list expected → clear error.
def test_config_json_scalar_todos_rejected(tmp_path, org_file):
    """S25-AC3: JSON 'todos' as string instead of list → clear error."""
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"todos": "LOGBOOK"}))
    result = _run_cli("--config", str(config), str(org_file), check=False)
    assert result.returncode != 0
    assert "todos" in result.stderr
    assert "list" in result.stderr.lower()


# AC4: JSON scalar where list expected for frozenset field → clear error.
def test_config_json_scalar_exclude_drawers_rejected(tmp_path, org_file):
    """S25-AC4: JSON 'exclude_drawers' as string → clear error."""
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"exclude_drawers": "LOGBOOK"}))
    result = _run_cli("--config", str(config), str(org_file), check=False)
    assert result.returncode != 0
    assert "exclude_drawers" in result.stderr
    assert "list" in result.stderr.lower()


# AC5: JSON with correct types continues to work.
def test_config_json_correct_types(tmp_path):
    """S25-AC5: JSON config with all list fields as lists works fine."""
    org = _write_org(tmp_path, """\
        * TODO Item
          :PROPERTIES:
          :ID: id-s25-05
          :END:
    """)
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "todos": ["TODO"],
        "dones": ["DONE"],
        "exclude_drawers": ["LOGBOOK"],
        "exclude_blocks": ["src"],
        "exclude_properties": ["CREATED"],
        "tags_exclude_from_inheritance": ["noexport"],
    }))
    result = _run_cli("--json", "--config", str(config), str(org))
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["todo"] == "TODO"
