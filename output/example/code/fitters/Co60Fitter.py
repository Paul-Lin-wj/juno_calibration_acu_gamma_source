import numpy as np
import matplotlib.pyplot as plt
from matplotlib import pyplot as plt
import smx_ana
from iminuit import Minuit
from iminuit.cost import LeastSquares
from smx_ana.smx_ana_cpp import sum_distributions_fast_cpp
from plot_style import apply_fitter_plot_style
from .Compat import GetBinCenter
from .FitterUtils import *

apply_fitter_plot_style()

bins_C14 = np.arange(0, 0.2, 0.001)
bins_C14_center = GetBinCenter(bins_C14)

def Co60_calculate_components(dict_result, bins_center, dict_bkg, bins_fit):
    energy_sigma = EnergyResolutionModel(
        bins_center,
        dict_result["a"]["value"],
        dict_result["b"]["value"],
        dict_result["c"]["value"],
    )

    energy_sigma_C14 = EnergyResolutionModel(
        bins_C14_center,
        dict_result["a"]["value"],
        dict_result["b"]["value"],
        dict_result["c"]["value"],
    )

    bkg_compton = (
        dict_result["Compton"]["value"]
        * np.histogram(
            dict_bkg["Compton"] * dict_result["E_scale"]["value"],
            bins=bins_fit,
            weights=np.ones_like(dict_bkg["Compton"]) / len(dict_bkg["Compton"]),
            # density=True,
        )[0]
    )

    if dict_result.get("enable_c14", True):
        C14_part = np.histogram(
            dict_bkg["C14"] * dict_result["E_scale"]["value"],
            bins=bins_C14,
            weights=np.ones_like(dict_bkg["C14"]) / len(dict_bkg["C14"]),
            # density=True
        )[0]
    else:
        C14_part = np.zeros(len(bins_C14) - 1, dtype=float)

    bkg_conv = smx_ana.convolve(bkg_compton, bins_fit, energy_sigma).copy()
    # C14_conv = smx_ana.convolve(C14_part, bins_C14, energy_sigma_C14).copy()
    C14_conv = C14_part

    FEP_hist = FEP_part(
        bins_center=bins_center,
        amp_gauss=dict_result["amp_gauss"]["value"],
        center_gauss=dict_result["center_gauss"]["value"],
        sigma_gauss=dict_result["sigma_gauss"]["value"],
    )

    part_wo_pileup = bkg_conv + FEP_hist

    one_pileup, two_pileup = build_c14_pileup_terms(
        bins_center,
        part_wo_pileup,
        bins_fit,
        bins_C14_center,
        C14_conv,
        sum_distributions_fast_cpp,
    )

    # C14_Amp = dict_result["C14_Amp"]["value"] * dict_result["amp_gauss"]["value"]
    C14_Amp = dict_result["C14_Amp"]["value"]

    model_result = (
        part_wo_pileup + (C14_Amp*dict_result["total_count"]) * one_pileup + ((C14_Amp)**2 * dict_result["total_count"]) * two_pileup
    )
    return {
        "energy_sigma": energy_sigma,
        "energy_sigma_C14": energy_sigma_C14,
        "bins_center": bins_center,
        "bins_C14_center": bins_C14_center,
        "bkg_conv": bkg_conv,
        "C14_conv": C14_conv,
        "FEP_hist": FEP_hist,
        "one_pileup": (C14_Amp* dict_result["total_count"]) * one_pileup,
        "two_pileup": ((C14_Amp)**2 * dict_result["total_count"]) * two_pileup,
        "model_result": model_result,
        "part_wo_pileup": part_wo_pileup,
        "C14_Amp_effective": C14_Amp,
    }


