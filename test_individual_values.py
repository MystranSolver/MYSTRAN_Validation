#!/usr/bin/env python3

import sys
import os
import math
from io import TextIOWrapper
from pathlib import Path  #todo ?
from math_expression import Lexer
from math_expression import Parser
from math_expression import Evaluator
from math_expression import MathExpressionError
from grid_reader import read_grids
from element_reader import read_elements
from f06_query import F06Query
from case_definition import CaseDefinition

# Error messages with a code like ERROR 229606 are for bugs/corruption in the test suite.
# Error messages with explanations are for errors in test case definitions/usage.

INDENT = "  "
null_output = open(os.devnull, "w")




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


def get_layer_7(parsed_f06, expression, gp_transforms, shell_angles, gp_coordinates, gid_to_corners, output_file : TextIOWrapper):
    # Get values from layer 6 and:
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
            variable_values = parsed_f06.get_layer_6(path, gp_transforms, shell_angles, gp_coordinates, gid_to_corners, output_file)
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
        hasNone = False
        for variable_name, variable_values in variables.items():

            if len(variable_values) == 1:
                value = variable_values[0]
            elif len(variable_values) > 1:
                value = variable_values[index]
            else:
                print(f"ERROR: 963217")
                sys.exit(1)
            evaluator.set_variable(variable_name, value)

            hasNone = hasNone or value is None

        # Evaluate
        if hasNone:
            # If any variable is None, skip evaluation so the evaluator doesn't 
            # have to cope with None.
            result.append(None)
        else:
            try:
                result.append(evaluator.evaluate(ast))
            except MathExpressionError:
                result.append(None)

    return result


def test_individual_values(root_dir: Path,
                           test_f06_path: Path,
                           deck_path: Path,
                           output_file: TextIOWrapper,
                           test_case: CaseDefinition) -> int:

    def compare(test_value):
        nonlocal worst_error
        nonlocal fail_count

        reference_values = get_layer_7(parsed_f06, test_case.reference_value, gp_transforms, shell_angles, gp_coordinates, gid_to_corners, output_file)
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
            try:
                error = 100 * abs(test_value / reference_value - 1)
            except ZeroDivisionError:
                error = float('inf')
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

    values = get_layer_7(parsed_f06, test_case.filter_string, gp_transforms, shell_angles, gp_coordinates, gid_to_corners, output_file)

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
                if value is None:
                    x_sum = None
                    y_sum = None
                    z_sum = None
                    break
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
                try:
                    v_hat = [x_sum / v_mag, y_sum / v_mag, z_sum / v_mag]
                except ZeroDivisionError:
                    fail_count += 1
                    output_file.write(f"{INDENT * 2}FAILED. vector magnitude is zero.\n")
                else:
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






