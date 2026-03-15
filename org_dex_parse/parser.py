"""Tree walk, item discrimination, and raw_text collection.

Walks the orgparse tree, partitions headings into items and scaffolding
using the unified is_item check (:ID: invariant + configurable predicate),
collects raw_text for each item (item minus sub-items), and builds a
ParseResult with structural fields and raw_text.
"""
from __future__ import annotations

import re
import textwrap
from typing import Any, Callable

import orgparse
import orgparse.node as _orgparse_node
from orgparse.node import OrgEnv

from .config import Config
from orgparse.date import OrgDate

from .types import (
    ClockEntry, Item, Link, ParseResult, Range, StateChange, Timestamp,
)

# Save the original tag regex at import time so we can restore it
# when extra_tag_chars is not needed.  Used by the HACK(S04) monkey-patch.
_ORIGINAL_RE_HEADING_TAGS = _orgparse_node.RE_HEADING_TAGS

# -- Link extraction (S09a) ---------------------------------------------------

# Pass 1: org-mode links — [[target][description]] or [[target]].
# Aligned with org-mode's org-link-bracket-re semantics:
#   - Target: no raw [ or ] (org-mode also handles \-escaping, we don't
#     because Remi data doesn't use it).
#   - Description: any character, non-greedy — stops at first ]].
#     This correctly handles ] and [ inside descriptions (fix F-LK4:
#     descriptions like "[] Title" or "[TYPE] Title").
# Backslash escaping in targets is not implemented (no Remi use case).
_RE_ORG_LINK = re.compile(
    r'\[\['
    r'([^\[\]]+)'            # target: no [ or ] (aligned with org-mode)
    r'\]'
    r'(?:\[([\s\S]+?)\])?'   # description: any char, non-greedy
    r'\]'
)

# Pass 2: bare URLs — http:// or https://.
_RE_BARE_URL = re.compile(r'https?://[^\s\[\]<>]+')

# Characters stripped from the end of bare URLs (trailing punctuation
# that is syntactically part of the surrounding sentence, not the URL).
_BARE_URL_TRAILING = set(",;:)")


def _extract_links(text: str) -> tuple[Link, ...]:
    """Extract all links from raw_text in two passes.

    Pass 1 finds org-mode links ([[target][desc]] and [[target]]),
    records their character spans so pass 2 can skip overlapping bare
    URLs (dedup — AC5).

    Pass 2 finds bare http/https URLs, strips trailing punctuation
    (AC4), and skips any match whose span overlaps a pass-1 match.

    Both passes collect (position, Link) pairs, then sort by position
    to produce links in document order (AC11).
    """
    # Collect (start_position, Link) pairs from both passes, then
    # sort by position to interleave org links and bare URLs correctly.
    found: list[tuple[int, Link]] = []
    # Spans occupied by pass-1 matches — used by pass 2 for dedup.
    occupied: list[tuple[int, int]] = []

    # -- Pass 1: org-mode links -----------------------------------------------
    for m in _RE_ORG_LINK.finditer(text):
        raw_target = m.group(1)
        description = m.group(2)  # None if no [desc] part
        found.append((m.start(), Link(target=raw_target,
                                      description=description)))
        occupied.append((m.start(), m.end()))

    # -- Pass 2: bare URLs ----------------------------------------------------
    for m in _RE_BARE_URL.finditer(text):
        # Skip if this bare URL overlaps any org-link span (AC5).
        bare_start = m.start()
        if any(occ_s <= bare_start < occ_e
               for occ_s, occ_e in occupied):
            continue

        url = m.group()
        # Strip trailing punctuation (AC4).
        while url and url[-1] in _BARE_URL_TRAILING:
            url = url[:-1]

        # Bare URLs are stored as-is (complete URL).
        found.append((bare_start, Link(target=url, description=None)))

    # Sort by position for document order (AC11).
    found.sort(key=lambda x: x[0])
    return tuple(link for _, link in found)


# -- OrgDate conversion (S09b-1) ----------------------------------------------

