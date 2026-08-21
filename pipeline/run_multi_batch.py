#!/usr/bin/env python3
"""
Multi-batch pipeline runner: runs multiple batches of sources from different
time periods, each in its own timestamped output directory with full logs.
"""
from __future__ import annotations

import os, sys, time, json, subprocess
from pathlib import Path

import numpy as np

_PROJ_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJ_ROOT))
for _p in ["src", "fitters", "smx_ana"]:
    _path = str(_PROJ_ROOT / _p)
    if _path not in sys.path:
        sys.path.insert(0, _path)
os.environ["MPLCONFIGDIR"] = str(_PROJ_ROOT / "TMP" / "matplotlib")

# =============================================================================
# Batch definitions: (batch_name, [(src_name, run_id, e_true, fitter_type), ...])
# =============================================================================
BATCHES = [
    ("Batch_202508_Phase1", [
        ("Ge68",  9541, 0.8845, "fast"),
        ("Cs137", 9600, 0.662,  "fast"),
        ("Mn54",  9624, 0.835,  "fast"),
        ("Co60",  9591, 2.506,  "fast"),
        ("K40",   9632, 1.461,  "fast"),
    ]),
    ("Batch_202512_Phase2", [
        ("Ge68",  12370, 0.8845, "fast"),
        ("Cs137", 12295, 0.662,  "fast"),
        ("Mn54",  12247, 0.835,  "fast"),
        ("Co60",  12216, 2.506,  "fast"),
        ("K40",   9632, 1.461,  "fast"),
    ]),
    ("Batch_202603_Phase3", [
        ("Ge68",  14091, 0.8845, "fast"),
        ("Co60",  14087, 2.506,  "fast"),
        ("Mn54",  14083, 0.835,  "fast"),
    ]),
    ("Batch_202603_Phase4", [
        ("Ge68",  14417, 0.8845, "fast"),
    ]),
]

DATA_BASE = "/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz"
OUTPUT_ROOT = _PROJ_ROOT / "output"

results_summary = {}

