#!/usr/bin/env python3
"""
Main pipeline: run fits for all sources, collect results, draw ENL-style plot.
"""
from __future__ import annotations

import os
import sys
import time
import argparse
from pathlib import Path

_PROJ_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJ_ROOT))
for _p in ["src", "fitters", "smx_ana", "pipeline"]:
    _path = str(_PROJ_ROOT / _p)
    if _path not in sys.path:
        sys.path.insert(0, _path)

os.environ["MPLCONFIGDIR"] = str(_PROJ_ROOT / "TMP" / "matplotlib")
os.environ["NUMBA_CACHE_DIR"] = str(_PROJ_ROOT / "TMP" / "numba")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import contextlib

from config.paths import (
    PROJECT_ROOT, DATA_INPUT_PATH, SOURCES, RUN_INFO_CSV,
    A_JUNO_REF, B_JUNO_REF, COLORS, MARKERS,
)
from src.run_logger import RunLogger
from input_loader import normalize_event_input

# CLI args for agent-driven runs
_parser = argparse.ArgumentParser(description="JUNO calibration fitter pipeline")
_parser.add_argument("--launched-by", default="script", choices=["script", "agent"])
_parser.add_argument("--agent-name", default="")
_parser.add_argument("--agent-version", default="")
_parser.add_argument("--agent-workflow", default="")
_parser.add_argument("--input-dir", default=None,
                     help="directory containing Run{N}_SelectionResult.npz "
                          "(overrides config DATA_INPUT_PATH)")
_parser.add_argument("--out-dir", default=None,
                     help="output root (default: <project>/output/<timestamp>); "
                          "when given, writes directly into this directory")
_args, _unknown = _parser.parse_known_args()

# Overrides: input data dir + output root
if _args.input_dir:
    DATA_INPUT_PATH = _args.input_dir
    print(f"[Info] DATA_INPUT_PATH overridden: {DATA_INPUT_PATH}")

# Output directory
_timestamp = time.strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = (Path(_args.out_dir) if _args.out_dir
              else PROJECT_ROOT / "output" / _timestamp)
OUTPUT_RES_DIR = OUTPUT_DIR / "results"
OUTPUT_FIG_DIR = OUTPUT_DIR / "figures"
OUTPUT_RES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FIG_DIR.mkdir(parents=True, exist_ok=True)
print(f"[Info] Output directory: {OUTPUT_DIR}")
sys.stdout.flush()

