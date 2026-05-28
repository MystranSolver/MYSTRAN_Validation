#!/usr/bin/env python3

import subprocess
import sys
import os
from shutil import copyfile
from io import TextIOWrapper
from textwrap import dedent
from pathlib import Path
from f06csv_to_magic import f06csv_args_to_magic
from test_bulk_auto import test_bulk_auto
from test_individual_values import test_individual_values
from case_definition import CaseDefinition

# Error messages with a code like ERROR 229606 are for bugs/corruption in the test suite.
# Error messages with explanations are for errors in test case definitions/usage.

INDENT = "  "
null_output = open(os.devnull, "w")



def read_definitions(definitions_path: Path) -> list[CaseDefinition]:

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
            definition = CaseDefinition()
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
                case "my2" | "ms2" | "my3" | "ms3":
                    if len(definition_fields_str) > 2:
                        definition.knownfail = definition_fields_str[2].startswith("KNOWNFAIL")
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
                our_output: TextIOWrapper,
                std_output: TextIOWrapper) -> int:

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
        

def test_bulk_magic(root_dir: Path,
                    working_dir: Path,
                    test_f06_path: Path,
                    output_file: TextIOWrapper,
                    test_case: CaseDefinition) -> int:

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


def test_bulk_auto_magic(root_dir: Path,
                         working_dir: Path,
                         test_f06_path: Path,
                         output_file: TextIOWrapper,
                         test_case: CaseDefinition) -> int:

    def block(extraction_name, block, cols):
        return dedent(f"""\
        [[extractions]]
        name          = "{extraction_name}"
        block         = "{block}"
        cols          = {str(cols)}
        [[comparison]]
        name          = "{test_case.deck_filename} {extraction_name}"
        reference_f06 = "reference_file"
        test_f06      = "test_file"
        extraction    = "{extraction_name}"
        criteria      = "only criteria"
        predicate     = "(rmaxa != 0 and (abs(t - r) / rmaxa <= 2e-7)) or (rmaxa == 0 and t == 0)"
        printout      = "P {extraction_name}"
        [[printout]]
        name          = "P {extraction_name}"
        max           = "rmaxa"
        error_percent = "abs(t - r) / rmaxa * 100"
        """)

    if test_case.test_type == "my3":
        reference_f06_path = (root_dir / "reference_mystran" / test_case.deck_filename).with_suffix(".F06").resolve()
    elif test_case.test_type == "ms3":
        reference_f06_path = (root_dir / "reference_msc" / test_case.deck_filename).with_suffix(".f06").resolve()
    
    # Make script for f06magic
    script = dedent(f"""\
        [files]
        test_file      = \"{test_f06_path}\"
        reference_file = \"{reference_f06_path}\"

        [[criteria]]
        name           = \"only criteria\"

        {block("displacements T", "displacements", ["tx", "ty", "tz"])}
        {block("displacements R", "displacements", ["rx", "ry", "rz"])}

        {block("eigenvector T", "eigenvector", ["tx", "ty", "tz"])}
        {block("eigenvector R", "eigenvector", ["rx", "ry", "rz"])}

        {block("spc_forces T", "spc_forces", ["tx", "ty", "tz"])}
        {block("spc_forces R", "spc_forces", ["rx", "ry", "rz"])}

        {block("applied_forces T", "applied_forces", ["tx", "ty", "tz"])}
        {block("applied_forces R", "applied_forces", ["rx", "ry", "rz"])}

        {block("grid_point_force_balance T", "grid_point_force_balance", ["tx", "ty", "tz"])}
        {block("grid_point_force_balance R", "grid_point_force_balance", ["rx", "ry", "rz"])}

        {block("elas_1_forces", "elas_1_forces", ["force"])}

        {block("elas_1_stresses", "elas_1_stresses", ["stress"])}

        {block("rod_forces F", "rod_forces", ["axial_force"])}
        {block("rod_forces M", "rod_forces", ["torque"])}

        {block("rod_stresses", "rod_stresses", ["axial", "torsional"])}

        {block("bar_forces F", "bar_forces", ["shear_plane_1", "shear_plane_2", "axial_force"])}
        {block("bar_forces M", "bar_forces", ["bend_moment_end_a_plane_1",
                                              "bend_moment_end_a_plane_2",
                                              "bend_moment_end_b_plane_1",
                                              "bend_moment_end_b_plane_2",
                                              "torque"])}

        {block("bar_stresses", "bar_stresses", ["end_a_recovery_point_1", 
                                                "end_a_recovery_point_2",
                                                "end_a_recovery_point_3",
                                                "end_a_recovery_point_4", 
                                                "end_b_recovery_point_1",
                                                "end_b_recovery_point_2",
                                                "end_b_recovery_point_3",
                                                "end_b_recovery_point_4",
                                                "axial"])}

    """)

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




