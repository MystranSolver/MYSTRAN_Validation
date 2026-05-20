"""
Nastran input deck parser for element grid point connectivity.

Supports CTRIA3, CQUAD4, CQUAD8, CHEXA, CPENTA, CTETRA elements.
Handles short-field (8-char), long-field (16-char), and free-field (CSV) formats.

Returns a list of ElementRecord namedtuples with fields:
    elem_type : str   – e.g. 'CTRIA3'
    eid       : int   – element ID
    pid       : int   – property ID
    nodes     : list[int] – grid point IDs (G1 … Gn)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------

@dataclass
class ElementRecord:
    elem_type: str
    eid: int
    pid: int
    nodes: list[int]

    def __repr__(self) -> str:
        return (
            f"ElementRecord(type={self.elem_type!r}, eid={self.eid}, "
            f"pid={self.pid}, nodes={self.nodes})"
        )


# ---------------------------------------------------------------------------
# Expected node counts per element type
# (minimum required; trailing zeros / blanks are stripped automatically)
# ---------------------------------------------------------------------------

_ELEM_NODES: dict[str, int] = {
    "CTRIA3": 3,
    "CQUAD4": 4,
    "CQUAD8": 8,
    "CHEXA":  20,
    "CPENTA": 15,
    "CTETRA": 10,
}

_TARGET_TYPES = set(_ELEM_NODES)


# ---------------------------------------------------------------------------
# Line format detection
# ---------------------------------------------------------------------------

def _is_long_field(line: str) -> bool:
    """A long-field card starts with an asterisk (*) or the keyword ends with *."""
    return line.startswith("*") or (len(line) > 8 and line[8] == "*") or bool(re.match(r"^[A-Z0-9]+\*", line))


def _is_free_field(line: str) -> bool:
    """Free-field cards contain commas."""
    return "," in line


# ---------------------------------------------------------------------------
# Field parsers
# ---------------------------------------------------------------------------

def _parse_short_fields(line: str) -> list[str]:
    """Split an 80-column short-field card into 10 × 8-character fields."""
    padded = line.rstrip("\n").rstrip("\r")
    # Pad to at least 80 chars so we can always slice
    padded = padded.ljust(80)
    return [padded[i: i + 8] for i in range(0, 80, 8)]


def _parse_long_fields(line: str) -> list[str]:
    """Split a long-field continuation card into 5 × 16-character data fields.

    Long-field layout (per field):
        col  1–8  : keyword (or *)
        col  9–24 : field 2  (16 chars)
        col 25–40 : field 3
        col 41–56 : field 4
        col 57–72 : field 5
        col 73–80 : sequence / ignored
    We return fields [1..4] as strings (0-based index 1–4 after the keyword).
    """
    padded = line.rstrip("\n").rstrip("\r").ljust(80)
    fields = [padded[0:8]]  # keyword field
    for i in range(8, 72, 16):
        fields.append(padded[i: i + 16])
    return fields


def _parse_free_fields(line: str) -> list[str]:
    """Split a free-field (comma-delimited) card."""
    # Strip inline comments ($ after a comma-delimited field)
    line = line.split("$")[0]
    parts = line.split(",")
    return [p.strip() for p in parts]


def _clean_int(s: str) -> int | None:
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Logical-line assembler
# ---------------------------------------------------------------------------

def _iter_logical_lines(raw_lines: list[str]) -> Iterator[list[str]]:
    """
    Yield logical cards as lists of raw text lines (first line + continuations).
    Handles:
      - $ comment lines (skipped)
      - INCLUDE directives (skipped with a warning)
      - Short, long, and free-field continuation detection
    """
    i = 0
    n = len(raw_lines)

    while i < n:
        line = raw_lines[i]

        # Skip blank lines and comment lines
        stripped = line.strip()
        if not stripped or stripped.startswith("$"):
            i += 1
            continue

        # Skip INCLUDE (not supported here)
        if stripped.upper().startswith("INCLUDE"):
            i += 1
            continue

        # Skip Executive / Case Control section markers
        upper = stripped.upper()
        if upper in ("BEGIN BULK", "ENDDATA", "END DATA"):
            i += 1
            continue

        logical = [line]
        i += 1

        # Gather continuation lines
        while i < n:
            next_line = raw_lines[i]
            ns = next_line.strip()

            # Blank / comment → end of continuation
            if not ns or ns.startswith("$"):
                break

            # A continuation line starts with a '+', '*', or a space in col 1
            # (for short-field) or col 1 is '*' (long-field continuation).
            first_char = next_line[0] if next_line else ""
            if first_char in (" ", "+", "*"):
                logical.append(next_line)
                i += 1
            elif "," in next_line and "," in line:
                # Free-field continuation: just a comma-starting line
                # Some encoders put a bare comma at the start
                if ns.startswith(",") or next_line[0] == ",":
                    logical.append(next_line)
                    i += 1
                else:
                    break
            else:
                break

        yield logical


# ---------------------------------------------------------------------------
# Card decoder
# ---------------------------------------------------------------------------

def _decode_card(logical_lines: list[str]) -> tuple[str, list[str]] | None:
    """
    Return (keyword, [data_fields]) for a logical card, or None to skip.

    data_fields is a flat list of stripped strings for fields F2, F3, … across
    all continuation lines (field 1 / keyword is excluded).
    """
    first = logical_lines[0]

    if _is_free_field(first):
        # ---- FREE FIELD -------------------------------------------------------
        fields = _parse_free_fields(first)
        keyword = fields[0].strip().rstrip("*").upper() if fields else ""
        data: list[str] = list(fields[1:])

        for cont in logical_lines[1:]:
            cf = _parse_free_fields(cont)
            # Skip the leading continuation marker field ('+' or blank)
            start = 1 if cf and cf[0].strip() in ("", "+") else 0
            data.extend(cf[start:])

    elif _is_long_field(first):
        # ---- LONG FIELD -------------------------------------------------------
        raw_kw = first[:8].strip().lstrip("*").rstrip("*").upper()
        keyword = raw_kw
        lf = _parse_long_fields(first)
        data = [f.strip() for f in lf[1:]]  # fields 2–5

        for cont in logical_lines[1:]:
            cf = _parse_long_fields(cont)
            # field[0] is the continuation marker (* or +*)
            data.extend(f.strip() for f in cf[1:])

    else:
        # ---- SHORT FIELD ------------------------------------------------------
        sf = _parse_short_fields(first)
        keyword = sf[0].strip().upper()
        data = [f.strip() for f in sf[1:]]  # fields 2–10

        for cont in logical_lines[1:]:
            csf = _parse_short_fields(cont)
            # field[0] is the continuation marker
            data.extend(f.strip() for f in csf[1:])

    if not keyword:
        return None
    return keyword, data


# ---------------------------------------------------------------------------
# Element builder
# ---------------------------------------------------------------------------

def _build_element(keyword: str, data: list[str]) -> ElementRecord | None:
    """
    Parse EID, PID, and node list from the flat data fields.

    data[0] = EID, data[1] = PID, data[2:] = G1, G2, … (with possible blanks)
    """
    if len(data) < 3:
        return None

    eid = _clean_int(data[0])
    pid = _clean_int(data[1])
    if eid is None or pid is None:
        return None

    n_expected = _ELEM_NODES[keyword]
    raw_nodes = data[2: 2 + n_expected + 5]  # grab a few extra to be safe

    nodes: list[int] = []
    for token in raw_nodes:
        if len(nodes) >= n_expected:
            break
        v = _clean_int(token)
        if v is not None and v != 0:
            nodes.append(v)

    return ElementRecord(elem_type=keyword, eid=eid, pid=pid, nodes=nodes)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_nastran_connectivity(
    source: str | Path,
    *,
    bulk_only: bool = True,
) -> list[ElementRecord]:
    """
    Read a Nastran input deck and extract element connectivity records for
    CTRIA3, CQUAD4, CQUAD8, CHEXA, CPENTA, and CTETRA elements.

    Parameters
    ----------
    source : str | Path
        Path to the .bdf / .dat / .nas file, **or** a multi-line string
        containing the deck contents directly.
    bulk_only : bool
        If True (default) only parse cards after the "BEGIN BULK" marker.
        Set to False to parse from the top of the file (useful for pure
        bulk-only files that omit the marker).

    Returns
    -------
    list[ElementRecord]
        Each record has .elem_type, .eid, .pid, .nodes attributes.
    """
    # Accept both file paths and raw strings
    text: str
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).exists()):
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    else:
        text = source  # treat as raw deck text

    raw_lines = text.splitlines(keepends=False)

    # Optionally fast-forward to BEGIN BULK
    if bulk_only:
        for idx, ln in enumerate(raw_lines):
            if ln.strip().upper().startswith("BEGIN BULK"):
                raw_lines = raw_lines[idx + 1:]
                break

    elements: list[ElementRecord] = []

    for logical in _iter_logical_lines(raw_lines):
        decoded = _decode_card(logical)
        if decoded is None:
            continue
        keyword, data = decoded

        if keyword not in _TARGET_TYPES:
            continue

        rec = _build_element(keyword, data)
        if rec is not None:
            elements.append(rec)

    return elements

# ---------------------------------------------------------------------------
# CLI / quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import textwrap

    SAMPLE_DECK = textwrap.dedent("""\
        $ Simple test deck
        BEGIN BULK
        $ --- Short-field CTRIA3 ---
        CTRIA3  101     1       11      12      13
        $ --- Short-field CQUAD4 ---
        CQUAD4  201     2       21      22      23      24
        $ --- Short-field CQUAD8 (two lines) ---
        CQUAD8  301     3       31      32      33      34      35      36
        +       37      38
        $ --- Long-field CHEXA ---
        CHEXA*  401             4               101             102
        *       103             104             105             106
        *       107             108             109             110
        *       111             112             113             114
        *       115             116             117             118
        *       119             120
        $ --- Free-field CTETRA ---
        CTETRA, 501, 5, 201, 202, 203, 204, 205, 206,
        +, 207, 208, 209, 210
        $ --- CPENTA short field ---
        CPENTA  601     6       301     302     303     304     305     306
        +       307     308     309     310     311     312     313     314
        +       315
        CPENTA  602     6       301     302     303     304     305 
        ENDDATA
    """)

    records = parse_nastran_connectivity(SAMPLE_DECK)

    for r in records:
        print(f"{r.elem_type}  EID={r.eid}  nodes={r.nodes}")
