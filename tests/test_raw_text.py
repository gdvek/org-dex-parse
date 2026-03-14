"""Tests for item tree construction and raw_text collection (S06).

Verifies that parse_file builds the item tree correctly and that each
Item.raw_text contains the complete unfiltered source text for that item,
minus sub-items.  Uses the raw_text.org fixture.
"""
from pathlib import Path

from org_dex_parse import Config, parse_file

FIXTURE = str(Path(__file__).parent / "fixtures" / "raw_text.org")


def _parse():
    """Parse the fixture with default config (all :ID: headings are items)."""
    return parse_file(FIXTURE, Config())


def _items_by_id():
    """Return a dict mapping item_id -> Item for easy lookup."""
    result = _parse()
    return {item.item_id: item for item in result.items}


# --- AC1, AC10: item count and document order ---

def test_item_count_and_order():
    """parse_file returns 4 items in document order."""
    result = _parse()
    assert len(result.items) == 4
    ids = [item.item_id for item in result.items]
    assert ids == ["aaa", "bbb", "ccc", "ddd"]


# --- AC11: structural fields ---

def test_structural_fields():
    """All structural fields populated correctly."""
    items = _items_by_id()

    a = items["aaa"]
    assert a.title == "Item A"
    assert a.level == 1
    assert a.linenumber == 1
    assert a.file_path == FIXTURE

    b = items["bbb"]
    assert b.title == "Item B"
    assert b.level == 2
    assert b.linenumber == 9

    c = items["ccc"]
    assert c.title == "Item C"
    assert c.level == 1
    assert c.linenumber == 16

    d = items["ddd"]
    assert d.title == "Item D"
    assert d.level == 1
    assert d.linenumber == 21


# --- AC9: parent_item_id (transparent traversal) ---

def test_parent_item_id():
    """parent_item_id resolves through scaffolding correctly."""
    items = _items_by_id()

    # Top-level items have no parent.
    assert items["aaa"].parent_item_id is None
    assert items["ccc"].parent_item_id is None
    assert items["ddd"].parent_item_id is None

    # bbb is under scaffolding, parent is aaa.
    assert items["bbb"].parent_item_id == "aaa"


# --- AC2, AC4: raw_text excludes sub-items ---

def test_raw_text_excludes_sub_item():
    """Parent raw_text does not contain sub-item lines."""
    items = _items_by_id()
    raw_a = items["aaa"].raw_text

    # B's heading and body must not appear in A's raw_text.
    assert "** Item B" not in raw_a
    assert ":ID: bbb" not in raw_a
    assert "Body di B." not in raw_a


# --- AC3: raw_text includes scaffolding ---

def test_raw_text_includes_scaffolding():
    """Parent raw_text includes non-item children (scaffolding)."""
    items = _items_by_id()
    raw_a = items["aaa"].raw_text

    assert "** Scaffolding pre-B" in raw_a
    assert "Testo scaffolding pre-B." in raw_a


# --- AC5: scaffolding after last sub-item belongs to parent ---

def test_raw_text_scaffolding_after_sub_item():
    """Scaffolding after the last sub-item belongs to the parent."""
    items = _items_by_id()
    raw_a = items["aaa"].raw_text

    assert "** Scaffolding post-B" in raw_a
    assert "Testo scaffolding post-B." in raw_a


# --- AC6: interleaved scaffolding attributed correctly ---

def test_raw_text_interleaved():
    """Scaffolding interleaved with sub-items: both scaffoldings in parent,
    sub-item excluded."""
    items = _items_by_id()
    raw_a = items["aaa"].raw_text

    # Both scaffolding sections belong to A.
    assert "Scaffolding pre-B" in raw_a
    assert "Scaffolding post-B" in raw_a

    # B is excluded.
    assert "Item B" not in raw_a
    assert "Body di B." not in raw_a


# --- AC7: leaf item raw_text = complete heading + body ---

def test_raw_text_leaf_item():
    """Leaf item (no children): raw_text is the full node text."""
    items = _items_by_id()
    raw_c = items["ccc"].raw_text

    assert raw_c == (
        "* Item C\n"
        "  :PROPERTIES:\n"
        "  :ID: ccc\n"
        "  :END:\n"
        "  Body di C."
    )


# --- AC8: item with no body ---

def test_raw_text_no_body():
    """Item with no body: raw_text is heading + PROPERTIES only."""
    items = _items_by_id()
    raw_d = items["ddd"].raw_text

    assert raw_d == (
        "* Item D\n"
        "  :PROPERTIES:\n"
        "  :ID: ddd\n"
        "  :END:"
    )
