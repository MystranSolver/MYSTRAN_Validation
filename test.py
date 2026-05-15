#!/usr/bin/env python3

import subprocess
import sys
import shutil
import os
import io
import math
from pathlib import Path
from f06csv_to_magic import f06csv_args_to_magic
from f06tree import read_f06_tree
from f06tree import tree_get
from f06tree import write_structure_dense

# Error messages with a code like ERROR 229606 are for bugs/corruption in the test suite.
# Error messages with explanations are for errors in test case definitions/usage.

INDENT = "  "

class Definition:
    def __init__(self):
        self.test_type = ""
        self.deck_filename = ""
        self.filter_string = ""
        self.operation = ""
        self.reference_value = 0.0
        self.threshold = 0.0
        self.comparison_type = "percent"
        self.tolerance = 0.0

    def tolerance_suffix(self):
        return "%" if self.comparison_type == "percent" else ""        

def read_definitions(definitions_path: Path) -> list[Definition]:

    def read_tolerance(field):
        nonlocal definition
        if "%" in field:
            definition.comparison_type = "percent"
        else:
            definition.comparison_type = "difference"
        definition.tolerance = float(field.replace("%",""))


    # Read a line for each test case definition
    definitions_str = definitions_path.read_text().splitlines()

    result = []
    
    for definition_str in definitions_str:
        definition_str = definition_str.strip()
        if definition_str == "":
            # Skip blank lines
            pass
        elif definition_str.startswith("#"):
            # Skip comments
            pass
        elif definition_str.startswith("INCLUDE"):
            # Include another definitions file
            filename = definition_str.split(" ")[1]
            include_path = definitions_path.parent / filename
            result += read_definitions(include_path)
        else:
            definition_fields_str = definition_str.split(";")
            definition_fields_str = [s.strip() for s in definition_fields_str]
            definition = Definition()
            definition.test_type = definition_fields_str[0]
            definition.deck_filename = definition_fields_str[1]
            definition.filter_string = definition_fields_str[2]
            match definition.test_type:
                case "mys" | "msc":
                    definition.threshold = float(definition_fields_str[3])
                    read_tolerance(definition_fields_str[4])
                case "pth":
                    definition.operation = definition_fields_str[3]
                    definition.reference_value = definition_fields_str[4]
                    read_tolerance(definition_fields_str[5])


            result.append(definition)
    
    return result


def clear_fails_directory(path: Path) -> bool:
    
    # Safety check to avoid clearing the wrong directory.
    if path.stem != "fails":
        print("ERROR 235476")
        sys.exit(1)

    # Create fails directory if it doesn't exist.
    path.mkdir(exist_ok=True)

    if not os.path.isdir(path):
        print("ERROR 222476")
        sys.exit(1)

    # Delete only the expected file type (F06) to reduce blast radius of a bug.
    for item_path in path.rglob("*.F06"):
        if item_path.is_file():
            item_path.unlink()
    
    return True


def clear_working_directory(path: Path) -> bool:
    
    # Safety check to avoid clearing the wrong directory.
    if path.stem != "working":
        print("ERROR 911875")
        return False

    # Create working directory if it doesn't exist.
    path.mkdir(exist_ok=True)

    if not os.path.isdir(path):
        print("ERROR 911279")
        sys.exit(1)

    for item in os.listdir(path):
        item_path = path / item
        # Don't delete subdirectories or symlinks to reduce blast radius of a bug.
        if item_path.is_file():
            item_path.unlink()
    
    return True


def run_program(program_path: Path,
                args: list[str],
                working_dir: Path,
                our_output: io.TextIOWrapper,
                std_output: io.TextIOWrapper) -> int:

    name = program_path.stem

    cmd = [str(program_path)] 
    cmd = cmd + args

    our_output.write(f"{program_path}")
    for arg in args:
        our_output.write(f" {arg}")
    our_output.write("\n")
    our_output.flush()

    try:
        subprocess.run(cmd, check=True, text=True,
                       cwd=working_dir,
                       stdout=std_output,
                       stderr=std_output)
        
    except subprocess.CalledProcessError as e:
        return e.returncode

    return 0
        

