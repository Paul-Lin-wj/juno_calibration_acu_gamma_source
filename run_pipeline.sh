#!/bin/bash
# =============================================================================
# run_pipeline.sh — One-click run of the entire fitting pipeline
# =============================================================================
# Usage: bash run_pipeline.sh
#
# This script:
# 1. Activates the virtual environment (creates it if missing)
# 2. Runs pipeline/run_fit_all.py
# 3. Outputs results to output/ directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="${SCRIPT_DIR}/.venv"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "[Info] Virtual environment not found. Running setup_env.sh..."
    bash setup_env.sh
fi

# Activate venv
source "${VENV_DIR}/bin/activate"

echo "[Info] Virtual environment activated: $(which python)"
echo "[Info] Starting pipeline..."

# Run the pipeline
python pipeline/run_fit_all.py

echo ""
echo "[Info] Pipeline finished successfully."