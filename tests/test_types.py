"""Tests for org_dex_parse.types — data structures.

Covers AC1 (public imports), AC2 (frozen), AC3 (Item minimal construction),
AC4 (field types), AC7 (ParseResult).
"""
import datetime
from dataclasses import FrozenInstanceError

import pytest

from org_dex_parse import (
    ClockEntry,
    Config,
    Item,
    Link,
    ParseResult,
    Range,
    StateChange,
    Timestamp,
)


# --- AC1: public imports ---


class TestPublicImports:
    """All 8 public types are importable from org_dex_parse."""

    def test_all_types_importable(self):
        for cls in (
            Config,
            ClockEntry,
            Item,
            Link,
            ParseResult,
            Range,
            StateChange,
            Timestamp,
        ):
            assert cls is not None


# --- AC2: frozen ---


class TestFrozen:
    """All dataclasses are frozen — assignment raises FrozenInstanceError."""

    def test_timestamp_frozen(self):
        ts = Timestamp(date=datetime.date(2026, 3, 13), active=True)
        with pytest.raises(FrozenInstanceError):
            ts.active = False

    def test_link_frozen(self):
        link = Link(target="abc", type="id")
        with pytest.raises(FrozenInstanceError):
            link.target = "xyz"

    def test_range_frozen(self):
        start = Timestamp(date=datetime.date(2026, 1, 1), active=True)
        end = Timestamp(date=datetime.date(2026, 1, 2), active=True)
        r = Range(start=start, end=end, active=True)
        with pytest.raises(FrozenInstanceError):
            r.active = False

    def test_clock_entry_frozen(self):
        ce = ClockEntry(start=datetime.datetime(2026, 3, 13, 9, 0))
        with pytest.raises(FrozenInstanceError):
            ce.start = datetime.datetime(2026, 3, 13, 10, 0)

    def test_state_change_frozen(self):
        sc = StateChange(
            to_state="DONE",
            from_state="TODO",
            timestamp=datetime.datetime(2026, 3, 13, 14, 0),
        )
        with pytest.raises(FrozenInstanceError):
            sc.to_state = "CANCELED"

    def test_item_frozen(self):
        item = Item(
            title="Test",
            item_id="abc-123",
            level=1,
            linenumber=1,
            file_path="/test.org",
        )
        with pytest.raises(FrozenInstanceError):
            item.title = "Changed"

    def test_parse_result_frozen(self):
        pr = ParseResult()
        with pytest.raises(FrozenInstanceError):
            pr.items = ()


# --- AC3: Item minimal construction ---


class TestItemMinimal:
    """Item can be constructed with only the 5 required fields."""

    def test_minimal_construction(self):
        item = Item(
            title="Test item",
            item_id="uuid-123",
            level=2,
            linenumber=42,
            file_path="/home/user/notes.org",
        )
        assert item.title == "Test item"
        assert item.item_id == "uuid-123"
        assert item.level == 2
        assert item.linenumber == 42
        assert item.file_path == "/home/user/notes.org"

    def test_defaults_none(self):
        item = Item(
            title="T", item_id="id", level=1, linenumber=1, file_path="/f"
        )
        assert item.todo is None
        assert item.priority is None
        assert item.parent_item_id is None
        assert item.scheduled is None
        assert item.deadline is None
        assert item.closed is None
        assert item.created is None
        assert item.archived_on is None
        assert item.body is None

    def test_defaults_empty_tuples(self):
        item = Item(
            title="T", item_id="id", level=1, linenumber=1, file_path="/f"
        )
        assert item.local_tags == frozenset()
        assert item.inherited_tags == frozenset()
        assert item.active_ts == ()
        assert item.inactive_ts == ()
        assert item.range_ts == ()
        assert item.clock == ()
        assert item.state_changes == ()
        assert item.properties == ()
        assert item.org_links == ()
        assert item.web_links == ()
        assert item.excalidraw_links == ()
        assert item.image_links == ()
        assert item.file_links == ()
        assert item.other_links == ()

    def test_default_raw_text(self):
        item = Item(
            title="T", item_id="id", level=1, linenumber=1, file_path="/f"
        )
        assert item.raw_text == ""


