"""Tests for S09b-1 — planning timestamps (scheduled, deadline, closed).

Fixture: timestamps_dedicated.org (items ts-001 through ts-008).
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


# -- AC1: scheduled populated ------------------------------------------------

class TestScheduledPopulated:

    def test_scheduled_present(self):
        """AC1: ts-001 has SCHEDULED → scheduled is a Timestamp."""
        items = _parse()
        ts = items["ts-001"].scheduled
        assert ts is not None
        assert isinstance(ts, Timestamp)
        assert ts.date == datetime.date(2026, 4, 1)


# -- AC2: deadline populated -------------------------------------------------

class TestDeadlinePopulated:

    def test_deadline_present(self):
        """AC2: ts-001 has DEADLINE → deadline is a Timestamp."""
        items = _parse()
        ts = items["ts-001"].deadline
        assert ts is not None
        assert isinstance(ts, Timestamp)
        assert ts.date == datetime.date(2026, 4, 15)


# -- AC3: closed populated ---------------------------------------------------

class TestClosedPopulated:

    def test_closed_present(self):
        """AC3: ts-001 has CLOSED → closed is a Timestamp."""
        items = _parse()
        ts = items["ts-001"].closed
        assert ts is not None
        assert isinstance(ts, Timestamp)
        assert ts.date == datetime.datetime(2026, 3, 30, 14, 30)


# -- AC4: absent planning → None ---------------------------------------------

class TestAbsentPlanning:

    def test_scheduled_none(self):
        """AC4: ts-002 has no SCHEDULED → scheduled is None."""
        items = _parse()
        assert items["ts-002"].scheduled is None

    def test_deadline_none(self):
        """AC4: ts-002 has no DEADLINE → deadline is None."""
        items = _parse()
        assert items["ts-002"].deadline is None

    def test_closed_none(self):
        """AC4: ts-002 has no CLOSED → closed is None."""
        items = _parse()
        assert items["ts-002"].closed is None


# -- AC5: date vs datetime ---------------------------------------------------

class TestDateType:

    def test_date_without_time(self):
        """AC5: ts-001 SCHEDULED has no time → date is datetime.date."""
        items = _parse()
        ts = items["ts-001"].scheduled
        assert type(ts.date) is datetime.date

    def test_date_with_time_closed(self):
        """AC5: ts-001 CLOSED has time → date is datetime.datetime."""
        items = _parse()
        ts = items["ts-001"].closed
        assert type(ts.date) is datetime.datetime

    def test_date_with_time_deadline(self):
        """AC5: ts-006 DEADLINE has time 09:00 → date is datetime.datetime."""
        items = _parse()
        ts = items["ts-006"].deadline
        assert type(ts.date) is datetime.datetime
        assert ts.date == datetime.datetime(2026, 5, 1, 9, 0)


# -- AC6: active flag --------------------------------------------------------

class TestActiveFlag:

    def test_scheduled_active(self):
        """AC6: SCHEDULED uses <> → active=True."""
        items = _parse()
        assert items["ts-001"].scheduled.active is True

    def test_deadline_active(self):
        """AC6: DEADLINE uses <> → active=True."""
        items = _parse()
        assert items["ts-001"].deadline.active is True

    def test_closed_inactive(self):
        """AC6: CLOSED uses [] → active=False."""
        items = _parse()
        assert items["ts-001"].closed.active is False


# -- AC7: repeater present ---------------------------------------------------

class TestRepeaterPresent:

    def test_repeater_cumulate(self):
        """AC7: ts-005 SCHEDULED has +1w → repeater='+1w'."""
        items = _parse()
        assert items["ts-005"].scheduled.repeater == "+1w"


# -- AC8: repeater absent ----------------------------------------------------

class TestRepeaterAbsent:

    def test_no_repeater(self):
        """AC8: ts-001 SCHEDULED has no repeater → repeater=None."""
        items = _parse()
        assert items["ts-001"].scheduled.repeater is None

    def test_no_repeater_closed(self):
        """AC8: ts-001 CLOSED has no repeater → repeater=None."""
        items = _parse()
        assert items["ts-001"].closed.repeater is None


# -- AC9: all repeater forms -------------------------------------------------

class TestRepeaterForms:

    def test_catchup(self):
        """AC9: ts-007 SCHEDULED has ++2d → repeater='++2d'."""
        items = _parse()
        assert items["ts-007"].scheduled.repeater == "++2d"

    def test_restart(self):
        """AC9: ts-008 SCHEDULED has .+1m → repeater='.+1m'."""
        items = _parse()
        assert items["ts-008"].scheduled.repeater == ".+1m"


# AC10 guard tests moved to test_orgparse_compat.py (S20).
