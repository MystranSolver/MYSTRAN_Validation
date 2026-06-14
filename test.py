#!/usr/bin/env python3

import subprocess
import sys
import os
from shutil import copyfile
from io import TextIOWrapper
from pathlib import Path
from test_bulk import test_bulk
from test_individual_values import test_individual_values
from case_definition import CaseDefinition
from datetime import datetime
import re

# Error messages with a code like ERROR 229606 are for bugs/corruption in the test suite.
# Error messages with explanations are for errors in test case definitions/usage.

INDENT = "  "
null_output = open(os.devnull, "w")

messages = []

def show_message(message):
    print(message)
    messages.append(message)


def fatal(message):
    print(message)
    sys.exit(1)


def read_definitions(definitions_path: Path) -> list[CaseDefinition]:

    def read_tolerance(field):
        nonlocal definition
        if "%" in field:
            definition.comparison_type = "percent"
        else:
            definition.comparison_type = "difference"
        definition.tolerance = float(field.replace("%",""))


    def parse_variables(s: str) -> dict[str, float]:
        """
        Parse a string of variable assignments like "A = 1e-9 C= -0.000123 B = 3.4E-6".
        
        - Variable names must be single uppercase letters (A-Z)
        - Whitespace around '=' is ignored
        - Numbers can be in any common float format (decimal, scientific notation, negative)
        
        Returns a dict mapping variable names to float values.
        Raises ValueError if the string contains invalid tokens.
        """
        pattern = r'([A-Z])\s*=\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)'
        
        matches = re.findall(pattern, s)
        
        # Verify no unrecognised content remains (strip all valid matches and whitespace)
        leftover = re.sub(pattern, '', s).strip()
        if leftover:
            raise ValueError(f"Unrecognised content in input: {leftover!r}")
        
        return {var: float(value) for var, value in matches}


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
                fatal(f"ERROR: Not enough fields in\n{definition_str}")
            definition = CaseDefinition()
            definition.test_type = definition_fields_str[0]
            definition.deck_filename = definition_fields_str[1]
            match definition.test_type:
                case "mys" | "msc":
                    if len(definition_fields_str) > 2 and definition_fields_str[2] != "":
                        definition.group_atol = parse_variables(definition_fields_str[2])
                    if len(definition_fields_str) > 3:
                        definition.knownfail = definition_fields_str[3].startswith("KNOWNFAIL")
                case "pth":
                    if len(definition_fields_str) < 6:
                        show_message(f"ERROR: Not enough fields in\n{definition_str}")
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
        fatal("ERROR 235476")

    # Create fails directory if it doesn't exist.
    path.mkdir(exist_ok=True)

    if not os.path.isdir(path):
        fatal("ERROR 222476")

    # Delete only the expected file type (F06) to reduce blast radius of a bug.
    for item_path in path.rglob("*.F06"):
        if item_path.is_file():
            item_path.unlink()
    
    return True


def clear_working_directory(path: Path) -> bool:
    
    # Safety check to avoid clearing the wrong directory.
    if path.stem != "working":
        fatal("ERROR 911875")

    # Create working directory if it doesn't exist.
    path.mkdir(exist_ok=True)

    if not os.path.isdir(path):
        fatal("ERROR 911279")

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
        

def run_case(mystran_path: Path,
             root_dir: Path,
             fails_dir: Path,
             output_file: TextIOWrapper,
             test_case: CaseDefinition,
             previous_deck_filename: str) -> bool:
    """Run one test case return True for pass or False for fail."""

    working_dir = (root_dir / "working").resolve()

    deck_path = root_dir / "decks" / test_case.deck_filename

    # If it's the same deck as the previous test, reuse the .f06 to save time.
    if test_case.deck_filename != previous_deck_filename:

        output_file.write(f"\n")
    
        # Clear working directory
        if not clear_working_directory(working_dir):
            return False

        # Copy deck to working directory
        try:
            working_deck_filename_str = copyfile(deck_path, working_dir / deck_path.name)

            # Run Mystran
            run_program(mystran_path, [working_deck_filename_str], working_dir, null_output, null_output)

        except Exception as e:
            output_file.write(f"{INDENT * 0}ERROR: {e}\n")
            fail_count = 1

    test_f06_path = (working_dir / Path(test_case.deck_filename).name).with_suffix(".F06").resolve()

    if test_case.test_type in ["mys", "msc"]:

        output_file.write(f"{INDENT * 0}{test_case.test_type}; {test_case.deck_filename}\n")
        #todo write atols
        fail_count, comparison_count, message = test_bulk(root_dir, test_f06_path, deck_path, output_file, test_case)
        count_suffix = "/" + str(comparison_count)

    elif test_case.test_type == "pth":

        output_file.write(f"{INDENT * 0}{test_case.test_type}; {test_case.deck_filename}; {test_case.filter_string}; {test_case.operation}; {test_case.reference_value}; {test_case.tolerance}{test_case.tolerance_suffix()}\n")

        fail_count, comparison_count, message = test_individual_values(root_dir, test_f06_path, deck_path, output_file, test_case)
        count_suffix = "/" + str(comparison_count)
  
    else:
        show_message(f"ERROR: {test_case.test_type} is invalid.\t{test_case.deck_filename}")
        return False

    # Known fails must fail.
    if test_case.knownfail:
        if fail_count > 0:
            fail_count = 0
            message = f"\tKNOWNFAIL failed as expected"
        else:
            fail_count += 1
            message = f"\tKNOWNFAIL passed"

    pass_fail = "PASS" if fail_count == 0 else "FAILED"
    fails_text = f"{fail_count}{count_suffix}".ljust(10)
    show_message(f"{pass_fail}\t{fails_text}{test_case.deck_filename.ljust(50)} {message}")
        
    # Save a copy of failed F06 for inspecting after.

    if fail_count != 0:
        destination = (fails_dir / test_case.deck_filename).with_suffix(".F06").resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Don't overwrite anything to reduce damage caused by wrong-path bugs.
        if not os.path.exists(destination):
            try:
                copyfile(test_f06_path, destination)
            except Exception:
                # Swallow exception if file didn't exist or whatever.
                pass

    return fail_count == 0




def main():

    show_message("========================")
    show_message("Mystran validation suite")
    show_message("========================")

    show_message(datetime.now().isoformat())

    # Get Mystran binary path from command line
    if len(sys.argv) > 1:
        mystran_path = Path(sys.argv[1]).resolve()
    else:
        fatal(f"ERROR: No command line argument. Use the path to the mystran binary.")

    root_dir = Path(__file__).resolve().parent
    fails_dir = root_dir / "fails"
    definitions_path = (root_dir / "cases.txt").resolve()
    output_path = (root_dir / "output.txt").resolve()

    # Clear any fail outputs from the previous run.
    clear_fails_directory(fails_dir)

    show_message(str(mystran_path))
    show_message("")

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
        show_message("="*len(final_summary))
        show_message(final_summary)
        show_message("="*len(final_summary))
        output_file.write("\n".join(messages))

    # Return exit code 0 for pass and 1 for fail
    sys.exit(exit_code)


if __name__ == "__main__":
    main()