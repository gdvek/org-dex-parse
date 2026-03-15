"""Tests for S09b-3 — archived timestamp from ARCHIVE_TIME property.

Fixture: timestamps_dedicated.org (items ts-004, ts-013, ts-014).
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


def _parse() -> dict[str, Item]:
    """Parse timestamps_dedicated.org and return items indexed by id."""
    return _items_by_id(parse_file(str(TS_ORG), CONFIG))


# -- AC1: bare with time → datetime.datetime ---------------------------------

class TestArchivedBareWithTime:

    def test_datetime_value(self):
        """AC1: ts-004 ARCHIVE_TIME 2026-01-15 Thu 14:30 → datetime."""
        items = _parse()
        ts = items["ts-004"].archived
        assert ts is not None
        assert isinstance(ts, Timestamp)
        assert ts.date == datetime.datetime(2026, 1, 15, 14, 30)


# -- AC2: absent → None ------------------------------------------------------

class TestArchivedAbsent:

    def test_no_archive_time(self):
        """AC2: ts-002 has no ARCHIVE_TIME → archived is None."""
        items = _parse()
        assert items["ts-002"].archived is None


# -- AC3: active flag always False --------------------------------------------

class TestArchivedActiveFlag:

    def test_bare_with_time_is_inactive(self):
        """AC3: ts-004 bare timestamp → active=False."""
        items = _parse()
        assert items["ts-004"].archived.active is False

    def test_bare_date_only_is_inactive(self):
        """AC3: ts-013 bare date-only → active=False."""
        items = _parse()
        assert items["ts-013"].archived.active is False


# -- AC4: repeater always None -----------------------------------------------

class TestArchivedRepeater:

    def test_repeater_none(self):
        """AC4: ARCHIVE_TIME never has repeater → repeater=None."""
        items = _parse()
        assert items["ts-004"].archived.repeater is None


# -- AC5: date-only → datetime.date ------------------------------------------

class TestArchivedDateOnly:

    def test_date_only(self):
        """AC5: ts-013 ARCHIVE_TIME 2026-07-01 Tue → date."""
        items = _parse()
        ts = items["ts-013"].archived
        assert ts is not None
        assert type(ts.date) is datetime.date
        assert ts.date == datetime.date(2026, 7, 1)


# -- AC6: malformed → None ---------------------------------------------------

class TestArchivedMalformed:

    def test_malformed_returns_none(self):
        """AC6: ts-014 has garbage ARCHIVE_TIME → archived is None."""
        items = _parse()
        assert items["ts-014"].archived is None
