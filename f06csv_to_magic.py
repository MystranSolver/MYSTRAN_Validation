# Made by Claude

"""Convert f06csv filter arguments to an f06magic TOML extraction block.

f06csv flags handled:
  -b / --blocks   CsvBlockId values  -> block / blocks
  -g / --gids     grid point IDs     -> node / nodes
  -e / --eids     element IDs        -> element / elements
  -t / --etypes   element types      -> element_type / element_types
  -s / --subcases subcase IDs        -> subcase / subcases
  -c / --cols     column indices     -> column / columns

Flags that are purely CSV formatting (-o, -H, -d, --tab, --crlf, -v, --align,
etc.) have no equivalent in an f06magic extraction and are silently ignored.
"""

from __future__ import annotations

import re
import shlex
from typing import Any


# ---------------------------------------------------------------------------
# Block ID -> canonical name mapping
# Derived from CsvBlockId in nas_csv/src/layout.rs.
# Keys are every accepted alias (including the numeric shorthand string).
# ---------------------------------------------------------------------------

_BLOCK_NAME: dict[str, str] = {}

_BLOCK_ALIASES: list[tuple[str, list[str]]] = [
    ("metadata",              ["0", "sol", "sol_info", "info"]),
    ("displacements",         ["1", "disp", "displs", "displacements"]),
    ("stresses",              ["2", "stresses"]),
    ("strains",               ["3", "strains"]),
    ("eng_forces",            ["4", "engforces", "eng_forces"]),
    ("grid_point_forces",     ["5", "gpfb", "gpfor", "gpforces",
                               "grid_point_forces", "grid_point_force_balance"]),
    ("applied",               ["6", "applied"]),
    ("spcforces",             ["7", "spcf", "spcforces"]),
    ("eigenvectors",          ["8", "eigenvectors"]),
    ("eigenvalues",           ["9", "eigenvalues"]),
]

for _canonical, _aliases in _BLOCK_ALIASES:
    for _alias in _aliases:
        _BLOCK_NAME[_alias.lower()] = _canonical


def _resolve_block(raw: str) -> str:
    """Return the canonical block name for a raw f06csv block token.

    Accepts numeric IDs (``"1"``), short aliases (``"disp"``), and full
    names (``"displacements"``). Unknown values are returned unchanged.
    """
    return _BLOCK_NAME.get(raw.lower(), raw)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _toml_value(values: list[Any]) -> str:
    """Render a list of values as a compact TOML value.

    * Empty list  -> should not be called (caller skips the key).
    * Single item -> bare scalar  (e.g.  "displacements"  or  1)
    * Many items  -> inline array (e.g.  [1, 3, 7])
    """
    def _fmt(v: Any) -> str:
        if isinstance(v, str):
            return f'"{v}"'
        return str(v)

    if len(values) == 1:
        return _fmt(values[0])
    return "[" + ", ".join(_fmt(v) for v in values) + "]"


def _split_csv(raw: str) -> list[str]:
    """Split a comma-separated token, stripping whitespace."""
    return [p.strip() for p in raw.split(",") if p.strip()]


# ---------------------------------------------------------------------------
# Argument parser (lightweight, no argparse dependency)
# ---------------------------------------------------------------------------

# Maps short flag -> (long key used in result dict, value type)
_FLAG_MAP: dict[str, tuple[str, str]] = {
    "b": ("blocks",        "block"),
    "g": ("gids",          "int"),
    "e": ("eids",          "int"),
    "t": ("etypes",        "str"),
    "s": ("subcases",      "int"),
    "c": ("cols",          "int"),
    # long-form aliases
    "blocks":    ("blocks",   "block"),
    "gids":      ("gids",     "int"),
    "eids":      ("eids",     "int"),
    "etypes":    ("etypes",   "str"),
    "subcases":  ("subcases", "int"),
    "cols":      ("cols",     "int"),
}

# Flags that take no value (boolean switches) – ignored for TOML output
_BOOL_FLAGS = {"H", "headers", "tab", "crlf", "v", "verbose"}


