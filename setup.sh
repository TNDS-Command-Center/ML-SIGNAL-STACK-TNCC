#!/bin/bash
# setup.sh — SignalStack virtual environment setup
# Usage: bash setup.sh

PROJECT_NAME=${1:-tnds-signal-engine}
VENV_DIR="venv_${PROJECT_NAME}"

echo "============================================================"
echo "  SignalStack — Environment Setup"
echo "  Project: $PROJECT_NAME"
echo "  Venv:    $VENV_DIR"
echo "============================================================"

python3 -m venv "$VENV_DIR"

source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "============================================================"
echo "  Setup complete."
echo "  Activate:  source $VENV_DIR/bin/activate"
echo "  Run:       python run_pipeline.py --source sales"
echo "  Run all:   python run_pipeline.py --source all"
echo "============================================================"
