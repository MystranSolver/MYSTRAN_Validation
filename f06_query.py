import math
import sys
from io import TextIOWrapper


INDENT = "  "

class F06Query:
  
    def __init__(self, file_name):
        self.file_name = file_name
        self.parsed_f06 = self._read()
        
    def _read(self):

        try:
            # Unicode by default for U-dot-dot character in GPFORCE's INERTIA FORCE
            with open(self.file_name, mode='r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            # Unicode fails on older versions of Mystran that use some 
            # other encoding for U-dot-dot.
            # We can't always use this default encoding because it treats
            # the unicode U-dot-dot as two characters and misaligns the line.
            with open(self.file_name, mode='r') as f:
                lines = f.readlines()

        root = {}
        line_no = 0
        previous_prefix = None

        def ensure_path(current_node, path):
            for node in path:
                if not node in current_node:
                    current_node[node] = {}
                current_node = current_node[node]
            return current_node

        def set(node, key, value):
            node[key] = value

        def get_next_line():
            nonlocal line_no
            if line_no >= len(lines):
                print(f"ERROR: Unexpected end of file at line {line_no} of {self.file_name}")
                return ""
            line = lines[line_no]
            line_no += 1
            return line

        def peek_line_delta(delta):
            return lines[line_no - 1 + delta]

        def number(line, start, length, blank_is_inf=False):
            segment = line[start - 1:start - 1 + length].strip()
            if blank_is_inf and segment == "":
                return float('inf')
            try:
                return float(segment)
            except Exception as e:
                # It might be a 3-digit exponent without the "e" like:
                #
                #           2.714527-111
                # or
                #           2.714527+111
                segment = segment[:-4] + "E" + segment[-4:]
                return float(segment)

        def subcase_or_mode():
            # Search backwards not more than up to 8 non-blank lines and skipping blank lines
            # Non-blank lines are typically TITLE, SUBT, LABEL
            # Sometimes TITLE appears 2-6 times due to a possible Mystran bug
            # Blank lines are sometimes a lot due to a possible Mystran bug
            nonlocal previous_prefix
            non_blanks = 0
            delta = -2
            while True:
                line = peek_line_delta(delta)
                if "OUTPUT FOR SUBCASE" in line:
                    subcase = int(number(line, 21, 8))
                    previous_prefix = ["SC", str(subcase)]
                    return previous_prefix
                if "OUTPUT FOR EIGENVECTOR" in line:
                    mode = int(number(line, 25, 8))
                    previous_prefix = ["MODE", str(mode)]
                    return previous_prefix
                if line.strip() != "":
                    non_blanks += 1
                if non_blanks > 8:
                    return None
                delta -= 1        
      
        while line_no < len(lines):
            line = get_next_line()

            
            if "D I S P L A C E M E N T S" in line \
            or "E I G E N V E C T O R" in line \
            or "S P C   F O R C E S" in line \
            or "M P C   F O R C E S" in line \
            or "A P P L I E D    F O R C E S" in line:
                if "D I S P L A C E M E N T S" in line:     block_name = "DISPLACEMENTS"
                if "E I G E N V E C T O R" in line:         block_name = "EIGENVECTOR"
                if "S P C   F O R C E S" in line:           block_name = "SPCFORCES"
                if "M P C   F O R C E S" in line:           block_name = "MPCFORCES"
                if "A P P L I E D    F O R C E S" in line:  block_name = "APPLIEDFORCES"
                prefix = subcase_or_mode()
                gids_node = ensure_path(root, prefix + [block_name, "GID"])
                get_next_line()
                line = get_next_line()
                if "(including equivalent thermal loads)" in line:
                    get_next_line()
                get_next_line()
                had_blank_line = False
                while True:
                    line = get_next_line()
                    if len(line) >= 27 and line[0:15].strip().isdigit():
                        # This line has data.
                        had_blank_line = False
                        gid = int(number(line, 8, 8))
                        gid_node = ensure_path(gids_node, [str(gid)])
                        set(gid_node, "TX", number(line, 26, 13))
                        set(gid_node, "TY", number(line, 40, 13))
                        set(gid_node, "TZ", number(line, 54, 13))
                        set(gid_node, "RX", number(line, 68, 13))
                        set(gid_node, "RY", number(line, 82, 13))
                        set(gid_node, "RZ", number(line, 96, 13))
                    elif line.startswith(" *INFORMATION:"):
                        # It can be this:
                        # *INFORMATION: COORD SYSTEM       -2 FOR STRESS TRANSFORMATION IS UNDEFINED. LOCAL ELEMENT COORD SYSTEM WILL BE USED
                        had_blank_line = False
                        break
                    elif had_blank_line:
                        # A non-data line after a blank line is past the end of the block.
                        break
                    elif len(line.strip()) == 0:
                        # Skip blank line at GID gaps.
                        had_blank_line = True
                        continue
                    else:
                        # Not data and not blank. Might be ---
                        break

            elif "G R I D   P O I N T   F O R C E   B A L A N C E" in line \
            and not "C B   G R I D   P O I N T   F O R C E   B A L A N C E   O T M" in line:
                prefix = subcase_or_mode()
                if prefix is None:
                    if previous_prefix is not None:
                        # Some v15 files (SS-BAR-10-BUCKLING-CF-LOAD-LAN-3D.F06) have no subcase or
                        # mode for GPFORCE. Use the subcase or mode that was last read, from the 
                        # previous block.
                        prefix = previous_prefix
                    else:
                        # Can't know what to do.
                        print(f"ERROR reading {self.file_name}: No previous block with subcase or eigenvector before line {line_no}:")
                        print(line)
                        sys.exit(1)
                get_next_line()
                get_next_line()
                gids_node = ensure_path(root, prefix + ["GPFORCE","GID"])
                # Read grid point sub-blocks
                while True:
                    line = get_next_line()
                    if "FORCE BALANCE FOR GRID POINT" in line:
                        gid = int(number(line, 62, 8))
                        get_next_line()
                        get_next_line()
                        get_next_line()
                        gid_node = ensure_path(gids_node, [str(gid)])
                        # Rows in sub-block
                        while True:
                            line = get_next_line()
                            if "APPLIED FORCE" in line:
                                applied_node = ensure_path(gid_node, ["APPLIED"])
                                set(applied_node, "TX", number(line, 26, 13))
                                set(applied_node, "TY", number(line, 40, 13))
                                set(applied_node, "TZ", number(line, 54, 13))
                                set(applied_node, "RX", number(line, 68, 13))
                                set(applied_node, "RY", number(line, 82, 13))
                                set(applied_node, "RZ", number(line, 96, 13))
                            elif "SPC FORCE" in line:
                                spc_node = ensure_path(gid_node, ["SPC"])
                                set(spc_node, "TX", number(line, 26, 13))
                                set(spc_node, "TY", number(line, 40, 13))
                                set(spc_node, "TZ", number(line, 54, 13))
                                set(spc_node, "RX", number(line, 68, 13))
                                set(spc_node, "RY", number(line, 82, 13))
                                set(spc_node, "RZ", number(line, 96, 13))
                            elif "MPC FORCE" in line:
                                mpc_node = ensure_path(gid_node, ["MPC"])
                                set(mpc_node, "TX", number(line, 26, 13))
                                set(mpc_node, "TY", number(line, 40, 13))
                                set(mpc_node, "TZ", number(line, 54, 13))
                                set(mpc_node, "RX", number(line, 68, 13))
                                set(mpc_node, "RY", number(line, 82, 13))
                                set(mpc_node, "RZ", number(line, 96, 13))
                            elif "INERTIA FORCE" in line:
                                inertia_node = ensure_path(gid_node, ["INERTIA"])
                                set(inertia_node, "TX", number(line, 26, 13))
                                set(inertia_node, "TY", number(line, 40, 13))
                                set(inertia_node, "TZ", number(line, 54, 13))
                                set(inertia_node, "RX", number(line, 68, 13))
                                set(inertia_node, "RY", number(line, 82, 13))
                                set(inertia_node, "RZ", number(line, 96, 13))
                            elif "ELEM" in line:
                                eid = int(number(line, 17, 8))
                                eids_node = ensure_path(gid_node, ["EID"])
                                eid_node = ensure_path(eids_node, [str(eid)])
                                set(eid_node, "TX", number(line, 26, 13))
                                set(eid_node, "TY", number(line, 40, 13))
                                set(eid_node, "TZ", number(line, 54, 13))
                                set(eid_node, "RX", number(line, 68, 13))
                                set(eid_node, "RY", number(line, 82, 13))
                                set(eid_node, "RZ", number(line, 96, 13))
                            else:
                                # End of sub-block
                                break
                    elif line.startswith(" TOTALS"):
                        continue
                    elif line.startswith(" (should all be 0)"):
                        continue
                    elif line.strip() == "":
                        continue
                    else:
                        # End of block
                        break

            elif "E L E M E N T   S T R E S S E S   I N   M A T E R I A L   C O O R D I N A T E   S Y S T E M" in line:
                prefix = subcase_or_mode()
                if prefix is not None:
                    line = get_next_line()
                    if "F O R   E L E M E N T   T Y P E   H E X A" in line \
                    or "F O R   E L E M E N T   T Y P E   P E N T A" in line \
                    or "F O R   E L E M E N T   T Y P E   T E T R A" in line:
                        eids_node = ensure_path(root, prefix + ["SOLIDSTRESSES","EID"])
                        get_next_line()
                        get_next_line()
                        corner = None
                        while True:
                            line = get_next_line()
                            if line.strip().startswith("---") or len(line.strip()) == 0:
                                break
                            if line[11:11+6] == "CENTER":
                                eid = int(number(line, 2,8))
                                eid_node = ensure_path(eids_node, [str(eid)])
                                corner =0
                                corner_gid = None
                            elif line[11:11+3] == "GRD":
                                corner += 1
                                corner_gid = int(number(line, 15, 8))
                            corner_node = ensure_path(eid_node, ["CORNER", str(corner)])
                            if corner_gid is not None:
                                set(corner_node, "GID", corner_gid)
                            set(corner_node, "XX", number(line, 29, 13))
                            set(corner_node, "YY", number(line, 43, 13))
                            set(corner_node, "ZZ", number(line, 57, 13))
                            set(corner_node, "XY", number(line, 71, 13))
                            set(corner_node, "YZ", number(line, 85, 13))
                            set(corner_node, "ZX", number(line, 99, 13))
                            set(corner_node, "VONMISES", number(line, 113, 13)) # todo might be max. shear. Read column header to decide.

            elif "E L E M E N T   S T R E S S E S   I N   L O C A L   E L E M E N T   C O O R D I N A T E   S Y S T E M" in line:
                prefix = subcase_or_mode()
                if prefix is None:
                    print(f"ERROR reading {self.file_name}: No subcase or eigenvector found before line {line_no}:")
                    print(line)
                    sys.exit(1)
                line = get_next_line()
                if "F O R   E L E M E N T   T Y P E   Q U A D 4" in line \
                or "F O R   E L E M E N T   T Y P E   Q U A D 8" in line:
                    eids_node = ensure_path(root, prefix + ["SHELLSTRESSES","EID"])
                    get_next_line()
                    get_next_line()
                    get_next_line()
                    corner = None
                    while True:
                        line = get_next_line()
                        if line.strip().startswith("---"):
                            break
                        if line[11:11+6] == "CENTER":
                            eid = int(number(line, 2,8))
                            eid_node = ensure_path(eids_node, [str(eid)])
                            corner = 0
                            corner_gid = None
                        elif line[11:11+3] == "GRD":
                            corner += 1
                            corner_gid = int(number(line, 15, 8))
                        else:
                            # Skip the blank lines between corners
                            continue
                        corner_node = ensure_path(eid_node, ["CORNER", str(corner)])
                        if corner_gid is not None:
                            set(corner_node, "GID", corner_gid)
                        set(corner_node, "ZX", number(line, 121, 12))
                        set(corner_node, "YZ", number(line, 134, 12))
                        z1_node = ensure_path(corner_node, ["Z1"])
                        set(z1_node, "XX", number(line, 35, 12))
                        set(z1_node, "YY", number(line, 48, 12))
                        set(z1_node, "XY", number(line, 61, 12))
                        set(z1_node, "PRINCIPALANGLE", number(line, 75, 6))
                        set(z1_node, "VONMISES", number(line, 108, 12))
                        line = get_next_line()
                        z2_node = ensure_path(corner_node, ["Z2"])
                        set(z2_node, "XX", number(line, 35, 12))
                        set(z2_node, "YY", number(line, 48, 12))
                        set(z2_node, "XY", number(line, 61, 12))
                        set(z2_node, "PRINCIPALANGLE", number(line, 75, 6))
                        set(z2_node, "VONMISES", number(line, 108, 12))

                elif "F O R   E L E M E N T   T Y P E   T R I A 3" in line:
                    eids_node = ensure_path(root, prefix + ["SHELLSTRESSES","EID"])
                    get_next_line()
                    get_next_line()
                    get_next_line()
                    corner = None
                    while True:
                        line = get_next_line()
                        if line.strip().startswith("---"):
                            break
                        if line[13:13+8] == "Anywhere":
                            eid = int(number(line, 2,8))
                            eid_node = ensure_path(eids_node, [str(eid)])
                            corner =0
                            corner_node = ensure_path(eid_node, ["CORNER", str(corner)])
                            set(corner_node, "ZX", number(line, 125, 12))
                            set(corner_node, "YZ", number(line, 138, 12))
                            z1_node = ensure_path(corner_node, ["Z1"])
                            set(z1_node, "XX", number(line, 38, 12))
                            set(z1_node, "YY", number(line, 51, 12))
                            set(z1_node, "XY", number(line, 64, 12))
                            set(z1_node, "PRINCIPALANGLE", number(line, 78, 7))
                            set(z1_node, "VONMISES", number(line, 112, 12))
                            line = get_next_line()
                            z2_node = ensure_path(corner_node, ["Z2"])
                            set(z2_node, "XX", number(line, 38, 12))
                            set(z2_node, "YY", number(line, 51, 12))
                            set(z2_node, "XY", number(line, 64, 12))
                            set(z2_node, "PRINCIPALANGLE", number(line, 78, 7))
                            set(z2_node, "VONMISES", number(line, 112, 12))

                elif "F O R   E L E M E N T   T Y P E   B U S H" in line:
                    eids_node = ensure_path(root, prefix + ["BUSHSTRESSES","EID"])
                    get_next_line()
                    get_next_line()
                    while True:
                        line = get_next_line()
                        if line.strip().startswith("---") or len(line.strip()) == 0:
                            break
                        eid = int(number(line, 20, 8))
                        eid_node = ensure_path(eids_node, [str(eid)])
                        set(eid_node, "TX", number(line, 29, 13))
                        set(eid_node, "TY", number(line, 43, 13))
                        set(eid_node, "TZ", number(line, 57, 13))
                        set(eid_node, "RX", number(line, 71, 13))
                        set(eid_node, "RY", number(line, 85, 13))
                        set(eid_node, "RZ", number(line, 99, 13))

                elif "F O R   E L E M E N T   T Y P E   B A R" in line:
                    eids_node = ensure_path(root, prefix + ["BARSTRESSES","EID"])
                    get_next_line()
                    get_next_line()
                    get_next_line()
                    while True:
                        line = get_next_line()
                        if line.strip().startswith("---"):
                            break
                        elif len(line.strip()) == 0:
                            continue # Skip blank lines
                        else:
                            eid = int(number(line, 2,8))
                            eid_node = ensure_path(eids_node, [str(eid)])
                            set(eid_node, "SA1", number(line, 11, 13))
                            set(eid_node, "SA2", number(line, 25, 13))
                            set(eid_node, "SA3", number(line, 39, 13))
                            set(eid_node, "SA4", number(line, 53, 13))
                            set(eid_node, "AXIAL", number(line, 67, 13))
                            line = get_next_line()
                            set(eid_node, "SB1", number(line, 11, 13))
                            set(eid_node, "SB2", number(line, 25, 13))
                            set(eid_node, "SB3", number(line, 39, 13))
                            set(eid_node, "SB4", number(line, 53, 13))

                elif "F O R   E L E M E N T   T Y P E   R O D" in line:
                    eids_node = ensure_path(root, prefix + ["RODSTRESSES","EID"])
                    get_next_line()
                    get_next_line()
                    while True:
                        line = get_next_line()
                        if line.strip().startswith("---"):
                            break
                        else:
                            eid = int(number(line, 2,8))
                            eid_node = ensure_path(eids_node, [str(eid)])
                            set(eid_node, "AXIAL", number(line, 11, 13))
                            set(eid_node, "AXIALSAFETY", number(line, 25, 9, blank_is_inf=True))
                            set(eid_node, "TORSIONAL", number(line, 36, 13))
                            set(eid_node, "TORSIONALSAFETY", number(line, 50, 9, blank_is_inf=True))
                            if len(line) > 67 and line[66] != " ":
                                eid = int(number(line, 60,8))
                                eid_node = ensure_path(eids_node, [str(eid)])
                                set(eid_node, "AXIAL", number(line, 69, 13))
                                set(eid_node, "AXIALSAFETY", number(line, 83, 9, blank_is_inf=True))
                                set(eid_node, "TORSIONAL", number(line, 94, 13))
                                set(eid_node, "TORSIONALSAFETY", number(line, 108, 9, blank_is_inf=True))

                elif "F O R   E L E M E N T   T Y P E   E L A S 1" in line:
                    eids_node = ensure_path(root, prefix + ["ELAS1STRESSES","EID"])
                    get_next_line()
                    get_next_line()
                    while True:
                        line = get_next_line()
                        if line.strip().startswith("---") or len(line.strip()) == 0:
                            break
                        else:
                            for element_col in range(5):
                                start = element_col * 23
                                if len(line) > start+9 and line[start+8] != " ":
                                    eid = int(number(line, start + 2,8))
                                    set(eids_node, str(eid), number(line, start + 11, 13))


            elif "S T R E S S E S   I N   L A Y E R E D   C O M P O S I T E   E L E M E N T S" in line:
                prefix = subcase_or_mode()
                if prefix is not None:
                    get_next_line()
                    get_next_line()
                    get_next_line()
                    line = get_next_line()
                    if "F O R   E L E M E N T   T Y P E   Q U A D 4" in line \
                    or "F O R   E L E M E N T   T Y P E   Q U A D 8" in line \
                    or "F O R   E L E M E N T   T Y P E   T R I A 3" in line:
                        eids_node = ensure_path(root, prefix + ["COMPOSITESTRESSES","EID"])
                        get_next_line()
                        get_next_line()
                        get_next_line()
                        get_next_line()
                        get_next_line()
                        get_next_line()
                        get_next_line()
                        get_next_line()
                        while True:
                            line = get_next_line()
                            if line.strip().startswith("---"):
                                break
                            if line[1:1+8].strip() != "":
                                eid = int(number(line, 2,8))
                                eid_node = ensure_path(eids_node, [str(eid)])
                            elif line.strip() == "":
                                # Skip the blank lines between elements
                                continue
                            ply_num = int(number(line, 11,5))
                            ply_node = ensure_path(eid_node, ["PLY", str(ply_num)])
                            set(ply_node, "11", number(line, 17, 12))
                            set(ply_node, "22", number(line, 30, 12))
                            set(ply_node, "12", number(line, 43, 12))
                            set(ply_node, "13", number(line, 59, 12))
                            set(ply_node, "23", number(line, 73, 12))

            elif "E L E M E N T   S T R A I N S   I N   M A T E R I A L   C O O R D I N A T E   S Y S T E M" in line:
                prefix = subcase_or_mode()
                if prefix is not None:
                    line = get_next_line()
                    if "F O R   E L E M E N T   T Y P E   H E X A" in line \
                    or "F O R   E L E M E N T   T Y P E   P E N T A" in line \
                    or "F O R   E L E M E N T   T Y P E   T E T R A" in line:
                        eids_node = ensure_path(root, prefix + ["SOLIDSTRAINS","EID"])
                        get_next_line()
                        get_next_line()
                        corner = None
                        while True:
                            line = get_next_line()
                            if line.strip().startswith("---") or len(line.strip()) == 0:
                                break
                            if line[11:11+6] == "CENTER":
                                eid = int(number(line, 2,8))
                                eid_node = ensure_path(eids_node, [str(eid)])
                                corner = 0
                                corner_gid = None
                            elif line[11:11+3] == "GRD":
                                corner += 1
                                corner_gid = int(number(line, 15, 8))
                            corner_node = ensure_path(eid_node, ["CORNER", str(corner)])
                            if corner_gid is not None:
                                set(corner_node, "GID", corner_gid)
                            set(corner_node, "XX", number(line, 29, 13))
                            set(corner_node, "YY", number(line, 43, 13))
                            set(corner_node, "ZZ", number(line, 57, 13))
                            set(corner_node, "XY", number(line, 71, 13))
                            set(corner_node, "YZ", number(line, 85, 13))
                            set(corner_node, "ZX", number(line, 99, 13))
                            set(corner_node, "VONMISES", number(line, 113, 13)) # todo might be max. shear. Read column header to decide.

            elif "E L E M E N T   S T R A I N S   I N   L O C A L   E L E M E N T   C O O R D I N A T E   S Y S T E M" in line:
                prefix = subcase_or_mode()
                if prefix is not None:
                    line = get_next_line()
                    if "F O R   E L E M E N T   T Y P E   Q U A D 4" in line \
                    or "F O R   E L E M E N T   T Y P E   Q U A D 8" in line:
                        eids_node = ensure_path(root, prefix + ["SHELLSTRAINS","EID"])
                        get_next_line()
                        get_next_line()
                        get_next_line()
                        corner = None
                        while True:
                            line = get_next_line()
                            if line.strip().startswith("---"):
                                break
                            if line[11:11+6] == "CENTER":
                                eid = int(number(line, 2,8))
                                eid_node = ensure_path(eids_node, [str(eid)])
                                corner = 0
                                corner_gid = None
                            elif line[11:11+3] == "GRD":
                                corner += 1
                                corner_gid = int(number(line, 15, 8))
                            else:
                                # Skip the blank lines between corners
                                continue
                            corner_node = ensure_path(eid_node, ["CORNER", str(corner)])
                            if corner_gid is not None:
                                set(corner_node, "GID", corner_gid)
                            set(corner_node, "ZX", number(line, 121, 12))
                            set(corner_node, "YZ", number(line, 134, 12))
                            z1_node = ensure_path(corner_node, ["Z1"])
                            set(z1_node, "XX", number(line, 35, 12))
                            set(z1_node, "YY", number(line, 48, 12))
                            set(z1_node, "XY", number(line, 61, 12))
                            set(z1_node, "PRINCIPALANGLE", number(line, 75, 6))
                            line = get_next_line()
                            z2_node = ensure_path(corner_node, ["Z2"])
                            set(z2_node, "XX", number(line, 35, 12))
                            set(z2_node, "YY", number(line, 48, 12))
                            set(z2_node, "XY", number(line, 61, 12))
                            set(z2_node, "PRINCIPALANGLE", number(line, 75, 6))

                    elif "F O R   E L E M E N T   T Y P E   T R I A 3" in line:
                        eids_node = ensure_path(root, prefix + ["SHELLSTRAINS","EID"])
                        get_next_line()
                        get_next_line()
                        get_next_line()
                        corner = None
                        while True:
                            line = get_next_line()
                            if line.strip().startswith("---"):
                                break
                            if line[13:13+8] == "Anywhere":
                                eid = int(number(line, 2,8))
                                eid_node = ensure_path(eids_node, [str(eid)])
                                corner =0
                                corner_node = ensure_path(eid_node, ["CORNER", str(corner)])
                                set(corner_node, "ZX", number(line, 125, 12))
                                set(corner_node, "YZ", number(line, 138, 12))
                                z1_node = ensure_path(corner_node, ["Z1"])
                                set(z1_node, "XX", number(line, 38, 12))
                                set(z1_node, "YY", number(line, 51, 12))
                                set(z1_node, "XY", number(line, 64, 12))
                                set(z1_node, "PRINCIPALANGLE", number(line, 78, 7))
                                line = get_next_line()
                                z2_node = ensure_path(corner_node, ["Z2"])
                                set(z2_node, "XX", number(line, 38, 12))
                                set(z2_node, "YY", number(line, 51, 12))
                                set(z2_node, "XY", number(line, 64, 12))
                                set(z2_node, "PRINCIPALANGLE", number(line, 78, 7))

                    elif "F O R   E L E M E N T   T Y P E   B U S H" in line:
                        eids_node = ensure_path(root, prefix + ["BUSHSTRAINS","EID"])
                        get_next_line()
                        get_next_line()
                        while True:
                            line = get_next_line()
                            if line.strip().startswith("---") or len(line.strip()) == 0:
                                break
                            eid = int(number(line, 20, 8))
                            eid_node = ensure_path(eids_node, [str(eid)])
                            set(eid_node, "TX", number(line, 29, 13))
                            set(eid_node, "TY", number(line, 43, 13))
                            set(eid_node, "TZ", number(line, 57, 13))
                            set(eid_node, "RX", number(line, 71, 13))
                            set(eid_node, "RY", number(line, 85, 13))
                            set(eid_node, "RZ", number(line, 99, 13))

            elif "E L E M E N T   E N G I N E E R I N G   F O R C E S" in line:
                prefix = subcase_or_mode()
                if prefix is None:
                    print(f"ERROR reading {self.file_name}: No subcase or eigenvector found before line {line_no}:")
                    print(line)
                    sys.exit(1)
                line = get_next_line()
                if "F O R   E L E M E N T   T Y P E   Q U A D 4" in line \
                or "F O R   E L E M E N T   T Y P E   Q U A D 8" in line \
                or "F O R   E L E M E N T   T Y P E   T R I A 3" in line:
                    eids_node = ensure_path(root, prefix + ["SHELLFORCES","EID"])
                    get_next_line()
                    get_next_line()
                    get_next_line()
                    corner = None
                    while True:
                        line = get_next_line()
                        if line.strip().startswith("---") or len(line.strip()) == 0:
                            break
                        if line[11:11+3] == "GRD":
                            corner += 1
                            corner_gid = int(number(line, 15, 8))
                        else:
                            if "CENTER" in line:
                                # Some elements (QUAD8) say "CENTER"
                                eid = int(number(line, 2,8))
                            else:
                                # Some elements (QUAD4, TRIA3) don't say "CENTER" and older Mystran put EID futher right
                                eid = int(number(line, 2,23))
                            eid_node = ensure_path(eids_node, [str(eid)])
                            corner = 0
                            corner_gid = None
                        corner_node = ensure_path(eid_node, ["CORNER", str(corner)])
                        if corner_gid is not None:
                            set(corner_node, "GID", corner_gid)
                        set(corner_node, "NXX", number(line, 26, 13))
                        set(corner_node, "NYY", number(line, 40, 13))
                        set(corner_node, "NXY", number(line, 54, 13))
                        set(corner_node, "MXX", number(line, 68, 13))
                        set(corner_node, "MYY", number(line, 82, 13))
                        set(corner_node, "MXY", number(line, 96, 13))
                        set(corner_node, "QX", number(line, 110, 13))
                        set(corner_node, "QY", number(line, 124, 13))

                if "F O R   E L E M E N T   T Y P E   B U S H" in line:
                    eids_node = ensure_path(root, prefix + ["BUSHFORCES","EID"])
                    get_next_line()
                    get_next_line()
                    while True:
                        line = get_next_line()
                        if line.strip().startswith("---") or len(line.strip()) == 0:
                            break
                        else:
                            eid = int(number(line, 17, 8))
                            eid_node = ensure_path(eids_node, [str(eid)])
                        set(eid_node, "TX", number(line, 26, 13))
                        set(eid_node, "TY", number(line, 40, 13))
                        set(eid_node, "TZ", number(line, 54, 13))
                        set(eid_node, "RX", number(line, 68, 13))
                        set(eid_node, "RY", number(line, 82, 13))
                        set(eid_node, "RZ", number(line, 96, 13))

                if "F O R   E L E M E N T   T Y P E   B A R" in line:
                    eids_node = ensure_path(root, prefix + ["BARFORCES","EID"])
                    get_next_line()
                    get_next_line()
                    while True:
                        line = get_next_line()
                        if line.strip().startswith("OUTPUT FOR"):
                            # Mystran v15- would sometimes include this spurious line.
                            continue
                        if line.strip().startswith("---") or len(line.strip()) == 0:
                            break
                        else:
                            eid = int(number(line, 17, 8))
                            eid_node = ensure_path(eids_node, [str(eid)])
                        set(eid_node, "MA1", number(line, 26, 13))
                        set(eid_node, "MA2", number(line, 40, 13))
                        set(eid_node, "MB1", number(line, 54, 13))
                        set(eid_node, "MB2", number(line, 68, 13))
                        set(eid_node, "S1", number(line, 82, 13))
                        set(eid_node, "S2", number(line, 96, 13))
                        set(eid_node, "AXIAL", number(line, 110, 13))
                        set(eid_node, "TORQUE", number(line, 124, 13))

                if "F O R   E L E M E N T   T Y P E   R O D" in line:
                    eids_node = ensure_path(root, prefix + ["RODFORCES","EID"])
                    get_next_line()
                    get_next_line()
                    while True:
                        line = get_next_line()
                        if line.strip().startswith("---"):
                            break
                        eid = int(number(line, 17, 8))
                        eid_node = ensure_path(eids_node, [str(eid)])
                        set(eid_node, "AXIAL", number(line, 26, 13))
                        set(eid_node, "TORQUE", number(line, 40, 13))
                        if len(line) > 60 and line[59] != " ":
                            eid = int(number(line, 53,8))
                            eid_node = ensure_path(eids_node, [str(eid)])
                            set(eid_node, "AXIAL", number(line, 62, 13))
                            set(eid_node, "TORQUE", number(line, 76, 13))
                        if len(line) > 96 and line[95] != " ":
                            eid = int(number(line, 89,8))
                            eid_node = ensure_path(eids_node, [str(eid)])
                            set(eid_node, "AXIAL", number(line, 98, 13))
                            set(eid_node, "TORQUE", number(line, 112, 13))

                elif "F O R   E L E M E N T   T Y P E   E L A S 1" in line:
                    eids_node = ensure_path(root, prefix + ["ELAS1FORCES","EID"])
                    get_next_line()
                    get_next_line()
                    while True:
                        line = get_next_line()
                        if line.strip().startswith("---") or len(line.strip()) == 0:
                            break
                        else:
                            for element_col in range(5):
                                start = 16 + element_col * 22
                                if len(line) > start+8 and line[start+7] != " ":
                                    eid = int(number(line, start+1, 8))
                                    set(eids_node, str(eid), number(line, start + 10, 13))


            elif "R E A L   E I G E N V A L U E S" in line:
                modes_node = ensure_path(root, ["REALEIGENVALUES","MODE"])
                line = get_next_line()
                buckling = "buckling" in line
                get_next_line()
                get_next_line()
                if buckling:
                    get_next_line()
                    get_next_line()
                
                while True:
                    line = get_next_line()
                    if line.strip().startswith("---") or len(line.strip()) == 0:
                        break
                    if buckling:
                        mode = int(number(line, 39, 8))
                        mode_node = ensure_path(modes_node, [str(mode)])
                        eigenvalue = number(line, 62, 13)
                        set(mode_node, "EIGENVALUE", eigenvalue)
                    else:
                        mode = int(number(line, 2, 8))
                        mode_node = ensure_path(modes_node, [str(mode)])
                        eigenvalue = number(line, 25, 13)
                        cycles = number(line, 65, 13)
                        set(mode_node, "EIGENVALUE", eigenvalue)
                        set(mode_node, "CYCLES", cycles)
                    

        return root


    def write_structure_dense(self, file, tree_node, prefix="", parent_key=""):
        # Start at the root
        if tree_node is None:
            tree_node = self.parsed_f06

        is_first = True
        for key, value in tree_node.items():
            # Only show the first GID and EID as an example because there could be a lot.
            if (not is_first) and (parent_key == "GID" \
                                or parent_key == "EID" \
                                or parent_key == "MODE"):
                file.write(prefix + "...\n")
                break
            is_first = False

            if isinstance(value, dict):
                self.write_structure_dense(file, value, prefix + str(key) + "/", key)
            else:
                file.write(prefix + str(key) + "\n")


    def dump(self, file, tree_node=None, prefix="", parent_key=""):
        # Start at the root
        if tree_node is None:
            tree_node = self.parsed_f06

        for key, value in tree_node.items():
            if isinstance(value, dict):
                self.dump(file, value, prefix + str(key) + "/", key)
            else:
                file.write(f"{prefix}{key} = {value}\n")



    def get_layer_0(self, path):
        # Get a value from the file unmolested.
        
        current_node = self.parsed_f06
       
        value = None

        for index, node in enumerate(path):

            if not isinstance(current_node, dict):
                # Fail if we reached the leaf before the end of the path.
                value = None
                break
            if not node in current_node:
                value = None
                break
            else:
                current_node = current_node[node]
                value = current_node

        return value


    def get_layer_1(self, path):
        # Get a value from layer 0 and:
        # - Return 0.0 for missing data in cases where it logically means 0.0.

        value = self.get_layer_0(path)

        if value is None:
            # Some types of missing node represent zero values.
            # But only if the block is present.
            
            # /SC/#/SPCFORCES/GID/#/##
            #                     ^--- gid not present.
            if len(path) == 6 \
            and path[0] == "SC" \
            and path[2] in("DISPLACEMENTS", "SPCFORCES", "MPCFORCES", "APPLIEDFORCES") \
            and path[3] == "GID" \
            and path[5] in("TX","TY","TZ","RX","RY","RZ"):
                if self.get_layer_0(path[0:4]) is not None:
                    value = 0.0

            # /SC,MODE/#/GPFORCES/GID/#/#####/##
            #                             ^--- force type not present.
            elif len(path) == 7 \
            and path[0] in("SC","MODE") \
            and path[2] == "GPFORCE" \
            and path[3] == "GID" \
            and path[5] in("APPLIED", "SPC", "MPC", "INERTIA") \
            and path[6] in("TX","TY","TZ","RX","RY","RZ"):
                if self.get_layer_0(path[0:5]) is not None:
                    value = 0.0

        return value


    def get_layer_2(self, path, output_file : TextIOWrapper):
        # Get a value from layer 1 and:
        # - Write a message if it doesn't exist.
        
        value = self.get_layer_1(path)

        if value is None:
            output_file.write(f"{INDENT * 2}No value at: {"/".join(path)}\n")

        return value


    def get_layer_3(self, path, gp_transforms, shell_angles, output_file : TextIOWrapper):
        # Get a value from layer 2 and optionally:
        # - Transform vectors at grid points according to the supplied transformation matrices.
        # - Transform shell stress/strain/force according to the supplied element rotation angles.

        def rotate_2D_rank2_tensor(xx, yy, xy, angle, shear_factor, component):
            if xx is None or yy is None or xy is None:
                return None
            match component:
                case "XX": return (xx + yy) / 2 + (xx - yy) / 2 * math.cos(2*angle) - xy/shear_factor * math.sin(2*angle)
                case "YY": return (xx + yy) / 2 - (xx - yy) / 2 * math.cos(2*angle) + xy/shear_factor * math.sin(2*angle)
                case "XY": return                ((xx - yy) / 2 * math.sin(2*angle) + xy/shear_factor * math.cos(2*angle)) * shear_factor

        
        # Transform displacement components
        if len(path) > 5 \
        and path[0] == "SC" \
        and (path[2] == "DISPLACEMENTS" or path[2] == "SPCFORCES") \
        and path[3] == "GID":
            gid = int(path[4])
            if gid in gp_transforms:
                # Get the 3-component displacement (translation or rotation) vector
                if path[5][0] == "T" or path[5][0] == "R":
                    x_path = path.copy(); x_path[5] = f"{path[5][0]}X"; x = self.get_layer_2(x_path, output_file)
                    y_path = path.copy(); y_path[5] = f"{path[5][0]}Y"; y = self.get_layer_2(y_path, output_file)
                    z_path = path.copy(); z_path[5] = f"{path[5][0]}Z"; z = self.get_layer_2(z_path, output_file)

                    # Transform it but only calculate the requested component
                    if path[5][1] == "X": component = 0
                    if path[5][1] == "Y": component = 1
                    if path[5][1] == "Z": component = 2
                    row = gp_transforms[gid][component]
                    if x is None or y is None or z is None:
                        result = None
                    else:
                        result = row[0] * x + row[1] * y + row[2] * z

        # Transform shell stress, strain, and engineering forces

        if len(path) > 6 \
        and path[0] == "SC" \
        and path[2] == "SHELLSTRESSES" \
        and path[3] == "EID" \
        and path[5] == "CORNER":
            eid = int(path[4])
            if eid in shell_angles:
                corner = int(path[6])
                angle = shell_angles[eid][corner]
                if len(path) > 7 and (path[7] == "YZ" or path[7] == "ZX"):
                    # Transverse shear stress:
                    # SC/#/SHELLSTRESSES/EID/#/CORNER/#/YZ,ZX
                    x_path = path.copy(); x_path[7] = "ZX"; x = self.get_layer_2(x_path, output_file)
                    y_path = path.copy(); y_path[7] = "YZ"; y = self.get_layer_2(y_path, output_file)
                    if x is None or y is None:
                        result = None
                    elif path[7] == "ZX":
                        result = x * math.cos(angle) - y * math.sin(angle)
                    else:
                        result = x * math.sin(angle) + y * math.cos(angle)
                elif len(path) > 8 and (path[8] == "XX" or path[8] == "YY" or path[8] == "XY"):
                    # In-layer stress:
                    # SC/#/SHELLSTRESSES/EID/#/CORNER/#/Z#/XX,YY,XY
                    xx_path = path.copy(); xx_path[8] = "XX"; xx = self.get_layer_2(xx_path, output_file)
                    yy_path = path.copy(); yy_path[8] = "YY"; yy = self.get_layer_2(yy_path, output_file)
                    xy_path = path.copy(); xy_path[8] = "XY"; xy = self.get_layer_2(xy_path, output_file)
                    result = rotate_2D_rank2_tensor(xx, yy, xy, angle, 1, path[8])
                elif len(path) > 8 and path[8] == "PRINCIPALANGLE":
                    result = self.get_layer_2(path, output_file) + angle

        if len(path) > 6 \
        and path[0] == "SC" \
        and path[2] == "SHELLSTRAINS" \
        and path[3] == "EID" \
        and path[5] == "CORNER":
            eid = int(path[4])
            if eid in shell_angles:
                corner = int(path[6])
                angle = shell_angles[eid][corner]
                if len(path) > 7 and (path[7] == "YZ" or path[7] == "ZX"):
                    # Transverse shear strain:
                    # SC/#/SHELLSTRAINS/EID/#/CORNER/#/YZ,ZX
                    x_path = path.copy(); x_path[7] = "ZX"; x = self.get_layer_2(x_path, output_file)
                    y_path = path.copy(); y_path[7] = "YZ"; y = self.get_layer_2(y_path, output_file)
                    if x is None or y is None:
                        result = None
                    elif path[7] == "ZX":
                        result = x * math.cos(angle) - y * math.sin(angle)
                    else:
                        result = x * math.sin(angle) + y * math.cos(angle)
                elif len(path) > 8 and (path[8] == "XX" or path[8] == "YY" or path[8] == "XY"):
                    # In-layer strain:
                    # SC/#/SHELLSTRAINS/EID/#/CORNER/#/Z#/XX,YY,XY
                    xx_path = path.copy(); xx_path[8] = "XX"; xx = self.get_layer_2(xx_path, output_file)
                    yy_path = path.copy(); yy_path[8] = "YY"; yy = self.get_layer_2(yy_path, output_file)
                    xy_path = path.copy(); xy_path[8] = "XY"; xy = self.get_layer_2(xy_path, output_file)
                    result = rotate_2D_rank2_tensor(xx, yy, xy, angle, 2, path[8])
                elif len(path) > 8 and path[8] == "PRINCIPALANGLE":
                    result = self.get_layer_2(path, output_file) + angle

        if len(path) > 6 \
        and path[0] == "SC" \
        and path[2] == "SHELLFORCES" \
        and path[3] == "EID" \
        and path[5] == "CORNER":
            eid = int(path[4])
            if eid in shell_angles:
                corner = int(path[6])
                angle = shell_angles[eid][corner]
                if len(path) > 7 and (path[7] == "QX" or path[7] == "QY"):
                    # Transverse shear force resultant:
                    # SC/#/SHELLFORCES/EID/#/CORNER/#/QX,QY
                    x_path = path.copy(); x_path[7] = "QX"; x = self.get_layer_2(x_path, output_file)
                    y_path = path.copy(); y_path[7] = "QY"; y = self.get_layer_2(y_path, output_file)
                    if x is None or y is None:
                        result = None
                    elif path[7] == "QX":
                        result = x * math.cos(angle) - y * math.sin(angle)
                    else:
                        result = x * math.sin(angle) + y * math.cos(angle)
                elif len(path) > 7 and (path[7] == "NXX" or path[7] == "NYY" or path[7] == "NXY"):
                    # In-layer force resultants:
                    # SC/#/SHELLFORCES/EID/#/CORNER/#/NXX,NYY,NXY
                    xx_path = path.copy(); xx_path[7] = "NXX"; xx = self.get_layer_2(xx_path, output_file)
                    yy_path = path.copy(); yy_path[7] = "NYY"; yy = self.get_layer_2(yy_path, output_file)
                    xy_path = path.copy(); xy_path[7] = "NXY"; xy = self.get_layer_2(xy_path, output_file)
                    result = rotate_2D_rank2_tensor(xx, yy, xy, angle, 1, path[7][-2:])
                elif len(path) > 7 and (path[7] == "MXX" or path[7] == "MYY" or path[7] == "MXY"):
                    # Moment resultants:
                    # SC/#/SHELLFORCES/EID/#/CORNER/#/MXX,MYY,MXY
                    xx_path = path.copy(); xx_path[7] = "MXX"; xx = self.get_layer_2(xx_path, output_file)
                    yy_path = path.copy(); yy_path[7] = "MYY"; yy = self.get_layer_2(yy_path, output_file)
                    xy_path = path.copy(); xy_path[7] = "MXY"; xy = self.get_layer_2(xy_path, output_file)
                    result = rotate_2D_rank2_tensor(xx, yy, xy, angle, 1, path[7][-2:])

        try:
            return result
        except NameError:
            # No change
            return self.get_layer_2(path, output_file)
            

    def get_layer_4(self, path, gp_transforms, shell_angles, gp_coordinates, output_file : TextIOWrapper):
        # Get a value from layer 3 and optionally:
        # - ZMID for shell midsurface
        # - MXORIGIN, MYORIGIN, MZORIGIN for moment about the origin from SPCFORCES and MPCFORCES

        if len(path) > 7 \
        and path[0] == "SC" \
        and (path[2] == "SHELLSTRESSES" or path[2] == "SHELLSTRAINS") \
        and path[3] == "EID" \
        and path[5] == "CORNER" \
        and path[7] == "ZMID":

            z1_path = path.copy(); z1_path[7] = "Z1"; z1 = self.get_layer_3(z1_path, gp_transforms, shell_angles, output_file)
            z2_path = path.copy(); z2_path[7] = "Z2"; z2 = self.get_layer_3(z2_path, gp_transforms, shell_angles, output_file)
            if z1 is None or z2 is None:
                return None
            else:
                return (z1 + z2) / 2

        elif len(path) > 5 \
        and path[0] == "SC" \
        and (path[2] == "SPCFORCES" or path[2] == "MPCFORCES") \
        and path[3] == "GID" \
        and (path[5] == "MXORIGIN" or path[5] == "MYORIGIN" or path[5] == "MZORIGIN"):

            fx_path = path.copy(); fx_path[5] = "TX"
            fx = self.get_layer_3(fx_path, gp_transforms, shell_angles, output_file)
            fy_path = path.copy(); fy_path[5] = "TY"
            fy = self.get_layer_3(fy_path, gp_transforms, shell_angles, output_file)
            fz_path = path.copy(); fz_path[5] = "TZ"
            fz = self.get_layer_3(fz_path, gp_transforms, shell_angles, output_file)
            mx_path = path.copy(); mx_path[5] = "RX"
            mx = self.get_layer_3(mx_path, gp_transforms, shell_angles, output_file)
            my_path = path.copy(); my_path[5] = "RY"
            my = self.get_layer_3(my_path, gp_transforms, shell_angles, output_file)
            mz_path = path.copy(); mz_path[5] = "RZ"
            mz = self.get_layer_3(mz_path, gp_transforms, shell_angles, output_file)

            gid = int(path[4])
           
            match path[5][1]:
                case "X": 
                    if mx is None or fy is None or fz is None:
                        moment = None
                    else:
                        moment = mx + gp_coordinates[gid][1] * fz - gp_coordinates[gid][2] * fy 
                case "Y":
                    if my is None or fz is None or fx is None:
                        moment = None
                    else:
                        moment = my + gp_coordinates[gid][2] * fx - gp_coordinates[gid][0] * fz
                case "Z":
                    if mz is None or fx is None or fy is None:
                        moment = None
                    else:
                        moment = mz + gp_coordinates[gid][0] * fy - gp_coordinates[gid][1] * fx

            return moment

        else:

            return self.get_layer_3(path, gp_transforms, shell_angles, output_file)


    def get_layer_5(self, path, gp_transforms, shell_angles, gp_coordinates, gid_to_corners, output_file : TextIOWrapper):
        # Get a value from layer 4 and optionally:
        # - Node averaging
        
        if (len(path) > 5
                and path[0] == "SC"
                and path[2] in ("SHELLSTRESSES", "SHELLSTRAINS", "SHELLFORCES",
                                "SOLIDSTRESSES", "SOLIDSTRAINS")
                and path[3] == "GID"):
            # Eg: SC/1/SHELLSTRESSES/GID/123/Z1/XX
            gid = path[4]
            rest = path[5:]

            if gid not in gid_to_corners:
                output_file.write(f"{INDENT * 2}GID {gid} not found in reverse lookup. Available GIDs:\n")
                output_file.write(f"{INDENT * 2}")
                for available_gid in gid_to_corners.keys():
                    output_file.write(f"{available_gid}\t")
                output_file.write(f"\n")
                return None

            total   = 0.0
            count   = 0

            output_file.write(f"{INDENT * 2}Node averaging from element values:\n")
            for eid, corner in gid_to_corners[gid]:
                element_path = [path[0], path[1], path[2], "EID", eid, "CORNER", corner] + rest
                value = self.get_layer_4(element_path, gp_transforms, shell_angles, gp_coordinates, output_file)
                output_file.write(f"{INDENT * 3}{"/".join(element_path)} =\t{value}\n")
                if value is not None:
                    total += value
                    count += 1
                else:
                    # gid_to_corners might be inconsistent with the data.
                    output_file.write(f"{INDENT * 2}Strangely no value.\n")
                    return None

            if count == 0:
                output_file.write(f"{INDENT * 2}No elements with data found for GID {gid}.\n")
                return None

            return total / count

        else:

            return self.get_layer_4(path, gp_transforms, shell_angles, gp_coordinates, output_file)


    def get_layer_6(self, path, gp_transforms, shell_angles, gp_coordinates, gid_to_corners, output_file : TextIOWrapper):
        # Get a value from layer 5 and:
        # - Path can describe multiple values.
        
        def expand_lists(path, expanded_paths=None):
            # Convert eg: 
            #
            # ["A","B","1,2,3","D"]
            #   to
            # [["A","B","1","D"], ["A","B","2","D"], ["A","B","3","D"]]
            #
            # and
            #
            # ["2"-"7"]
            #   to
            # ["2","3","4","5","6","7"]
            
            # Initialize inside function because same list persists across calls otherwise.
            if expanded_paths is None:
                expanded_paths = []

            for i, element in enumerate(path):
                if "-" in str(element):
                    first = int(element.split("-")[0])
                    last = int(element.split("-")[1])
                    for value in range(first, last+1):
                        expand_lists(path[:i] + [str(value)] + path[i+1:], expanded_paths)
                    return expanded_paths
                elif "," in str(element):
                    for value in element.split(","):
                        expand_lists(path[:i] + [value.strip()] + path[i+1:], expanded_paths)
                    return expanded_paths
            expanded_paths.append(path)
            return expanded_paths
        
        single_paths = expand_lists(path)

        result = []

        for single_path in single_paths:
            result.append(self.get_layer_5(single_path, gp_transforms, shell_angles, gp_coordinates, gid_to_corners, output_file))

        return result
