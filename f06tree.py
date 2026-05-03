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

    return root


def tree_get(tree, path_string : str):
    current_node = tree
    
    # Convert / delimited string to list
    path = path_string.split("/")

    # convert numbers to int
    path_2 = []
    for node in path:
        if node[0].isdigit():
            path_2.append(int(node))
        else:
            path_2.append(node)

    for node in path_2:
        if not node in current_node:
            return None
        current_node = current_node[node]
    return current_node
    

def write_tree(tree, file, indent=0, parent_key=""):
    for key, value in tree.items():
        if isinstance(value, dict):
            file.write("  " * indent + str(key) + "\n")
            print_tree(value, file, indent + 1, key)
        else:
            file.write("  " * indent + str(key) + " = " + str(value) + "\n")

def write_structure_dense(tree, file, prefix="", parent_key=""):
    is_first = True
    for key, value in tree.items():
        # Only show the first GID and EID as an example because there could be a lot.
        if (not is_first) and (parent_key == "GID" or parent_key == "EID"):
            file.write(prefix + "...\n")
            break
        is_first = False

        file.write(prefix + str(key) + "\n")

        if isinstance(value, dict):
            write_structure_dense(value, file, prefix + str(key) + "/", key)
