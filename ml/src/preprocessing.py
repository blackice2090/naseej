"""Preprocessing helpers for AMLworld transactions.

Operates on a DataFrame whose columns were already normalized by
`data_loader.normalize_columns`.

All functions are pure-ish: they accept a DataFrame (or scalar) and return a
new DataFrame (or scalar). No side effects.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Iterable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Stable, well-known formats for AMLworld:
TIMESTAMP_FORMATS: tuple[str, ...] = (
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def parse_timestamp(series: pd.Series) -> pd.Series:
    """Parse timestamp strings into pandas datetimes. Tries known formats first
    then falls back to dateutil parsing. Unparseable rows become NaT.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    for fmt in TIMESTAMP_FORMATS:
        out = pd.to_datetime(series, format=fmt, errors="coerce")
        if out.notna().any():
            # If most rows parsed with this format, accept it.
            if out.notna().mean() > 0.95:
                return out
    return pd.to_datetime(series, errors="coerce")


def _stable_codes(series: pd.Series) -> pd.Series:
    """Return integer codes derived from sorted unique values (deterministic)."""
    cats = pd.Categorical(series.astype("string").fillna("__NA__"), ordered=False)
    return pd.Series(cats.codes.astype("int32"), index=series.index)


def encode_payment_type(series: pd.Series) -> pd.Series:
    return _stable_codes(series)


def encode_currency(series: pd.Series) -> pd.Series:
    return _stable_codes(series)


def _hash_id(value: object, *, salt: str) -> str:
    """Deterministic short hash for an opaque account / bank ID."""
    s = f"{salt}|{value}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def create_source_account_id(
    df: pd.DataFrame, *, salt: str = "naseej", out_col: str = "src_id"
) -> pd.DataFrame:
    """Produce a stable surrogate ID for the source account (`from_account`)."""
    df = df.copy()
    if "from_account" not in df.columns:
        raise KeyError("from_account column missing")
    df[out_col] = df["from_account"].map(lambda v: _hash_id(v, salt=salt))
    return df


def create_target_account_id(
    df: pd.DataFrame, *, salt: str = "naseej", out_col: str = "dst_id"
) -> pd.DataFrame:
    df = df.copy()
    if "to_account" not in df.columns:
        raise KeyError("to_account column missing")
    df[out_col] = df["to_account"].map(lambda v: _hash_id(v, salt=salt))
    return df


def create_bank_id(df: pd.DataFrame) -> pd.DataFrame:
    """Add canonical bank id columns (`from_bank_id`, `to_bank_id`) as ints."""
    df = df.copy()
    if "from_bank" in df.columns:
        df["from_bank_id"] = pd.to_numeric(df["from_bank"], errors="coerce").astype("Int64")
    if "to_bank" in df.columns:
        df["to_bank_id"] = pd.to_numeric(df["to_bank"], errors="coerce").astype("Int64")
    return df


def create_label(df: pd.DataFrame, *, out_col: str = "label") -> pd.DataFrame:
    """Materialize the binary supervision label (`is_laundering` → `label`)."""
    df = df.copy()
    if "is_laundering" not in df.columns:
        raise KeyError("is_laundering column missing")
    df[out_col] = pd.to_numeric(df["is_laundering"], errors="coerce").fillna(0).astype("int8")
    return df


# ------------------------------------------------------------------ pipeline


def derive_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    """Cheap, per-row features used by the dataset prep pipeline. Heavier
    graph features land in `graph_features.py` (Phase 3).
    """
    df = df.copy()

    if "timestamp" in df.columns:
        ts = parse_timestamp(df["timestamp"])
        df["timestamp"] = ts
        df["hour_of_day"] = ts.dt.hour.astype("Int16")
        df["day_of_week"] = ts.dt.dayofweek.astype("Int8")

    # Amount: prefer amount_paid then amount_received; fill the other if absent.
    amount = None
    if "amount_paid" in df.columns:
        amount = pd.to_numeric(df["amount_paid"], errors="coerce")
    elif "amount_received" in df.columns:
        amount = pd.to_numeric(df["amount_received"], errors="coerce")
    if amount is not None:
        df["amount"] = amount.fillna(0.0).astype("float64")

    if "payment_format" in df.columns:
        df["payment_format_code"] = encode_payment_type(df["payment_format"])
    if "payment_currency" in df.columns:
        df["payment_currency_code"] = encode_currency(df["payment_currency"])
    elif "receiving_currency" in df.columns:
        df["payment_currency_code"] = encode_currency(df["receiving_currency"])

    df = create_bank_id(df)
    if "from_bank_id" in df.columns and "to_bank_id" in df.columns:
        df["same_bank_transfer"] = (df["from_bank_id"] == df["to_bank_id"]).astype("int8")
        df["cross_bank_transfer"] = (1 - df["same_bank_transfer"]).astype("int8")

    return df


def build_processed_table(
    df: pd.DataFrame,
    *,
    salt: str = "naseej",
    drop_raw_accounts: bool = True,
) -> pd.DataFrame:
    """Full normalize → derive → label pipeline. Outputs a model-ready frame.

    When `drop_raw_accounts=True` (default) the raw account hashes from the
    source data are dropped from the output, keeping only the salted surrogate
    IDs. This is a precaution — AMLworld accounts are already synthetic, but
    enforcing the same posture as production keeps the privacy contract intact.
    """
    df = derive_basic_features(df)
    df = create_source_account_id(df, salt=salt)
    df = create_target_account_id(df, salt=salt)
    df = create_label(df)

    if drop_raw_accounts:
        df = df.drop(columns=[c for c in ("from_account", "to_account") if c in df.columns])

    return df


def select_default_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the canonical columns useful for Phase 3+. Missing columns
    are silently dropped so this works with a degraded schema."""
    candidates: Iterable[str] = (
        "timestamp",
        "src_id",
        "dst_id",
        "from_bank_id",
        "to_bank_id",
        "amount",
        "payment_format_code",
        "payment_currency_code",
        "hour_of_day",
        "day_of_week",
        "same_bank_transfer",
        "cross_bank_transfer",
        "is_laundering",
        "label",
    )
    keep = [c for c in candidates if c in df.columns]
    return df[keep].copy()


def prevalence(df: pd.DataFrame, label_col: str = "label") -> float:
    if label_col not in df.columns:
        return float("nan")
    return float(df[label_col].mean())


__all__ = [
    "parse_timestamp",
    "encode_payment_type",
    "encode_currency",
    "create_source_account_id",
    "create_target_account_id",
    "create_bank_id",
    "create_label",
    "derive_basic_features",
    "build_processed_table",
    "select_default_columns",
    "prevalence",
]


# numpy is imported above only to keep static checkers happy about types; the
# pipeline itself only uses pandas. Re-export quietly.
_ = np
