# Skill: Running the Pipeline — Fit All Sources and Generate Plots

## Description

This skill explains how to execute the full fitting pipeline. Use this skill when you want to fit all calibration sources and produce the ENL-style resolution summary plot.

---

## Quick Start

After configuration, run:

```bash
bash run_pipeline.sh
```

This single command:
1. Creates the virtual environment (if not exists)
2. Installs dependencies
3. Runs all fits sequentially
4. Generates the ENL-style summary plot

---

## What the Pipeline Does

The pipeline (`pipeline/run_fit_all.py`) executes these steps:

### Step 1: Fit Each Source (Sequentially)

For each entry in `config/paths.py` → `SOURCES`:

| Source | Fitter | Typical Time |
|--------|--------|:------------:|
| Ge68 | `FastGe68Fitter` (cached) | **~4-6 seconds** |
| Cs137 | `FastSourceFitter` (cached) | **~0.3-0.6 seconds** |
| Mn54 | `FastSourceFitter` (cached) | **~0.2-0.5 seconds** |
| Co60 | `FastSourceFitter` (cached) | **~0.3-0.7 seconds** |
| K40 | `FastSourceFitter` (cached) | **~0.2-0.4 seconds** |

Total: **~6 seconds** for all 5 sources.

### Step 2: Collect Results

Each fit produces a `.npz` result file. The pipeline reads:
- `center_gauss` → peak position μ
- `sigma_gauss` → width σ
- `chi2` / `ndf` → goodness of fit

### Step 3: Draw ENL-Style Summary Plot

A single plot is generated showing **σ/E (%) vs E_rec (MeV)** for all sources, with a JUNO reference resolution curve.

---

## Output Directory Structure

Each run produces a timestamped output directory:

```
output/20260820_211401/
├── results/
│   ├── RUN9541_Ge68.npz       # Fit result: parameters, χ², components
│   ├── RUN9600_Cs137.npz
│   ├── RUN9624_Mn54.npz
│   ├── RUN9591_Co60.npz
│   └── RUN9632_K40.npz
├── figures/
│   ├── RUN9541_Ge68.pdf       # Fit figure: data + model + components
│   ├── RUN9600_Cs137.pdf
│   ├── RUN9624_Mn54.pdf
│   ├── RUN9591_Co60.pdf
│   └── RUN9632_K40.pdf
├── code/                      # ★ complete code snapshot + code/sha256.json
├── enl_style_resolution.png   # Summary plot (raster)
└── enl_style_resolution.pdf   # Summary plot (vector)
```

> **End-of-run audit (automatic)**: every run finishes by copying the complete
> code tree into `code/` (byte-identical, sha256-fingerprinted) and verifying
> that (a) every code file matches the working tree and (b) every deliverable
> exists. Result in `run_log.json -> audit` / `run_log.md -> Audit`.
> Failure: script mode exits with **code 3**; agent mode prints
> `[AUDIT] WARNING` and sets status `audit-failed`.

---

## Understanding the Output Files

### Result NPZ Files

Each `.npz` contains a dictionary with keys:

| Key | Type | Description |
|-----|------|-------------|
| `center_gauss` | dict `{value, error}` | Fitted peak position μ [MeV] |
| `sigma_gauss` | dict `{value, error}` | Fitted peak width σ [MeV] |
| `amp_gauss` | dict | Fitted peak amplitude |
| `center_gauss_HE` | dict | High-energy gamma (1.08 MeV) peak position |
| `sigma_gauss_HE` | dict | High-energy gamma width |
| `amp_b0`, `amp_b0_2`, `amp_b1` | dict | Background component amplitudes |
| `C14_Amp` | dict | ¹⁴C pileup amplitude |
| `E_scale` | dict | Energy scale factor |
| `a`, `b`, `c` | dict | Energy resolution model parameters |
| `chi2` | float | Chi-squared value |
| `ndf` | int | Number of degrees of freedom |
| `total_count` | int | Total events used in fit |
| `components` | dict | Decomposed fit components (for plotting) |

### Fit Figures

- **Ge68 (Fast)**: LogY scale, showing data + total model + component breakdown
- **Other sources (Classic)**: Linear scale full-range fit

### Summary Plot

- **X-axis**: Reconstructed energy E_rec [MeV]
- **Y-axis**: Energy resolution σ/E [%]
- **Points**: Each source at its fitted μ and σ/E
- **Dashed curve**: JUNO reference stochastic resolution model

---

## Running Individual Sources

To fit a single source without the full pipeline, you need to set up the Python path first:

```bash
# Fast Ge68 fitter
source .venv/bin/activate
PROJ_DIR="$(pwd)"
python -c "
import sys
sys.path.insert(0, '${PROJ_DIR}')
sys.path.insert(0, '${PROJ_DIR}/src')
sys.path.insert(0, '${PROJ_DIR}/fitters')
sys.path.insert(0, '${PROJ_DIR}/smx_ana')

from src.FastGe68Fitter import run_fast_ge68_fitter
outputs = run_fast_ge68_fitter(
    run_id=9541,
    input_path='/path/to/Run9541_SelectionResult.npz',
    output_fig_dir='output/figures',
    output_res_dir='output/results',
    enable_c14=True,
    c14_convolver='fft',
)
print(outputs['result_npz'])
"

# Fast source fitter (Cs137, Mn54, Co60, K40)
python -c "
import sys
sys.path.insert(0, '${PROJ_DIR}')
sys.path.insert(0, '${PROJ_DIR}/src')
sys.path.insert(0, '${PROJ_DIR}/fitters')
sys.path.insert(0, '${PROJ_DIR}/smx_ana')

from src.FastSourceFitter import run_fast_source_fitter
outputs = run_fast_source_fitter(
    source='Cs137',
    run_id=9600,
    input_path='/path/to/Run9600_SelectionResult.npz',
    output_fig_dir='output/figures',
    output_res_dir='output/results',
    enable_c14=True,
)
print(outputs['result_npz'])
"

# Classic fitter (fallback, for comparison)
python -c "
import sys
sys.path.insert(0, '${PROJ_DIR}')
sys.path.insert(0, '${PROJ_DIR}/src')
sys.path.insert(0, '${PROJ_DIR}/fitters')
sys.path.insert(0, '${PROJ_DIR}/smx_ana')

from src.MCBased_Fitter import run_fitter
outputs = run_fitter(
    run_id=9600,
    source='Cs137',
    input_path='/path/to/Run9600_SelectionResult.npz',
    output_fig_dir='output/figures',
    output_res_dir='output/results',
)
print(outputs['result_npz'])
"
```

