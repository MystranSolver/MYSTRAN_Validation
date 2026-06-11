from pathlib import Path
import io
from case_definition import CaseDefinition
from f06_query import F06Query
import math


INDENT = "  "

def test_bulk(root_dir: Path,
              test_f06_path: Path,
              deck_path: Path,
              output_file: io.TextIOWrapper,
              test_case: CaseDefinition) -> int:

    fail_count = 0
    comparison_count = 0
    worst_error = 0
    worst_path = []

    def compare(title, group_letter, paths):
        nonlocal fail_count
        nonlocal worst_error
        nonlocal worst_path
        nonlocal comparison_count

        maximum = 0.0
        for path in paths:
            value = ref_f06.get_layer_0(path)
            if value is not None:
                maximum = max(maximum, abs(value))
        
        atol = test_case.group_atol.get(group_letter)
        if atol is None:
            # Default tolerance
            if group_letter == "C":
                atol = 1e-12
            else:
                atol = 1e-8 * maximum
       
        batch_comparison_count = 0
        batch_fail_count = 0

        batch_worst_error = 0
        batch_worst_path = None
        batch_worst_tst_value = None
        batch_worst_ref_value = None
    
        # Sort for easier side-by-side comparison between runs
        paths.sort()
    
        # Compare them
        for path in paths:
            batch_comparison_count += 1

            ref_value = ref_f06.get_layer_0(path)
            tst_value = tst_f06.get_layer_0(path)

            # This handles the case of rows of all-zeros being omitted from the .f06 file.
            if tst_value is None:
                tst_value = 0
            if ref_value is None:
                ref_value = 0

            if math.isnan(ref_value):
                # Testing for NaN is boolean
                if math.isnan(tst_value):
                    error = 0 # Force pass
                else:
                    error = float('inf') # Force fail
            else:
                error = abs(tst_value-ref_value)
            
            if error >= batch_worst_error:
                batch_worst_error = error
                batch_worst_path = path
                batch_worst_tst_value = tst_value
                batch_worst_ref_value = ref_value

            if error <= atol:
                pass
            else:
                # Fail is the else clause so that NaN fails.
                batch_fail_count += 1

        if batch_comparison_count > 0:
            pass_fail = "PASS  " if batch_fail_count == 0 else "FAILED"
            fails_text = f"{batch_fail_count}/{batch_comparison_count}".ljust(11)
            output_file.write(f"{INDENT * 1}{pass_fail} {fails_text} {title}")
            maxabs_text = f"Max = {maximum:.0e}".ljust(6+5)
            allow_diff_text = f"Atol {group_letter} = " + f"{atol:.0e}".ljust(5)
            worst_diff_text = f"Worst diff = {batch_worst_error:.0e}".ljust(13+5)
            path_str = "/".join(batch_worst_path)
            tst_str = "Test = " + f"{batch_worst_tst_value:.6e}".rjust(13)
            ref_str = "Ref = "  + f"{batch_worst_ref_value:.6e}".rjust(13)
            output_file.write(f" {maxabs_text}  {allow_diff_text}  {worst_diff_text}  {tst_str}  {ref_str}  {path_str}")
            output_file.write(f"\n")

            # Accumulate summary results for the whole test case.
            if batch_worst_error >= worst_error:
                worst_error = batch_worst_error
                worst_path = batch_worst_path
            comparison_count += batch_comparison_count
            fail_count += batch_fail_count
        

    if test_case.test_type == "mys":
        reference_f06_path = (root_dir / "reference_mystran" / test_case.deck_filename).with_suffix(".F06").resolve()
    elif test_case.test_type == "msc":
        reference_f06_path = (root_dir / "reference_msc" / test_case.deck_filename).with_suffix(".f06").resolve()

    # Read f06 files
    try:
        ref_f06 = F06Query(str(reference_f06_path))
    except FileNotFoundError as e:
        output_file.write(f"{INDENT * 1}{e}\n")
        return 1, 1, "ERROR: Reference solution not found"
    tst_f06 = F06Query(str(test_f06_path))