for batch_name, sources in BATCHES:
    print(f"\n{'='*70}")
    print(f"  BATCH: {batch_name} ({len(sources)} sources)")
    print(f"{'='*70}")
    sys.stdout.flush()

    # Build a temporary config file for this batch
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    batch_output_dir = OUTPUT_ROOT / f"{timestamp}_{batch_name}"

    # Run each source individually
    for src_name, run_id, e_true, fitter_type in sources:
        input_path = f"{DATA_BASE}/Run{run_id}_SelectionResult.npz"
        if not os.path.exists(input_path):
            print(f"  [SKIP] {src_name} RUN{run_id}: data not found")
            continue

        output_stem = f"RUN{run_id}_{src_name}"
        fig_dir = str(batch_output_dir / "figures")
        res_dir = str(batch_output_dir / "results")
        os.makedirs(fig_dir, exist_ok=True)
        os.makedirs(res_dir, exist_ok=True)

        t0 = time.time()

        if fitter_type == "fast" and src_name == "Ge68":
            from src.FastGe68Fitter import run_fast_ge68_fitter
            outputs = run_fast_ge68_fitter(
                run_id=run_id, input_path=input_path,
                output_fig_dir=fig_dir, output_res_dir=res_dir,
                output_stem=output_stem, enable_c14=True,
                c14_convolver="fft", results_only=False,
            )
        elif fitter_type == "fast":
            from src.FastSourceFitter import run_fast_source_fitter
            outputs = run_fast_source_fitter(
                source=src_name, run_id=run_id, input_path=input_path,
                output_fig_dir=fig_dir, output_res_dir=res_dir,
                output_stem=output_stem, enable_c14=True,
                c14_convolver="fft", results_only=False,
            )
        else:
            from src.MCBased_Fitter import run_fitter as run_classic_fitter
            outputs = run_classic_fitter(
                run_id=run_id, source=src_name, input_path=input_path,
                output_fig_dir=fig_dir, output_res_dir=res_dir,
                output_stem=output_stem, enable_c14=True,
            )

        elapsed = time.time() - t0

        # Load result
        data = np.load(outputs["result_npz"], allow_pickle=True)
        cv = data["center_gauss"].item()
        sv = data["sigma_gauss"].item()
        mu = cv["value"]
        sigma = sv["value"]
        chi2 = float(data["chi2"])
        ndf = int(data["ndf"])
        se = sigma / mu * 100
        data.close()

        results_summary.setdefault(batch_name, {})[src_name] = {
            "run": run_id, "mu": mu, "se": se, "chi2": chi2, "ndf": ndf, "t": elapsed,
        }

        print(f"  [{src_name:6}] RUN{run_id}  μ={mu:.4f}  σ/E={se:.2f}%  "
              f"χ²/ndf={chi2:.0f}/{ndf}  {elapsed:.1f}s")

    # Generate ENL-style plot for this batch
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        batch_results = results_summary[batch_name]
        if len(batch_results) >= 2:
            colors = {"Ge68":"#1f77b4","Cs137":"#ff7f0e","Mn54":"#d62728","Co60":"#2ca02c","K40":"#9467bd"}
            markers = {"Ge68":"o","Cs137":"s","Mn54":"^","Co60":"D","K40":"v"}

            fig, ax = plt.subplots(figsize=(7, 5))
            e_fine = np.linspace(0.4, 2.8, 200)
            ax.plot(e_fine, np.sqrt((3.309/np.sqrt(e_fine))**2+1.28**2),
                    "k--", alpha=0.35, lw=1.5, label="JUNO ref (a=3.31, b=1.28)")

            for src, r in batch_results.items():
                ax.errorbar(r["mu"], r["se"], fmt=markers.get(src,"o"),
                            color=colors.get(src,"gray"), markersize=10, capsize=4,
                            label=f"{src}")
                ax.annotate(f"{src}\n({r['se']:.2f}%)", (r["mu"], r["se"]),
                            textcoords="offset points", xytext=(10, 8), fontsize=10,
                            color=colors.get(src,"gray"))

            ax.set_xlim(0.4, 2.8); ax.set_ylim(1.5, 5.5)
            ax.set_xlabel(r"$E_{\mathrm{rec}}$ [MeV]", fontsize=14)
            ax.set_ylabel(r"$\sigma/\mu$ [%]", fontsize=14)
            ax.set_title(f"Energy Resolution — {batch_name}", fontsize=13, fontweight="bold")
            ax.tick_params(direction="in", top=True, right=True, labelsize=12)
            ax.grid(True, alpha=0.3, linestyle=":"); ax.legend(fontsize=11, loc="upper right")

            png = str(batch_output_dir / "enl_style_resolution.png")
            pdf = str(batch_output_dir / "enl_style_resolution.pdf")
            plt.savefig(png, dpi=200, bbox_inches="tight")
            plt.savefig(pdf, bbox_inches="tight")
            plt.close()
            print(f"  [Plot] {png}")
    except Exception as e:
        print(f"  [Plot] skip: {e}")

    print(f"  [Output] {batch_output_dir}")

# =============================================================================
# Final comparison table
# =============================================================================
print(f"\n{'='*70}")
print("  CROSS-BATCH COMPARISON")
print(f"{'='*70}")

# All sources across batches
all_sources = set()
for batch_name, sources in BATCHES:
    for src, _, _, _ in sources:
        all_sources.add(src)

for src in sorted(all_sources):
    print(f"\n  {src}:")
    for batch_name in results_summary:
        if src in results_summary[batch_name]:
            r = results_summary[batch_name][src]
            print(f"    {batch_name:25s}  RUN{r['run']:6}  μ={r['mu']:.4f}  σ/E={r['se']:.2f}%  {r['t']:.1f}s")

print(f"\n{'='*70}")
print("  All batches complete.")
print(f"{'='*70}")