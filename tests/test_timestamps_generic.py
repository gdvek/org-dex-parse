"""Tests for S09b-4 — generic timestamps (active_ts, inactive_ts, range_ts).

Fixture: timestamps_generic.org (items gen-001 through gen-012).
"""
from __future__ import annotations

import datetime
from pathlib import Path

from org_dex_parse import Config, Item, ParseResult, Range, Timestamp, parse_file

FIXTURES = Path(__file__).parent / "fixtures"
TS_ORG = FIXTURES / "timestamps_generic.org"

CONFIG = Config(todos=("TODO",), dones=("DONE",))


# -- Helpers ------------------------------------------------------------------

def _items_by_id(result: ParseResult) -> dict[str, Item]:
    """Index ParseResult items by item_id for easy lookup."""
    return {item.item_id: item for item in result.items}


def _parse() -> dict[str, Item]:
    """Parse timestamps_generic.org and return items indexed by id."""
    return _items_by_id(parse_file(str(TS_ORG), CONFIG))


# -- AC1: active_ts contains only active point timestamps --------------------

class TestActivePointTimestamp:

    def test_active_ts_from_body(self):
        """AC1: gen-001 has <2026-05-01> in body → active_ts."""
        items = _parse()
        assert len(items["gen-001"].active_ts) == 1
        ts = items["gen-001"].active_ts[0]
        assert ts.active is True
        assert ts.date == datetime.date(2026, 5, 1)

    def test_active_ts_not_in_inactive(self):
        """AC1: active timestamp must not appear in inactive_ts."""
        items = _parse()
        assert len(items["gen-001"].inactive_ts) == 0


# -- AC2: inactive_ts contains only inactive point timestamps -----------------

class TestInactivePointTimestamp:

    def test_inactive_ts_from_body(self):
        """AC2: gen-002 has [2026-03-01] in body → inactive_ts."""
        items = _parse()
        assert len(items["gen-002"].inactive_ts) == 1
        ts = items["gen-002"].inactive_ts[0]
        assert ts.active is False
        assert ts.date == datetime.date(2026, 3, 1)

    def test_inactive_ts_not_in_active(self):
        """AC2: inactive timestamp must not appear in active_ts."""
        items = _parse()
        assert len(items["gen-002"].active_ts) == 0


# -- AC3: range_ts contains ranges -------------------------------------------

class TestRangeTimestamp:

    def test_active_range(self):
        """AC3: gen-003 has <d1>--<d2> → range_ts, active=True."""
        items = _parse()
        assert len(items["gen-003"].range_ts) == 1
        r = items["gen-003"].range_ts[0]
        assert r.active is True
        assert r.start.date == datetime.date(2026, 6, 1)
        assert r.end.date == datetime.date(2026, 6, 3)

    def test_inactive_range(self):
        """AC3: gen-011 has [d1]--[d2] → range_ts, active=False."""
        items = _parse()
        assert len(items["gen-011"].range_ts) == 1
        r = items["gen-011"].range_ts[0]
        assert r.active is False
        assert r.start.date == datetime.date(2026, 7, 1)
        assert r.end.date == datetime.date(2026, 7, 14)

    def test_range_not_in_point_fields(self):
        """AC3: ranges must not appear in active_ts or inactive_ts."""
        items = _parse()
        assert len(items["gen-003"].active_ts) == 0
        assert len(items["gen-003"].inactive_ts) == 0


# -- AC4: scope includes scaffolding body ------------------------------------

class TestScopeWalk:

    def test_scaffolding_body_collected(self):
        """AC4: gen-008 scaffold body has [2026-11-01] → parent inactive_ts."""
        items = _parse()
        inactive_dates = [ts.date for ts in items["gen-008"].inactive_ts]
        assert datetime.date(2026, 11, 1) in inactive_dates


# -- AC5: planning line excluded ----------------------------------------------

class TestPlanningExcluded:

    def test_no_generics_when_only_planning(self):
        """AC5: gen-004 has only SCHEDULED, no body ts → empty generics."""
        items = _parse()
        assert items["gen-004"].active_ts == ()
        assert items["gen-004"].inactive_ts == ()
        assert items["gen-004"].range_ts == ()

    def test_planning_not_duplicated_in_generics(self):
        """AC5: gen-005 SCHEDULED/DEADLINE not in active_ts."""
        items = _parse()
        active_dates = [ts.date for ts in items["gen-005"].active_ts]
        # Only the body ts should be present, not SCHEDULED or DEADLINE.
        assert datetime.date(2026, 7, 1) in active_dates
        assert datetime.date(2026, 4, 1) not in active_dates   # SCHEDULED
        assert datetime.date(2026, 4, 15) not in active_dates  # DEADLINE


# -- AC6: PROPERTIES drawer excluded -----------------------------------------

class TestPropertiesExcluded:

    def test_created_not_in_generics(self):
        """AC6: gen-005 CREATED [2026-03-01] not in inactive_ts."""
        items = _parse()
        inactive_dates = [ts.date for ts in items["gen-005"].inactive_ts]
        assert datetime.date(2026, 3, 1) not in inactive_dates


# -- AC7: link descriptions stripped ------------------------------------------

class TestLinkDescriptionStripped:

    def test_link_desc_not_extracted(self):
        """AC7: gen-007 link desc '2026-01-15 report' not a timestamp."""
        items = _parse()
        all_dates = (
            [ts.date for ts in items["gen-007"].active_ts]
            + [ts.date for ts in items["gen-007"].inactive_ts]
        )
        assert datetime.date(2026, 1, 15) not in all_dates

    def test_real_ts_still_extracted(self):
        """AC7: gen-007 real <2026-09-01> still in active_ts."""
        items = _parse()
        assert len(items["gen-007"].active_ts) == 1
        assert items["gen-007"].active_ts[0].date == datetime.date(2026, 9, 1)


