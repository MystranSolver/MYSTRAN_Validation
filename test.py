#!/usr/bin/env python3

import subprocess
import sys
import shutil
import os
import io
import math
from pathlib import Path
from f06csv_to_magic import f06csv_args_to_magic
from math_expression import Lexer
from math_expression import Parser
from math_expression import Evaluator
from grid_reader import read_grids
from element_reader import read_elements
from f06_query import F06Query

# Error messages with a code like ERROR 229606 are for bugs/corruption in the test suite.
# Error messages with explanations are for errors in test case definitions/usage.

INDENT = "  "
null_output = open(os.devnull, "w")



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
        self.knownfail = False

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
            if len(definition_fields_str) < 2:
                print(f"ERROR: Not enough fields in")
                print(f"{definition_str}")
                sys.exit(1)
            definition = Definition()
            definition.test_type = definition_fields_str[0]
            definition.deck_filename = definition_fields_str[1]
            match definition.test_type:
                case "mys" | "msc":
                    if len(definition_fields_str) < 5:
                        print(f"ERROR: Not enough fields in")
                        print(f"{definition_str}")
                        sys.exit(1)
                    definition.filter_string = definition_fields_str[2]
                    definition.threshold = float(definition_fields_str[3])
                    read_tolerance(definition_fields_str[4])
                    if len(definition_fields_str) > 5:
                        definition.knownfail = definition_fields_str[5].startswith("KNOWNFAIL")
                case "pth":
                    if len(definition_fields_str) < 6:
                        print(f"ERROR: Not enough fields in")
                        print(f"{definition_str}")
                        sys.exit(1)
                    definition.filter_string = definition_fields_str[2]
                    definition.operation = definition_fields_str[3]
                    definition.reference_value = definition_fields_str[4]
                    read_tolerance(definition_fields_str[5])
                    if len(definition_fields_str) > 6:
                        definition.knownfail = definition_fields_str[6].startswith("KNOWNFAIL")
                case "my2":
                    if len(definition_fields_str) > 2:
                        definition.knownfail = definition_fields_str[2].startswith("KNOWNFAIL")
                

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
    if test_case.comparison_type == "percent":
        script = script + f"""
percent_tolerance = {str(test_case.tolerance)}
epsilon = {str(test_case.threshold)}
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

    args = ["--verbose", f06magic_script_path]

    # Run f06magic
    fail_count = run_program(root_dir / "f06magic.exe", args, working_dir, output_file, output_file)


    message = ""

    # Known fails must fail.
    if test_case.knownfail:
        if fail_count > 0:
            fail_count = 0
            message += f"\tKNOWNFAIL failed as expected"
        else:
            fail_count += 1
            message += f"\tKNOWNFAIL passed"

    return fail_count, message


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
        

def read_gid_to_corners(deck_path: Path) -> dict:
    """Build a reverse lookup from GID to list of (EID, corner) pairs using
    the input deck."""

    result: dict = {}

    records = read_elements(deck_path)

    for element in records:
        corners = None
        match element.elem_type:
            case "CTRIA3": corners = range(0, 1)
            case "CQUAD4": corners = range(1, 5)
            case "CQUAD8": corners = range(1, 5)
            case "CHEXA": corners = range(1, 9)
            case "CPENTA": corners = range(1, 7)
            case "CTETRA": corners = range(1, 5)
            case _:
                print(f"ERROR 876287 {element.elem_type}")
                sys.exit(1)
        for corner in corners:

            if corner == 0:
                # Center only
                for gid_int in element.nodes:
                    gid = str(gid_int)
                    # Make sure a list exists for this GID
                    if gid not in result:
                        result[gid] = []
                    result[gid].append((str(element.eid), str(corner)))
            
            if corner >= 1:
                # Corners only
                gid = str(element.nodes[corner - 1])
                # Make sure a list exists for this GID
                if gid not in result:
                    result[gid] = []
                result[gid].append((str(element.eid), str(corner)))

    return result


def get_layer_6(parsed_f06, expression, gp_transforms, shell_angles, gp_coordinates, gid_to_corners, output_file : io.TextIOWrapper):
    # Get values from layer 5 and:
    # - Use a math expression.

    # Tokenize the expression
    lexer = Lexer(expression)
    tokens = lexer.tokenize()

    # Parse tokens into abstract syntax tree
    parser = Parser(tokens)
    ast = parser.parse()

    # Collect variables' values. Variables are f06 paths with values from f06.
    variables = {}
    for token in tokens:
        if token.type == "VARIABLE":
            path = token.value.split("/")
            variable_values = parsed_f06.get_layer_5(path, gp_transforms, shell_angles, gp_coordinates, gid_to_corners, output_file)
            variables[token.value] = variable_values

    # Count the number of values in each variable
    n = None
    for variable_name, variable_values in variables.items():
        count = len(variable_values)
        if count == 1:
            pass
        elif n == None:
            n = count
        elif n == count:
            pass
        else:
            output_file.write(f"{INDENT * 2} A path resolves to a number of values that's incompatible with other paths in the expression:\n")
            output_file.write(f"{INDENT * 2} {variable_name} has {count} values but another path has {n} values.\n")
            output_file.write(f"{INDENT * 2} Every path in the expression must have either the same number of values or 1 value.\n")
            return [None]

    # If there are no variables, there's one value.
    if n == None:
        n = 1

    result = []
    for index in range(n):
    
        evaluator = Evaluator()

        # Set variables' values.
        for variable_name, variable_values in variables.items():

            if len(variable_values) == 1:
                evaluator.set_variable(variable_name, variable_values[0])
            elif len(variable_values) > 1:
                evaluator.set_variable(variable_name, variable_values[index])

        # Evaluate
        result.append(evaluator.evaluate(ast))

    return result


def test_path(root_dir: Path,
              working_dir: Path,
              test_f06_path: Path,
              deck_path: Path,
              output_file: io.TextIOWrapper,
              test_case: Definition) -> int:

    def compare(test_value):
        nonlocal worst_error
        nonlocal fail_count

        reference_values = get_layer_6(parsed_f06, test_case.reference_value, gp_transforms, shell_angles, gp_coordinates, gid_to_corners, output_file)
        if len(reference_values) > 1:
            fail_count += 1
            print(f"ERROR: reference value resolves to more than one value.")
            output_file.write(f"{INDENT * 2}{"FAILED\tERROR: reference value resolves to more than one value."}\n")
            return
        else:
            reference_value = reference_values[0]

        if math.isnan(reference_value):
            # Testing for NaN doesn't use the tolerance or comparison type.
            if math.isnan(test_value):
                error = 0 # Force pass
            else:
                error = float('inf') # Force fail
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
        parsed_f06 = F06Query(str(test_f06_path))

        # Read grid point transformations file
        gp_transforms = read_gp_transforms(deck_path.with_suffix(".gptransform"))

        # Read shell angles file
        shell_angles = read_shell_angles(deck_path.with_suffix(".shellangles"))

        # Read grid point coordinates from the input deck
        gp_coordinates = read_grids(deck_path)

        # Make GID to (EID,corner) reverse lookup
        gid_to_corners = read_gid_to_corners(deck_path)

        values = get_layer_6(parsed_f06, test_case.filter_string, gp_transforms, shell_angles, gp_coordinates, gid_to_corners, output_file)

        match test_case.operation:
            case "":

                for value in values:
                    comparison_count += 1
                    if value is None:
                        fail_count += 1
                        output_file.write(f"{INDENT * 2}FAILED\n")
                    else:
                        compare(value)

            case "SUM":

                comparison_count += 1
                value_sum = 0
                for value in values:
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

            case "NORM":

                comparison_count += 1
                value_squared_sum = 0
                for value in values:
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
                for value in values:
                    x = value["TX"]
                    y = value["TY"]
                    z = value["TZ"]
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

                for value in values:
                    comparison_count += 1
                    if value is not None:
                        fail_count += 1
                        output_file.write(f"{INDENT * 2}FAILED\n")
                    else:
                        pass
       
            case _:
            
                fail_count +=1
                output_file.write(f"{INDENT * 2}FAILED. Invalid operation\n")

    # todo re-enable later
    # except Exception as e:
        # fail_count += 1
        # output_file.write(f"{INDENT * 2}ERROR: {e}\n")
    finally:
        pass
   
    if worst_error > 0:
        message = f"Error = {worst_error:.2g}{test_case.tolerance_suffix()}"
    else:
        message = ""

    # Known fails must fail.
    if test_case.knownfail:
        if fail_count > 0:
            fail_count = 0
            message += f"\tKNOWNFAIL failed as expected"
        else:
            fail_count += 1
            message += f"\tKNOWNFAIL passed"

    return fail_count, comparison_count, message

def test_bulk_auto(root_dir: Path,
                   working_dir: Path,
                   test_f06_path: Path,
                   deck_path: Path,
                   output_file: io.TextIOWrapper,
                   test_case: Definition) -> int:

    tolerance = 2e-5 # in percent
    fail_count = 0
    comparison_count = 0
    worst_error = 0
    worst_path = ""

    def compare(path, maximum):
        nonlocal fail_count
        nonlocal worst_error
        nonlocal worst_path
        nonlocal comparison_count

        ref_value = ref_f06.get_layer_4(path, {}, {}, {}, {}, output_file)
        tst_value = tst_f06.get_layer_4(path, {}, {}, {}, {}, output_file)

        comparison_count += 1

        if math.isnan(ref_value):
            # Testing for NaN doesn't use the tolerance or comparison type.
            if math.isnan(tst_value):
                error = 0 # Force pass
            else:
                error = float('inf') # Force fail
        elif maximum == 0:
            # With zero maximum, if we tolerate any small non-zero values, we
            # need to choose a tolerance somehow so default to exact comparison.
            error = float('inf') if tst_value != 0 else 0
        else:
            error = 100 * abs(tst_value-ref_value) / maximum
        

        if error <= tolerance:
            pass_fail = "PASS"
        else:
            # Fail is the else clause so that NaN fails.
            path_str = "/".join(path)
            if error >= worst_error:
                worst_error = error
                worst_path = path_str
            fail_count += 1
            output_file.write(f"{INDENT * 3}FAILED\tError = {error:.2g}% ({tolerance}%)\t{path_str}\tValue = {tst_value} ({ref_value:.9g})\n")


    try:

        if test_case.test_type == "my2":
            reference_f06_path = (root_dir / "reference_mystran" / test_case.deck_filename).with_suffix(".F06").resolve()
        elif test_case.test_type == "ms2":
            reference_f06_path = (root_dir / "reference_msc" / test_case.deck_filename).with_suffix(".f06").resolve()

        # Read f06 files
        ref_f06 = F06Query(str(reference_f06_path))
        tst_f06 = F06Query(str(test_f06_path))


        # Subcases
        # ========
        subcases_block = ref_f06.get_layer_4(["SC"], {}, {}, {}, {}, null_output)
        for subcase in subcases_block.keys():

            # DISPLACEMENTS TX, TY, TZ in each subcase
            #-----------------------------------------
            block_path = ["SC",subcase,"DISPLACEMENTS"] # Doesn't include GID here because there may be none if all zero.
            ref_block = ref_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
            tst_block = tst_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
            if ref_block is not None:
                output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
                comparison_count += 1
                if tst_block is None:
                    fail_count += 1
                    output_file.write(f"\n")
                    output_file.write(f"{INDENT * 3}FAILED\t{"/".join(block_path)} is not present in the test solution.\n")
                else:
                    # Identify GIDs from the union of the test and reference blocks
                    gids = ref_block["GID"].keys() | tst_block["GID"].keys()
                    # Find the maximum of all values we'll be testing in the block
                    maximum = 0
                    for gid in gids:
                        for component in ["TX", "TY", "TZ"]:
                            value = ref_f06.get_layer_4(block_path + ["GID",str(gid),component], {}, {}, {}, {}, output_file)
                            maximum = max(maximum, abs(value))
                    output_file.write(f"\tMaximum value = {maximum}\n")
                    # Compare each value normalized by the maximum
                    for gid in gids:
                        for component in ["TX", "TY", "TZ"]:
                            compare(block_path + ["GID",str(gid),component], maximum)

            # APPLIEDFORCES TX, TY, TZ in each subcase
            #-----------------------------------------
            block_path = ["SC",subcase,"APPLIEDFORCES"] # Doesn't include GID here because there may be none if all zero.
            ref_block = ref_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
            tst_block = tst_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
            if ref_block is not None:
                output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
                comparison_count += 1
                if tst_block is None:
                    fail_count += 1
                    output_file.write(f"\n")
                    output_file.write(f"{INDENT * 3}FAILED\t{"/".join(block_path)} is not present in the test solution.\n")
                else:
                    comparison_count += 1
                    # Identify GIDs from the union of the test and reference blocks
                    gids = ref_block["GID"].keys() | tst_block["GID"].keys()
                    # Find the maximum of all values we'll be testing in the block
                    maximum = 0
                    for gid in gids:
                        for component in ["TX", "TY", "TZ"]:
                            value = ref_f06.get_layer_4(block_path + ["GID",str(gid),component], {}, {}, {}, {}, output_file)
                            maximum = max(maximum, abs(value))
                    output_file.write(f"\tMaximum value = {maximum}\n")
                    # Compare each value normalized by the maximum
                    for gid in gids:
                        for component in ["TX", "TY", "TZ"]:
                            compare(block_path + ["GID",str(gid),component], maximum)

            # GPFORCES TX, TY, TZ in each subcase
            #------------------------------------
            block_path = ["SC",subcase,"GPFORCE"]
            ref_block = ref_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
            tst_block = tst_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
            if ref_block is not None:
                output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
                comparison_count += 1
                if tst_block is None:
                    fail_count += 1
                    output_file.write(f"\n")
                    output_file.write(f"{INDENT * 3}FAILED\t{"/".join(block_path)} is not present in the test solution.\n")
                else:
                    # Identify GIDs from the union of the test and reference blocks
                    gids = ref_block["GID"].keys() | tst_block["GID"].keys()
                    # Find the maximum of all values we'll be testing in the block
                    maximum = 0
                    for gid in gids:
                        gid_ref_block = ref_block["GID"][gid]
                        for force_type in ["APPLIED", "SPC", "MPC", "INERTIA"]:
                            for component in ["TX", "TY", "TZ"]:
                                value = ref_f06.get_layer_4(block_path + ["GID",str(gid),force_type,component], {}, {}, {}, {}, output_file)
                                maximum = max(maximum, abs(value))
                        # todo we should use the union of EIDs from test and ref for this grid point because either one might be absent if all zero.
                        # same for the comparison loop below.
                        if "EID" in gid_ref_block.keys():
                            for eid in gid_ref_block["EID"].keys():
                                for component in ["TX", "TY", "TZ"]:
                                    value = ref_f06.get_layer_4(block_path + ["GID",str(gid),"EID",eid,component], {}, {}, {}, {}, output_file)
                                    maximum = max(maximum, abs(value))

                    output_file.write(f"\tMaximum value = {maximum}\n")
                    # Compare each value normalized by the maximum
                    for gid in gids:
                        gid_ref_block = ref_block["GID"][gid]
                        for force_type in ["APPLIED", "SPC", "MPC", "INERTIA"]:
                            for component in ["TX", "TY", "TZ"]:
                                compare(block_path + ["GID",str(gid),force_type,component], maximum)
                        if "EID" in gid_ref_block.keys():
                            for eid in gid_ref_block["EID"].keys():
                                for component in ["TX", "TY", "TZ"]:
                                    compare(block_path + ["GID",str(gid),"EID",eid,component], maximum)

            # BARSTRESSES
            # -----------
            block_path = ["SC", subcase, "BARSTRESSES"]
            ref_block = ref_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
            tst_block = tst_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
            if ref_block is not None:
                output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
                comparison_count += 1
                if tst_block is None:
                    fail_count += 1
                    output_file.write(f"\n")
                    output_file.write(f"{INDENT * 3}FAILED\t{"/".join(block_path)} is not present in the test solution.\n")
                else:
                    # Identify EIDs from the union of the test and reference blocks
                    eids = ref_block["EID"].keys() | tst_block["EID"].keys()
                    # Find the maximum of all values we'll be testing in the block
                    maximum = 0
                    for eid in eids:
                        for component in ["SA1", "SA2", "SA3", "SA4", "SB1", "SB2", "SB3", "SB4", "AXIAL"]:
                            value = ref_f06.get_layer_4(block_path + ["EID",str(eid),component], {}, {}, {}, {}, output_file)
                            maximum = max(maximum, abs(value))
                    output_file.write(f"\tMaximum value = {maximum}\n")
                    # Compare each value normalized by the maximum
                    for eid in eids:
                        for component in ["SA1", "SA2", "SA3", "SA4", "SB1", "SB2", "SB3", "SB4", "AXIAL"]:
                            compare(block_path + ["EID",str(eid),component], maximum)

            # BARFORCES
            # -----------
            #todo moments and forces should be normalized separately.
            block_path = ["SC", subcase, "BARFORCES"]
            ref_block = ref_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
            tst_block = tst_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
            if ref_block is not None:
                output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
                comparison_count += 1
                if tst_block is None:
                    fail_count += 1
                    output_file.write(f"\n")
                    output_file.write(f"{INDENT * 3}FAILED\t{"/".join(block_path)} is not present in the test solution.\n")
                else:
                    # Identify EIDs from the union of the test and reference blocks
                    eids = ref_block["EID"].keys() | tst_block["EID"].keys()
                    # Find the maximum of all values we'll be testing in the block
                    maximum = 0
                    for eid in eids:
                        for component in ["MA1", "MA2", "MB1", "MB2", "S1", "S2", "AXIAL", "TORQUE"]:
                            value = ref_f06.get_layer_4(block_path + ["EID",str(eid),component], {}, {}, {}, {}, output_file)
                            maximum = max(maximum, abs(value))
                    output_file.write(f"\tMaximum value = {maximum}\n")
                    # Compare each value normalized by the maximum
                    for eid in eids:
                        for component in ["MA1", "MA2", "MB1", "MB2", "S1", "S2", "AXIAL", "TORQUE"]:
                            compare(block_path + ["EID",str(eid),component], maximum)


        # Eigenvalues
        #------------
        block_path = ["SC","2","REALEIGENVALUES","MODE"] # Includes MODE here so it's easier to safely enumerate mode numbers.
        ref_block = ref_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
        tst_block = tst_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
        if ref_block is not None:
            output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
            comparison_count += 1
            if tst_block is None:
                fail_count += 1
                output_file.write(f"\n")
                output_file.write(f"{INDENT * 3}FAILED\t{"/".join(block_path)} is not present in the test solution.\n")
            else:
                # Find the maximum of all values we'll be testing in the block
                maximum = 0
                for mode in ref_block.keys():
                    for component in ["EIGENVALUE"]:
                        value = ref_f06.get_layer_4(block_path + [str(mode),component], {}, {}, {}, {}, output_file)
                        maximum = max(maximum, abs(value))
                output_file.write(f"\tMaximum value = {maximum}\n")
                # Compare each value normalized by the maximum
                for mode in ref_block.keys():
                    for component in ["EIGENVALUE"]:
                        compare(block_path + [str(mode),component], maximum)

        # Modes
        # =====
        modes_block = ref_f06.get_layer_4(["SC","2","MODE"], {}, {}, {}, {}, null_output)
        if modes_block is not None:
            for mode in modes_block.keys():
            
                # EIGENVECTORS TX, TY, TZ
                #------------------------
                block_path = ["SC", "2", "MODE", mode, "EIGENVECTOR"]
                ref_block = ref_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
                tst_block = tst_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
                if ref_block is not None:
                    output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
                    comparison_count += 1
                    if tst_block is None:
                        fail_count += 1
                        output_file.write(f"\n")
                        output_file.write(f"{INDENT * 3}FAILED\t{"/".join(block_path)} is not present in the test solution.\n")
                    else:
                        # Identify GIDs from the union of the test and reference blocks
                        gids = ref_block["GID"].keys() | tst_block["GID"].keys()
                        # Find the maximum of all values we'll be testing in the block
                        maximum = 0
                        for gid in gids:
                            for component in ["TX", "TY", "TZ"]:
                                value = ref_f06.get_layer_4(block_path + ["GID",str(gid),component], {}, {}, {}, {}, output_file)
                                maximum = max(maximum, abs(value))
                        output_file.write(f"\tMaximum value = {maximum}\n")
                        # Compare each value normalized by the maximum
                        for gid in gids:
                            for component in ["TX", "TY", "TZ"]:
                                compare(block_path + ["GID",str(gid),component], maximum)

                # BARSTRESSES
                # -----------
                block_path = ["SC", "2", "MODE", mode, "BARSTRESSES"]
                ref_block = ref_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
                tst_block = tst_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
                if ref_block is not None:
                    output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
                    comparison_count += 1
                    if tst_block is None:
                        fail_count += 1
                        output_file.write(f"\n")
                        output_file.write(f"{INDENT * 3}FAILED\t{"/".join(block_path)} is not present in the test solution.\n")
                    else:
                        # Identify EIDs from the union of the test and reference blocks
                        eids = ref_block["EID"].keys() | tst_block["EID"].keys()
                        # Find the maximum of all values we'll be testing in the block
                        maximum = 0
                        for eid in eids:
                            for component in ["SA1", "SA2", "SA3", "SA4", "SB1", "SB2", "SB3", "SB4", "AXIAL"]:
                                value = ref_f06.get_layer_4(block_path + ["EID",str(eid),component], {}, {}, {}, {}, output_file)
                                maximum = max(maximum, abs(value))
                        output_file.write(f"\tMaximum value = {maximum}\n")
                        # Compare each value normalized by the maximum
                        for eid in eids:
                            for component in ["SA1", "SA2", "SA3", "SA4", "SB1", "SB2", "SB3", "SB4", "AXIAL"]:
                                compare(block_path + ["EID",str(eid),component], maximum)

                # BARFORCES
                # -----------
                #todo moments and forces should be normalized separately.
                block_path = ["SC", "2", "MODE", mode, "BARFORCES"]
                ref_block = ref_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
                tst_block = tst_f06.get_layer_4(block_path, {}, {}, {}, {}, null_output)
                if ref_block is not None:
                    output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
                    comparison_count += 1
                    if tst_block is None:
                        fail_count += 1
                        output_file.write(f"\n")
                        output_file.write(f"{INDENT * 3}FAILED\t{"/".join(block_path)} is not present in the test solution.\n")
                    else:
                        # Identify EIDs from the union of the test and reference blocks
                        eids = ref_block["EID"].keys() | tst_block["EID"].keys()
                        # Find the maximum of all values we'll be testing in the block
                        maximum = 0
                        for eid in eids:
                            for component in ["MA1", "MA2", "MB1", "MB2", "S1", "S2", "AXIAL", "TORQUE"]:
                                value = ref_f06.get_layer_4(block_path + ["EID",str(eid),component], {}, {}, {}, {}, output_file)
                                maximum = max(maximum, abs(value))
                        output_file.write(f"\tMaximum value = {maximum}\n")
                        # Compare each value normalized by the maximum
                        for eid in eids:
                            for component in ["MA1", "MA2", "MB1", "MB2", "S1", "S2", "AXIAL", "TORQUE"]:
                                compare(block_path + ["EID",str(eid),component], maximum)

    # todo re-enable later
    # except Exception as e:
        # fail_count += 1
        # output_file.write(f"{INDENT * 2}ERROR: {e}\n")
    finally:
        pass
   
    if worst_error > 0:
        message = f"Error = {worst_error:.2g}{test_case.tolerance_suffix()} {worst_path}"
    else:
        message = ""

    # Known fails must fail.
    if test_case.knownfail:
        if fail_count > 0:
            fail_count = 0
            message += f"\tKNOWNFAIL failed as expected"
        else:
            fail_count += 1
            message += f"\tKNOWNFAIL passed"

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
            run_program(mystran_path, [working_deck_filename_str], working_dir, null_output, null_output)

        except Exception as e:
            output_file.write(f"{INDENT * 1}ERROR: {e}\n")
            fail_count = 1

    test_f06_path = (working_dir / deck_stem).with_suffix(".F06").resolve()

    if test_case.test_type == "mys" or test_case.test_type == "msc":

        output_file.write(f"{INDENT * 1}{test_case.test_type}; {test_case.deck_filename}; {test_case.filter_string}; {test_case.threshold}; {test_case.tolerance}{test_case.tolerance_suffix()}\n")

        fail_count, message = test_f06csv(root_dir, working_dir, test_f06_path, output_file, test_case)
        if fail_count == 254:
            # 254 is the maximum that f06magic can report through the exit code.
            count_suffix = "+"
        else:
            count_suffix = ""

    elif test_case.test_type == "pth":

        output_file.write(f"{INDENT * 1}{test_case.test_type}; {test_case.deck_filename}; {test_case.filter_string}; {test_case.operation}; {test_case.reference_value}; {test_case.tolerance}{test_case.tolerance_suffix()}\n")

        fail_count, comparison_count, message = test_path(root_dir, working_dir, test_f06_path, deck_path, output_file, test_case)
        count_suffix = "/" + str(comparison_count)

    elif test_case.test_type == "my2" or test_case.test_type == "ms2":

        output_file.write(f"{INDENT * 1}{test_case.test_type}; {test_case.deck_filename}\n")

        fail_count, comparison_count, message = test_bulk_auto(root_dir, working_dir, test_f06_path, deck_path, output_file, test_case)
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