# --- AC4: field types ---


class TestItemFieldTypes:
    """Item fields accept the documented types from README Public API."""

    def test_full_construction(self):
        ts_active = Timestamp(
            date=datetime.datetime(2026, 3, 15, 9, 0),
            active=True,
            repeater="+1w",
        )
        ts_inactive = Timestamp(
            date=datetime.date(2026, 1, 10), active=False
        )
        link = Link(target="abc-123", type="id", description="My note")
        web_link = Link(target="example.com", type="https")
        clock = ClockEntry(
            start=datetime.datetime(2026, 3, 13, 9, 0),
            end=datetime.datetime(2026, 3, 13, 10, 30),
            duration_minutes=90,
        )
        sc = StateChange(
            to_state="DONE",
            from_state="TODO",
            timestamp=datetime.datetime(2026, 3, 13, 14, 0),
        )
        date_range = Range(
            start=Timestamp(date=datetime.date(2026, 1, 1), active=True),
            end=Timestamp(date=datetime.date(2026, 1, 5), active=True),
            active=True,
        )

        item = Item(
            title="Full item",
            item_id="uuid-full",
            level=2,
            linenumber=100,
            file_path="/notes.org",
            todo="DOING",
            priority="A",
            parent_item_id="uuid-parent",
            scheduled=ts_active,
            deadline=ts_active,
            closed=ts_inactive,
            created=ts_inactive,
            archived_on=ts_inactive,
            active_ts=(ts_active,),
            inactive_ts=(ts_inactive,),
            range_ts=(date_range,),
            clock=(clock,),
            state_changes=(sc,),
            body="Some body text with *bold* markup.",
            raw_text="* DOING Full item :tag:\n...",
            org_links=(link,),
            web_links=(web_link,),
            excalidraw_links=(),
            image_links=(),
            file_links=(),
            other_links=(),
            properties=(("Type", "project"), ("EFFORT", "1:00")),
        )

        assert item.todo == "DOING"
        assert item.priority == "A"
        assert item.parent_item_id == "uuid-parent"
        assert item.scheduled.repeater == "+1w"
        assert item.closed.active is False
        assert item.created.date == datetime.date(2026, 1, 10)
        assert item.clock[0].duration_minutes == 90
        assert item.state_changes[0].from_state == "TODO"
        assert item.org_links[0].description == "My note"
        assert item.properties[0] == ("Type", "project")

    def test_timestamp_date_only(self):
        ts = Timestamp(date=datetime.date(2026, 3, 13), active=True)
        assert isinstance(ts.date, datetime.date)
        assert not isinstance(ts.date, datetime.datetime)

    def test_timestamp_datetime(self):
        ts = Timestamp(
            date=datetime.datetime(2026, 3, 13, 9, 0), active=True
        )
        assert isinstance(ts.date, datetime.datetime)

    def test_clock_entry_open(self):
        ce = ClockEntry(start=datetime.datetime(2026, 3, 13, 9, 0))
        assert ce.end is None
        assert ce.duration_minutes is None

    def test_state_change_first_assignment(self):
        sc = StateChange(
            to_state="TODO",
            from_state=None,
            timestamp=datetime.datetime(2026, 3, 13, 9, 0),
        )
        assert sc.from_state is None

    def test_link_no_description(self):
        link = Link(target="uuid-123", type="id")
        assert link.description is None

    def test_link_no_schema(self):
        link = Link(target="some heading", type="")
        assert link.type == ""


# --- AC7: ParseResult ---


class TestParseResult:
    """ParseResult wraps a tuple of Items."""

    def test_empty(self):
        pr = ParseResult()
        assert pr.items == ()

    def test_with_items(self):
        item = Item(
            title="T", item_id="id", level=1, linenumber=1, file_path="/f"
        )
        pr = ParseResult(items=(item,))
        assert len(pr.items) == 1
        assert pr.items[0].title == "T"