def run_case(mystran_path: Path,
             root_dir: Path,
             fails_dir: Path,
             output_file: TextIOWrapper,
             test_case: CaseDefinition,
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
            working_deck_filename_str = copyfile(deck_path, working_dir / deck_path.name)

            # Run Mystran
            run_program(mystran_path, [working_deck_filename_str], working_dir, null_output, null_output)

        except Exception as e:
            output_file.write(f"{INDENT * 1}ERROR: {e}\n")
            fail_count = 1

    test_f06_path = (working_dir / deck_stem).with_suffix(".F06").resolve()

    if test_case.test_type == "mys" or test_case.test_type == "msc":

        output_file.write(f"{INDENT * 1}{test_case.test_type}; {test_case.deck_filename}; {test_case.filter_string}; {test_case.threshold}; {test_case.tolerance}{test_case.tolerance_suffix()}\n")

        fail_count, message = test_bulk_magic(root_dir, working_dir, test_f06_path, output_file, test_case)
        if fail_count == 254:
            # 254 is the maximum that f06magic can report through the exit code.
            count_suffix = "+"
        else:
            count_suffix = ""

    elif test_case.test_type == "my2" or test_case.test_type == "ms2":

        output_file.write(f"{INDENT * 1}{test_case.test_type}; {test_case.deck_filename}\n")

        fail_count, comparison_count, message = test_bulk_auto(root_dir, test_f06_path, deck_path, output_file, test_case)
        count_suffix = "/" + str(comparison_count)

    elif test_case.test_type == "my3" or test_case.test_type == "ms3":

        output_file.write(f"{INDENT * 1}{test_case.test_type}; {test_case.deck_filename}; {test_case.filter_string}; {test_case.threshold}; {test_case.tolerance}{test_case.tolerance_suffix()}\n")

        fail_count, message = test_bulk_auto_magic(root_dir, working_dir, test_f06_path, output_file, test_case)
        if fail_count == 254:
            # 254 is the maximum that f06magic can report through the exit code.
            count_suffix = "+"
        else:
            count_suffix = ""

    elif test_case.test_type == "pth":

        output_file.write(f"{INDENT * 1}{test_case.test_type}; {test_case.deck_filename}; {test_case.filter_string}; {test_case.operation}; {test_case.reference_value}; {test_case.tolerance}{test_case.tolerance_suffix()}\n")

        fail_count, comparison_count, message = test_individual_values(root_dir, test_f06_path, deck_path, output_file, test_case)
        count_suffix = "/" + str(comparison_count)
  
    else:
        print(f"ERROR: {test_case.test_type} is invalid.\t{test_case.deck_filename}")
        return False

    pass_fail = "PASS" if fail_count == 0 else "FAILED"
    display_message = f"{pass_fail}\t{fail_count}{count_suffix}\t{test_case.deck_filename}\t{message}"
    print(display_message)
    output_file.write(f"{INDENT * 2}{display_message}\n")
        
    # Save a copy of failed F06 for inspecting after.

    if fail_count != 0:
        destination = (fails_dir / test_case.deck_filename).with_suffix(".F06").resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Don't overwrite anything to reduce damage caused by wrong-path bugs.
        if not os.path.exists(destination):
            try:
                copyfile(test_f06_path, destination)
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


    with open(output_path, "w") as output_file:
        fails = 0
        count = len(test_cases)
        previous_deck_filename = ""
        for test_case in test_cases:
            if not run_case(mystran_path, root_dir, fails_dir, output_file, test_case, previous_deck_filename):
                fails += 1
            previous_deck_filename = test_case.deck_filename

        exit_code = 0 if fails == 0 and count > 0 else 1
        final_summary = f"{fails}/{count} failed -> {"PASS" if exit_code == 0 else "FAIL"}."
        print("="*len(final_summary))
        print(final_summary)
        print("="*len(final_summary))
        output_file.write(f"{"="*len(final_summary)}\n")
        output_file.write(f"{final_summary}\n")
        output_file.write(f"{"="*len(final_summary)}\n")

    # Return exit code 0 for pass and 1 for fail
    sys.exit(exit_code)


if __name__ == "__main__":
    main()