def _repeater_to_str(od: Any) -> str | None:
    """Extract the repeater cookie from an OrgDate as a string.

    Accesses the private _repeater attribute — a 3-tuple (prefix, value, unit)
    where prefix is '+', '++', or '.+', value is an int, and unit is a
    single char ('d', 'w', 'm', 'y').  Returns e.g. '+1w', '++2d', '.+1m'.

    Returns None when no repeater is present.  Protected by guard test AC10.
    """
    rep = od._repeater
    if rep is None:
        return None
    prefix, value, unit = rep
    return f"{prefix}{value}{unit}"


def _orgdate_to_timestamp(od: Any) -> Timestamp:
    """Convert an orgparse OrgDate to our Timestamp type.

    Maps OrgDate fields to Timestamp: date preserves the date/datetime
    distinction from orgparse (date-only vs date+time), active reflects
    angle vs square brackets, repeater is extracted via _repeater_to_str.

    Used for planning fields (S09b-1) and generic timestamps (S09b-4).
    """
    return Timestamp(
        date=od.start,
        active=od.is_active(),
        repeater=_repeater_to_str(od),
    )


def _orgdate_to_range(od: Any) -> Range:
    """Convert an orgparse OrgDate with end to our Range type.

    Uses _orgdate_to_timestamp for the start (preserving repeater),
    and builds the end Timestamp directly (ranges don't carry repeaters
    on the end component).  active reflects the bracket type.

    Used for generic timestamps (S09b-4).
    """
    return Range(
        start=_orgdate_to_timestamp(od),
        end=Timestamp(date=od.end, active=od.is_active(), repeater=None),
        active=od.is_active(),
    )


# -- Generic timestamp extraction (S09b-4) ------------------------------------

# Drawer delimiters for LOGBOOK exclusion from _body_lines.
# The LOGBOOK drawer contains structured logging data (CLOCK, state changes,
# refile entries, capture entries, notes) — all with timestamps that must NOT
# appear in generic timestamp fields.  We exclude the entire :LOGBOOK:...:END:
# block rather than filtering individual line types, because the LOGBOOK can
# contain many entry types (- Refiled on, - CAPTURED ON, - Note taken on, etc.)
# beyond just CLOCK and State.
#
# LIMITATION (S09b-5): this filter is hardcoded on the drawer name "LOGBOOK",
# which is the default when org-log-into-drawer = t.  Two alternative org-mode
# configurations are NOT supported:
#   1. Custom drawer name (org-log-into-drawer = a string, e.g. "CLOCKING")
#      → logging data ends up in a drawer we don't filter.
#   2. Inline logging (org-log-into-drawer = nil) → state changes, Refiled,
#      Captured, Note entries stay in _body_lines unfiltered.
# In both cases, logging timestamps would appear as false positives in
# inactive_ts.  This is acceptable for now — the standard LOGBOOK covers
# the common case.  If custom drawer support is needed, the natural evolution
# is a Config.log_drawer field (str | None, default "LOGBOOK").
_RE_LOGBOOK_START = re.compile(r'^\s*:LOGBOOK:\s*$')
_RE_DRAWER_END = re.compile(r'^\s*:END:\s*$')


def _strip_link_descriptions(text: str) -> str:
    """Remove descriptions from org links before timestamp extraction.

    Replaces [[target][description]] with [[target]], so that
    timestamp-like text in descriptions (e.g. [[url][2026-01-15 report]])
    is not falsely extracted by OrgDate.list_from_str.  Fix for F-TS3.
    """
    return _RE_ORG_LINK.sub(lambda m: f"[[{m.group(1)}]]", text)


