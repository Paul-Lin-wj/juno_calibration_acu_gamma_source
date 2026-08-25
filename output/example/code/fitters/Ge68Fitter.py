import numpy as np
import matplotlib.pyplot as plt
from matplotlib import pyplot as plt
import os
import smx_ana
from iminuit import Minuit
from iminuit.cost import LeastSquares
from plot_style import apply_fitter_plot_style
from .Compat import GetBinCenter
from .FitterUtils import *

apply_fitter_plot_style()

bins_C14 = np.arange(0, 0.2, 0.001)
bins_C14_center = GetBinCenter(bins_C14)

def calculate_components(dict_result, bins_center, dict_bkg, bins_fit):
    """Calculate all components of the fit for plotting, including C14 pileup."""
    # Energy resolution
    energy_sigma = EnergyResolutionModel(
        bins_center,
        dict_result["a"]["value"],
        dict_result["b"]["value"],
        dict_result["c"]["value"],
    )
    
    # C14 energy resolution
    energy_sigma_C14 = EnergyResolutionModel(
        bins_C14_center,
        dict_result["a"]["value"],
        dict_result["b"]["value"],
        dict_result["c"]["value"],
    )

    # High energy gaussian
    gauss_HE = FEP_part(bins_center,
        dict_result["amp_gauss_HE"]["value"],
        dict_result["center_gauss_HE"]["value"],
        dict_result["sigma_gauss_HE"]["value"])

    # Background components
    bkg_0_part = (
        dict_result["amp_b0"]["value"]
        * np.histogram(
            dict_bkg["Compton_0"] * dict_result["E_scale"]["value"],
            bins=bins_fit,
            weights=np.ones_like(dict_bkg["Compton_0"]) / len(dict_bkg["Compton_0"]),
        )[0]
    )
    bkg_0_2_part = (
        dict_result["amp_b0_2"]["value"]
        * np.histogram(
            dict_bkg["Compton_1"] * dict_result["E_scale"]["value"],
            bins=bins_fit,
            weights=np.ones_like(dict_bkg["Compton_1"]) / len(dict_bkg["Compton_1"]),
        )[0]
    )

    bkg_conv_0 = smx_ana.convolve(bkg_0_part, bins_fit, energy_sigma).copy()
    bkg_conv_0_2 = smx_ana.convolve(bkg_0_2_part, bins_fit, energy_sigma).copy()

    bkg_1_part = (
        dict_result["amp_b1"]["value"]
        * np.histogram(
            dict_bkg["gamma_positron_mixing"] * dict_result["E_scale"]["value"],
            bins=bins_fit,
            weights=np.ones_like(dict_bkg["gamma_positron_mixing"])
            / len(dict_bkg["gamma_positron_mixing"]),
        )[0]
    )
    bkg_conv_1 = smx_ana.convolve(bkg_1_part, bins_fit, energy_sigma).copy()

    # C14 background
    if dict_result.get("enable_c14", True):
        C14_part = np.histogram(
            dict_bkg["C14"] * dict_result["E_scale"]["value"],
            bins=bins_C14,
            weights=np.ones_like(dict_bkg["C14"]) / len(dict_bkg["C14"]),
        )[0]
    else:
        C14_part = np.zeros(len(bins_C14) - 1, dtype=float)
    C14_conv = smx_ana.convolve(C14_part, bins_C14, energy_sigma_C14).copy()

    # Full energy peak
    FEP_hist = FEP_part(
        bins_center=bins_center,
        amp_gauss=dict_result["amp_gauss"]["value"],
        center_gauss=dict_result["center_gauss"]["value"],
        sigma_gauss=dict_result["sigma_gauss"]["value"],
    )

    # Combine all components without pileup
    part_wo_pileup = bkg_conv_0 + bkg_conv_0_2 + bkg_conv_1 + gauss_HE + FEP_hist

    # Calculate pileup effects (following K40 logic)
    one_pileup, two_pileup = build_c14_pileup_terms(
        bins_center,
        part_wo_pileup,
        bins_fit,
        bins_C14_center,
        C14_conv,
        sum_distributions_fast,
    )

    C14_Amp = dict_result["C14_Amp"]["value"]
    model_result = (
        part_wo_pileup
          + (C14_Amp* dict_result["total_count"]) * one_pileup
            + (C14_Amp**2 * dict_result["total_count"]) * two_pileup
    )

    return {
        "energy_sigma": energy_sigma,
        "energy_sigma_C14": energy_sigma_C14,
        "gauss_HE": gauss_HE,
        "bkg_conv_0": bkg_conv_0,
        "bkg_conv_0_2": bkg_conv_0_2,
        "bkg_conv_1": bkg_conv_1,
        "C14_conv": C14_conv,
        "FEP_hist": FEP_hist,
        "one_pileup": (C14_Amp* dict_result["total_count"]) * one_pileup,
        "two_pileup": (C14_Amp**2 * dict_result["total_count"]) * two_pileup,
        "model_result": model_result,
        "part_wo_pileup": part_wo_pileup,
        "C14_Amp_effective": C14_Amp,
    }

