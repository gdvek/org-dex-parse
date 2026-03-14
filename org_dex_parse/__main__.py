"""CLI for quick exploration: python -m org_dex_parse FILE [FILE ...]

Parses org files and prints each item with its populated fields.
Uses the Remi workflow configuration by default.

Usage:
    python -m org_dex_parse ~/Remi/REMI/remi.org
    python -m org_dex_parse -v ~/Remi/ROAM/*.org
    python -m org_dex_parse --bare ~/org/plain.org   # no Remi config
"""
from __future__ import annotations

import argparse

from .config import Config
from .parser import parse_file


# -- Remi workflow configuration ----------------------------------------------
# Hardcoded from remi-init.org / org-init.org.  Matches the remi-org-db
# pipeline so the CLI output is identical to what the real system sees.

_REMI_TODOS = (
    "PLANNING", "TODO", "NEXT", "DOING", "TESTING",
    "PAUSED", "WAITING", "HOLD", "IDLE", "RESTART",
    "PERIPHERY", "FOREGROUND", "TIMELESS",
    "TODISCOVER", "BLOCKED", "TOANALYZE", "TOSYNTHESIZE",
    "DISCOVERING", "ANALYZING", "SYNTHESIZING",
    "MTODO", "MNEXT", "MASTERING", "HIBERNATED",
    "MPAUSED", "MHOLD", "MRESTART",
    "FAILED", "SUCCESS",
    "REPEAT", "SYNC", "MISSED", "STANDBY",
    "EASY", "MEDIUM", "HARD", "IMPOSSIBLE",
    "NEW",
    "DRAFT", "REFINING", "FINAL", "VALIDATED",
    "TOUPDATE", "UPDATING",
    "TOREVIEW", "REVIEWING", "OUTDATED", "EXCLUDED",
    "SKIPPED",
    "ARCHIVED",
)

_REMI_DONES = (
    "DONE", "CANCELED",
    "CONSUMED",
    "DISCOVERED", "ANALYZED", "SYNTHESIZED",
    "MASTERED",
    "CHECKED",
    "COMPLETED",
    "JUNK",
)

_REMI_TAGS_EXCLUDE = frozenset({
    "today", "week", "sprint", "side", "quarter", "someday", "next",
    "roam", "focus", "pin", "star", "fav", "_sf", "_era", "exercise",
    "kata", "sub", "principle", "pattern", "abc", "regression", "fault",
    "habit", "suspended", "_ext", "_bur", "fcreset", "fcnow", "new",
    "fczoom", "fcedit", "fcpractice", "failed", "edited", "_iw", "_ir",
    "_iwatch", "_feynman", "_bg", "_shadowing", "fc_r", "now", "main",
    "mit", "idle", "exempt", "expired", "sync", "core", "slack", "drill",
    "work", "mvmnt", "pause", "other", "_exp", "_feed", "_mntrng",
    "_low", "_medium", "_high", "_peak", "_plan", "_execute", "_review",
    "_research", "_shallow", "_deep", "_immerse", "_distill", "_embody",
    "_integrate", "_maintain", "_reg", "_acc", "_trk", "_bra", "_lf",
    "_grf", "_schema", "_unapproved", "_new", "_valid", "_doubt",
    "_untrusted", "_excluded", "staged",
})

_REMI_EXCLUDE_DRAWERS = frozenset({
    "logbook", "see_also", "unapproved", "help", "image",
    "___links_to___", "___linked_by___", "___parents___", "___children___",
})

_REMI_EXCLUDE_PROPERTIES = frozenset({
    "archive_file", "archive_category", "archive_todo", "archive_itags",
    "archive_olpath", "archive_ltags", "last_interaction", "remiauto_tags",
})

_REMI_EXTRA_TAG_CHARS = "%#"

# Remi predicate: a heading is an item only if it has a :Type: property.
# The :ID: check is the structural invariant applied before the predicate.
_REMI_PREDICATE = lambda h: h.get_property("Type") is not None

REMI_CONFIG = Config(
    item_predicate=_REMI_PREDICATE,
    todos=_REMI_TODOS,
    dones=_REMI_DONES,
    tags_exclude_from_inheritance=_REMI_TAGS_EXCLUDE,
    exclude_drawers=_REMI_EXCLUDE_DRAWERS,
    exclude_properties=_REMI_EXCLUDE_PROPERTIES,
    extra_tag_chars=_REMI_EXTRA_TAG_CHARS,
)


# -- Output -------------------------------------------------------------------

def _print_item(item, verbose: bool) -> None:
    """Print a single item."""
    print(f"  {item.title}")
    print(f"    id={item.item_id}  level={item.level}  line={item.linenumber}")

    if item.parent_item_id:
        print(f"    parent={item.parent_item_id}")
    if item.todo:
        print(f"    todo={item.todo}", end="")
        if item.priority:
            print(f"  priority={item.priority}", end="")
        print()
    elif item.priority:
        print(f"    priority={item.priority}")
    if item.local_tags:
        print(f"    local_tags={sorted(item.local_tags)}")
    if item.inherited_tags:
        print(f"    inherited_tags={sorted(item.inherited_tags)}")
    if item.properties:
        print(f"    properties={dict(item.properties)}")

    if verbose and item.raw_text:
        lines = item.raw_text.split("\n")
        preview = lines[0][:80]
        if len(lines) > 1:
            preview += f"  ... ({len(lines)} lines)"
        print(f"    raw_text: {preview}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m org_dex_parse",
        description="Parse org files and show items (Remi config by default).",
    )
    parser.add_argument("files", nargs="+", help="Org files to parse")
    parser.add_argument(
        "--bare", action="store_true",
        help="Use bare config (no keywords, no exclusions)",
    )
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show raw_text preview")

    args = parser.parse_args()
    config = Config() if args.bare else REMI_CONFIG

    for path in args.files:
        result = parse_file(path, config)
        print(f"\n{path}: {len(result.items)} items")
        for item in result.items:
            _print_item(item, args.verbose)


if __name__ == "__main__":
    main()