class Co60Fitter:
    def __init__(
        self,
        bins_fit: np.ndarray,
        data_arr: np.ndarray,
        is_hist: bool,
        data_err: np.ndarray = None,
        bkg_path: str = f"{PROJECT_ROOT}/Co60_Compton_BKG.npz",
        x_limit: float = 1,
        if_fix_abc: bool = True,
        enable_c14: bool = True,
        fix_c14_amplitude: bool = False,
    ):
        self.MC_Qedep_Center = 2.305448059680732
        self.x_limit = x_limit
        self.if_fix_abc = if_fix_abc
        self.enable_c14 = enable_c14
        self.fix_c14_amplitude = fix_c14_amplitude
        self.bkg_data = self._load_background_data(bkg_path)
        self.bins_fit = bins_fit
        self.bins_center = GetBinCenter(bins_fit)

        # 存储C14相关的bins信息
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
        Compton,
        C14_Amp,
        E_scale,
        a,
        b,
        c,
    ):
        """更新的拟合函数，使用专门的C14能谱处理"""
        # Compton背景
        bkg_part = (
            Compton
            * np.histogram(
                self.bkg_data["Compton"] * E_scale,
                bins=self.bins_fit,
                weights=np.ones_like(self.bkg_data["Compton"])
                / len(self.bkg_data["Compton"]),
                # density=True,
            )[0]
        )

        # C14背景 - 使用专门的C14 bins
        if self.enable_c14:
            C14_part = np.histogram(
                self.bkg_data["C14"] * E_scale,
                bins=self.bins_C14,  # 使用C14专用的bins
                weights=np.ones_like(self.bkg_data["C14"]) / len(self.bkg_data["C14"]),
                # density=True
            )[0]
        else:
            C14_part = np.zeros(len(self.bins_C14) - 1, dtype=float)

        # 能量分辨率和卷积 - 分别计算主能谱和C14能谱的分辨率
        energy_res = EnergyResolutionModel(self.bins_center, a, b, c)
        # energy_sigma_C14 = EnergyResolutionModel(self.bins_C14_center, a, b, c)

        pdf_conv = smx_ana.convolve(bkg_part, self.bins_fit, energy_res).copy()
        # C14_conv = smx_ana.convolve(C14_part, self.bins_C14, energy_sigma_C14).copy()
        C14_conv = C14_part

        # 全能峰
        full_energy_part = FEP_part(
            self.bins_center, amp_gauss, center_gauss, sigma_gauss
        )

        # 无堆积效应的部分
        part_wo_pileup = pdf_conv + full_energy_part

        # make pdf wo pile with other bin method:

        # 一次堆积 - 使用C14的bins_center
        # bins_width = self.bins_fit[1:] - self.bins_fit[:-1]
        one_pileup, two_pileup = build_c14_pileup_terms(
            self.bins_center,
            part_wo_pileup,
            self.bins_fit,
            self.bins_C14_center,
            C14_conv,
            sum_distributions_fast_cpp,
        )

        result = (
            part_wo_pileup
            + (C14_Amp*self.total_count) * one_pileup
            + (C14_Amp**2*self.total_count) * two_pileup
        )
        return result[self.index_nonzero]

    def _load_background_data(self, path: str) -> dict:
        """加载背景数据"""
        data = np.load(path)
        return {k: np.array(v) for k, v in data.items()}

    def _initialize_fit_data(
        self, data_arr: np.ndarray, is_hist: bool, data_err: np.ndarray = None
    ):
        """初始化拟合数据"""
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
        print(f"Data initialized, total count in fit range: {self.total_count}")
        self._setup_minuit()

    def _setup_minuit(self):
        """配置Minuit拟合器"""
        max_center = self.bins_center[np.argmax(self.data_binned)]

        c = LeastSquares(
            self.bins_center[self.index_nonzero],
            self.data_binned[self.index_nonzero],
            self.data_errors[self.index_nonzero],
            self,
        )

        # 参数设置
        m = Minuit(
            c,
            amp_gauss=np.max(self.data_binned[self.index_nonzero]),
            center_gauss=max_center,
            sigma_gauss=max_center * 0.0386,
            Compton=np.max(self.data_binned[self.index_nonzero]) * 10,
            # C14_Amp=0.002*0.064,  # C14幅度参数
            C14_Amp=5 * 1e-2 if self.enable_c14 else 0.0,
            E_scale=max_center / self.MC_Qedep_Center,
            a=3.309,
            b=1.28,
            c=0,
        )

        # 参数限制
        m.limits["E_scale"] = (
            max_center / self.MC_Qedep_Center * 0.50,
            max_center / self.MC_Qedep_Center * 1.1,
        )
        m.fixed["E_scale"] = True
        m.limits["a"] = (0, 4)
        m.limits["b"] = (0, 1)
        m.limits["c"] = (0, 2)
        if self.if_fix_abc:
            m.fixed["a"] = True
            m.fixed["b"] = True
            m.fixed["c"] = True

        m.limits["Compton"] = (0, None)
        m.limits["C14_Amp"] = (0, None)  # C14幅度限制
        m.fixed["C14_Amp"] = (not self.enable_c14) or self.fix_c14_amplitude

        self.minuit_core = m

    def _organize_component(self):
        """组织拟合成分"""
        # 计算模型结果
        model_result = self(
            self.bins_center,
            self.dict_result["amp_gauss"]["value"],
            self.dict_result["center_gauss"]["value"],
            self.dict_result["sigma_gauss"]["value"],
            self.dict_result["Compton"]["value"],
            self.dict_result["C14_Amp"]["value"],
            self.dict_result["E_scale"]["value"],
            self.dict_result["a"]["value"],
            self.dict_result["b"]["value"],
            self.dict_result["c"]["value"],
        )

        # 计算chi2和NDF
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

        # 计算所有成分
        components = Co60_calculate_components(
            self.dict_result, self.bins_center, self.bkg_data, self.bins_fit
        )
        components["model_result"] = model_result
        components["bins_center"] = self.bins_center[self.index_nonzero]
        self.dict_result["components"] = components

    def fit(self):
        """执行拟合"""
        (self.minuit_core.migrad())
        self.dict_result = extract_fit_results(self.minuit_core)
        self._organize_component()


