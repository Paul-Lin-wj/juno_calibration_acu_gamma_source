from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

try:
    _PROJ_ROOT = Path(__file__).resolve().parent.parent
    cache_root = _PROJ_ROOT / "TMP"
    cache_root.mkdir(parents=True, exist_ok=True)
    mpl_cache = cache_root / "matplotlib"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(mpl_cache)
    numba_cache = cache_root / "numba"
    numba_cache.mkdir(parents=True, exist_ok=True)
    os.environ["NUMBA_CACHE_DIR"] = str(numba_cache)
except Exception as exc:
    print(f"[Warning] Failed to set fast fitter cache directories: {exc}", flush=True)

import matplotlib.pyplot as plt
import numpy as np
from iminuit import Minuit
from iminuit.cost import LeastSquares

# ================= 确保本地模块在 path 上 =================
_PROJ_ROOT = Path(__file__).resolve().parent.parent
for _p in ["src", "fitters", "smx_ana"]:
    _path = str(_PROJ_ROOT / _p)
    if _path not in sys.path:
        sys.path.insert(0, _path)

try:
    import smx_ana
except ImportError:
    smx_ana = None

from input_loader import infer_sample_label, normalize_event_input
from plot_style import apply_runner_plot_style
from fitters.Compat import GetBinCenter
from fitters.FitterUtils import (
    EnergyResolutionModel,
    FEP_part,
    build_c14_pileup_terms,
    extract_fit_results,
    normalize_histogram,
    sum_distributions_fft,
    sum_distributions_fast,
)


apply_runner_plot_style()

SOURCE_DIR = _PROJ_ROOT / "fitters"
BKG_PATH = SOURCE_DIR / "Ge68_MCbased_BKG_v4.npz"
BINS_C14 = np.arange(0, 0.2, 0.001)
BINS_C14_CENTER = GetBinCenter(BINS_C14)
C14_CONVOLVERS = ("python", "fft")
DEFAULT_C14_CONVOLVER = "fft"


def _bootstrap_smx_ana() -> None:
    global smx_ana
    if smx_ana is not None:
        return
    if "smx_ana.smx_ana_cpp" in sys.modules:
        import smx_ana as loaded_smx_ana

        smx_ana = loaded_smx_ana
        return

    # smx_ana should already be importable from the local path set above
    try:
        import smx_ana as loaded_smx_ana
        smx_ana = loaded_smx_ana
        print(f"[Info] smx_ana loaded from: {smx_ana.__file__}", flush=True)
        return
    except ImportError:
        pass

    candidate_roots = []
    env_root = os.environ.get("SMX_ANA_ROOT", "").strip()
    if env_root:
        candidate_roots.append(Path(env_root).expanduser())

    seen_roots: set[str] = set()
    for root in candidate_roots:
        resolved = root.expanduser()
        resolved_str = str(resolved)
        if resolved_str in seen_roots:
            continue
        seen_roots.add(resolved_str)

        package_dir = resolved / "smx_ana"
        if package_dir.is_dir() and resolved_str not in sys.path:
            sys.path.insert(0, resolved_str)

        extension_candidates = list(resolved.glob("build/**/smx_ana_cpp*.so"))
        extension_candidates.extend(resolved.glob("cpp/build/**/smx_ana_cpp*.so"))
        if not extension_candidates:
            continue

        extension_path = sorted(extension_candidates)[0]
        spec = importlib.util.spec_from_file_location("smx_ana.smx_ana_cpp", extension_path)
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        sys.modules["smx_ana.smx_ana_cpp"] = module
        sys.modules.setdefault("smx_ana_cpp", module)
        spec.loader.exec_module(module)
        import smx_ana as loaded_smx_ana

        smx_ana = loaded_smx_ana
        print(f"[Info] Loaded smx_ana extension from: {extension_path}", flush=True)
        return

    raise RuntimeError("Could not import or bootstrap smx_ana. Set SMX_ANA_ROOT to the AnalysisTool root.")


def _weighted_histogram(values: np.ndarray, bins: np.ndarray, scale: float) -> np.ndarray:
    return np.histogram(
        values * scale,
        bins=bins,
        weights=np.ones_like(values) / len(values),
    )[0]


