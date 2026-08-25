#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np


RUN_PATTERN = re.compile(r"RUN(\d+)")
REQUIRED_BRANCHES = ("recx", "recy", "recz", "m_QTEn")


def extract_run_number(path: str) -> int:
    match = RUN_PATTERN.search(path)
    return int(match.group(1)) if match else -1


def load_run_files(manifest_path: str) -> Dict[int, List[str]]:
    run_files: Dict[int, List[str]] = defaultdict(list)
    seen = set()

    with open(manifest_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if not line.endswith(".root"):
                continue
            if line in seen:
                continue

            run = extract_run_number(line)
            if run < 0:
                print(f"[Warning] Failed to extract run number from: {line}")
                continue

            run_files[run].append(line)
            seen.add(line)

    for run in run_files:
        run_files[run].sort()
    return dict(sorted(run_files.items()))


def ensure_required_branches(chain) -> bool:
    missing = [name for name in REQUIRED_BRANCHES if not chain.GetBranch(name)]
    if missing:
        print(f"[Error] Missing required branches: {', '.join(missing)}")
        return False
    return True


def convert_run(run: int, files: List[str], out_dir: str) -> bool:
    import ROOT

    chain = ROOT.TChain("TRec")
    for path in files:
        chain.Add(path)

    if chain.GetEntries() <= 0:
        print(f"[Warning] Run {run}: no entries found")
        return False

    if not ensure_required_branches(chain):
        print(f"[Warning] Run {run}: skipped due to missing branches")
        return False

    chain.SetBranchStatus("*", 0)
    for branch_name in REQUIRED_BRANCHES:
        chain.SetBranchStatus(branch_name, 1)

    recx = []
    recy = []
    recz = []
    energy = []

    entries = chain.GetEntries()
    for entry in range(entries):
        chain.GetEntry(entry)
        recx.append(float(chain.recx))
        recy.append(float(chain.recy))
        recz.append(float(chain.recz))
        energy.append(float(chain.m_QTEn))

    output_path = os.path.join(out_dir, f"SelectionResult_RUN{run}.npz")
    np.savez_compressed(
        output_path,
        calib_omilrec_x=np.asarray(recx, dtype=np.float64),
        calib_omilrec_y=np.asarray(recy, dtype=np.float64),
        calib_omilrec_z=np.asarray(recz, dtype=np.float64),
        calib_omilrec_energy=np.asarray(energy, dtype=np.float64),
    )

    print(
        f"[Output] Run {run}: {len(energy)} entries from {len(files)} files -> {output_path}"
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert TRec reconstruction ROOT files into per-run NPZ files."
    )
    parser.add_argument(
        "--filelist",
        default="/junofs/users/wuwenjie/evtrec_performance/performance/dingxf_omilrecv2_filelist.txt",
        help="Manifest text file with one ROOT path per line.",
    )
    parser.add_argument(
        "--outdir",
        default="/junofs/users/wuwenjie/evtrec_performance/performance/dingxf_omilrecv2_plots/data",
        help="Output directory for merged per-run NPZ files.",
    )
    parser.add_argument(
        "--runs",
        nargs="*",
        type=int,
        default=None,
        help="Optional list of run numbers to convert.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.filelist):
        raise FileNotFoundError(f"File list not found: {args.filelist}")

    os.makedirs(args.outdir, exist_ok=True)
    run_files = load_run_files(args.filelist)
    if not run_files:
        raise RuntimeError(f"No valid ROOT files found in: {args.filelist}")

    selected_runs: Optional[set] = set(args.runs) if args.runs else None
    converted = 0
    skipped = 0

    for run, files in run_files.items():
        if selected_runs is not None and run not in selected_runs:
            continue
        if convert_run(run, files, args.outdir):
            converted += 1
        else:
            skipped += 1

    print(f"[Summary] Converted runs: {converted}, skipped runs: {skipped}")


if __name__ == "__main__":
    main()
