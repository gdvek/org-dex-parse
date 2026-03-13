"""Parser configuration — predicate, keywords, exclusion lists."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any


# Default predicate: any heading with :ID: is an item.
# The :ID: check is a structural invariant applied before the predicate,
# so the default predicate just returns True unconditionally.
_DEFAULT_PREDICATE: Callable[[Any], bool] = lambda h: True


@dataclass(frozen=True)
class Config:
    """Configuration for org-dex-parse.

    The caller constructs this with TODO keywords, tag rules, and
    exclusion lists matching their org-mode environment.

    :arg item_predicate: Function ``(headline) -> bool`` that determines
        which headings (that already have ``:ID:``) are items.
        Default: ``lambda h: True`` (any heading with ``:ID:``).
    :arg todos: Active (unfinished) TODO keywords.
    :arg dones: Terminal (finished) TODO keywords.
    :arg tags_exclude_from_inheritance: Tags that don't propagate to
        children (corresponds to ``org-tags-exclude-from-inheritance``).
    :arg exclude_drawers: Drawer names to exclude from body text.
        Case-insensitive — normalized to lowercase in ``__post_init__``.
    :arg exclude_blocks: Block names to exclude from body text.
        Case-insensitive — normalized to lowercase in ``__post_init__``.
    :arg exclude_properties: Property names to omit from the properties
        tuple.  Case-insensitive — normalized to lowercase in
        ``__post_init__``.
    """

    item_predicate: Callable[[Any], bool] = field(
        default=_DEFAULT_PREDICATE
    )
    todos: tuple[str, ...] = ()
    dones: tuple[str, ...] = ()
    tags_exclude_from_inheritance: frozenset[str] = frozenset()
    exclude_drawers: frozenset[str] = frozenset()
    exclude_blocks: frozenset[str] = frozenset()
    exclude_properties: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        """Normalize exclusion sets to lowercase for case-insensitive matching.

        Uses object.__setattr__ because the dataclass is frozen — the
        standard Python pattern for post-init normalization on frozen
        dataclasses.
        """
        object.__setattr__(
            self,
            "exclude_drawers",
            frozenset(d.lower() for d in self.exclude_drawers),
        )
        object.__setattr__(
            self,
            "exclude_blocks",
            frozenset(b.lower() for b in self.exclude_blocks),
        )
        object.__setattr__(
            self,
            "exclude_properties",
            frozenset(p.lower() for p in self.exclude_properties),
        )
