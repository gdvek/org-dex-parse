"""S03 verification script — run from org-dex-parse root:

    .venv/bin/python verify_s03.py
"""
from org_dex_parse import parse_file, Config

FIXTURE = "tests/fixtures/tree_basic.org"
FIXTURE_NO_ID = "tests/fixtures/tree_parent_no_id.org"

REMI_PREDICATE = lambda h: h.get_property("Type") is not None


def show(label, result):
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    if not result.items:
        print("  (nessun item)")
    for item in result.items:
        indent = "  " * item.level
        parent = item.parent_item_id or "None"
        print(f"  {indent}{item.item_id}  parent={parent}  title={item.title!r}")


# 1. Default predicate: qualsiasi heading con :ID: → 6 item
show(
    "Default predicate (tutti gli :ID:) — attesi 6 item",
    parse_file(FIXTURE, Config()),
)

# 2. Remi predicate: solo :ID: + :Type: → 5 item (item-004 escluso)
show(
    "Remi predicate (:ID: + :Type:) — attesi 5 item (item-004 escluso)",
    parse_file(FIXTURE, Config(item_predicate=REMI_PREDICATE)),
)

# 3. Con todos/dones: i title non contengono keyword
show(
    "Con todos/dones — i title sono puliti",
    parse_file(
        FIXTURE,
        Config(todos=("TODO", "NEXT", "DOING"), dones=("DONE", "CANCELED")),
    ),
)

# 4. Parent senza :ID: → child parent_item_id = None
show(
    "Parent senza :ID: — child parent = None",
    parse_file(FIXTURE_NO_ID, Config()),
)

print()
