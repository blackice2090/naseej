# Run the Phase 4 baseline trainer. Stub until Phase 4.
$ErrorActionPreference = "Stop"
Set-Location -Path (Join-Path $PSScriptRoot "..")
python ml/src/train_baseline.py `
    --input ml/data/processed/transactions_features.csv `
    --output ml/models/baseline_model.joblib
