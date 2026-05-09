import io


def read_f06_tree(file_name):

    with open(file_name, 'r') as f:
        lines = f.readlines()

    root = {}

    line_no = 0

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
        line = lines[line_no]
        line_no += 1
        return line

    def peek_line_delta(delta):
        return lines[line_no - 1 + delta]

    def number(line, start, length):
        return float(line[start - 1:start - 1 + length].strip() or 0)

    while line_no <= len(lines) - 1:
        line = get_next_line()

        if "D I S P L A C E M E N T S" in line:
            subcase = int(number(peek_line_delta(-2), 21, 8))
            gids_node = ensure_path(root, ["SC", subcase, "DISPLACEMENTS","GID"])
            get_next_line()
            get_next_line()
            get_next_line()
            while True:
                line = get_next_line()
                if line.strip().startswith("---") or len(line.strip()) == 0:
                    break
                gid = int(number(line, 8, 8))
                gid_node = ensure_path(gids_node, [gid])
                set(gid_node, "TX", number(line, 26, 13))
                set(gid_node, "TY", number(line, 40, 13))
                set(gid_node, "TZ", number(line, 54, 13))
                set(gid_node, "RX", number(line, 68, 13))
                set(gid_node, "RY", number(line, 82, 13))
                set(gid_node, "RZ", number(line, 96, 13))

        elif "S P C   F O R C E S" in line:
            subcase = int(number(peek_line_delta(-2), 21, 8))
            gids_node = ensure_path(root, ["SC", subcase, "SPCFORCES","GID"])
            get_next_line()
            get_next_line()
            get_next_line()
            while True:
                line = get_next_line()
                if line.strip().startswith("---") or len(line.strip()) == 0:
                    break
                gid = int(number(line, 8, 8))
                gid_node = ensure_path(gids_node, [gid])
                set(gid_node, "TX", number(line, 26, 13))
                set(gid_node, "TY", number(line, 40, 13))
                set(gid_node, "TZ", number(line, 54, 13))
                set(gid_node, "RX", number(line, 68, 13))
                set(gid_node, "RY", number(line, 82, 13))
                set(gid_node, "RZ", number(line, 96, 13))

        if "E I G E N V E C T O R" in line:
            subcase = 2
            mode = int(number(peek_line_delta(-2), 25, 8))
            gids_node = ensure_path(root, ["SC", subcase, "MODE", mode, "EIGENVECTOR", "GID"])
            get_next_line()
            get_next_line()
            get_next_line()
            while True:
                line = get_next_line()
                if line.strip().startswith("---") or len(line.strip()) == 0:
                    break
                gid = int(number(line, 8, 8))
                gid_node = ensure_path(gids_node, [gid])
                set(gid_node, "TX", number(line, 26, 13))
                set(gid_node, "TY", number(line, 40, 13))
                set(gid_node, "TZ", number(line, 54, 13))
                set(gid_node, "RX", number(line, 68, 13))
                set(gid_node, "RY", number(line, 82, 13))
                set(gid_node, "RZ", number(line, 96, 13))

        elif "E L E M E N T   S T R E S S E S   I N   M A T E R I A L   C O O R D I N A T E   S Y S T E M" in line:
            subcase = int(number(peek_line_delta(-2), 21, 8))
            line = get_next_line()
            if "F O R   E L E M E N T   T Y P E   H E X A" in line \
            or "F O R   E L E M E N T   T Y P E   P E N T A" in line \
            or "F O R   E L E M E N T   T Y P E   T E T R A" in line:
                eids_node = ensure_path(root, ["SC", subcase, "SOLIDSTRESSES","EID"])
                get_next_line()
                get_next_line()
                corner = None
                while True:
                    line = get_next_line()
                    if line.strip().startswith("---") or len(line.strip()) == 0:
                        break
                    if line[11:11+6] == "CENTER":
                        eid = int(number(line, 2,8))
                        eid_node = ensure_path(eids_node, [eid])
                        corner =0
                    elif line[11:11+3] == "GRD":
                        corner += 1
                    corner_node = ensure_path(eid_node, ["CORNER", corner])
                    set(corner_node, "XX", number(line, 29, 13))
                    set(corner_node, "YY", number(line, 43, 13))
                    set(corner_node, "ZZ", number(line, 57, 13))
                    set(corner_node, "XY", number(line, 71, 13))
                    set(corner_node, "YZ", number(line, 85, 13))
                    set(corner_node, "ZX", number(line, 99, 13))
                    set(corner_node, "VM", number(line, 113, 13)) # todo might be max. shear. Read column header to decide.

        elif "E L E M E N T   S T R A I N S   I N   M A T E R I A L   C O O R D I N A T E   S Y S T E M" in line:
            subcase = int(number(peek_line_delta(-2), 21, 8))
            line = get_next_line()
            if "F O R   E L E M E N T   T Y P E   H E X A" in line \
            or "F O R   E L E M E N T   T Y P E   P E N T A" in line \
            or "F O R   E L E M E N T   T Y P E   T E T R A" in line:
                eids_node = ensure_path(root, ["SC", subcase, "SOLIDSTRAINS","EID"])
                get_next_line()
                get_next_line()
                corner = None
                while True:
                    line = get_next_line()
                    if line.strip().startswith("---") or len(line.strip()) == 0:
                        break
                    if line[11:11+6] == "CENTER":
                        eid = int(number(line, 2,8))
                        eid_node = ensure_path(eids_node, [eid])
                        corner =0
                    elif line[11:11+3] == "GRD":
                        corner += 1
                    corner_node = ensure_path(eid_node, ["CORNER", corner])
                    set(corner_node, "XX", number(line, 29, 13))
                    set(corner_node, "YY", number(line, 43, 13))
                    set(corner_node, "ZZ", number(line, 57, 13))
                    set(corner_node, "XY", number(line, 71, 13))
                    set(corner_node, "YZ", number(line, 85, 13))
                    set(corner_node, "ZX", number(line, 99, 13))
                    set(corner_node, "VM", number(line, 113, 13)) # todo might be max. shear. Read column header to decide.

        elif "E L E M E N T   S T R E S S E S   I N   L O C A L   E L E M E N T   C O O R D I N A T E   S Y S T E M" in line:
            subcase = int(number(peek_line_delta(-2), 21, 8))
            line = get_next_line()
            if "F O R   E L E M E N T   T Y P E   Q U A D 4" in line \
            or "F O R   E L E M E N T   T Y P E   Q U A D 8" in line:
                eids_node = ensure_path(root, ["SC", subcase, "SHELLSTRESSES","EID"])
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
                        eid_node = ensure_path(eids_node, [eid])
                        corner = 0
                    elif line[11:11+3] == "GRD":
                        corner += 1
                    else:
                        # Skip the blank lines between corners
                        continue
                    corner_node = ensure_path(eid_node, ["CORNER", corner])
                    set(corner_node, "ZX", number(line, 121, 12))
                    set(corner_node, "YZ", number(line, 134, 12))
                    z1_node = ensure_path(corner_node, ["Z1"])
                    set(z1_node, "XX", number(line, 35, 12))
                    set(z1_node, "YY", number(line, 48, 12))
                    set(z1_node, "XY", number(line, 61, 12))
                    line = get_next_line()
                    z2_node = ensure_path(corner_node, ["Z2"])
                    set(z2_node, "XX", number(line, 35, 12))
                    set(z2_node, "YY", number(line, 48, 12))
                    set(z2_node, "XY", number(line, 61, 12))

            elif "F O R   E L E M E N T   T Y P E   T R I A 3" in line:
                eids_node = ensure_path(root, ["SC", subcase, "SHELLSTRESSES","EID"])
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
                        eid_node = ensure_path(eids_node, [eid])
                        corner =0
                        corner_node = ensure_path(eid_node, ["CORNER", corner])
                        set(corner_node, "ZX", number(line, 125, 12))
                        set(corner_node, "YZ", number(line, 138, 12))
                        z1_node = ensure_path(corner_node, ["Z1"])
                        set(z1_node, "XX", number(line, 38, 12))
                        set(z1_node, "YY", number(line, 51, 12))
                        set(z1_node, "XY", number(line, 64, 12))
                        line = get_next_line()
                        z2_node = ensure_path(corner_node, ["Z2"])
                        set(z2_node, "XX", number(line, 38, 12))
                        set(z2_node, "YY", number(line, 51, 12))
                        set(z2_node, "XY", number(line, 64, 12))


        elif "E L E M E N T   S T R A I N S   I N   L O C A L   E L E M E N T   C O O R D I N A T E   S Y S T E M" in line:
            subcase = int(number(peek_line_delta(-2), 21, 8))
            line = get_next_line()
            if "F O R   E L E M E N T   T Y P E   Q U A D 4" in line \
            or "F O R   E L E M E N T   T Y P E   Q U A D 8" in line:
                eids_node = ensure_path(root, ["SC", subcase, "SHELLSTRAINS","EID"])
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
                        eid_node = ensure_path(eids_node, [eid])
                        corner = 0
                    elif line[11:11+3] == "GRD":
                        corner += 1
                    else:
                        # Skip the blank lines between corners
                        continue
                    corner_node = ensure_path(eid_node, ["CORNER", corner])
                    set(corner_node, "ZX", number(line, 121, 12))
                    set(corner_node, "YZ", number(line, 134, 12))
                    z1_node = ensure_path(corner_node, ["Z1"])
                    set(z1_node, "XX", number(line, 35, 12))
                    set(z1_node, "YY", number(line, 48, 12))
                    set(z1_node, "XY", number(line, 61, 12))
                    line = get_next_line()
                    z2_node = ensure_path(corner_node, ["Z2"])
                    set(z2_node, "XX", number(line, 35, 12))
                    set(z2_node, "YY", number(line, 48, 12))
                    set(z2_node, "XY", number(line, 61, 12))

            elif "F O R   E L E M E N T   T Y P E   T R I A 3" in line:
                eids_node = ensure_path(root, ["SC", subcase, "SHELLSTRAINS","EID"])
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
                        eid_node = ensure_path(eids_node, [eid])
                        corner =0
                        corner_node = ensure_path(eid_node, ["CORNER", corner])
                        set(corner_node, "ZX", number(line, 125, 12))
                        set(corner_node, "YZ", number(line, 138, 12))
                        z1_node = ensure_path(corner_node, ["Z1"])
                        set(z1_node, "XX", number(line, 38, 12))
                        set(z1_node, "YY", number(line, 51, 12))
                        set(z1_node, "XY", number(line, 64, 12))
                        line = get_next_line()
                        z2_node = ensure_path(corner_node, ["Z2"])
                        set(z2_node, "XX", number(line, 38, 12))
                        set(z2_node, "YY", number(line, 51, 12))
                        set(z2_node, "XY", number(line, 64, 12))


        elif "S T R E S S E S   I N   L A Y E R E D   C O M P O S I T E   E L E M E N T S" in line:
            subcase = int(number(peek_line_delta(-2), 21, 8))
            get_next_line()
            get_next_line()
            get_next_line()
            line = get_next_line()
            if "F O R   E L E M E N T   T Y P E   Q U A D 4" in line \
            or "F O R   E L E M E N T   T Y P E   Q U A D 8" in line \
            or "F O R   E L E M E N T   T Y P E   T R I A 3" in line:
                eids_node = ensure_path(root, ["SC", subcase, "COMPOSITESTRESSES","EID"])
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
                        eid_node = ensure_path(eids_node, [eid])
                    elif line.strip == "":
                        # Skip the blank lines between elements
                        continue
                    ply_num = int(number(line, 11,5))
                    ply_node = ensure_path(eid_node, ["PLY", ply_num])
                    # Stress component names are numbers because it's hard to identify them as strings!
                    set(ply_node, 11, number(line, 17, 12))
                    set(ply_node, 22, number(line, 30, 12))
                    set(ply_node, 12, number(line, 43, 12))
                    set(ply_node, 13, number(line, 59, 12))
                    set(ply_node, 23, number(line, 73, 12))


        elif "E L E M E N T   E N G I N E E R I N G   F O R C E S" in line:
            subcase = int(number(peek_line_delta(-2), 21, 8))
            line = get_next_line()
            if "F O R   E L E M E N T   T Y P E   Q U A D 4" in line \
            or "F O R   E L E M E N T   T Y P E   Q U A D 8" in line \
            or "F O R   E L E M E N T   T Y P E   T R I A 3" in line:
                eids_node = ensure_path(root, ["SC", subcase, "SHELLFORCES","EID"])
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
                    else:
                        eid = int(number(line, 2,8))
                        eid_node = ensure_path(eids_node, [eid])
                        corner =0
                    corner_node = ensure_path(eid_node, ["CORNER", corner])
                    set(corner_node, "NXX", number(line, 26, 13))
                    set(corner_node, "NYY", number(line, 40, 13))
                    set(corner_node, "NXY", number(line, 54, 13))
                    set(corner_node, "MXX", number(line, 68, 13))
                    set(corner_node, "MYY", number(line, 82, 13))
                    set(corner_node, "MXY", number(line, 96, 13))
                    set(corner_node, "QX", number(line, 110, 13))
                    set(corner_node, "QY", number(line, 124, 13))


        elif "R E A L   E I G E N V A L U E S" in line:
            subcase = 2
            modes_node = ensure_path(root, ["SC", subcase, "REALEIGENVALUES","MODE"])
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
                    eigenvalue = number(line, 62, 13)
                    mode_node = ensure_path(modes_node, [mode])
                    set(mode_node, "EIGENVALUE", eigenvalue)
                else:
                    mode = int(number(line, 2, 8))
                    cycles = number(line, 65, 13)
                    mode_node = ensure_path(modes_node, [mode])
                    set(mode_node, "CYCLES", cycles)
                

    return root


