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

    :arg item_predicate: Determines which headings (that already have
        ``:ID:``) are items.  Accepts three forms:
        - ``Callable[[Any], bool]`` — a Python function (backward compat)
        - ``list`` — a JSON-like s-expression compiled via the evaluator
          (e.g. ``["property", "Type"]``)
        - ``None`` — default predicate (any heading with ``:ID:``).
        After ``__post_init__``, always stored as a callable.
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
    :arg created_property: Name of the org property that holds the
        creation date (e.g. ``"CREATED"``).  The parser looks for this
        property on each item and uses its value for the ``Item.created``
        field.  Case-insensitive — normalized to uppercase in
        ``__post_init__`` (org-mode convention for property names).
        Default: ``"CREATED"``.  This property is automatically excluded
        from ``Item.properties`` (like ``ID`` and ``ARCHIVE_TIME``).
    :arg extra_tag_chars: Additional characters to allow in org-mode tag
        names beyond the default ``[a-zA-Z0-9_@#%]``.  The parser uses
        this to build a monkey-patch regex for orgparse (applied in S04).
        Default: ``""`` (no extra characters).
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
    created_property: str = "CREATED"
    extra_tag_chars: str = ""

    # S19g: True when item_predicate was None (default — any heading with
    # :ID:).  Set in __post_init__ before compilation erases the distinction.
    # parse_file checks this to skip L12 when no explicit predicate is
    # configured (flagging every heading without :ID: would be pure noise).
    predicate_is_default: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        """Normalize fields on frozen dataclass.

        - item_predicate: list/None compiled to callable via evaluator,
          callable passed through, anything else raises ValueError.
        - Exclusion sets lowercased for case-insensitive matching.

        Uses object.__setattr__ because the dataclass is frozen — the
        standard Python pattern for post-init normalization on frozen
        dataclasses.
        """
        # -- Predicate normalization (S08) -----------------------------------
        pred = self.item_predicate
        # S19g: record whether predicate is the default before compilation.
        # Two paths to default: Config() uses _DEFAULT_PREDICATE sentinel,
        # Config(item_predicate=None) passes None.  Both mean "no explicit
        # predicate" — L12 should not fire.
        object.__setattr__(
            self, "predicate_is_default",
            pred is None or pred is _DEFAULT_PREDICATE,
        )
        if isinstance(pred, list) or pred is None:
            from .evaluator import compile_predicate
            object.__setattr__(
                self, "item_predicate", compile_predicate(pred)
            )
        elif not callable(pred):
            raise ValueError(
                f"item_predicate must be callable, list, or None,"
                f" got {type(pred).__name__}: {pred!r}"
            )

        # -- Exclusion normalization -----------------------------------------
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
        object.__setattr__(
            self,
            "created_property",
            self.created_property.upper(),
        )
