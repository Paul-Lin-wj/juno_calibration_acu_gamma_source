# -*- coding:utf-8 -*-
# -------------------------------------------------------------------------
# 程序名: MCBased_Fitter.py
# 作者: Shubing Liu <liusb@ihep.ac.cn>
# 创建日期: 2026-01-21
# 更新日期: 2026-03-04
# 程序描述: 
#    基于 JUNO MC 模板的能谱拟合自动化脚本。
#    根据输入的 RUN 号自动查找源类型、读取数据、选择对应的 Fitter 进行拟合。
#    支持源: Cs137, Ge68, Co60, Mn54, K40, AmC(O16)
#    支持通过传入 suffix 后缀区分同一 RUN 的不同处理文件 (如 tail_0d01)。
# 运行方式: 
#    python MCBased_Fitter.py <RUN_NUMBER> [SUFFIX]
#    例如: python MCBased_Fitter.py 12118 tail_0d01
# -------------------------------------------------------------------------

import importlib.util
import os
import sys
from pathlib import Path

# ================= 路径配置 =================
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
sys.path.insert(0, str(_CONFIG_DIR.parent))  # project root
from config.paths import (
    DATA_INPUT_PATH,
    OUTPUT_RES_DIR,
    OUTPUT_FIG_DIR,
    RUN_INFO_CSV as _RUN_INFO_CSV,
)  # noqa: E402

RUN_INFO_CSV = str(_RUN_INFO_CSV)

# ================= 确保本地模块在 path 上 =================
_PROJ_ROOT = Path(__file__).resolve().parent.parent
for _p in ["src", "fitters", "smx_ana"]:
    _path = str(_PROJ_ROOT / _p)
    if _path not in sys.path:
        sys.path.insert(0, _path)

# ================= 环境变量配置 (必须在 import 其他库之前) =================
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

    print(f"[Info] Cache directories set to: {cache_root}")
except Exception as e:
    print(f"[Warning] Failed to set cache directories: {e}")

# =========================================================================

import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from input_loader import infer_sample_label, normalize_event_input
from plot_style import apply_runner_plot_style

# 设置绘图风格
apply_runner_plot_style()


def _bootstrap_smx_ana() -> None:
    if "smx_ana.smx_ana_cpp" in sys.modules:
        return

    # First, ensure the local smx_ana package is on the path
    _smx_ana_local = str(Path(__file__).resolve().parent.parent / "smx_ana")
    if _smx_ana_local not in sys.path:
        sys.path.insert(0, str(Path(_smx_ana_local).parent))

    # First, try to import smx_ana directly from path (Python fallback)
    try:
        import smx_ana
        print(f"[Info] smx_ana loaded from: {smx_ana.__file__}", flush=True)
        return
    except ImportError:
        pass

    candidate_roots = []
    env_root = os.environ.get("SMX_ANA_ROOT", "").strip()
    if env_root:
        candidate_roots.append(Path(env_root).expanduser())

    seen_roots = set()
    for root in candidate_roots:
        if not root:
            continue
        resolved = root.expanduser()
        resolved_str = str(resolved)
        if resolved_str in seen_roots:
            continue
        seen_roots.add(resolved_str)

        package_dir = resolved / "smx_ana"
        if package_dir.is_dir() and resolved_str not in sys.path:
            sys.path.insert(0, resolved_str)

        # Try Python fallback first
        try:
            import smx_ana
            print(f"[Info] smx_ana loaded from: {smx_ana.__file__}", flush=True)
            return
        except ImportError:
            pass

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
        try:
            spec.loader.exec_module(module)
            print(f"[Info] Loaded smx_ana extension from: {extension_path}", flush=True)
            return
        except ImportError as e:
            print(f"[Warning] Failed to load smx_ana extension: {e}, will try Python fallback", flush=True)
            continue
        return


_bootstrap_smx_ana()

