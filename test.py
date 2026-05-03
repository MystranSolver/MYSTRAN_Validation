#!/usr/bin/env python3

import subprocess
import sys
import shutil
import os
import io
from pathlib import Path
from f06csv_to_magic import f06csv_args_to_magic
from f06tree import read_f06_tree
from f06tree import tree_get
from f06tree import write_structure_dense

# Error messages with a code like ERROR 229606 are for bugs/corruption in the test suite.
# Error messages with explanations are for errors in test case definitions/usage.


class Definition:
    def __init__(self):
        self.test_type = ""
        self.deck_filename = ""
        self.filter_string = ""
        self.reference_value = 0.0
        self.threshold = 0.0
        self.comparison_type = "percent"
        self.tolerance = 0.0

def read_definitions(definitions_path: Path) -> list[Definition]:

    # Read a line for each test case definition
    definitions_str = definitions_path.read_text().splitlines()

    result = []
    
    for definition_str in definitions_str:
        definition_fields_str = definition_str.split(";")
        if len(definition_fields_str) <= 1:
            # Skip blank lines
            pass
        elif definition_fields_str[0].strip().startswith("#"):
            # Skip comments
            pass
        else:
            definition_fields_str = [s.strip() for s in definition_fields_str]
            definition = Definition()
            definition.test_type = definition_fields_str[0]
            definition.deck_filename = definition_fields_str[1]
            definition.filter_string = definition_fields_str[2]
            definition.reference_value = float(definition_fields_str[3])
            definition.threshold = float(definition_fields_str[3])

            if "%" in definition_fields_str[4]:
                definition.comparison_type = "percent"
            else:
                definition.comparison_type = "difference"
            definition.tolerance = float(definition_fields_str[4].replace("%",""))

            result.append(definition)
    
    return result


def clear_fails_directory(path: Path) -> bool:
    
    # Safety check to avoid clearing the wrong directory.
    if path.stem != "fails":
        print("ERROR 235476")
        return False

    # Create fails directory if it doesn't exist.
    path.mkdir(exist_ok=True)

    if not os.path.isdir(path):
        print("ERROR 222476")
        return False

    # Delete only the expected file type (f06) to reduce blast radius of a bug.
    for item_path in path.rglob("*.f06"):
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
        return False

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

    our_output.write(f"************************\n")
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
        

def run_case(mystran_path: Path,
             root_dir: Path,
             fails_dir: Path,
             output_file: io.TextIOWrapper,
             test_case: Definition,
             previous_deck_filename: str) -> bool:
    """Run one test case comparing to a reference f06 and return True for pass or False for fail."""

    working_dir = (root_dir / "working").resolve()

    deck_path = root_dir / "decks" / test_case.deck_filename
    deck_stem = deck_path.stem

    # If it's the same deck as the previous test, reuse the .f06 to save time.
    if test_case.deck_filename != previous_deck_filename:
    
        # Clear working directory
        if not clear_working_directory(working_dir):
            return False

        # Copy deck to working directory
        working_deck_filename_str = shutil.copyfile(deck_path, working_dir / deck_path.name)
        
        # Run Mystran
        with open(os.devnull, "w") as null_output:
            run_program(mystran_path, [working_deck_filename_str], working_dir, null_output, null_output)


    test_f06_path = (working_dir / deck_stem).with_suffix(".f06").resolve()

    result_message = ""

    if test_case.test_type == "mys" or test_case.test_type == "msc":

        if test_case.test_type == "mys":
            reference_dir = (root_dir / "reference_mystran").resolve()
        elif test_case.test_type == "msc":
            reference_dir = (root_dir / "reference_msc").resolve()
        reference_f06_path = (reference_dir / test_case.deck_filename).with_suffix(".f06").resolve()
 
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

    elif test_case.test_type == "chk":

        if test_case.comparison_type == "percent":
            difference_tolerance = abs(test_case.reference_value * test_case.tolerance/100)
        elif test_case.comparison_type == "difference":
            difference_tolerance = test_case.tolerance
        else:
            print("ERROR 862621")
    
        args = ['--oneliner',
                test_case.filter_string + " " + str(test_case.reference_value) + " delta " + str(difference_tolerance),
                test_f06_path
               ]

        # Run f06magic
        fail_count = run_program(root_dir / "f06magic.exe", args, working_dir, output_file, output_file)

    elif test_case.test_type == "pth":

        tree = read_f06_tree(test_f06_path)
        test_values = tree_get(tree, test_case.filter_string)

        fail_count = 0 # Default

        # Do the same comparison on each value separately.
        for test_value in test_values:
        
            if test_value is None:
                fail_count = 1
                result_message = f"No value at {test_case.filter_string}"
                output_file.write(f"************************\n")
                output_file.write(f"{test_f06_path}\n")
                output_file.write(f"Requested path: {test_case.filter_string}\n")
                output_file.write(f"Available paths existing in f06 file:\n")
                write_structure_dense(tree, output_file)
            else:
                if test_case.comparison_type == "percent":
                    if 100 * abs(test_value / test_case.reference_value - 1) > test_case.tolerance:
                        fail_count = 1
                        result_message = f"Is {str(test_value)}, should be {str(test_case.reference_value)} +/- {str(test_case.tolerance)}%"
                elif test_case.comparison_type == "difference":
                    if abs(test_value - test_case.reference_value) > test_case.tolerance:
                        fail_count = 1
                        result_message = f"Is {str(test_value)}, should be {str(test_case.reference_value)} +/- {str(test_case.tolerance)}"
                else:
                    print("ERROR 862621")

    else:
        print(f"ERROR: {test_case.test_type} is invalid.\t{test_case.deck_filename}")
        return False


    pass_fail = "PASS" if fail_count == 0 else "FAILED"
    print(f"{pass_fail}\t{fail_count}\t{test_case.deck_filename} {result_message}")
        
    # Save a copy of failed f06 for inspecting after.
    if fail_count != 0:
        destination = (fails_dir / test_case.deck_filename).with_suffix(".f06").resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Don't overwrite anything to reduce damage caused by wrong-path bugs.
        if not os.path.exists(destination):
            shutil.copyfile(test_f06_path, destination)

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
    output_path = (root_dir / "run_output.txt").resolve()

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