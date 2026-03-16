"""Guard tests for the orgparse private API adapter (S20).

Tests that orgparse internals still have the expected shape.  If orgparse
changes an attribute name or type, these tests fail immediately —
protecting the adapter from silent breakage.

Migrated from: test_timestamps_planning.py (AC10), test_clock.py (AC7),
test_timestamps_generic.py (AC11).
"""
from __future__ import annotations

from pathlib import Path

import orgparse
from orgparse.date import OrgDate, OrgDateClock

from org_dex_parse._orgparse_compat import (
    get_repeater, get_clock_duration, get_body_lines,
)

FIXTURES = Path(__file__).parent / "fixtures"
CLK_ORG = FIXTURES / "clock.org"
TS_ORG = FIXTURES / "timestamps_generic.org"


# -- AC10: guard test for get_repeater (wraps OrgDate._repeater) -----------

class TestRepeaterGuard:
    """Guard test: verify that get_repeater returns the expected format.

    _repeater is a private API.  If orgparse changes the format,
    this test fails immediately — protecting _repeater_to_str from
    silent corruption.
    """

    def test_repeater_is_tuple_of_three(self):
        """AC10: get_repeater returns a 3-tuple (prefix, value, unit)."""
        od = OrgDate.list_from_str("<2026-04-01 Wed +1w>")[0]
        rep = get_repeater(od)
        assert isinstance(rep, tuple)
        assert len(rep) == 3

    def test_repeater_values(self):
        """AC10: +1w → ('+', 1, 'w')."""
        od = OrgDate.list_from_str("<2026-04-01 Wed +1w>")[0]
        prefix, value, unit = get_repeater(od)
        assert prefix == "+"
        assert value == 1
        assert unit == "w"

    def test_repeater_none_when_absent(self):
        """AC10: no repeater → get_repeater returns None."""
        od = OrgDate.list_from_str("<2026-04-01 Wed>")[0]
        assert get_repeater(od) is None


# -- AC7: guard test for get_clock_duration (wraps OrgDateClock._duration) -

class TestClockDurationGuard:
    """Guard test: verify that get_clock_duration returns the expected type.

    _duration is a private API.  If orgparse changes the attribute name
    or type, this test fails immediately — protecting clock extraction
    from silent breakage.
    """

    def test_duration_is_int_on_closed(self):
        """AC7: get_clock_duration returns int (minutes) on closed clock."""
        root = orgparse.load(str(CLK_ORG))
        # clk-001 is the first real node — has closed clocks.
        node = root[1]
        assert len(node.clock) > 0
        cl = node.clock[0]
        assert isinstance(cl, OrgDateClock)
        assert isinstance(get_clock_duration(cl), int)

    def test_duration_is_none_on_open(self):
        """AC7: get_clock_duration returns None on open clock."""
        root = orgparse.load(str(CLK_ORG))
        # clk-002 is the second real node — has open clock.
        node = root[2]
        assert len(node.clock) > 0
        cl = node.clock[0]
        assert get_clock_duration(cl) is None


# -- AC11: guard test for get_body_lines (wraps node._body_lines) ----------

class TestBodyLinesGuard:
    """Guard test: verify that get_body_lines returns the expected type.

    _body_lines is a private API.  If orgparse changes the attribute
    name or type, this test fails immediately — protecting the timestamp
    extraction from silent breakage.
    """

    def test_body_lines_exists(self):
        """AC11: get_body_lines returns a value (no AttributeError)."""
        root = orgparse.load(str(TS_ORG))
        # First real node (skip virtual root).
        node = root[1]
        lines = get_body_lines(node)
        assert lines is not None

    def test_body_lines_is_list_of_strings(self):
        """AC11: get_body_lines returns a list of strings."""
        root = orgparse.load(str(TS_ORG))
        node = root[1]
        lines = get_body_lines(node)
        assert isinstance(lines, list)
        for line in lines:
            assert isinstance(line, str)