# 引入 Fitter 类
try:
    from fitters.Cs137Fitter import Cs137Fitter, Cs137_plot_results
    from fitters.Ge68Fitter import Ge68Fitter, Ge68_plot_results
    from fitters.Co60Fitter import Co60Fitter, Co60_plot_results
    from fitters.Mn54Fitter import Mn54Fitter, Mn54_plot_results
    from fitters.K40Fitter import K40Fitter, K40_plot_results
    from fitters.O16Fitter import O16Fitter, O16_plot_results
    from fitters.Po214C14Fitter import Po214C14Fitter, Po214_plot_results
except ImportError as e:
    missing_name = getattr(e, "name", None) or str(e)
    raise ImportError(
        "Fitter import failed. Ensure the standalone_fitter directory structure is intact. "
        f"Original import error: {missing_name}"
    ) from e

# ================= 配置路径 =================
# (paths imported from config/paths.py above)
BASE_PATH = "/lustrefs/juno26/users/zhaorz/Calib/ReProd26B"

def get_source_type(run_id, run_info_csv=RUN_INFO_CSV):
    """Search for source type in CSV by RUN ID"""
    print(f"[Progress] Looking up source type for run {run_id} ...", flush=True)
    if not os.path.exists(run_info_csv):
        raise FileNotFoundError(f"Run info file not found: {run_info_csv}")
    
    df = pd.read_csv(run_info_csv)
    row = df[df['RUN'] == int(run_id)]
    
    if row.empty:
        raise ValueError(f"Run {run_id} not found in {run_info_csv}")
    
    source = row.iloc[0]['Source']
    print(f"[Info] Run {run_id} identified as Source: {source}")
    return source

def resolve_input_path(run_id=None, source="", suffix="", input_path="", data_input_path=DATA_INPUT_PATH, base_path=BASE_PATH):
    if input_path:
        return str(Path(input_path).expanduser())

    print(f"[Progress] Preparing input path for run {run_id}, source {source}, suffix '{suffix}' ...", flush=True)
    if run_id is None:
        raise RuntimeError("Either input_path or run_id must be provided.")

    suffix_str = f"_{suffix}" if suffix and not suffix.startswith('_') else suffix
    
    if source == "AmC": # O16
        data_path = f"{base_path}/correlate_selection/Results/RUN{run_id}/correlation_result_RUN{run_id}{suffix_str}.npz"
    else:
        # Try ENL naming: Run{N}_SelectionResult.npz
        data_path = f"{data_input_path}/Run{run_id}_SelectionResult.npz"
        if not os.path.exists(data_path):
            # Try original naming: SelectionResult_RUN{N}.npz
            data_path = f"{data_input_path}/SelectionResult_RUN{run_id}{suffix_str}.npz"

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Data file not found: {data_path}")
    return data_path


def load_event_data(input_path, source):
    print(f"[Info] Loading event data from: {input_path}", flush=True)
    event_data = normalize_event_input(input_path, source)
    energy = np.asarray(event_data["energy"], dtype=float)
    finite_energy = energy[np.isfinite(energy)]
    print(f"[Progress] Loaded {finite_energy.shape[0]} finite energy entries", flush=True)
    if finite_energy.shape[0] == 0:
        raise RuntimeError(f"No finite energy entries were found in {input_path}")
    event_data["energy"] = finite_energy
    return event_data