def test_f06csv(root_dir: Path,
                working_dir: Path,
                test_f06_path: Path,
                output_file: io.TextIOWrapper,
                test_case: Definition) -> int:

    if test_case.test_type == "mys":
        reference_f06_path = (root_dir / "reference_mystran" / test_case.deck_filename).with_suffix(".F06").resolve()
    elif test_case.test_type == "msc":
        reference_f06_path = (root_dir / "reference_msc" / test_case.deck_filename).with_suffix(".f06").resolve()

    # Convert f06csv args to f06magic
    extraction_name = test_case.filter_string
    extraction_lines = f06csv_args_to_magic(test_case.filter_string, name=extraction_name)
    
    # Make script for f06magic
    script = f"""
[files]
test_file = \"{test_f06_path}\"
reference_file = \"{reference_f06_path}\"
{extraction_lines}
[[criteria]]
name = \"only criteria\"
    """
# todo max_ratio is not the same kind of test as percent. Even scaling by 100 can't make it the same.
    if test_case.comparison_type == "percent":
        script = script + f"""
max_ratio = {str(test_case.tolerance)}
threshold = {str(test_case.threshold)}
        """
    elif test_case.comparison_type == "difference":
        script = script + f"""
max_difference = {str(test_case.tolerance)}
        """
    else:
        print("ERROR 986251")
        sys.exit(1)
    
    script = script + f"""
[[comparison]]
name = \"{test_case.deck_filename}\"
reference_f06 = \"reference_file\"
test_f06 = \"test_file\"
extraction = \"{extraction_name}\"
criteria = \"only criteria\"
    """

    # Escape \ to \\ for TOML
    script = script.replace("\\", "\\\\")
    f06magic_script_path = working_dir / "f06magic_script.toml"
    with open(f06magic_script_path, "w") as script_file:
        script_file.write(script)

    args = [f06magic_script_path]

    # Run f06magic
    fail_count = run_program(root_dir / "f06magic.exe", args, working_dir, output_file, output_file)

    return fail_count



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


def read_gp_transforms(filepath: str) -> dict:

    # Example a line in the file:
    # 5, 0.8660254037844, 0, -0.5, 0, 1, 0, 0.5, 0, 0.8660254037844
    # First number is grid point. Other 6 are transformation matrix.

    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {}

    result = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        values = [v.strip() for v in line.split(',')]
        gid = int(values[0])
        floats = [float(v) for v in values[1:10]]
        result[gid] = [floats[0:3], floats[3:6], floats[6:9]]
    return result


def read_shell_angles(filepath: str) -> dict:

    # Example a line in the file:
    # 3, -0.785398163397448, -0.785398163397448, -0.785398163397448, -0.785398163397448, -0.785398163397448
    # The first number is elemend ID.
    # The 2nd to 6th numbers are angles to rotates the the shell stresses, strains, and engineering forces by.
    # The 1st angle is for the center value, angles 2-5 are for corners 1-4 respectively.
    # Only the center value is used for tria elements.

    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {}

    result = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        values = [v.strip() for v in line.split(',')]
        eid = int(values[0])
        result[eid] = [float(v) for v in values[1:7]]
    return result
        

def build_gid_to_corners(parsed_f06) -> dict:
    """Build a reverse lookup from GID to list of (EID, corner) pairs using
    corner GID numbers in SHELLSTRESSES, SHELLSTRAINS, and SHELLFORCES."""

    result: dict = {}

    subcases_node = parsed_f06.get("SC")
    if subcases_node is not None:
        for subcase_node in subcases_node.values():
            for block_type in ["SHELLSTRESSES", "SHELLSTRAINS", "SHELLFORCES"]:
                block_node = subcase_node.get(block_type)
                if block_node is not None:
                    eids_node = block_node["EID"]
                    for eid in eids_node.keys():
                        corners_node = eids_node[eid]["CORNER"]
                        for corner in corners_node.keys():
                            gid_int = corners_node[corner].get("GID")
                            # GID doesn't exist for corner 0 (center).
                            if gid_int is not None:
                                gid = str(gid_int)
                                # Make sure a list exists for this GID
                                if gid not in result:
                                    result[gid] = []
                                # Prevent duplicates from different blocks and subcases.
                                if (eid, corner) not in result[gid]:
                                    result[gid].append((eid, corner))

    return result


