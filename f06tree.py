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

        elif "E L E M E N T   S T R E S S E S   I N   M A T E R I A L   C O O R D I N A T E   S Y S T E M" in line:
            line = get_next_line()
            if "F O R   E L E M E N T   T Y P E   H E X A" in line \
            or "F O R   E L E M E N T   T Y P E   P E N T A" in line \
            or "F O R   E L E M E N T   T Y P E   T E T R A" in line:
                subcase = int(number(peek_line_delta(-3), 21, 8))
                eids_node = ensure_path(root, ["SC", subcase, "STRESS_SOLID","EID"])
                get_next_line()
                get_next_line()
                corner = 0
                while True:
                    line = get_next_line()
                    if line.strip().startswith("---") or len(line.strip()) == 0:
                        break
                    if line[11:11+6] == "CENTER":
                        eid = int(number(line, 2,8))
                        eid_node = ensure_path(eids_node, [eid])
                        corner =0
                        corner_node = ensure_path(eid_node, ["CENTER"])
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
            line = get_next_line()
            if "F O R   E L E M E N T   T Y P E   H E X A" in line \
            or "F O R   E L E M E N T   T Y P E   P E N T A" in line \
            or "F O R   E L E M E N T   T Y P E   T E T R A" in line:
                subcase = int(number(peek_line_delta(-3), 21, 8))
                eids_node = ensure_path(root, ["SC", subcase, "STRAIN_SOLID","EID"])
                get_next_line()
                get_next_line()
                corner = 0
                while True:
                    line = get_next_line()
                    if line.strip().startswith("---") or len(line.strip()) == 0:
                        break
                    if line[11:11+6] == "CENTER":
                        eid = int(number(line, 2,8))
                        eid_node = ensure_path(eids_node, [eid])
                        corner =0
                        corner_node = ensure_path(eid_node, ["CENTER"])
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
            line = get_next_line()
            if "F O R   E L E M E N T   T Y P E   Q U A D 4" in line \
            or "F O R   E L E M E N T   T Y P E   Q U A D 8" in line:
                subcase = int(number(peek_line_delta(-3), 21, 8))
                eids_node = ensure_path(root, ["SC", subcase, "STRESS_QUAD","EID"])
                get_next_line()
                get_next_line()
                get_next_line()
                corner = 0
                while True:
                    line = get_next_line()
                    if line.strip().startswith("---"):
                        break
                    if line[11:11+6] == "CENTER":
                        eid = int(number(line, 2,8))
                        eid_node = ensure_path(eids_node, [eid])
                        corner =0
                        corner_node = ensure_path(eid_node, ["CENTER"])
                    elif line[11:11+3] == "GRD":
                        corner += 1
                        corner_node = ensure_path(eid_node, ["CORNER", corner])
                    else:
                        # Skip the blank lines between corners
                        continue
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

    return root


def tree_get(parsed_f06, path):
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
        if (not is_first) and (parent_key == "GID" or parent_key == "EID" or parent_key == "CORNER"):
            file.write(prefix + "...\n")
            break
        is_first = False

        if isinstance(value, dict):
            write_structure_dense(value, file, prefix + str(key) + "/", key)
        else:
            file.write(prefix + str(key) + "\n")
