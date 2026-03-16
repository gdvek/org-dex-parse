"""Playground script to verify README examples against actual parser output.

Run from the org-dex-parse directory:
    .venv/bin/python tests/readme_playground.py
"""
from __future__ import annotations

import datetime
from pathlib import Path

from org_dex_parse import Config, parse_file

FIXTURES = Path(__file__).parent / "fixtures" / "readme"

# Track pass/fail
_results: list[tuple[str, bool, str]] = []


def check(label: str, actual, expected):
    ok = actual == expected
    _results.append((label, ok, "" if ok else f"\n  expected: {expected!r}\n  actual:   {actual!r}"))
    mark = "✓" if ok else "✗"
    print(f"  {mark} {label}")
    if not ok:
        print(f"    expected: {expected!r}")
        print(f"    actual:   {actual!r}")


# =============================================================================
# Example 1: default predicate — items and scaffolding
# =============================================================================
def example_1():
    print("\n== Example 1: default predicate ==")
    config = Config(todos=("TODO",), dones=("DONE",))
    result = parse_file(str(FIXTURES / "ex1_project.org"), config)

    check("item count", len(result.items), 2)

    item = result.items[0]  # Write report
    check("item[0].title", item.title, "Write report")
    check("item[0].todo", item.todo, "TODO")
    check("item[0].local_tags", item.local_tags, frozenset({"work"}))
    check("item[0].deadline.date", item.deadline.date, datetime.date(2026, 4, 1))
    check("item[0].active_ts[0].date", item.active_ts[0].date, datetime.date(2026, 3, 20))
    check("item[0].links[0].target", item.links[0].target, "id:ref")
    check("'Notes' in body", "Notes" in item.body, True)
    check("'Some text with a link' in body", "Some text with a link" in item.body, True)

    item1 = result.items[1]  # Review draft
    check("item[1].title", item1.title, "Review draft")
    check("item[1].closed.date", item1.closed.date,
          datetime.datetime(2026, 3, 15, 10, 0))


# =============================================================================
# Example 2: :Type: predicate — narrower item definition
# =============================================================================
def example_2():
    print("\n== Example 2: :Type: predicate ==")
    config = Config(
        item_predicate=["property", "Type"],
        todos=("TODO",),
        dones=("DONE",),
    )
    result = parse_file(str(FIXTURES / "ex2_inbox.org"), config)

    check("item count", len(result.items), 2)

    item = result.items[1]  # Buy groceries
    check("item[1].title", item.title, "Buy groceries")
    check("item[1].scheduled.date", item.scheduled.date, datetime.date(2026, 3, 17))
    check("item[1].properties", item.properties, (("Type", "task"),))
    check("item[1].parent_item_id", item.parent_item_id, "aaa-111")

    # "Grocery list" is scaffolding at level 2, sibling of "Buy groceries",
    # child of "Inbox" → its content goes to Inbox, not Buy groceries.
    inbox = result.items[0]  # Inbox
    check("'Grocery list' in Inbox body", "Grocery list" in inbox.body, True)
    check("'Milk' in Inbox body", "Milk" in inbox.body, True)
    check("'Bread' in Inbox body", "Bread" in inbox.body, True)
    check("Buy groceries body is None", item.body, None)


# =============================================================================
# Example 3: org-roam style — exclude ROAM_EXCLUDE
# =============================================================================
def example_3():
    print("\n== Example 3: org-roam style ==")
    config = Config(
        item_predicate=["not", ["property", "ROAM_EXCLUDE"]],
    )
    result = parse_file(str(FIXTURES / "ex3_roam.org"), config)

    check("item count", len(result.items), 2)
    check("item[0].title", result.items[0].title, "Main topic")
    check("item[1].title", result.items[1].title, "Supporting argument")

    item = result.items[0]  # Main topic
    check("item[0].links[0].target", item.links[0].target,
          "https://example.com/reference")
    check("item[0].links[0].description", item.links[0].description,
          "Reference paper")
    # Draft section is scaffolding → its content rolls into Main topic
    check("'COMMENT Draft section' in body",
          "COMMENT Draft section" in item.body, True)
    check("'Work in progress' in body",
          "Work in progress" in item.body, True)


# =============================================================================
# Example 4: LOGBOOK data — clock entries and state changes
# =============================================================================
def example_4():
    print("\n== Example 4: LOGBOOK data ==")
    config = Config(
        todos=("PLANNING", "TODO"),
        dones=("DONE",),
    )
    result = parse_file(str(FIXTURES / "ex4_clock.org"), config)
    item = result.items[0]

    # Clock entries
    check("len(clock)", len(item.clock), 2)
    check("clock[0].start", item.clock[0].start,
          datetime.datetime(2026, 3, 16, 10, 0))
    check("clock[0].end", item.clock[0].end,
          datetime.datetime(2026, 3, 16, 11, 45))
    check("clock[0].duration_minutes", item.clock[0].duration_minutes, 105)
    check("clock[1].start", item.clock[1].start,
          datetime.datetime(2026, 3, 16, 14, 0))
    check("clock[1].duration_minutes", item.clock[1].duration_minutes, 90)

    # State changes
    check("len(state_changes)", len(item.state_changes), 2)
    check("sc[0].to_state", item.state_changes[0].to_state, "PLANNING")
    check("sc[0].from_state", item.state_changes[0].from_state, None)
    check("sc[1].to_state", item.state_changes[1].to_state, "TODO")
    check("sc[1].from_state", item.state_changes[1].from_state, "PLANNING")

    # Body excludes LOGBOOK
    check("body", item.body, "Focus on the analysis section.")