def build_fitter(source, data_arr, enable_c14=True, fix_c14_amplitude=True):
    source = str(source)
    fitter = None
    plot_func = None
    bins_fit = None
    fit_args = {}
    zoom_xlim = (0, 3)

    if source == "Cs137":
        bins_fit = np.arange(0.3, 0.9, 0.004)
        fitter = Cs137Fitter(
            bins_fit=bins_fit,
            data_arr=data_arr,
            is_hist=False,
            enable_c14=enable_c14,
            if_fix_abc=True,
        )
        plot_func = Cs137_plot_results
        zoom_xlim = (0.3, 1.1)
    elif source == "Ge68":
        bins_fit = np.arange(0.3, 2.0, 0.004)
        fitter = Ge68Fitter(
            bins_fit=bins_fit,
            data_arr=data_arr,
            is_hist=False,
            x_limit=0.51,
            enable_c14=enable_c14,
            fix_c14_amplitude=True,
            if_fix_abc=True
        )
        plot_func = Ge68_plot_results
        zoom_xlim = (0.3, 1.6)
        fit_args["ylimit"] = 1e-3
    elif source == "Co60":
        bins_fit = np.arange(1.9, 2.7, 0.004)
        fitter = Co60Fitter(
            bins_fit=bins_fit,
            data_arr=data_arr,
            is_hist=False,
            enable_c14=enable_c14,
            if_fix_abc=True,
        )
        plot_func = Co60_plot_results
        zoom_xlim = (2.0, 2.6)
    elif source == "Mn54":
        bins_fit = np.arange(0.5, 1.0, 0.004)
        fitter = Mn54Fitter(
            bins_fit=bins_fit,
            data_arr=data_arr,
            is_hist=False,
            enable_c14=enable_c14,
            if_fix_abc=True,
        )
        plot_func = Mn54_plot_results
        zoom_xlim = (0.6, 1.0)
    elif source == "K40":
        bins_fit = np.arange(1.0, 1.8, 0.004)
        fitter = K40Fitter(
            bins_fit=bins_fit,
            data_arr=data_arr,
            is_hist=False,
            enable_c14=enable_c14,
            if_fix_abc=True,
        )
        plot_func = K40_plot_results
        zoom_xlim = (1.1, 1.7)
    elif source in {"AmC", "O16"}:
        bins_fit = np.arange(5.6, 6.8, 0.04)
        fitter = O16Fitter(bins_fit=bins_fit, data_arr=data_arr, is_hist=False, if_fix_abc=True)
        plot_func = O16_plot_results
        zoom_xlim = (5.6, 6.7)
        source = "AmC"
    elif source == "Po214":
        bins_fit = np.linspace(0.85, 1.30, 151)
        fitter = Po214C14Fitter(
            bins_fit=bins_fit,
            data_arr=data_arr,
            is_hist=False,
            enable_c14=enable_c14,
            fix_c14_amplitude=fix_c14_amplitude,
            if_fix_abc=True,
        )
        plot_func = Po214_plot_results
        zoom_xlim = (0.85, 1.30)
        fit_args["ylimit"] = 1e-1
    else:
        raise RuntimeError(f"Unsupported source type: {source}")

    return source, fitter, plot_func, bins_fit, fit_args, zoom_xlim


