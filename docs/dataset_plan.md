# Naseej | نسيج — Dataset & ML Plan

## Selected Dataset

**IBM Transactions for Anti-Money Laundering (AML)**
- Source: IBM / Kaggle public release
- Reference: [IBM AML Dataset](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml)
- License: Open for research use

## Starting Point

We will begin with the **Small dataset** variant to keep iteration cycles fast during early development. Once the pipeline is validated end-to-end, we will scale to the Medium and Large variants.

| Variant | Approx. Rows | Notes |
|---------|-------------|-------|
| Small   | ~550 K      | Initial target |
| Medium  | ~5.5 M      | Scale-up phase |
| Large   | ~180 M      | Production-scale |

Raw CSV files should be placed in `ml/data/raw/` after download.

---

## ML Objective

**Transaction-level laundering risk scoring**

For each transaction, produce a continuous risk score in [0, 1] indicating the likelihood that the transaction is part of a money-laundering scheme. The score is derived from both tabular transaction attributes and graph-structural features computed from the transaction network.

---

## Target Label

| Field | Type | Description |
|-------|------|-------------|
| `is_laundering` | binary (0 / 1) | 1 if the transaction is flagged as part of a laundering pattern in the dataset |

Class imbalance is expected (laundering transactions are rare). Evaluation must account for this via precision-recall curves and F1, not raw accuracy.

---

## Initial Feature Set

### Tabular Features (raw columns)

| Feature | Source Column | Notes |
|---------|--------------|-------|
| `amount` | `Amount` | Transaction amount in originating currency |
| `currency` | `Payment Currency` | Currency code of the transaction |
| `payment_type` | `Payment Format` | Wire, SWIFT, ACH, Cheque, etc. |
| `timestamp` | `Timestamp` | Date-time of the transaction |
| `source_account` | `Account` | Originating account ID |
| `target_account` | `Account.1` | Receiving account ID |
| `source_bank` | `From Bank` | Bank ID of the sender |
| `target_bank` | `To Bank` | Bank ID of the receiver |

### Graph / Velocity Features (engineered)

| Feature | Description |
|---------|-------------|
| `transaction_velocity` | Number of transactions from source account in a rolling time window |
| `in_degree` | Number of incoming edges to target account in the transaction graph |
| `out_degree` | Number of outgoing edges from source account |
| `fan_in_count` | Count of distinct senders to a single receiver within a time window |
| `fan_out_count` | Count of distinct receivers from a single sender within a time window |
| `cross_bank_flag` | 1 if source bank != target bank |
| `cycle_indicator` | 1 if the transaction is part of a detected cycle in the graph |

---

## Pipeline Stages

```
ml/data/raw/          <- Downloaded IBM AML CSVs land here
       |
ml/scripts/load_data.py       -> validate, clean, split
       |
ml/data/processed/    <- Cleaned DataFrames (Parquet)
       |
ml/scripts/build_graph_features.py  -> NetworkX / graph construction
       |
ml/data/features/     <- Feature matrices ready for training
       |
ml/scripts/train_baseline.py  -> XGBoost / logistic regression baseline
       |
ml/models/            <- Saved model artifacts (.pkl / .json)
       |
ml/scripts/evaluate_model.py  -> metrics, confusion matrix, PR curve
```

---

## Next Steps

1. Download the IBM AML Small dataset and place CSVs in `ml/data/raw/`.
2. Run `load_data.py` to validate and produce cleaned Parquet files.
3. Run `build_graph_features.py` to compute graph-structural features.
4. Run `train_baseline.py` to fit an initial XGBoost classifier.
5. Run `evaluate_model.py` to benchmark precision, recall, F1, and AUC-PR.
6. Iterate on feature engineering and model selection.
7. Integrate risk scores into the React frontend via a lightweight inference API.
