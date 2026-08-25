#!/usr/bin/env python3
"""Compare Fast vs Classic fitters for Cs137, Mn54, Co60, K40."""
from __future__ import annotations

import os, sys, time
from pathlib import Path
_PROJ_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJ_ROOT))
for _p in ["src", "fitters", "smx_ana", "pipeline", "config"]:
    _path = str(_PROJ_ROOT / _p)
    if _path not in sys.path:
        sys.path.insert(0, _path)
os.environ.setdefault("MPLCONFIGDIR", str(_PROJ_ROOT / "TMP" / "matplotlib"))

import numpy as np
from input_loader import normalize_event_input

# Classic fitters
from fitters.Cs137Fitter import Cs137Fitter
from fitters.Mn54Fitter import Mn54Fitter
from fitters.Co60Fitter import Co60Fitter
from fitters.K40Fitter import K40Fitter
from fitters.FitterUtils import extract_fit_results

# Fast fitters
from src.FastSourceFitter import FastSourceFitter

# ============================================================
# Configuration
# ============================================================
DATA_BASE = "/lustrefs/juno26/users/zhaorz/Calib/ReProd26B/singles_selection/Results_fromFinalcorrection/npz"
SOURCES = [
    ("Cs137", 9600, 0.662,  np.arange(0.3, 0.9, 0.004), 0.3),
    ("Mn54",  9624, 0.835,  np.arange(0.5, 1.0, 0.004), 0.3),
    ("Co60",  9591, 2.506,  np.arange(1.9, 2.7, 0.004), 1.0),
    ("K40",   9632, 1.461,  np.arange(1.0, 1.8, 0.004), 0.6),
]

results = {}

for src_name, run_id, e_true, bins_fit, x_limit in SOURCES:
    input_path = f"{DATA_BASE}/Run{run_id}_SelectionResult.npz"
    if not os.path.exists(input_path):
        print(f"[SKIP] {src_name}: data not found")
        continue

    event_data = normalize_event_input(input_path, src_name)
    energy = np.asarray(event_data["energy"], dtype=float)
    energy = energy[np.isfinite(energy)]
    print(f"\n{'='*60}")
    print(f"{src_name} RUN{run_id}: {len(energy)} events")

    # ---- Classic Fitter ----
    fitter_class = {
        "Cs137": Cs137Fitter, "Mn54": Mn54Fitter,
        "Co60": Co60Fitter, "K40": K40Fitter,
    }[src_name]
    t0 = time.time()
    cf = fitter_class(bins_fit=bins_fit, data_arr=energy, is_hist=False,
                      x_limit=x_limit, if_fix_abc=True, enable_c14=True,
                      fix_c14_amplitude=True)
    cf.fit()
    t_classic = time.time() - t0
    cv = cf.dict_result["center_gauss"]["value"]
    sv = cf.dict_result["sigma_gauss"]["value"]
    mu_c = cv
    se_c = sv / cv * 100
    chi2_c = cf.dict_result["chi2"]
    ndf_c = cf.dict_result["ndf"]

    # ---- Fast Fitter ----
    t0 = time.time()
    ff = FastSourceFitter(src_name, energy, enable_c14=True, c14_convolver="fft")
    ff.fit()
    t_fast = time.time() - t0
    cv = ff.dict_result["center_gauss"]["value"]
    sv = ff.dict_result["sigma_gauss"]["value"]
    mu_f = cv
    se_f = sv / cv * 100
    chi2_f = ff.dict_result["chi2"]
    ndf_f = ff.dict_result["ndf"]

    # Store
    results[src_name] = {
        "mu_c": mu_c, "mu_f": mu_f,
        "se_c": se_c, "se_f": se_f,
        "chi2_c": chi2_c, "chi2_f": chi2_f,
        "ndf_c": ndf_c, "ndf_f": ndf_f,
        "t_c": t_classic, "t_f": t_fast,
        "e_true": e_true,
    }

    print(f"  Classic: mu={mu_c:.4f}, sigma/E={se_c:.2f}%, "
          f"chi2/ndf={chi2_c:.0f}/{ndf_c}, time={t_classic:.1f}s")
    print(f"  Fast:    mu={mu_f:.4f}, sigma/E={se_f:.2f}%, "
          f"chi2/ndf={chi2_f:.0f}/{ndf_f}, time={t_fast:.2f}s")
    print(f"  Δmu: {abs(mu_c-mu_f)*1000:.2f} keV, "
          f"Δσ/E: {abs(se_c-se_f):.3f}%")

# ============================================================
# Summary table
# ============================================================
print(f"\n{'='*80}")
print(f"{'Source':<8} {'E_true':<8} {'mu_classic':<12} {'mu_fast':<12} {'Δmu(keV)':<10} "
      f"{'σ/E_classic':<12} {'σ/E_fast':<12} {'Δσ/E':<8} {'t_classic':<10} {'t_fast':<8} {'speedup':<8}")
print("-" * 80)
for src_name, _, _, _, _ in SOURCES:
    r = results[src_name]
    dmu = abs(r["mu_c"] - r["mu_f"]) * 1000
    dse = abs(r["se_c"] - r["se_f"])
    speedup = r["t_c"] / r["t_f"] if r["t_f"] > 0 else float("inf")
    print(f"{src_name:<8} {r['e_true']:<8.3f} {r['mu_c']:<12.4f} {r['mu_f']:<12.4f} "
          f"{dmu:<10.2f} {r['se_c']:<12.2f}% {r['se_f']:<12.2f}% {dse:<8.2f} "
          f"{r['t_c']:<10.1f}s {r['t_f']:<8.2f}s {speedup:<8.1f}x")
print("=" * 80)