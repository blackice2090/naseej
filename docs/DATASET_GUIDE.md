# Dataset Guide — AMLworld HI-Small

## Where the data lives

```
ml/data/raw/HI-Small_Trans.csv     ~475 MB  (already present)
ml/data/processed/*.parquet        ~165 MB total
ml/data/features/*.parquet         ~290 MB total
ml/data/samples/                   smaller sampled CSVs (Phase 2 outputs)
```

## Expected columns (AMLworld HI-Small)

| Column | Type | Notes |
|---|---|---|
| Timestamp | string | AMLworld format, e.g. `2022/09/01 00:20` |
| From Bank | int/string | Bank ID of the originating account |
| Account | string | Source account hash |
| To Bank | int/string | Bank ID of the destination account |
| Account.1 | string | Destination account hash |
| Amount Received | float | Currency-denominated value received |
| Receiving Currency | string | e.g. US Dollar, Euro |
| Amount Paid | float | Currency-denominated value paid |
| Payment Currency | string | |
| Payment Format | string | ACH, Cheque, Cash, Credit Card, Wire, Bitcoin, … |
| Is Laundering | 0/1 | Ground-truth label |

`ml/src/data_loader.normalize_columns` (Phase 2) maps these to lowercase snake_case and renames `Account.1` → `to_account` so downstream code never trips on the dot.

## Replacing or sampling the dataset

The HI-Small file is checked in (large). If you want to use a different AMLworld split (HI-Medium, LI-Small, …):

1. Drop the new CSV in `ml/data/raw/`.
2. Adjust the `--input` path when running `prepare_dataset.py` (Phase 2):
   ```bash
   python ml/src/prepare_dataset.py \
       --input ml/data/raw/HI-Medium_Trans.csv \
       --output ml/data/processed/hi_medium_sample.parquet \
       --sample 200000
   ```

## Privacy posture

- Synthetic data only — no real PII.
- All exported pattern shares (Phase 6) are zero-PII by construction; account hashes never leave the local pipeline.
- The HI-Small CSV may be excluded from version control via `.gitignore` if the repo migrates to git (currently this is not a git repository).

## Reproducibility

- Sample size, seed, and split ratio are CLI arguments to `prepare_dataset.py`.
- Phase 4 records the exact dataset hash, row count, and prevalence in `ml/reports/training_summary.md`.