def _collect_timestamps(
    node: Any, predicate: Callable[[Any], bool]
) -> tuple[tuple[Timestamp, ...], tuple[Timestamp, ...], tuple[Range, ...]]:
    """Collect generic timestamps from an item's scope.

    Walks the item subtree node-by-node (same pattern as _collect_raw_text):
    includes the item node itself, recurses into non-item children, skips
    item children.

    For each node, extracts timestamps from two structured sources:
    1. node.heading — timestamps in the heading line
    2. node._body_lines — body text with planning and PROPERTIES already
       excluded by orgparse, further filtered to exclude the :LOGBOOK:
       drawer (CLOCK, state changes, refile, capture, note entries)

    For scaffolding nodes (non-root), planning timestamps become generics:
    SCHEDULED/DEADLINE → active_ts, CLOSED → inactive_ts.

    Returns (active_ts, inactive_ts, range_ts) in document order.
    """
    active: list[Timestamp] = []
    inactive: list[Timestamp] = []
    ranges: list[Range] = []

    _collect_timestamps_walk(node, predicate, active, inactive, ranges,
                             is_item_node=True)

    return tuple(active), tuple(inactive), tuple(ranges)


def _classify_orgdate(
    od: Any,
    active: list[Timestamp],
    inactive: list[Timestamp],
    ranges: list[Range],
) -> None:
    """Classify an OrgDate into the appropriate list.

    has_end() → Range, is_active() → active_ts, else → inactive_ts.
    """
    if od.has_end():
        ranges.append(_orgdate_to_range(od))
    elif od.is_active():
        active.append(_orgdate_to_timestamp(od))
    else:
        inactive.append(_orgdate_to_timestamp(od))


def _collect_timestamps_walk(
    node: Any,
    predicate: Callable[[Any], bool],
    active: list[Timestamp],
    inactive: list[Timestamp],
    ranges: list[Range],
    is_item_node: bool = False,
) -> None:
    """Recursive walk for timestamp collection.

    is_item_node distinguishes the item itself (planning → dedicated fields)
    from scaffolding nodes (planning → generic timestamps).
    """
    # Source 1: heading — timestamps in the heading line.
    heading_text = _strip_link_descriptions(node.heading)
    for od in OrgDate.list_from_str(heading_text):
        _classify_orgdate(od, active, inactive, ranges)

    # Source 2: _body_lines — planning and PROPERTIES already excluded
    # by orgparse.  Exclude the entire :LOGBOOK: drawer (CLOCK, state
    # changes, refile/capture/note entries — all logging data with
    # timestamps that belong to dedicated fields, not generics).
    body_lines: list[str] = []
    in_logbook = False
    for line in node._body_lines:
        if not in_logbook and _RE_LOGBOOK_START.match(line):
            in_logbook = True
            continue
        if in_logbook:
            if _RE_DRAWER_END.match(line):
                in_logbook = False
            continue
        body_lines.append(line)
    body_text = _strip_link_descriptions("\n".join(body_lines))
    for od in OrgDate.list_from_str(body_text):
        _classify_orgdate(od, active, inactive, ranges)

    # Scaffolding planning → generic timestamps.
    # The item's own planning is in dedicated fields (S09b-1); scaffolding
    # planning has no dedicated destination, so it becomes generic.
    if not is_item_node:
        if node.scheduled:
            _classify_orgdate(node.scheduled, active, inactive, ranges)
        if node.deadline:
            _classify_orgdate(node.deadline, active, inactive, ranges)
        if node.closed:
            _classify_orgdate(node.closed, active, inactive, ranges)

    # Recurse into non-item children (scaffolding).
    for child in node.children:
        if is_item(child, predicate):
            continue
        _collect_timestamps_walk(child, predicate, active, inactive, ranges)


# -- Timestamp property parsing (S09b-2) ---------------------------------------

# Regex for org-mode timestamp in a property value.  Handles three forms:
#   - active:   <2026-03-01 Sun 14:30>
#   - inactive: [2026-03-01 Sun 14:30]
#   - bare:     2026-03-01 Sun 14:30
# Day-of-week is optional and ignored.  Time (HH:MM) is optional — when
# absent, date is datetime.date; when present, datetime.datetime.
# Named groups: open (delimiter), year/month/day, hour/minute, close.
_RE_TIMESTAMP_PROPERTY = re.compile(
    r'^\s*(?P<open>[<\[])?'                  # optional opening delimiter
    r'\s*(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})'  # YYYY-MM-DD
    r'(?:\s+\w+)?'                           # optional day-of-week (ignored)
    r'(?:\s+(?P<hour>\d{2}):(?P<minute>\d{2}))?'  # optional HH:MM
    r'\s*(?:[>\]])?'                         # optional closing delimiter
    r'\s*$'
)