# =============================================================================
# Example 5: timestamps — dedicated vs generic
# =============================================================================
def example_5():
    print("\n== Example 5: timestamps ==")
    config = Config(dones=("DONE",))
    result = parse_file(str(FIXTURES / "ex5_timestamps.org"), config)
    item = result.items[0]

    # Dedicated
    check("scheduled.date", item.scheduled.date, datetime.date(2026, 3, 1))
    check("scheduled.active", item.scheduled.active, True)
    check("deadline.date", item.deadline.date, datetime.date(2026, 3, 10))
    check("closed.date", item.closed.date,
          datetime.datetime(2026, 3, 9, 23, 55))
    check("closed.active", item.closed.active, False)
    check("created.date", item.created.date, datetime.date(2026, 1, 10))
    check("archived.date", item.archived.date,
          datetime.datetime(2026, 3, 15, 12, 0))

    # Generic
    check("len(active_ts)", len(item.active_ts), 0)
    check("len(inactive_ts)", len(item.inactive_ts), 1)
    check("len(range_ts)", len(item.range_ts), 1)
    check("range_ts[0].start.date", item.range_ts[0].start.date,
          datetime.date(2026, 6, 15))
    check("range_ts[0].end.date", item.range_ts[0].end.date,
          datetime.date(2026, 6, 18))
    check("range_ts[0].active", item.range_ts[0].active, True)


# =============================================================================
# Example 5b: scaffolding planning → generic timestamps
# =============================================================================
def example_5b():
    print("\n== Example 5b: scaffolding planning ==")
    config = Config(todos=("TODO",), dones=("DONE",))
    result = parse_file(str(FIXTURES / "ex5b_scaffold_planning.org"), config)
    item = result.items[0]

    # Item's own planning → dedicated
    check("deadline.date", item.deadline.date, datetime.date(2026, 4, 1))

    # Scaffolding planning → promoted to active_ts
    check("len(active_ts)", len(item.active_ts), 2)
    check("active_ts[0].date (Phase 1 SCHEDULED)",
          item.active_ts[0].date, datetime.date(2026, 3, 15))
    check("active_ts[1].date (Phase 2 DEADLINE)",
          item.active_ts[1].date, datetime.date(2026, 3, 25))


# =============================================================================
# Example 6: tags, properties, and inheritance
# =============================================================================
def example_6():
    print("\n== Example 6: tags and properties ==")
    config = Config(
        item_predicate=["property", "Type"],
        tags_exclude_from_inheritance=frozenset({"noexport"}),
    )
    result = parse_file(str(FIXTURES / "ex6_tags.org"), config)

    parent = result.items[0]  # Research
    check("parent.local_tags", parent.local_tags, frozenset({"science"}))
    check("parent.inherited_tags", parent.inherited_tags, frozenset({"project"}))
    check("parent.properties", parent.properties,
          (("Type", "area"), ("Effort", "180")))

    child = result.items[1]  # Literature review
    check("child.local_tags", child.local_tags, frozenset({"reading"}))
    check("child.inherited_tags", child.inherited_tags,
          frozenset({"project", "science"}))
    check("child.parent_item_id", child.parent_item_id, "tag-001")
    check("child.properties", child.properties, (("Type", "task"),))


# =============================================================================
# Example 7: links — org-mode and bare URLs
# =============================================================================
def example_7():
    print("\n== Example 7: links ==")
    config = Config(
        exclude_drawers=frozenset({"see_also"}),
    )
    result = parse_file(str(FIXTURES / "ex7_links.org"), config)
    item = result.items[0]

    check("len(links)", len(item.links), 4)

    check("links[0].target", item.links[0].target,
          "https://arxiv.org/abs/2301.00001")
    check("links[0].description", item.links[0].description,
          "Attention is all you need")

    check("links[1].target", item.links[1].target, "id:abc-123")
    check("links[1].description", item.links[1].description,
          "Transformer architecture")

    check("links[2].target", item.links[2].target,
          "https://example.com/transformers")
    check("links[2].description", item.links[2].description, None)

    check("links[3].target", item.links[3].target, "id:def-456")
    check("links[3].description", item.links[3].description,
          "History of neural networks")

    # Body excludes :SEE_ALSO:
    check("'Key paper' in body", "Key paper" in item.body, True)
    check("'History of neural' not in body",
          "History of neural" not in item.body, True)


# =============================================================================
# Example 8: body and raw_text
# =============================================================================
def example_8():
    print("\n== Example 8: body and raw_text ==")
    config = Config(
        item_predicate=["property", "Type"],
        todos=("PLANNING", "TODO"),
        dones=("DONE",),
    )
    result = parse_file(str(FIXTURES / "ex8_body.org"), config)
    item = result.items[0]

    # body: filtered
    check("'First draft' in body", "First draft" in item.body, True)
    check("'design document' in body", "design document" in item.body, True)
    check("'Outline' in body", "Outline" in item.body, True)
    check("'Introduction (5 min)' in body",
          "Introduction (5 min)" in item.body, True)
    # LOGBOOK excluded from body
    check("'LOGBOOK' not in body", "LOGBOOK" not in item.body, True)

    # raw_text: unfiltered
    check("'LOGBOOK' in raw_text", "LOGBOOK" in item.raw_text, True)
    check("':ID:' in raw_text", ":ID:" in item.raw_text, True)
    check("'[[id:ref-001]' in raw_text",
          "[[id:ref-001]" in item.raw_text, True)


# =============================================================================
# Run all
# =============================================================================
if __name__ == "__main__":
    example_1()
    example_2()
    example_3()
    example_4()
    example_5()
    example_5b()
    example_6()
    example_7()
    example_8()

    # Summary
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print(f"\n{'='*60}")
    print(f"  {passed} passed, {failed} failed, {len(_results)} total")
    if failed:
        print(f"\n  FAILURES:")
        for label, ok, msg in _results:
            if not ok:
                print(f"    {label}{msg}")
    print()