def rotate_2D_rank2_tensor(xx, yy, xy, angle, shear_factor, component):
    match component:
        case "XX": return (xx + yy) / 2 + (xx - yy) / 2 * math.cos(2*angle) - xy/shear_factor * math.sin(2*angle)
        case "YY": return (xx + yy) / 2 - (xx - yy) / 2 * math.cos(2*angle) + xy/shear_factor * math.sin(2*angle)
        case "XY": return                ((xx - yy) / 2 * math.sin(2*angle) + xy/shear_factor * math.cos(2*angle)) * shear_factor


def tree_get_layer_1(parsed_f06, path, output_file : io.TextIOWrapper):
    # Get a value from the parsed f06 file without any modification.
    
    value = tree_get(parsed_f06, path)

    if value is None:
        output_file.write(f"{INDENT * 2}No value at path: {"/".join(path)}\n")
        output_file.write(f"{INDENT * 2}Available paths existing in F06 file:\n")
        write_structure_dense(parsed_f06, output_file, f"{INDENT * 2}")

    return value


def tree_get_layer_2(parsed_f06, path, gp_transforms, shell_angles, output_file : io.TextIOWrapper):
    # Get a value from the f06 file with optional coordinate system transformations applied.
    #
    # If it's a kind that's stored in displacement coordinates and we have a 
    # transformation matrix available, then transform it to basic coordinates.
    #
    # If it's a shell stress, strain or engineering force and we have shell angles 
    # available then rotate it by those angles.

    result = tree_get_layer_1(parsed_f06, path, output_file)
    
    # Transform displacement components
    if len(path) > 5 \
    and path[0] == "SC" \
    and (path[2] == "DISPLACEMENTS" or path[2] == "SPCFORCES") \
    and path[3] == "GID":
        gid = int(path[4])
        if gid in gp_transforms:
            # Get the 3-component displacement (translation or rotation) vector
            if path[5][0] == "T":
                x_path = path.copy(); x_path[5] = "TX"; x = tree_get_layer_1(parsed_f06, x_path, output_file)
                y_path = path.copy(); y_path[5] = "TY"; y = tree_get_layer_1(parsed_f06, y_path, output_file)
                z_path = path.copy(); z_path[5] = "TZ"; z = tree_get_layer_1(parsed_f06, z_path, output_file)
            elif path[5][0] == "R":
                x_path = path.copy(); x_path[5] = "RX"; x = tree_get_layer_1(parsed_f06, x_path, output_file)
                y_path = path.copy(); y_path[5] = "RY"; y = tree_get_layer_1(parsed_f06, y_path, output_file)
                z_path = path.copy(); z_path[5] = "RZ"; z = tree_get_layer_1(parsed_f06, z_path, output_file)
            else:
                print("ERROR 672525")
                sys.exit(1)

            # Transform it but only calculate the requested component
            if path[5][1] == "X": component = 0
            if path[5][1] == "Y": component = 1
            if path[5][1] == "Z": component = 2
            row = gp_transforms[gid][component]
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
                x_path = path.copy(); x_path[7] = "ZX"; x = tree_get_layer_1(parsed_f06, x_path, output_file)
                y_path = path.copy(); y_path[7] = "YZ"; y = tree_get_layer_1(parsed_f06, y_path, output_file)
                if path[7] == "ZX":
                    result = x * math.cos(angle) - y * math.sin(angle)
                else:
                    result = x * math.sin(angle) + y * math.cos(angle)
            elif len(path) > 8 and (path[8] == "XX" or path[8] == "YY" or path[8] == "XY"):
                # In-layer stress:
                # SC/#/SHELLSTRESSES/EID/#/CORNER/#/Z#/XX,YY,XY
                xx_path = path.copy(); xx_path[8] = "XX"; xx = tree_get_layer_1(parsed_f06, xx_path, output_file)
                yy_path = path.copy(); yy_path[8] = "YY"; yy = tree_get_layer_1(parsed_f06, yy_path, output_file)
                xy_path = path.copy(); xy_path[8] = "XY"; xy = tree_get_layer_1(parsed_f06, xy_path, output_file)
                result = rotate_2D_rank2_tensor(xx, yy, xy, angle, 1, path[8])

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
                x_path = path.copy(); x_path[7] = "ZX"; x = tree_get_layer_1(parsed_f06, x_path, output_file)
                y_path = path.copy(); y_path[7] = "YZ"; y = tree_get_layer_1(parsed_f06, y_path, output_file)
                if path[7] == "ZX":
                    result = x * math.cos(angle) - y * math.sin(angle)
                else:
                    result = x * math.sin(angle) + y * math.cos(angle)
            elif len(path) > 8 and (path[8] == "XX" or path[8] == "YY" or path[8] == "XY"):
                # In-layer strain:
                # SC/#/SHELLSTRAINS/EID/#/CORNER/#/Z#/XX,YY,XY
                xx_path = path.copy(); xx_path[8] = "XX"; xx = tree_get_layer_1(parsed_f06, xx_path, output_file)
                yy_path = path.copy(); yy_path[8] = "YY"; yy = tree_get_layer_1(parsed_f06, yy_path, output_file)
                xy_path = path.copy(); xy_path[8] = "XY"; xy = tree_get_layer_1(parsed_f06, xy_path, output_file)
                result = rotate_2D_rank2_tensor(xx, yy, xy, angle, 2, path[8])

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
                x_path = path.copy(); x_path[7] = "QX"; x = tree_get_layer_1(parsed_f06, x_path, output_file)
                y_path = path.copy(); y_path[7] = "QY"; y = tree_get_layer_1(parsed_f06, y_path, output_file)
                if path[7] == "QX":
                    result = x * math.cos(angle) - y * math.sin(angle)
                else:
                    result = x * math.sin(angle) + y * math.cos(angle)
            elif len(path) > 7 and (path[7] == "NXX" or path[7] == "NYY" or path[7] == "NXY"):
                # In-layer force resultants:
                # SC/#/SHELLFORCES/EID/#/CORNER/#/NXX,NYY,NXY
                xx_path = path.copy(); xx_path[7] = "NXX"; xx = tree_get_layer_1(parsed_f06, xx_path, output_file)
                yy_path = path.copy(); yy_path[7] = "NYY"; yy = tree_get_layer_1(parsed_f06, yy_path, output_file)
                xy_path = path.copy(); xy_path[7] = "NXY"; xy = tree_get_layer_1(parsed_f06, xy_path, output_file)
                result = rotate_2D_rank2_tensor(xx, yy, xy, angle, 1, path[7][-2:])
            elif len(path) > 7 and (path[7] == "MXX" or path[7] == "MYY" or path[7] == "MXY"):
                # Moment resultants:
                # SC/#/SHELLFORCES/EID/#/CORNER/#/MXX,MYY,MXY
                xx_path = path.copy(); xx_path[7] = "MXX"; xx = tree_get_layer_1(parsed_f06, xx_path, output_file)
                yy_path = path.copy(); yy_path[7] = "MYY"; yy = tree_get_layer_1(parsed_f06, yy_path, output_file)
                xy_path = path.copy(); xy_path[7] = "MXY"; xy = tree_get_layer_1(parsed_f06, xy_path, output_file)
                result = rotate_2D_rank2_tensor(xx, yy, xy, angle, 1, path[7][-2:])
    
    return result


