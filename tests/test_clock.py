"""Tests for S09c-1 — clock entries.

Fixture: clock.org (items clk-001 through clk-007).
"""
from __future__ import annotations

import datetime
from pathlib import Path

import orgparse
from orgparse.date import OrgDateClock

from org_dex_parse import Config, Item, ParseResult, parse_file
from org_dex_parse.types import ClockEntry

FIXTURES = Path(__file__).parent / "fixtures"
CLK_ORG = FIXTURES / "clock.org"

CONFIG = Config(todos=("TODO",), dones=("DONE",))


# -- Helpers ------------------------------------------------------------------

def _items_by_id(result: ParseResult) -> dict[str, Item]:
    """Index ParseResult items by item_id for easy lookup."""
    return {item.item_id: item for item in result.items}


def _parse() -> dict[str, Item]:
    """Parse clock.org and return items indexed by id."""
    return _items_by_id(parse_file(str(CLK_ORG), CONFIG))


# -- AC1: closed clock → ClockEntry with start, end, duration_minutes --------

class TestClosedClock:

    def test_closed_clock_fields(self):
        """AC1: clk-001 has two closed clocks with correct fields."""
        items = _parse()
        clock = items["clk-001"].clock
        assert len(clock) == 2
        # Chronological order: 9 Mar before 10 Mar.
        assert clock[0] == ClockEntry(
            start=datetime.datetime(2026, 3, 9, 9, 0),
            end=datetime.datetime(2026, 3, 9, 10, 15),
            duration_minutes=75,
        )
        assert clock[1] == ClockEntry(
            start=datetime.datetime(2026, 3, 10, 14, 0),
            end=datetime.datetime(2026, 3, 10, 15, 30),
            duration_minutes=90,
        )


# -- AC2: open clock → end=None, duration_minutes=None ----------------------

class TestOpenClock:

    def test_open_clock_fields(self):
        """AC2: clk-002 has one open clock."""
        items = _parse()
        clock = items["clk-002"].clock
        assert len(clock) == 1
        assert clock[0] == ClockEntry(
            start=datetime.datetime(2026, 3, 8, 20, 0),
            end=None,
            duration_minutes=None,
        )


# -- AC3: chronological order (reversed from file) --------------------------

class TestChronologicalOrder:

    def test_mixed_clocks_in_chronological_order(self):
        """AC3: clk-003 has 3 clocks — oldest first after reversal."""
        items = _parse()
        clock = items["clk-003"].clock
        assert len(clock) == 3
        starts = [c.start for c in clock]
        assert starts == [
            datetime.datetime(2026, 3, 10, 8, 30),   # oldest
            datetime.datetime(2026, 3, 11, 16, 0),    # middle (open)
            datetime.datetime(2026, 3, 12, 11, 0),    # newest
        ]


# -- AC4: scaffolding walk — scaffold clocks included, sub-item excluded ----

class TestScaffoldingWalk:

    def test_scaffold_clock_included(self):
        """AC4: clk-005 scaffold child's clock belongs to parent item."""
        items = _parse()
        clock = items["clk-005"].clock
        assert len(clock) == 1
        assert clock[0].start == datetime.datetime(2026, 3, 15, 10, 0)

    def test_subitem_clock_excluded(self):
        """AC4: clk-006 sub-item's clock does NOT belong to parent."""
        items = _parse()
        assert items["clk-006"].clock == ()

    def test_subitem_has_own_clock(self):
        """AC4: clk-006-sub has its own clock."""
        items = _parse()
        clock = items["clk-006-sub"].clock
        assert len(clock) == 1
        assert clock[0].start == datetime.datetime(2026, 3, 14, 9, 0)


# -- AC5: clock timestamps not in inactive_ts (deduplication) ---------------

class TestClockDeduplication:

    def test_clock_ts_not_in_inactive(self):
        """AC5: clk-007 CLOCK [09:00]--[10:30] not in inactive_ts."""
        items = _parse()
        item = items["clk-007"]
        inactive_dates = [ts.date for ts in item.inactive_ts]
        assert datetime.datetime(2026, 3, 10, 9, 0) not in inactive_dates
        assert datetime.datetime(2026, 3, 10, 10, 30) not in inactive_dates

    def test_body_ts_still_in_inactive(self):
        """AC5: clk-007 body [2026-05-01] still in inactive_ts."""
        items = _parse()
        item = items["clk-007"]
        inactive_dates = [ts.date for ts in item.inactive_ts]
        assert datetime.date(2026, 5, 1) in inactive_dates


# -- AC6: no clock → empty tuple -------------------------------------------

class TestNoClock:

    def test_empty_tuple(self):
        """AC6: clk-004 has no LOGBOOK → clock = ()."""
        items = _parse()
        assert items["clk-004"].clock == ()


# -- AC7: guard test for OrgDateClock._duration (private API) ---------------

class TestGuardOrgDateClockDuration:
    """Guard test: verify orgparse OrgDateClock._duration attribute.

    _duration is a private API.  If orgparse changes the attribute name
    or type, this test fails immediately — protecting clock extraction
    from silent breakage.
    """

    def test_duration_is_int_on_closed(self):
        """AC7: _duration is int (minutes) on closed clock."""
        root = orgparse.load(str(CLK_ORG))
        # clk-001 is the first real node — has closed clocks.
        node = root[1]
        assert len(node.clock) > 0
        cl = node.clock[0]
        assert isinstance(cl, OrgDateClock)
        assert isinstance(cl._duration, int)

    def test_duration_is_none_on_open(self):
        """AC7: _duration is None on open clock."""
        root = orgparse.load(str(CLK_ORG))
        # clk-002 is the second real node — has open clock.
        node = root[2]
        assert len(node.clock) > 0
        cl = node.clock[0]
        assert cl._duration is None


# -- AC8: start and end are always datetime.datetime -----------------------

class TestClockAlwaysDatetime:

    def test_start_is_datetime(self):
        """AC8: ClockEntry.start is datetime.datetime, not date."""
        items = _parse()
        for entry in items["clk-001"].clock:
            assert type(entry.start) is datetime.datetime

    def test_end_is_datetime_when_present(self):
        """AC8: ClockEntry.end is datetime.datetime when not None."""
        items = _parse()
        for entry in items["clk-001"].clock:
            assert type(entry.end) is datetime.datetime
