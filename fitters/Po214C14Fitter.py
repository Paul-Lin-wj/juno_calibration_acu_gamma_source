from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import smx_ana
from iminuit import Minuit
from iminuit.cost import LeastSquares

from plot_style import apply_fitter_plot_style
from .Compat import GetBinCenter
from .FitterUtils import (
    EnergyResolutionModel,
    FEP_part,
    build_c14_pileup_terms,
    extract_fit_results,
    sum_distributions_fft,
)

apply_fitter_plot_style()

PROJECT_ROOT = Path(__file__).parent
DEFAULT_C14_TEMPLATE_PATH = PROJECT_ROOT / "Ge68_MCbased_BKG_v4.npz"
PO214_MIN_FIT_EVENTS = 50
DEFAULT_C14_AMP = 4.7e-2
bins_C14 = np.arange(0, 0.2, 0.001)
bins_C14_center = GetBinCenter(bins_C14)


class Po214C14Fitter:
    def __init__(
        self,
        bins_fit: np.ndarray,
        data_arr: np.ndarray,
        is_hist: bool,
        data_err: np.ndarray | None = None,
        bkg_path: str | Path = DEFAULT_C14_TEMPLATE_PATH,
        enable_c14: bool = True,
        fix_c14_amplitude: bool = True,
        if_fix_abc: bool = True,
    ):
        self.enable_c14 = bool(enable_c14)
        self.fix_c14_amplitude = bool(fix_c14_amplitude)
        self.if_fix_abc = bool(if_fix_abc)
        self.bkg_data = self._load_background_data(bkg_path)
        self.bins_fit = np.asarray(bins_fit, dtype=float)
        self.bins_center = GetBinCenter(self.bins_fit)
        self.bins_C14 = bins_C14
        self.bins_C14_center = bins_C14_center

        self.index_nonzero = None
        self.data_binned = None
        self.data_errors = None
        self.total_count = 0.0
        self._c14_cache_key = None
        self._c14_cache_value = None
        self._initialize_fit_data(data_arr, is_hist, data_err)

        self.minuit_core = None
        self._setup_minuit()
        self.dict_result = None

    def __call__(
        self,
        x,
        amp_gauss,
        center_gauss,
        sigma_gauss,
        pol1_intercept,
        pol1_slope,
        C14_Amp,
        E_scale,
        a,
        b,
        c,
    ):
        return self._model_components(
            amp_gauss,
            center_gauss,
            sigma_gauss,
            pol1_intercept,
            pol1_slope,
            C14_Amp,
            E_scale,
            a,
            b,
            c,
        )["model_result"][self.index_nonzero]

    def _load_background_data(self, path: str | Path) -> dict[str, np.ndarray]:
        data = np.load(path)
        if "C14" not in data.files:
            raise RuntimeError(f"C14 template key is missing from background file: {path}")
        return {"C14": np.asarray(data["C14"], dtype=float)}

    def _initialize_fit_data(
        self,
        data_arr: np.ndarray,
        is_hist: bool,
        data_err: np.ndarray | None = None,
    ) -> None:
        if is_hist:
            data_binned = np.asarray(data_arr, dtype=float)
            if len(data_binned) != len(self.bins_center):
                raise ValueError("Data length does not match bins_center length.")
            if data_err is not None:
                data_errors = np.asarray(data_err, dtype=float)
                if len(data_errors) != len(self.bins_center):
                    raise ValueError("Error data length does not match bins_center length.")
            else:
                data_errors = np.sqrt(np.clip(data_binned, 0.0, None))
            event_count = float(np.sum(data_binned))
        else:
            if data_err is not None:
                raise ValueError("data_err can only be provided when is_hist=True")
            finite = np.asarray(data_arr, dtype=float)
            finite = finite[np.isfinite(finite)]
            event_count = float(finite.size)
            data_binned = np.histogram(finite, bins=self.bins_fit)[0].astype(float)
            data_errors = np.sqrt(data_binned)

        if event_count < PO214_MIN_FIT_EVENTS:
            raise RuntimeError(
                f"Po214 C14 fit requires at least {PO214_MIN_FIT_EVENTS} events; got {event_count:.0f}"
            )
        self.data_binned = data_binned
        self.data_errors = data_errors
        self.index_nonzero = data_binned > 0
        if int(np.count_nonzero(self.index_nonzero)) < 5:
            raise RuntimeError("Po214 C14 fit requires at least 5 populated histogram bins.")
        self.total_count = float(np.sum(self.data_binned[self.index_nonzero]))
        print("Po214 data initialized")

    def _setup_minuit(self) -> None:
        positive = self.index_nonzero
        max_center = float(self.bins_center[np.argmax(self.data_binned)])
        positive_counts = self.data_binned[positive]
        baseline0 = float(np.median(positive_counts))
        amp0 = max(float(np.max(positive_counts)) - baseline0, 1.0)
        mean0 = float(np.average(self.bins_center[positive], weights=positive_counts))
        variance0 = float(np.average((self.bins_center[positive] - mean0) ** 2, weights=positive_counts))
        sigma0 = max(np.sqrt(max(variance0, 0.0)), 0.01)

        cost = LeastSquares(
            self.bins_center[positive],
            self.data_binned[positive],
            np.sqrt(self.data_binned[positive] + 1.0),
            self,
        )
        m = Minuit(
            cost,
            amp_gauss=amp0,
            center_gauss=max_center,
            sigma_gauss=sigma0,
            pol1_intercept=baseline0,
            pol1_slope=0.0,
            C14_Amp=DEFAULT_C14_AMP if self.enable_c14 else 0.0,
            E_scale=1.0,
            a=3.309,
            b=1.28,
            c=0.0,
        )
        m.limits["amp_gauss"] = (0, None)
        m.limits["center_gauss"] = (float(self.bins_fit[0]), float(self.bins_fit[-1]))
        m.limits["sigma_gauss"] = (1.0e-4, max(float(self.bins_fit[-1] - self.bins_fit[0]), 1.0e-3))
        m.limits["C14_Amp"] = (0, None)
        m.limits["E_scale"] = (0.8, 1.2)
        m.fixed["E_scale"] = True
        m.limits["a"] = (0, 5)
        m.limits["b"] = (0, 5)
        m.limits["c"] = (0, 5)
        if self.if_fix_abc:
            m.fixed["a"] = True
            m.fixed["b"] = True
            m.fixed["c"] = True
        m.fixed["C14_Amp"] = (not self.enable_c14) or self.fix_c14_amplitude
        self.minuit_core = m

    def _c14_component(self, E_scale: float, a: float, b: float, c: float) -> np.ndarray:
        cache_key = (bool(self.enable_c14), float(E_scale), float(a), float(b), float(c))
        if self._c14_cache_key == cache_key and self._c14_cache_value is not None:
            return self._c14_cache_value
        if self.enable_c14:
            c14_part = np.histogram(
                self.bkg_data["C14"] * E_scale,
                bins=self.bins_C14,
                weights=np.ones_like(self.bkg_data["C14"]) / len(self.bkg_data["C14"]),
            )[0]
        else:
            c14_part = np.zeros(len(self.bins_C14) - 1, dtype=float)
        energy_sigma_C14 = EnergyResolutionModel(self.bins_C14_center, a, b, c)
        self._c14_cache_key = cache_key
        self._c14_cache_value = smx_ana.convolve(c14_part, self.bins_C14, energy_sigma_C14).copy()
        return self._c14_cache_value

    def _model_components(
        self,
        amp_gauss,
        center_gauss,
        sigma_gauss,
        pol1_intercept,
        pol1_slope,
        C14_Amp,
        E_scale,
        a,
        b,
        c,
    ) -> dict[str, np.ndarray]:
        gaussian = FEP_part(self.bins_center, amp_gauss, center_gauss, sigma_gauss)
        pol1_background = pol1_intercept + pol1_slope * self.bins_center
        C14_conv = self._c14_component(E_scale, a, b, c)
        one_pileup, two_pileup = build_c14_pileup_terms(
            self.bins_center,
            gaussian,
            self.bins_fit,
            self.bins_C14_center,
            C14_conv,
            sum_distributions_fft,
        )
        scaled_one_pileup = (C14_Amp * self.total_count) * one_pileup
        scaled_two_pileup = (C14_Amp**2 * self.total_count) * two_pileup
        model_result = gaussian + scaled_one_pileup + scaled_two_pileup + pol1_background
        return {
            "FEP_hist": gaussian,
            "pol1_background": pol1_background,
            "C14_conv": C14_conv,
            "one_pileup": scaled_one_pileup,
            "two_pileup": scaled_two_pileup,
            "model_result": model_result,
            "C14_Amp_effective": np.asarray(C14_Amp),
        }

    def _organize_component(self) -> None:
        values = self.dict_result
        components = self._model_components(
            values["amp_gauss"]["value"],
            values["center_gauss"]["value"],
            values["sigma_gauss"]["value"],
            values["pol1_intercept"]["value"],
            values["pol1_slope"]["value"],
            values["C14_Amp"]["value"],
            values["E_scale"]["value"],
            values["a"]["value"],
            values["b"]["value"],
            values["c"]["value"],
        )
        model_result = components["model_result"][self.index_nonzero]
        chi2 = np.sum(
            ((self.data_binned[self.index_nonzero] - model_result) / np.sqrt(self.data_binned[self.index_nonzero] + 1.0)) ** 2
        )
        n_free = sum(not self.minuit_core.fixed[name] for name in self.minuit_core.parameters)
        ndf = len(self.data_binned[self.index_nonzero]) - n_free
        self.dict_result["chi2"] = float(chi2)
        self.dict_result["ndf"] = int(ndf)
        self.dict_result["total_count"] = self.total_count
        self.dict_result["enable_c14"] = self.enable_c14
        self.dict_result["fix_c14_amplitude"] = self.fix_c14_amplitude
        self.dict_result["bins_center"] = self.bins_center
        self.dict_result["data_binned"] = self.data_binned
        self.dict_result["components"] = components

    def fit(self) -> None:
        try:
            display(self.minuit_core.migrad())
        except Exception:
            self.minuit_core.migrad()
        self.dict_result = extract_fit_results(self.minuit_core)
        self._organize_component()