def _parse_timestamp_property(value: str) -> Timestamp | None:
    """Parse a timestamp string from an org property value.

    Handles active (<>), inactive ([]), and bare (no delimiters) forms.
    Returns None on malformed input (regex no match).

    active flag: True only for <> delimiters, False for [] and bare.
    repeater: always None — property timestamps don't carry repeaters.

    Reusable: S09b-2 (created) and S09b-3 (archived) both call this.
    """
    m = _RE_TIMESTAMP_PROPERTY.match(value)
    if m is None:
        return None

    year = int(m.group("year"))
    month = int(m.group("month"))
    day = int(m.group("day"))

    # Time component determines date vs datetime (AC5/AC6).
    if m.group("hour") is not None:
        import datetime
        date = datetime.datetime(year, month, day,
                                 int(m.group("hour")),
                                 int(m.group("minute")))
    else:
        import datetime
        date = datetime.date(year, month, day)

    # Active only when explicitly delimited with <> (AC7).
    active = m.group("open") == "<"

    return Timestamp(date=date, active=active, repeater=None)


# -- Clock extraction (S09c-1) ------------------------------------------------

def _collect_clock(
    node: Any, predicate: Callable[[Any], bool]
) -> tuple[ClockEntry, ...]:
    """Collect CLOCK entries from an item's scope.

    Walks the item subtree node-by-node (same pattern as _collect_raw_text
    and _collect_timestamps): includes the item node itself, recurses into
    non-item children (scaffolding), skips item children (separate items).

    Uses orgparse's node.clock API (list[OrgDateClock]) — no regex needed.
    Each OrgDateClock is converted to our ClockEntry type.

    Returns entries in chronological order.  The LOGBOOK drawer grows upward
    (newest entry at top), so node.clock is in reverse-chronological order.
    We collect all entries, then reverse the full list once at the end.
    """
    entries: list[ClockEntry] = []
    _collect_clock_walk(node, predicate, entries)
    # Reverse for chronological order: oldest first.
    entries.reverse()
    return tuple(entries)


def _collect_clock_walk(
    node: Any,
    predicate: Callable[[Any], bool],
    entries: list[ClockEntry],
) -> None:
    """Recursive walk for clock collection.

    Converts each OrgDateClock to ClockEntry using _duration (private API,
    guarded by test AC7).  _duration is int (minutes) on closed clocks,
    None on open clocks.  The public .duration property computes a timedelta
    from end-start and raises TypeError on open clocks — so we use _duration.
    """
    for cl in node.clock:
        entries.append(ClockEntry(
            start=cl.start,
            end=cl.end,
            duration_minutes=cl._duration,
        ))

    # Recurse into non-item children (scaffolding).
    for child in node.children:
        if is_item(child, predicate):
            continue
        _collect_clock_walk(child, predicate, entries)


# -- State change extraction (S09c-2) ----------------------------------------

# Regex for org-mode state change lines in the LOGBOOK drawer.
# Format from org-log-note-headings: "State %-12s from %-12S%t"
# Two variants:
#   Normal:    - State "DONE"       from "TODO"       [2026-03-10 Tue 10:30]
#   First:     - State "TODO"       from              [2026-03-10 Tue 10:30]
# First assignment has no quotes after "from" — the quoted group is optional.
# The %-12s padding produces variable whitespace, handled by \s+.
# Note lines (trailing \\) are on subsequent lines and don't affect this regex.
_RE_STATE_CHANGE = re.compile(
    r'- State\s+"(?P<to>[^"]+)"\s+'
    r'from\s+(?:"(?P<from>[^"]+)")?\s*'
    r'\[(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})'
    r'\s+\w+'                          # day-of-week, ignored
    r'(?:\s+(?P<hour>\d{2}):(?P<minute>\d{2}))?'  # optional time
    r'\]'
)


