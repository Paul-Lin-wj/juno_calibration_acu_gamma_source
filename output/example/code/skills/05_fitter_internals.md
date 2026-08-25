# Skill: Fitter Internals — Model, Parameters, and Algorithm

## Description

This skill explains the mathematical model and fitting algorithm used by the fitters. Use this skill when you need to understand what the fitters compute, interpret fit parameters, or customize the fitting model.

---

## Common Fitting Model

All source fitters share the same underlying approach:

### Step 1: Histogram the Data

The input event energies are histogrammed into bins:

```python
bins_fit = np.arange(0.3, 2.0, 0.004)   # Example: Ge68 range
data_binned = np.histogram(data_arr, bins=bins_fit)[0]
data_errors = np.sqrt(data_binned)        # Poisson errors
```

Only bins with `count > 0` and `E > x_limit` are included in the fit.

### Step 2: Build the Model

The model has these components (example: Ge68):

```
model =  bkg_conv_0      (Compton background, smeared)
       + bkg_conv_0_2    (e⁺ in-flight background, smeared)
       + bkg_conv_1      (e⁺+γ mixing background, smeared)
       + gauss_HE        (γ~1.08 MeV high-energy peak)
       + FEP_hist        (Full-Energy Peak — the main signal)
       + C14 pileup      (single + double ¹⁴C pileup)
```

### Step 3: MC Template Convolution

Background components from MC templates are processed as:

```python
# 1. Scale by E_scale and histogram
bkg_hist = np.histogram(bkg_data * E_scale, bins=bins_fit, 
                         weights=np.ones_like(bkg_data)/len(bkg_data))[0]

# 2. Apply energy resolution smearing
energy_resolution = sqrt((a/sqrt(E))**2 + b**2 + (c/E)**2) * E * 0.01
bkg_conv = smx_ana.convolve(bkg_hist, bins_fit, energy_resolution)
```

### Step 4: C14 Pileup

The ¹⁴C pileup is computed by convolving the spectrum with the ¹⁴C energy distribution:

```python
# Single pileup: convolve spectrum with C14
z, single_pileup = convolver(bins_center, spectrum, bins_c14, c14_conv)
# Double pileup: convolve single pileup with C14 again
z, double_pileup = convolver(bins_center, single_pileup, bins_c14, c14_conv)
# Scale by C14_Amp
total = spectrum + C14_Amp * N * single + C14_Amp² * N * double
```

### Step 5: Minimize χ²

```python
from iminuit import Minuit
from iminuit.cost import LeastSquares

cost = LeastSquares(bins_center[nonzero], data_binned[nonzero], 
                    data_errors[nonzero], model_function)
m = Minuit(cost, ...)
m.migrad()  # χ² minimization
```

---

## Fitter Parameters

### Ge68 (FastGe68Fitter)

The FastGe68Fitter uses **14 parameters**, of which **5 are fixed**:

| Parameter | Default | Fixed? | Description |
|-----------|---------|:------:|-------------|
| `amp_gauss` | max(data) | No | Full-Energy Peak amplitude |
| `center_gauss` | argmax(data) | No | **Peak position μ** [MeV] |
| `sigma_gauss` | μ × 0.035 | No | **Peak width σ** [MeV] |
| `amp_gauss_HE` | max/10 | No | High-energy γ amplitude |
| `center_gauss_HE` | μ + 0.1 | No | High-energy γ position |
| `sigma_gauss_HE` | 0.045 | No | High-energy γ width |
| `amp_b0` | max × 10 | No | Compton background amplitude |
| `amp_b0_2` | max × 10 | No | e⁺ in-flight background amplitude |
| `amp_b1` | max/10 | No | e⁺+γ mixing amplitude |
| **`C14_Amp`** | **0.047** | **Yes** | ¹⁴C pileup amplitude |
| **`E_scale`** | μ/0.8845 | **Yes** | Energy scale factor |
| **`a`** | **3.309** | **Yes** | Resolution stochastic term |
| **`b`** | **1.28** | **Yes** | Resolution constant term |
| **`c`** | **0.0** | **Yes** | Resolution noise term |

### Why Parameters Are Fixed

- **`E_scale`**: The data is already Finalcorrection-corrected, so the absolute energy scale is known
- **`a/b/c`**: Resolution parameters are determined from the full multi-source fit (step ⑤ of the chain), not per-run
- **`C14_Amp`**: The ¹⁴C background level is stable and pre-calibrated

---

## Energy Resolution Model

The detector energy resolution is parameterized as:

```
σ(E) = √((a/√E)² + (b/E)² + c²) × E / 100
```

Or equivalently:

```
σ/E (%) = √(a²/E + b²/E² + c²) × 100
```