def tree_get(parsed_f06, path, output_file : io.TextIOWrapper):
    current_node = parsed_f06
   
    value = None

    for index, node in enumerate(path):

        # convert numbers to int
        if node[0].isdigit():
            node =  int(node)

        if not isinstance(current_node, dict):
            # Fail if we reached the leaf before the end of the path.
            value = None
            break

        if not node in current_node:
            # Some types of missing node represent zero values.
            
            # /SC/#/SPCFORCES/GID/#/##
            #                     ^--- not present.
            if index == 4 and len(path) == 6 and path[0] == "SC" and path[2] == "SPCFORCES" and path[3] == "GID":
                value = 0.0
                break
            else:
                # Otherwise, fail if a node in the path isn't present.
                value = None
                break
        else:

            current_node = current_node[node]

            if isinstance(current_node, float):
                # Reached leaf.
                value = current_node

    if value is None:
        output_file.write(f"No value at path: {"/".join(path)}\n")
        output_file.write(f"Available paths existing in f06 file:\n")
        write_structure_dense(parsed_f06, output_file)

    return value
    

def write_tree(parsed_f06, file, indent=0, parent_key=""):
    for key, value in parsed_f06.items():
        if isinstance(value, dict):
            file.write("  " * indent + str(key) + "\n")
            print_tree(value, file, indent + 1, key)
        else:
            file.write("  " * indent + str(key) + " = " + str(value) + "\n")


def write_structure_dense(parsed_f06, file, prefix="", parent_key=""):
    is_first = True
    for key, value in parsed_f06.items():
        # Only show the first GID and EID as an example because there could be a lot.
        if (not is_first) and (parent_key == "GID" \
                            or parent_key == "EID" \
                            or parent_key == "MODE"):
            file.write(prefix + "...\n")
            break
        is_first = False

        if isinstance(value, dict):
            write_structure_dense(value, file, prefix + str(key) + "/", key)
        else:
            file.write(prefix + str(key) + "\n")