def Co60_plot_results(
    EnergyFitclss: object,
    title_latex: str,
    fig_path: str,
    ylabel_show: str,
    ylimit=1,
    if_show_ylog=True,
):
    """生成并保存拟合结果图 - 更新版本显示C14和堆积效应"""
    apply_fitter_plot_style()
    plt.figure(figsize=(5, 4))
    total_count = np.sum(EnergyFitclss.dict_result["components"]["bkg_conv"]+ 
                     EnergyFitclss.dict_result["components"]["FEP_hist"]+
                     EnergyFitclss.dict_result["components"]["one_pileup"]+
                     EnergyFitclss.dict_result["components"]["two_pileup"])
    C14_part = np.sum(EnergyFitclss.dict_result["components"]["one_pileup"] + EnergyFitclss.dict_result["components"]["two_pileup"])
    pile_pro = C14_part / total_count * 100
    # 绘制数据和模型
    label_text = f"$\\chi^{{2}}/ndf$: {EnergyFitclss.dict_result['chi2']:.0f}/{EnergyFitclss.dict_result['ndf']:.0f}\nPile-up Pro. {pile_pro:.1f} %"
    plt.errorbar(
        EnergyFitclss.bins_center[EnergyFitclss.index_nonzero],
        EnergyFitclss.data_binned[EnergyFitclss.index_nonzero],
        yerr=EnergyFitclss.data_errors[EnergyFitclss.index_nonzero],
        fmt="o",
        mfc="None",
        color="tab:green",
        markersize=2,
        lw=0.5,
        label="Data",
    )

    # 绘制模型总结果
    plt.plot(
        EnergyFitclss.bins_center[EnergyFitclss.index_nonzero],
        EnergyFitclss.dict_result["components"]["model_result"],
        color="k",
        label=label_text,
        lw=1.5,
    )

    # 绘制各成分
    components = EnergyFitclss.dict_result["components"]

    plt.fill_between(
        x=EnergyFitclss.bins_center,
        y1=np.zeros_like(components["bkg_conv"]),
        y2=components["bkg_conv"],
        label="Compton Bkg.",
        color="tab:orange",
        alpha=0.4,
    )

    # 全能峰
    # FEP_label = f"Full Energy Peak: {EnergyFitclss.dict_result['center_gauss']['value']:.3f} MeV"
    FEP_label = (
        f"$\\gamma$ Peak: \n"
        f"$\\mu$: {EnergyFitclss.dict_result['center_gauss']['value']:.3f} MeV\n"
        f"$\\sigma/E$: {100*EnergyFitclss.dict_result['sigma_gauss']['value']/EnergyFitclss.dict_result['center_gauss']['value']:.2f} %"
    )
    plt.plot(
        EnergyFitclss.bins_center,
        components["FEP_hist"],
        label=FEP_label,
        color="tab:red",
    )

    plt.plot(
        EnergyFitclss.bins_center,
        components["one_pileup"],
        label="One Pileup",
        color="tab:purple",
        ls="--",
        lw=1.5,
    )
    plt.plot(
        EnergyFitclss.bins_center,
        components["two_pileup"],
        label="Double Pileup",
        color="tab:red",
        ls="--",
        lw=1.5,
    )

    # 最终设置
    plt.legend(fontsize=10, loc="upper right", framealpha=0.7)
    plt.xlabel("E$_{\\mathrm{rec}}$ [MeV]", fontsize=14)
    plt.ylabel(ylabel_show, fontsize=14)
    plt.tick_params(axis="both", which="major", labelsize=12)

    if if_show_ylog:
        plt.semilogy()
        plt.ylim(ylimit, max(components["FEP_hist"]) * 10)
    else:
        plt.ylim(1e-9, None)

    plt.title(f"{title_latex}", fontsize=16)
    plt.grid(True, alpha=0.3)

    if fig_path is not None:
        import os

        os.makedirs(os.path.dirname(fig_path) or "./fig", exist_ok=True)
        plt.savefig(fig_path, dpi=300, bbox_inches="tight")
        print(f"Figure saved to {fig_path}")

    return plt.gca()