class Ge68Fitter:
    def __init__(
        self,
        bins_fit: np.ndarray,
        data_arr: np.ndarray,
        is_hist: bool,
        data_err: np.ndarray = None,
        # bkg_path: str = "/home/yupd/myjunofs/CalibAlg/Ge68/MCbasedFitting/Ge68_MCbased_BKG_v4.npz",
        bkg_path: str = f"{PROJECT_ROOT}/Ge68_MCbased_BKG_v4.npz",
        x_limit: float = 0.5,  # Added x_limit parameter like K40 fitter
        enable_c14: bool = True,
        fix_c14_amplitude: bool = True,
        if_fix_abc: bool = True,
    ):
        self.MC_Qedep_Center = 0.8845
        self.x_limit = x_limit
        self.enable_c14 = enable_c14
        self.fix_c14_amplitude = fix_c14_amplitude
        self.if_fix_abc = if_fix_abc
        self.x_limit = x_limit
        self.bkg_data = self._load_background_data(bkg_path)
        self.bins_fit = bins_fit
        self.bins_center = GetBinCenter(bins_fit)
        
        # Store C14 bins information
        self.bins_C14 = bins_C14
        self.bins_C14_center = bins_C14_center

        self.index_nonzero = None
        self.data_binned = None
        self.data_errors = None
        self._initialize_fit_data(data_arr, is_hist, data_err)

        self.minuit_core = None
        self._setup_minuit()

        self.dict_result = None

    def __call__(
        self,
        x,  # Must be first argument for LeastSquares
        amp_gauss,
        center_gauss,
        sigma_gauss,
        amp_gauss_HE,
        center_gauss_HE,
        sigma_gauss_HE,
        amp_b0,
        amp_b0_2,
        amp_b1,
        C14_Amp,  # Added C14 amplitude parameter
        E_scale,
        a,
        b,
        c,
    ):
        """The actual fitting function with all parameters, including C14 pileup."""
        # Background components (same as before)
        bkg_part = (
            amp_b0
            * np.histogram(
                self.bkg_data["Compton_0"] * E_scale,
                bins=self.bins_fit,
                weights=np.ones_like(self.bkg_data["Compton_0"])
                / len(self.bkg_data["Compton_0"]),
            )[0]
        )
        bkg_part += (
            amp_b0_2
            * np.histogram(
                self.bkg_data["Compton_1"] * E_scale,
                bins=self.bins_fit,
                weights=np.ones_like(self.bkg_data["Compton_1"])
                / len(self.bkg_data["Compton_1"]),
            )[0]
        )
        bkg_part += (
            amp_b1
            * np.histogram(
                self.bkg_data["gamma_positron_mixing"] * E_scale,
                bins=self.bins_fit,
                weights=np.ones_like(self.bkg_data["gamma_positron_mixing"])
                / len(self.bkg_data["gamma_positron_mixing"]),
            )[0]
        )

        # C14 background
        if self.enable_c14:
            C14_part = np.histogram(
                self.bkg_data["C14"] * E_scale,
                bins=self.bins_C14,
                weights=np.ones_like(self.bkg_data["C14"]) / len(self.bkg_data["C14"]),
            )[0]
        else:
            C14_part = np.zeros(len(self.bins_C14) - 1, dtype=float)

        # Energy resolution and convolution
        energy_res = EnergyResolutionModel(self.bins_center, a, b, c)
        energy_sigma_C14 = EnergyResolutionModel(self.bins_C14_center, a, b, c)

        pdf_conv = smx_ana.convolve(bkg_part, self.bins_fit, energy_res).copy()
        C14_conv = smx_ana.convolve(C14_part, self.bins_C14, energy_sigma_C14).copy()

        # High energy peak and full energy peak
        pdf_conv += FEP_part(
            self.bins_center,
            amp_gauss_HE,
            center_gauss_HE,
            sigma_gauss_HE
        )

        full_energy_part = FEP_part(
            self.bins_center,
            amp_gauss,
            center_gauss,
            sigma_gauss
        )

        # Combine components without pileup
        part_wo_pileup = pdf_conv + full_energy_part

        # Calculate pileup effects (following K40 logic)
        one_pileup, two_pileup = build_c14_pileup_terms(
            self.bins_center,
            part_wo_pileup,
            self.bins_fit,
            self.bins_C14_center,
            C14_conv,
            sum_distributions_fast,
        )

        result = (
            part_wo_pileup
            + (C14_Amp * self.total_count) * one_pileup
            + (C14_Amp**2 * self.total_count) * two_pileup
        )
        return result[self.index_nonzero]

    def _load_background_data(self, path: str) -> dict:
        data = np.load(path)
        return {k: np.array(v) for k, v in data.items()}

    def _initialize_fit_data(
        self, data_arr: np.ndarray, is_hist: bool, data_err: np.ndarray = None
    ) -> tuple:
        """Initialize the fitting data."""
        if is_hist:
            if len(data_arr) != len(self.bins_center):
                raise ValueError("Data length does not match bins_center length.")
            data_binned = data_arr

            if data_err is not None:
                if len(data_err) != len(self.bins_center):
                    raise ValueError(
                        f"Error data length {len(data_err)} doesn't match bins_center length {len(self.bins_center)}."
                    )
                data_errors = np.array(data_err)
            else:
                data_errors = np.sqrt(data_binned)
        else:
            if data_err is not None:
                raise ValueError("data_err can only be provided when is_hist=True")
            data_binned = np.histogram(data_arr, bins=self.bins_fit)[0]
            data_errors = np.sqrt(data_binned)

        self.data_binned = data_binned
        self.data_errors = data_errors
        self.index_nonzero = (data_binned > 0) & (self.bins_center > self.x_limit)
        self.total_count = np.sum(self.data_binned[self.index_nonzero])
        print("Data initialized")
        self._setup_minuit()

    def _setup_minuit(self):
        """Configure Minuit fitter with initial parameters including C14."""
        max_center = self.bins_center[np.argmax(self.data_binned)]
        
        c = LeastSquares(
            self.bins_center[self.index_nonzero],
            self.data_binned[self.index_nonzero],
            self.data_errors[self.index_nonzero],
            self,
        )

        # Initialize Minuit with parameters (added C14_Amp)
        m = Minuit(
            c,
            amp_gauss=np.max(self.data_binned[self.index_nonzero]),
            center_gauss=max_center,
            sigma_gauss=max_center * 0.035,
            amp_gauss_HE=np.max(self.data_binned[self.index_nonzero]) / 10,
            center_gauss_HE=0.98 * max_center / self.MC_Qedep_Center,
            sigma_gauss_HE=0.045,
            amp_b0=np.max(self.data_binned[self.index_nonzero]) * 10,
            amp_b0_2=np.max(self.data_binned[self.index_nonzero]) * 10,
            amp_b1=np.max(self.data_binned[self.index_nonzero]) / 10,
            C14_Amp=4.7 * 1e-2 if self.enable_c14 else 0.0,  # Added C14 amplitude parameter
            E_scale=max_center / self.MC_Qedep_Center,
            a=3.309,
            b=1.28,
            c=0,
        )

        # Set parameter limits (added C14_Amp limits)
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
        # m.limits["C14_Amp"] = (0, 0.01)  # C14 amplitude limits
        m.fixed["C14_Amp"] = (not self.enable_c14) or self.fix_c14_amplitude
        m.limits["E_scale"] = (
            max_center / self.MC_Qedep_Center * 0.90,
            max_center / self.MC_Qedep_Center * 1.1,
        )
        m.fixed["E_scale"] = True
        m.limits["a"] = (0, 5)
        m.limits["b"] = (0, 5)
        m.limits["c"] = (0, 5)
        if self.if_fix_abc:
            m.fixed["a"] = True
            m.fixed["b"] = True
            m.fixed["c"] = True
        
        self.minuit_core = m

    def _organize_component(self):
        """Organize components including pileup effects."""
        model_result = self(
            self.bins_center,
            self.dict_result["amp_gauss"]["value"],
            self.dict_result["center_gauss"]["value"],
            self.dict_result["sigma_gauss"]["value"],
            self.dict_result["amp_gauss_HE"]["value"],
            self.dict_result["center_gauss_HE"]["value"],
            self.dict_result["sigma_gauss_HE"]["value"],
            self.dict_result["amp_b0"]["value"],
            self.dict_result["amp_b0_2"]["value"],
            self.dict_result["amp_b1"]["value"],
            self.dict_result["C14_Amp"]["value"],
            self.dict_result["E_scale"]["value"],
            self.dict_result["a"]["value"],
            self.dict_result["b"]["value"],
            self.dict_result["c"]["value"],
        )

        # Calculate chi2 and NDF
        chi2 = np.sum(
            (
                (self.data_binned[self.index_nonzero] - model_result)
                / self.data_errors[self.index_nonzero]
            )
            ** 2
        )
        ndf = len(self.data_binned[self.index_nonzero]) - len(
            self.minuit_core.parameters
        )
        self.dict_result["chi2"] = chi2
        self.dict_result["ndf"] = ndf
        self.dict_result["total_count"] = self.total_count
        self.dict_result["enable_c14"] = self.enable_c14
        self.dict_result["fix_c14_amplitude"] = self.fix_c14_amplitude

        # Calculate all components for plotting
        components = calculate_components(self.dict_result, self.bins_center, self.bkg_data, self.bins_fit)
        components["model_result"] = model_result
        self.dict_result["components"] = components

    def fit(self):
        """Execute the fit."""
        try:
            display(self.minuit_core.migrad())
        except:
            self.minuit_core.migrad()
        self.dict_result = extract_fit_results(self.minuit_core)
        self._organize_component()