# ================= Main with context manager =================
with RunLogger(
    output_dir=OUTPUT_DIR,
    project_root=PROJECT_ROOT,
    launched_by=_args.launched_by,
) as logger:

    # Record launch command and capture console output
    logger.record_command(sys.argv)
    _tee_stdout = logger.ConsoleTee(sys.stdout, logger)
    _tee_stderr = logger.ConsoleTee(sys.stderr, logger)

    if _args.launched_by == "agent" and _args.agent_name:
        logger.set_agent_info(
            agent_name=_args.agent_name,
            agent_version=_args.agent_version,
            workflow_description=_args.agent_workflow,
        )

    logger.save_config_snapshot()

    results: dict[str, dict] = {}
    total_start = time.time()

    with contextlib.redirect_stdout(_tee_stdout), contextlib.redirect_stderr(_tee_stderr):
        for src_name, run_id, e_true, fitter_type in SOURCES:
            input_path = f"{DATA_INPUT_PATH}/Run{run_id}_SelectionResult.npz"
            if not os.path.exists(input_path):
                print(f"[Warning] {src_name} RUN{run_id}: data not found at {input_path}, skip")
                logger.add_source_record(
                    src_name=src_name, run_id=run_id, e_true=e_true,
                    fitter_type=fitter_type, fitter_file="N/A",
                    input_path=input_path, output_files={},
                    status="skipped", error_message=f"Data file not found: {input_path}",
                )
                continue

            print(f"\n{'='*60}")
            print(f"[{src_name}] RUN{run_id} (E_true={e_true} MeV)")
            print(f"[{src_name}] Input: {input_path}")
            sys.stdout.flush()

            event_data = None
            try:
                event_data = normalize_event_input(input_path, src_name)
            except Exception as e:
                print(f"[Warning] Could not load event data for logging: {e}")

            t0 = time.time()
            output_stem = f"RUN{run_id}_{src_name}"
            source_status = "success"
            source_error = None
            outputs = {}
            fitter_file = "src/MCBased_Fitter.py"
            fitter_params = {}

            try:
                if fitter_type == "fast" and src_name == "Ge68":
                    from src.FastGe68Fitter import run_fast_ge68_fitter
                    outputs = run_fast_ge68_fitter(
                        run_id=run_id, input_path=input_path,
                        output_fig_dir=str(OUTPUT_FIG_DIR),
                        output_res_dir=str(OUTPUT_RES_DIR),
                        output_stem=output_stem, enable_c14=True,
                        c14_convolver="fft", results_only=False,
                    )
                    fitter_file = "src/FastGe68Fitter.py"
                    fitter_params = {
                        "template_path": str(PROJECT_ROOT / "fitters" / "Ge68_MCbased_BKG_v4.npz"),
                        "bins_fit": "arange(0.3, 2.0, 0.004)",
                        "x_limit": 0.51,
                        "enable_c14": True,
                        "c14_convolver": "fft",
                        "fixed_params": {"E_scale": "auto", "a": 3.309, "b": 1.28, "c": 0.0, "C14_Amp": 0.047},
                    }
                elif fitter_type == "fast" and src_name != "Ge68":
                    from src.FastSourceFitter import run_fast_source_fitter
                    from src.FastSourceFitter import SOURCE_CONFIG
                    outputs = run_fast_source_fitter(
                        source=src_name, run_id=run_id, input_path=input_path,
                        output_fig_dir=str(OUTPUT_FIG_DIR),
                        output_res_dir=str(OUTPUT_RES_DIR),
                        output_stem=output_stem, enable_c14=True,
                        c14_convolver="fft", results_only=False,
                    )
                    fitter_file = "src/FastSourceFitter.py"
                    _cfg = SOURCE_CONFIG[src_name]
                    fitter_params = {
                        "template_path": str(PROJECT_ROOT / "fitters" / _cfg["bkg_npz"]),
                        "bins_fit": f"arange({_cfg['bins_fit'][0]:.3f}, {_cfg['bins_fit'][-1]:.3f}, {_cfg['bins_fit'][1]-_cfg['bins_fit'][0]:.3f})",
                        "x_limit": _cfg["x_limit"],
                        "mc_center": _cfg["mc_center"],
                        "enable_c14": True,
                        "c14_convolver": "fft",
                        "fixed_params": {"E_scale": "auto", "a": 3.309, "b": 1.28, "c": 0.0, "C14_Amp": 0.05},
                    }
                else:
                    from src.MCBased_Fitter import run_fitter as run_classic_fitter
                    outputs = run_classic_fitter(
                        run_id=run_id, source=src_name, input_path=input_path,
                        output_fig_dir=str(OUTPUT_FIG_DIR),
                        output_res_dir=str(OUTPUT_RES_DIR),
                        output_stem=output_stem, enable_c14=True,
                    )
                    fitter_file = "src/MCBased_Fitter.py"
                    fitter_params = {
                        "enable_c14": True,
                        "fixed_params": {"a": 3.309, "b": 1.28, "c": 0.0},
                    }
            except Exception as e:
                source_status = "failed"
                source_error = str(e)
                import traceback
                traceback.print_exc()
                print(f"[Error] {src_name} RUN{run_id} failed: {e}", flush=True)

            elapsed = time.time() - t0

            if source_status == "success" and outputs.get("result_npz"):
                npz_path = outputs["result_npz"]
                data = np.load(npz_path, allow_pickle=True)
                sv = data["sigma_gauss"].item()
                cv = data["center_gauss"].item()
                mu = cv["value"]
                sigma = sv["value"]
                chi2 = float(data["chi2"])
                ndf = int(data["ndf"])
                data.close()
                sigma_over_e = sigma / mu * 100
                results[src_name] = {"mu": mu, "sigma": sigma, "sigma_over_e": sigma_over_e,
                                      "chi2": chi2, "ndf": ndf, "e_true": e_true, "elapsed_s": elapsed}
                fit_results = {"mu": mu, "sigma": sigma, "sigma_over_e_pct": sigma_over_e, "chi2": chi2, "ndf": ndf}
            else:
                mu = 0
                sigma = 0
                sigma_over_e = 0
                fit_results = {}
                results[src_name] = {"mu": 0, "sigma": 0, "sigma_over_e": 0,
                                      "chi2": 0, "ndf": 0, "e_true": e_true, "elapsed_s": elapsed}

            output_files = {}
            if outputs.get("result_npz"):
                output_files["result_npz"] = outputs["result_npz"]
            for key in ["figure", "log_figure", "full_figure", "zoom_figure"]:
                if outputs.get(key):
                    output_files[key] = outputs[key]

            logger.add_source_record(
                src_name=src_name, run_id=run_id, e_true=e_true,
                fitter_type=fitter_type, fitter_file=fitter_file,
                input_path=input_path, output_files=output_files,
                event_data=event_data, fit_results=fit_results,
                fitter_params=fitter_params,
                elapsed_s=elapsed, status=source_status, error_message=source_error,
            )

            if source_status == "success":
                print(f"[{src_name}] mu={mu:.4f}, sigma/E={sigma_over_e:.2f}%, "
                      f"chi2/ndf={chi2:.0f}/{ndf}, time={elapsed:.1f}s")
            else:
                print(f"[{src_name}] FAILED: {source_error}", flush=True)
            sys.stdout.flush()

        print(f"\n{'='*60}")
        print(f"Total time: {time.time() - total_start:.1f}s")
        print()

        print(f"{'Source':<8} {'E_true':<10} {'E_rec':<10} {'sigma/E':<10} {'chi2/ndf':<12} {'Time':<10} {'Fitter':<10}")
        print("-" * 70)
        for src_name, _, _, fitter_type in SOURCES:
            if src_name not in results:
                continue
            r = results[src_name]
            if r["mu"] > 0:
                print(f"{src_name:<8} {r['e_true']:<10.3f} {r['mu']:<10.4f} "
                      f"{r['sigma_over_e']:<10.2f}% {r['chi2']:<.0f}/{r['ndf']:<5} {r['elapsed_s']:<8.1f}s {fitter_type:<10}")
            else:
                print(f"{src_name:<8} {r['e_true']:<10.3f} {'FAILED':<10} {'N/A':<10} {'N/A':<12} {r['elapsed_s']:<8.1f}s {fitter_type:<10}")

        # ENL-style plot
        print("\nDrawing ENL-style resolution plot...")
        sys.stdout.flush()

        fig, ax = plt.subplots(figsize=(7, 5))
        e_fine = np.linspace(0.4, 2.8, 200)
        ax.plot(e_fine, np.sqrt((A_JUNO_REF / np.sqrt(e_fine)) ** 2 + B_JUNO_REF ** 2),
                "k--", alpha=0.35, linewidth=1.5,
                label=f"JUNO reference ($a$={A_JUNO_REF:.2f}, $b$={B_JUNO_REF:.2f})")

        for src_name, _, _, fitter_type in SOURCES:
            if src_name not in results or results[src_name]["mu"] == 0:
                continue
            r = results[src_name]
            ax.errorbar(r["mu"], r["sigma_over_e"], fmt=MARKERS[src_name],
                        color=COLORS[src_name], markersize=10, capsize=4,
                        capthick=1.5, linewidth=1.5, label=f"{src_name}", zorder=4)
            ax.annotate(f"{src_name}\n({r['sigma_over_e']:.2f}%)",
                        (r["mu"], r["sigma_over_e"]), textcoords="offset points",
                        xytext=(10, 8), fontsize=10, color=COLORS[src_name], zorder=5)

        ax.set_xlim(0.4, 2.8); ax.set_ylim(1.5, 5.5)
        ax.set_xlabel(r"$E_{\mathrm{rec}}$ [MeV]", fontsize=14)
        ax.set_ylabel(r"$\sigma/\mu$ [%]", fontsize=14)
        ax.set_title("Energy Resolution vs Reconstructed Energy (CD Center)", fontsize=13, fontweight="bold")
        ax.tick_params(axis="both", which="major", labelsize=12, direction="in", top=True, right=True)
        ax.tick_params(axis="both", which="minor", direction="in", top=True, right=True)
        ax.grid(True, alpha=0.3, linestyle=":")
        ax.legend(fontsize=11, loc="upper right", framealpha=0.85)
        plt.tight_layout()

        png_path = str(OUTPUT_DIR / "enl_style_resolution.png")
        pdf_path = str(OUTPUT_DIR / "enl_style_resolution.pdf")
        plt.savefig(png_path, dpi=200, bbox_inches="tight")
        plt.savefig(pdf_path, bbox_inches="tight")
        plt.close()

        print(f"Saved {png_path}")
        print(f"Saved {pdf_path}")

        logger.set_summary({
            "total_sources_configured": len(SOURCES),
            "total_sources_fitted": len(results),
            "total_time_s": f"{time.time() - total_start:.1f}",
            "sources": ", ".join(results.keys()),
            "output_directory": str(OUTPUT_DIR),
        })

        # ---- end-of-run audit: full code snapshot + output completeness ----
        snap = logger.snapshot_code_full()
        expected = [OUTPUT_DIR / "config_snapshot.json",
                    OUTPUT_DIR / "enl_style_resolution.png"]
        for src_name, run_id, _, _f in SOURCES:
            if src_name not in results:
                continue
            expected += [OUTPUT_DIR / "results" / f"RUN{run_id}_{src_name}.npz",
                         OUTPUT_DIR / "figures" / f"RUN{run_id}_{src_name}.pdf"]
        audit = logger.run_audit(expected)
        audit_failed = False
        if audit["passed"]:
            print(f"[AUDIT] PASSED ({snap['n_files']} code files, "
                  f"outputs complete)", flush=True)
        else:
            cs, oo = audit["code_snapshot"], audit["outputs"]
            logger.add_error(
                "audit",
                f"completeness audit failed: code all_match={cs['all_match']} "
                f"(missing={len(cs['missing'])}, mismatched={len(cs['mismatched'])},"
                f" extra={len(cs['extra'])}), outputs all_present={oo['all_present']}"
                f" (missing={oo['missing'][:4]})")
            logger.record["status"] = "audit-failed"
            if _args.launched_by == "agent":
                print("[AUDIT] WARNING: code/output completeness audit FAILED. "
                      "Agent, review run_log.json -> audit before using outputs.",
                      flush=True)
            else:
                print("[AUDIT] FAILED: code/output completeness audit failed "
                      f"(missing outputs: {oo['missing'][:4]}; "
                      f"code mismatches: {cs['mismatched'][:3]}). "
                      "Exiting with code 3.", flush=True)
                audit_failed = True

    if audit_failed:
        logger.set_exit_code(3)
    else:
        logger.set_exit_code(0)

print(f"\n{'='*60}")
print(f"Pipeline complete. Output directory: {OUTPUT_DIR}")
print(f"Log files: run_log.json, run_log.md, console.log")
print(f"To view results: open {png_path}")