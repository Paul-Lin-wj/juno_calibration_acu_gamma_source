# Skill: Setup & Environment — Install Dependencies

## Description

This skill covers how to set up the Python environment for the juno_calibration_acu_gamma_source project. Use this skill when setting up the project for the first time, or when you need to recreate the environment.

---

## Prerequisites

- **Python ≥ 3.10** (tested with Python 3.12.3)
- **pip** (installed with Python)
- No ROOT, cppyy, or C++ compiler required

## One-Command Setup

From the project root directory:

```bash
bash setup_env.sh
```

This will:
1. Create a Python virtual environment at `.venv/`
2. Upgrade pip to the latest version
3. Install all dependencies from `requirements.txt`

## Manual Setup (Step by Step)

If you prefer to do it manually:

```bash
# 1. Create virtual environment
python3 -m venv .venv

# 2. Activate it
source .venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Requirements (Pinned Versions)

From `requirements.txt`:

```
numpy==1.26.4
scipy==1.13.1
matplotlib==3.9.0
iminuit==2.30.1
pandas==2.2.2
```

### What Each Package Is For

| Package | Purpose |
|---------|---------|
| **numpy** | Array operations, histogramming, mathematical computations |
| **scipy** | Interpolation, integration (for C14 pileup convolution), FFT |
| **matplotlib** | Plotting fit results and summary figures |
| **iminuit** | χ² minimization (Minuit2 algorithm via Python bindings) |
| **pandas** | Reading CalibRUN.csv run-info mapping table |

## Self-Contained Packages (No Installation Needed)

The following are included directly in the repository and do not require separate installation:

- **`smx_ana/`** — Pure Python replacement for the `smx_ana` C++ extension
  - Provides `convolve()` — variable Gaussian smearing
  - Provides `sum_distributions_fast_cpp()` — C14 pileup convolution
  - Automatically loaded by `sys.path.insert` in each fitter script

## Verifying the Environment

After setup, verify everything works:

```bash
source .venv/bin/activate
python -c "
import numpy; print(f'numpy {numpy.__version__}')
import scipy; print(f'scipy {scipy.__version__}')
import matplotlib; print(f'matplotlib {matplotlib.__version__}')
import iminuit; print(f'iminuit {iminuit.__version__}')
import pandas; print(f'pandas {pandas.__version__}')
# Verify smx_ana works
import sys; sys.path.insert(0, 'smx_ana')
import smx_ana; print(f'smx_ana OK: {smx_ana.__file__}')
"
```

## Troubleshooting

### Problem: `pip install` fails with permission errors

```bash
# The .venv is in the project directory, so --user should not be needed.
# If it happens, try:
python3 -m venv .venv --clear
source .venv/bin/activate
pip install --no-cache-dir -r requirements.txt
```

### Problem: `matplotlib` backend errors ("Tcl_Init" or similar)

The pipeline automatically sets `matplotlib.use('Agg')` (non-interactive backend).
If running individual scripts and you see display errors:

```bash
export MPLCONFIGDIR=/tmp/mplconfig
export MPLBACKEND=Agg
```

### Problem: Missing `scipy.signal.fftconvolve` (older scipy)

The FastGe68Fitter defaults to FFT convolution for C14 pileup. If your scipy version is very old:

```python
# FastGe68Fitter falls back to np.convolve automatically:
# See FitterUtils.sum_distributions_fft() — it handles ImportError
```

### Problem: `iminuit` migration cost function change

The code uses `iminuit.cost.LeastSquares` (available in iminuit ≥ 2.22).
If using an older version, you may need:

```python
# Old API (not used in this project):
from iminuit import Minuit
c = LeastSquares(x, y, yerr, model)
m = Minuit(c, ...)
```

## Recreating the Environment

If you encounter issues or want a clean start:

```bash
rm -rf .venv
bash setup_env.sh
```