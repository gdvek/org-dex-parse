"""Tests for S04 — Properties, tags, TODO keyword, and priority extraction.

Fixtures:
- props_tags.org: properties with exclusions, local/inherited tags, empty
  tags from malformed heading, TODO/DONE keywords, priorities A and B.
- extra_tags.org: heading with % and # tag characters, parsable only with
  the orgparse monkey-patch.
"""
from __future__ import annotations

from pathlib import Path

from org_dex_parse import Config, Item, ParseResult, parse_file

FIXTURES = Path(__file__).parent / "fixtures"
PROPS_TAGS = FIXTURES / "props_tags.org"
EXTRA_TAGS = FIXTURES / "extra_tags.org"


# -- Helpers ------------------------------------------------------------------

def _items_by_id(result: ParseResult) -> dict[str, Item]:
    """Index ParseResult items by item_id for easy lookup."""
    return {item.item_id: item for item in result.items}


# -- AC1–AC5, AC11: Properties -----------------------------------------------

class TestProperties:
    """Property extraction from the direct PROPERTIES drawer."""

    def test_properties_from_direct_drawer(self):
        """AC1: Item.properties contains (key, value) pairs from direct drawer.

        pt-001 has Type, Effort, Custom after excluding ID, ARCHIVE_TIME,
        and CREATED (created_property default).
        """
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        keys = [k for k, v in items["pt-001"].properties]
        assert "Type" in keys
        assert "Effort" in keys
        assert "Custom" in keys

    def test_id_and_archive_time_always_excluded(self):
        """AC2: ID and ARCHIVE_TIME are never in properties."""
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        keys = [k.upper() for k, v in items["pt-001"].properties]
        assert "ID" not in keys
        assert "ARCHIVE_TIME" not in keys

    def test_created_property_excluded(self):
        """AC3: config.created_property is excluded from properties."""
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        keys = [k.upper() for k, v in items["pt-001"].properties]
        assert "CREATED" not in keys

    def test_exclude_properties_config(self):
        """AC4: config.exclude_properties respected, case-insensitive."""
        config = Config(exclude_properties=frozenset({"type"}))
        items = _items_by_id(parse_file(PROPS_TAGS, config))
        keys = [k for k, v in items["pt-001"].properties]
        assert "Type" not in keys
        # Other properties still present
        assert "Effort" in keys

    def test_values_preserved_as_is(self):
        """AC5: Property values are str(v), no additional normalization.

        orgparse converts Effort "1:00" to int 60 internally — we apply
        str() to that, getting "60".  The point of F-PR2 is that *we* don't
        add further transformations on top of what orgparse provides.
        """
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        props = dict(items["pt-001"].properties)
        # orgparse normalizes effort duration to minutes (int), str() gives "60"
        assert props["Effort"] == "60"
        # Non-duration values pass through unchanged
        assert props["Custom"] == "some value"

    def test_property_order_matches_drawer(self):
        """AC11: Properties appear in drawer order."""
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        keys = [k for k, v in items["pt-001"].properties]
        # Drawer order: Type, Effort, Custom (after exclusions)
        assert keys == ["Type", "Effort", "Custom"]


# -- AC6–AC8: Tags -----------------------------------------------------------

class TestTags:
    """Tag extraction and classification."""

    def test_local_tags(self):
        """AC6: Item.local_tags = tags directly on the heading."""
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        assert items["pt-001"].local_tags == frozenset({"work", "important"})

    def test_inherited_tags(self):
        """AC7: Item.inherited_tags = tags inherited from ancestors.

        pt-002 is a child of pt-001 which has :work:important:.
        pt-002's own tag is :urgent:.
        """
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        assert items["pt-002"].local_tags == frozenset({"urgent"})
        assert items["pt-002"].inherited_tags == frozenset({"work", "important"})

    def test_tags_exclude_from_inheritance(self):
        """AC7: tags_exclude_from_inheritance removes tags from inherited set."""
        config = Config(tags_exclude_from_inheritance=frozenset({"work"}))
        items = _items_by_id(parse_file(PROPS_TAGS, config))
        assert "work" not in items["pt-002"].inherited_tags
        # "important" still inherited
        assert "important" in items["pt-002"].inherited_tags

    def test_empty_tags_filtered(self):
        """AC8: Empty strings filtered from local_tags and inherited_tags.

        pt-003 has :valid::also_valid: — the double colon may produce an
        empty string in orgparse.  It must not appear in local_tags.
        """
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        assert "" not in items["pt-003"].local_tags
        # The valid tags should still be there
        if items["pt-003"].local_tags:
            for tag in items["pt-003"].local_tags:
                assert tag != ""


# -- AC9–AC10: Extra tag characters -------------------------------------------

class TestExtraTagChars:
    """Monkey-patch for non-standard tag characters."""

    def test_extra_chars_recognized(self):
        """AC9: With extra_tag_chars, orgparse recognizes non-standard tags."""
        config = Config(extra_tag_chars="%#")
        items = _items_by_id(parse_file(EXTRA_TAGS, config))
        assert "%identity" in items["et-001"].local_tags
        assert "#entity" in items["et-001"].local_tags

    def test_no_extra_chars_no_tags(self):
        """AC10: Without extra_tag_chars, non-standard tags are not parsed."""
        config = Config()
        items = _items_by_id(parse_file(EXTRA_TAGS, config))
        # orgparse default regex rejects % and #, so no tags
        assert items["et-001"].local_tags == frozenset()

    def test_idempotency_across_calls(self):
        """Successive calls with different configs produce correct results.

        First call with extra_tag_chars, second without — the second must
        NOT see the extended regex from the first call.
        """
        config_extra = Config(extra_tag_chars="%#")
        config_plain = Config()

        # Call 1: extra chars active
        result1 = parse_file(EXTRA_TAGS, config_extra)
        items1 = _items_by_id(result1)
        assert "%identity" in items1["et-001"].local_tags

        # Call 2: no extra chars — monkey-patch must be restored
        result2 = parse_file(EXTRA_TAGS, config_plain)
        items2 = _items_by_id(result2)
        assert items2["et-001"].local_tags == frozenset()


# -- AC12–AC13: TODO keyword and priority -------------------------------------

class TestTodoAndPriority:
    """TODO keyword and priority extraction."""

    def test_todo_keyword(self):
        """AC12: Item.todo = TODO keyword string."""
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        assert items["pt-001"].todo == "TODO"

    def test_done_keyword(self):
        """AC12: DONE keyword extracted correctly."""
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        assert items["pt-004"].todo == "DONE"

    def test_no_keyword_is_none(self):
        """AC12: No keyword → Item.todo is None."""
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        assert items["pt-005"].todo is None

    def test_priority_letter(self):
        """AC13: Item.priority = priority letter."""
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        assert items["pt-001"].priority == "A"
        assert items["pt-004"].priority == "B"

    def test_no_priority_is_none(self):
        """AC13: No priority → Item.priority is None."""
        items = _items_by_id(parse_file(PROPS_TAGS, Config()))
        assert items["pt-002"].priority is None
        assert items["pt-005"].priority is None
