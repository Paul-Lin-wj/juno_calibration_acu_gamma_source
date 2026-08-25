# JUNO ACU Gamma Source — Standalone Energy Spectrum Fitter

JUNO（江门中微子实验）ACU 伽马源刻度分析的能量谱拟合工具。基于 JUNO MC 模板，使用最小二乘（χ²）拟合，支持多种刻度源的能量谱分解与峰位提取。

## 项目结构

```
standalone_fitter/
├── config/
│   ├── __init__.py
│   └── paths.py              # ★ 集中路径配置，唯一需要编辑的文件
│
├── src/
│   ├── FastGe68Fitter.py      # 缓存优化的 Fast 版 Ge68 拟合器
│   ├── FastSourceFitter.py    # 通用 Fast 版拟合器（Cs137 / Mn54 / Co60 / K40）
│   ├── MCBased_Fitter.py      # 经典版拟合入口（回退选择）
│   ├── input_loader.py         # 输入数据加载 (.npz / .csv)
│   ├── plot_style.py           # 绘图样式配置
│   ├── plot_fit_summary.py     # 汇总趋势图工具
│   └── convert_root_to_npz.py  # ROOT → NPZ 转换
│   ├── plot_style.py           # 绘图样式配置
│   ├── plot_fit_summary.py     # 汇总趋势图工具
│   └── convert_root_to_npz.py  # ROOT → NPZ 转换
│
├── fitters/                   # 各刻度源的拟合器实现
│   ├── __init__.py
│   ├── Compat.py              # 兼容工具（GetBinCenter）
│   ├── FitterUtils.py         # 公共工具（能量分辨率模型、C14 pileup、卷积）
│   ├── Ge68Fitter.py          # Ge68 经典拟合器
│   ├── Cs137Fitter.py         # Cs137 拟合器
│   ├── Co60Fitter.py          # Co60 拟合器
│   ├── Mn54Fitter.py          # Mn54 拟合器
│   ├── K40Fitter.py           # K40 拟合器
│   ├── O16Fitter.py           # O16 / AmC 拟合器
│   ├── Po214C14Fitter.py      # Po214 拟合器
│   └── *.npz                  # MC 本底模板（Ge68 / Cs137 / Co60 / Mn54 / K40 / O16）
│
├── smx_ana/                   # smx_ana 纯 Python 实现（无 C++ 扩展依赖）
│   ├── __init__.py
│   ├── smx_ana_cpp.py         # Python fallback（convolve + sum_distributions_fast_cpp）
│   ├── ResponseTool.py
│   └── MultiGaussFitter.py
│
├── pipeline/
│   ├── __init__.py
│   ├── run_fit_all.py         # ★ 主流程：跑所有源 → 收集结果 → 画 ENL 风格图
│   └── compare_fast_vs_classic.py  # Fast 版与经典版对比测试
│
├── tests/
│   └── smoke_test.sh            # 环境验证脚本（15 项检查）
├── setup_env.sh                 # 创建 Python 虚拟环境并安装依赖
├── run_pipeline.sh              # 一键运行
├── CalibRUN.csv                 # Run → 源类型 / 位置 映射表
└── .gitignore
```

## 环境要求

- **Python ≥ 3.10**（推荐 3.12）
- numpy, scipy, matplotlib, iminuit（`setup_env.sh` 自动安装）

无需 ROOT、cppyy、C++ 扩展——`smx_ana` 已提供纯 Python fallback。

## 快速开始

### 1. 配置数据路径

编辑 `config/paths.py`，修改 `DATA_INPUT_PATH` 指向你的数据目录：

```python
DATA_INPUT_PATH = "/你的数据目录"  # 应包含 Run{N}_SelectionResult.npz 文件
```

数据文件预期包含 `calib_omilrec_energy` 字段（OMILREC 重建能量）。

### 2. 一键运行

```bash
bash run_pipeline.sh
```

脚本会自动：
- 创建 `.venv` 虚拟环境并安装依赖
- 遍历 `config/paths.py` 中配置的源，逐个拟合
- Ge68 使用 Fast 版（缓存 MC 模板卷积，~5 秒/run）
- 其余源使用经典版（~15-90 秒/run）
- 汇总结果并绘制 ENL 风格的分辨率 vs E_rec 图

### 3. 输出

```
output/{YYYYMMDD_HHMMSS}/
├── results/
│   ├── RUN9541_Ge68.npz       # 拟合结果（含参数、χ²、成分分解）
│   ├── RUN9600_Cs137.npz
│   └── ...
├── figures/
│   ├── RUN9541_Ge68.pdf        # 单源拟合图（LogY）
│   ├── RUN9600_Cs137.pdf       # 单源拟合图（全范围）
│   └── ...
├── code/                      # ★ 完整代码快照 + code/sha256.json
├── enl_style_resolution.pdf   # ★ ENL 风格：分辨率 vs E_rec 汇总图
└── enl_style_resolution.png
```

