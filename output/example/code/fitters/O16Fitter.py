import numpy as np
import matplotlib.pyplot as plt
from matplotlib import pyplot as plt
import smx_ana
from iminuit import Minuit
from iminuit.cost import LeastSquares
from plot_style import apply_fitter_plot_style
from .Compat import GetBinCenter
from .FitterUtils import *
from smx_ana.smx_ana_cpp import sum_distributions_fast_cpp

apply_fitter_plot_style()

# O16专用的bins设置
bins_proton_pileup = np.arange(0, 0.14, 0.001)  # 质子反冲能区
bins_proton_pileup_center = GetBinCenter(bins_proton_pileup)

def O16_calculate_components(dict_result, bins_center, dict_bkg, bins_fit):
    """计算O16能谱的各成分 - 修正版本"""
    # 能量分辨率模型
    energy_sigma = EnergyResolutionModel(
        bins_center,
        dict_result["a"]["value"],
        dict_result["b"]["value"],
        dict_result["c"]["value"],
    )

    # Component 1: O16基态成分（卷积能量分辨率）
    O16_ground_part = np.histogram(
        dict_bkg["GND"] * dict_result["E_scale_ground"]["value"],
        bins=bins_fit,
        weights=np.ones_like(dict_bkg["GND"]) / len(dict_bkg["GND"]),
    )[0]

    # 对基态成分进行能量分辨率卷积
    O16_ground_conv = smx_ana.convolve(O16_ground_part, bins_fit, energy_sigma).copy()
    
    # 添加基态幅度
    O16_ground_final = dict_result["amp_ground"]["value"] * O16_ground_conv

    # Component 2: O16第二激发态（6.13 MeV高斯与质子反冲卷积）
    # 2.1 6.13 MeV高斯峰
    gauss_6_13 = FEP_part(
        bins_center=bins_center,
        amp_gauss=dict_result["amp_gauss_6_13"]["value"],
        center_gauss=dict_result["center_gauss_6_13"]["value"],
        sigma_gauss=dict_result["sigma_gauss_6_13"]["value"],
    )

    # 2.2 质子反冲能谱（不进行分辨率卷积）
    proton_recoil_part = np.histogram(
        dict_bkg["pileup"] * dict_result["E_scale_proton"]["value"],
        bins=bins_proton_pileup,
        weights=np.ones_like(dict_bkg["pileup"]) / len(dict_bkg["pileup"]),
    )[0]

    # 2.3 高斯与质子反冲能谱卷积（只需要卷积一次）
    z, sum_pdf = sum_distributions_fast_cpp(
        bins_center, gauss_6_13, bins_proton_pileup_center, proton_recoil_part
    )
    gauss_proton_conv = np.histogram(z, bins=bins_fit, weights=sum_pdf)[0]
    space_ = np.sum(gauss_proton_conv)
    gauss_proton_conv = gauss_proton_conv / space_ if space_ > 0 else gauss_proton_conv

    # 总模型：两个成分直接相加
    model_result = O16_ground_final + gauss_proton_conv

    return {
        "energy_sigma": energy_sigma,
        "bins_center": bins_center,
        "bins_proton_center": bins_proton_pileup_center,
        "O16_ground_conv": O16_ground_conv,
        "O16_ground_final": O16_ground_final,
        "proton_recoil_part": proton_recoil_part,
        "gauss_6_13": gauss_6_13,
        "gauss_proton_conv": gauss_proton_conv,
        "model_result": model_result,
        "E_scale_ground": dict_result["E_scale_ground"]["value"],
        "E_scale_proton": dict_result["E_scale_proton"]["value"],
        "amp_ground": dict_result["amp_ground"]["value"],
    }


