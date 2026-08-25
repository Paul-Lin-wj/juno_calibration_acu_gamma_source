# Skill: Troubleshooting — Common Issues and Solutions

## Description

This skill covers common problems encountered when running the fitting pipeline and how to resolve them.

---

## Fitting Issues

### Problem: Fit does not converge (iminuit reports `valid=False`)

**Symptoms**:
```
[migrad] fval=... center=0.000000 valid=False
```
or `chi2/ndf` is extremely large (>10).

**Causes and Solutions**:

| Cause | Solution |
|-------|----------|
| Wrong initial parameter values | The code auto-initializes from data max, but for unusual runs this may fail. Check the data histogram first. |
| Empty or all-zero data | Verify the input NPZ has valid events. |
| x_limit too high | Reduce `x_limit` (currently 0.51 for Fast, 0.6 for classic) to include more bins. |
| Too few events | Fits need at least ~1000 events for stable convergence. |

### Problem: χ²/ndf is too high (> 2.0)

**Causes**:
- Model mismatch (e.g., Ge68 fitter used on a non-Ge68 source)
- Data quality issues (noisy events, wrong selection)
- Fit range includes regions poorly described by the model

**Solutions**:
- Check the fit figure to identify where the model deviates from data
- Verify the run source type in `CalibRUN.csv`
- Try adjusting `x_limit` to exclude problematic low-energy bins

### Problem: Peak position μ is far from expected E_true

For Ge68 (E_true = 0.8845 MeV), typical fitted μ is ~0.906 MeV after Finalcorrection.

| μ Value | Likely Cause |
|:-------:|--------------|
| ~0.906 | ✅ Normal (energy non-linearity) |
| ~0.884 | ❌ Data is NOT Finalcorrection-corrected |
| ~0.700 | ❌ Wrong source type (maybe Cs137) |
| ~0.500 | ❌ Fit converged to background, not peak |
| > 1.0 | ❌ Wrong source or bad data |

**Solution**: Verify the input data. If μ is close to E_true exactly, the data may not have been Finalcorrection-corrected (which applies a ~2% scale factor).

### Problem: σ/E (resolution) is unexpectedly large

| σ/E Value | Likely Cause |
|:---------:|--------------|
| 3.5% | ✅ Normal for Ge68 at center (0.9 MeV) |
| > 5% | ❌ Too broad — x_limit too low includes noisy bins |
| > 10% | ❌ Fit didn't converge properly |
| < 2% | ❌ Too narrow — fit captured noise peak |

---

## Environment Issues

### Problem: Module import errors

**Symptom**:
```
ModuleNotFoundError: No module named 'fitters'
```

**Cause**: The Python path does not include the project directory.

**Solution**:
```bash
cd /path/to/standalone_fitter
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd):$(pwd)/src:$(pwd)/fitters:$(pwd)/smx_ana"
python pipeline/run_fit_all.py
```

Or just use:
```bash
bash run_pipeline.sh  # handles paths automatically
```

### Problem: `smx_ana` import fails

**Symptom**:
```
ImportError: cannot import name 'convolve' from 'smx_ana'
```

**Cause**: The `smx_ana` package is not on the Python path, or the `__init__.py` is missing.

**Solution**: Verify the directory structure:
```
standalone_fitter/
  smx_ana/
    __init__.py       # contains: from smx_ana.smx_ana_cpp import convolve
    smx_ana_cpp.py    # contains: def convolve(...)
```

### Problem: `sum_distributions_fast_cpp` not found

**Symptom**:
```
ImportError: cannot import name 'sum_distributions_fast_cpp' from 'smx_ana.smx_ana_cpp'
```

**Solution**: This function is provided as a Python fallback in the included `smx_ana_cpp.py`. Verify it exists:
```python
from smx_ana.smx_ana_cpp import sum_distributions_fast_cpp
```
If not, check that you have the latest version of `smx_ana/smx_ana_cpp.py` from the repository.

---

## Data Issues

### Problem: Input file not found

**Symptom**:
```
FileNotFoundError: Data file not found: /path/to/Run9541_SelectionResult.npz
```

