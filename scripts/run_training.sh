#!/usr/bin/env bash
# Run the Phase 4 baseline trainer. Stub until Phase 4.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python ml/src/train_baseline.py \
    --input ml/data/processed/transactions_features.csv \
    --output ml/models/baseline_model.joblib