def Ge68_plot_results(
    EnergyFitclss: object,
    title_latex: str,
    fig_path: str,
    ylabel_show: str,
    ylimit=1,
    if_show_ylog=True,
):
    """Generate and save the fitting results plot with C14 pileup components."""
    apply_fitter_plot_style()
    plt.figure(figsize=(5, 4))

    # Calculate pileup proportion
    total = np.sum(EnergyFitclss.dict_result["components"]["bkg_conv_0"]
                   + EnergyFitclss.dict_result["components"]["bkg_conv_0_2"]
                   + EnergyFitclss.dict_result["components"]["bkg_conv_1"]
                   + EnergyFitclss.dict_result["components"]["gauss_HE"]
                   + EnergyFitclss.dict_result["components"]["FEP_hist"]
                   + EnergyFitclss.dict_result["components"]["one_pileup"]
                   + EnergyFitclss.dict_result["components"]["two_pileup"])
    C14_pileup = np.sum(EnergyFitclss.dict_result["components"]["one_pileup"]) + \
                 np.sum(EnergyFitclss.dict_result["components"]["two_pileup"])

    pile_pro = C14_pileup / total * 100

    # Plot data and model
    label_text = (f"$\\chi^2/ndf$: {EnergyFitclss.dict_result['chi2']:.0f}/"
                  f"{EnergyFitclss.dict_result['ndf']:.0f}\n"
                  f" Pile-up Pro. {pile_pro:.1f} %")

    plt.errorbar(
        EnergyFitclss.bins_center[EnergyFitclss.index_nonzero],
        EnergyFitclss.data_binned[EnergyFitclss.index_nonzero],
        yerr=EnergyFitclss.data_errors[EnergyFitclss.index_nonzero],
        fmt="o",
        mfc="None",
        color="tab:green",
        markersize=2,
        lw=0.5,
        label="Data"
    )

    # Plot model total result
    plt.plot(
        EnergyFitclss.bins_center[EnergyFitclss.index_nonzero],
        EnergyFitclss.dict_result["components"]["model_result"],
        color="k",
        label=label_text,
        lw=1.0,
    )
    # Full energy peak
    FEP_label = (
        f"$\\mu$: {EnergyFitclss.dict_result['center_gauss']['value']:.3f}, "
        f"$\\sigma$: {EnergyFitclss.dict_result['sigma_gauss']['value']:.3f}\n"
        f"$\\sigma/E$: {100*EnergyFitclss.dict_result['sigma_gauss']['value']/EnergyFitclss.dict_result['center_gauss']['value']:.2f} %"
    )
    components = EnergyFitclss.dict_result["components"]
    plt.plot(
        EnergyFitclss.bins_center,
        components["FEP_hist"],
        label=FEP_label,
        color="tab:red",
        lw=1.5,
    )
    # Plot components
    

    # Background components
    plt.fill_between(
        x=EnergyFitclss.bins_center,
        y1=np.zeros_like(components["bkg_conv_0"]),
        y2=components["bkg_conv_0"],
        label="MC: Compton",
        color="tab:orange",
        alpha=0.3,
    )
    plt.fill_between(
        x=EnergyFitclss.bins_center,
        y1=np.zeros_like(components["bkg_conv_0_2"]),
        y2=components["bkg_conv_0_2"],
        label="MC: $e^{+}$ in-flight",
        color="tab:green",
        alpha=0.3,
    )
    # High energy peak
    plt.fill_between(
        x=EnergyFitclss.bins_center-0.02,
        y1=np.zeros_like(components["gauss_HE"]),
        y2=components["gauss_HE"]*2,
        label="$\\gamma \\sim$1.08 MeV",
        color="tab:purple",
        alpha=0.3,
    )
    plt.fill_between(
        x=EnergyFitclss.bins_center,
        y1=np.zeros_like(components["bkg_conv_1"]),
        y2=components["bkg_conv_1"],
        label="MC: $e^{+}+\\gamma$",
        color="tab:blue",
        alpha=0.2,
    )
    # Pileup components
    plt.plot(
        EnergyFitclss.bins_center,
        (components["one_pileup"]+ components["two_pileup"]),
        label="$^{14}$C pile-up\n(single & double)",
        color="tab:purple",
        ls="--",
        lw=1.5,
    )
    # plt.plot(
    #     EnergyFitclss.bins_center,
    #     components["two_pileup"],
    #     label="Double Pileup",
    #     color="tab:red",
    #     ls="--",
    #     lw=1.5,
    # )

    # Finalize plot
    plt.legend(fontsize=10, loc="upper right", framealpha=0.7)
    plt.xlabel("E$_{\\mathrm{rec}}$ [MeV]", fontsize=14)
    plt.ylabel(ylabel_show, fontsize=14)
    plt.tick_params(axis='both', which='major', labelsize=12)

    if if_show_ylog:
        plt.semilogy()
        plt.ylim(ylimit, max(components["FEP_hist"]) * 10)
    else:
        plt.ylim(1e-9, None)

    plt.title(f"{title_latex}", fontsize=16)
    plt.grid(True, alpha=0.3)

    # Save figure
    if fig_path is not None:
        os.makedirs(os.path.dirname(fig_path) or "./fig", exist_ok=True)
        plt.savefig(fig_path, dpi=300, bbox_inches="tight")
        plt.savefig(fig_path.replace(".png", ".pdf"), bbox_inches="tight")
        print(f"Figure saved to {fig_path}")

    return plt.gca()

