"""Tests for L12 — post-parse predicate check (S19g).

L12 detects headings that match the item predicate but lack :ID:
("quasi-items" the user forgot to assign an ID to).

Tests cover:
  AC1: ParseWarning frozen dataclass, ParseResult.warnings default
  AC2: L12 fires on predicate match without :ID:
  AC3: L12 skipped when predicate is default (None)
  AC4: L12 skipped when predicate does not match
  AC6: No regression — items with :ID:, clean files
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from org_dex_parse import Config, ParseResult, ParseWarning, parse_file


# -- AC1: ParseWarning dataclass ----------------------------------------------


class TestParseWarning:
    """ParseWarning is a frozen dataclass with 4 fields."""

    def test_frozen(self):
        w = ParseWarning(line=1, code="L12", message="test", severity="warning")
        with pytest.raises(FrozenInstanceError):
            w.line = 2

    def test_fields(self):
        w = ParseWarning(line=10, code="L12", message="msg", severity="warning")
        assert w.line == 10
        assert w.code == "L12"
        assert w.message == "msg"
        assert w.severity == "warning"

    def test_parse_result_warnings_default_empty(self):
        """ParseResult().warnings defaults to empty tuple."""
        pr = ParseResult()
        assert pr.warnings == ()


# -- AC3: Config.predicate_is_default flag ------------------------------------


class TestPredicateIsDefault:
    """Config.predicate_is_default tracks whether predicate was None."""

    def test_predicate_is_default_none(self):
        """Predicate=None → predicate_is_default=True."""
        config = Config(item_predicate=None)
        assert config.predicate_is_default is True

    def test_predicate_is_default_omitted(self):
        """Default construction → predicate_is_default=True."""
        config = Config()
        assert config.predicate_is_default is True

    def test_predicate_is_default_explicit_list(self):
        """Explicit list predicate → predicate_is_default=False."""
        config = Config(item_predicate=["property", "Type"])
        assert config.predicate_is_default is False

    def test_predicate_is_default_explicit_callable(self):
        """Explicit callable predicate → predicate_is_default=False."""
        config = Config(item_predicate=lambda h: True)
        assert config.predicate_is_default is False


# -- AC2: L12 fires on predicate match without :ID: --------------------------


class TestL12Detection:
    """L12 detects headings matching predicate but missing :ID:."""

    def test_l12_heading_matches_predicate_no_id(self, tmp_path):
        """AC2: heading with Type property but no :ID: → 1 L12 warning."""
        f = tmp_path / "test.org"
        f.write_text(
            "* Item with ID\n"
            "  :PROPERTIES:\n"
            "  :ID: abc-123\n"
            "  :Type: note\n"
            "  :END:\n"
            "* Quasi-item no ID\n"
            "  :PROPERTIES:\n"
            "  :Type: note\n"
            "  :END:\n"
        )
        config = Config(item_predicate=["property", "Type"])
        result = parse_file(str(f), config)

        # One real item, one L12 warning.
        assert len(result.items) == 1
        assert result.items[0].item_id == "abc-123"

        assert len(result.warnings) == 1
        w = result.warnings[0]
        assert w.code == "L12"
        assert w.severity == "warning"
        assert "Quasi-item no ID" in w.message
        assert w.line == 6  # line of the heading

    def test_l12_multiple_violations(self, tmp_path):
        """AC2: multiple quasi-items → multiple warnings in document order."""
        f = tmp_path / "test.org"
        f.write_text(
            "* First quasi\n"
            "  :PROPERTIES:\n"
            "  :Type: note\n"
            "  :END:\n"
            "* Second quasi\n"
            "  :PROPERTIES:\n"
            "  :Type: project\n"
            "  :END:\n"
        )
        config = Config(item_predicate=["property", "Type"])
        result = parse_file(str(f), config)

        assert len(result.items) == 0
        assert len(result.warnings) == 2
        assert result.warnings[0].line < result.warnings[1].line
        assert "First quasi" in result.warnings[0].message
        assert "Second quasi" in result.warnings[1].message


# -- AC3: default predicate → no L12 -----------------------------------------


class TestL12DefaultPredicate:
    """L12 is skipped when predicate is default (None)."""

    def test_l12_default_predicate_no_warnings(self, tmp_path):
        """AC3: predicate=None → no L12 warnings even with headings lacking :ID:."""
        f = tmp_path / "test.org"
        f.write_text(
            "* Heading without ID\n"
            "  Some body text.\n"
            "* Another heading\n"
        )
        config = Config()  # default predicate
        result = parse_file(str(f), config)

        assert len(result.warnings) == 0


# -- AC4: predicate does not match → no L12 ----------------------------------


class TestL12NoPredicateMatch:
    """L12 skipped when heading without :ID: does not match predicate."""

    def test_l12_heading_no_predicate_match(self, tmp_path):
        """AC4: heading without :ID: and without Type → no L12."""
        f = tmp_path / "test.org"
        f.write_text(
            "* Plain heading\n"
            "  No properties at all.\n"
        )
        config = Config(item_predicate=["property", "Type"])
        result = parse_file(str(f), config)

        assert len(result.warnings) == 0


# -- AC6: no regression -------------------------------------------------------


class TestL12NoRegression:
    """Existing behavior is unchanged."""

    def test_l12_heading_with_id_no_warning(self, tmp_path):
        """AC6: heading with :ID: + predicate match → item, no warning."""
        f = tmp_path / "test.org"
        f.write_text(
            "* Real item\n"
            "  :PROPERTIES:\n"
            "  :ID: real-001\n"
            "  :Type: note\n"
            "  :END:\n"
        )
        config = Config(item_predicate=["property", "Type"])
        result = parse_file(str(f), config)

        assert len(result.items) == 1
        assert len(result.warnings) == 0

    def test_l12_clean_file_no_warnings(self, tmp_path):
        """AC6: file with only proper items → warnings empty."""
        f = tmp_path / "test.org"
        f.write_text(
            "* Item A\n"
            "  :PROPERTIES:\n"
            "  :ID: a-001\n"
            "  :Type: note\n"
            "  :END:\n"
            "* Item B\n"
            "  :PROPERTIES:\n"
            "  :ID: b-002\n"
            "  :Type: project\n"
            "  :END:\n"
        )
        config = Config(item_predicate=["property", "Type"])
        result = parse_file(str(f), config)

        assert len(result.items) == 2
        assert len(result.warnings) == 0
