"""
Generic Fast Fitter for Cs137, Mn54, Co60, K40.
Caches MC template convolutions for ~10-50x speedup vs classic fitters.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_PROJ_ROOT = Path(__file__).resolve().parent.parent
for _p in ["src", "fitters", "smx_ana"]:
    _path = str(_PROJ_ROOT / _p)
    if _path not in sys.path:
        sys.path.insert(0, _path)

os.environ.setdefault("MPLCONFIGDIR", str(_PROJ_ROOT / "TMP" / "matplotlib"))
os.environ.setdefault("NUMBA_CACHE_DIR", str(_PROJ_ROOT / "TMP" / "numba"))

import numpy as np
from iminuit import Minuit
from iminuit.cost import LeastSquares

try:
    import smx_ana
except ImportError:
    smx_ana = None

from fitters.Compat import GetBinCenter
from fitters.FitterUtils import (
    EnergyResolutionModel, FEP_part, build_c14_pileup_terms,
    extract_fit_results, sum_distributions_fft, sum_distributions_fast,
)

SOURCE_CONFIG = {
    "Cs137": {
        "bkg_npz": "Cs137_Compton_BKG.npz",
        "mc_center": 0.58423,
        "x_limit": 0.3,
        "bins_fit": np.arange(0.3, 0.9, 0.004),
    },
    "Mn54": {
        "bkg_npz": "Mn54_Compton_BKG.npz",
        "mc_center": 0.7506673749012558,
        "x_limit": 0.3,
        "bins_fit": np.arange(0.5, 1.0, 0.004),
    },
    "Co60": {
        "bkg_npz": "Co60_Compton_BKG.npz",
        "mc_center": 2.305448059680732,
        "x_limit": 1.0,
        "bins_fit": np.arange(1.9, 2.7, 0.004),
    },
    "K40": {
        "bkg_npz": "K40_Compton_BKG.npz",
        "mc_center": 1.3550554274479678,
        "x_limit": 0.6,
        "bins_fit": np.arange(1.0, 1.8, 0.004),
    },
}

C14_CONVOLVERS = {"python": sum_distributions_fast, "fft": sum_distributions_fft}
BINS_C14 = np.arange(0, 0.2, 0.001)
BINS_C14_CENTER = GetBinCenter(BINS_C14)
FITTERS_DIR = _PROJ_ROOT / "fitters"


def _bootstrap_smx_ana() -> None:
    global smx_ana
    if smx_ana is not None:
        return
    try:
        import smx_ana as loaded_smx_ana
        smx_ana = loaded_smx_ana
    except ImportError:
        raise RuntimeError("Could not import smx_ana.")


def _weighted_histogram(values: np.ndarray, bins: np.ndarray, scale: float) -> np.ndarray:
    return np.histogram(values * scale, bins=bins,
                        weights=np.ones_like(values) / len(values))[0]


class FastSourceFitter:
    """Fast fitter for Cs137, Mn54, Co60, K40 with template caching."""

    def __init__(self, source: str, data_arr: np.ndarray,
                 enable_c14: bool = True, c14_convolver: str = "fft"):
        _bootstrap_smx_ana()
        if source not in SOURCE_CONFIG:
            raise ValueError(f"Unsupported source: {source}")
        cfg = SOURCE_CONFIG[source]
        self.source = source
        self.MC_Qedep_Center = cfg["mc_center"]
        self.x_limit = cfg["x_limit"]
        self.enable_c14 = enable_c14
        self.c14_convolver_func = C14_CONVOLVERS[c14_convolver]
        self.bins_fit = cfg["bins_fit"].copy()
        self.bins_center = GetBinCenter(self.bins_fit)
        self.bins_C14 = BINS_C14
        self.bins_C14_center = BINS_C14_CENTER

        bkg_path = FITTERS_DIR / cfg["bkg_npz"]
        with np.load(bkg_path) as d:
            self.bkg_data = {k: np.asarray(v) for k, v in d.items()}

        data_binned = np.histogram(data_arr, bins=self.bins_fit)[0]
        self.data_binned = data_binned
        self.data_errors = np.sqrt(data_binned)
        self.index_nonzero = (data_binned > 0) & (self.bins_center > self.x_limit)
        self.total_count = float(np.sum(self.data_binned[self.index_nonzero]))

        self.cached: dict = {}
        self.model_eval_count = 0
        self._setup_minuit()

    def _setup_minuit(self) -> None:
        max_center = self.bins_center[np.argmax(self.data_binned)]
        e_scale = max_center / self.MC_Qedep_Center
        a, b, c = 3.309, 1.28, 0.0
        c14_amp = 5e-2 if self.enable_c14 else 0.0

        energy_res = EnergyResolutionModel(self.bins_center, a, b, c)
        uc = _weighted_histogram(self.bkg_data["Compton"], self.bins_fit, e_scale)
        self.cached["compton_conv"] = smx_ana.convolve(uc, self.bins_fit, energy_res).copy()
        self.cached["energy_sigma"] = energy_res
        if self.enable_c14:
            self.cached["C14_part"] = _weighted_histogram(self.bkg_data["C14"], self.bins_C14, e_scale)
        else:
            self.cached["C14_part"] = np.zeros(len(self.bins_C14) - 1, dtype=float)

        cost = LeastSquares(self.bins_center[self.index_nonzero],
                            self.data_binned[self.index_nonzero],
                            self.data_errors[self.index_nonzero], self)
        m = Minuit(cost, amp_gauss=np.max(self.data_binned[self.index_nonzero]),
                   center_gauss=max_center, sigma_gauss=max_center * 0.0386,
                   Compton=np.max(self.data_binned[self.index_nonzero]) * 10,
                   C14_Amp=c14_amp, E_scale=e_scale, a=a, b=b, c=c)
        m.limits["Compton"] = (0, None)
        m.limits["C14_Amp"] = (0, None)
        m.fixed["C14_Amp"] = True
        m.fixed["E_scale"] = True
        m.fixed["a"] = True
        m.fixed["b"] = True
        m.fixed["c"] = True
        self.minuit_core = m

    def __call__(self, x, amp_gauss, center_gauss, sigma_gauss,
                 Compton, C14_Amp, E_scale, a, b, c):
        self.model_eval_count += 1
        bkg_conv = Compton * self.cached["compton_conv"]
        fep = FEP_part(self.bins_center, amp_gauss, center_gauss, sigma_gauss)
        part_wo = bkg_conv + fep
        o, t = build_c14_pileup_terms(self.bins_center, part_wo, self.bins_fit,
                                       self.bins_C14_center, self.cached["C14_part"],
                                       self.c14_convolver_func)
        result = part_wo + (C14_Amp * self.total_count) * o + (C14_Amp**2 * self.total_count) * t
        return result[self.index_nonzero]

    def fit(self) -> None:
        self.minuit_core.migrad()
        self.dict_result = extract_fit_results(self.minuit_core)
        vals = self.dict_result

        # Compute full (unfiltered) model_result for components
        bkg_conv = vals["Compton"]["value"] * self.cached["compton_conv"]
        fep = FEP_part(self.bins_center, vals["amp_gauss"]["value"],
                       vals["center_gauss"]["value"], vals["sigma_gauss"]["value"])
        part_wo = bkg_conv + fep
        o, t = build_c14_pileup_terms(self.bins_center, part_wo, self.bins_fit,
                                       self.bins_C14_center, self.cached["C14_part"],
                                       self.c14_convolver_func)
        model_result_full = part_wo + (vals["C14_Amp"]["value"] * self.total_count) * o \
                            + (vals["C14_Amp"]["value"]**2 * self.total_count) * t

        model_result_filtered = model_result_full[self.index_nonzero]
        chi2 = np.sum(((self.data_binned[self.index_nonzero] - model_result_filtered)
                       / self.data_errors[self.index_nonzero])**2)
        self.dict_result["chi2"] = chi2
        self.dict_result["ndf"] = len(self.data_binned[self.index_nonzero]) - len(self.minuit_core.parameters)
        self.dict_result["total_count"] = self.total_count
        self.dict_result["enable_c14"] = self.enable_c14
        self.dict_result["model_eval_count"] = self.model_eval_count
        self.dict_result["fast_cached_templates"] = True

        self.dict_result["components"] = {
            "bkg_conv": bkg_conv,
            "FEP_hist": fep,
            "one_pileup": (vals["C14_Amp"]["value"] * self.total_count) * o,
            "two_pileup": (vals["C14_Amp"]["value"]**2 * self.total_count) * t,
            "model_result": model_result_full,
            "part_wo_pileup": part_wo,
        }


def run_fast_source_fitter(source, run_id=None, input_path="",
                           output_fig_dir=".", output_res_dir=".",
                           output_stem="", enable_c14=True,
                           c14_convolver="fft", results_only=False):
    """Run FastSourceFitter and produce outputs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from input_loader import normalize_event_input, infer_sample_label

    event_data = normalize_event_input(input_path, source)
    energy = np.asarray(event_data["energy"], dtype=float)
    finite_energy = energy[np.isfinite(energy)]
    if finite_energy.shape[0] == 0:
        raise RuntimeError(f"No finite energy entries in {input_path}")

    fitter = FastSourceFitter(source, finite_energy, enable_c14, c14_convolver)
    sample_label = infer_sample_label(input_path, event_data.get("metadata"), output_stem, run_id)
    os.makedirs(output_res_dir, exist_ok=True)
    os.makedirs(output_fig_dir, exist_ok=True)

    print(f"[Info] Starting fast {source} fit for {sample_label}", flush=True)
    fitter.fit()
    print(f"[Progress] Fast {source} fit finished for {sample_label}", flush=True)

    npz_path = f"{output_res_dir}/{sample_label}.npz"
    np.savez(npz_path, **fitter.dict_result)
    outputs = {"result_npz": npz_path, "sample_label": sample_label}

    if not results_only:
        from plot_style import apply_runner_plot_style
        apply_runner_plot_style()
        fig, ax = plt.subplots(figsize=(5, 4))
        comp = fitter.dict_result["components"]
        cv = fitter.dict_result["center_gauss"]["value"]
        sv = fitter.dict_result["sigma_gauss"]["value"]
        ax.errorbar(fitter.bins_center[fitter.index_nonzero],
                     fitter.data_binned[fitter.index_nonzero],
                     yerr=fitter.data_errors[fitter.index_nonzero],
                     fmt="o", mfc="None", color="tab:green", markersize=2, lw=0.5, label="Data")
        ax.plot(fitter.bins_center[fitter.index_nonzero],
                comp["model_result"][fitter.index_nonzero], "k-", lw=1.0,
                label=f"$\\chi^2/ndf$: {fitter.dict_result['chi2']:.0f}/{fitter.dict_result['ndf']}")
        ax.fill_between(fitter.bins_center, np.zeros_like(comp["bkg_conv"]),
                         comp["bkg_conv"], label="Compton", color="tab:orange", alpha=0.3)
        ax.plot(fitter.bins_center, comp["FEP_hist"], "r-", lw=1.5,
                label=f"$\\mu$={cv:.3f}, $\\sigma/E$={sv/cv*100:.2f}%")
        ax.plot(fitter.bins_center, comp["one_pileup"] + comp["two_pileup"],
                "purple", ls="--", lw=1.0, label="$^{14}$C pile-up")
        ax.set_yscale("log")
        ax.set_ylim(1e-3, max(comp["FEP_hist"]) * 10)
        ax.legend(fontsize=8, loc="upper right")
        ax.set_xlabel("E_rec [MeV]")
        ax.set_ylabel("Counts/bin")
        ax.set_title(f"{sample_label.replace('_', ' ')} {source} Fast Fit")
        ax.grid(True, alpha=0.3)
        fig_path = f"{output_fig_dir}/{sample_label}.pdf"
        fig.savefig(fig_path, bbox_inches="tight")
        plt.close(fig)
        outputs["figure"] = fig_path

    return outputs