def _extract_state_changes(text: str) -> tuple[StateChange, ...]:
    """Extract state changes from an item node's text.

    Parses str(node) — the item's own lines — for state change entries.
    No walk scaffolding: state changes are the history of this specific
    heading's TODO keyword, not of its children.  This differs from clock
    entries (which aggregate time across scaffolding).

    Same approach as remi-org-parse: regex on str(node), no orgparse API.

    Returns entries in chronological order.  The LOGBOOK grows upward
    (newest first), so matches are in reverse-chronological order.
    We collect all, then reverse once at the end.
    """
    import datetime

    entries: list[StateChange] = []
    for m in _RE_STATE_CHANGE.finditer(text):
        year = int(m.group("year"))
        month = int(m.group("month"))
        day = int(m.group("day"))

        # Time is always present in org-mode state changes, but we handle
        # date-only for robustness (AC7): default to midnight.
        if m.group("hour") is not None:
            ts = datetime.datetime(year, month, day,
                                   int(m.group("hour")),
                                   int(m.group("minute")))
        else:
            ts = datetime.datetime(year, month, day, 0, 0)

        # First assignment: "from" without quotes → group is None → None.
        # Normal: "from" with quotes → captured string.
        from_state = m.group("from")

        entries.append(StateChange(
            to_state=m.group("to"),
            from_state=from_state,
            timestamp=ts,
        ))

    # Reverse for chronological order: oldest first.
    entries.reverse()
    return tuple(entries)


# -- Body extraction (S09d) ---------------------------------------------------

# Drawer opener: :NAME: on its own line (whitespace-tolerant).
# Reuses the same pattern as _RE_LOGBOOK_START but generalized: any drawer
# name, not just LOGBOOK.  The stripped line must start and end with ':'
# and have at least one character between them.
#
# Block opener: #+BEGIN_NAME [args...] on its own line.
# Block closer is name-specific: #+END_NAME (not generic :END: like drawers).
# Both patterns are handled inline in _filter_body_text — no compiled regex
# needed because the checks are simple string operations.


def _filter_body_text(
    text: str,
    exclude_drawers: frozenset[str],
    exclude_blocks: frozenset[str],
) -> str:
    """Strip excluded drawers and blocks from body text.

    Single-pass state machine over the lines of get_body('plain').
    LOGBOOK is always excluded (hardcoded, merged into the drawer set).
    Config drawers and blocks are excluded per configuration.

    Drawer detection: :NAME: on its own line (after stripping whitespace),
    closed by :END:.  Case-insensitive.
    Block detection: #+BEGIN_NAME [args...], closed by #+END_NAME.
    Case-insensitive.  Block name is the first token after #+BEGIN_.

    Drawers and blocks cannot nest in org-mode, so one state variable
    (outside / inside-drawer / inside-block) is sufficient.
    """
    # Merge LOGBOOK into the exclusion set — always excluded from body.
    all_exclude_drawers = exclude_drawers | frozenset({"logbook"})

    lines = text.splitlines(True)  # preserve line endings
    result: list[str] = []
    inside_drawer = False
    inside_block_name: str | None = None

    for line in lines:
        stripped = line.strip()

        # Inside an excluded drawer — skip everything until :END:.
        if inside_drawer:
            if stripped.upper() == ":END:":
                inside_drawer = False
            continue

        # Inside an excluded block — skip until the matching #+END_NAME.
        if inside_block_name is not None:
            if stripped.upper() == f"#+END_{inside_block_name}":
                inside_block_name = None
            continue

        # Check for drawer opener: :NAME: on its own line.
        # Minimum length 3 (:X:), starts and ends with ':'.
        if (
            stripped.startswith(":")
            and stripped.endswith(":")
            and len(stripped) > 2
        ):
            name = stripped[1:-1].lower()
            if name in all_exclude_drawers:
                inside_drawer = True
                continue

        # Check for block opener: #+BEGIN_NAME [args...].
        stripped_upper = stripped.upper()
        if stripped_upper.startswith("#+BEGIN_"):
            after = stripped_upper[8:]
            name = after.split()[0] if after else ""
            if name.lower() in exclude_blocks:
                inside_block_name = name
                continue

        result.append(line)

    return "".join(result)


