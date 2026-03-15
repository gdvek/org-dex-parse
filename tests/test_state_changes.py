"""Tests for S09c-2 — state changes.

Fixture: state_changes.org (items sc-001 through sc-009).
"""
from __future__ import annotations

import datetime
from pathlib import Path

from org_dex_parse import Config, Item, ParseResult, parse_file
from org_dex_parse.types import StateChange

FIXTURES = Path(__file__).parent / "fixtures"
SC_ORG = FIXTURES / "state_changes.org"

CONFIG = Config(todos=("TODO", "DOING"), dones=("DONE",))


# -- Helpers ------------------------------------------------------------------

def _items_by_id(result: ParseResult) -> dict[str, Item]:
    """Index ParseResult items by item_id for easy lookup."""
    return {item.item_id: item for item in result.items}


def _parse() -> dict[str, Item]:
    """Parse state_changes.org and return items indexed by id."""
    return _items_by_id(parse_file(str(SC_ORG), CONFIG))


# -- AC1: normal state change → StateChange with to, from, timestamp ---------

class TestNormalStateChange:

    def test_normal_state_change_fields(self):
        """AC1: sc-001 has two state changes with correct fields."""
        items = _parse()
        sc = items["sc-001"].state_changes
        assert len(sc) == 2
        # Chronological order: 10 Mar before 12 Mar.
        assert sc[0] == StateChange(
            to_state="DOING",
            from_state="TODO",
            timestamp=datetime.datetime(2026, 3, 10, 9, 0),
        )
        assert sc[1] == StateChange(
            to_state="DONE",
            from_state="DOING",
            timestamp=datetime.datetime(2026, 3, 12, 16, 0),
        )


# -- AC2: first assignment (from without quotes) → from_state=None -----------

class TestFirstAssignment:

    def test_first_assignment_from_none(self):
        """AC2: sc-002 has first assignment → from_state=None."""
        items = _parse()
        sc = items["sc-002"].state_changes
        assert len(sc) == 1
        assert sc[0] == StateChange(
            to_state="TODO",
            from_state=None,
            timestamp=datetime.datetime(2026, 3, 8, 20, 0),
        )


# -- AC3: chronological order (reversed from file) ---------------------------

class TestChronologicalOrder:

    def test_multiple_in_chronological_order(self):
        """AC3: sc-003 has 3 state changes — oldest first after reversal."""
        items = _parse()
        sc = items["sc-003"].state_changes
        assert len(sc) == 3
        timestamps = [s.timestamp for s in sc]
        assert timestamps == [
            datetime.datetime(2026, 3, 10, 8, 0),    # oldest
            datetime.datetime(2026, 3, 12, 9, 30),    # middle
            datetime.datetime(2026, 3, 15, 14, 0),    # newest
        ]

    def test_first_assignment_in_sequence(self):
        """AC3: sc-003 first entry is first assignment (from_state=None)."""
        items = _parse()
        sc = items["sc-003"].state_changes
        assert sc[0].from_state is None
        assert sc[0].to_state == "TODO"


# -- AC4: only item node — no scaffolding, no sub-items ----------------------

class TestItemNodeOnly:

    def test_scaffolding_sc_not_included(self):
        """AC4: sc-006 scaffold child's state change NOT in parent."""
        items = _parse()
        sc = items["sc-006"].state_changes
        # Parent has only its own state change, not the scaffold child's.
        assert len(sc) == 1
        assert sc[0].to_state == "DONE"
        assert sc[0].timestamp == datetime.datetime(2026, 3, 14, 12, 0)

    def test_subitem_sc_not_included(self):
        """AC4: sc-007 sub-item's state change NOT in parent."""
        items = _parse()
        sc = items["sc-007"].state_changes
        assert len(sc) == 1
        assert sc[0].timestamp == datetime.datetime(2026, 3, 14, 15, 0)

    def test_subitem_has_own_sc(self):
        """AC4: sc-007-sub has its own state change."""
        items = _parse()
        sc = items["sc-007-sub"].state_changes
        assert len(sc) == 1
        assert sc[0].timestamp == datetime.datetime(2026, 3, 13, 11, 0)


# -- AC5: state change timestamps not in inactive_ts (deduplication) ----------

class TestDeduplication:

    def test_sc_ts_not_in_inactive(self):
        """AC5: sc-008 state-change [2026-03-10 10:30] not in inactive_ts."""
        items = _parse()
        item = items["sc-008"]
        inactive_dates = [ts.date for ts in item.inactive_ts]
        assert datetime.datetime(2026, 3, 10, 10, 30) not in inactive_dates

    def test_body_ts_still_in_inactive(self):
        """AC5: sc-008 body [2026-05-01] still in inactive_ts."""
        items = _parse()
        item = items["sc-008"]
        inactive_dates = [ts.date for ts in item.inactive_ts]
        assert datetime.date(2026, 5, 1) in inactive_dates


# -- AC6: no state changes → empty tuple -------------------------------------

class TestNoStateChanges:

    def test_no_logbook(self):
        """AC6: sc-004 has no LOGBOOK → state_changes = ()."""
        items = _parse()
        assert items["sc-004"].state_changes == ()

    def test_logbook_without_sc(self):
        """AC6: sc-005 has LOGBOOK with only CLOCK → state_changes = ()."""
        items = _parse()
        assert items["sc-005"].state_changes == ()


# -- AC7: timestamp is always datetime.datetime ------------------------------

class TestAlwaysDatetime:

    def test_timestamp_is_datetime(self):
        """AC7: StateChange.timestamp is datetime.datetime, not date."""
        items = _parse()
        for entry in items["sc-001"].state_changes:
            assert type(entry.timestamp) is datetime.datetime


# -- AC8: multiple state changes all captured --------------------------------

class TestMultipleCapture:

    def test_all_three_captured(self):
        """AC8: sc-003 has 3 state changes — all captured."""
        items = _parse()
        sc = items["sc-003"].state_changes
        assert len(sc) == 3
        assert sc[0].to_state == "TODO"
        assert sc[1].to_state == "DOING"
        assert sc[2].to_state == "DONE"


# -- AC9: note after state change does not corrupt parsing --------------------

class TestNoteAfterStateChange:

    def test_note_does_not_corrupt(self):
        """AC9: sc-009 state change with trailing note parsed correctly."""
        items = _parse()
        sc = items["sc-009"].state_changes
        assert len(sc) == 1
        assert sc[0] == StateChange(
            to_state="DONE",
            from_state="TODO",
            timestamp=datetime.datetime(2026, 3, 11, 14, 0),
        )
