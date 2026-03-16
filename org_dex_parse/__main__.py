"""CLI for org-dex-parse: python -m org_dex_parse FILE [FILE ...]

Parses org files and prints each item with its populated fields.
Uses bare configuration by default (any heading with :ID: is an item).

Usage:
    python -m org_dex_parse file.org
    python -m org_dex_parse --json file.org
    python -m org_dex_parse --config myconfig.json file.org
    python -m org_dex_parse --predicate '["property", "Type"]' file.org
    python -m org_dex_parse --todos TODO,NEXT --dones DONE file.org
    python -m org_dex_parse --json -vv file.org   # full output with raw_text
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import sys
from pathlib import Path

from .config import Config
from .parser import parse_file


# -- Config construction -------------------------------------------------------
# Builds a Config from CLI flags and optional JSON config file.
# Precedence: CLI flags > config file > Config defaults.

# Valid keys in the JSON config file — must match Config fields.
# Used to reject typos early (AC11).
_VALID_CONFIG_KEYS = frozenset({
    "predicate", "todos", "dones", "tags_exclude_from_inheritance",
    "exclude_drawers", "exclude_blocks", "exclude_properties",
    "created_property", "extra_tag_chars",
})

# Expected JSON types for each config field.  Used to reject scalars
# where a list is expected (e.g. "todos": "LOGBOOK" instead of ["LOGBOOK"]).
_CONFIG_EXPECTED_TYPES: dict[str, type | tuple[type, ...]] = {
    "todos": list,
    "dones": list,
    "tags_exclude_from_inheritance": list,
    "exclude_drawers": list,
    "exclude_blocks": list,
    "exclude_properties": list,
    "predicate": (list, type(None)),
    "created_property": str,
    "extra_tag_chars": str,
}


def _load_config_file(path: str) -> dict:
    """Load and validate a JSON config file.

    Returns a dict with only known keys.  Raises SystemExit on
    unknown keys or missing file (with clear error messages).
    """
    try:
        text = Path(path).read_text()
    except FileNotFoundError:
        print(f"error: config file not found: {path}", file=sys.stderr)
        raise SystemExit(1)

    data = json.loads(text)
    if not isinstance(data, dict):
        print(f"error: config file must be a JSON object, got {type(data).__name__}",
              file=sys.stderr)
        raise SystemExit(1)

    unknown = set(data.keys()) - _VALID_CONFIG_KEYS
    if unknown:
        print(f"error: unknown fields in config file: {', '.join(sorted(unknown))}",
              file=sys.stderr)
        raise SystemExit(1)

    # Validate value types — reject scalars where lists are expected.
    for key, value in data.items():
        expected = _CONFIG_EXPECTED_TYPES.get(key)
        if expected is not None and not isinstance(value, expected):
            # Human-readable expected type name.
            if isinstance(expected, tuple):
                names = " or ".join(t.__name__ for t in expected)
            else:
                names = expected.__name__
            print(
                f"error: config field \"{key}\" must be {names}, "
                f"got {type(value).__name__}: {value!r}",
                file=sys.stderr,
            )
            raise SystemExit(1)

    return data


def _build_config(args: argparse.Namespace) -> Config:
    """Build a Config from CLI args, merging config file if present.

    Precedence: CLI flags > config file > Config defaults.
    A CLI flag is considered "set" when its value differs from None
    (argparse default for all our optional flags).
    """
    # Start with config file values (if any).
    file_cfg: dict = {}
    if args.config is not None:
        file_cfg = _load_config_file(args.config)

    # Map CLI flag names to config dict keys.
    # Each entry: (argparse dest, config key, transform).
    # transform converts the CLI string to the config value type.
    # Strip whitespace around each token and drop empty strings.
    # Without this, "--todos 'TODO, NEXT,'" would produce (" NEXT", "").
    _split = lambda s: tuple(
        t for t in (x.strip() for x in s.split(",")) if t
    ) if s else ()
    _split_frozen = lambda s: frozenset(
        t for t in (x.strip() for x in s.split(",")) if t
    ) if s else frozenset()

    cli_mappings = [
        ("predicate", "predicate", lambda s: json.loads(s)),
        ("todos", "todos", _split),
        ("dones", "dones", _split),
        ("tags_exclude", "tags_exclude_from_inheritance", _split_frozen),
        ("exclude_drawers", "exclude_drawers", _split_frozen),
        ("exclude_blocks", "exclude_blocks", _split_frozen),
        ("exclude_properties", "exclude_properties", _split_frozen),
        ("created_property", "created_property", lambda s: s),
        ("extra_tag_chars", "extra_tag_chars", lambda s: s),
    ]

    # Merge: CLI flags override config file.
    merged: dict = {}
    for arg_name, cfg_key, transform in cli_mappings:
        cli_val = getattr(args, arg_name, None)
        if cli_val is not None:
            # CLI flag was explicitly set — it wins.
            merged[cfg_key] = transform(cli_val)
        elif cfg_key in file_cfg:
            # Config file has this key — use it.
            merged[cfg_key] = file_cfg[cfg_key]
        # else: use Config default (don't set in merged).

    # Convert config file types to Config constructor types.
    # JSON arrays → tuples/frozensets as needed.
    if "todos" in merged and isinstance(merged["todos"], list):
        merged["todos"] = tuple(merged["todos"])
    if "dones" in merged and isinstance(merged["dones"], list):
        merged["dones"] = tuple(merged["dones"])
    for set_key in ("tags_exclude_from_inheritance", "exclude_drawers",
                     "exclude_blocks", "exclude_properties"):
        if set_key in merged and isinstance(merged[set_key], list):
            merged[set_key] = frozenset(merged[set_key])

    # predicate: list or None passed directly to Config (compiled in
    # __post_init__).  "null" on CLI becomes None via json.loads.
    if "predicate" in merged:
        merged["item_predicate"] = merged.pop("predicate")

    return Config(**merged)


# -- JSON serialization --------------------------------------------------------
# Custom encoder for Item dataclasses and org-dex-parse types.

class _ItemEncoder(json.JSONEncoder):
    """JSON encoder for Item and its nested types."""

    def default(self, obj):
        # date/datetime → ISO string.
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        # frozenset → sorted list.
        if isinstance(obj, frozenset):
            return sorted(obj)
        return super().default(obj)


def _item_to_dict(item, verbosity: int) -> dict:
    """Convert an Item to a JSON-friendly dict.

    Verbosity controls which fields are included:
    - 0 (default): all fields except body and raw_text
    - 1 (-v): adds body
    - 2 (-vv): adds body and raw_text

    Properties tuple-of-tuples is converted to a dict for readability.
    """
    d = dataclasses.asdict(item)

    # Properties: tuple-of-tuples → dict.
    d["properties"] = dict(d["properties"])

    # Verbosity filtering.
    if verbosity < 2:
        d.pop("raw_text", None)
    if verbosity < 1:
        d.pop("body", None)

    return d


# -- Text output ---------------------------------------------------------------

def _print_item(item, verbosity: int) -> None:
    """Print a single item in human-readable text format."""
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

    # -v: show body.
    if verbosity >= 1 and item.body:
        lines = item.body.split("\n")
        preview = lines[0][:80]
        if len(lines) > 1:
            preview += f"  ... ({len(lines)} lines)"
        print(f"    body: {preview}")

    # -vv: show raw_text.
    if verbosity >= 2 and item.raw_text:
        lines = item.raw_text.split("\n")
        preview = lines[0][:80]
        if len(lines) > 1:
            preview += f"  ... ({len(lines)} lines)"
        print(f"    raw_text: {preview}")


# -- Main ----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m org_dex_parse",
        description="Parse org files and show items (bare config by default).",
    )
    parser.add_argument("files", nargs="+", help="Org files to parse")

    # Configuration flags — all optional, override config file values.
    parser.add_argument(
        "--config", type=str, default=None, metavar="FILE",
        help="JSON config file (all fields optional)",
    )
    parser.add_argument(
        "--predicate", type=str, default=None,
        help='JSON s-expression predicate, e.g. \'["property", "Type"]\'',
    )
    parser.add_argument(
        "--todos", type=str, default=None,
        help="Comma-separated active TODO keywords",
    )
    parser.add_argument(
        "--dones", type=str, default=None,
        help="Comma-separated done TODO keywords",
    )
    parser.add_argument(
        "--tags-exclude", type=str, default=None, dest="tags_exclude",
        help="Comma-separated tags excluded from inheritance",
    )
    parser.add_argument(
        "--exclude-drawers", type=str, default=None, dest="exclude_drawers",
        help="Comma-separated drawer names to exclude from body",
    )
    parser.add_argument(
        "--exclude-blocks", type=str, default=None, dest="exclude_blocks",
        help="Comma-separated block names to exclude from body",
    )
    parser.add_argument(
        "--exclude-properties", type=str, default=None, dest="exclude_properties",
        help="Comma-separated property names to exclude",
    )
    parser.add_argument(
        "--created-property", type=str, default=None, dest="created_property",
        help="Property name for creation date (default: CREATED)",
    )
    parser.add_argument(
        "--extra-tag-chars", type=str, default=None, dest="extra_tag_chars",
        help="Additional characters allowed in tag names",
    )

    # Output flags.
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output items as JSON",
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="Increase verbosity: -v adds body, -vv adds raw_text",
    )

    args = parser.parse_args()
    config = _build_config(args)

    if args.json_output:
        # JSON mode: collect all items across files, output as one array.
        all_items = []
        for path in args.files:
            result = parse_file(path, config)
            all_items.extend(
                _item_to_dict(item, args.verbose) for item in result.items
            )
        print(json.dumps(all_items, cls=_ItemEncoder, indent=2,
                         ensure_ascii=False))
    else:
        # Text mode: print per-file summary.
        for path in args.files:
            result = parse_file(path, config)
            print(f"\n{path}: {len(result.items)} items")
            for item in result.items:
                _print_item(item, args.verbose)


if __name__ == "__main__":
    main()
