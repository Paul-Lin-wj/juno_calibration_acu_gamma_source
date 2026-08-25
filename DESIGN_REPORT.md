# standalone_fitter 项目设计详细汇报

> **项目路径**：`/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_fitter`
> **Git 远端**：`git@github.com:Paul-Lin-wj/juno_calibration_acu_gamma_source.git`
> **当前分支**：`main` @ commit `ff0a201`
> **汇报日期**：2026-08-23

---

## 一、项目总览

**功能**：JUNO（江门中微子实验）ACU 伽马源能谱拟合流水线——读取刻度源选择数据（NPZ），用 MC 模板 + 最小二乘拟合提取峰位 μ、分辨率 σ/E，输出结果与审计日志。

---

## 二、代码来源目录映射

本项目是对两个上游目录的**独立化重构**，全部代码收敛到一个自包含目录：

| 本项目位置 | 代码来源 | 原始出处 | 改动 |
|-----------|---------|---------|------|
| `src/FastGe68Fitter.py` | `SourceEnergyFitter/FastGe68Fitter.py` | `/datafs/users/wujxy/agent-sci/ENL_agent/sourceenergyfitter/` | 路径改为相对引用、bootstrap 本地化 |
| `src/FastSourceFitter.py` | **新增**（本会话开发） | 基于 FastGe68Fitter 模式泛化 | Cs137/Mn54/Co60/K40 通用 Fast 版 |
| `src/MCBased_Fitter.py` | `SourceEnergyFitter/MCBased_Fitter.py` | 同上 | 路径从 config 导入、fitters 相对引用 |
| `src/input_loader.py` | `SourceEnergyFitter/input_loader.py` | 同上 | 未改动 |
| `src/plot_fit_summary.py` | `SourceEnergyFitter/plot_fit_summary.py` | 同上 | 默认路径改为项目根 |
| `src/convert_root_to_npz.py` | `SourceEnergyFitter/convert_root_to_npz.py` | 同上 | 未改动 |
| `src/run_logger.py` | **新增**（本会话开发） | 审计日志系统 v2 | 独立实现 |
| `fitters/`（8 个 .py） | `SourceEnergyFitter/JUNOMCBasedFitter/` | 同上 | 经典版保留作回退 |
| `fitters/*.npz`（6 个 MC 模板） | `SourceEnergyFitter/JUNOMCBasedFitter/` | 同上 | 未改动 |
| `smx_ana/` | `ENL_agent/.../local_pkgs/smx_ana/` | `juno_calibration_acu_gamma_source/local_pkgs/` | 只保留 Python fallback，剔除 C++ `.so` |
| `CalibRUN.csv` | `ReProd26B/calib_run_info/CalibRUN_from_file.csv` | `/lustrefs/juno26/users/zhaorz/...` | Run→源/位置/日期映射 |
| `skills/`（10 份） | **新增**（本会话开发） | 基于评审迭代 | 操作手册 + 日志规范 |
| `tests/smoke_test.sh` | **新增** | 17 项环境自检 | — |
| `pipeline/run_fit_all.py` | **新增** | 主流程编排 | — |
| `pipeline/compare_fast_vs_classic.py` | **新增** | Fast vs 经典验证 | — |

**依赖策略**：第三方依赖固定于 `requirements.txt`（numpy 1.26.4/scipy 1.13.1/matplotlib 3.9.0/iminuit 2.30.1/pandas 2.2.2，实际环境为更高版本）；自建包 `smx_ana` 纯 Python 化，无 ROOT/cppyy/C++ 依赖，保证可移植。

---

## 三、流水线设计

### 3.1 数据流

