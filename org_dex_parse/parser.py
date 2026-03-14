"""Tree walk, item discrimination, and field extraction.

Walks the orgparse tree, partitions headings into items and scaffolding
using the unified is_item check (:ID: invariant + configurable predicate),
and extracts structural, semantic, and property fields for each item.
"""
from __future__ import annotations

import datetime
import re
from typing import Any, Callable

import orgparse
import orgparse.node as _orgparse_node
from orgparse.node import OrgEnv

from orgparse.date import OrgDate

from .config import Config
from .types import Item, ParseResult, Timestamp

# Save the original tag regex at import time so we can restore it
# when extra_tag_chars is not needed.  Used by the HACK(S04) monkey-patch.
_ORIGINAL_RE_HEADING_TAGS = _orgparse_node.RE_HEADING_TAGS


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


def _extract_properties(
    node: Any, excluded: frozenset[str]
) -> tuple[tuple[str, str], ...]:
    """Extract properties from the heading's direct PROPERTIES drawer.

    Returns (key, value) pairs in drawer order, excluding properties in
    the excluded set.  Comparison is case-insensitive (key lowered against
    the already-lowercase excluded set).

    Values are preserved as-is via str() — no normalization (F-PR2).
    Only the direct drawer is read — orgparse node.properties does not
    walk the subtree, which fixes F-PR1 by design.
    """
    return tuple(
        (k, str(v))
        for k, v in node.properties.items()
        if k.lower() not in excluded
    )


def _extract_tags(
    node: Any, tags_exclude_from_inheritance: frozenset[str]
) -> tuple[frozenset[str], frozenset[str]]:
    """Classify tags into local and inherited sets.

    Empty strings are filtered before classification (F-TG1: malformed
    headings like "::" can produce empty tag strings in orgparse).

    Returns (local_tags, inherited_tags).
    """
    # Filter empty tags first — before any set operation.
    raw_local = frozenset(t for t in node.shallow_tags if t)
    raw_all = frozenset(t for t in node.tags if t)

    # Inherited = all tags minus local tags minus excluded-from-inheritance.
    inherited = raw_all - raw_local - tags_exclude_from_inheritance

    return raw_local, inherited


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


# Regex for ARCHIVE_TIME bare format: "2026-01-15 Thu 14:30"
# No delimiters (<> or []) — Emacs writes this format on archiving.
_RE_ARCHIVE_TIME = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})\s+\w+\s+(\d{2}):(\d{2})"
)


def _orgdate_to_timestamp(od: OrgDate) -> Timestamp:
    """Convert an orgparse OrgDate to a Timestamp.

    Preserves date vs datetime (AC7), active flag (AC8), and formats
    the repeater tuple as a string like "+1w" (AC9).
    """
    # Repeater: orgparse stores it as a private (prefix, num, unit) tuple.
    # We format it as a single string for simpler downstream use.
    repeater = None
    if od._repeater:
        prefix, num, unit = od._repeater
        repeater = f"{prefix}{num}{unit}"

    return Timestamp(date=od.start, active=od.is_active(), repeater=repeater)


def _parse_created(node: Any, created_property: str) -> Timestamp | None:
    """Extract the created timestamp from a configurable property.

    The property value is an org timestamp string (active or inactive).
    Returns None if the property is absent.
    """
    value = node.get_property(created_property)
    if value is None:
        return None

    dates = OrgDate.list_from_str(str(value))
    if not dates:
        return None

    return _orgdate_to_timestamp(dates[0])


def _parse_archive_time(node: Any) -> Timestamp | None:
    """Extract archived_on from the ARCHIVE_TIME property.

    ARCHIVE_TIME uses a bare format without org delimiters:
    "2026-01-15 Thu 14:30".  Always inactive (archiving is a past event),
    never has a repeater.  Returns None if the property is absent.
    """
    value = node.get_property("ARCHIVE_TIME")
    if value is None:
        return None

    match = _RE_ARCHIVE_TIME.search(str(value))
    if not match:
        return None

    year, month, day, hour, minute = (int(g) for g in match.groups())

    return Timestamp(
        date=datetime.datetime(year, month, day, hour, minute),
        active=False,
    )


def parse_file(path: str, config: Config) -> ParseResult:
    """Parse an org file into a ParseResult with Items.

    Loads the file via orgparse (passing todos/dones through OrgEnv for
    correct keyword recognition), walks all nodes in document order, and
    builds an Item for each heading that passes the is_item check.

    Each Item includes structural fields (S03), properties, tags, TODO
    keyword, and priority (S04), and dedicated timestamp fields —
    scheduled, deadline, closed, created, archived_on (S05a).  Fields
    for generic timestamps, clock, body, and links are left at defaults
    (S05b–S08).
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

    # Build the property exclusion set once — all lowercase for
    # case-insensitive comparison.  Always excluded: ID (in item_id),
    # ARCHIVE_TIME (will be in archived_on, S05), and created_property
    # (will be in created, S05).
    always_excluded = {"id", "archive_time", config.created_property.lower()}
    property_exclusions = always_excluded | config.exclude_properties

    items: list[Item] = []

    # root[1:] iterates ALL nodes in document order, skipping the
    # virtual root.  No recursion needed — orgparse provides a flat
    # iterator over the entire tree.
    for node in root[1:]:
        if is_item(node, predicate):
            # S04: extract properties, tags, todo, priority.
            properties = _extract_properties(node, property_exclusions)
            local_tags, inherited_tags = _extract_tags(
                node, config.tags_exclude_from_inheritance
            )

            # TODO keyword: orgparse returns "" when no keyword is set;
            # we normalize to None for consistency with Item.todo type.
            todo = node.todo if node.todo else None

            # S05a: dedicated timestamp fields.
            # Planning: orgparse returns falsy OrgDate subclasses when absent.
            scheduled = (
                _orgdate_to_timestamp(node.scheduled)
                if node.scheduled
                else None
            )
            deadline = (
                _orgdate_to_timestamp(node.deadline)
                if node.deadline
                else None
            )
            closed = (
                _orgdate_to_timestamp(node.closed)
                if node.closed
                else None
            )

            items.append(
                Item(
                    title=node.heading,
                    item_id=node.get_property("ID"),
                    level=node.level,
                    parent_item_id=_find_parent_id(node, predicate),
                    linenumber=node.linenumber,
                    file_path=path_str,
                    todo=todo,
                    priority=node.priority,
                    local_tags=local_tags,
                    inherited_tags=inherited_tags,
                    properties=properties,
                    scheduled=scheduled,
                    deadline=deadline,
                    closed=closed,
                    created=_parse_created(node, config.created_property),
                    archived_on=_parse_archive_time(node),
                )
            )

    return ParseResult(items=tuple(items))