def Co60FitterRunner(
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
    xlimit: float = 0.3,
    bkg_path: str = "Co60_Compton_BKG.npz",
):
    """运行Co60拟合器"""
    energy_fitter = Co60Fitter(
        bins_fit=bins_fit,
        data_arr=fitted_data,
        is_hist=is_hist,
        data_err=data_err,
        bkg_path=bkg_path,
        xlimit = xlimit,
    )
    energy_fitter.fit()

    # 保存结果
    if npz_path is not None:
        import os

        os.makedirs(os.path.dirname(npz_path) or "./result", exist_ok=True)
        np.savez(npz_path, **energy_fitter.dict_result)

    return Co60_plot_results(
        energy_fitter,
        title_latex=fig_title,
        fig_path=fig_path,
        ylabel_show=ylabel_show,
        ylimit=ylim,
        if_show_ylog=if_show_ylog,
    )

def Co60_plot_results_with_residuals(
    EnergyFitclss: object,
    title_latex: str,
    fig_path: str,
    ylabel_show: str,
    ylimit=1,
    if_show_ylog=True,
):
    """生成并保存拟合结果图 - 包含残差子图"""
    apply_fitter_plot_style()
    
    # 创建子图
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5, 5), 
                                   gridspec_kw={'height_ratios': [3, 1]}, 
                                   sharex=True)
    total_count = np.sum(EnergyFitclss.dict_result["components"]["bkg_conv"]+ 
                     EnergyFitclss.dict_result["components"]["FEP_hist"]+
                     EnergyFitclss.dict_result["components"]["one_pileup"]+
                     EnergyFitclss.dict_result["components"]["two_pileup"])
    C14_part = np.sum(EnergyFitclss.dict_result["components"]["one_pileup"] + EnergyFitclss.dict_result["components"]["two_pileup"])
    pile_pro = C14_part / total_count * 100
    label_text = f"$\\chi^{{2}}/ndf$: {EnergyFitclss.dict_result['chi2']:.0f}/{EnergyFitclss.dict_result['ndf']:.0f}\nPile-up Pro. {pile_pro:.1f} %"
    ax1.errorbar(
        EnergyFitclss.bins_center[EnergyFitclss.index_nonzero],
        EnergyFitclss.data_binned[EnergyFitclss.index_nonzero],
        yerr=EnergyFitclss.data_errors[EnergyFitclss.index_nonzero],
        fmt="o",
        mfc="None",
        color="tab:green",
        markersize=2,
        lw=0.5,
        label="Data",
    )

    # 绘制模型总结果
    ax1.plot(
        EnergyFitclss.bins_center[EnergyFitclss.index_nonzero],
        EnergyFitclss.dict_result["components"]["model_result"],
        color="k",
        label=label_text,
        lw=1.5,
    )

    # 绘制各成分
    components = EnergyFitclss.dict_result["components"]

    ax1.fill_between(
        x=EnergyFitclss.bins_center,
        y1=np.zeros_like(components["bkg_conv"]),
        y2=components["bkg_conv"],
        label="Compton Bkg.",
        color="tab:orange",
        alpha=0.4,
    )

    # 全能峰
    FEP_label = (
        f"$\\gamma$ Peak: \n"
        f"$\\mu$: {EnergyFitclss.dict_result['center_gauss']['value']:.3f} MeV\n"
        f"$\\sigma/E$: {100*EnergyFitclss.dict_result['sigma_gauss']['value']/EnergyFitclss.dict_result['center_gauss']['value']:.2f} %"
    )
    ax1.plot(
        EnergyFitclss.bins_center,
        components["FEP_hist"],
        label=FEP_label,
        color="tab:red",
    )

    ax1.plot(
        EnergyFitclss.bins_center,
        components["one_pileup"],
        label="One Pileup",
        color="tab:purple",
        ls="--",
        lw=1.5,
    )
    ax1.plot(
        EnergyFitclss.bins_center,
        components["two_pileup"],
        label="Double Pileup",
        color="tab:red",
        ls="--",
        lw=1.5,
    )

    ax1.legend(fontsize=9, loc="upper right", framealpha=0.7)
    ax1.set_ylabel(ylabel_show, fontsize=12)
    ax1.tick_params(axis="both", which="major", labelsize=10)

    if if_show_ylog:
        ax1.semilogy()
        ax1.set_ylim(ylimit, max(components["FEP_hist"]) * 10)
    else:
        ax1.set_ylim(1e-9, None)

    ax1.set_title(f"{title_latex}", fontsize=14)
    ax1.grid(True, alpha=0.3)

    data_points = EnergyFitclss.data_binned[EnergyFitclss.index_nonzero]
    model_points = EnergyFitclss.dict_result["components"]["model_result"]
    errors = EnergyFitclss.data_errors[EnergyFitclss.index_nonzero]
    
    residuals = (data_points - model_points) / errors
    
    ax2.errorbar(
        EnergyFitclss.bins_center[EnergyFitclss.index_nonzero],
        residuals,
        yerr=1,  # 每个点的误差为1（标准化残差）
        fmt="o",
        mfc="None",
        color="k",
        markersize=2,
        lw=0.5,
        label="Residuals"
    )
    ax2.axhline(y=0, color='black', linestyle='-', alpha=0.8, lw=1)
    
    # ax2.axhline(y=3, color='red', linestyle='--', alpha=0.6, lw=0.8, label='$\\pm$3$\\sigma$')
    # ax2.axhline(y=-3, color='red', linestyle='--', alpha=0.6, lw=0.8)
    
    ax2.set_xlabel("E$_{\\mathrm{rec}}$ [MeV]", fontsize=12)
    ax2.set_ylabel("Residuals", fontsize=12)
    ax2.tick_params(axis="both", which="major", labelsize=10)
    # set major interval of y-axis is 2:
    from matplotlib import ticker
    ax2.yaxis.set_major_locator(ticker.MultipleLocator(2))
    ax2.set_ylim(-3, 3)  # 固定y轴范围便于比较
    ax2.grid(True, alpha=0.3)
    # ax2.legend(fontsize=9, loc="upper right", framealpha=0.7)
    
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.01)

    if fig_path is not None:
        import os
        os.makedirs(os.path.dirname(fig_path) or "./fig", exist_ok=True)
        plt.savefig(fig_path, dpi=300, bbox_inches="tight")
        print(f"Figure with residuals saved to {fig_path}")

    return fig