每次运行独立时间戳目录，不会覆盖之前的输出。

**结束审计（自动）**：每次运行结束时自动——① 拷贝完整代码树到 `code/`（附 sha256 指纹）；② 校验 code 快照与工作树逐字节一致、全部关键输出（结果 npz/拟合图/汇总图/日志）存在；③ 结果写入 `run_log.json -> audit`（run_log.md 含 Audit 段）。失败时：脚本模式 `exit 3`，agent 模式打印 `[AUDIT] WARNING`。

## 配置说明

### 修改拟合的源

编辑 `config/paths.py` 中的 `SOURCES` 列表：

```python
SOURCES = [
    ("Ge68",  9541, 0.8845, "fast"),     # 用 Fast 版拟合
    ("Cs137", 9600, 0.662,  "fast"),     # 用 Fast 版拟合
    ("Mn54",  9624, 0.835,  "fast"),
    ("Co60",  9591, 2.506,  "fast"),
    ("K40",   9632, 1.461,  "fast"),
]
# 格式: (源名, Run号, 真能量(MeV), 拟合器类型)
```

`fitter_type` 支持：
- `"fast"` — **推荐**，使用缓存优化的 Fast 版拟合器，所有源都可用
- `"classic"` — 使用经典版拟合器，保留作为回退选择

### 修改 Run→源映射

`CalibRUN.csv` 格式：
```
RUN,Date,X[m],Y[m],Z[m],Source,R[m]
9541,2025-08-24,0.0,0.0,0.0,Ge68,0.0
```

## 拟合器说明

### FastFitter 系列（缓存优化版，推荐）

所有源都支持 Fast 版，实现模板缓存优化：

| 源 | Fast 版 | 实现文件 | 单 run 耗时 |
|----|---------|---------|:-----------:|
| Ge68 | ✅ | `src/FastGe68Fitter.py` | **~4-6 秒** |
| Cs137 | ✅ | `src/FastSourceFitter.py` | **~0.2-0.6 秒** |
| Mn54 | ✅ | `src/FastSourceFitter.py` | **~0.2-0.5 秒** |
| Co60 | ✅ | `src/FastSourceFitter.py` | **~0.3-0.7 秒** |
| K40 | ✅ | `src/FastSourceFitter.py` | **~0.2-0.4 秒** |

**核心原理**：初始化时一次性缓存 MC 模板的 histogram 和卷积结果，Minuit 迭代时无需重复计算。C14 pileup 使用 FFT 加速。

**加速效果**：
- Ge68: ~50-100x（vs 经典版 5-15 分钟）
- Cs137/Mn54/Co60/K40: ~45-100x（vs 经典版 7-27 秒）

### 经典版（MCBased_Fitter，回退选择）

`fitters/` 目录下的 `Cs137Fitter.py`、`Co60Fitter.py`、`Mn54Fitter.py`、`K40Fitter.py` 保留作为回退。

- 每次 Minuit 迭代重新 histogram + convolve
- 使用方式：将 `config/paths.py` 中 `fitter_type` 改为 `"classic"`
- 用于交叉验证或排查 Fast 版的潜在问题

## 关键技术参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| bins_fit | 0.3–2.0 MeV, step 0.004 | Ge68 拟合范围与分箱 |
| x_limit | 0.51 (Fast) / 0.6 (classic) | 参与拟合的最小能量 |
| a/b/c | 3.309 / 1.28 / 0.0 (fix) | 能量分辨率模型参数 |
| C14_Amp | 0.047 (fix) | ¹⁴C 本底振幅 |
| E_scale | 峰位/0.8845 (fix) | 能量刻度因子 |
| C14 pileup | FFT (Fast) / Python (classic) | 卷积算法 |

## 输入数据格式

### NPZ 文件（主要格式）

单 run 的 selection 数据，路径 `{DATA_INPUT_PATH}/Run{run_id}_SelectionResult.npz`，包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `calib_omilrec_energy` | float32/64 | 重建能量 [MeV] |
| `calib_omilrec_x/y/z` | float32/64 | 重建顶点位置 [mm]（可选） |

### CSV 文件（备选格式）

包含 `rec_energy` 列，可选 `x_mm / y_mm / z_mm` 列。

## 遗留问题

- 数据需经过 Finalcorrection 修正（含绝对能标），否则峰位会有系统性偏移
- `FastGe68Fitter` 和 `FastSourceFitter` 只支持 C14 pileup 启用模式（enable_c14=True），如需禁用 C14 请使用经典版