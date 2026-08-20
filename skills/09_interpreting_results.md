# Skill: Interpreting Results — Fit Parameters, Quality Metrics, and Next Steps

## Description

This skill explains how to interpret the fitting results, assess fit quality, and use the outputs for downstream analysis (energy non-linearity correction).

---

## Reading a Fit Result NPZ File

Each `.npz` file contains a serialized dictionary with all fit parameters and diagnostic information:

```python
import numpy as np

with np.load("output/20260820_211401/results/RUN9541_Ge68.npz", allow_pickle=True) as f:
    # Access scalar parameters
    chi2 = float(f["chi2"])
    ndf = int(f["ndf"])
    total_count = float(f["total_count"])

    # Access fitted values with errors
    center = f["center_gauss"].item()
    sigma = f["sigma_gauss"].item()
    print(f"μ = {center['value']:.4f} ± {center['error']:.6f} MeV")
    print(f"σ = {sigma['value']:.4f} ± {sigma['error']:.6f} MeV")
    print(f"σ/E = {sigma['value']/center['value']*100:.2f}%")

    # Access background components
    components = f["components"].item()
    # components contains: bkg_conv_0, bkg_conv_0_2, bkg_conv_1,
    #                      gauss_HE, FEP_hist, one_pileup, two_pileup, model_result
```

---

## Fit Quality Metrics

### 1. χ² / ndf

The primary goodness-of-fit metric:

| χ²/ndf | Assessment |
|:------:|-----------|
| **0.8 – 1.2** | ✅ **Excellent fit** — model describes data well |
| **1.2 – 1.5** | ⚠️ Acceptable — minor model-data discrepancies |
| **1.5 – 2.0** | ⚠️ Marginal — possible model deficiencies or data issues |
| **> 2.0** | ❌ Poor fit — investigate |

Note: χ² is computed only for bins with `E > x_limit` and `data_binned > 0`.

### 2. Parameter Errors

Parameter errors from Minuit (HESSE or MINOS):

- Small errors (< 1% of value) → well-constrained parameters ✅
- Large errors (> 10% of value) → parameter is not well-constrained ⚠️
- Errors reported as zero → parameter may have hit boundary

### 3. Visual Inspection

Always check the fit figure PDF:
- **Does the model (black line) follow the data (green points)?**
- **Are the background components physically reasonable?**
- **Are there systematic deviations in any energy region?**

### 4. C14 Pileup Proportion

The pileup proportion is shown on the fit figure:

```
Pile-up Pro. 4.6%
```

This should be:
- **~4-6%** for typical Ge68 runs (default C14_Amp=0.047)
- Higher for runs with more events
- Lower if C14 component is disabled

---

## Key Fitting Results Summary

A successful Ge68 fit at CD center should produce:

| Parameter | Expected Value | Notes |
|-----------|:--------------:|-------|
| **μ** (center_gauss) | **0.906 ± 0.001 MeV** | After Finalcorrection; ~2.4% above E_true (0.8845) due to non-linearity |
| **σ** (sigma_gauss) | **0.0314 ± 0.0004 MeV** | Corresponds to ~3.47% resolution |
| **σ/E** | **3.47%** | At 0.9 MeV, center position |
| **χ²/ndf** | **~1.08** | For Ge68 with x_limit=0.51, ~351 bins |
| **E_scale** | **1.029** | Peak position / MC_Qedep_Center |
| **C14_Amp** | 0.047 (fixed) | ¹⁴C background amplitude |
| **a** | 3.309 (fixed) | Stochastic resolution term |
| **b** | 1.28 (fixed) | Constant resolution term |

### Variation with Z-Position

| Z Position | μ (MeV) | σ/E (%) | Notes |
|:----------:|:-------:|:-------:|-------|
| **0 m** (center) | 0.906 | 3.47% | Best resolution |
| **+18.4 m** (top) | 0.762 | 4.66% | Worst resolution, largest bias |
| **-17.3 m** (bottom) | ~0.78 | ~4.7% | Similar to top (symmetric) |

---

## Component Breakdown Interpretation

The fit decomposes the measured spectrum into:

### Physical Components

| Component | Physical Origin | Shape |
|-----------|----------------|-------|
| **FEP_hist** (Full-Energy Peak) | Gamma fully absorbed in scintillator | Gaussian (~3.5% width) |
| **Compton (bkg_conv_0)** | Gamma Compton-scatters, escapes | Continuum from 0 to E_γ |
| **e⁺ in-flight (bkg_conv_0_2)** | Positron annihilates while moving | Broad continuum |
| **e⁺+γ mixing (bkg_conv_1)** | Mixed e⁺ and gamma interactions | Complex shape |
| **γ~1.08 MeV (gauss_HE)** | High-energy gamma from Ge68 decay | Gaussian at ~1.08 MeV |
| **¹⁴C pileup** | Two independent events pile up | Smeared low-energy hump |

### Component Amplitudes

The amplitudes (`amp_b0`, `amp_b0_2`, `amp_b1`) represent the scaling factors applied to the MC template shapes. They are not physically meaningful on their own, but their ratios can indicate:

- `amp_b0` > `amp_b0_2` → Compton scattering dominates (normal)
- `amp_b0_2` > `amp_b0` → Possible detector geometry effect (check position)

---

## Using Results for Downstream Analysis

### 1. Energy Non-Linearity Correction

The fitted μ values for multiple sources are used as input to the energy non-linearity (ENL) fitter:

```
Input:  (E_true_i, μ_i) for i ∈ {Ge68, Cs137, Mn54, Co60, K40}
Output: f(E) = μ(E_true) / E_true  →  non-linearity correction function
```

This is the purpose of the separate `fitter_energynl_dybmodel/` module.

### 2. Resolution Model Fitting

The σ/E values at different energies are fitted with the JUNO resolution model:

```
σ/E(E) = √(a²/E + b²/E² + c²)
```

This gives per-phase (or per-position) resolution parameters a, b, c.

### 3. Time Evolution

Fitting the same source at the same position over time (different runs from different dates) → monitor detector stability.

---

## Common Red Flags

| Red Flag | What It Means | Action |
|----------|---------------|--------|
| `χ²/ndf < 0.5` | Very unlikely for real data | Check if errors are over-estimated |
| `χ²/ndf > 3.0` | Model fails to describe data | Check fit figure for systematic deviation |
| `center_gauss.error > 0.01` | Peak not well determined | Low statistics or poor fit range |
| `sigma_gauss.value < 0.01` | Unphysically narrow peak | Fit may have locked onto noise |
| `total_count < 1000` | Very few events | Results may be unreliable |
| Component amplitudes at boundary | Background component not needed | Consider simplifying the model |