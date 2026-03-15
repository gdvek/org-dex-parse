"""Tests for S09d — body text extraction.

Fixtures: body.org (11 items testing plain body collection, drawer/block
exclusion, scaffolding, item boundaries, empty body, case-insensitive
matching, and block arguments).
"""
from __future__ import annotations

from pathlib import Path

from org_dex_parse import Config, Item, ParseResult, parse_file

FIXTURES = Path(__file__).parent / "fixtures"
BODY_ORG = FIXTURES / "body.org"

# Config with NOTES drawer and COMMENT/SRC blocks excluded.
# Covers AC3, AC4, AC10, AC11.  LOGBOOK is always excluded (hardcoded).
CONFIG = Config(
    exclude_drawers=frozenset({"NOTES"}),
    exclude_blocks=frozenset({"COMMENT", "SRC"}),
)


# -- Helpers ------------------------------------------------------------------

def _items_by_id(result: ParseResult) -> dict[str, Item]:
    """Index ParseResult items by item_id for easy lookup."""
    return {item.item_id: item for item in result.items}


def _parse() -> dict[str, Item]:
    """Parse body.org and return items indexed by id."""
    return _items_by_id(parse_file(str(BODY_ORG), CONFIG))


# -- AC1: plain text (link-resolved, markup preserved) -----------------------

def test_ac1_plain_markup():
    """AC1: get_body('plain') resolves links, preserves bold/italic."""
    items = _parse()
    body = items["body-ac1"].body
    # Links resolved: [[https://example.com][un link]] → "un link"
    assert "un link" in body
    assert "[[" not in body
    # Bold/italic markers preserved by orgparse's plain format.
    assert "*bold*" in body
    assert "/italic/" in body


# -- AC2: LOGBOOK excluded (hardcoded) ----------------------------------------

def test_ac2_logbook_excluded():
    """AC2: LOGBOOK drawer content excluded from body."""
    items = _parse()
    body = items["body-ac2"].body
    assert body == "Testo dopo logbook."
    assert "LOGBOOK" not in body
    assert "State" not in body
    assert "CLOCK" not in body


# -- AC3: configurable drawer exclusion ---------------------------------------

def test_ac3_configurable_drawer():
    """AC3: drawer in config.exclude_drawers excluded from body."""
    items = _parse()
    body = items["body-ac3"].body
    assert body == "Testo dopo drawer."
    assert "NOTES" not in body
    assert "Appunti" not in body


# -- AC4: configurable block exclusion ----------------------------------------

def test_ac4_configurable_block():
    """AC4: block in config.exclude_blocks excluded from body."""
    items = _parse()
    body = items["body-ac4"].body
    assert body == "Testo dopo block."
    assert "COMMENT" not in body
    assert "Commento" not in body


# -- AC5: preserved drawer and block ------------------------------------------

def test_ac5_preserved_drawer_and_block():
    """AC5: drawers/blocks NOT in exclusion lists are preserved in body."""
    items = _parse()
    body = items["body-ac5"].body
    # :CUSTOM: drawer preserved (not in exclude_drawers).
    assert ":CUSTOM:" in body
    assert "Contenuto custom drawer." in body
    # #+BEGIN_EXAMPLE block preserved (not in exclude_blocks).
    assert "#+BEGIN_EXAMPLE" in body
    assert "Esempio preservato." in body
    assert "Testo finale." in body


# -- AC6, AC7: scaffold heading and body included -----------------------------

def test_ac6_ac7_scaffold_heading_and_body():
    """AC6/AC7: heading and body of scaffold children included."""
    items = _parse()
    body = items["body-ac6"].body
    # Item's own body.
    assert "Testo item." in body
    # Scaffold child heading (node.heading) included (fix F-BD3).
    assert "Scaffold child" in body
    # Scaffold child body included.
    assert "Testo scaffolding." in body


# -- AC8: sub-item boundary ---------------------------------------------------

def test_ac8_subitem_boundary():
    """AC8: sub-items (heading with :ID: + predicate) excluded from body."""
    items = _parse()
    body = items["body-ac8"].body
    assert body == "Testo genitore."
    # Sub-item content NOT in parent body.
    assert "sub-item" not in body.lower()


# -- AC9: empty body → None ---------------------------------------------------

def test_ac9a_empty_body():
    """AC9: item with no body text → body is None."""
    items = _parse()
    assert items["body-ac9a"].body is None


def test_ac9b_empty_after_filter():
    """AC9: body that becomes empty after LOGBOOK filter → None."""
    items = _parse()
    assert items["body-ac9b"].body is None


# -- AC10: case-insensitive drawer exclusion -----------------------------------

def test_ac10_case_insensitive():
    """AC10: drawer/block exclusion is case-insensitive."""
    items = _parse()
    body = items["body-ac10"].body
    assert body == "Testo dopo."
    # :Logbook: (mixed case) excluded by hardcoded LOGBOOK filter.
    assert "Logbook" not in body
    assert "State" not in body
    # :notes: (lowercase) excluded by config.exclude_drawers={"NOTES"}.
    assert "notes" not in body
    assert "Appunti" not in body


# -- AC11: block with arguments after name ------------------------------------

def test_ac11_block_with_args():
    """AC11: #+begin_src python :tangle yes → SRC matched, block excluded."""
    items = _parse()
    body = items["body-ac11"].body
    assert body == "Testo dopo block."
    assert "begin_src" not in body
    assert "print" not in body