def _collect_body(
    node: Any,
    predicate: Callable[[Any], bool],
    exclude_drawers: frozenset[str],
    exclude_blocks: frozenset[str],
) -> str | None:
    """Collect body text from an item's scope.

    Walks the item subtree node-by-node (same pattern as _collect_raw_text
    and _collect_timestamps): includes the item node itself, recurses into
    non-item children (scaffolding), skips item children (separate items).

    For each node, collects get_body('plain') — org-mode link syntax
    resolved to descriptions, other markup preserved.  The result is
    filtered through _filter_body_text to strip excluded drawers and blocks.

    Scaffolding nodes contribute their heading (node.heading) in addition
    to their body text — fix F-BD3.

    Returns None when the result is empty after stripping.
    """
    parts: list[str] = []
    _collect_body_walk(node, predicate, exclude_drawers, exclude_blocks,
                       parts, is_item_node=True)

    text = "\n".join(parts).strip()
    return text if text else None


def _collect_body_walk(
    node: Any,
    predicate: Callable[[Any], bool],
    exclude_drawers: frozenset[str],
    exclude_blocks: frozenset[str],
    parts: list[str],
    is_item_node: bool = False,
) -> None:
    """Recursive walk for body collection.

    is_item_node distinguishes the item itself (no heading — already in
    Item.title) from scaffolding nodes (heading included as body content).
    """
    # Scaffolding nodes: include heading as body content (fix F-BD3).
    # node.heading is the clean title (orgparse strips TODO, priority, tags).
    if not is_item_node:
        parts.append(node.heading)

    # Collect this node's body text (plain format: links resolved,
    # other markup preserved).  Filter out excluded drawers/blocks.
    # textwrap.dedent removes org-mode heading-level indentation for
    # consistent output.
    body = textwrap.dedent(
        _filter_body_text(
            node.get_body(format='plain'),
            exclude_drawers,
            exclude_blocks,
        )
    ).strip()
    if body:
        parts.append(body)

    # Recurse into non-item children (scaffolding).
    for child in node.children:
        if is_item(child, predicate):
            continue
        _collect_body_walk(child, predicate, exclude_drawers, exclude_blocks,
                           parts)


def is_item(node: Any, predicate: Callable[[Any], bool]) -> bool:
    """Unified item boundary check.

    A heading is an item if and only if it has an :ID: property (structural
    invariant) AND the predicate returns True.  This single function is used
    everywhere — in the main walk and in _find_parent_id — to guarantee
    that the discrimination criterion is always the same.

    Why a single helper: remi-org-parse had 4 separate helpers that checked
    the predicate without pre-checking :ID:, causing silent data corruption
    (headings without :ID: recognized as item boundaries).
    """
    return node.get_property("ID") is not None and predicate(node)


def _find_parent_id(
    node: Any, predicate: Callable[[Any], bool]
) -> str | None:
    """Walk up the tree to find the nearest item ancestor.

    Non-item headings are transparent — they are skipped.  Returns the
    :ID: of the first ancestor that passes is_item, or None if the node
    is top-level (no item ancestor exists).

    Stop condition: orgparse's virtual root has level == 0.
    """
    ancestor = node.parent
    while ancestor.level > 0:
        if is_item(ancestor, predicate):
            return ancestor.get_property("ID")
        ancestor = ancestor.parent
    return None


