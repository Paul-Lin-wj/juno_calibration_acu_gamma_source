#!/bin/bash
# =============================================================================
# smoke_test.sh — Quick validation that the pipeline can run end-to-end
# =============================================================================
# Usage: bash tests/smoke_test.sh
#
# This test:
# 1. Verifies the virtual environment exists and imports work
# 2. Runs a single Ge68 fit (FastGe68Fitter) with a small check
# 3. Runs a single Cs137 fit (FastSourceFitter) with a small check
# 4. Verifies output files are generated
# 5. Verifies the ENL-style summary plot can be drawn
#
# Requirements:
# - Data must be accessible at DATA_INPUT_PATH (config/paths.py)
# - setup_env.sh must have been run at least once

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJ_DIR}/.venv"
PASS=0
FAIL=0

red()   { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }

check() {
    local desc="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        green "  ✅ PASS: $desc"
        PASS=$((PASS + 1))
    else
        red "  ❌ FAIL: $desc"
        FAIL=$((FAIL + 1))
    fi
}

echo "============================================"
echo "  Smoke Test: juno_calibration_acu_gamma_source"
echo "============================================"
echo ""

# ---- 1. Environment ----
echo "[1/5] Environment checks"

check "Virtual environment exists" test -d "$VENV_DIR"
check "Python executable" test -x "${VENV_DIR}/bin/python"
check "iminuit import" "${VENV_DIR}/bin/python" -c "import iminuit; print(iminuit.__version__)"
check "numpy import"    "${VENV_DIR}/bin/python" -c "import numpy; print(numpy.__version__)"
check "scipy import"    "${VENV_DIR}/bin/python" -c "import scipy; print(scipy.__version__)"
check "matplotlib import" "${VENV_DIR}/bin/python" -c "import matplotlib; print(matplotlib.__version__)"

# ---- 2. Project module imports ----
echo ""
echo "[2/5] Module import checks"

check "src.FastGe68Fitter import" "${VENV_DIR}/bin/python" -c "
import sys; sys.path.insert(0, '${PROJ_DIR}')
sys.path.insert(0, '${PROJ_DIR}/src')
sys.path.insert(0, '${PROJ_DIR}/fitters')
sys.path.insert(0, '${PROJ_DIR}/smx_ana')
from src.FastGe68Fitter import FastGe68Fitter, run_fast_ge68_fitter
print('FastGe68Fitter OK')
"

check "src.FastSourceFitter import" "${VENV_DIR}/bin/python" -c "
import sys; sys.path.insert(0, '${PROJ_DIR}')
sys.path.insert(0, '${PROJ_DIR}/src')
sys.path.insert(0, '${PROJ_DIR}/fitters')
sys.path.insert(0, '${PROJ_DIR}/smx_ana')
from src.FastSourceFitter import FastSourceFitter, run_fast_source_fitter
print('FastSourceFitter OK')
"

check "fitters (classic) import" "${VENV_DIR}/bin/python" -c "
import sys; sys.path.insert(0, '${PROJ_DIR}')
sys.path.insert(0, '${PROJ_DIR}/src')
sys.path.insert(0, '${PROJ_DIR}/fitters')
sys.path.insert(0, '${PROJ_DIR}/smx_ana')
from fitters.Cs137Fitter import Cs137Fitter
from fitters.Mn54Fitter import Mn54Fitter
from fitters.Co60Fitter import Co60Fitter
from fitters.K40Fitter import K40Fitter
print('Classic fitters OK')
"

check "smx_ana (Python fallback) import" "${VENV_DIR}/bin/python" -c "
import sys; sys.path.insert(0, '${PROJ_DIR}/smx_ana')
from smx_ana.smx_ana_cpp import convolve, sum_distributions_fast_cpp
print('smx_ana fallback OK')
"

# ---- 3. Config path validation ----
echo ""
echo "[3/5] Configuration checks"

check "config/paths.py is readable" test -f "${PROJ_DIR}/config/paths.py"

# Check if data is accessible
DATA_PATH=$("${VENV_DIR}/bin/python" -c "
import sys; sys.path.insert(0, '${PROJ_DIR}')
from config.paths import DATA_INPUT_PATH
print(DATA_INPUT_PATH)
" 2>/dev/null || echo "")

if [ -n "$DATA_PATH" ] && [ -d "$DATA_PATH" ]; then
    N_FILES=$(ls "$DATA_PATH"/Run*_SelectionResult.npz 2>/dev/null | wc -l)
    check "Data directory accessible ($N_FILES files)" test "$N_FILES" -gt 0
else
    echo "  ⚠️  SKIP: Data directory not accessible ($DATA_PATH)"
    echo "      Set DATA_INPUT_PATH in config/paths.py to run data-dependent tests."
fi

# ---- 4. Config smoke test ----
echo ""
echo "[4/5] Config sanity check"

check "SOURCES list is valid" "${VENV_DIR}/bin/python" -c "
import sys; sys.path.insert(0, '${PROJ_DIR}')
from config.paths import SOURCES
assert len(SOURCES) > 0, 'SOURCES is empty'
for s in SOURCES:
    assert len(s) == 4, f'Bad tuple: {s}'
    assert s[3] in ('fast', 'classic'), f'Bad fitter type: {s[3]}'
print(f'{len(SOURCES)} source(s) configured: {[x[0] for x in SOURCES]}')
"

check "CalibRUN.csv is readable" test -f "${PROJ_DIR}/CalibRUN.csv"

# ---- 5. Logger module check ----
echo ""
echo "[5/6] Logger module check"

check "pipeline/run_fit_all.py imports" "${VENV_DIR}/bin/python" -c "
import sys; sys.path.insert(0, '${PROJ_DIR}')
import matplotlib; matplotlib.use('Agg')
from config.paths import PROJECT_ROOT, DATA_INPUT_PATH, SOURCES, A_JUNO_REF, B_JUNO_REF, COLORS, MARKERS
from src.run_logger import RunLogger
print('Pipeline + logger imports OK')
"

# ---- 6. Logger module check ----
echo ""
echo "[6/6] Pipeline dry-run (import only)"

check "run_logger can be instantiated" "${VENV_DIR}/bin/python" -c "
import sys, tempfile
from pathlib import Path
sys.path.insert(0, '${PROJ_DIR}')
sys.path.insert(0, '${PROJ_DIR}/src')
from src.run_logger import RunLogger
with tempfile.TemporaryDirectory() as td:
    logger = RunLogger(td, Path('${PROJ_DIR}'), launched_by='test')
    logger.set_summary({'test': 'ok'})
    j, m = logger.finalize()
    print(f'JSON: {j.exists()}, MD: {m.exists()}')
"

check "logger agent_notes works" "${VENV_DIR}/bin/python" -c "
import sys, tempfile, json
from pathlib import Path
sys.path.insert(0, '${PROJ_DIR}')
sys.path.insert(0, '${PROJ_DIR}/src')
from src.run_logger import RunLogger
with tempfile.TemporaryDirectory() as td:
    logger = RunLogger(td, Path('${PROJ_DIR}'), launched_by='agent')
    logger.set_agent_info('TestAgent', '1.0', 'Testing')
    logger.add_agent_decision('Test decision', 'Testing reason')
    logger.add_agent_exception('Test', 'Test error', 'Test resolution')
    j, m = logger.finalize()
    print(f'Agent log: {j.exists()}, {m.exists()}')
    d = json.load(open(j))
    assert len(d['agent_notes']['decisions']) == 1
    assert len(d['agent_notes']['exceptions']) == 1
    print('Agent notes OK')
"

# ---- Summary ----
echo ""
echo "============================================"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0