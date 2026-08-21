# Skill: Project Overview — juno_calibration_acu_gamma_source

## Description

This skill provides a comprehensive overview of the **JUNO ACU Gamma Source Energy Spectrum Fitter** project. Use this skill when you need to understand what the project does, its architecture, and when to apply it.

---

## What This Project Does

This is a **standalone Python fitting workflow** for JUNO (Jiangmen Underground Neutrino Observatory) calibration-source energy spectra. It fits reconstructed energy distributions with source-specific models built from JUNO Monte Carlo (MC) templates plus detector-response parameters.

### Supported Calibration Sources

The default pipeline configuration supports these 5 sources at CD center:

| Source | True Energy (MeV) | Type | Default Fitter |
|--------|:-----------------:|------|:--------------:|
| Ge68   | 0.8845            | Gamma (e⁺e⁻ annihilation) | FastGe68Fitter |
| Cs137  | 0.662             | Mono-energetic gamma | FastSourceFitter |
| Mn54   | 0.835             | Mono-energetic gamma | FastSourceFitter |
| Co60   | 2.506             | Two gamma cascade (1.173 + 1.332 MeV) | FastSourceFitter |
| K40    | 1.461             | Mono-energetic gamma | FastSourceFitter |

> ⚠️ **AmC / O16**: The repository includes O16/AmC fitter code (`fitters/O16Fitter.py`), but it is **not** part of the default pipeline because it requires data from the `correlate_selection` chain (different NPZ format) and has not been validated end-to-end in this standalone project.

### Pipeline Outputs

For each run, the pipeline produces:

1. **Fit results** (`.npz`): peak position μ, resolution σ, χ²/ndf, background amplitudes, component decomposition
2. **Fit figure** (`.pdf`): data points + total model + component breakdown (LogY for Ge68, linear full-range for others)
3. **ENL-style summary plot** (`.png` + `.pdf`): resolution σ/E vs reconstructed energy E_rec for all sources

### Architecture Overview

```
input data (NPZ)  →  source-specific fitter  →  χ² minimization (iminuit)  →  result NPZ + figure
                                                                                ↓
                                                                         ENL-style summary plot
```

### Key Design Decisions

- **Two fitter families**:
  - `FastGe68Fitter` — Ge68-specific, caches MC template convolutions, ~4-6s per run
  - `FastSourceFitter` — Generic fast fitter for Cs137/Mn54/Co60/K40, ~0.2-0.7s per run
  - Classic fitters — Per-source implementations in `fitters/`, retained as fallback (~7-27s per run)
- **Pure Python**: No ROOT, cppyy, or C++ extensions required
- **smx_ana fallback**: The `smx_ana` package is included as pure Python (no compiled `.so` needed)
- **Timestamp outputs**: Each run creates `output/YYYYMMDD_HHMMSS/` — never overwrites previous results

### When to Use This Project

- ✅ Fitting JUNO calibration gamma ray energy spectra
- ✅ Extracting peak positions and energy resolutions from ACU source runs
- ✅ Comparing different detector positions (z-scan) or time periods
- ✅ Preparing input data for energy non-linearity correction fitting

### When NOT to Use This Project

- ❌ Raw data processing (use the upstream `npz_from_root` + `Finalcorrection` chain)
- ❌ Event selection / filtering (use the upstream `calib_selection` scripts)
- ❌ Energy non-linearity global fitting (use `fitter_energynl_dybmodel` instead)

---

## Project Directory Structure

```
standalone_fitter/
├── config/paths.py              # ★ Central path configuration (edit this first)
├── src/
│   ├── FastGe68Fitter.py        # Cached-template Ge68 fitter (~4-6s/run)
│   ├── FastSourceFitter.py      # Generic fast fitter for Cs137/Mn54/Co60/K40 (~0.2-0.7s/run)
│   └── MCBased_Fitter.py        # Classic fitter entry point (fallback, ~7-27s/run)
├── fitters/                     # Per-source fitter implementations + MC templates
├── smx_ana/                     # Pure-Python smx_ana replacement
├── pipeline/run_fit_all.py      # Main orchestration script
├── setup_env.sh                 # Environment setup (venv + deps)
├── run_pipeline.sh              # One-click run
├── requirements.txt             # Pinned dependency versions
└── CalibRUN.csv                 # Run → source/position mapping
```

---

## Relationship to Upstream Chain

This project is **step ④** of the full JUNO calibration analysis pipeline:

```
ROOT/ESD  → ① NPZ conversion  → ② Finalcorrection  → ③ Event selection  → ④ ★ THIS FITTER  → ⑤ Analysis
```

It reads the output of steps ①-③ (the `Run{N}_SelectionResult.npz` files) and produces inputs for step ⑤ (energy non-linearity correction and time-evolution analysis).