#   Don't bother comparing eigenvectors because we don't have a reliable way (like MAC) yet.

    ref_subcases_block = ref_f06.get_layer_0(["SC"])
    tst_subcases_block = tst_f06.get_layer_0(["SC"])
    ref_subcase_numbers = ref_subcases_block.keys() if ref_subcases_block is not None else set()
    tst_subcase_numbers = tst_subcases_block.keys() if tst_subcases_block is not None else set()
    for subcase in sorted(ref_subcase_numbers | tst_subcase_numbers):
        prefix = ["SC", subcase]

        # Quantities of the same dimension that should be of similar
        # orders of magnitude are normalized together. This allows greater
        # reative error for values smaller than the maximum in a model,
        # which often happens because of acceptable numerical error.
        # For example, if applied forces balance, all SPCFORCES will be
        # effectively zero so they can't be normalized by themselves.
        # However, since SPCFORCES are in the same normalization group as
        # APPLIEDFORCES, they will be normalized correctly.
        paths_eigenvalues = []
        paths_translation = []
        paths_rotation = []
        paths_force = []
        paths_moment = []
        paths_stress = []
        paths_strain = []
        paths_elas1_stress = []
        paths_bush_stress = []
        paths_bush_strain = []
        paths_shell_force = []
    
        # REALEIGENVALUES
        #----------------
        block_path = prefix + ["REALEIGENVALUES","MODE"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_modes = ref_block.keys() if ref_block is not None else set()
        tst_modes = tst_block.keys() if tst_block is not None else set()
        modes = ref_modes | tst_modes
        for mode in sorted(modes):
            paths_eigenvalues.append(block_path + [str(mode),"EIGENVALUE"])
    
        # DISPLACEMENTS, EIGENVECTOR
        #---------------------------
        for block_name in ["DISPLACEMENTS", "EIGENVECTOR"]:
            block_path = prefix + [block_name, "GID"]
            ref_block = ref_f06.get_layer_0(block_path)
            tst_block = tst_f06.get_layer_0(block_path)
            ref_gids = ref_block.keys() if ref_block is not None else set()
            tst_gids = tst_block.keys() if tst_block is not None else set()
            for gid in ref_gids | tst_gids:
                for component in ["TX", "TY", "TZ"]:
                    paths_translation.append(block_path + [str(gid),component])
                for component in ["RX", "RY", "RZ"]:
                    paths_rotation.append(block_path + [str(gid),component])

        # SPCFORCES, APPLIEDFORCES
        #-------------------------
        for block_name in ["SPCFORCES", "APPLIEDFORCES"]:
            block_path = prefix + [block_name, "GID"]
            ref_block = ref_f06.get_layer_0(block_path)
            tst_block = tst_f06.get_layer_0(block_path)
            ref_gids = ref_block.keys() if ref_block is not None else set()
            tst_gids = tst_block.keys() if tst_block is not None else set()
            for gid in ref_gids | tst_gids:
                for component in ["TX", "TY", "TZ"]:
                    paths_force.append(block_path + [str(gid),component])
                for component in ["RX", "RY", "RZ"]:
                    paths_moment.append(block_path + [str(gid),component])

        # GPFORCE
        #--------
        block_path = prefix + [subcase,"GPFORCE","GID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_gids = ref_block.keys() if ref_block is not None else set()
        tst_gids = tst_block.keys() if tst_block is not None else set()
        for gid in ref_gids | tst_gids:
            for force_type in ["APPLIED", "SPC", "MPC"]:
                for component in ["TX", "TY", "TZ"]:
                    paths_force.append(block_path + [str(gid),force_type,component])
                for component in ["RX", "RY", "RZ"]:
                    paths_moment.append(block_path + [str(gid),force_type,component])
            # Identify EIDs from the union of the test and reference sub-blocks for this GID.
            eid_ref_block = ref_f06.get_layer_0(block_path + [gid,"EID"])
            eid_tst_block = tst_f06.get_layer_0(block_path + [gid,"EID"])
            eids_ref = eid_ref_block.keys() if eid_ref_block is not None else set()
            eids_tst = eid_tst_block.keys() if eid_tst_block is not None else set() 
            for eid in eids_ref | eids_tst:
                for component in ["TX", "TY", "TZ"]:
                    paths_force.append(block_path + [str(gid),"EID",eid,component])
                for component in ["RX", "RY", "RZ"]:
                    paths_moment.append(block_path + [str(gid),"EID",eid,component])

        # ELAS1FORCES
        # -----------
        block_path = prefix + ["ELAS1FORCES", "EID"]
        ref_block = ref_f06.get_layer_1(block_path)
        tst_block = tst_f06.get_layer_1(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            paths_force.append(block_path + [str(eid)])

        # ELAS1STRESSES
        # -------------
        block_path = prefix + ["ELAS1STRESSES", "EID"]
        ref_block = ref_f06.get_layer_1(block_path)
        tst_block = tst_f06.get_layer_1(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        # CELAS1 stresses are not included in the stress normalization
        # group because they may represent something different from stress
        # by choice of stress recovery coefficient.
        for eid in ref_eids | tst_eids:
            paths_elas1_stress.append(block_path + [str(eid)])

        # RODFORCES
        # ---------
        block_path = prefix + ["RODFORCES", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            paths_force.append(block_path + [str(eid),"AXIAL"])
            paths_moment.append(block_path + [str(eid),"TORQUE"])

        # RODSTRESSES
        # -----------
        block_path = prefix + ["RODSTRESSES", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            for component in ["AXIAL", "TORSIONAL"]:
                paths_stress.append(block_path + [str(eid),component])

        # BARFORCES
        # ---------
        block_path = prefix + ["BARFORCES", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            for component in ["S1", "S2", "AXIAL"]:
                paths_force.append(block_path + [str(eid),component])
            for component in ["MA1", "MA2", "MB1", "MB2", "TORQUE"]:
                paths_moment.append(block_path + [str(eid),component])

        # BARSTRESSES
        # -----------
        block_path = prefix + ["BARSTRESSES", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            for component in ["SA1", "SA2", "SA3", "SA4", "SB1", "SB2", "SB3", "SB4", "AXIAL"]:
                paths_stress.append(block_path + [str(eid), component])

        # BUSHFORCES
        # ----------
        block_path = prefix + ["BUSHFORCES", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            for component in ["TX", "TY", "TZ"]:
                paths_force.append(block_path + [str(eid),component])
            for component in ["RX","RY","RZ"]:
                paths_moment.append(block_path + [str(eid),component])

        # BUSHSTRESSES
        # ------------
        block_path = prefix + ["BUSHSTRESSES", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        # CBUSH stresses are not included in the stress normalization
        # group because they may represent something different from stress
        # by choice of stress recovery coefficient.
        for eid in ref_eids | tst_eids:
            for component in ["TX", "TY", "TZ", "RX", "RY", "RZ"]:
                paths_bush_stress.append(block_path + [str(eid), component])

        # BUSHSTRAINS
        # -----------
        block_path = prefix + ["BUSHSTRAINS", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            for component in ["TX", "TY", "TZ", "RX", "RY", "RZ"]:
                paths_bush_strain.append(block_path + [str(eid), component])

        # SHELLFORCES
        # -----------
        block_path = prefix + ["SHELLFORCES", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            for corner in ["0", "1", "2", "3", "4"]:
                for component in ["NXX", "NYY", "NXY", "QX", "QY"]:
                    paths_shell_force.append(block_path + [str(eid), "CORNER", corner, component])
        for eid in ref_eids | tst_eids:
            for corner in ["0", "1", "2", "3", "4"]:
                for component in ["MXX","MYY","MXY"]:
                    paths_force.append(block_path + [str(eid), "CORNER", corner, component])

        # SHELLSTRESSES
        # -------------
        block_path = prefix + ["SHELLSTRESSES", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            for corner in ["0", "1", "2", "3", "4"]:
                for z in ["Z1", "Z2"]:
                    for component in ["XX", "YY", "XY", "VONMISES"]:
                        paths_stress.append(block_path + [str(eid), "CORNER", corner, z, component])
#                for component in ["ZX", "YZ"]:
#                    paths_stress.append(block_path + [str(eid), "CORNER", corner, component])

        # SHELLSTRAINS
        # ------------
        block_path = prefix + ["SHELLSTRAINS", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            for corner in ["0", "1", "2", "3", "4"]:
                for z in ["Z1", "Z2"]:
                    for component in ["XX", "YY", "XY", "VONMISES"]:
                        paths_strain.append(block_path + [str(eid), "CORNER", corner, z, component])
#                for component in ["ZX", "YZ"]:
#                    paths_strain.append(block_path + [str(eid), "CORNER", corner, component])

        # SOLIDSTRESSES
        # -------------
        block_path = prefix + ["SOLIDSTRESSES", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            for corner in ["0", "1", "2", "3", "4", "5", "6", "7", "8"]:
                for component in ["XX", "YY", "XX", "XY", "YZ", "ZX", "VONMISES"]:
                    paths_stress.append(block_path + [str(eid), "CORNER", corner, component])

        # SOLIDSTRAINS
        # ------------
        block_path = prefix + ["SOLIDSTRAINS", "EID"]
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        for eid in ref_eids | tst_eids:
            for corner in ["0", "1", "2", "3", "4", "5", "6", "7", "8"]:
                for component in ["XX", "YY", "XX", "XY", "YZ", "ZX", "VONMISES"]:
                    paths_strain.append(block_path + [str(eid), "CORNER", corner, component])


        subcase_name = "/".join(prefix)
        compare(f"{subcase_name} Eigenvalues    ", "A", paths_eigenvalues)
        compare(f"{subcase_name} Translations   ", "B", paths_translation)
        compare(f"{subcase_name} Rotations      ", "C", paths_rotation)
        compare(f"{subcase_name} Forces         ", "D", paths_force)
        compare(f"{subcase_name} Moments        ", "E", paths_moment)
        compare(f"{subcase_name} Stresses       ", "F", paths_stress)
        compare(f"{subcase_name} Strains        ", "G", paths_strain)
        compare(f"{subcase_name} ELAS1 stresses ", "H", paths_elas1_stress)
        compare(f"{subcase_name} BUSH stresses  ", "I", paths_bush_stress)
        compare(f"{subcase_name} BUSH strains   ", "J", paths_bush_strain)
        compare(f"{subcase_name} Shell forces   ", "K", paths_shell_force)
   
   
    if fail_count > 0:
        message = f"Error = {worst_error:.2g}\t{ "/".join(worst_path)}"
    else:
        message = ""


    return fail_count, comparison_count, message
