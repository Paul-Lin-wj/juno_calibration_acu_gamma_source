"""
Centralized path configuration for the standalone fitter pipeline.

Only this file needs editing when the environment changes.
"""
from pathlib import Path

# ============================================================
# Project root (auto-detected from this file's location)
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ============================================================
# Input data path — edit this to point to your data directory
# The directory should contain Run{N}_SelectionResult.npz files
# ============================================================
DATA_INPUT_PATH = "/datafs/users/lin/workplace/energy_reco/ENL_agent/standalone_esd2npz/output/latest/results/selection_npz"

# ============================================================
# Output directories (relative to PROJECT_ROOT)
# ============================================================
OUTPUT_DIR       = PROJECT_ROOT / "output"
OUTPUT_RES_DIR   = OUTPUT_DIR / "results"
OUTPUT_FIG_DIR   = OUTPUT_DIR / "figures"

# ============================================================
# Source definitions: (name, run_id, e_true, fitter_type)
#   fitter_type = "fast" | "classic"
# ============================================================
SOURCES = [
    ("Ge68",  12370, 0.8845, "fast"),   # 2025-12-17, Z=0
    ("Cs137", 12295, 0.662,  "fast"),   # 2025-12-16, Z=0
    ("Mn54",  12247, 0.835,  "fast"),   # 2025-12-15, Z=0
    ("Co60",  12216, 2.506,  "fast"),   # 2025-12-15, Z=0
    ("K40",   9632,  1.461,  "fast"),   # 2025-08-25, Z=0（唯一K40 run）
]

# ============================================================
# Run info CSV (run -> source type mapping)
# ============================================================
RUN_INFO_CSV = PROJECT_ROOT / "CalibRUN.csv"

# ============================================================
# Plot style: ENL reference resolution parameters
# ============================================================
A_JUNO_REF = 3.309
B_JUNO_REF = 1.28
C_JUNO_REF = 0.0

# Color and marker scheme (ENL style)
COLORS = {
    "Ge68":  "#1f77b4",
    "Cs137": "#ff7f0e",
    "Mn54":  "#d62728",
    "Co60":  "#2ca02c",
    "K40":   "#9467bd",
}
MARKERS = {
    "Ge68":  "o",
    "Cs137": "s",
    "Mn54":  "^",
    "Co60":  "D",
    "K40":   "v",
}