Where:
- **a**: Stochastic term (photoelectron statistics)
- **b**: Constant term (non-uniformity, calibration)
- **c**: Noise term (electronics)

Default JUNO values: `a = 3.309`, `b = 1.28`, `c = 0.0`

---

## What Each Fitter Does Differently

| Aspect | Ge68 | Cs137 | Mn54 | Co60 | K40 |
|--------|------|-------|------|------|-----|
| **Fit range** | 0.3–2.0 MeV | 0.3–0.9 MeV | 0.5–1.0 MeV | 1.9–2.7 MeV | 1.0–1.8 MeV |
| **Bin width** | 0.004 MeV | 0.004 MeV | 0.004 MeV | 0.004 MeV | 0.004 MeV |
| **Background templates** | Compton_0, Compton_1, gamma_positron | Compton | Compton | Compton | Compton |
| **Extra peaks** | γ~1.08 MeV HE | — | — | — | — |
| **MC_Qedep_Center** | 0.8845 MeV | — | — | — | — |

---

## FastGe68Fitter & FastSourceFitter Caching Strategy

The key optimization in both `FastGe68Fitter` (Ge68) and `FastSourceFitter` (Cs137, Mn54, Co60, K40):

```
INIT (once):
  ┌── histogram MC templates (3 backgrounds + C14)
  ├── smx_ana.convolve each (3 backgrounds)           ← cached
  └── save in self.cached dict

ITERATION (each Minuit call):
  ┌── multiply cached backgrounds by amplitudes        ← O(1), no histogram
  ├── add Gaussian peaks                                ← O(n_bins)
  ├── compute C14 pileup (only non-cached part)        ← O(n_bins × n_c14)
  └── return model[nonzero]
```

The classic fitters do **all** of the "INIT" work on **every** iteration, which is why they are ~100× slower.

---

## Interpreting Fit Quality

### χ²/ndf

| Value | Interpretation |
|:-----:|---------------|
| < 1.0 | Possible over-fitting or over-estimated errors |
| **1.0–1.5** | **Good fit** |
| 1.5–2.0 | Acceptable; may have minor model deficiencies |
| > 2.0 | Poor fit; check input data, range, or model |

### sigma/E (Resolution)

| Energy | Typical JUNO Resolution |
|:------:|:-----------------------:|
| 0.6 MeV (Cs137) | ~4.3% |
| 0.8 MeV (Mn54) | ~3.9% |
| 0.9 MeV (Ge68) | ~3.5% |
| 1.5 MeV (K40) | ~3.0% |
| 2.5 MeV (Co60) | ~2.3% |

These values assume CD (central detector) center position after Finalcorrection.

### μ vs E_true

Ideally μ ≈ E_true. Differences indicate:
- Energy non-linearity (physical)
- Residual calibration offset (systematic)
- Poor fit convergence (algorithmic; check χ²)

---

## FastSourceFitter (Generic Fast Fitter)

`src/FastSourceFitter.py` implements a generic fast fitter for Cs137, Mn54, Co60, and K40.

### Configuration

The per-source parameters are defined in `SOURCE_CONFIG`:

```python
SOURCE_CONFIG = {
    "Cs137": { "bkg_npz": "Cs137_Compton_BKG.npz", "mc_center": 0.58423,
               "x_limit": 0.3, "bins_fit": np.arange(0.3, 0.9, 0.004) },
    "Mn54":  { "bkg_npz": "Mn54_Compton_BKG.npz",  "mc_center": 0.75067,
               "x_limit": 0.3, "bins_fit": np.arange(0.5, 1.0, 0.004) },
    "Co60":  { "bkg_npz": "Co60_Compton_BKG.npz",  "mc_center": 2.30545,
               "x_limit": 1.0, "bins_fit": np.arange(1.9, 2.7, 0.004) },
    "K40":   { "bkg_npz": "K40_Compton_BKG.npz",   "mc_center": 1.35506,
               "x_limit": 0.6, "bins_fit": np.arange(1.0, 1.8, 0.004) },
}
```

### Model Structure

All four sources have the same model:
- 1 Compton background template (histogrammed + smeared once, cached)
- 1 Gaussian Full-Energy Peak
- C14 pileup (single + double, computed on each iteration)

This is simpler than Ge68's model (which has 3 backgrounds + 1 extra high-energy peak).

### Performance

| Source | Fast | Classic | Speedup |
|--------|:----:|:-------:|:-------:|
| Cs137 | 0.22s | 12.5s | **56x** |
| Mn54 | 0.17s | 7.5s | **45x** |
| Co60 | 0.32s | 26.6s | **84x** |
| K40 | 0.16s | 16.5s | **103x** |

All 4 sources run in **~0.9 seconds total** (vs ~63s for classic).