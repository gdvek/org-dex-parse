"""Tests for parser.py — tree walk, item discrimination, parent resolution.

Story S03: Partizionamento albero e discriminazione item.
Fixture: tree_basic.org (6 items with default predicate, 5 with remi predicate).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from org_dex_parse import Config, Item, ParseResult, parse_file

FIXTURES = Path(__file__).parent / "fixtures"
TREE_BASIC = FIXTURES / "tree_basic.org"
TREE_PARENT_NO_ID = FIXTURES / "tree_parent_no_id.org"

# Remi-style predicate: only headings with :Type: property count as items.
REMI_PREDICATE = lambda h: h.get_property("Type") is not None


# -- Helpers ------------------------------------------------------------------

def _items_by_id(result: ParseResult) -> dict[str, Item]:
    """Index ParseResult items by item_id for easy lookup."""
    return {item.item_id: item for item in result.items}


# -- AC1, AC2, AC7, AC8, AC10 ------------------------------------------------

class TestParseFileBasic:
    """Basic parse_file behavior: return type, item detection, skeleton."""

    def test_returns_parse_result(self):
        """AC1: parse_file returns a ParseResult instance."""
        result = parse_file(TREE_BASIC, Config())
        assert isinstance(result, ParseResult)

    def test_items_with_id_detected(self):
        """AC2: headings with :ID: + default predicate → 6 items."""
        result = parse_file(TREE_BASIC, Config())
        assert len(result.items) == 6

    def test_top_level_parent_none(self):
        """AC7: top-level items have parent_item_id is None."""
        items = _items_by_id(parse_file(TREE_BASIC, Config()))
        # item-001, item-004, item-005 are top-level
        assert items["item-001"].parent_item_id is None
        assert items["item-004"].parent_item_id is None
        assert items["item-005"].parent_item_id is None

    def test_skeleton_fields_populated(self):
        """AC8: only 6 structural fields populated; all others at defaults."""
        items = _items_by_id(parse_file(TREE_BASIC, Config()))
        item = items["item-001"]

        # Structural fields are populated
        assert item.title != ""
        assert item.item_id == "item-001"
        assert item.level == 1
        assert item.linenumber > 0
        assert item.file_path == str(TREE_BASIC)

        # All optional fields at defaults
        assert item.todo is None
        assert item.priority is None
        assert item.local_tags == frozenset()
        assert item.inherited_tags == frozenset()
        assert item.scheduled is None
        assert item.deadline is None
        assert item.closed is None
        assert item.created is None
        assert item.archived_on is None
        assert item.active_ts == ()
        assert item.inactive_ts == ()
        assert item.range_ts == ()
        assert item.clock == ()
        assert item.state_changes == ()
        assert item.body is None
        assert item.raw_text == ""
        assert item.links == ()
        assert item.properties == ()

    def test_item_order_matches_document(self):
        """Items in result follow document order."""
        result = parse_file(TREE_BASIC, Config())
        ids = [item.item_id for item in result.items]
        assert ids == [
            "item-001", "item-002", "item-003",
            "item-004", "item-005", "item-006",
        ]


# -- AC3, AC4 ----------------------------------------------------------------

class TestItemDiscrimination:
    """Predicate-based item filtering."""

    def test_no_id_not_item(self):
        """AC3: headings without :ID: are never items."""
        result = parse_file(TREE_BASIC, Config())
        titles = [item.title for item in result.items]
        # "Scaffolding section" and "Heading without ID" have no :ID:
        assert "Scaffolding section" not in titles
        assert "Heading without ID" not in titles

    def test_id_but_predicate_false(self):
        """AC4: :ID: present but predicate returns false → not an item."""
        config = Config(item_predicate=REMI_PREDICATE)
        result = parse_file(TREE_BASIC, config)
        ids = [item.item_id for item in result.items]
        # item-004 has :ID: but no :Type: → excluded by remi predicate
        assert "item-004" not in ids

    def test_predicate_changes_result_count(self):
        """Same file, different predicate → different item count."""
        default_result = parse_file(TREE_BASIC, Config())
        remi_result = parse_file(TREE_BASIC, Config(item_predicate=REMI_PREDICATE))
        # Default: 6 items (all with :ID:).  Remi: 5 (item-004 excluded).
        assert len(default_result.items) == 6
        assert len(remi_result.items) == 5

    def test_scaffolding_only_file_empty_result(self):
        """File with no :ID: headings → ParseResult(items=())."""
        # Create a minimal scaffolding-only content via a temp file
        import tempfile
        content = "#+TITLE: Empty\n\n* Section A\n** Section B\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".org", delete=False
        ) as f:
            f.write(content)
            f.flush()
            result = parse_file(f.name, Config())
        assert result.items == ()


# -- AC6, AC7 ----------------------------------------------------------------

class TestParentResolution:
    """Transparent traversal: scaffolding is invisible to parent lookup."""

    def test_parent_skips_scaffolding(self):
        """AC6: item under scaffolding → parent is nearest item ancestor."""
        items = _items_by_id(parse_file(TREE_BASIC, Config()))
        # item-002 is under "Scaffolding section" (no :ID:) → parent is item-001
        assert items["item-002"].parent_item_id == "item-001"

    def test_direct_child_parent(self):
        """Direct child item → parent is the direct parent item."""
        items = _items_by_id(parse_file(TREE_BASIC, Config()))
        # item-003 is a direct child of item-001
        assert items["item-003"].parent_item_id == "item-001"

    def test_deep_nesting_skips_scaffolding(self):
        """AC6: item under 2 levels of scaffolding → parent is item ancestor."""
        items = _items_by_id(parse_file(TREE_BASIC, Config()))
        # item-006 is under "Level 2 scaffolding" / "Level 3 scaffolding"
        # → parent is item-005
        assert items["item-006"].parent_item_id == "item-005"

    def test_parent_without_id(self):
        """Parent has :Type: but no :ID: → child parent_item_id is None."""
        items = _items_by_id(
            parse_file(TREE_PARENT_NO_ID, Config())
        )
        assert items["child-001"].parent_item_id is None


# -- AC9 ---------------------------------------------------------------------

class TestOrgEnv:
    """TODO/DONE keywords passed to orgparse via OrgEnv."""

    def test_title_strips_todo_keyword(self):
        """AC9: with todos in Config, heading text excludes TODO keyword."""
        config = Config(todos=("TODO", "NEXT", "DOING"), dones=("DONE", "CANCELED"))
        items = _items_by_id(parse_file(TREE_BASIC, config))
        # "* TODO Project Alpha" → title should be "Project Alpha"
        assert items["item-001"].title == "Project Alpha"
        # "*** NEXT Task under scaffolding" → "Task under scaffolding"
        assert items["item-002"].title == "Task under scaffolding"

    def test_title_without_todos_includes_keyword(self):
        """Without todos in Config and no #+TODO in file, keyword is part of heading."""
        import tempfile
        # File without #+TODO line — orgparse has no keyword definitions
        content = (
            "* TODO My task\n"
            "  :PROPERTIES:\n"
            "  :ID: kw-001\n"
            "  :END:\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".org", delete=False
        ) as f:
            f.write(content)
            f.flush()
            result = parse_file(f.name, Config())
        # Without any keyword source, "TODO" is part of the heading
        assert result.items[0].title == "TODO My task"


# -- Edge cases ---------------------------------------------------------------

class TestEdgeCases:
    """Boundary conditions."""

    def test_empty_file(self):
        """Empty org file → ParseResult(items=())."""
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".org", delete=False
        ) as f:
            f.write("")
            f.flush()
            result = parse_file(f.name, Config())
        assert result.items == ()
