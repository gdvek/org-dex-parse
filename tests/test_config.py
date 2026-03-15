"""Tests for org_dex_parse.config — parser configuration.

Covers AC5 (item_predicate), AC6 (case normalization).
"""
from dataclasses import FrozenInstanceError

import pytest

from org_dex_parse import Config


# --- AC5: item_predicate ---


class TestConfigPredicate:
    """Config.item_predicate accepts callable, list, or None."""

    def test_default_predicate(self):
        config = Config()
        # Default predicate accepts anything.
        assert config.item_predicate(None) is True
        assert config.item_predicate("anything") is True
        assert config.item_predicate(42) is True

    def test_custom_predicate(self):
        pred = lambda h: hasattr(h, "properties")
        config = Config(item_predicate=pred)
        assert config.item_predicate is pred

    def test_predicate_from_list(self):
        """AC4: list is compiled to callable via evaluator."""
        config = Config(item_predicate=["property", "Type"])
        assert callable(config.item_predicate)

        # Verify it actually works on a node-like object.
        class FakeNode:
            def get_property(self, name):
                return "note" if name == "Type" else None

        assert config.item_predicate(FakeNode()) is True

    def test_predicate_from_none(self):
        """AC4: None → default predicate (always True)."""
        config = Config(item_predicate=None)
        assert callable(config.item_predicate)
        assert config.item_predicate("anything") is True

    def test_predicate_invalid_raises(self):
        """AC4: invalid type raises ValueError."""
        with pytest.raises(ValueError):
            Config(item_predicate=42)

    def test_frozen(self):
        config = Config()
        with pytest.raises(FrozenInstanceError):
            config.todos = ("NEW",)


# --- AC6: case normalization ---


class TestConfigCaseNormalization:
    """Config normalizes exclude_drawers/blocks/properties to lowercase."""

    def test_exclude_drawers_lowered(self):
        config = Config(exclude_drawers=frozenset({"LOGBOOK", "Custom"}))
        assert config.exclude_drawers == frozenset({"logbook", "custom"})

    def test_exclude_blocks_lowered(self):
        config = Config(exclude_blocks=frozenset({"COMMENT", "SRC"}))
        assert config.exclude_blocks == frozenset({"comment", "src"})

    def test_exclude_properties_lowered(self):
        config = Config(
            exclude_properties=frozenset({"HALFLIFE", "Effort"})
        )
        assert config.exclude_properties == frozenset({"halflife", "effort"})

    def test_already_lowercase_unchanged(self):
        config = Config(exclude_drawers=frozenset({"logbook"}))
        assert config.exclude_drawers == frozenset({"logbook"})

    def test_empty_frozenset_unchanged(self):
        config = Config()
        assert config.exclude_drawers == frozenset()
        assert config.exclude_blocks == frozenset()
        assert config.exclude_properties == frozenset()

    def test_tags_not_normalized(self):
        """tags_exclude_from_inheritance is NOT lowered — tags are case-sensitive."""
        config = Config(
            tags_exclude_from_inheritance=frozenset({"TODAY", "habit"})
        )
        assert config.tags_exclude_from_inheritance == frozenset(
            {"TODAY", "habit"}
        )


# --- created_property ---


class TestConfigCreatedProperty:
    """Config.created_property is normalized to uppercase."""

    def test_default(self):
        config = Config()
        assert config.created_property == "CREATED"

    def test_custom(self):
        config = Config(created_property="captured_on")
        assert config.created_property == "CAPTURED_ON"

    def test_already_uppercase(self):
        config = Config(created_property="MY_DATE")
        assert config.created_property == "MY_DATE"


# --- extra_tag_chars ---


class TestConfigExtraTagChars:
    """Config.extra_tag_chars is a raw string for monkey-patch characters."""

    def test_default_empty(self):
        config = Config()
        assert config.extra_tag_chars == ""

    def test_custom_chars(self):
        config = Config(extra_tag_chars="%#")
        assert config.extra_tag_chars == "%#"
