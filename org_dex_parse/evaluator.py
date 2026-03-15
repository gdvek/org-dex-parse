"""S-expression predicate compiler for item predicates.

Compiles a JSON-like s-expression (Python list) into a callable predicate
``(node) -> bool``.  The expression format mirrors org-ql, serialized as
JSON arrays for cross-process transport (Elisp -> JSON-RPC -> Python).

Example::

    >>> pred = compile_predicate(["and", ["property", "Type"],
    ...                                  ["not", ["property", "ARCHIVE_TIME"]]])
    >>> pred(some_orgparse_node)
    True

Supported operators (extensible via ``_OPERATORS`` dispatch table):

- ``["property", "Name"]`` — ``node.get_property("Name") is not None``
- ``["not", expr]``        — negation
- ``["and", expr, ...]``   — conjunction (n-ary, short-circuits)
- ``["or", expr, ...]``    — disjunction (n-ary, short-circuits)
- ``None``                 — default predicate (always True)
"""
from __future__ import annotations

from typing import Any, Callable


def compile_predicate(
    expr: list | None,
) -> Callable[[Any], bool]:
    """Compile a JSON-like s-expression into a predicate callable.

    :arg expr: A list (s-expression) or None.  None returns the default
        predicate (always True).
    :returns: A callable ``(node) -> bool``.
    :raises ValueError: On unknown operators, wrong arity, or invalid types.
    """
    if expr is None:
        return _DEFAULT_PREDICATE

    if not isinstance(expr, list):
        raise ValueError(
            f"expected list or None, got {type(expr).__name__}: {expr!r}"
        )

    if len(expr) == 0:
        raise ValueError("empty expression — expected [operator, ...args]")

    operator = expr[0]
    args = expr[1:]

    if operator not in _OPERATORS:
        raise ValueError(
            f"unknown operator {operator!r}"
            f" — supported: {', '.join(sorted(_OPERATORS))}"
        )

    return _OPERATORS[operator](operator, args)


# -- Default predicate -------------------------------------------------------

_DEFAULT_PREDICATE: Callable[[Any], bool] = lambda _node: True


# -- Operator handlers -------------------------------------------------------
# Each handler takes (operator_name, args) and returns a callable.
# operator_name is passed for error messages.


def _compile_property(op: str, args: list) -> Callable[[Any], bool]:
    """["property", "Name"] → node.get_property("Name") is not None."""
    if len(args) != 1:
        raise ValueError(
            f"{op!r} expects exactly 1 argument (property name),"
            f" got {len(args)}: {args!r}"
        )
    prop_name = args[0]
    return lambda node: node.get_property(prop_name) is not None


def _compile_not(op: str, args: list) -> Callable[[Any], bool]:
    """["not", expr] → negation of sub-expression."""
    if len(args) != 1:
        raise ValueError(
            f"{op!r} expects exactly 1 argument (sub-expression),"
            f" got {len(args)}: {args!r}"
        )
    inner = compile_predicate(args[0])
    return lambda node: not inner(node)


def _compile_and(op: str, args: list) -> Callable[[Any], bool]:
    """["and", expr, ...] → conjunction with short-circuit."""
    if len(args) == 0:
        raise ValueError(f"{op!r} expects at least 1 operand, got 0")
    compiled = [compile_predicate(a) for a in args]
    return lambda node: all(p(node) for p in compiled)


def _compile_or(op: str, args: list) -> Callable[[Any], bool]:
    """["or", expr, ...] → disjunction with short-circuit."""
    if len(args) == 0:
        raise ValueError(f"{op!r} expects at least 1 operand, got 0")
    compiled = [compile_predicate(a) for a in args]
    return lambda node: any(p(node) for p in compiled)


# -- Dispatch table -----------------------------------------------------------
# Adding a new operator: one entry here + one handler above.

_OPERATORS: dict[str, Callable[[str, list], Callable[[Any], bool]]] = {
    "property": _compile_property,
    "not": _compile_not,
    "and": _compile_and,
    "or": _compile_or,
}
