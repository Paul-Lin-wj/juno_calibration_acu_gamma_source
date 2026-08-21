#!/usr/bin/env python3
"""
Main pipeline: run fits for all sources, collect results, draw ENL-style plot.

Usage:
    python pipeline/run_fit_all.py

The pipeline will:
1. Run FastGe68Fitter for Ge68 (fast cached version)
2. Run classic MCBased_Fitter for other sources (Cs137, Mn54, Co60, K40)
3. Collect fit results (mu, sigma)
4. Draw ENL-style resolution vs E_rec plot
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# ================= Ensure all modules are on path =================
_PROJ_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJ_ROOT))  # For: from config.paths import ...
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

from config.paths import (
    PROJECT_ROOT,
    DATA_INPUT_PATH,
    SOURCES,
    RUN_INFO_CSV,
    A_JUNO_REF,
    B_JUNO_REF,
    COLORS,
    MARKERS,
)

from src.run_logger import RunLogger
from input_loader import normalize_event_input

# ================= Timestamp-based output directory =================
_timestamp = time.strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = PROJECT_ROOT / "output" / _timestamp
OUTPUT_RES_DIR = OUTPUT_DIR / "results"
OUTPUT_FIG_DIR = OUTPUT_DIR / "figures"
OUTPUT_RES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FIG_DIR.mkdir(parents=True, exist_ok=True)

print(f"[Info] Output directory: {OUTPUT_DIR}")
sys.stdout.flush()

# ================= Initialize run logger =================
logger = RunLogger(
    output_dir=OUTPUT_DIR,
    project_root=PROJECT_ROOT,
    launched_by="script",
)

# ================= Run fits =================
results: dict[str, dict] = {}
total_start = time.time()

for src_name, run_id, e_true, fitter_type in SOURCES:
    input_path = f"{DATA_INPUT_PATH}/Run{run_id}_SelectionResult.npz"
    if not os.path.exists(input_path):
        print(f"[Warning] {src_name} RUN{run_id}: data not found at {input_path}, skip")
        continue

    print(f"\n{'='*60}")
    print(f"[{src_name}] RUN{run_id} (E_true={e_true} MeV)")
    print(f"[{src_name}] Input: {input_path}")
    sys.stdout.flush()

    # Load event data for logging (before fit)
    event_data = None
    try:
        event_data = normalize_event_input(input_path, src_name)
    except Exception as e:
        print(f"[Warning] Could not load event data for logging: {e}")

    t0 = time.time()
    output_stem = f"RUN{run_id}_{src_name}"

    if fitter_type == "fast" and src_name == "Ge68":
        from src.FastGe68Fitter import run_fast_ge68_fitter

        outputs = run_fast_ge68_fitter(
            run_id=run_id,
            input_path=input_path,
            output_fig_dir=str(OUTPUT_FIG_DIR),
            output_res_dir=str(OUTPUT_RES_DIR),
            output_stem=output_stem,
            enable_c14=True,
            c14_convolver="fft",
            results_only=False,
        )
        fitter_file = "src/FastGe68Fitter.py"
    elif fitter_type == "fast" and src_name != "Ge68":
        from src.FastSourceFitter import run_fast_source_fitter

        outputs = run_fast_source_fitter(
            source=src_name,
            run_id=run_id,
            input_path=input_path,
            output_fig_dir=str(OUTPUT_FIG_DIR),
            output_res_dir=str(OUTPUT_RES_DIR),
            output_stem=output_stem,
            enable_c14=True,
            c14_convolver="fft",
            results_only=False,
        )
        fitter_file = "src/FastSourceFitter.py"
    else:
        from src.MCBased_Fitter import run_fitter as run_classic_fitter

        outputs = run_classic_fitter(
            run_id=run_id,
            source=src_name,
            input_path=input_path,
            output_fig_dir=str(OUTPUT_FIG_DIR),
            output_res_dir=str(OUTPUT_RES_DIR),
            output_stem=output_stem,
            enable_c14=True,
        )
        fitter_file = "src/MCBased_Fitter.py"

    elapsed = time.time() - t0

    # Load result
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
    results[src_name] = {
        "mu": mu,
        "sigma": sigma,
        "sigma_over_e": sigma_over_e,
        "chi2": chi2,
        "ndf": ndf,
        "e_true": e_true,
        "elapsed_s": elapsed,
    }

    # Collect output file paths
    output_files = {
        "result_npz": str(npz_path),
    }
    if "figure" in outputs:
        output_files["figure"] = outputs["figure"]
    if "log_figure" in outputs:
        output_files["figure_log"] = outputs["log_figure"]
    if "full_figure" in outputs:
        output_files["figure"] = outputs["full_figure"]
    if "zoom_figure" in outputs:
        output_files["figure_zoom"] = outputs["zoom_figure"]

    # Log this source
    logger.add_source_record(
        src_name=src_name,
        run_id=run_id,
        e_true=e_true,
        fitter_type=fitter_type,
        fitter_file=fitter_file,
        input_path=input_path,
        output_files=output_files,
        event_data=event_data,
        fit_results={
            "mu": mu,
            "sigma": sigma,
            "sigma_over_e_pct": sigma_over_e,
            "chi2": chi2,
            "ndf": ndf,
        },
        elapsed_s=elapsed,
    )

    print(f"[{src_name}] mu={mu:.4f}, sigma/E={sigma_over_e:.2f}%, "
          f"chi2/ndf={chi2:.0f}/{ndf}, time={elapsed:.1f}s")
    sys.stdout.flush()

print(f"\n{'='*60}")
print(f"Total time: {time.time() - total_start:.1f}s")
print()

# ===== Print summary table =====
print(f"{'Source':<8} {'E_true':<10} {'E_rec':<10} {'sigma/E':<10} {'chi2/ndf':<12} {'Time':<10} {'Fitter':<10}")
print("-" * 70)
for src_name, _, _, fitter_type in SOURCES:
    if src_name not in results:
        continue
    r = results[src_name]
    print(f"{src_name:<8} {r['e_true']:<10.3f} {r['mu']:<10.4f} "
          f"{r['sigma_over_e']:<10.2f}% {r['chi2']:<.0f}/{r['ndf']:<5} {r['elapsed_s']:<8.1f}s {fitter_type:<10}")

# ===== ENL-style plot: Resolution vs E_rec =====
print("\nDrawing ENL-style resolution plot...")
sys.stdout.flush()

fig, ax = plt.subplots(figsize=(7, 5))

# Ideal JUNO stochastic resolution model
e_fine = np.linspace(0.4, 2.8, 200)
model_res = np.sqrt((A_JUNO_REF / np.sqrt(e_fine)) ** 2 + B_JUNO_REF ** 2)
ax.plot(e_fine, model_res, "k--", alpha=0.35, linewidth=1.5,
        label=f"JUNO reference ($a$={A_JUNO_REF:.2f}, $b$={B_JUNO_REF:.2f})")

# Plot each source
for src_name, _, _, fitter_type in SOURCES:
    if src_name not in results:
        continue
    r = results[src_name]
    ax.errorbar(
        r["mu"], r["sigma_over_e"],
        fmt=MARKERS[src_name],
        color=COLORS[src_name],
        markersize=10,
        capsize=4,
        capthick=1.5,
        linewidth=1.5,
        label=f"{src_name}",
        zorder=4,
    )
    ax.annotate(
        f"{src_name}\n({r['sigma_over_e']:.2f}%)",
        (r["mu"], r["sigma_over_e"]),
        textcoords="offset points",
        xytext=(10, 8),
        fontsize=10,
        color=COLORS[src_name],
        zorder=5,
    )

# Formatting - ENL style
ax.set_xlim(0.4, 2.8)
ax.set_ylim(1.5, 5.5)
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

# ===== Finalize log =====
total_time = time.time() - total_start
logger.set_summary({
    "total_sources_configured": len(SOURCES),
    "total_sources_fitted": len(results),
    "total_time_s": f"{total_time:.1f}",
    "total_time_min": f"{total_time/60:.1f}",
    "sources": ", ".join(results.keys()),
    "output_directory": str(OUTPUT_DIR),
})
json_path, md_path = logger.finalize()

print(f"\n{'='*60}")
print(f"Pipeline complete. Output directory: {OUTPUT_DIR}")
print(f"Log files: {json_path.name}, {md_path.name}")
print(f"To view results: open {png_path}")