> ⚠️ The `sys.path.insert` calls are required because the fitter modules use `from fitters.xxx import ...` and `from src.xxx import ...` style imports. The `run_pipeline.sh` script handles this automatically — these manual steps are only needed when calling individual fitters directly.

---

## Understanding the Console Output

During the pipeline run, you'll see output like:

```
============================================================
[Ge68] RUN9541 (E_true=0.8845 MeV)
[Ge68] Input: /data/.../Run9541_SelectionResult.npz
[Info] Starting fast Ge68 fit for RUN9541_Ge68
[Progress] Fast Ge68 fit finished for RUN9541_Ge68
[Output] Fit results saved to: .../RUN9541_Ge68.npz
[Output] Log-y figure saved to: .../RUN9541_Ge68.pdf
[Ge68] mu=0.9056, sigma/E=3.47%, chi2/ndf=380/351, time=4.1s
```

Key indicators:
- **`chi2/ndf`**: Should be close to 1.0 for a good fit (values up to ~1.2 are acceptable)
- **`sigma/E`**: Typical JUNO resolution is 3-5% at 1 MeV
- **`time`**: Compare with expected times (Fast ~5s, Classic ~15-90s)

---

## Performance Benchmarks

Measured on: **Intel Xeon Platinum 8358P** (128 logical cores, 1 TB RAM), **Python 3.12.3**, **serial execution** (single core), **~22k events** per run, **after first-run cache warmup**.

| Source | Fitter Type | Single Run | 41 Runs (serial) | 41 Runs (parallel) |
|--------|:-----------:|:----------:|:-----------------:|:------------------:|
| Ge68 | Fast | **4-6 s** | ~3 min | ~6-10 s (41 cores) |
| Ge68 | Classic | ~5-15 min | ~3-5 hours | ~20-25 min (41 cores) |
| Cs137 | Fast | **~0.3 s** | **~12 s** | **~0.3 s** (41 cores) |
| Cs137 | Classic | ~7-15 s | ~5-10 min | ~10-20 s (41 cores) |
| Co60 | Fast | **~0.5 s** | **~20 s** | **~0.5 s** (41 cores) |
| Co60 | Classic | ~15-27 s | ~10-18 min | ~30-60 s (41 cores) |

> **Performance notes**: Times may vary depending on CPU, event count, Python version, and whether matplotlib/smx_ana caches are warm. The first run after a fresh `.venv` may be slower due to matplotlib font cache initialization. Parallel execution assumes independent runs — no shared state.

---

## Re-running the Pipeline

- **Each run creates a new timestamp directory** — no output is overwritten
- To re-run with the same configuration: just run `bash run_pipeline.sh` again
- To compare results from different runs: look in different `output/*/` directories

---

## Multi-Batch Processing (Multiple Time Periods)

There is **no separate multi-batch script**. To process multiple batches of runs
(e.g. several data-taking periods), run the normal pipeline once per batch —
each run gets its own timestamped directory and full audit log.

### Recommended Agent Workflow

1. **Prepare batch configurations** — for each batch, edit `SOURCES` in
   `config/paths.py` to the runs of that period (see `03_configuration.md`).
2. **Run once per batch**:

   ```bash
   bash run_pipeline.sh        # batch 1 → output/YYYYMMDD_HHMMSS_1/
   # edit config/paths.py SOURCES for batch 2
   bash run_pipeline.sh        # batch 2 → output/YYYYMMDD_HHMMSS_2/
   ```

3. **Compare batches** with `plot_fit_summary.py` using multiple result dirs:

   ```bash
   source .venv/bin/activate
   python src/plot_fit_summary.py \
       --results-dir "Phase1=output/20260101_000000/results" \
       --results-dir "Phase2=output/20260201_000000/results" \
       --run-info CalibRUN.csv \
       --outdir output/comparison
   ```

   This produces μ-vs-Z and σ/E-vs-Z plots with a **ratio panel** comparing
   the two batches (see `08_zscan_analysis.md` for interpretation).

4. **For agent-driven batch runs**, pass agent metadata on each invocation:

   ```bash
   python pipeline/run_fit_all.py \
       --launched-by agent \
       --agent-name "YourAgent" \
       --agent-version "1.0" \
       --agent-workflow "Batch 1: Aug 2025 sources at CD center"
   ```

> **Note**: Each batch produces a fully independent `run_log.json` /
> `run_log.md` / `config_snapshot.json` / `console.log` with its own
> `run_id`, SHA-256 fingerprints, and source-level status — suitable for
> third-party audit of every batch separately.