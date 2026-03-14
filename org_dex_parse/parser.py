"""Tree walk and item discrimination.

Walks the orgparse tree, partitions headings into items and scaffolding
using the unified is_item check (:ID: invariant + configurable predicate),
and builds skeleton Items with structural fields only.
"""
from __future__ import annotations

from typing import Any, Callable

import orgparse
from orgparse.node import OrgEnv

from .config import Config
from .types import Item, ParseResult


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


def parse_file(path: str, config: Config) -> ParseResult:
    """Parse an org file into a ParseResult with skeleton Items.

    Loads the file via orgparse (passing todos/dones through OrgEnv for
    correct keyword recognition), walks all nodes in document order, and
    builds an Item for each heading that passes the is_item check.

    Items contain only structural fields (title, item_id, level,
    parent_item_id, linenumber, file_path).  All other fields are left
    at their defaults — they will be populated by subsequent stories
    (S04–S08).
    """
    # Normalize path to string for consistent file_path values.
    path_str = str(path)

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
    items: list[Item] = []

    # root[1:] iterates ALL nodes in document order, skipping the
    # virtual root.  No recursion needed — orgparse provides a flat
    # iterator over the entire tree.
    for node in root[1:]:
        if is_item(node, predicate):
            items.append(
                Item(
                    title=node.heading,
                    item_id=node.get_property("ID"),
                    level=node.level,
                    parent_item_id=_find_parent_id(node, predicate),
                    linenumber=node.linenumber,
                    file_path=path_str,
                )
            )

    return ParseResult(items=tuple(items))