class O16Fitter:
    def __init__(
        self,
        bins_fit: np.ndarray,
        data_arr: np.ndarray,
        is_hist: bool,
        data_err: np.ndarray = None,
        bkg_path: str = f"{PROJECT_ROOT}/O16prompt_decomposition.npz",
        x_limit: float = 5.5,
        if_fix_abc: bool = True,
        if_fix_E_scale: bool = False,
    ):
        self.MC_Qedep_Center_ground = 5.918  # O16基态γ峰能量
        self.x_limit = x_limit
        self.if_fix_abc = if_fix_abc
        self.if_fix_E_scale = if_fix_E_scale
        self.bkg_data = self._load_background_data(bkg_path)
        self.bins_fit = bins_fit
        self.bins_center = GetBinCenter(bins_fit)

        # 存储质子反冲相关的bins信息
        self.bins_proton = bins_proton_pileup
        self.bins_proton_center = bins_proton_pileup_center

        self.index_nonzero = None
        self.data_binned = None
        self.data_errors = None
        self._initialize_fit_data(data_arr, is_hist, data_err)

        self.minuit_core = None
        self._setup_minuit()

        self.dict_result = None

    def __call__(
        self,
        x,
        amp_gauss_6_13,      # 6.13 MeV高斯幅度
        center_gauss_6_13,    # 6.13 MeV高斯中心
        sigma_gauss_6_13,     # 6.13 MeV高斯宽度
        amp_ground,           # 基态成分幅度
        E_scale_ground,       # 基态能量刻度
        E_scale_proton,       # 质子反冲能量刻度
        a, b, c,              # 能量分辨率参数
    ):
        """O16拟合函数 - 修正版本：两个独立成分"""
        # Component 1: O16基态成分（卷积能量分辨率）
        O16_ground_part = np.histogram(
            self.bkg_data["GND"] * E_scale_ground,
            bins=self.bins_fit,
            weights=np.ones_like(self.bkg_data["GND"]) / len(self.bkg_data["GND"]),
        )[0]

        # 能量分辨率模型
        energy_res = EnergyResolutionModel(self.bins_center, a, b, c)

        # 对基态成分进行能量分辨率卷积
        O16_ground_conv = smx_ana.convolve(O16_ground_part, self.bins_fit, energy_res).copy()
        
        # 添加基态幅度
        component1 = amp_ground * O16_ground_conv

        # Component 2: O16第二激发态（高斯与质子反冲卷积）
        # 2.1 6.13 MeV高斯峰
        gauss_6_13 = FEP_part(
            self.bins_center, amp_gauss_6_13, center_gauss_6_13, sigma_gauss_6_13
        )

        # 2.2 质子反冲能谱（不进行分辨率卷积）
        proton_recoil_part = np.histogram(
            self.bkg_data["pileup"] * E_scale_proton,
            bins=self.bins_proton,
            weights=np.ones_like(self.bkg_data["pileup"]) / len(self.bkg_data["pileup"]),
        )[0]

        # 2.3 高斯与质子反冲能谱卷积（只需要卷积一次）
        z, sum_pdf = sum_distributions_fast_cpp(
            self.bins_center, gauss_6_13, self.bins_proton_center, proton_recoil_part
        )
        component2 = np.histogram(z, bins=self.bins_fit, weights=sum_pdf)[0]
        space_ = np.sum(component2)
        component2 = component2 / space_ if space_ > 0 else component2

        # 总模型：两个成分直接相加
        result = component1 + component2
        
        return result[self.index_nonzero]

    def _load_background_data(self, path: str) -> dict:
        """加载O16背景数据"""
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
        print(f"O16 Data initialized, total count in fit range: {self.total_count}")
        self._setup_minuit()

    def _setup_minuit(self):
        """配置Minuit拟合器 - 修正版本"""
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
            amp_gauss_6_13=np.max(self.data_binned[self.index_nonzero]) * 0.5,  # 高斯幅度
            center_gauss_6_13=max_center,  # 6.13 MeV固定中心
            sigma_gauss_6_13=max_center * 0.015,  # 3%能量分辨率
            amp_ground=np.max(self.data_binned[self.index_nonzero]) * 0.5,  # 基态幅度
            E_scale_ground=max_center / self.MC_Qedep_Center_ground,
            E_scale_proton=1.0,
            a=3.309, b=1.28, c=0,
        )

        # 参数限制
        m.limits["amp_gauss_6_13"] = (0, None)
        m.limits["amp_ground"] = (0, None)
        
        m.limits["E_scale_ground"] = (0.5, 1.5)
        m.fixed["E_scale_ground"] = self.if_fix_E_scale
        
        m.limits["E_scale_proton"] = (0.5, 2.0)
        m.fixed["E_scale_proton"] = self.if_fix_E_scale

        m.limits["center_gauss_6_13"] = (5.8, 6.4)  # 6.13 MeV附近范围
        m.limits["sigma_gauss_6_13"] = (0.1, 0.5)   # 合理的宽度范围

        m.limits["a"] = (0, 4)
        m.limits["b"] = (0, 1)
        m.limits["c"] = (0, 2)
        if self.if_fix_abc:
            m.fixed["a"] = True
            m.fixed["b"] = True
            m.fixed["c"] = True

        self.minuit_core = m

    def _organize_component(self):
        """组织拟合成分"""
        model_result = self(
            self.bins_center,
            self.dict_result["amp_gauss_6_13"]["value"],
            self.dict_result["center_gauss_6_13"]["value"],
            self.dict_result["sigma_gauss_6_13"]["value"],
            self.dict_result["amp_ground"]["value"],
            self.dict_result["E_scale_ground"]["value"],
            self.dict_result["E_scale_proton"]["value"],
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
        ndf = len(self.data_binned[self.index_nonzero]) - len(self.minuit_core.parameters)
        self.dict_result["chi2"] = chi2
        self.dict_result["ndf"] = ndf

        # 计算所有成分
        components = O16_calculate_components(
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


def O16_plot_results(
    EnergyFitclss: object,
    title_latex: str,
    fig_path: str,
    ylabel_show: str,
    ylimit=1,
    if_show_ylog=True,
):
    """生成O16拟合结果图 - 修正版本"""
    apply_fitter_plot_style()
    plt.figure(figsize=(6, 4))
    
    components = EnergyFitclss.dict_result["components"]
    
    # 显示参数信息
    param_info = (f"E-scale(ground): {components['E_scale_ground']:.3f}\n"
                  f"E-scale(proton): {components['E_scale_proton']:.3f}\n"
                  f"Amp(ground): {components['amp_ground']:.3f}")
    
    label_text = (f"$\\chi^{{2}}/ndf$: {EnergyFitclss.dict_result['chi2']:.0f}/"
                 f"{EnergyFitclss.dict_result['ndf']:.0f}\n{param_info}")

    # 绘制数据和模型
    plt.errorbar(
        EnergyFitclss.bins_center[EnergyFitclss.index_nonzero],
        EnergyFitclss.data_binned[EnergyFitclss.index_nonzero],
        yerr=EnergyFitclss.data_errors[EnergyFitclss.index_nonzero],
        fmt="o",
        mfc="None",
        color="tab:green",
        markersize=2,
        lw=0.5,
        label="O16 Data",
    )

    plt.plot(
        EnergyFitclss.bins_center[EnergyFitclss.index_nonzero],
        components["model_result"],
        color="k",
        label=label_text,
        lw=1.5,
    )

    # Component 1: O16基态成分
    plt.plot(
        EnergyFitclss.bins_center,
        components["O16_ground_final"],
        label="O16 Ground State",
        color="tab:blue",
        lw=1.5,
        alpha=0.8,
    )

    # Component 2: 6.13 MeV高斯与质子反冲卷积
    plt.plot(
        EnergyFitclss.bins_center,
        components["gauss_proton_conv"],
        label="6.13 MeV γ + Proton Recoil",
        color="tab:red",
        lw=1.5,
        alpha=0.8,
    )

    # 子成分：6.13 MeV高斯（单独显示）
    plt.plot(
        EnergyFitclss.bins_center,
        components["gauss_6_13"],
        label="6.13 MeV γ (pure)",
        color="tab:red",
        linestyle=":",
        lw=1.0,
        alpha=0.6,
    )

    # 最终设置
    plt.legend(fontsize=8, loc="upper right", framealpha=0.7)
    plt.xlabel("E$_{\\mathrm{rec}}$ [MeV]", fontsize=14)
    plt.ylabel(ylabel_show, fontsize=14)
    plt.tick_params(axis="both", which="major", labelsize=12)

    if if_show_ylog:
        plt.semilogy()
        plt.ylim(ylimit, max(components["model_result"]) * 10)
    else:
        plt.ylim(1e-9, None)

    plt.title(f"{title_latex}", fontsize=16)
    plt.grid(True, alpha=0.3)

    if fig_path is not None:
        import os
        os.makedirs(os.path.dirname(fig_path) or "./fig", exist_ok=True)
        plt.savefig(fig_path, dpi=300, bbox_inches="tight")
        print(f"O16 Figure saved to {fig_path}")

    return plt.gca()
