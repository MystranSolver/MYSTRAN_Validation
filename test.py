#!/usr/bin/env python3

import subprocess
import sys
import shutil
import os
import io
from pathlib import Path
from f06csv_to_magic import f06csv_args_to_magic

class Definition:
    def __init__(self):
        self.test_type = ""
        self.deck_filename = ""
        self.filter_string = ""
        self.reference_value = 0.0
        self.percent_threshold = 0.0
        self.percent_allow = 0.0
        self.diff_threshold = 0.0
        self.diff_allow = 0.0


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
            definition.percent_threshold = float(definition_fields_str[3])

            definition.percent_allow = float(definition_fields_str[4])
            definition.diff_threshold = float(definition_fields_str[5])
            definition.diff_allow = float(definition_fields_str[6])
            result.append(definition)
    
    return result


def clear_working_directory(path: Path) -> bool:
    
    # Safety check to avoid clearing the wrong directory.
    if not str(path).endswith("working"):
        print(f"  ERROR: Directory '{path}' not called 'working'.")
        return False

    # Create working directory if it doesn't exist.
    # Helpful because being normally empty, it doesn't get into the Git repo.
    path.mkdir(exist_ok=True)

    if not os.path.isdir(path):
        print(f"  ERROR: '{path}' is not a directory.")
        return False

    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path) or os.path.islink(item_path):
            os.remove(item_path)
        # Don't delete subdirectories to reduce blast radius of 
        # clearing the wrong directory and there shouldn't be any.
    
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
             decks_dir: Path,
             reference_mystran_dir: Path,
             reference_msc_dir: Path,
             working_dir: Path,
             f06magic_path: Path,
             output_file: io.TextIOWrapper,
             test_case: Definition) -> bool:
    """Run one test case comparing to a reference f06 and return True for pass or False for fail."""

    deck_path = decks_dir / test_case.deck_filename
    deck_stem = deck_path.stem

    # Clear working directory
    if not clear_working_directory(working_dir):
        return False
    
    # Copy deck to working directory
    working_deck_filename_str = shutil.copyfile(deck_path, working_dir / deck_path.name)
    
    # Run Mystran
    if run_program(mystran_path, [working_deck_filename_str], working_dir, output_file, output_file) != 0:
        print(f"{test_case.deck_filename} ERROR: from mystran. FAIL")
        return False

    test_f06_path = (working_dir / deck_stem).with_suffix(".f06").resolve()


    if test_case.test_type == "mys" or test_case.test_type == "msc":

        if test_case.test_type == "mys":
            reference_dir = reference_mystran_dir
        elif test_case.test_type == "msc":
            reference_dir = reference_msc_dir
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
max_difference = {str(test_case.diff_allow)}
max_ratio = {str(test_case.percent_allow)}
threshold = {str(test_case.percent_threshold)}
[[comparison]]
name = \"{test_case.deck_filename}\"
reference_f06 = \"reference_file\"
test_f06 = \"test_file\"
extraction = \"{extraction_name}\"
criteria = \"only criteria\"
        """

        #todo two thresholds

        # Escape \ to \\ for TOML
        script = script.replace("\\", "\\\\")
        f06magic_script_path = working_dir / "f06magic_script.toml"
        with open(f06magic_script_path, "w") as script_file:
            script_file.write(script)

        args = [f06magic_script_path]


    elif test_case.test_type == "chk":
    
        range_min = test_case.reference_value * (1 - test_case.percent_allow/100)
        range_max = test_case.reference_value * (1 + test_case.percent_allow/100)
    
        args = ['--oneliner',
                test_case.filter_string + " " + str(range_min) + " to " + str(range_max),
                test_f06_path
               ]

    else:
        print(f"ERROR: {test_case.test_type} is invalid.\t{test_case.deck_filename}")
        return False

    # Run f06magic
    fail_count = run_program(f06magic_path, args, working_dir, output_file, output_file)
    pass_fail = "PASS" if fail_count == 0 else "FAILED"
    print(f"{pass_fail}\t{fail_count}\t{test_case.deck_filename}")

    return fail_count == 0


def main():

    print("==================")
    print("Mystran test suite")
    print("==================")

    # Get Mystran binary path from command line
    if len(sys.argv) > 1:
        mystran_path = Path(sys.argv[1]).resolve()
    else:
        print(f"ERROR: No command line argument. Use the path to the mystran binary.")
        sys.exit(1)

    root_dir = Path(__file__).resolve().parent
    decks_dir = (root_dir / "decks").resolve()
    working_dir = (root_dir / "working").resolve()
    reference_msc_dir = (root_dir / "reference_msc").resolve()
    reference_mystran_dir = (root_dir / "reference_mystran").resolve()
    f06magic_path = (root_dir / "f06magic.exe").resolve()
    definitions_path = (root_dir / "cases.txt").resolve()
    output_path = (root_dir / "run_output.txt").resolve()


    print()

    test_cases = read_definitions(definitions_path)

    success = 0
    count = len(test_cases)

    with open(output_path, "w") as output_file:
        for test_case in test_cases:
            if run_case(mystran_path, decks_dir, reference_mystran_dir, reference_msc_dir, working_dir, f06magic_path, output_file, test_case):
                success += 1

    print()
    exit_code = 0 if success == count and count > 0 else 1
    print(f"{success}/{count} passed -> {"PASS" if exit_code == 0 else "FAIL"}.")
    print()

    # Return exit code 0 for pass and 1 for fail
    sys.exit(exit_code)


if __name__ == "__main__":
    main()