"""Tests for S09b-2 — created timestamp from property.

Fixture: timestamps_dedicated.org (items ts-001 through ts-012).
"""
from __future__ import annotations

import datetime
from pathlib import Path

from org_dex_parse import Config, Item, ParseResult, Timestamp, parse_file

FIXTURES = Path(__file__).parent / "fixtures"
TS_ORG = FIXTURES / "timestamps_dedicated.org"

CONFIG = Config(todos=("TODO",), dones=("DONE",))


# -- Helpers ------------------------------------------------------------------

def _items_by_id(result: ParseResult) -> dict[str, Item]:
    """Index ParseResult items by item_id for easy lookup."""
    return {item.item_id: item for item in result.items}


def _parse(config: Config = CONFIG) -> dict[str, Item]:
    """Parse timestamps_dedicated.org and return items indexed by id."""
    return _items_by_id(parse_file(str(TS_ORG), config))


# -- AC1: created from bare property -----------------------------------------

class TestCreatedBare:

    def test_bare_no_dow(self):
        """AC1/AC8: ts-009 has bare CREATED without dow → populated."""
        items = _parse()
        ts = items["ts-009"].created
        assert ts is not None
        assert isinstance(ts, Timestamp)
        assert ts.date == datetime.date(2026, 6, 1)

    def test_bare_with_time_and_dow(self):
        """AC1/AC6/AC8: ts-010 has bare CREATED with dow and time."""
        items = _parse()
        ts = items["ts-010"].created
        assert ts is not None
        assert ts.date == datetime.datetime(2026, 6, 15, 8, 45)


# -- AC2: created from active property ---------------------------------------

class TestCreatedActive:

    def test_active_with_time(self):
        """AC2/AC6: ts-003 has <2026-02-15 Sat 10:00> → active Timestamp."""
        items = _parse()
        ts = items["ts-003"].created
        assert ts is not None
        assert ts.date == datetime.datetime(2026, 2, 15, 10, 0)


# -- AC3: created from inactive property -------------------------------------

class TestCreatedInactive:

    def test_inactive(self):
        """AC3: ts-001 has [2026-03-01 Sun] → inactive Timestamp."""
        items = _parse()
        ts = items["ts-001"].created
        assert ts is not None
        assert ts.date == datetime.date(2026, 3, 1)

    def test_inactive_on_archived(self):
        """AC3: ts-004 has [2026-01-01 Wed] → inactive Timestamp."""
        items = _parse()
        ts = items["ts-004"].created
        assert ts is not None
        assert ts.date == datetime.date(2026, 1, 1)


# -- AC4: created absent → None ----------------------------------------------

class TestCreatedAbsent:

    def test_no_created(self):
        """AC4: ts-002 has no CREATED → created is None."""
        items = _parse()
        assert items["ts-002"].created is None


# -- AC5: date type (datetime.date when no time) -----------------------------

class TestCreatedDateType:

    def test_date_without_time(self):
        """AC5: ts-001 CREATED has no time → type is datetime.date."""
        items = _parse()
        assert type(items["ts-001"].created.date) is datetime.date

    def test_date_with_time(self):
        """AC6: ts-003 CREATED has time → type is datetime.datetime."""
        items = _parse()
        assert type(items["ts-003"].created.date) is datetime.datetime


# -- AC7: active flag --------------------------------------------------------

class TestCreatedActiveFlag:

    def test_active_delimiters(self):
        """AC7: <> delimiters → active=True."""
        items = _parse()
        assert items["ts-003"].created.active is True

    def test_inactive_delimiters(self):
        """AC7: [] delimiters → active=False."""
        items = _parse()
        assert items["ts-001"].created.active is False

    def test_bare_is_inactive(self):
        """AC7: no delimiters → active=False."""
        items = _parse()
        assert items["ts-009"].created.active is False

    def test_bare_with_time_is_inactive(self):
        """AC7: bare with time → active=False."""
        items = _parse()
        assert items["ts-010"].created.active is False


# -- AC9: malformed → None ---------------------------------------------------

class TestCreatedMalformed:

    def test_malformed_returns_none(self):
        """AC9: ts-011 has garbage CREATED → created is None."""
        items = _parse()
        assert items["ts-011"].created is None


# -- AC10: configurable property name ----------------------------------------

class TestCreatedConfigurable:

    def test_custom_property_name(self):
        """AC10: config with created_property='CUSTOM_DATE' reads :CUSTOM_DATE:."""
        custom_config = Config(
            todos=("TODO",), dones=("DONE",),
            created_property="CUSTOM_DATE",
        )
        items = _parse(custom_config)
        # ts-012 has :CUSTOM_DATE: <2026-07-01 Wed> and no :CREATED:
        ts = items["ts-012"].created
        assert ts is not None
        assert ts.date == datetime.date(2026, 7, 1)
        assert ts.active is True

    def test_default_property_misses_custom(self):
        """AC10: default config does not read :CUSTOM_DATE:."""
        items = _parse()
        # ts-012 has no :CREATED:, only :CUSTOM_DATE:
        assert items["ts-012"].created is None


# -- AC11: repeater always None ----------------------------------------------

class TestCreatedRepeater:

    def test_repeater_none_inactive(self):
        """AC11: CREATED never has repeater → repeater=None."""
        items = _parse()
        assert items["ts-001"].created.repeater is None

    def test_repeater_none_active(self):
        """AC11: active CREATED → repeater=None."""
        items = _parse()
        assert items["ts-003"].created.repeater is None

    def test_repeater_none_bare(self):
        """AC11: bare CREATED → repeater=None."""
        items = _parse()
        assert items["ts-009"].created.repeater is None


# -- S18: malformed robustness -----------------------------------------------

class TestCreatedMalformedS18:
    """S18: impossible dates and mismatched delimiters → None, no crash."""

    def test_impossible_date_returns_none(self):
        """S18-AC1: impossible date (Feb 31) → created is None."""
        items = _parse()
        assert items["ts-015"].created is None

    def test_impossible_date_with_time_returns_none(self):
        """S18-AC2: impossible date with time (Feb 31 10:00) → created is None."""
        items = _parse()
        assert items["ts-016"].created is None

    def test_mismatch_open_angle_close_bracket(self):
        """S18-AC3: <...] mismatch → created is None."""
        items = _parse()
        assert items["ts-017"].created is None

    def test_mismatch_open_bracket_close_angle(self):
        """S18-AC4: [...> mismatch → created is None."""
        items = _parse()
        assert items["ts-018"].created is None
