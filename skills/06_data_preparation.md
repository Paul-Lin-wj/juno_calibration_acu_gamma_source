# Skill: Data Preparation — Converting ROOT Files to NPZ Input

## Description

This skill explains how to prepare input data for the fitter pipeline. The pipeline expects `.npz` files with reconstructed event energy arrays. Use this skill when you need to convert raw JUNO ROOT reconstruction output to the NPZ format the fitters require.

---

## Input Data Format

The fitter expects per-run `.npz` files containing:

### Required Field

| Field | Type | Description |
|-------|------|-------------|
| `calib_omilrec_energy` | float32/64 | Reconstructed energy [MeV] |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `calib_omilrec_x` | float32/64 | Reconstructed x position [mm] |
| `calib_omilrec_y` | float32/64 | Reconstructed y position [mm] |
| `calib_omilrec_z` | float32/64 | Reconstructed z position [mm] |

### Example: Loading a NPZ File

```python
import numpy as np

with np.load("Run9541_SelectionResult.npz") as data:
    energy = data["calib_omilrec_energy"]
    print(f"Events: {len(energy)}")
    print(f"Range: {energy.min():.3f} – {energy.max():.3f} MeV")
    print(f"Mean: {energy.mean():.3f} MeV")
```

---

## Conversion from ROOT: `convert_root_to_npz.py`

The project includes a conversion script at `src/convert_root_to_npz.py`.

### Usage

```bash
# Activate environment
source .venv/bin/activate

# Basic usage
python src/convert_root_to_npz.py \
    --filelist /path/to/filelist.txt \
    --outdir /path/to/output/data

# Specific runs only
python src/convert_root_to_npz.py \
    --filelist /path/to/filelist.txt \
    --outdir /path/to/output/data \
    --runs 9541 9600 9624
```

### Input File List Format

The `--filelist` argument expects a text file with one ROOT file path per line:

```
/junofs/data/run9541/Rec_RUN9541_001.root
/junofs/data/run9541/Rec_RUN9541_002.root
/junofs/data/run9542/Rec_RUN9542_001.root
```

Lines starting with `#` are skipped as comments.

### What the Script Does

1. Reads the file list and groups files by run number (extracted from the path)
2. For each run:
   - Opens all ROOT files via `ROOT.TChain("TRec")`
   - Reads branches: `recx`, `recy`, `recz`, `m_QTEn`
   - Converts to numpy arrays
   - Saves as compressed NPZ
3. Output filename format: `SelectionResult_RUN{N}.npz`

### Requirements for ROOT Conversion

- **PyROOT** (`import ROOT`) — this is NOT included in the project's `requirements.txt`
- ROOT must be installed and accessible in the Python environment
- Typically this means running on a JUNO computing node with CVMFS or JUNO offline software

**Note**: The fitting pipeline itself does NOT require ROOT — only the conversion script does.

---

## Alternative: CSV Input

The fitter also accepts CSV input (for backward compatibility):

```python
# Required column
rec_energy

# Optional columns
x_mm, y_mm, z_mm
```

CSV files can be passed via the `--input` argument to `run_fitter()`:

```python
from src.MCBased_Fitter import run_fitter
outputs = run_fitter(
    input_path="/path/to/data.csv",
    source="Ge68",
    output_fig_dir="output/figures",
    output_res_dir="output/results",
)
```

---

## Full Upstream Data Chain

If you have access to the full JUNO offline data chain, the recommended preparation workflow is:

```
RAW DATA → JUNO Reconstruction (TRec) → ROOT Files
                                              ↓
                           convert_root_to_npz.py
                                              ↓
                         SelectionResult_RUN{N}.npz
                                              ↓
                           Finalcorrection (26B)
                                              ↓
                         Run{N}_SelectionResult.npz
                                              ↓
                           ★ THIS FITTER
```

### Finalcorrection Step

The Finalcorrection applies:
1. **r-bias correction**: Corrects vertex-position-dependent energy bias
2. **Po214 2D spatial correction**: 2D map correction using Po214 events
3. **v2 time stability correction**: Corrects time-dependent variations
4. **Phase absolute energy scale**: Phase-dependent scaling factor (≈0.993–0.997)

These corrections are applied before the event selection step and are embedded in the `calib_omilrec_energy` field of the input NPZ files.

**If your data has NOT been Finalcorrection-corrected**, the fitted peak positions will show systematic offsets relative to the expected values.

---

## Verifying Your Data

Before running the pipeline, verify:

```python
import numpy as np

data = np.load("/path/to/your/Run9541_SelectionResult.npz")

# Check required field exists
assert "calib_omilrec_energy" in data, "Missing energy field"

# Check for finite values
energy = data["calib_omilrec_energy"]
finite = energy[np.isfinite(energy)]
print(f"Total events: {len(energy)}")
print(f"Finite events: {len(finite)}")
print(f"Energy range: {finite.min():.3f} – {finite.max():.3f} MeV")
print(f"Median energy: {np.median(finite):.3f} MeV")

# Quick histogram check
import matplotlib.pyplot as plt
plt.hist(finite, bins=200, range=(0, 3))
plt.xlabel("Energy [MeV]")
plt.ylabel("Counts")
plt.savefig("data_check.png")
print("Saved data_check.png — verify it shows a peak near 0.9 MeV for Ge68")
```