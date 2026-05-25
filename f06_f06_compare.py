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

        # todo remove
        if "ALL-ELEM" in test_case.deck_filename:
            ref_f06.dump(output_file)

        # Subcases
        # ========
        subcases_block = ref_f06.get_layer_0(["SC"])
        for subcase in subcases_block.keys():

            # DISPLACEMENTS TX, TY, TZ
            #-------------------------
            block_path = ["SC",subcase,"DISPLACEMENTS"] # Doesn't include GID here because there may be none if all zero.
            ref_block = ref_f06.get_layer_0(block_path)
            tst_block = tst_f06.get_layer_0(block_path)
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
                            value = ref_f06.get_layer_1(block_path + ["GID",str(gid),component], output_file)
                            maximum = max(maximum, abs(value))
                    output_file.write(f"\tMaximum value = {maximum}\n")
                    # Compare each value normalized by the maximum
                    for gid in gids:
                        for component in ["TX", "TY", "TZ"]:
                            compare(block_path + ["GID",str(gid),component], maximum)

            # APPLIEDFORCES TX, TY, TZ
            #-------------------------
            block_path = ["SC",subcase,"APPLIEDFORCES"] # Doesn't include GID here because there may be none if all zero.
            ref_block = ref_f06.get_layer_0(block_path)
            tst_block = tst_f06.get_layer_0(block_path)
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
                            value = ref_f06.get_layer_1(block_path + ["GID",str(gid),component], output_file)
                            maximum = max(maximum, abs(value))
                    output_file.write(f"\tMaximum value = {maximum}\n")
                    # Compare each value normalized by the maximum
                    for gid in gids:
                        for component in ["TX", "TY", "TZ"]:
                            compare(block_path + ["GID",str(gid),component], maximum)

            # SPCFORCES TX, TY, TZ
            #---------------------
            block_path = ["SC",subcase,"SPCFORCES"] # Doesn't include GID here because there may be none if all zero.
            ref_block = ref_f06.get_layer_0(block_path)
            tst_block = tst_f06.get_layer_0(block_path)
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
                            value = ref_f06.get_layer_1(block_path + ["GID",str(gid),component], output_file)
                            maximum = max(maximum, abs(value))
                    output_file.write(f"\tMaximum value = {maximum}\n")
                    # Compare each value normalized by the maximum
                    for gid in gids:
                        for component in ["TX", "TY", "TZ"]:
                            compare(block_path + ["GID",str(gid),component], maximum)

            # GPFORCE TX, TY, TZ
            #-------------------
            block_path = ["SC",subcase,"GPFORCE"]
            ref_block = ref_f06.get_layer_0(block_path)
            tst_block = tst_f06.get_layer_0(block_path)
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
                                value = ref_f06.get_layer_1(block_path + ["GID",str(gid),force_type,component], output_file)
                                maximum = max(maximum, abs(value))
                        # Identify EIDs from the union of the test and reference sub-blocks for this GID.
                        eid_ref_block = ref_f06.get_layer_0(block_path + ["GID",gid,"EID"])
                        eid_tst_block = tst_f06.get_layer_0(block_path + ["GID",gid,"EID"])
                        eids_ref = set() if eid_ref_block is None else eid_ref_block.keys()
                        eids_tst = set() if eid_tst_block is None else eid_tst_block.keys()
                        for eid in eids_ref | eids_tst:
                            for component in ["TX", "TY", "TZ"]:
                                value = ref_f06.get_layer_1(block_path + ["GID",str(gid),"EID",eid,component], output_file)
                                maximum = max(maximum, abs(value))

                    output_file.write(f"\tMaximum value = {maximum}\n")
                    # Compare each value normalized by the maximum
                    for gid in gids:
                        gid_ref_block = ref_block["GID"][gid]
                        for force_type in ["APPLIED", "SPC", "MPC", "INERTIA"]:
                            for component in ["TX", "TY", "TZ"]:
                                compare(block_path + ["GID",str(gid),force_type,component], maximum)
                        # Identify EIDs from the union of the test and reference sub-blocks for this GID.
                        eid_ref_block = ref_f06.get_layer_0(block_path + ["GID",gid,"EID"])
                        eid_tst_block = tst_f06.get_layer_0(block_path + ["GID",gid,"EID"])
                        eids_ref = set() if eid_ref_block is None else eid_ref_block.keys()
                        eids_tst = set() if eid_tst_block is None else eid_tst_block.keys()
                        for eid in eids_ref | eids_tst:
                            for component in ["TX", "TY", "TZ"]:
                                compare(block_path + ["GID",str(gid),"EID",eid,component], maximum)

            # BARSTRESSES
            # -----------
            block_path = ["SC", subcase, "BARSTRESSES"]
            ref_block = ref_f06.get_layer_0(block_path)
            tst_block = tst_f06.get_layer_0(block_path)
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
                            value = ref_f06.get_layer_1(block_path + ["EID",str(eid),component], output_file)
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
            ref_block = ref_f06.get_layer_0(block_path)
            tst_block = tst_f06.get_layer_0(block_path)
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
                            value = ref_f06.get_layer_1(block_path + ["EID",str(eid),component], output_file)
                            maximum = max(maximum, abs(value))
                    output_file.write(f"\tMaximum value = {maximum}\n")
                    # Compare each value normalized by the maximum
                    for eid in eids:
                        for component in ["MA1", "MA2", "MB1", "MB2", "S1", "S2", "AXIAL", "TORQUE"]:
                            compare(block_path + ["EID",str(eid),component], maximum)

            # RODSTRESSES
            # -----------
            #todo safety margins
            block_path = ["SC", subcase, "RODSTRESSES"]
            ref_block = ref_f06.get_layer_0(block_path)
            tst_block = tst_f06.get_layer_0(block_path)
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
                        for component in ["AXIAL", "TORSIONAL"]:
                            value = ref_f06.get_layer_1(block_path + ["EID",str(eid),component], output_file)
                            maximum = max(maximum, abs(value))
                    output_file.write(f"\tMaximum value = {maximum}\n")
                    # Compare each value normalized by the maximum
                    for eid in eids:
                        for component in ["AXIAL", "TORSIONAL"]:
                            compare(block_path + ["EID",str(eid),component], maximum)


        # Eigenvalues
        #------------
        block_path = ["SC","2","REALEIGENVALUES","MODE"] # Includes MODE here so it's easier to safely enumerate mode numbers.
        ref_block = ref_f06.get_layer_0(block_path)
        tst_block = tst_f06.get_layer_0(block_path)
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
                        value = ref_f06.get_layer_1(block_path + [str(mode),component], output_file)
                        maximum = max(maximum, abs(value))
                output_file.write(f"\tMaximum value = {maximum}\n")
                # Compare each value normalized by the maximum
                for mode in ref_block.keys():
                    for component in ["EIGENVALUE"]:
                        compare(block_path + [str(mode),component], maximum)

        # Modes
        # =====
        modes_block = ref_f06.get_layer_0(["SC","2","MODE"])
        if modes_block is not None:
            for mode in modes_block.keys():
            
                # EIGENVECTORS TX, TY, TZ
                #------------------------
                block_path = ["SC", "2", "MODE", mode, "EIGENVECTOR"]
                ref_block = ref_f06.get_layer_0(block_path)
                tst_block = tst_f06.get_layer_0(block_path)
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
                                value = ref_f06.get_layer_1(block_path + ["GID",str(gid),component], output_file)
                                maximum = max(maximum, abs(value))
                        output_file.write(f"\tMaximum value = {maximum}\n")
                        # Compare each value normalized by the maximum
                        for gid in gids:
                            for component in ["TX", "TY", "TZ"]:
                                compare(block_path + ["GID",str(gid),component], maximum)

                # SPCFORCES TX, TY, TZ
                #---------------------
                block_path = ["SC", "2", "MODE", mode, "SPCFORCES"] # Doesn't include GID here because there may be none if all zero.
                ref_block = ref_f06.get_layer_0(block_path)
                tst_block = tst_f06.get_layer_0(block_path)
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
                                value = ref_f06.get_layer_1(block_path + ["GID",str(gid),component], output_file)
                                maximum = max(maximum, abs(value))
                        output_file.write(f"\tMaximum value = {maximum}\n")
                        # Compare each value normalized by the maximum
                        for gid in gids:
                            for component in ["TX", "TY", "TZ"]:
                                compare(block_path + ["GID",str(gid),component], maximum)

                # GPFORCE TX, TY, TZ
                #-------------------
                block_path = ["SC", "2", "MODE", mode, "GPFORCE"]
                ref_block = ref_f06.get_layer_0(block_path)
                tst_block = tst_f06.get_layer_0(block_path)
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
                                    value = ref_f06.get_layer_1(block_path + ["GID",str(gid),force_type,component], output_file)
                                    maximum = max(maximum, abs(value))
                            # Identify EIDs from the union of the test and reference sub-blocks for this GID.
                            eid_ref_block = ref_f06.get_layer_0(block_path + ["GID",gid,"EID"])
                            eid_tst_block = tst_f06.get_layer_0(block_path + ["GID",gid,"EID"])
                            eids_ref = set() if eid_ref_block is None else eid_ref_block.keys()
                            eids_tst = set() if eid_tst_block is None else eid_tst_block.keys()
                            for eid in eids_ref | eids_tst:
                                for component in ["TX", "TY", "TZ"]:
                                    value = ref_f06.get_layer_1(block_path + ["GID",str(gid),"EID",eid,component], output_file)
                                    maximum = max(maximum, abs(value))

                        output_file.write(f"\tMaximum value = {maximum}\n")
                        # Compare each value normalized by the maximum
                        for gid in gids:
                            gid_ref_block = ref_block["GID"][gid]
                            for force_type in ["APPLIED", "SPC", "MPC", "INERTIA"]:
                                for component in ["TX", "TY", "TZ"]:
                                    compare(block_path + ["GID",str(gid),force_type,component], maximum)
                            # Identify EIDs from the union of the test and reference sub-blocks for this GID.
                            eid_ref_block = ref_f06.get_layer_0(block_path + ["GID",gid,"EID"])
                            eid_tst_block = tst_f06.get_layer_0(block_path + ["GID",gid,"EID"])
                            eids_ref = set() if eid_ref_block is None else eid_ref_block.keys()
                            eids_tst = set() if eid_tst_block is None else eid_tst_block.keys()
                            for eid in eids_ref | eids_tst:
                                for component in ["TX", "TY", "TZ"]:
                                    compare(block_path + ["GID",str(gid),"EID",eid,component], maximum)


                # BARSTRESSES
                # -----------
                block_path = ["SC", "2", "MODE", mode, "BARSTRESSES"]
                ref_block = ref_f06.get_layer_0(block_path)
                tst_block = tst_f06.get_layer_0(block_path)
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
                                value = ref_f06.get_layer_1(block_path + ["EID",str(eid),component], output_file)
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
                ref_block = ref_f06.get_layer_0(block_path)
                tst_block = tst_f06.get_layer_0(block_path)
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
                                value = ref_f06.get_layer_1(block_path + ["EID",str(eid),component], output_file)
                                maximum = max(maximum, abs(value))
                        output_file.write(f"\tMaximum value = {maximum}\n")
                        # Compare each value normalized by the maximum
                        for eid in eids:
                            for component in ["MA1", "MA2", "MB1", "MB2", "S1", "S2", "AXIAL", "TORQUE"]:
                                compare(block_path + ["EID",str(eid),component], maximum)

                # RODSTRESSES
                # -----------
                #todo safety margins
                block_path = ["SC", "2", "MODE", mode, "RODSTRESSES"]
                ref_block = ref_f06.get_layer_0(block_path)
                tst_block = tst_f06.get_layer_0(block_path)
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
                            for component in ["AXIAL", "TORSIONAL"]:
                                value = ref_f06.get_layer_1(block_path + ["EID",str(eid),component], output_file)
                                maximum = max(maximum, abs(value))
                        output_file.write(f"\tMaximum value = {maximum}\n")
                        # Compare each value normalized by the maximum
                        for eid in eids:
                            for component in ["AXIAL", "TORSIONAL"]:
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
