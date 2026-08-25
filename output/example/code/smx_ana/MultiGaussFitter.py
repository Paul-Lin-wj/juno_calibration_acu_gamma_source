from iminuit import Minuit
from iminuit.cost import LeastSquares
from smx_ana.DataUtil import GetBinCenter
import numpy as np

def create_multi_gauss_exp_model(n_gauss):
    """创建具有明确参数签名的多高斯+指数模型函数"""
    
    params = []
    for i in range(1, n_gauss + 1):
        params.extend([f'center_gauss{i}=0', f'sigma_gauss{i}=1', f'amp_gauss{i}=0'])
    params.extend(['exp_a=0', 'exp_b=0'])
    
    # 创建函数定义字符串
    func_def = f"""
def MultiGaussExpModel(xe, {', '.join(params)}):
    total = 0.0
"""
    
    # 添加高斯分量
    for i in range(1, n_gauss + 1):
        func_def += f"""
    gauss{i} = amp_gauss{i} * np.exp(-0.5 * ((xe - center_gauss{i}) / sigma_gauss{i}) ** 2)
    total += gauss{i}
"""
    
    # 添加指数本底
    func_def += """
    exp_background = exp_a * np.exp(exp_b * xe)
    return total + exp_background
"""
    
    # 执行函数定义
    local_vars = {'np': np}
    exec(func_def, local_vars)
    
    return local_vars['MultiGaussExpModel']

def MultiGaussExpFitter(
    fitted_data=None,
    bins_pe=None,
    hist_input=None,
    init_params=None,
    bin_limit=5,
    if_hist_input=False,
    if_show_migrad = False
):
    """
    通用多高斯+指数本底拟合器
    """
    
    if init_params is None:
        init_params = {}
    
    # 处理输入数据
    if if_hist_input:
        try:
            bins_center = hist_input[0]
            data_binned = hist_input[1]
            data_err = hist_input[2]
        except Exception as e:
            print(f"Error in hist_input: {e}")
            return None
    else:
        bins_center = GetBinCenter(bins_pe)
        data_binned = np.histogram(np.array(fitted_data), bins=bins_pe)[0]
        data_err = np.sqrt(data_binned)
    
    # 只拟合计数大于阈值的bin
    index_nonzero = data_binned > bin_limit
    
    # 确定高斯峰的数量
    n_gauss = len([k for k in init_params.keys() if k.startswith('center_gauss')])
    
    if n_gauss == 0:
        print("No Gaussian parameters provided!")
        return None
    
    # 为每个高斯峰补充缺失的参数
    for i in range(1, n_gauss + 1):
        center_key = f'center_gauss{i}'
        sigma_key = f'sigma_gauss{i}'
        amp_key = f'amp_gauss{i}'
        
        if center_key not in init_params:
            peak_idx = np.argmax(data_binned)
            init_params[center_key] = bins_center[peak_idx]
        
        if sigma_key not in init_params:
            bin_width = bins_pe[1] - bins_pe[0] if bins_pe is not None else (bins_center[1] - bins_center[0])
            init_params[sigma_key] = bin_width * 2
        
        if amp_key not in init_params:
            center = init_params[center_key]
            window = (bins_center >= center - init_params[sigma_key]) & (bins_center <= center + init_params[sigma_key])
            if np.any(window):
                init_params[amp_key] = np.max(data_binned[window])
            else:
                init_params[amp_key] = np.max(data_binned) * 0.5
    
    # 补充指数本底参数
    if 'exp_a' not in init_params:
        init_params['exp_a'] = np.min(data_binned[data_binned > 0])
    if 'exp_b' not in init_params:
        init_params['exp_b'] = -0.1
    
    # 创建具有正确参数签名的模型函数
    try:
        ModelFunction = create_multi_gauss_exp_model(n_gauss)
    except Exception as e:
        print(f"Error creating model function: {e}")
        return None
    
    # 定义最小二乘代价函数
    least_squares = LeastSquares(
        bins_center[index_nonzero],
        data_binned[index_nonzero],
        data_err[index_nonzero],
        ModelFunction
    )
    
    # 创建Minuit拟合器
    m = Minuit(least_squares, **init_params)
    
    # 设置参数限制
    for i in range(1, n_gauss + 1):
        center = init_params.get(f'center_gauss{i}', 1)
        sigma = init_params.get(f'sigma_gauss{i}', 0.1)
        
        m.limits[f'center_gauss{i}'] = (center * 0.8, center * 1.5)
        m.limits[f'sigma_gauss{i}'] = (sigma * 0.5, sigma * 2.5)
        m.limits[f'amp_gauss{i}'] = (0, None)
    
    m.limits["exp_a"] = (0, None)
    
    # 执行拟合
    try:
        if if_show_migrad:
            display(m.migrad())
        else:
            m.migrad()
        if not m.valid:
            # print("Fit did not converge, trying with simplex...")
            m.simplex()
            if if_show_migrad:
                display(m.migrad())
            else:
                m.migrad()
    except Exception as e:
        print(f"Fitting failed: {e}")
        return None
    
    # 整理结果
    dict_result = {}
    for key in m.parameters:
        dict_result[key] = {"value": float(m.values[key]), "error": float(m.errors[key])}
    
    # 计算各分量
    x_fit = bins_center[index_nonzero]
    
    # 计算总拟合曲线
    model_args = {key: m.values[key] for key in m.parameters}
    total_fit = ModelFunction(x_fit, **model_args)
    
    # 计算各个高斯分量
    gauss_components = {}
    for i in range(1, n_gauss + 1):
        center = m.values[f'center_gauss{i}']
        sigma = m.values[f'sigma_gauss{i}']
        amp = m.values[f'amp_gauss{i}']
        gauss_components[f'gauss{i}Y'] = amp * np.exp(-0.5 * ((x_fit - center) / sigma) ** 2)
    
    # 计算指数本底
    exp_fit = m.values['exp_a'] * np.exp(m.values['exp_b'] * x_fit)
    
    # 计算拟合优度
    residuals = data_binned[index_nonzero] - total_fit
    chi2 = np.sum((residuals / data_err[index_nonzero]) ** 2)
    ndf = len(data_binned[index_nonzero]) - len(m.parameters)
    
    # 计算各高斯峰的面积
    gauss_nums = {}
    for i in range(1, n_gauss + 1):
        gauss_nums[f'gauss{i}_num'] = np.sum(gauss_components[f'gauss{i}Y'])
    
    # 返回完整结果
    dict_result["result"] = {"chi2": chi2, "ndf": ndf}
    dict_result["x"] = x_fit
    dict_result["fitY"] = total_fit
    dict_result["expY"] = exp_fit
    dict_result["y"] = data_binned[index_nonzero]
    dict_result["yerr"] = data_err[index_nonzero]
    
    # 添加各个高斯分量
    for key, value in gauss_components.items():
        dict_result[key] = value
    
    # 添加高斯峰面积
    for key, value in gauss_nums.items():
        dict_result[key] = value
    
    # 添加高斯峰数量信息
    dict_result["n_gauss"] = n_gauss
    
    return dict_result

