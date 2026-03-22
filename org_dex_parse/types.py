"""Data types for parsed org-mode items.

All types are frozen dataclasses — immutable value objects.  The parser
collects data in a mutable dict and constructs these at the end via
Item(**data).  See architecture.org for the design rationale.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Timestamp:
    """A single org-mode timestamp with optional repeater cookie.

    :arg date: The base date.  ``datetime.date`` when no time component,
        ``datetime.datetime`` when time is present.
    :arg active: True for active ``<...>``, False for inactive ``[...]``.
    :arg repeater: Raw repeater string (e.g. ``"+1w"``), or None.
    """

    date: datetime.date | datetime.datetime
    active: bool
    repeater: str | None = None


@dataclass(frozen=True)
class Link:
    """A single org-mode link.

    :arg target: The raw link target as it appears inside ``[[...]]``
        in org-mode.  For ``[[id:abc-123]]`` this is ``"id:abc-123"``.
        For ``[[https://example.com]]`` this is ``"https://example.com"``.
        For fuzzy links ``[[Some heading]]`` this is ``"Some heading"``.
        No decomposition: the consumer extracts the schema if needed.
    :arg description: Display text from ``[description]``, or None.
    """

    target: str
    description: str | None = None


@dataclass(frozen=True)
class Range:
    """A date range: double-dash or intra-day.

    :arg start: Start of the range as a Timestamp.
    :arg end: End of the range as a Timestamp.
    :arg active: True for active ranges, False for inactive.
    """

    start: Timestamp
    end: Timestamp
    active: bool


@dataclass(frozen=True)
class ClockEntry:
    """A single CLOCK entry from the LOGBOOK drawer.

    :arg start: Session start time (always datetime).
    :arg end: Session end time, or None for open clocks.
    :arg duration_minutes: Duration in minutes, or None for open clocks.
    """

    start: datetime.datetime
    end: datetime.datetime | None = None
    duration_minutes: int | None = None


@dataclass(frozen=True)
class StateChange:
    """A single TODO-keyword state transition from the LOGBOOK drawer.

    :arg to_state: The new TODO keyword (e.g. ``"DONE"``).
    :arg from_state: The previous keyword, or None for first assignment.
    :arg timestamp: When the transition occurred (always datetime).
    """

    to_state: str
    from_state: str | None
    timestamp: datetime.datetime


# Item field ordering: required fields first (no default), then optional
# fields with defaults.  Python dataclass requires this: fields without
# defaults must precede fields with defaults.


@dataclass(frozen=True)
class Item:
    """A single parsed org-mode item.

    Only headings with ``:ID:`` that pass the configured predicate produce
    an Item.  Fields are grouped by role; required fields (no default)
    come first, optional fields (with defaults) follow.

    The parser builds Items via dict: collect data incrementally, then
    ``Item(**data)``.  Defaults allow skeleton construction (S03) with
    only the 5 required fields; subsequent stories fill the rest.
    """

    # --- Required (no default) ---

    # Identity
    title: str
    item_id: str

    # Structure
    level: int

    # Source position
    linenumber: int
    file_path: str

    # --- Optional with defaults ---

    # Semantic
    todo: str | None = None
    priority: str | None = None
    local_tags: frozenset[str] = frozenset()
    inherited_tags: frozenset[str] = frozenset()

    # Structure (optional)
    parent_item_id: str | None = None

    # Planning
    scheduled: Timestamp | None = None
    deadline: Timestamp | None = None
    closed: Timestamp | None = None

    # Temporal
    created: Timestamp | None = None
    archived: Timestamp | None = None
    active_ts: tuple[Timestamp, ...] = ()
    inactive_ts: tuple[Timestamp, ...] = ()
    range_ts: tuple[Range, ...] = ()

    # LOGBOOK
    clock: tuple[ClockEntry, ...] = ()
    state_changes: tuple[StateChange, ...] = ()

    # Content
    body: str | None = None
    raw_text: str = ""

    # Links — flat tuple; classification is the consumer's responsibility
    links: tuple[Link, ...] = ()

    # Properties
    properties: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ParseWarning:
    """A non-critical issue found during parsing.

    L12 (S19g) detects headings that match the item predicate but lack
    ``:ID:`` — "quasi-items" the user likely forgot to assign an ID to.
    This check requires the AST and compiled predicate, so it lives in
    the parser rather than the pre-parse linter.

    Same shape as org-dex's ``LintProblem`` but independent type — the
    parser package does not depend on the daemon package.  The pipeline
    converts at the boundary (anti-corruption layer).

    :arg line: 1-based line number of the heading.
    :arg code: Stable check code (e.g. ``"L12"``).
    :arg message: Human-readable description.
    :arg severity: ``"error"`` or ``"warning"``.
    """

    line: int
    code: str
    message: str
    severity: str


@dataclass(frozen=True)
class ParseResult:
    """Result of parsing an org file.

    Wraps the item tuple so the return type can grow without breaking
    callers.

    :arg items: Parsed items in file order.
    :arg warnings: Non-critical issues found during parsing (e.g. L12).
    """

    items: tuple[Item, ...] = ()
    warnings: tuple[ParseWarning, ...] = ()
