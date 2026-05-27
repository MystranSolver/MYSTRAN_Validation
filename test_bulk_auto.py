from pathlib import Path
import io
from case_definition import CaseDefinition
from f06_query import F06Query
import math


INDENT = "  "

def test_bulk_auto(root_dir: Path,
                   test_f06_path: Path,
                   deck_path: Path,
                   output_file: io.TextIOWrapper,
                   test_case: CaseDefinition) -> int:

    tolerance = 2e-5 # in percent
    fail_count = 0
    comparison_count = 0
    worst_error = 0
    worst_path = ""

    def compare(paths):
        nonlocal fail_count
        nonlocal worst_error
        nonlocal worst_path
        nonlocal comparison_count

        # Find the maximum of all values we'll be testing in the block
        maximum = 0
        for path in paths:
            value = ref_f06.get_layer_0(path)
            if value is not None:
                maximum = max(maximum, abs(value))
        output_file.write(f"\t{len(paths)} values\tMaximum value = {maximum}\n")

        batch_comparison_count = 0
        batch_fail_count = 0
    
        # Compare them
        for path in paths:
            batch_comparison_count += 1

            ref_value = ref_f06.get_layer_2(path, output_file)
            tst_value = tst_f06.get_layer_2(path, output_file)

            if tst_value is None:
                tst_value = 0
            if ref_value is None:
                ref_value = 0

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
                batch_fail_count += 1
                tst_str = "None" if tst_value is None else f"{tst_value}"
                ref_str = "None" if ref_value is None else f"{ref_value:.9g}"
                output_file.write(f"{INDENT * 3}FAILED\tError = {error:.2g}% ({tolerance}%)\t{path_str}\tValue = {tst_str} ({ref_str})\n")

        output_file.write(f"{INDENT * 3}{batch_fail_count}/{batch_comparison_count}\n")

        comparison_count += batch_comparison_count
        fail_count += batch_fail_count
        

    if test_case.test_type == "my2":
        reference_f06_path = (root_dir / "reference_mystran" / test_case.deck_filename).with_suffix(".F06").resolve()
    elif test_case.test_type == "ms2":
        reference_f06_path = (root_dir / "reference_msc" / test_case.deck_filename).with_suffix(".f06").resolve()

    # Read f06 files
    ref_f06 = F06Query(str(reference_f06_path))
    tst_f06 = F06Query(str(test_f06_path))

    # Subcases
    # ========
    subcases_block = ref_f06.get_layer_1(["SC"])
    for subcase in subcases_block.keys():

        # DISPLACEMENTS, APPLIEDFORCES, SPCFORCES
        #----------------------------------------
        for block_name in ["DISPLACEMENTS", "APPLIEDFORCES", "SPCFORCES"]:
            block_path = ["SC", subcase, block_name, "GID"]
            output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
            ref_block = ref_f06.get_layer_0(block_path)
            tst_block = tst_f06.get_layer_0(block_path)
            ref_gids = ref_block.keys() if ref_block is not None else set()
            tst_gids = tst_block.keys() if tst_block is not None else set()
            paths = []
            for gid in ref_gids | tst_gids:
                for component in ["TX", "TY", "TZ"]:
                    paths.append(block_path + [str(gid),component])
            compare(paths)
            paths = []
            for gid in ref_gids | tst_gids:
                for component in ["RX", "RY", "RZ"]:
                    paths.append(block_path + [str(gid),component])
            compare(paths)

        # GPFORCE
        #--------
        block_path = ["SC",subcase,"GPFORCE","GID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_gids = ref_block.keys() if ref_block is not None else set()
        tst_gids = tst_block.keys() if tst_block is not None else set()
        # Identify EIDs from the union of the test and reference sub-blocks for each GID.
        gid_eids = {}
        for gid in ref_gids | tst_gids:
            eid_ref_block = ref_f06.get_layer_0(block_path + [gid,"EID"])
            eid_tst_block = tst_f06.get_layer_0(block_path + [gid,"EID"])
            eids_ref = eid_ref_block.keys() if eid_ref_block is not None else set()
            eids_tst = eid_tst_block.keys() if eid_tst_block is not None else set() 
            gid_eids[gid] = eids_ref | eids_tst
        paths = []
        for gid in ref_gids | tst_gids:
            for force_type in ["APPLIED", "SPC", "MPC", "INERTIA"]:
                for component in ["TX", "TY", "TZ"]:
                    paths.append(block_path + [str(gid),force_type,component])
            for eid in gid_eids[gid]:
                for component in ["RX", "RY", "RZ"]:
                    paths.append(block_path + [str(gid),"EID",eid,component])
        compare(paths)
        paths = []
        for gid in ref_gids | tst_gids:
            for force_type in ["APPLIED", "SPC", "MPC", "INERTIA"]:
                for component in ["RX", "RY", "RZ"]:
                    paths.append(block_path + [str(gid),force_type,component])
            for eid in gid_eids[gid]:
                for component in ["RX", "RY", "RZ"]:
                    paths.append(block_path + [str(gid),"EID",eid,component])
        compare(paths)

        # BARSTRESSES
        # -----------
        block_path = ["SC", subcase, "BARSTRESSES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            for component in ["SA1", "SA2", "SA3", "SA4", "SB1", "SB2", "SB3", "SB4", "AXIAL"]:
                paths.append(block_path + [str(eid), component])
        compare(paths)

        # BARFORCES
        # -----------
        block_path = ["SC", subcase, "BARFORCES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            for component in ["MA1", "MA2", "MB1", "MB2", "TORQUE"]:
                paths.append(block_path + [str(eid),component])
        compare(paths)
        paths = []
        for eid in ref_eids | tst_eids:
            for component in ["S1", "S2", "AXIAL"]:
                paths.append(block_path + [str(eid),component])
        compare(paths)

        # RODSTRESSES
        # -----------
        #todo safety margins
        block_path = ["SC", subcase, "RODSTRESSES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            for component in ["AXIAL", "TORSIONAL"]:
                paths.append(block_path + [str(eid),component])
        compare(paths)

        # RODFORCES
        # ---------
        block_path = ["SC", subcase, "RODFORCES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            paths.append(block_path + [str(eid),"AXIAL"])
        compare(paths)
        paths = []
        for eid in ref_eids | tst_eids:
            paths.append(block_path + [str(eid),"TORQUE"])
        compare(paths)

        # ELAS1STRESSES
        # -------------
        block_path = ["SC", subcase, "ELAS1STRESSES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_1(block_path)
        tst_block = tst_f06.get_layer_1(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            paths.append(block_path + [str(eid)])
        compare(paths)

        # ELAS1FORCES
        # -----------
        block_path = ["SC", subcase, "ELAS1FORCES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_1(block_path)
        tst_block = tst_f06.get_layer_1(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            paths.append(block_path + [str(eid)])
        compare(paths)



    # Eigenvalues
    #------------
    block_path = ["SC","2","REALEIGENVALUES","MODE"]
    output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
    ref_block = ref_f06.get_layer_0(block_path)
    tst_block = tst_f06.get_layer_0(block_path)
    ref_modes = ref_block.keys() if ref_block is not None else set()
    tst_modes = tst_block.keys() if tst_block is not None else set()
    modes = ref_modes | tst_modes
    paths = []
    for mode in modes:
        paths.append(block_path + [str(mode),"EIGENVALUE"])
    compare(paths)


    # Modes
    # =====
    modes_block = ref_f06.get_layer_1(["SC","2","MODE"])
    if modes_block is None:
        modes = []
    else:
        modes = modes_block.keys()
    for mode in modes:

        # DISPLACEMENTS, APPLIEDFORCES, SPCFORCES, EIGENVECTOR
        #-----------------------------------------------------
        for block_name in ["DISPLACEMENTS", "APPLIEDFORCES", "SPCFORCES", "EIGENVECTOR"]:
            block_path = ["SC", "2", "MODE", mode, block_name, "GID"]
            output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
            ref_block = ref_f06.get_layer_0(block_path)
            tst_block = tst_f06.get_layer_0(block_path)
            ref_gids = ref_block.keys() if ref_block is not None else set()
            tst_gids = tst_block.keys() if tst_block is not None else set()
            paths = []
            for gid in ref_gids | tst_gids:
                for component in ["TX", "TY", "TZ"]:
                    paths.append(block_path + [str(gid),component])
            compare(paths)
            paths = []
            for gid in ref_gids | tst_gids:
                for component in ["RX", "RY", "RZ"]:
                    paths.append(block_path + [str(gid),component])
            compare(paths)

        # GPFORCE
        #--------
        block_path = ["SC", "2", "MODE", mode, "GPFORCE", "GID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_gids = ref_block.keys() if ref_block is not None else set()
        tst_gids = tst_block.keys() if tst_block is not None else set()
        # Identify EIDs from the union of the test and reference sub-blocks for each GID.
        gid_eids = {}
        for gid in ref_gids | tst_gids:
            eid_ref_block = ref_f06.get_layer_0(block_path + [gid,"EID"])
            eid_tst_block = tst_f06.get_layer_0(block_path + [gid,"EID"])
            eids_ref = eid_ref_block.keys() if eid_ref_block is not None else set()
            eids_tst = eid_tst_block.keys() if eid_tst_block is not None else set() 
            gid_eids[gid] = eids_ref | eids_tst
        paths = []
        for gid in ref_gids | tst_gids:
            for force_type in ["APPLIED", "SPC", "MPC", "INERTIA"]:
                for component in ["TX", "TY", "TZ"]:
                    paths.append(block_path + [str(gid),force_type,component])
            for eid in gid_eids[gid]:
                for component in ["RX", "RY", "RZ"]:
                    paths.append(block_path + [str(gid),"EID",eid,component])
        compare(paths)
        paths = []
        for gid in ref_gids | tst_gids:
            for force_type in ["APPLIED", "SPC", "MPC", "INERTIA"]:
                for component in ["RX", "RY", "RZ"]:
                    paths.append(block_path + [str(gid),force_type,component])
            for eid in gid_eids[gid]:
                for component in ["RX", "RY", "RZ"]:
                    paths.append(block_path + [str(gid),"EID",eid,component])
        compare(paths)
      
        # BARSTRESSES
        # -----------
        block_path = ["SC", "2", "MODE", mode, "BARSTRESSES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            for component in ["SA1", "SA2", "SA3", "SA4", "SB1", "SB2", "SB3", "SB4", "AXIAL"]:
                paths.append(block_path + [str(eid), component])
        compare(paths)

        # BARFORCES
        # -----------
        block_path = ["SC", "2", "MODE", mode, "BARFORCES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            for component in ["MA1", "MA2", "MB1", "MB2", "TORQUE"]:
                paths.append(block_path + [str(eid),component])
        compare(paths)
        paths = []
        for eid in ref_eids | tst_eids:
            for component in ["S1", "S2", "AXIAL"]:
                paths.append(block_path + [str(eid),component])
        compare(paths)

        # RODSTRESSES
        # -----------
        #todo safety margins
        block_path = ["SC", "2", "MODE", mode, "RODSTRESSES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            for component in ["AXIAL", "TORSIONAL"]:
                paths.append(block_path + [str(eid),component])
        compare(paths)

        # RODFORCES
        # ---------
        block_path = ["SC", "2", "MODE", mode, "RODFORCES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            paths.append(block_path + [str(eid),"AXIAL"])
        compare(paths)
        paths = []
        for eid in ref_eids | tst_eids:
            paths.append(block_path + [str(eid),"TORQUE"])
        compare(paths)

        # ELAS1STRESSES
        # -------------
        block_path = ["SC", "2", "MODE", mode, "ELAS1STRESSES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_1(block_path)
        tst_block = tst_f06.get_layer_1(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            paths.append(block_path + [str(eid)])
        compare(paths)

        # ELAS1FORCES
        # -----------
        block_path = ["SC", "2", "MODE", mode, "ELAS1FORCES", "EID"]
        output_file.write(f"{INDENT * 2}{"/".join(block_path)}")
        ref_block = ref_f06.get_layer_1(block_path)
        tst_block = tst_f06.get_layer_1(block_path)
        ref_eids = ref_block.keys() if ref_block is not None else set()
        tst_eids = tst_block.keys() if tst_block is not None else set()
        paths = []
        for eid in ref_eids | tst_eids:
            paths.append(block_path + [str(eid)])
        compare(paths)

   
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
