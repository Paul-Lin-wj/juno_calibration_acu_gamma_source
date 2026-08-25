# Skill: Configuration — Paths, Sources, and Run Mapping

## Description

This skill explains how to configure the project for your environment and data. Use this skill when adapting the project to a new data location, adding new runs, or changing which sources to fit.

---

## Configuration File

The primary configuration file is:

```
config/paths.py
```

For the **default 5 sources with standard NPZ naming**, this is the **only file you need to edit** when moving to a new environment.

### When you need to edit other files

| Scenario | What to edit |
|----------|-------------|
| Different run numbers or sources | `SOURCES` list in `config/paths.py` |
| Different NPZ file naming convention | `resolve_input_path()` in `src/MCBased_Fitter.py` |
| Adding a new source type | New fitter in `fitters/` + import in `src/MCBased_Fitter.py` |
| ROOT→NPZ conversion | `src/convert_root_to_npz.py` (requires ROOT environment) |
| O16/AmC source | Not yet integrated into the default pipeline (see `01_project_overview.md`)

---

## Configuring the Data Path

### `DATA_INPUT_PATH`

Edit `config/paths.py`:

```python
DATA_INPUT_PATH = "/path/to/your/data/directory"
```

This directory should contain `Run{N}_SelectionResult.npz` files. Each NPZ file contains:
- `calib_omilrec_energy` — reconstructed energy array (required)
- `calib_omilrec_x/y/z` — reconstructed vertex positions (optional)

### File Naming Convention

The pipeline looks for files named:

```
{DATA_INPUT_PATH}/Run{run_id}_SelectionResult.npz
```

For example, with `run_id=9541` and `DATA_INPUT_PATH=/data/npz/`:
```
/data/npz/Run9541_SelectionResult.npz
```

### Input Data Sources

The data should be the output of the JUNO calibration selection chain:
1. **Gamma sources** (Ge68, Cs137, Mn54, Co60, K40): from `singles_selection`
2. **AmC/O16 sources**: from `correlate_selection` (requires additional path configuration)

---

## Configuring Sources

### The `SOURCES` List

In `config/paths.py`, the `SOURCES` list defines which runs to fit:

```python
SOURCES = [
    # (name, run_id, e_true_MeV, fitter_type)
    ("Ge68",  9541, 0.8845, "fast"),
    ("Cs137", 9600, 0.662,  "classic"),
    ("Mn54",  9624, 0.835,  "classic"),
    ("Co60",  9591, 2.506,  "classic"),
    ("K40",   9632, 1.461,  "classic"),
]
```

Each tuple contains:

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Source name (used in output filenames and plots) |
| `run_id` | int | JUNO run number |
| `e_true` | float | True energy of the calibration source (MeV) |
| `fitter_type` | str | `"fast"` (Ge68 only) or `"classic"` (all sources) |

### Adding a New Run

```python
# Add another Ge68 run at a different position
SOURCES = [
    ("Ge68_center",  9541, 0.8845, "fast"),
    ("Ge68_top",     9497, 0.8845, "fast"),    # Z = +18.4 m
    ("Ge68_bottom",  9577, 0.8845, "fast"),    # Z = -17.3 m
    ("Cs137",       9600, 0.662,  "classic"),
    # ...
]
```

### Fitter Type Selection

| fitter_type | Available For | Speed | Notes |
|-------------|---------------|:-----:|-------|
| `"fast"` | **Ge68 only** | ~5s | Caches MC template convolutions |
| `"classic"` | All sources | ~15-90s | Re-computes convolutions every iteration |

---

## Configuring the Run-to-Source Mapping

### `CalibRUN.csv`

This CSV maps run numbers to source type and physical position:

```csv
RUN,Date,X[m],Y[m],Z[m],Source,R[m]
9541,2025-08-24,0.0,0.0,0.0,Ge68,0.0
9497,2025-08-24,0.0,0.0,18.4,Ge68,18.4
9600,2025-08-24,0.0,0.0,0.0,Cs137,0.0
```

| Column | Description |
|--------|-------------|
| `RUN` | Run number (integer) |
| `Date` | Acquisition date (informational) |
| `X[m]`, `Y[m]`, `Z[m]` | Source position in meters |
| `Source` | Source type (Ge68, Cs137, Mn54, Co60, K40, AmC100, ...) |
| `R[m]` | Radial distance from detector center |

### How It's Used

The pipeline uses `CalibRUN.csv` in two places:
1. **Source identification**: When a run number is provided without explicit source
2. **Summary plots**: `plot_fit_summary.py` reads Z positions for z-scan plots

### Updating the CSV

If you have a new set of runs:
1. Add rows to `CalibRUN.csv`
2. Add corresponding entries to `SOURCES` in `config/paths.py`

---

## Configuring Output Paths

Output is always written to timestamped directories:

```
output/{YYYYMMDD_HHMMSS}/
├── results/          # Fit result NPZ files
├── figures/          # Per-source fit figures
├── enl_style_resolution.png
└── enl_style_resolution.pdf
```

The timestamp is generated automatically — no configuration needed.

---

## Configuring Plot Style

### Colors and Markers

In `config/paths.py`:

```python
COLORS = {
    "Ge68":  "#1f77b4",  # Blue
    "Cs137": "#ff7f0e",  # Orange
    "Mn54":  "#d62728",  # Red
    "Co60":  "#2ca02c",  # Green
    "K40":   "#9467bd",  # Purple
}
MARKERS = {
    "Ge68":  "o",        # Circle
    "Cs137": "s",        # Square
    "Mn54":  "^",        # Triangle up
    "Co60":  "D",        # Diamond
    "K40":   "v",        # Triangle down
}
```

### JUNO Reference Resolution Parameters

```python
A_JUNO_REF = 3.309   # Stochastic term
B_JUNO_REF = 1.28    # Constant term
C_JUNO_REF = 0.0     # Noise term
```

These are displayed as a dashed reference curve on the summary plot.

---

## Quick Reference: Typical Configuration Changes

| Task | What to Edit |
|------|-------------|
| Use different data directory | `DATA_INPUT_PATH` in `config/paths.py` |
| Fit different runs | `SOURCES` list in `config/paths.py` |
| Add new run to CSV | `CalibRUN.csv` |
| Switch source to fast/classic | `fitter_type` in SOURCES tuples |
| Add a new source type | Create fitter in `fitters/` + import in `src/MCBased_Fitter.py` |
| Change plot colors | `COLORS` dict in `config/paths.py` |