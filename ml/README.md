# ML Pipeline — نسيج | Naseej

This directory contains two coexisting pipelines:

| Directory     | Status      | Purpose |
|---------------|-------------|---------|
| `ml/scripts/` | Working     | Original pipeline. Produced `ml/models/baseline_model.pkl` (XGBoost, PR-AUC ≈ 0.43, ROC-AUC ≈ 0.99 on the AMLworld HI-Small test split). Kept as the source of truth for the current trained model. |
| `ml/src/`     | In progress | New modular pipeline scaffolded in Phase 1. Real implementations land in Phases 2–6. |

## Data layout

```
ml/
├── data/
│   ├── raw/HI-Small_Trans.csv            # AMLworld HI-Small synthetic AML transactions (~475 MB)
│   ├── processed/{train,val,test}.parquet
│   ├── features/{train,val,test}_features.parquet
│   └── samples/                          # small samples produced by Phase 2 prepare_dataset
├── models/
│   ├── baseline_model.pkl                # legacy artefact — DO NOT overwrite
│   ├── baseline_model.joblib             # produced by Phase 4 — does not exist yet
│   ├── baseline_threshold.json
│   ├── feature_importance.csv
│   └── metrics.json
└── reports/                              # populated by Phases 4/5
    ├── model_metrics.json
    ├── confusion_matrix.json
    ├── feature_importance.json
    ├── cross_bank_results.json
    └── cross_bank_summary.md
```

## CLI entry points (planned)

```bash
# Phase 2 — dataset prep
python ml/src/prepare_dataset.py \
    --input ml/data/raw/HI-Small_Trans.csv \
    --output ml/data/processed/transactions_sample.csv \
    --sample 100000

# Phase 4 — baseline training
python ml/src/train_baseline.py \
    --input ml/data/processed/transactions_features.csv \
    --output ml/models/baseline_model.joblib

# Phase 5 — cross-bank experiment
python ml/src/cross_bank_experiment.py \
    --input ml/data/processed/transactions_features.csv \
    --banks 3
```

All scripts are currently stubs that raise `NotImplementedError` with a phase tag.

## Compatibility contract

- `baseline_model.pkl` and everything else under `ml/scripts/` and `ml/models/` are **read-only** for Phase 1.
- Phase 4 saves to a **new** path: `ml/models/baseline_model.joblib`. The legacy `.pkl` is untouched.
- The backend (`backend/app/services/model_service.py`) loads `baseline_model.joblib` lazily and falls back gracefully when the file is missing.
