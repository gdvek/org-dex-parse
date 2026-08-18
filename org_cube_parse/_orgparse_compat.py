"""Adapter for orgparse private API (S20).

Centralizes all accesses to orgparse internals so the rest of the
codebase depends only on this module.  If orgparse changes an
internal attribute, this is the only file to update.

Each function documents which private attribute it wraps and has
a corresponding guard test in tests/test_orgparse_compat.py.
"""
from __future__ import annotations

import re
from typing import Any

import orgparse.node as _orgparse_node

# Save the original tag regex at import time so we can restore it
# when extra_tag_chars is not needed.  Used by apply_tag_patch.
_ORIGINAL_RE_HEADING_TAGS = _orgparse_node.RE_HEADING_TAGS


def get_repeater(od: Any) -> tuple | None:
    """Return the repeater cookie from an OrgDate.

    Wraps: od._repeater — a 3-tuple (prefix, value, unit) where
    prefix is '+', '++', or '.+', value is int, unit is char.
    Returns None when no repeater is present.

    Guard test: TestRepeaterGuard in test_orgparse_compat.py.
    """
    return od._repeater


def get_clock_duration(cl: Any) -> int | None:
    """Return the duration in minutes from an OrgDateClock.

    Wraps: cl._duration — int (minutes) on closed clocks, None on
    open clocks.  The public .duration property raises TypeError on
    open clocks, so we use the private attribute.

    Guard test: TestClockDurationGuard in test_orgparse_compat.py.
    """
    return cl._duration


def get_body_lines(node: Any) -> list[str]:
    """Return body lines with planning and PROPERTIES already excluded.

    Wraps: node._body_lines — a list of strings, one per line.
    orgparse builds this by removing the planning line and the
    PROPERTIES drawer from the node's raw body.

    Guard test: TestBodyLinesGuard in test_orgparse_compat.py.
    """
    return node._body_lines


def apply_tag_patch(extra_tag_chars: str) -> None:
    """Set or restore the orgparse tag regex based on extra_tag_chars.

    HACK(S04): orgparse only accepts [a-zA-Z0-9_@] in tags.
    Workflows that use additional characters need an extended regex.

    If extra_tag_chars is non-empty, overrides
    orgparse.node.RE_HEADING_TAGS with an extended regex.
    If empty, restores the original regex.

    Why a monkey-patch: orgparse does not expose tag character
    configuration.  The proper fix is an upstream PR or a fork.

    Limitation: not thread-safe — modifies a module-level global.
    Acceptable for single-threaded use.
    """
    if extra_tag_chars:
        _orgparse_node.RE_HEADING_TAGS = re.compile(
            rf'(.*?)\s*:([\w@{re.escape(extra_tag_chars)}:]+):\s*$'
        )
    else:
        _orgparse_node.RE_HEADING_TAGS = _ORIGINAL_RE_HEADING_TAGS