def _apply_tag_monkey_patch(extra_tag_chars: str) -> None:
    """Set or restore the orgparse tag regex based on extra_tag_chars.

    HACK(S04): orgparse only accepts [a-zA-Z0-9_@] in tags (the org-mode
    standard).  Workflows that use additional characters (e.g. % for
    identity, # for entities) need an extended regex.

    If extra_tag_chars is non-empty, we override orgparse._parser.RE_HEADING_TAGS
    with a regex that includes the extra characters.  If empty, we restore
    the original regex.  This is called at the start of every parse_file
    to ensure idempotency across calls with different configs.

    Why a monkey-patch: orgparse does not expose tag character configuration.
    The proper fix is an upstream PR or a fork.

    Limitation: not thread-safe — modifies a module-level global.
    Acceptable for single-threaded use.
    """
    if extra_tag_chars:
        _orgparse_node.RE_HEADING_TAGS = re.compile(
            rf'(.*?)\s*:([\w@{re.escape(extra_tag_chars)}:]+):\s*$'
        )
    else:
        _orgparse_node.RE_HEADING_TAGS = _ORIGINAL_RE_HEADING_TAGS


def _collect_raw_text(
    node: Any, predicate: Callable[[Any], bool]
) -> str:
    """Collect the complete unfiltered source text for an item node.

    Concatenates str(node) — the original file lines for this node
    (heading, PROPERTIES, planning, drawers, body, everything) — then
    recurses into non-item children.  Children passing is_item are
    separate items and are skipped entirely.

    No filtering is applied: no drawer exclusion, no block exclusion,
    no dedenting, no markup stripping.  The result is the raw org-mode
    source text that belongs to this item.

    Same algorithm as remi-org-parse _collect_raw_text (body.py:45-77),
    with is_item as the unified gate instead of the hardcoded :Type: check.
    """
    parts: list[str] = [str(node)]

    for child in node.children:
        if is_item(child, predicate):
            continue
        parts.append(_collect_raw_text(child, predicate))

    return "\n".join(parts)