class FastGe68Fitter:
    """Ge68 fitter variant that caches fixed template histograms/convolutions.

    This keeps the same floating parameterization as the legacy Ge68 fitter for
    the default fixed E_scale/a/b/c/C14_Amp settings, while avoiding repeated
    MC-template histogramming and smearing during Minuit evaluations.
    """

    def __init__(
        self,
        bins_fit: np.ndarray,
        data_arr: np.ndarray,
        is_hist: bool,
        data_err: np.ndarray | None = None,
        bkg_path: str | Path = BKG_PATH,
        x_limit: float = 0.51,
        enable_c14: bool = True,
        c14_convolver: str = DEFAULT_C14_CONVOLVER,
    ):
        _bootstrap_smx_ana()
        if c14_convolver not in C14_CONVOLVERS:
            raise ValueError(f"Unsupported C14 convolver: {c14_convolver}")
        self.MC_Qedep_Center = 0.8845
        self.x_limit = x_limit
        self.enable_c14 = enable_c14
        self.c14_convolver = c14_convolver
        self.c14_convolver_func = self._select_c14_convolver(c14_convolver)
        self.bkg_data = self._load_background_data(bkg_path)
        self.bins_fit = bins_fit
        self.bins_center = GetBinCenter(bins_fit)
        self.bins_C14 = BINS_C14
        self.bins_C14_center = BINS_C14_CENTER

        self.data_binned: np.ndarray
        self.data_errors: np.ndarray
        self.index_nonzero: np.ndarray
        self.total_count: float
        self._initialize_fit_data(data_arr, is_hist, data_err)

        self.cached: dict[str, np.ndarray | float] = {}
        self.minuit_core: Minuit
        self.dict_result: dict | None = None
        self.stage_timing: dict[str, dict[str, float]] = {}
        self.profile_timing: dict[str, dict[str, float]] = {}
        self.model_eval_count = 0
        self._setup_minuit()

    def _select_c14_convolver(self, name: str):
        if name == "python":
            return sum_distributions_fast
        if name == "fft":
            return sum_distributions_fft
        raise ValueError(f"Unsupported C14 convolver: {name}")

    def _load_background_data(self, path: str | Path) -> dict[str, np.ndarray]:
        with np.load(path) as data:
            return {key: np.asarray(value) for key, value in data.items()}

    def _initialize_fit_data(
        self,
        data_arr: np.ndarray,
        is_hist: bool,
        data_err: np.ndarray | None,
    ) -> None:
        if is_hist:
            if len(data_arr) != len(self.bins_center):
                raise ValueError("Data length does not match bins_center length.")
            data_binned = np.asarray(data_arr)
            data_errors = np.asarray(data_err) if data_err is not None else np.sqrt(data_binned)
        else:
            if data_err is not None:
                raise ValueError("data_err can only be provided when is_hist=True")
            data_binned = np.histogram(data_arr, bins=self.bins_fit)[0]
            data_errors = np.sqrt(data_binned)

        self.data_binned = data_binned
        self.data_errors = data_errors
        self.index_nonzero = (data_binned > 0) & (self.bins_center > self.x_limit)
        self.total_count = float(np.sum(self.data_binned[self.index_nonzero]))

    def _setup_minuit(self) -> None:
        max_center = self.bins_center[np.argmax(self.data_binned)]
        e_scale = max_center / self.MC_Qedep_Center
        a = 3.309
        b = 1.28
        c_value = 0.0
        c14_amp = 4.7e-2 if self.enable_c14 else 0.0
        self._cache_fixed_components(e_scale=e_scale, a=a, b=b, c=c_value)

        cost = LeastSquares(
            self.bins_center[self.index_nonzero],
            self.data_binned[self.index_nonzero],
            self.data_errors[self.index_nonzero],
            self,
        )
        m = Minuit(
            cost,
            amp_gauss=np.max(self.data_binned[self.index_nonzero]),
            center_gauss=max_center,
            sigma_gauss=max_center * 0.035,
            amp_gauss_HE=np.max(self.data_binned[self.index_nonzero]) / 10,
            center_gauss_HE=0.98 * max_center / self.MC_Qedep_Center,
            sigma_gauss_HE=0.045,
            amp_b0=np.max(self.data_binned[self.index_nonzero]) * 10,
            amp_b0_2=np.max(self.data_binned[self.index_nonzero]) * 10,
            amp_b1=np.max(self.data_binned[self.index_nonzero]) / 10,
            C14_Amp=c14_amp,
            E_scale=e_scale,
            a=a,
            b=b,
            c=c_value,
        )
        m.limits["amp_gauss_HE"] = (0, None)
        m.limits["center_gauss_HE"] = (
            m.values["center_gauss"] + 0.05,
            m.values["center_gauss"] + 0.2,
        )
        m.limits["sigma_gauss_HE"] = (
            m.values["sigma_gauss"] + 0.001,
            m.values["sigma_gauss"] + 0.015,
        )
        m.limits["amp_b0"] = (0, None)
        m.limits["amp_b0_2"] = (0, None)
        m.limits["amp_b1"] = (0, None)
        m.fixed["C14_Amp"] = True
        m.fixed["E_scale"] = True
        m.limits["a"] = (0, 5)
        m.limits["b"] = (0, 5)
        m.limits["c"] = (0, 5)
        m.fixed["a"] = True
        m.fixed["b"] = True
        m.fixed["c"] = True
        self.minuit_core = m

    def _cache_fixed_components(self, *, e_scale: float, a: float, b: float, c: float) -> None:
        energy_res = EnergyResolutionModel(self.bins_center, a, b, c)
        energy_sigma_C14 = EnergyResolutionModel(self.bins_C14_center, a, b, c)

        unit_bkg_0 = _weighted_histogram(self.bkg_data["Compton_0"], self.bins_fit, e_scale)
        unit_bkg_0_2 = _weighted_histogram(self.bkg_data["Compton_1"], self.bins_fit, e_scale)
        unit_bkg_1 = _weighted_histogram(self.bkg_data["gamma_positron_mixing"], self.bins_fit, e_scale)

        if self.enable_c14:
            c14_part = _weighted_histogram(self.bkg_data["C14"], self.bins_C14, e_scale)
        else:
            c14_part = np.zeros(len(self.bins_C14) - 1, dtype=float)

        self.cached = {
            "energy_sigma": energy_res,
            "energy_sigma_C14": energy_sigma_C14,
            "unit_bkg_conv_0": smx_ana.convolve(unit_bkg_0, self.bins_fit, energy_res).copy(),
            "unit_bkg_conv_0_2": smx_ana.convolve(unit_bkg_0_2, self.bins_fit, energy_res).copy(),
            "unit_bkg_conv_1": smx_ana.convolve(unit_bkg_1, self.bins_fit, energy_res).copy(),
            "C14_conv": smx_ana.convolve(c14_part, self.bins_C14, energy_sigma_C14).copy(),
        }

    def _add_profile_time(self, name: str, wall_s: float, cpu_s: float) -> None:
        current = self.profile_timing.setdefault(name, {"wall_s": 0.0, "cpu_s": 0.0})
        current["wall_s"] += wall_s
        current["cpu_s"] += cpu_s

    def _build_c14_pileup_terms_profiled(
        self,
        part_wo_pileup: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        if float(np.sum(self.cached["C14_conv"])) <= 0.0:
            zero_hist = np.zeros(len(self.bins_fit) - 1, dtype=float)
            return zero_hist, zero_hist.copy()

        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        z, sum_pdf = self.c14_convolver_func(
            self.bins_center,
            part_wo_pileup,
            self.bins_C14_center,
            self.cached["C14_conv"],
        )
        one_pileup = np.histogram(z, bins=self.bins_fit, weights=sum_pdf)[0]
        one_pileup = normalize_histogram(one_pileup)
        self._add_profile_time(
            "c14_one_pileup",
            time.perf_counter() - wall_start,
            time.process_time() - cpu_start,
        )

        if float(np.sum(one_pileup)) <= 0.0:
            zero_hist = np.zeros(len(self.bins_fit) - 1, dtype=float)
            return zero_hist, zero_hist.copy()

        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        z, sum_pdf_1 = self.c14_convolver_func(
            self.bins_center,
            one_pileup,
            self.bins_C14_center,
            self.cached["C14_conv"],
        )
        two_pileup = np.histogram(z, bins=self.bins_fit, weights=sum_pdf_1)[0]
        two_pileup = normalize_histogram(two_pileup)
        self._add_profile_time(
            "c14_two_pileup",
            time.perf_counter() - wall_start,
            time.process_time() - cpu_start,
        )
        return one_pileup, two_pileup

    def _model_full(
        self,
        amp_gauss,
        center_gauss,
        sigma_gauss,
        amp_gauss_HE,
        center_gauss_HE,
        sigma_gauss_HE,
        amp_b0,
        amp_b0_2,
        amp_b1,
        C14_Amp,
        profile: bool = True,
    ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        bkg_conv_0 = amp_b0 * self.cached["unit_bkg_conv_0"]
        bkg_conv_0_2 = amp_b0_2 * self.cached["unit_bkg_conv_0_2"]
        bkg_conv_1 = amp_b1 * self.cached["unit_bkg_conv_1"]
        gauss_HE = FEP_part(self.bins_center, amp_gauss_HE, center_gauss_HE, sigma_gauss_HE)
        FEP_hist = FEP_part(self.bins_center, amp_gauss, center_gauss, sigma_gauss)
        part_wo_pileup = bkg_conv_0 + bkg_conv_0_2 + bkg_conv_1 + gauss_HE + FEP_hist
        if profile:
            self._add_profile_time(
                "model_nonpileup",
                time.perf_counter() - wall_start,
                time.process_time() - cpu_start,
            )

        if profile:
            one_pileup, two_pileup = self._build_c14_pileup_terms_profiled(part_wo_pileup)
        else:
            one_pileup, two_pileup = build_c14_pileup_terms(
                self.bins_center,
                part_wo_pileup,
                self.bins_fit,
                self.bins_C14_center,
                self.cached["C14_conv"],
                self.c14_convolver_func,
            )
        scaled_one_pileup = (C14_Amp * self.total_count) * one_pileup
        scaled_two_pileup = (C14_Amp**2 * self.total_count) * two_pileup
        model_result = part_wo_pileup + scaled_one_pileup + scaled_two_pileup
        return model_result, {
            "gauss_HE": gauss_HE,
            "bkg_conv_0": bkg_conv_0,
            "bkg_conv_0_2": bkg_conv_0_2,
            "bkg_conv_1": bkg_conv_1,
            "C14_conv": self.cached["C14_conv"],
            "FEP_hist": FEP_hist,
            "one_pileup": scaled_one_pileup,
            "two_pileup": scaled_two_pileup,
            "model_result": model_result,
            "part_wo_pileup": part_wo_pileup,
            "energy_sigma": self.cached["energy_sigma"],
            "energy_sigma_C14": self.cached["energy_sigma_C14"],
        }

    def __call__(
        self,
        x,
        amp_gauss,
        center_gauss,
        sigma_gauss,
        amp_gauss_HE,
        center_gauss_HE,
        sigma_gauss_HE,
        amp_b0,
        amp_b0_2,
        amp_b1,
        C14_Amp,
        E_scale,
        a,
        b,
        c,
    ):
        self.model_eval_count += 1
        model_result, _components = self._model_full(
            amp_gauss,
            center_gauss,
            sigma_gauss,
            amp_gauss_HE,
            center_gauss_HE,
            sigma_gauss_HE,
            amp_b0,
            amp_b0_2,
            amp_b1,
            C14_Amp,
        )
        return model_result[self.index_nonzero]

    def fit(self) -> None:
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        self.minuit_core.migrad()
        self.stage_timing["minuit_migrad"] = {
            "wall_s": time.perf_counter() - wall_start,
            "cpu_s": time.process_time() - cpu_start,
        }
        self.dict_result = extract_fit_results(self.minuit_core)
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        self._organize_component()
        self.stage_timing["organize_component"] = {
            "wall_s": time.perf_counter() - wall_start,
            "cpu_s": time.process_time() - cpu_start,
        }

    def _organize_component(self) -> None:
        if self.dict_result is None:
            raise RuntimeError("fit() must be called before organizing components.")
        values = self.dict_result
        model_result, components = self._model_full(
            values["amp_gauss"]["value"],
            values["center_gauss"]["value"],
            values["sigma_gauss"]["value"],
            values["amp_gauss_HE"]["value"],
            values["center_gauss_HE"]["value"],
            values["sigma_gauss_HE"]["value"],
            values["amp_b0"]["value"],
            values["amp_b0_2"]["value"],
            values["amp_b1"]["value"],
            values["C14_Amp"]["value"],
            profile=False,
        )
        chi2 = np.sum(
            ((self.data_binned[self.index_nonzero] - model_result[self.index_nonzero]) / self.data_errors[self.index_nonzero])
            ** 2
        )
        self.dict_result["chi2"] = chi2
        self.dict_result["ndf"] = len(self.data_binned[self.index_nonzero]) - len(self.minuit_core.parameters)
        self.dict_result["total_count"] = self.total_count
        self.dict_result["enable_c14"] = self.enable_c14
        self.dict_result["c14_convolver"] = self.c14_convolver
        self.dict_result["model_eval_count"] = self.model_eval_count
        self.dict_result["fast_cached_templates"] = True
        self.dict_result["components"] = components


def _filter_source_name(source: str) -> str:
    return {"Ge68": "{68}Ge"}.get(source, source)


def plot_fast_ge68_results(fitter: FastGe68Fitter, title_latex: str, fig_path: str, *, log_y: bool) -> None:
    if fitter.dict_result is None:
        raise RuntimeError("fit() must be called before plotting.")
    apply_runner_plot_style()
    plt.figure(figsize=(5, 4))
    components = fitter.dict_result["components"]
    total = np.sum(
        components["bkg_conv_0"]
        + components["bkg_conv_0_2"]
        + components["bkg_conv_1"]
        + components["gauss_HE"]
        + components["FEP_hist"]
        + components["one_pileup"]
        + components["two_pileup"]
    )
    c14_pileup = np.sum(components["one_pileup"]) + np.sum(components["two_pileup"])
    pile_pro = c14_pileup / total * 100 if total else 0.0
    label_text = f"$\\chi^2/ndf$: {fitter.dict_result['chi2']:.0f}/{fitter.dict_result['ndf']:.0f}\n Pile-up Pro. {pile_pro:.1f} %"

    plt.errorbar(
        fitter.bins_center[fitter.index_nonzero],
        fitter.data_binned[fitter.index_nonzero],
        yerr=fitter.data_errors[fitter.index_nonzero],
        fmt="o",
        mfc="None",
        color="tab:green",
        markersize=2,
        lw=0.5,
        label="Data",
    )
    plt.plot(
        fitter.bins_center[fitter.index_nonzero],
        components["model_result"][fitter.index_nonzero],
        color="k",
        label=label_text,
        lw=1.0,
    )
    fep_label = (
        f"$\\mu$: {fitter.dict_result['center_gauss']['value']:.3f}, "
        f"$\\sigma$: {fitter.dict_result['sigma_gauss']['value']:.3f}\n"
        f"$\\sigma/E$: {100 * fitter.dict_result['sigma_gauss']['value'] / fitter.dict_result['center_gauss']['value']:.2f} %"
    )
    plt.plot(fitter.bins_center, components["FEP_hist"], label=fep_label, color="tab:red", lw=1.5)
    plt.fill_between(fitter.bins_center, np.zeros_like(components["bkg_conv_0"]), components["bkg_conv_0"], label="MC: Compton", color="tab:orange", alpha=0.3)
    plt.fill_between(fitter.bins_center, np.zeros_like(components["bkg_conv_0_2"]), components["bkg_conv_0_2"], label="MC: $e^{+}$ in-flight", color="tab:green", alpha=0.3)
    plt.fill_between(fitter.bins_center - 0.02, np.zeros_like(components["gauss_HE"]), components["gauss_HE"] * 2, label="$\\gamma \\sim$1.08 MeV", color="tab:purple", alpha=0.3)
    plt.fill_between(fitter.bins_center, np.zeros_like(components["bkg_conv_1"]), components["bkg_conv_1"], label="MC: $e^{+}+\\gamma$", color="tab:blue", alpha=0.2)
    plt.plot(fitter.bins_center, components["one_pileup"] + components["two_pileup"], label="$^{14}$C pile-up\n(single & double)", color="tab:purple", ls="--", lw=1.5)
    plt.legend(fontsize=10, loc="upper right", framealpha=0.7)
    plt.xlabel("E$_{\\mathrm{rec}}$ [MeV]", fontsize=14)
    plt.ylabel("Event Rate [Hz/bin]", fontsize=14)
    plt.tick_params(axis="both", which="major", labelsize=12)
    if log_y:
        plt.semilogy()
        positive = components["FEP_hist"][components["FEP_hist"] > 0]
        upper = max(positive) * 10 if len(positive) else None
        if upper is not None:
            plt.ylim(1e-3, upper)
    else:
        plt.ylim(0, None)
    plt.title(title_latex, fontsize=16)
    plt.grid(True, alpha=0.3)
    os.makedirs(os.path.dirname(fig_path) or ".", exist_ok=True)
    plt.savefig(fig_path, bbox_inches="tight")
    plt.close()


def run_fast_ge68_fitter(
    *,
    run_id: int | None = None,
    input_path: str,
    output_fig_dir: str,
    output_res_dir: str,
    output_stem: str = "",
    enable_c14: bool = True,
    c14_convolver: str = DEFAULT_C14_CONVOLVER,
    results_only: bool = False,
    timing_output_path: str | None = None,
) -> dict[str, object]:
    timing: dict[str, object] = {
        "mode": "fast_c14_on" if enable_c14 else "fast_c14_off",
        "enable_c14": bool(enable_c14),
        "c14_convolver": c14_convolver,
        "results_only": bool(results_only),
        "stages": {},
    }
    total_wall_start = time.perf_counter()
    total_cpu_start = time.process_time()

    stage_wall_start = time.perf_counter()
    stage_cpu_start = time.process_time()
    event_data = normalize_event_input(input_path, "Ge68")
    energy = np.asarray(event_data["energy"], dtype=float)
    finite_energy = energy[np.isfinite(energy)]
    if finite_energy.shape[0] == 0:
        raise RuntimeError(f"No finite energy entries were found in {input_path}")
    timing["stages"]["input_load"] = {
        "wall_s": time.perf_counter() - stage_wall_start,
        "cpu_s": time.process_time() - stage_cpu_start,
    }

    bins_fit = np.arange(0.3, 2.0, 0.004)
    stage_wall_start = time.perf_counter()
    stage_cpu_start = time.process_time()
    fitter = FastGe68Fitter(
        bins_fit=bins_fit,
        data_arr=finite_energy,
        is_hist=False,
        x_limit=0.51,
        enable_c14=enable_c14,
        c14_convolver=c14_convolver,
    )
    timing["stages"]["fitter_init"] = {
        "wall_s": time.perf_counter() - stage_wall_start,
        "cpu_s": time.process_time() - stage_cpu_start,
    }
    sample_label = infer_sample_label(input_path, metadata=event_data.get("metadata"), explicit_label=output_stem, run_id=run_id)
    os.makedirs(output_res_dir, exist_ok=True)
    os.makedirs(output_fig_dir, exist_ok=True)

    print(f"[Info] Starting fast Ge68 fit for {sample_label}", flush=True)
    stage_wall_start = time.perf_counter()
    stage_cpu_start = time.process_time()
    fitter.fit()
    timing["stages"]["fit"] = {
        "wall_s": time.perf_counter() - stage_wall_start,
        "cpu_s": time.process_time() - stage_cpu_start,
    }
    timing["stages"].update(fitter.stage_timing)
    timing["stages"].update(fitter.profile_timing)
    timing["model_eval_count"] = int(fitter.model_eval_count)
    print(f"[Progress] Fast Ge68 fit finished for {sample_label}", flush=True)

    npz_path = f"{output_res_dir}/{sample_label}.npz"
    stage_wall_start = time.perf_counter()
    stage_cpu_start = time.process_time()
    np.savez(npz_path, **fitter.dict_result)
    timing["stages"]["write_npz"] = {
        "wall_s": time.perf_counter() - stage_wall_start,
        "cpu_s": time.process_time() - stage_cpu_start,
    }
    outputs = {"result_npz": npz_path, "sample_label": sample_label, "input_path": input_path}
    print(f"[Output] Fit results saved to: {npz_path}", flush=True)

    if not results_only:
        stage_wall_start = time.perf_counter()
        stage_cpu_start = time.process_time()
        title = f"{sample_label.replace('_', ' ')} $^{{{_filter_source_name('Ge68')}}}$ Fast Fitting Result"
        fig_path = f"{output_fig_dir}/{sample_label}.pdf"
        plot_fast_ge68_results(fitter, title, fig_path, log_y=True)
        timing["stages"]["plot"] = {
            "wall_s": time.perf_counter() - stage_wall_start,
            "cpu_s": time.process_time() - stage_cpu_start,
        }
        outputs["figure"] = fig_path
        print(f"[Output] Log-y figure saved to: {fig_path}", flush=True)

    timing["total_wall_s"] = time.perf_counter() - total_wall_start
    timing["total_cpu_s"] = time.process_time() - total_cpu_start
    timing["event_count"] = int(finite_energy.shape[0])
    timing["sample_label"] = sample_label
    timing["input_path"] = str(input_path)
    outputs["timing"] = timing
    if timing_output_path:
        timing_path = Path(timing_output_path)
        timing_path.parent.mkdir(parents=True, exist_ok=True)
        timing_path.write_text(json.dumps(timing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outputs["timing_json"] = str(timing_path)
        print(f"[Output] Timing saved to: {timing_path}", flush=True)

    return outputs
