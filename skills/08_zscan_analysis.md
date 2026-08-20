# Skill: Running Z-Scans — Fitting Multiple Positions Along the Detector

## Description

This skill explains how to run fits for multiple runs at different source positions (z-scan) to study position-dependent detector response. Use this skill when you want to analyze how the energy scale and resolution vary with source position along the detector axis.

---

## What is a Z-Scan?

A z-scan moves the calibration source along the z-axis of the JUNO detector (central detector, ACU system). This produces a set of runs at different z positions, typically from z = +18.4 m (top) to z = -17.3 m (bottom), in ~0.2-2.0 m steps.

Typical Ge68 z-scan: **41 runs** from 9497 to 9577 (step 2).

---

## Running a Z-Scan with FastGe68Fitter

For Ge68, the FastGe68Fitter makes z-scans practical — **41 runs in ~3 minutes** (serial).

### Step 1: Prepare the Source List

In `config/paths.py`, configure the sources:

```python
SOURCES = [
    ("Ge68_top",    9497, 0.8845, "fast"),
    ("Ge68_top2",   9499, 0.8845, "fast"),
    # ... add all z-scan runs
    ("Ge68_bottom", 9577, 0.8845, "fast"),
]
```

Or for a quick test, run directly:

```python
runs = list(range(9497, 9578, 2))  # 41 runs
for run_id in runs:
    outputs = run_fast_ge68_fitter(
        run_id=run_id,
        input_path=f"{DATA_INPUT_PATH}/Run{run_id}_SelectionResult.npz",
        output_fig_dir="output/zscan/figures",
        output_res_dir="output/zscan/results",
        enable_c14=True,
        c14_convolver="fft",
    )
```

### Step 2: Generate Z-Scan Summary Plots

After fitting all z-scan runs, use `plot_fit_summary.py`:

```bash
source .venv/bin/activate
python src/plot_fit_summary.py \
    --results-dir "zscan=output/zscan/results" \
    --run-info CalibRUN.csv \
    --outdir output/zscan/summary
```

This produces:

| Plot | Description |
|------|-------------|
| `fit_mu_vs_true_z.png` | Fitted peak position μ vs source Z position |
| `fit_resolution_vs_true_z.png` | Energy resolution σ/E vs source Z position |

### Interpreting Z-Scan Plots

**μ vs Z**: 
- Ideally flat (position-independent energy scale)
- Residual slope indicates position-dependent non-linearity
- Typical variation: ~1-2% from center to edge (z = ±17.2 m)

**σ/E vs Z**:
- Should be symmetric around z = 0
- Worse resolution at edges due to larger light collection variation
- Typical: ~3.5% at center, ~4.5-5.0% at ±17.2 m

---

## Performance Comparison: Z-Scan (41 runs)

| Method | Serial | Parallel (41 cores) |
|--------|:------:|:-------------------:|
| **FastGe68Fitter** | **~3 minutes** | **~6-10 seconds** |
| Classic Ge68Fitter | ~3-5 hours | ~20-25 minutes |
| Original BinnedNLL | ~12 hours | ~25 minutes (documented) |

For parallel execution with GNU parallel:

```bash
seq 9497 2 9577 | parallel -j 41 "python -c '
from src.FastGe68Fitter import run_fast_ge68_fitter
run_fast_ge68_fitter(run_id={}, input_path=\".../Run[removed]_SelectionResult.npz\")'"
```

---

## Comparing Multiple Versions

The `plot_fit_summary.py` script supports comparing two sets of results:

```bash
python src/plot_fit_summary.py \
    --results-dir "version_A=output/vA/results" \
    --results-dir "version_B=output/vB/results" \
    --run-info CalibRUN.csv \
    --outdir output/comparison
```

This produces a two-panel plot:
- **Top**: μ or σ/E vs Z for both versions
- **Bottom**: Ratio (version_B / version_A) vs Z

Useful for comparing:
- Different calibration versions (e.g., with/without Finalcorrection)
- Different reconstruction algorithms
- Different time periods