# -- AC8: scaffolding planning → generic -------------------------------------

class TestScaffoldingPlanning:

    def test_scaffold_scheduled_as_active(self):
        """AC8: gen-008 scaffold SCHEDULED <2026-10-15> → active_ts."""
        items = _parse()
        active_dates = [ts.date for ts in items["gen-008"].active_ts]
        assert datetime.date(2026, 10, 15) in active_dates


# -- AC9: Timestamp conversion (date/datetime, active, repeater) -------------

class TestTimestampConversion:

    def test_datetime_with_time(self):
        """AC9: gen-010 <2026-04-01 Wed 14:30 +1w> → datetime with time."""
        items = _parse()
        ts = items["gen-010"].active_ts[0]
        assert type(ts.date) is datetime.datetime
        assert ts.date == datetime.datetime(2026, 4, 1, 14, 30)

    def test_date_without_time(self):
        """AC9: gen-010 <2026-05-01 Fri> → date only."""
        items = _parse()
        ts = items["gen-010"].active_ts[1]
        assert type(ts.date) is datetime.date
        assert ts.date == datetime.date(2026, 5, 1)

    def test_repeater_present(self):
        """AC9: gen-010 +1w → repeater='+1w'."""
        items = _parse()
        assert items["gen-010"].active_ts[0].repeater == "+1w"

    def test_repeater_absent(self):
        """AC9: gen-010 second ts has no repeater → None."""
        items = _parse()
        assert items["gen-010"].active_ts[1].repeater is None


# -- AC10: Range structure ---------------------------------------------------

class TestRangeStructure:

    def test_range_start_is_timestamp(self):
        """AC10: Range.start is a Timestamp instance."""
        items = _parse()
        r = items["gen-003"].range_ts[0]
        assert isinstance(r.start, Timestamp)

    def test_range_end_is_timestamp(self):
        """AC10: Range.end is a Timestamp instance."""
        items = _parse()
        r = items["gen-003"].range_ts[0]
        assert isinstance(r.end, Timestamp)

    def test_range_active_matches_delimiters(self):
        """AC10: active range <> → active=True, inactive range [] → False."""
        items = _parse()
        assert items["gen-003"].range_ts[0].active is True
        assert items["gen-011"].range_ts[0].active is False


# AC11 guard tests moved to test_orgparse_compat.py (S20).


# -- AC12: empty tuples when no generic timestamps ----------------------------

class TestEmptyDefaults:

    def test_all_empty_when_no_generics(self):
        """AC12: gen-004 has no generic ts → all three are ()."""
        items = _parse()
        item = items["gen-004"]
        assert item.active_ts == ()
        assert item.inactive_ts == ()
        assert item.range_ts == ()


# -- AC13: document order preserved -------------------------------------------

class TestDocumentOrder:

    def test_active_ts_in_order(self):
        """AC13: gen-010 two active ts appear in document order."""
        items = _parse()
        dates = [ts.date for ts in items["gen-010"].active_ts]
        assert dates == [
            datetime.datetime(2026, 4, 1, 14, 30),
            datetime.date(2026, 5, 1),
        ]


# -- AC14: CLOCK lines excluded ----------------------------------------------

class TestClockExcluded:

    def test_clock_ts_not_in_generics(self):
        """AC14: gen-009 CLOCK timestamps not in inactive_ts or range_ts."""
        items = _parse()
        item = items["gen-009"]
        # CLOCK range [09:00]--[10:30] must not appear.
        inactive_dates = [ts.date for ts in item.inactive_ts]
        assert datetime.datetime(2026, 3, 10, 9, 0) not in inactive_dates
        assert datetime.datetime(2026, 3, 10, 10, 30) not in inactive_dates
        # Nor as a range.
        assert len(item.range_ts) == 0

    def test_real_ts_still_present(self):
        """AC14: gen-009 body <2026-12-01> still in active_ts."""
        items = _parse()
        assert len(items["gen-009"].active_ts) == 1
        assert items["gen-009"].active_ts[0].date == datetime.date(2026, 12, 1)


# -- AC15: state-change lines excluded ---------------------------------------

class TestStateChangeExcluded:

    def test_sc_ts_not_in_generics(self):
        """AC15: gen-009 state-change timestamp not in inactive_ts."""
        items = _parse()
        inactive_dates = [ts.date for ts in items["gen-009"].inactive_ts]
        # State change [2026-03-10 Tue 10:30] must not appear.
        assert datetime.datetime(2026, 3, 10, 10, 30) not in inactive_dates


# -- AC16: timestamp in item heading -----------------------------------------

class TestHeadingTimestamp:

    def test_heading_ts_extracted(self):
        """AC16: gen-006 heading has <2026-08-01> → active_ts."""
        items = _parse()
        assert len(items["gen-006"].active_ts) == 1
        assert items["gen-006"].active_ts[0].date == datetime.date(2026, 8, 1)


# -- AC17: timestamp in scaffolding heading -----------------------------------

class TestScaffoldingHeadingTimestamp:

    def test_scaffold_heading_ts(self):
        """AC17: gen-008 scaffold heading <2026-10-01> → parent active_ts."""
        items = _parse()
        active_dates = [ts.date for ts in items["gen-008"].active_ts]
        assert datetime.date(2026, 10, 1) in active_dates
