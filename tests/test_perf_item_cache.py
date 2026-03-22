"""Tests for S29 — is_item cache (pre-computed item map).

Verifies that the item predicate is evaluated exactly once per node,
not re-evaluated on every walk.  Uses tree_basic.org which has 6 nodes
with :ID: and 4 without.  The predicate is called:
- 6 times via item_map (once per :ID: node, cached for all walks)
- 4 times via L12 check (S19g, once per non-:ID: node when predicate
  is explicit — detects quasi-items missing :ID:)
Total: 10 calls with explicit predicate.
"""
from __future__ import annotations

from pathlib import Path

from org_dex_parse import Config, parse_file

FIXTURES = Path(__file__).parent / "fixtures"
TREE_BASIC = FIXTURES / "tree_basic.org"


class TestItemPredicateEvaluatedOnce:
    """AC1: is_item evaluates the predicate once per node, not per walk."""

    def test_predicate_called_once_per_node_with_id(self):
        """Predicate called exactly 10 times on tree_basic.org.

        tree_basic.org has 6 headings with :ID: and 4 without.
        - 6 calls via item_map (once per :ID: node, cached for all walks)
        - 4 calls via L12 check (S19g: once per non-:ID: node, explicit
          predicate triggers quasi-item detection)
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

        # 6 item_map + 4 L12 = 10 predicate calls.
        assert call_count == 10
        # All 6 are items (predicate always returns True).
        assert len(result.items) == 6

    def test_predicate_called_once_with_filtering(self):
        """Same total even when predicate filters some items out.

        Remi predicate rejects item-004 (no :Type:), but the predicate
        is still called 10 times: 6 via item_map + 4 via L12 check
        (S19g: explicit predicate → quasi-item detection on non-:ID: nodes).
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

        # 6 item_map + 4 L12 = 10 predicate calls.
        assert call_count == 10
        # But only 5 items pass (item-004 rejected).
        assert len(result.items) == 5
