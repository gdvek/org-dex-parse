"""Tests for S05a — Dedicated timestamp fields and OrgDate conversion.

Fixture: timestamps_dedicated.org
- ts-001: full planning (SCHEDULED, DEADLINE, CLOSED) + CREATED inactive
- ts-002: no planning, no CREATED, no ARCHIVE_TIME (all None)
- ts-003: CREATED active with time component
- ts-004: ARCHIVE_TIME bare format + CREATED inactive
- ts-005: SCHEDULED with repeater (+1w)
"""
from __future__ import annotations

import datetime
from pathlib import Path

from orgparse.date import OrgDate

from org_dex_parse import Config, Item, ParseResult, parse_file

FIXTURES = Path(__file__).parent / "fixtures"
TS_DEDICATED = FIXTURES / "timestamps_dedicated.org"


# -- Helpers ------------------------------------------------------------------

def _items_by_id(result: ParseResult) -> dict[str, Item]:
    """Index ParseResult items by item_id for easy lookup."""
    return {item.item_id: item for item in result.items}


def _parse() -> dict[str, Item]:
    """Parse the dedicated-timestamps fixture with default config."""
    return _items_by_id(parse_file(TS_DEDICATED, Config()))


# -- AC1–AC2: Planning fields ------------------------------------------------

class TestPlanningFields:
    """scheduled, deadline, closed from the item's planning line."""

    def test_scheduled_extracted(self):
        """AC1: scheduled extracted.  AC7: date-only preserved.
        AC8: active (angle brackets).  AC9: no repeater → None."""
        items = _parse()
        ts = items["ts-001"].scheduled
        assert ts is not None
        assert ts.date == datetime.date(2026, 4, 1)
        assert ts.active is True
        assert ts.repeater is None

    def test_deadline_extracted(self):
        """AC1: deadline extracted, active, date-only."""
        items = _parse()
        ts = items["ts-001"].deadline
        assert ts is not None
        assert ts.date == datetime.date(2026, 4, 15)
        assert ts.active is True

    def test_closed_extracted(self):
        """AC1: closed extracted.  AC7: datetime preserved (14:30).
        AC8: inactive (square brackets)."""
        items = _parse()
        ts = items["ts-001"].closed
        assert ts is not None
        assert ts.date == datetime.datetime(2026, 3, 30, 14, 30)
        assert ts.active is False

    def test_planning_none_when_absent(self):
        """AC2: all planning fields None when no planning line."""
        items = _parse()
        item = items["ts-002"]
        assert item.scheduled is None
        assert item.deadline is None
        assert item.closed is None


# -- AC3–AC4: Created --------------------------------------------------------

class TestCreated:
    """created from config.created_property."""

    def test_created_inactive_date_only(self):
        """AC3: created from CREATED property.
        AC7: date-only preserved.  AC8: inactive."""
        items = _parse()
        ts = items["ts-001"].created
        assert ts is not None
        assert ts.date == datetime.date(2026, 3, 1)
        assert ts.active is False

    def test_created_active_with_time(self):
        """AC3: created from CREATED property (active, with time).
        AC7: datetime preserved.  AC8: active."""
        items = _parse()
        ts = items["ts-003"].created
        assert ts is not None
        assert ts.date == datetime.datetime(2026, 2, 15, 10, 0)
        assert ts.active is True

    def test_created_none_when_absent(self):
        """AC4: created is None when property not present."""
        items = _parse()
        assert items["ts-002"].created is None


# -- AC5–AC6: Archived on ----------------------------------------------------

class TestArchivedOn:
    """archived_on from ARCHIVE_TIME (bare format)."""

    def test_archived_on_bare_format(self):
        """AC5: ARCHIVE_TIME parsed from bare format, always inactive."""
        items = _parse()
        ts = items["ts-004"].archived_on
        assert ts is not None
        assert ts.date == datetime.datetime(2026, 1, 15, 14, 30)
        assert ts.active is False
        assert ts.repeater is None

    def test_archived_on_none_when_absent(self):
        """AC6: archived_on is None when ARCHIVE_TIME absent."""
        items = _parse()
        assert items["ts-002"].archived_on is None


# -- AC9: Repeater ------------------------------------------------------------

class TestRepeater:
    """Repeater formatted as string or None."""

    def test_repeater_string(self):
        """AC9: repeater present → formatted string '+1w'."""
        items = _parse()
        ts = items["ts-005"].scheduled
        assert ts is not None
        assert ts.repeater == "+1w"

    def test_repeater_none(self):
        """AC9: repeater absent → None."""
        items = _parse()
        assert items["ts-001"].scheduled.repeater is None


# -- AC10: OrgDate guard test ------------------------------------------------

class TestOrgDateGuard:
    """Guard test for OrgDate._repeater private attribute."""

    def test_orgdate_repeater_attribute_exists(self):
        """AC10: OrgDate._repeater accessible.

        If this test fails, orgparse changed its internals and the
        _orgdate_to_timestamp conversion needs updating.
        """
        dates = OrgDate.list_from_str("<2026-04-01 Wed +1w>")
        assert len(dates) >= 1
        od = dates[0]
        assert hasattr(od, "_repeater")
        assert od._repeater is not None

    def test_orgdate_repeater_tuple_format(self):
        """AC10: _repeater is a (prefix, num, unit) tuple."""
        dates = OrgDate.list_from_str("<2026-04-01 Wed +1w>")
        od = dates[0]
        prefix, num, unit = od._repeater
        assert prefix == "+"
        assert num == 1
        assert unit == "w"
