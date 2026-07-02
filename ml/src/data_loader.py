"""Dataset ingestion for AMLworld / IBM AML synthetic transactions.

Source CSV columns (HI-Small_Trans.csv):
    Timestamp, From Bank, Account, To Bank, Account.1,
    Amount Received, Receiving Currency, Amount Paid, Payment Currency,
    Payment Format, Is Laundering

After `normalize_columns` they become lowercase snake_case:
    timestamp, from_bank, from_account, to_bank, to_account,
    amount_received, receiving_currency, amount_paid, payment_currency,
    payment_format, is_laundering
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)

# Canonical column mapping. Keys are source headers (case-insensitive), values
# are the canonical snake_case names downstream code uses.
COLUMN_MAP: dict[str, str] = {
    "timestamp": "timestamp",
    "from bank": "from_bank",
    "account": "from_account",
    "to bank": "to_bank",
    "account.1": "to_account",
    "amount received": "amount_received",
    "receiving currency": "receiving_currency",
    "amount paid": "amount_paid",
    "payment currency": "payment_currency",
    "payment format": "payment_format",
    "is laundering": "is_laundering",
}

REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {"timestamp", "from_bank", "to_bank", "from_account", "to_account", "is_laundering"}
)

OPTIONAL_COLUMNS: frozenset[str] = frozenset(
    {
        "amount_received",
        "amount_paid",
        "receiving_currency",
        "payment_currency",
        "payment_format",
    }
)


def load_transactions(path: str | Path, nrows: int | None = None) -> pd.DataFrame:
    """Read a transactions CSV (or parquet) and return a DataFrame.

    Accepts either AMLworld raw headers or already-normalized headers.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Transactions file not found: {p}")
    if p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
        if nrows is not None:
            df = df.head(nrows)
    else:
        df = pd.read_csv(p, nrows=nrows)
    logger.info("Loaded %d rows from %s", len(df), p)
    return df


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename AMLworld headers to canonical snake_case. Idempotent."""
    rename: dict[str, str] = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in COLUMN_MAP:
            rename[col] = COLUMN_MAP[key]
    if rename:
        df = df.rename(columns=rename)
    return df


def validate_schema(df: pd.DataFrame, *, strict: bool = False) -> dict:
    """Check that REQUIRED columns are present. Report missing optionals.

    Returns a small report dict. Raises ValueError when `strict` and any
    required column is absent.
    """
    cols = set(df.columns)
    missing_required = sorted(REQUIRED_COLUMNS - cols)
    missing_optional = sorted(OPTIONAL_COLUMNS - cols)
    report = {
        "row_count": int(len(df)),
        "columns": sorted(cols),
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "ok": not missing_required,
    }
    if missing_required and strict:
        raise ValueError(f"Missing required columns: {missing_required}")
    if missing_optional:
        logger.warning("Optional columns absent (will use safe defaults): %s", missing_optional)
    return report


def sample_transactions(
    df: pd.DataFrame,
    n: int = 100_000,
    *,
    stratify_label: str | None = "is_laundering",
    seed: int = 42,
) -> pd.DataFrame:
    """Return up to `n` rows, preserving label prevalence when possible."""
    if len(df) <= n:
        return df.copy()
    if stratify_label and stratify_label in df.columns:
        positives = df[df[stratify_label] == 1]
        negatives = df[df[stratify_label] != 1]
        prevalence = len(positives) / max(len(df), 1)
        n_pos = max(1, int(round(n * prevalence))) if len(positives) else 0
        n_pos = min(n_pos, len(positives))
        n_neg = min(len(negatives), n - n_pos)
        out = pd.concat(
            [
                positives.sample(n=n_pos, random_state=seed) if n_pos else positives.iloc[0:0],
                negatives.sample(n=n_neg, random_state=seed) if n_neg else negatives.iloc[0:0],
            ],
            ignore_index=False,
        )
        return out.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return df.sample(n=n, random_state=seed).reset_index(drop=True)


def save_processed(df: pd.DataFrame, output_path: str | Path) -> Path:
    """Write the DataFrame to CSV or Parquet (chosen by file extension)."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() == ".parquet":
        df.to_parquet(p, index=False)
    else:
        df.to_csv(p, index=False)
    logger.info("Wrote %d rows -> %s", len(df), p)
    return p


def iter_chunks(
    path: str | Path, chunksize: int = 250_000
) -> Iterable[pd.DataFrame]:
    """Yield normalized chunks for very large CSVs without loading everything."""
    for chunk in pd.read_csv(path, chunksize=chunksize):
        yield normalize_columns(chunk)