**Solutions**:
1. Check `DATA_INPUT_PATH` in `config/paths.py`
2. Verify the file exists: `ls ${DATA_INPUT_PATH}/Run${RUN}_SelectionResult.npz`
3. If using a different naming convention, modify `resolve_input_path()` in `src/MCBased_Fitter.py`

### Problem: NPZ file has wrong keys

**Symptom**:
```
KeyError: 'calib_omilrec_energy'
```

**Solution**: Check what keys your NPZ file has:
```python
import numpy as np
with np.load("your_file.npz") as f:
    print(list(f.keys()))
```

If the energy key is different, you can:
1. Rename the key in your NPZ file
2. Or modify `input_loader.py` → `normalize_event_input()` to accept your key name

### Problem: No finite energy entries

**Symptom**:
```
RuntimeError: No finite energy entries were found in /path/to/file.npz
```

**Solutions**:
- Check for NaN or Inf values in the NPZ file
- Verify the energy field is named correctly (default: `calib_omilrec_energy`)
- For AmC/O16 sources, the code looks for `fast_omilrec_energy` first — verify this is correct for your data

---

## Performance Issues

### Problem: Fitting takes much longer than expected

| Expected | Actual | Likely Cause |
|:--------:|:------:|--------------|
| ~5s (Ge68 Fast) | > 30s | `smx_ana` C++ extension missing — using slow Python fallback for `convolve` |
| ~5s (Ge68 Fast) | > 60s | Very high event count (>100k) |
| ~20s (Cs137) | > 5min | Minuit struggling to converge — check data quality |
| ~80s (Co60) | > 10min | Same — Co60 is the most expensive due to pileup calculations |

**Solution for slow smx_ana**: The Python fallback `convolve` uses a dense matrix multiplication (O(n²) per call). For most cases this is fine, but for very large or complex fits it can be slow. The FastGe68Fitter minimizes this by caching convolutions.

### Problem: Memory usage is high

| Memory | Normal? |
|:------:|:-------:|
| ~100 MB | ✅ Normal for most runs |
| ~350 MB | ✅ Normal for large runs (~22k events as documented) |
| > 2 GB | ❌ Check for memory leak — restart Python process |

---

## Plotting Issues

### Problem: Figures show empty plots

**Symptom**: The fit figure is generated but shows no data points.

**Possible causes**:
- All bins were excluded by `x_limit`
- The fit failed completely (check `chi2` and `valid` in results)
- matplotlib backend issue

**Solution**: 
```bash
export MPLCONFIGDIR=/tmp/mplconfig
export MPLBACKEND=Agg
```

### Problem: "Failed to set cache directories" warning

This is non-critical. The script will still work, but matplotlib cache may not be set:
- matplotlib may produce a warning
- Performance is unaffected

---

## Getting Help

If you encounter an issue not covered here:

1. **Check the fit figure**: `output/*/figures/RUN*.pdf` — visual inspection often reveals the problem
2. **Check the result NPZ**: `center_gauss` for peak position, `chi2`/`ndf` for fit quality
3. **Check the console output**: Was the fit successful? What's the χ²?
4. **Verify inputs**: Is the data file valid? Is the run mapped correctly in `CalibRUN.csv`?

### Problem: Calling low-level functions directly fails

**Symptom**: Import errors when calling `from fitters.Cs137Fitter import Cs137Fitter` or `from src.FastGe68Fitter import run_fast_ge68_fitter` from a plain Python shell.

**Cause**: The project uses imports like `from fitters.xxx import ...` and `from src.xxx import ...`. These require the project root and subdirectories to be on `sys.path`. The `run_pipeline.sh` script handles this, but direct Python calls do not.

**Solution**: Use one of these entry points:
1. **`bash run_pipeline.sh`** — handles all paths automatically
2. Add paths manually when calling directly:
   ```python
   import sys
   sys.path.insert(0, "/path/to/standalone_fitter")
   sys.path.insert(0, "/path/to/standalone_fitter/src")
   sys.path.insert(0, "/path/to/standalone_fitter/fitters")
   sys.path.insert(0, "/path/to/standalone_fitter/smx_ana")
   ```

---

## Getting Help