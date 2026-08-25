#!/bin/bash
# =============================================================================
# setup_env.sh — Create Python virtual environment and install dependencies
# =============================================================================
# Usage: bash setup_env.sh
# This creates a .venv directory inside the project root.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="${SCRIPT_DIR}/.venv"

if [ -d "$VENV_DIR" ]; then
    echo "[Info] Virtual environment already exists at ${VENV_DIR}"
    echo "[Info] To recreate, remove it first: rm -rf ${VENV_DIR}"
else
    echo "[Info] Creating virtual environment at ${VENV_DIR}"
    python3 -m venv "$VENV_DIR"
fi

echo "[Info] Installing dependencies..."
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet -r requirements.txt

echo "[Info] Done. Virtual environment is ready."
echo ""
echo "To activate: source ${VENV_DIR}/bin/activate"
echo "To run pipeline: bash run_pipeline.sh"