def run_fitter(
    run_id=None,
    suffix="",
    source=None,
    input_path="",
    output_fig_dir=OUTPUT_FIG_DIR,
    output_res_dir=OUTPUT_RES_DIR,
    output_stem="",
    run_info_csv=RUN_INFO_CSV,
    data_input_path=DATA_INPUT_PATH,
    base_path=BASE_PATH,
    enable_c14=True,
    fix_c14_amplitude=True,
):
    label_hint = f"RUN{run_id}" if run_id is not None else input_path
    print(f"[Progress] Starting run_fitter for {label_hint} suffix='{suffix}'", flush=True)
    if source is None:
        if run_id is None:
            raise RuntimeError("run_id is required when source is not provided.")
        source = get_source_type(run_id, run_info_csv=run_info_csv)
    data_path = resolve_input_path(
        run_id=run_id,
        source=source,
        suffix=suffix,
        input_path=input_path,
        data_input_path=data_input_path,
        base_path=base_path,
    )
    event_data = load_event_data(data_path, source)
    data_arr = event_data["energy"]
    
    suffix_str = f"_{suffix}" if suffix and not suffix.startswith('_') else suffix
    source, fitter, plot_func, bins_fit, fit_args, zoom_xlim = build_fitter(
        source,
        data_arr,
        enable_c14=enable_c14,
        fix_c14_amplitude=fix_c14_amplitude,
    )
    sample_label = infer_sample_label(data_path, metadata=event_data.get("metadata"), explicit_label=output_stem, run_id=run_id)
    if suffix_str and not sample_label.endswith(suffix_str):
        sample_label = f"{sample_label}{suffix_str}"

    os.makedirs(output_fig_dir, exist_ok=True)
    os.makedirs(output_res_dir, exist_ok=True)

    print(
        f"[Progress] Configured {source} fitter with {len(bins_fit) - 1} bins "
        f"from {bins_fit[0]:.3f} to {bins_fit[-1]:.3f} MeV",
        flush=True,
    )

    # 执行拟合
    print(f"[Info] Starting fit for {source} (Run {run_id}{suffix_str})...", flush=True)
    fitter.fit()
    print(f"[Progress] Fit finished for {source} (Run {run_id}{suffix_str})", flush=True)
    
    # 保存结果 (NPZ)
    npz_path = f"{output_res_dir}/{sample_label}.npz"
    np.savez(npz_path, **fitter.dict_result)
    print(f"[Output] Fit results saved to: {npz_path}", flush=True)

    # 绘图 1: 全范围图 (PDF)
    fig_path_full = f"{output_fig_dir}/{sample_label}.pdf"
    ylimit_val = fit_args.get("ylimit", 1e-5)
    print(f"[Progress] Rendering full-range figure: {fig_path_full}", flush=True)
    
    plot_func(
        fitter,
        title_latex=f"{sample_label.replace('_', ' ')} $^{{{filter_source_name(source)}}}$ Fitting Result",
        fig_path=fig_path_full,
        ylabel_show="Event Rate [Hz/bin]",
        ylimit=ylimit_val,
        if_show_ylog=True,
    )
    print(f"[Output] Full figure saved to: {fig_path_full}", flush=True)

    plt.close('all')
    print(f"[Progress] {sample_label} finished successfully", flush=True)
    return {
        "result_npz": npz_path,
        "full_figure": fig_path_full,
        "source": source,
        "input_path": data_path,
        "sample_label": sample_label,
    }

def filter_source_name(source):
    """Helper for LaTeX formatting"""
    mapping = {
        "Cs137": "{137}Cs", "Ge68": "{68}Ge", "Co60": "{60}Co",
        "Mn54": "{54}Mn", "K40": "{40}K", "AmC": "{16}O",
        "Po214": "{214}Po",
    }
    return mapping.get(source, source)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JUNO MC-based Energy Spectrum Fitter Runner")
    parser.add_argument("run", type=int, nargs='?', default=None, help="Run number")
    parser.add_argument("suffix", type=str, nargs='?', default="", help="Optional suffix (e.g., tail_0d01)")
    parser.add_argument("--source", default="", help="Explicit source type, e.g. Ge68, Cs137, Co60.")
    parser.add_argument("--input", default="", help="Direct input file (.csv, .csv.gz, or .npz).")
    parser.add_argument("--output-fig-dir", default=OUTPUT_FIG_DIR, help="Directory for fit figures.")
    parser.add_argument("--output-res-dir", default=OUTPUT_RES_DIR, help="Directory for fit result npz files.")
    parser.add_argument("--output-stem", default="", help="Optional output stem used instead of RUN<id>.")
    parser.add_argument("--run-info-csv", default=RUN_INFO_CSV, help="RUN -> source mapping CSV used when --source is omitted.")
    parser.add_argument(
        "--disable-c14",
        action="store_true",
        help="Disable the C14 component by fixing its amplitude to zero.",
    )
    parser.add_argument(
        "--free-c14-amplitude",
        action="store_true",
        help="Let C14_Amp float instead of using the fixed default.",
    )
    
    args = parser.parse_args()
    
    try:
        run_fitter(
            run_id=args.run,
            suffix=args.suffix,
            source=args.source or None,
            input_path=args.input,
            output_fig_dir=args.output_fig_dir,
            output_res_dir=args.output_res_dir,
            output_stem=args.output_stem,
            run_info_csv=args.run_info_csv,
            enable_c14=not args.disable_c14,
            fix_c14_amplitude=not args.free_c14_amplitude,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Fatal Error] {e}")