```
输入：/lustrefs/.../singles_selection/Results_fromFinalcorrection/npz/Run{N}_SelectionResult.npz
  （含 calib_omilrec_energy 重建能量，已施加 Finalcorrection 修正）
        │
        ▼
config/paths.py 中 SOURCES 列表（源名, run号, E_true, fitter类型）
        │
        ▼
┌─────────────────────────────────────────────────┐
│  pipeline/run_fit_all.py（主流程，context manager）│
│  1. RunLogger 初始化（schema 2.0 + run_id + UUID）│
│  2. 记录启动命令 + ConsoleTee 捕获 stdout/stderr │
│  3. save_config_snapshot() 配置内容快照           │
│  4. 逐源拟合：                                   │
│     Ge68  → src/FastGe68Fitter（缓存模板卷积）    │
│     其他  → src/FastSourceFitter（通用缓存版）    │
│     回退  → src/MCBased_Fitter（经典版）          │
│  5. 每源 add_source_record()（状态/SHA-256/参数） │
│  6. 画 ENL 风格汇总图（σ/E vs E_rec）             │
│  7. set_exit_code + finalize（try/finally 保证）  │
└─────────────────────────────────────────────────┘
        │
        ▼
output/{YYYYMMDD_HHMMSS}/
├── run_log.json / run_log.md      ← 审计日志（双格式，含 Audit 段）
├── config_snapshot.json            ← 配置内容快照
├── console.log                     ← 终端输出捕获
├── traceback.log                   ← 异常时生成
├── code/ + code/sha256.json        ← ★ 完整代码快照（运行代码逐字节档案）
├── enl_style_resolution.png/.pdf   ← 汇总图
├── results/RUN{run}_{源}.npz       ← 拟合结果
└── figures/RUN{run}_{源}.pdf       ← 单源拟合图
```

> **结束审计（2026-08-25 新增）**：运行结束自动执行 `snapshot_code_full()`
> （完整代码树 → `code/`，附 sha256）+ `run_audit()`（code 快照与工作树逐
> 字节一致、关键输出齐全，结果写入 `run_log.json -> audit`）；finalize 后
> 再自检 4 件套日志文件。失败时脚本模式 `exit 3`、agent 模式 `[AUDIT] WARNING`。

### 3.2 拟合器架构（两层）

| 层 | 实现 | 原理 | 性能 |
|----|------|------|------|
| **Fast 版**（默认） | `FastGe68Fitter` + `FastSourceFitter` | 初始化时缓存 MC 模板 histogram + 卷积，Minuit 迭代只做加权+峰+pileup；C14 pileup 用 FFT | Ge68 ~5s；Cs137/Mn54/Co60/K40 ~0.2-0.8s（**45-103x 加速**） |
| **经典版**（回退） | `fitters/` 下 8 个 Fitter | 每次迭代重新 histogram + convolve，Python 插值积分 | ~7-27s |

**模型结构**：Compton MC 模板（卷积能量分辨率 σ(E)=√((a/√E)²+b²+(c/E)²)·E）+ FEP 高斯峰 + C14 单/双 pileup，14 参数（9 自由 + 5 固定：E_scale/a/b/c/C14_Amp）。

### 3.3 运行入口

- `bash run_pipeline.sh` — 一键运行（自动建 venv + 装依赖 + 主流程）
- `bash setup_env.sh` — 仅建环境
- `bash tests/smoke_test.sh` — 17 项环境/模块/配置自检
- `python pipeline/run_fit_all.py --launched-by agent --agent-name ...` — agent 驱动（写入 agent_notes）
- 多批处理 = 多次运行主流程 + `plot_fit_summary.py --results-dir` 多目录对比

---

## 四、Skill 内容清单（10 份）

| Skill | 内容 | 读者 |
|-------|------|------|
| `01_project_overview` | 项目定位、支持源、架构、适用/不适用场景 | 新用户入口 |
| `02_setup_environment` | venv 创建、依赖安装、环境验证、排错 | 冷启动 |
| `03_configuration` | 路径/源/映射配置、"只改一个文件"的边界说明 | 配置者 |
| `04_running_pipeline` | 运行步骤、输出解读、性能基准、多批处理引导 | 运行者 |
| `05_fitter_internals` | 模型数学、参数表、缓存策略、结果判读 | 分析者 |
| `06_data_preparation` | NPZ/CSV 格式、ROOT→NPZ 转换、数据校验 | 数据准备 |
| `07_troubleshooting` | 拟合/环境/数据/性能/路径 5 类问题 | 排障者 |
| `08_zscan_analysis` | Z-scan 批量拟合、汇总绘图、多版本对比 | 位置扫描 |
| `09_interpreting_results` | μ/σ/χ²/ndf 判读、成分物理意义、下游分析 | 分析者 |
| `10_run_logging` | **强制日志规范**：agent 身份注入、决策/异常记录、日志模板、验证步骤 | **agent 强制** |