def parse_file(path: str, config: Config) -> ParseResult:
    """Parse an org file into a ParseResult with Items.

    Loads the file via orgparse (passing todos/dones through OrgEnv for
    correct keyword recognition), walks all nodes in document order, and
    builds an Item for each heading that passes the is_item check.
    Each Item includes raw_text — the complete unfiltered source text
    for that item, minus sub-items.
    """
    # Normalize path to string for consistent file_path values.
    path_str = str(path)

    # HACK(S04): apply or restore the tag monkey-patch before loading
    # the file — orgparse parses tags during load().
    _apply_tag_monkey_patch(config.extra_tag_chars)

    # Build OrgEnv so orgparse recognizes TODO/DONE keywords and
    # correctly strips them from node.heading.
    # Pass todos/dones as lists.  Empty list means "no keywords" —
    # orgparse treats None as "use defaults ['TODO']/['DONE']", which
    # is not what we want when the consumer explicitly passes nothing.
    env = OrgEnv(
        todos=list(config.todos),
        dones=list(config.dones),
        filename=path_str,
    )

    root = orgparse.load(path_str, env=env)

    predicate = config.item_predicate

    # Property names always excluded from Item.properties.
    # ID → already in item_id; ARCHIVE_TIME → archived;
    # created_property → future created.  All compared lowercase.
    always_excluded_props = {
        "id", "archive_time", config.created_property.lower()
    }
    excluded_props = always_excluded_props | config.exclude_properties

    items: list[Item] = []

    # root[1:] iterates ALL nodes in document order, skipping the
    # virtual root.  No recursion needed — orgparse provides a flat
    # iterator over the entire tree.
    for node in root[1:]:
        if is_item(node, predicate):
            # -- Properties (AC1–AC6) ----------------------------------------
            # node.properties is the direct PROPERTIES drawer only (no
            # subtree) — this prevents F-PR1 (subtree leakage) by design.
            # str(v) preserves values as-is — prevents F-PR2 (effort
            # normalization).
            props = tuple(
                (k, str(v))
                for k, v in node.properties.items()
                if k.lower() not in excluded_props
            )

            # -- Tags (AC7–AC9) ----------------------------------------------
            # Filter empty strings before classification (fix F-TG1:
            # malformed headings like '::' produce empty-string tags).
            raw_local = frozenset(t for t in node.shallow_tags if t)
            raw_all = frozenset(t for t in node.tags if t)
            inherited = frozenset(
                raw_all - raw_local
                - config.tags_exclude_from_inheritance
            )

            # -- TODO and priority (AC12–AC13) --------------------------------
            # node.todo is "" when absent — normalize to None.
            # node.priority is already None when absent.
            todo = node.todo if node.todo else None
            priority = node.priority

            # -- Planning timestamps (S09b-1) ---------------------------------
            # node.scheduled/deadline/closed return OrgDate objects that are
            # falsy when absent (od.start is None), not Python None.
            # All three wrapped in Timestamp for consistency (remi-org-parse
            # had closed as bare datetime — we normalize).
            scheduled = (
                _orgdate_to_timestamp(node.scheduled)
                if node.scheduled else None
            )
            deadline = (
                _orgdate_to_timestamp(node.deadline)
                if node.deadline else None
            )
            closed = (
                _orgdate_to_timestamp(node.closed)
                if node.closed else None
            )

            # -- Created timestamp (S09b-2) ------------------------------------
            # Read from the configurable property (default "CREATED").
            # node.get_property accesses only the direct PROPERTIES drawer,
            # not children — same mechanism as :ID: and :Type:.
            created_raw = node.get_property(config.created_property)
            created = (
                _parse_timestamp_property(created_raw)
                if created_raw else None
            )

            # -- Archived timestamp (S09b-3) ----------------------------------
            # ARCHIVE_TIME is written by org-archive-subtree in bare format
            # (no delimiters).  _parse_timestamp_property handles bare → active=False.
            archive_raw = node.get_property("ARCHIVE_TIME")
            archived = (
                _parse_timestamp_property(archive_raw)
                if archive_raw else None
            )

            # -- Raw text and links (S06, S09a) --------------------------------
            # Collect raw_text first, then extract links from it.
            # Links operate on raw_text (no zone exclusion) — fix F-LK1.
            raw_text = _collect_raw_text(node, predicate)

            # -- Generic timestamps (S09b-4) --------------------------------
            # Walk the item subtree node-by-node, extracting from heading
            # and filtered _body_lines.  Excludes planning, PROPERTIES,
            # CLOCK, and state-change lines.
            active_ts, inactive_ts, range_ts = _collect_timestamps(
                node, predicate
            )

            # -- Clock entries (S09c-1) ------------------------------------
            # Walk scaffolding to collect CLOCK entries from item scope.
            # Uses orgparse's structured node.clock API — no regex.
            clock = _collect_clock(node, predicate)

            # -- State changes (S09c-2) ------------------------------------
            # Extract from str(node) only — no walk scaffolding.
            # State changes are the history of this heading's keyword,
            # not of its children (unlike clock which aggregates time).
            state_changes = _extract_state_changes(str(node))

            # -- Body text (S09d) ------------------------------------------
            # Collect body from item scope (walk scaffolding).  Plain
            # format: link syntax resolved, other markup preserved.
            # Excluded: LOGBOOK (hardcoded), config drawers/blocks.
            body = _collect_body(
                node, predicate,
                config.exclude_drawers, config.exclude_blocks,
            )

            items.append(
                Item(
                    title=node.heading,
                    item_id=node.get_property("ID"),
                    level=node.level,
                    parent_item_id=_find_parent_id(node, predicate),
                    linenumber=node.linenumber,
                    file_path=path_str,
                    scheduled=scheduled,
                    deadline=deadline,
                    closed=closed,
                    created=created,
                    archived=archived,
                    active_ts=active_ts,
                    inactive_ts=inactive_ts,
                    range_ts=range_ts,
                    clock=clock,
                    state_changes=state_changes,
                    body=body,
                    raw_text=raw_text,
                    links=_extract_links(raw_text),
                    properties=props,
                    local_tags=raw_local,
                    inherited_tags=inherited,
                    todo=todo,
                    priority=priority,
                )
            )

    return ParseResult(items=tuple(items))
