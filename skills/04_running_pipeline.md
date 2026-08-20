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
| Cs137 | `MCBased_Fitter` → `Cs137Fitter` | **~15-20 seconds** |
| Mn54 | `MCBased_Fitter` → `Mn54Fitter` | **~10-15 seconds** |
| Co60 | `MCBased_Fitter` → `Co60Fitter` | **~80-90 seconds** |
| K40 | `MCBased_Fitter` → `K40Fitter` | **~25-30 seconds** |

Total: **~2-3 minutes** for all 5 sources.

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
├── enl_style_resolution.png   # Summary plot (raster)
└── enl_style_resolution.pdf   # Summary plot (vector)
```

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

To fit a single source without the full pipeline:

```bash
# Fast Ge68 fitter (recommended for Ge68)
source .venv/bin/activate
python -c "
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

# Classic fitter (for other sources)
python -c "
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

Measured on: Intel Xeon Platinum 8358P (128 logical cores / 1TB RAM)

| Source | Fitter Type | Single Run | 41 Runs (serial) | 41 Runs (parallel) |
|--------|:-----------:|:----------:|:-----------------:|:------------------:|
| Ge68 | Fast | **4-6 s** | ~3 min | ~6-10 s (41 cores) |
| Ge68 | Classic | ~5-15 min | ~3-5 hours | ~20-25 min (41 cores) |
| Cs137 | Classic | ~15-20 s | ~10-15 min | ~1 min (5 cores) |
| Co60 | Classic | ~80-90 s | ~1 hour | ~2 min (5 cores) |

---

## Re-running the Pipeline

- **Each run creates a new timestamp directory** — no output is overwritten
- To re-run with the same configuration: just run `bash run_pipeline.sh` again
- To compare results from different runs: look in different `output/*/` directories