---

## 五、输出日志的可审计信息（重点）

每次运行输出目录固定生成 **4 件套日志**，配合结果文件形成完整审计链：

### 5.1 `run_log.json`（机器可读，schema 2.0）

**顶层标识**：
- `schema_version: "2.0"` — 日志格式版本
- `run_id`（时间戳 + 8 位 UUID）— 全局唯一运行标识
- `status` — `running/completed/partial_failure/failed`
- `errors[]` — 结构化错误数组（时间戳/来源/信息/处理）

**pipeline_metadata（环境与版本指纹）**：

| 类别 | 字段 |
|------|------|
| 启动方式 | `launched_by`（script/agent）、`command`（完整启动命令）、`exit_code` |
| 时间 | `timestamp_start/end_utc` + local 双格式（ISO 8601 UTC） |
| 系统 | hostname、user、platform、python_version、python_executable |
| 代码版本 | **git commit（rev-parse HEAD）**、branch、`has_uncommitted_changes` |
| 依赖 | 5 核心包版本 + **完整 `pip freeze --all`** |
| 配置指纹 | `config_snapshot`：paths.py / CalibRUN.csv / requirements.txt 的 **路径 + SHA-256 + 大小** |

**sources[]（每个源一条）**：

| 类别 | 字段 |
|------|------|
| 状态 | `status`（success/skipped/failed）、`error_message`、时间戳 |
| Run 信息 | 源名、run 号、日期、位置(X,Y,Z)、R、E_true（来自 CalibRUN.csv 查询） |
| 输入指纹 | 输入 NPZ **路径+存在性+大小+SHA-256**；MC 模板**路径+SHA-256** |
| 事件统计 | 总事件数、有限值数、能量 min/max/mean/median、**200-bin 预选择谱直方图**（可重建输入分布） |
| 代码指纹 | fitter 文件路径、fitter 类型、git commit |
| 拟合参数 | **bins_fit、x_limit、mc_center、enable_c14、c14_convolver、fixed_params**（E_scale/a/b/c/C14_Amp） |
| 拟合结果 | μ、σ、σ/E、χ²、ndf、χ²/ndf、耗时 |
| 输出指纹 | 每个输出文件（NPZ/PDF）的**路径+存在性+大小+SHA-256** |

**agent_notes（agent 驱动时）**：agent_name、agent_version、workflow_description、decisions[]（决策+理由+时间戳）、exceptions[]（异常+处理）。

### 5.2 `run_log.md`（人类可读）

同一内容的 Markdown 表格化，含 ✅/❌/⏭ 状态标记、SHA-256 前缀展示、命令与退出码、每源输入/事件/结果/输出清单、汇总表、agent 决策与异常列表。

### 5.3 `config_snapshot.json`

`config/paths.py`、`CalibRUN.csv`、`requirements.txt` 的**完整文件内容**快照——第三方无需访问源码即可重建配置。

### 5.4 `console.log` + `traceback.log`

- `console.log`：完整终端输出（含拟合过程 print）
- `traceback.log`：未处理异常时的完整 traceback（context manager `__exit__` 自动生成）

### 5.5 可审计性闭环

**第三方复核路径**：取 `run_log.json` → 按 git commit 检出代码 → 按 `config_snapshot` 恢复配置 → 按 SHA-256 校验输入 NPZ/MC 模板与输出文件**字节级一致** → 比对 `fit_results` 与 NPZ 内参数 → 确认每个源 status 与 `console.log` 过程吻合。**失败运行也保底**：异常时 status=failed + traceback.log + 已完成的源记录，日志必然落盘。

---

## 六、测试验证状态

- **smoke test**：17/17 通过
- **Fast vs 经典**：μ 差异 < 0.05 keV，σ/E 差异 < 0.004%，加速 45-103x
- **独立模型测试**：仅给数据路径，4 个 run 全部跑通，SHA-256 与数值经第三方复核全部 MATCH
- 当前 example 输出：`output/example/`（5 源，2025-12 批次，全 success）

---

*本报告由 AI Assistant 基于项目实际代码、日志输出与运行验证生成。*