def Ge68FitterRunner(
    fitted_data: np.ndarray,
    bins_fit: np.ndarray,
    is_hist: bool,
    npz_path: str,
    fig_path: str,
    fig_title: str,
    ylim: float,
    ylabel_show: str,
    data_err: np.ndarray = None,
    if_show_ylog=True,
    bkg_path: str = "/home/yupd/myjunofs/CalibAlg/Ge68/MCbasedFitting/Ge68_MCbased_BKG_v2.npz",
    x_limit: float = 0.5,
):
    """Run the Ge68 fitter with C14 pileup effects."""
    energy_fitter = Ge68Fitter(
        bins_fit=bins_fit,
        data_arr=fitted_data,
        is_hist=is_hist,
        data_err=data_err,
        bkg_path=bkg_path,
        x_limit=x_limit,
    )
    energy_fitter.fit()

    # Save results
    if npz_path is not None:
        os.makedirs(os.path.dirname(npz_path) or "./result", exist_ok=True)
        np.savez(npz_path, **energy_fitter.dict_result)

    return Ge68_plot_results(
        energy_fitter,
        title_latex=fig_title,
        fig_path=fig_path,
        ylabel_show=ylabel_show,
        ylimit=ylim,
        if_show_ylog=if_show_ylog,
    )

# Fitting example:
# MCbasedFitting(
#     fitted_data=data_fit,
#     bins_fit=bins_fit,
#     is_hist=False,
#     npz_path="test.npz",
#     fig_path="test.png",
#     fig_title="RUN17600 Mode 3 Fit with C14 Pileup",
#     ylim=1,
#     ylabel_show="Counts / 0.01 MeV",
# )