def _parse_args(args: list[str]) -> dict[str, list[Any]]:
    """Parse a flat list of f06csv tokens into a dict of filter lists.

    Accepts both ``-b=displacements`` and ``-b displacements`` styles,
    as well as comma-separated values in a single token (``-g=1,3,7``).
    """
    result: dict[str, list[Any]] = {
        "blocks": [], "gids": [], "eids": [],
        "etypes": [], "subcases": [], "cols": [],
    }

    i = 0
    while i < len(args):
        token = args[i]

        # ---- long flag: --key=value or --key value -------------------------
        m = re.fullmatch(r"--([a-zA-Z_-]+)(?:=(.*))?", token)
        if m:
            key_raw, val_inline = m.group(1), m.group(2)
            key_raw = key_raw.replace("-", "_")
            if key_raw in _BOOL_FLAGS:
                i += 1
                continue
            if key_raw not in _FLAG_MAP:
                i += 1
                continue
            dest, vtype = _FLAG_MAP[key_raw]
            if val_inline is None:
                i += 1
                if i < len(args) and not args[i].startswith("-"):
                    val_inline = args[i]
                else:
                    i += 1
                    continue
            for part in _split_csv(val_inline):
                if vtype == "int":
                    result[dest].append(int(part))
                elif vtype == "block":
                    result[dest].append(_resolve_block(part))
                else:
                    result[dest].append(part)
            i += 1
            continue

        # ---- short flag: -k=value or -k value ------------------------------
        m = re.fullmatch(r"-([a-zA-Z])(?:=(.*))?", token)
        if m:
            key_raw, val_inline = m.group(1), m.group(2)
            if key_raw in _BOOL_FLAGS:
                i += 1
                continue
            if key_raw not in _FLAG_MAP:
                i += 1
                continue
            dest, vtype = _FLAG_MAP[key_raw]
            if val_inline is None:
                i += 1
                if i < len(args) and not args[i].startswith("-"):
                    val_inline = args[i]
                else:
                    i += 1
                    continue
            for part in _split_csv(val_inline):
                if vtype == "int":
                    result[dest].append(int(part))
                elif vtype == "block":
                    result[dest].append(_resolve_block(part))
                else:
                    result[dest].append(part)
            i += 1
            continue

        # positional / unrecognised token – skip
        i += 1

    return result


# ---------------------------------------------------------------------------
# Mapping from f06csv filter keys to f06magic TOML keys
# ---------------------------------------------------------------------------

# (filter_key, singular_toml_key, plural_toml_key)
_FIELD_MAP = [
    ("blocks",   "block",        "blocks"),
    ("gids",     "node",         "nodes"),
    ("eids",     "element",      "elements"),
    ("etypes",   "element_type", "element_types"),
    ("subcases", "subcase",      "subcases"),
    ("cols",     "column",       "columns"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def f06csv_args_to_magic(
    args: list[str] | str,
    *,
    name: str = "extraction",
) -> str:
    """Convert f06csv filter arguments to an f06magic TOML extraction block.

    Parameters
    ----------
    args:
        Either a list of tokens (e.g. ``["-b", "displacements", "-g=1,3,7"]``)
        or a single shell-style string (e.g. ``"-b displacements -g 1,3,7"``).
    name:
        The value to use for the ``name`` key in the extraction block.

    Returns
    -------
    str
        A TOML ``[[extraction]]`` block as a string.

    Examples
    --------
    >>> print(f06csv_args_to_magic("-b displacements -g 1,3,7"))
    [[extraction]]
    name = "my_extraction"
    block = "displacements"
    nodes = [1, 3, 7]

    >>> print(f06csv_args_to_magic(["-b=1", "-s", "2", "-e", "10,20"]))
    [[extraction]]
    name = "my_extraction"
    block = 1
    subcase = 2
    elements = [10, 20]
    """
    if isinstance(args, str):
        args = shlex.split(args)

    filters = _parse_args(args)

    lines: list[str] = ["[[extraction]]", f'name = "{name}"']

    for filter_key, singular, plural in _FIELD_MAP:
        values = filters[filter_key]
        if not values:
            continue
        toml_key = singular if len(values) == 1 else plural
        lines.append(f"{toml_key} = {_toml_value(values)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # Everything after the script name is treated as f06csv args.
    # Optionally pass --name=<name> as the very first argument.
    argv = sys.argv[1:]
    extraction_name = "extraction"
    if argv and argv[0].startswith("--name="):
        extraction_name = argv[0].split("=", 1)[1]
        argv = argv[1:]

    print(f06csv_args_to_magic(argv, name=extraction_name))
