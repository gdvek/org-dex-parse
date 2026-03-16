"""Tests for S29 — is_item cache (pre-computed item map).

Verifies that the item predicate is evaluated exactly once per node,
not re-evaluated on every walk.  Uses tree_basic.org which has 6 nodes
with :ID: — the predicate should be called exactly 6 times (is_item
short-circuits on missing :ID: before calling the predicate).
"""
from __future__ import annotations

from pathlib import Path

from org_dex_parse import Config, parse_file

FIXTURES = Path(__file__).parent / "fixtures"
TREE_BASIC = FIXTURES / "tree_basic.org"


class TestItemPredicateEvaluatedOnce:
    """AC1: is_item evaluates the predicate once per node, not per walk."""

    def test_predicate_called_once_per_node_with_id(self):
        """Predicate called exactly 6 times on tree_basic.org.

        tree_basic.org has 6 headings with :ID: and 4 without.
        is_item checks :ID: first — the predicate is only called when
        :ID: is present.  With the pre-computed item_map, each node is
        evaluated exactly once regardless of how many walks traverse it.
        """
        call_count = 0

        def counting_predicate(node):
            nonlocal call_count
            call_count += 1
            return True

        config = Config(
            item_predicate=counting_predicate,
            todos=("TODO", "NEXT", "DOING"),
            dones=("DONE", "CANCELED"),
        )
        result = parse_file(TREE_BASIC, config)

        # 6 headings with :ID: → predicate called exactly 6 times.
        assert call_count == 6
        # All 6 are items (predicate always returns True).
        assert len(result.items) == 6

    def test_predicate_called_once_with_filtering(self):
        """Same count even when predicate filters some items out.

        Remi predicate rejects item-004 (no :Type:), but the predicate
        is still called exactly 6 times — once per :ID: node.
        """
        call_count = 0

        def counting_remi_predicate(node):
            nonlocal call_count
            call_count += 1
            return node.get_property("Type") is not None

        config = Config(
            item_predicate=counting_remi_predicate,
            todos=("TODO", "NEXT", "DOING"),
            dones=("DONE", "CANCELED"),
        )
        result = parse_file(TREE_BASIC, config)

        # Predicate still called exactly 6 times.
        assert call_count == 6
        # But only 5 items pass (item-004 rejected).
        assert len(result.items) == 5
