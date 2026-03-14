#!/usr/bin/env python3
"""S06 verification: compare raw_text between org-dex-parse and remi-org-parse.

Parses the same real fixture with both parsers and compares raw_text for
each item.  Uses remi-complex.org which has scaffolding, sub-items,
drawers, LOGBOOK, planning lines, and interleaved structure.

Usage:
    .venv/bin/python3 verify_s06.py
"""
import sys
from pathlib import Path

# --- remi-org-parse ---
REMI_PARSE_ROOT = Path(__file__).resolve().parent.parent / "remi-org-parse"
sys.path.insert(0, str(REMI_PARSE_ROOT))

from remi_org_parse.config import RemiConfig
from remi_org_parse.parser import parse_file as remi_parse_file

# --- org-dex-parse ---
sys.path.insert(0, str(Path(__file__).resolve().parent))

from org_dex_parse import Config, parse_file

# --- fixture ---
FIXTURE = str(
    REMI_PARSE_ROOT / "tests" / "fixtures" / "remi-complex.org"
)

# remi-org-parse config: requires :Type: (hardcoded) + :ID:
remi_config = RemiConfig(
    todos=("TODO", "NEXT", "DOING", "PLANNING", "FOREGROUND", "PERIPHERY"),
    dones=("DONE", "SYNTHESIZED", "CANCELED"),
    tags_exclude_from_inheritance=frozenset(),
    exclude_drawers=frozenset(),
    exclude_blocks=frozenset(),
    exclude_properties=frozenset(),
)

# org-dex-parse config: :ID: (structural) + predicate on :Type:
dex_config = Config(
    item_predicate=lambda h: h.get_property("Type") is not None,
    todos=("TODO", "NEXT", "DOING", "PLANNING", "FOREGROUND", "PERIPHERY"),
    dones=("DONE", "SYNTHESIZED", "CANCELED"),
)

# --- parse ---
remi_result = remi_parse_file(FIXTURE, remi_config)
dex_result = parse_file(FIXTURE, dex_config)

# --- compare ---
remi_by_id = {item.item_id: item for item in remi_result.items}
dex_by_id = {item.item_id: item for item in dex_result.items}

print(f"Fixture: {FIXTURE}")
print(f"remi-org-parse: {len(remi_result.items)} items")
print(f"org-dex-parse:  {len(dex_result.items)} items")
print()

# Check same item sets
remi_ids = set(remi_by_id.keys())
dex_ids = set(dex_by_id.keys())

if remi_ids != dex_ids:
    print("MISMATCH: different item sets!")
    print(f"  Only in remi: {remi_ids - dex_ids}")
    print(f"  Only in dex:  {dex_ids - remi_ids}")
    sys.exit(1)

# Compare raw_text for each item
all_match = True
for item_id in sorted(remi_ids):
    remi_raw = remi_by_id[item_id].raw_text
    dex_raw = dex_by_id[item_id].raw_text

    if remi_raw == dex_raw:
        status = "OK"
    else:
        status = "DIFF"
        all_match = False

    remi_lines = remi_raw.count("\n") + 1
    dex_lines = dex_raw.count("\n") + 1
    print(f"[{status}] {item_id:<30} remi={remi_lines} lines, dex={dex_lines} lines")

    if status == "DIFF":
        print(f"  --- remi raw_text ---")
        print(f"  {remi_raw[:200]!r}")
        print(f"  --- dex raw_text ---")
        print(f"  {dex_raw[:200]!r}")
        print()

print()
if all_match:
    print("All items match. raw_text is identical between the two parsers.")
else:
    print("Some items differ. See DIFF entries above.")