def Po214_plot_results(
    EnergyFitclss: object,
    title_latex: str,
    fig_path: str,
    ylabel_show: str,
    ylimit=1e-3,
    if_show_ylog=True,
) -> None:
    apply_fitter_plot_style()
    plt.figure(figsize=(5, 4))
    bins_center = EnergyFitclss.bins_center
    data_binned = EnergyFitclss.data_binned
    components = EnergyFitclss.dict_result["components"]
    c14_pileup = components["one_pileup"] + components["two_pileup"]

    plt.errorbar(
        bins_center,
        data_binned,
        yerr=np.sqrt(data_binned + 1.0),
        fmt="o",
        markersize=2.5,
        color="black",
        label="Data",
    )
    plt.plot(bins_center, components["model_result"], color="tab:red", label="Gaussian + C14 + pol1")
    plt.plot(bins_center, components["FEP_hist"], color="tab:blue", linestyle="--", label="Gaussian")
    plt.plot(bins_center, components["pol1_background"], color="tab:green", linestyle=":", label="pol1")
    plt.fill_between(bins_center, np.zeros_like(c14_pileup), c14_pileup, color="tab:purple", alpha=0.3, label="C14 pileup")

    center = EnergyFitclss.dict_result["center_gauss"]["value"]
    sigma = EnergyFitclss.dict_result["sigma_gauss"]["value"]
    c14_amp = EnergyFitclss.dict_result["C14_Amp"]["value"]
    plt.text(
        0.04,
        0.95,
        f"$\\mu$: {center:.4f} MeV\n$\\sigma$: {sigma:.4f} MeV\nC14_Amp: {c14_amp:.4g}",
        transform=plt.gca().transAxes,
        va="top",
        fontsize=9,
    )
    plt.title(title_latex)
    plt.xlabel("Reconstructed energy [MeV]")
    plt.ylabel(ylabel_show)
    plt.xlim(EnergyFitclss.bins_fit[0], EnergyFitclss.bins_fit[-1])
    if if_show_ylog:
        positive_max = max(float(np.max(data_binned)), float(np.max(components["model_result"])), 1.0)
        plt.yscale("log")
        plt.ylim(ylimit, positive_max * 2.0)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(fig_path, dpi=300, bbox_inches="tight")
