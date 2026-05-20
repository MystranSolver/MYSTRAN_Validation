import re
from typing import Dict, Tuple


def parse_nastran_float(s: str) -> float:
    """
    Parse a Nastran-format float string.
    Nastran allows the 'e' to be omitted, e.g. '1.5+3' means '1.5e+3'
    and '5.42245122022-4' means '5.42245122022e-4'.
    """
    s = s.strip()
    if not s:
        return 0.0
    # Insert 'e' between a digit and a bare +/- exponent sign
    s = re.sub(r'(\d)([+-])(\d)', r'\1e\2\3', s)
    return float(s)


def _short_fields(line: str) -> list[str]:
    """Split a short-field (8-char) Nastran line into 10 fields."""
    padded = line.ljust(80)
    return [padded[i:i + 8].strip() for i in range(0, 80, 8)]


def _long_fields(line: str) -> list[str]:
    """
    Split a long-field (16-char) Nastran line into 5 fields:
    [card_name(8), field2(16), field3(16), field4(16), field5(16)].
    The optional trailing continuation marker occupies chars 72-79.
    """
    padded = line.ljust(80)
    return [
        padded[0:8].strip(),
        padded[8:24].strip(),
        padded[24:40].strip(),
        padded[40:56].strip(),
        padded[56:72].strip(),
    ]


def read_nastran_grids(filename: str) -> Dict[int, Tuple[float, float, float]]:
    """
    Read a Nastran input deck and return a dict mapping grid-point IDs to
    (x, y, z) coordinate tuples.  Only grid points defined in the global
    coordinate system (CP == 0 or blank) are included.

    Supported formats
    -----------------
    Short field  : GRID  followed by 8-character fixed-width fields
    Long field   : GRID* followed by 16-character fixed-width fields
                   (always occupies two physical lines)
    Free field   : comma-separated fields on a single line

    Parameters
    ----------
    filename : path to the Nastran input file (.bdf / .dat / .nas / …)

    Returns
    -------
    Dict[int, Tuple[float, float, float]]
        {gid: (x, y, z), …}  for every qualifying GRID entry.
    """
    grids: Dict[int, Tuple[float, float, float]] = {}

    with open(filename, "r") as fh:
        raw_lines = fh.readlines()

    # Strip inline comments and trailing newlines, but keep line positions
    lines = []
    for raw in raw_lines:
        line = raw.rstrip("\n\r")
        dollar = line.find("$")
        if dollar != -1:
            line = line[:dollar]
        lines.append(line)

    i = 0
    while i < len(lines):
        line = lines[i]
        upper = line.upper()

        # ------------------------------------------------------------------ #
        #  Free-field  (comma-separated)                                      #
        # ------------------------------------------------------------------ #
        if "," in line:
            if upper.startswith("GRID,") or upper.startswith("GRID ,"):
                parts = [p.strip() for p in line.split(",")]
                # parts[0]=GRID, [1]=GID, [2]=CP, [3]=X, [4]=Y, [5]=Z
                gid_s = parts[1] if len(parts) > 1 else ""
                cp_s  = parts[2] if len(parts) > 2 else ""
                x_s   = parts[3] if len(parts) > 3 else ""
                y_s   = parts[4] if len(parts) > 4 else ""
                z_s   = parts[5] if len(parts) > 5 else ""

                cp = int(cp_s) if cp_s else 0
                if gid_s and cp == 0:
                    grids[int(gid_s)] = (
                        parse_nastran_float(x_s) if x_s else 0.0,
                        parse_nastran_float(y_s) if y_s else 0.0,
                        parse_nastran_float(z_s) if z_s else 0.0,
                    )
            i += 1

        # ------------------------------------------------------------------ #
        #  Long field  (GRID*)                                                #
        # ------------------------------------------------------------------ #
        elif upper[:8].strip() == "GRID*":
            f1 = _long_fields(line)
            # f1 layout: [GRID*, GID, CP, X, Y]
            i += 1
            # Consume the mandatory continuation line (starts with *)
            f2 = _long_fields(lines[i]) if i < len(lines) else [""] * 5
            # f2 layout: [*, Z, CD, ...]
            i += 1

            gid_s = f1[1]
            cp_s  = f1[2]
            cp = int(cp_s) if cp_s else 0

            if gid_s and cp == 0:
                grids[int(gid_s)] = (
                    parse_nastran_float(f1[3]) if f1[3] else 0.0,
                    parse_nastran_float(f1[4]) if f1[4] else 0.0,
                    parse_nastran_float(f2[1]) if f2[1] else 0.0,
                )

        # ------------------------------------------------------------------ #
        #  Short field  (GRID, 8-char columns)                                #
        # ------------------------------------------------------------------ #
        elif upper[:8].strip() == "GRID":
            f = _short_fields(line)
            # f layout: [GRID, GID, CP, X, Y, Z, CD, PS, SEID, -]
            gid_s = f[1]
            cp_s  = f[2]
            cp = int(cp_s) if cp_s else 0

            if gid_s and cp == 0:
                grids[int(gid_s)] = (
                    parse_nastran_float(f[3]) if f[3] else 0.0,
                    parse_nastran_float(f[4]) if f[4] else 0.0,
                    parse_nastran_float(f[5]) if f[5] else 0.0,
                )
            i += 1

        else:
            i += 1

    return grids