def tree_get_layer_3(parsed_f06, path, gp_transforms, shell_angles, output_file : io.TextIOWrapper):
    # Get a value from the parsed f06 file with optional shell midsurface as well as the effects of lower layers.

    if len(path) > 7 \
    and path[0] == "SC" \
    and (path[2] == "SHELLSTRESSES" or path[2] == "SHELLSTRAINS") \
    and path[3] == "EID" \
    and path[5] == "CORNER" \
    and path[7] == "ZMID":
        z1_path = path.copy(); z1_path[7] = "Z1"; z1 = tree_get_layer_2(parsed_f06, z1_path, gp_transforms, shell_angles, output_file)
        z2_path = path.copy(); z2_path[7] = "Z2"; z2 = tree_get_layer_2(parsed_f06, z2_path, gp_transforms, shell_angles, output_file)
        return (z1 + z2) / 2
    else:
        return tree_get_layer_2(parsed_f06, path, gp_transforms, shell_angles, output_file)

def tree_get_layer_4(parsed_f06, path, gp_transforms, shell_angles, gid_to_corners, output_file : io.TextIOWrapper):
    # Get a value from the parsed f06 file with optional node averaging as well as the effects of lower layers.
    
    if (len(path) > 5
            and path[0] == "SC"
            and path[2] in ("SHELLSTRESSES", "SHELLSTRAINS", "SHELLFORCES")
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
            value = tree_get_layer_3(parsed_f06, element_path, gp_transforms, shell_angles, output_file)
            output_file.write(f"{INDENT * 3}{"/".join(element_path)} =\t{value}\n")
            if value is not None:
                total += value
                count += 1
            else:
                # gid_to_corners might be inconsistent with the data.
                # Or there might be a row omitted from f06 becuase it's all-zero. In that case,
                # update the all-zero code to include this block type.
                output_file.write(f"{INDENT * 2}Strangely no value.\n")
                return None

        if count == 0:
            output_file.write(f"{INDENT * 2}No elements with data found for GID {gid}.\n")
            return None

        return total / count

    else:

        return tree_get_layer_3(parsed_f06, path, gp_transforms, shell_angles, output_file)


def test_path(root_dir: Path,
              working_dir: Path,
              test_f06_path: Path,
              deck_path: Path,
              output_file: io.TextIOWrapper,
              test_case: Definition) -> int:

    def compare(test_value):
        nonlocal worst_error
        nonlocal fail_count

        if "/" in test_case.reference_value:
            reference_value = tree_get_layer_4(parsed_f06, test_case.reference_value.split("/"), gp_transforms, shell_angles, gid_to_corners, output_file)
        else:
            reference_value = float(test_case.reference_value)

        if math.isnan(reference_value):
            # Testing for NaN doesn't use the tolerance or comparison type.
            if math.isnan(test_value):
                error = 0
            else:
                error = float('inf');
        elif test_case.comparison_type == "percent":
            error = 100 * abs(test_value / reference_value - 1)
        elif test_case.comparison_type == "difference":
            error = abs(test_value - reference_value)
        else:
            print("ERROR 862621")
            sys.exit(1)

        if error <= test_case.tolerance:
            pass_fail = "PASS"
        else:
            # Fail is the else clause so that NaN fails.
            worst_error = max(error, worst_error)
            fail_count += 1
            pass_fail = "FAILED"

        error_string = f"{error:.2g}{test_case.tolerance_suffix()}"
        tolerance_string = f"({test_case.tolerance}{test_case.tolerance_suffix()})"
        output_file.write(f"{INDENT * 2}{pass_fail}\tError = {error_string} {tolerance_string} \tValue = {test_value} ({reference_value:.9g})\n")


    fail_count = 0
    comparison_count = 0
    worst_error = 0

    try:

        # Read f06 file
        parsed_f06 = read_f06_tree(test_f06_path)

        # Read grid point transformations file
        gp_transforms = read_gp_transforms(deck_path.with_suffix(".gptransform"))

        # Read shell angles file
        shell_angles = read_shell_angles(deck_path.with_suffix(".shellangles"))

        # Make GID to (EID,corner) reverse lookup
        gid_to_corners = build_gid_to_corners(parsed_f06)

        # Convert path from "/" delimited string to list
        tree_path = test_case.filter_string.split("/")

        single_paths = expand_lists(tree_path)

        match test_case.operation:
            case "":

                for single_path in single_paths:
                    comparison_count += 1
                    value = tree_get_layer_4(parsed_f06, single_path, gp_transforms, shell_angles, gid_to_corners, output_file)
                    if value is None:
                        fail_count += 1
                        output_file.write(f"{INDENT * 2}FAILED\n")
                    else:
                        compare(value)

            case "SUM":

                comparison_count += 1
                value_sum = 0
                for single_path in single_paths:
                    value = tree_get_layer_4(parsed_f06, single_path, gp_transforms, shell_angles, gid_to_corners, output_file)
                    if value is None:
                        value_sum = None
                        break
                    else:
                       value_sum += value
                if value_sum is None:
                    fail_count += 1
                    output_file.write(f"{INDENT * 2}FAILED\n")
                else:
                    compare(value_sum)

            case "DIFF":

                comparison_count += 1
                if len(single_paths) < 2:
                    fail_count += 1
                    output_file.write(f"FAIL. Wrong number of values for DIFF. Must be at least two.\n")
                else:
                    # Calculate <first value> - <last value>
                    value1 = tree_get_layer_4(parsed_f06, single_paths[0], gp_transforms, shell_angles, gid_to_corners, output_file)
                    value2 = tree_get_layer_4(parsed_f06, single_paths[-1], gp_transforms, shell_angles, gid_to_corners, output_file)
                    if value1 is None or value2 is None:
                        fail_count += 1
                        output_file.write(f"{INDENT * 2}FAILED\n")
                    compare(value1 - value2)

            case "RATIO":

                comparison_count += 1
                if len(single_paths) < 2:
                    fail_count += 1
                    output_file.write(f"FAIL. Wrong number of values for RATIO. Must be at least two.\n")
                else:
                    # Calculate <first value> / <last value>
                    value1 = tree_get_layer_4(parsed_f06, single_paths[0], gp_transforms, shell_angles, gid_to_corners, output_file)
                    value2 = tree_get_layer_4(parsed_f06, single_paths[-1], gp_transforms, shell_angles, gid_to_corners, output_file)
                    if value1 is None or value2 is None:
                        fail_count += 1
                        output_file.write(f"{INDENT * 2}FAILED\n")
                    compare(value1 / value2)

            case "NORM":

                comparison_count += 1
                value_squared_sum = 0
                for single_path in single_paths:
                    value = tree_get_layer_4(parsed_f06, single_path, gp_transforms, shell_angles, gid_to_corners, output_file)
                    if value is None:
                        value_squared_sum = None
                        break
                    else:
                       value_squared_sum += value**2
                if value_squared_sum is None:
                    fail_count += 1
                    output_file.write(f"{INDENT * 2}FAILED\n")
                else:
                    compare(math.sqrt(value_squared_sum))

            case "ANGLEFROMX" | "ANGLEFROMY" | "ANGLEFROMZ":

                # Uses incomplete paths without the trailing DOF name.
                # 1 grid point:
                #   SC/2/MODE/1/EIGENVECTOR/GID/10
                # or multiple grid points to sum:
                #   SC/2/MODE/1/EIGENVECTOR/GID/10,13
                # Also works for displacement and other types of vector with DOF immediately after GID.
                comparison_count += 1
                x_sum = 0
                y_sum = 0
                z_sum = 0
                for single_path in single_paths:
                    x = tree_get_layer_4(parsed_f06, single_path + ["TX"], gp_transforms, shell_angles, gid_to_corners, output_file)
                    y = tree_get_layer_4(parsed_f06, single_path + ["TY"], gp_transforms, shell_angles, gid_to_corners, output_file)
                    z = tree_get_layer_4(parsed_f06, single_path + ["TZ"], gp_transforms, shell_angles, gid_to_corners, output_file)
                    if x is None or y is None or z is None:
                        x_sum = None
                        y_sum = None
                        z_sum = None
                        break
                    else:
                       x_sum += x
                       y_sum += y
                       z_sum += z
                if x_sum is None:
                    fail_count += 1
                    output_file.write(f"{INDENT * 2}FAILED\n")
                else:
                    match test_case.operation[-1]:
                        case "X": v_ref = [1.0, 0.0, 0.0]
                        case "Y": v_ref = [0.0, 1.0, 0.0]
                        case "Z": v_ref = [0.0, 0.0, 1.0]
                    v_mag = math.sqrt(x_sum**2 + y_sum**2 + z_sum**2)
                    v_hat = [x_sum / v_mag, y_sum / v_mag, z_sum / v_mag]
                    v_dot_ref = v_hat[0] * v_ref[0] \
                              + v_hat[1] * v_ref[1] \
                              + v_hat[2] * v_ref[2]
                    compare(math.acos(abs(v_dot_ref)))

            case "ABSENT":

                for single_path in single_paths:
                    comparison_count += 1
                    value = tree_get_layer_4(parsed_f06, single_path, gp_transforms, shell_angles, gid_to_corners, output_file)
                    if value is not None:
                        fail_count += 1
                        output_file.write(f"{INDENT * 2}FAILED\n")
                    else:
                        pass
       
            case _:
            
                fail_count +=1
                output_file.write(f"{INDENT * 2}FAILED. Invalid operation\n")

    except Exception as e:
        fail_count += 1
        output_file.write(f"{INDENT * 2}ERROR: {e}\n")
   
    if worst_error > 0:
        message = f"Error = {worst_error:.2g}{test_case.tolerance_suffix()}"
    else:
        message = ""

    return fail_count, comparison_count, message
   


def run_case(mystran_path: Path,
             root_dir: Path,
             fails_dir: Path,
             output_file: io.TextIOWrapper,
             test_case: Definition,
             previous_deck_filename: str) -> bool:
    """Run one test case return True for pass or False for fail."""

    working_dir = (root_dir / "working").resolve()

    deck_path = root_dir / "decks" / test_case.deck_filename
    deck_stem = deck_path.stem

    # If it's the same deck as the previous test, reuse the .f06 to save time.
    if test_case.deck_filename != previous_deck_filename:

        output_file.write(f"\n")
        output_file.write(f"{test_case.deck_filename}\n")
    
        # Clear working directory
        if not clear_working_directory(working_dir):
            return False

        # Copy deck to working directory
        try:
            working_deck_filename_str = shutil.copyfile(deck_path, working_dir / deck_path.name)

            # Run Mystran
            with open(os.devnull, "w") as null_output:
                run_program(mystran_path, [working_deck_filename_str], working_dir, null_output, null_output)

        except Exception as e:
            output_file.write(f"{INDENT * 1}ERROR: {e}\n")
            fail_count = 1
        
    match test_case.test_type:
        case "mys" | "msc":
            output_file.write(f"{INDENT * 1}{test_case.test_type}; {test_case.deck_filename}; {test_case.filter_string}; {test_case.threshold}; {test_case.tolerance}{test_case.tolerance_suffix()}\n")
        case "pth":
            output_file.write(f"{INDENT * 1}{test_case.test_type}; {test_case.deck_filename}; {test_case.filter_string}; {test_case.operation}; {test_case.reference_value}; {test_case.tolerance}{test_case.tolerance_suffix()}\n")

    test_f06_path = (working_dir / deck_stem).with_suffix(".F06").resolve()

    if test_case.test_type == "mys" or test_case.test_type == "msc":

        fail_count = test_f06csv(root_dir, working_dir, test_f06_path, output_file, test_case)
        message = ""
        if fail_count == 254:
            # 254 is the maximum that f06magic can report through the exit code.
            count_suffix = "+"
        else:
            count_suffix = ""

    elif test_case.test_type == "pth":

        fail_count, comparison_count, message = test_path(root_dir, working_dir, test_f06_path, deck_path, output_file, test_case)
        count_suffix = "/" + str(comparison_count)
  
    else:
        print(f"ERROR: {test_case.test_type} is invalid.\t{test_case.deck_filename}")
        return False

    pass_fail = "PASS" if fail_count == 0 else "FAILED"
    print(f"{pass_fail}\t{fail_count}{count_suffix}\t{test_case.deck_filename}\t{message}")
        
    # Save a copy of failed F06 for inspecting after.
    if fail_count != 0:
        destination = (fails_dir / test_case.deck_filename).with_suffix(".F06").resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Don't overwrite anything to reduce damage caused by wrong-path bugs.
        if not os.path.exists(destination):
            try:
                shutil.copyfile(test_f06_path, destination)
            except Exception:
                pass

    return fail_count == 0


def main():

    print("========================")
    print("Mystran validation suite")
    print("========================")

    # Get Mystran binary path from command line
    if len(sys.argv) > 1:
        mystran_path = Path(sys.argv[1]).resolve()
    else:
        print(f"ERROR: No command line argument. Use the path to the mystran binary.")
        sys.exit(1)


    root_dir = Path(__file__).resolve().parent
    fails_dir = root_dir / "fails"
    definitions_path = (root_dir / "cases.txt").resolve()
    output_path = (root_dir / "output.txt").resolve()

    # Clear any fail outputs from the previous run.
    clear_fails_directory(fails_dir)

    print()

    test_cases = read_definitions(definitions_path)

    fails = 0
    count = len(test_cases)

    previous_deck_filename = ""

    with open(output_path, "w") as output_file:
        for test_case in test_cases:
            if not run_case(mystran_path, root_dir, fails_dir, output_file, test_case, previous_deck_filename):
                fails += 1
            previous_deck_filename = test_case.deck_filename

    print()
    exit_code = 0 if fails == 0 and count > 0 else 1
    print(f"{fails}/{count} failed -> {"PASS" if exit_code == 0 else "FAIL"}.")
    print()

    # Return exit code 0 for pass and 1 for fail
    sys.exit(exit_code)


if __name__ == "__main__":
    main()