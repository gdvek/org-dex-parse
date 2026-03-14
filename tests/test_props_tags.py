"""Tests for S07 — properties, tags, TODO keyword, and priority extraction.

Fixtures: props_tags.org (5 items with properties, tags, TODO, priority),
extra_tags.org (1 item with non-standard tag characters).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from org_dex_parse import Config, Item, ParseResult, parse_file

FIXTURES = Path(__file__).parent / "fixtures"
PROPS_TAGS = FIXTURES / "props_tags.org"
EXTRA_TAGS = FIXTURES / "extra_tags.org"

# Config matching the #+TODO line in props_tags.org.
PT_CONFIG = Config(todos=("TODO", "NEXT"), dones=("DONE",))


# -- Helpers ------------------------------------------------------------------

def _items_by_id(result: ParseResult) -> dict[str, Item]:
    """Index ParseResult items by item_id for easy lookup."""
    return {item.item_id: item for item in result.items}


def _props_dict(item: Item) -> dict[str, str]:
    """Convert Item.properties tuple to dict for easier assertions."""
    return dict(item.properties)


# -- Properties (AC1–AC6) ----------------------------------------------------

class TestProperties:
    """Property extraction from the direct PROPERTIES drawer."""

    def test_properties_from_direct_drawer(self):
        """AC1: properties contains (key, value) pairs from PROPERTIES drawer.

        pt-001 has ID, Type, Effort, CREATED, ARCHIVE_TIME, Custom.
        After always-excluded (ID, ARCHIVE_TIME, CREATED): Type, Effort, Custom.
        """
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        props = _props_dict(items["pt-001"])
        assert "Type" in props
        assert "Effort" in props
        assert "Custom" in props

    def test_id_always_excluded(self):
        """AC2: ID is always excluded from properties."""
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        for item in items.values():
            keys = {k for k, _ in item.properties}
            assert "ID" not in keys

    def test_archive_time_always_excluded(self):
        """AC2: ARCHIVE_TIME is always excluded from properties."""
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        props = _props_dict(items["pt-001"])
        assert "ARCHIVE_TIME" not in props

    def test_created_property_excluded(self):
        """AC3: config.created_property (default 'CREATED') excluded."""
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        props = _props_dict(items["pt-001"])
        assert "CREATED" not in props

    def test_custom_exclude_properties(self):
        """AC4: config.exclude_properties removes matching properties."""
        config = Config(
            todos=("TODO", "NEXT"), dones=("DONE",),
            exclude_properties=frozenset({"type"}),
        )
        items = _items_by_id(parse_file(PROPS_TAGS, config))
        props = _props_dict(items["pt-001"])
        assert "Type" not in props
        # Other properties still present
        assert "Effort" in props

    def test_exclude_case_insensitive(self):
        """AC4: exclude_properties matching is case-insensitive.

        exclude_properties={'effort'} (lowercase) should exclude 'Effort'
        (mixed case) from the drawer.
        """
        config = Config(
            todos=("TODO", "NEXT"), dones=("DONE",),
            exclude_properties=frozenset({"effort"}),
        )
        items = _items_by_id(parse_file(PROPS_TAGS, config))
        props = _props_dict(items["pt-001"])
        assert "Effort" not in props

    def test_values_preserved_as_is(self):
        """AC5: property values preserved as-is via str(), no normalization.

        We apply str(v) to preserve whatever orgparse returns.  Note:
        orgparse itself normalizes Effort '1:00' → 60 (int, minutes).
        We don't add further processing — str(60) = '60'.
        Custom property 'some value' comes through unchanged.
        """
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        props = _props_dict(items["pt-001"])
        assert props["Custom"] == "some value"
        # Effort is normalized by orgparse, not by us — str(60) = "60"
        assert props["Effort"] == "60"

    def test_properties_order(self):
        """AC6: property order follows drawer insertion order."""
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        keys = [k for k, _ in items["pt-001"].properties]
        # After excluding ID, ARCHIVE_TIME, CREATED: Type, Effort, Custom
        assert keys == ["Type", "Effort", "Custom"]

    def test_item_without_extra_properties(self):
        """Item with only :ID: and :Type: → properties = (('Type', 'task'),)."""
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        assert items["pt-002"].properties == (("Type", "task"),)


# -- Tags (AC7–AC9) ----------------------------------------------------------

class TestTags:
    """Tag extraction: local, inherited, empty filtering."""

    def test_local_tags(self):
        """AC7: local_tags = tags directly on the heading."""
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        assert items["pt-001"].local_tags == frozenset({"work", "important"})

    def test_inherited_tags(self):
        """AC8: inherited_tags = parent tags minus local tags.

        pt-002 is a child of pt-001 (:work:important:).
        pt-002 has local :urgent: and inherits :work:important: from parent.
        """
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        assert items["pt-002"].local_tags == frozenset({"urgent"})
        assert items["pt-002"].inherited_tags == frozenset({"work", "important"})

    def test_inherited_with_exclusion(self):
        """AC8: tags_exclude_from_inheritance removes tags from inherited set."""
        config = Config(
            todos=("TODO", "NEXT"), dones=("DONE",),
            tags_exclude_from_inheritance=frozenset({"work"}),
        )
        items = _items_by_id(parse_file(PROPS_TAGS, config))
        assert items["pt-002"].inherited_tags == frozenset({"important"})

    def test_empty_tags_filtered(self):
        """AC9: empty tags from malformed headings ('::') are filtered out.

        pt-003 heading is 'Note with malformed tag :valid::also_valid:'.
        The '::' produces an empty string — must be filtered (fix F-TG1).
        """
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        assert "" not in items["pt-003"].local_tags
        assert "valid" in items["pt-003"].local_tags
        assert "also_valid" in items["pt-003"].local_tags


# -- Extra tag chars (AC10–AC11) ----------------------------------------------

class TestExtraTags:
    """Monkey-patch for non-standard tag characters (HACK S04)."""

    def test_extra_chars_recognized(self):
        """AC10: extra_tag_chars='%#' → orgparse recognizes % and # in tags."""
        config = Config(extra_tag_chars="%#")
        items = _items_by_id(parse_file(EXTRA_TAGS, config))
        assert "%identity" in items["et-001"].local_tags
        assert "#entity" in items["et-001"].local_tags

    def test_no_extra_chars_no_tags(self):
        """AC11: without extra_tag_chars, orgparse ignores % and # in tags.

        The tags stay glued to the heading text.  local_tags should not
        contain '%identity' or '#entity'.
        """
        config = Config()
        items = _items_by_id(parse_file(EXTRA_TAGS, config))
        assert "%identity" not in items["et-001"].local_tags
        assert "#entity" not in items["et-001"].local_tags


# -- TODO and priority (AC12–AC13) --------------------------------------------

class TestTodoPriority:
    """TODO keyword and priority extraction."""

    def test_todo_populated(self):
        """AC12: Item.todo = TODO keyword when present."""
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        assert items["pt-001"].todo == "TODO"

    def test_done_keyword(self):
        """AC12: DONE keyword is also captured."""
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        assert items["pt-004"].todo == "DONE"

    def test_todo_none_when_absent(self):
        """AC12: Item.todo = None when no keyword on heading."""
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        assert items["pt-005"].todo is None

    def test_priority_populated(self):
        """AC13: Item.priority = letter when priority cookie present."""
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        assert items["pt-001"].priority == "A"

    def test_priority_none_when_absent(self):
        """AC13: Item.priority = None when no priority cookie."""
        items = _items_by_id(parse_file(PROPS_TAGS, PT_CONFIG))
        assert items["pt-002"].priority is None
