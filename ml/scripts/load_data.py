"""
load_data.py
------------
Ingests raw IBM AML CSV files from ml/data/raw/, validates the schema,
applies basic cleaning (type coercion, null removal, deduplication), performs
a stratified train/validation/test split on the `is_laundering` label, and
saves the resulting DataFrames as Parquet files in ml/data/processed/.

Usage:
    python ml/scripts/load_data.py --raw_dir ml/data/raw \
                                   --out_dir ml/data/processed \
                                   --test_size 0.15 \
                                   --val_size 0.15
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "Timestamp",
    "From Bank",
    "Account",
    "To Bank",
    "Account.1",
    "Amount Received",
    "Receiving Currency",
    "Amount Paid",
    "Payment Currency",
    "Payment Format",
    "Is Laundering",
]

RENAME_MAP = {
    "Timestamp": "timestamp",
    "From Bank": "source_bank",
    "Account": "source_account",
    "To Bank": "target_bank",
    "Account.1": "target_account",
    "Amount Received": "amount_received",
    "Receiving Currency": "receiving_currency",
    "Amount Paid": "amount",
    "Payment Currency": "currency",
    "Payment Format": "payment_type",
    "Is Laundering": "is_laundering",
}


def load_raw(raw_dir: Path) -> pd.DataFrame:
    csv_files = sorted(raw_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {raw_dir}")
    log.info("Loading %d CSV file(s) from %s", len(csv_files), raw_dir)
    frames = [pd.read_csv(f, low_memory=False) for f in csv_files]
    return pd.concat(frames, ignore_index=True)


def validate_schema(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected columns: {missing}")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=RENAME_MAP)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["is_laundering"] = df["is_laundering"].astype(int)
    df = df.dropna(subset=["amount", "source_account", "target_account"])
    df = df.drop_duplicates()
    log.info("Clean dataset: %d rows", len(df))
    return df


def split_and_save(df: pd.DataFrame, out_dir: Path, test_size: float, val_size: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    train_val, test = train_test_split(df, test_size=test_size, stratify=df["is_laundering"], random_state=42)
    relative_val = val_size / (1 - test_size)
    train, val = train_test_split(train_val, test_size=relative_val, stratify=train_val["is_laundering"], random_state=42)

    for name, subset in [("train", train), ("val", val), ("test", test)]:
        path = out_dir / f"{name}.parquet"
        subset.to_parquet(path, index=False)
        log.info("Saved %s → %s (%d rows, %d laundering)", name, path, len(subset), subset["is_laundering"].sum())


def main() -> None:
    parser = argparse.ArgumentParser(description="Load and preprocess IBM AML data.")
    parser.add_argument("--raw_dir", type=Path, default=Path("ml/data/raw"))
    parser.add_argument("--out_dir", type=Path, default=Path("ml/data/processed"))
    parser.add_argument("--test_size", type=float, default=0.15)
    parser.add_argument("--val_size", type=float, default=0.15)
    args = parser.parse_args()

    df = load_raw(args.raw_dir)
    validate_schema(df)
    df = clean(df)
    split_and_save(df, args.out_dir, args.test_size, args.val_size)
    log.info("Done.")


if __name__ == "__main__":
    main()
