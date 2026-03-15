"""Tests for S11 — parent cache and tag inheritance pre-computation.

Verifies that the optimized parent_map and inherited_tags_map produce
identical results to orgparse's node.parent / node.tags.  These tests
must pass both BEFORE and AFTER the optimization (semantic equivalence).

Fixture: tag_inheritance.org (3 items with FILETAGS, scaffolding tags,
multi-level inheritance, and duplicate tags).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from org_dex_parse import Config, Item, ParseResult, parse_file

FIXTURES = Path(__file__).parent / "fixtures"
TAG_INHERITANCE = FIXTURES / "tag_inheritance.org"


# -- Helpers ------------------------------------------------------------------

def _items_by_id(result: ParseResult) -> dict[str, Item]:
    """Index ParseResult items by item_id for easy lookup."""
    return {item.item_id: item for item in result.items}


# -- FILETAGS inheritance (AC3) -----------------------------------------------

class TestFiletagsInheritance:
    """#+FILETAGS propagate as inherited tags to all items."""

    def test_filetags_inherited_by_top_level(self):
        """Top-level item inherits FILETAGS from file root.

        ti-001 has local :alpha: and should inherit :filetag: from
        #+FILETAGS.
        """
        items = _items_by_id(parse_file(TAG_INHERITANCE, Config()))
        assert "filetag" in items["ti-001"].inherited_tags

    def test_filetags_inherited_by_deep_item(self):
        """Deeply nested item also inherits FILETAGS.

        ti-002 is under scaffolding but FILETAGS reach it.
        """
        items = _items_by_id(parse_file(TAG_INHERITANCE, Config()))
        assert "filetag" in items["ti-002"].inherited_tags


# -- Inheritance through scaffolding (AC3) ------------------------------------

class TestScaffoldingTagInheritance:
    """Tags on non-item headings propagate to item descendants."""

    def test_scaffolding_tags_inherited(self):
        """Tags on scaffolding heading reach child items.

        ti-002 is under "Scaffolding heading :beta:".  :beta: should
        appear in inherited_tags even though the scaffolding heading
        is not an item.
        """
        items = _items_by_id(parse_file(TAG_INHERITANCE, Config()))
        assert "beta" in items["ti-002"].inherited_tags

    def test_multi_level_accumulation(self):
        """Tags accumulate across multiple levels.

        ti-002 should inherit:
        - :filetag: from #+FILETAGS (root)
        - :alpha: from ti-001 (parent item)
        - :beta: from scaffolding heading (non-item ancestor)
        """
        items = _items_by_id(parse_file(TAG_INHERITANCE, Config()))
        expected = frozenset({"filetag", "alpha", "beta"})
        assert items["ti-002"].inherited_tags == expected

    def test_local_tags_not_in_inherited(self):
        """Local tags do not appear in inherited_tags.

        ti-002 has local :gamma:.  It must NOT be in inherited_tags.
        """
        items = _items_by_id(parse_file(TAG_INHERITANCE, Config()))
        assert "gamma" not in items["ti-002"].inherited_tags
        assert "gamma" in items["ti-002"].local_tags


# -- Duplicate tag: local + ancestor (AC3) ------------------------------------

class TestDuplicateTagHandling:
    """Tag present on both node and ancestor appears only in local_tags."""

    def test_duplicate_tag_only_in_local(self):
        """ti-003 has :alpha: locally and inherits :alpha: from ti-001.

        :alpha: must appear in local_tags only, not in inherited_tags.
        """
        items = _items_by_id(parse_file(TAG_INHERITANCE, Config()))
        assert "alpha" in items["ti-003"].local_tags
        assert "alpha" not in items["ti-003"].inherited_tags

    def test_duplicate_tag_filetags_still_inherited(self):
        """Even with duplicate :alpha:, other inherited tags are present.

        ti-003 should still inherit :filetag: from #+FILETAGS.
        """
        items = _items_by_id(parse_file(TAG_INHERITANCE, Config()))
        assert items["ti-003"].inherited_tags == frozenset({"filetag"})
