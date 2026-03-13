"""Tests for org_dex_parse.config — parser configuration.

Covers AC5 (item_predicate), AC6 (case normalization).
"""
from dataclasses import FrozenInstanceError

import pytest

from org_dex_parse import Config


# --- AC5: item_predicate ---


class TestConfigPredicate:
    """Config.item_predicate accepts a callable; default is lambda h: True."""

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