def PlotMultiGaussFitResult(
    dict_result_info,
    title="Multi Gauss + Exp Fit Result",
    xlabel="p.e.", 
    ylabel="Event Number",
    save_path=None,
    if_ylog=False,
    legend_posi="right"
):
    """绘制多高斯+指数本底拟合结果（包含残差图）"""
    import matplotlib.pyplot as plt
    
    n_gauss = dict_result_info.get("n_gauss", 0)
    colors = plt.cm.tab10(np.linspace(0, 1, n_gauss))
    
    # 创建包含两个子图的图形
    fig, (ax1, ax2) = plt.subplots(
        2, 1, 
        figsize=(6, 4), 
        dpi=300, 
        sharex=True,
        gridspec_kw={'height_ratios': [3, 1], 'hspace': 0.1}
    )
    
    # 上子图：拟合结果
    ax1.errorbar(
        dict_result_info["x"],
        dict_result_info["y"], 
        yerr=dict_result_info["yerr"],
        fmt="o", markersize=3, color="k", 
        label=f"Data (Total: {np.sum(dict_result_info['y']):.0f} events)",
        alpha=0.7
    )
    
    x_plot = dict_result_info["x"]
    ax1.plot(x_plot, dict_result_info["fitY"], "-", color="r", linewidth=2, 
             label=f"$\\chi^2$/ndf = {dict_result_info['result']['chi2']:.1f}/{dict_result_info['result']['ndf']}")
    
    # 绘制各个高斯分量
    for i in range(1, n_gauss + 1):
        resolution = (dict_result_info[f"sigma_gauss{i}"]["value"] / 
                    dict_result_info[f"center_gauss{i}"]["value"] * 100)
        ax1.plot(x_plot, dict_result_info[f"gauss{i}Y"], "--", linewidth=1.5, color=colors[i-1],
                 label=f"Gauss{i} ($\\mu$={dict_result_info[f'center_gauss{i}']['value']:.4f}, "
                       f"E$_{{res}}$ = {resolution:.2f}%)")
    
    ax1.plot(x_plot, dict_result_info["expY"], "--", color="gray", linewidth=1.5, label="Exp Background")



    ax1.legend(loc=f'upper {legend_posi}', fontsize=8, framealpha=0.4)
    ax1.set_ylabel(ylabel)
    ax1.set_title(title)
    
    if if_ylog:
        ax1.set_yscale("log")
    else:
        ax1.set_ylim(0, None)
    
    # 下子图：残差分布
    residuals = dict_result_info["y"] - dict_result_info["fitY"]
    residuals_norm = residuals / dict_result_info["yerr"]
    
    # ax2.axhline(y=0, color='r', linestyle='--', linewidth=1, alpha=0.8)
    ax2.errorbar(dict_result_info["x"], residuals_norm, fmt='o', markersize=2, color='k', alpha=0.7)
    ax2.axhspan(-1, 1, color = "tab:red", alpha = 0.2)
    ax2.axhspan(-2, -1, color = "tab:red", alpha = 0.1)
    ax2.axhspan(1, 2, color = "tab:red", alpha = 0.1)
    ax2.set_ylabel("Residual/$\\sigma$")
    ax2.set_xlabel(xlabel)
    ax2.grid(True, alpha=0.3)
    
    # y_max = max(np.abs(residuals_norm)) * 1.2
    # ax2.set_ylim(-y_max, y_max)
    
    if save_path:
        plt.savefig(save_path, bbox_inches='tight', dpi=300)
        plt.close()
    return fig