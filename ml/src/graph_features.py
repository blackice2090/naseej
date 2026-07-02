"""Graph + behavior features for AML transactions (Phase 3).

Operates on a DataFrame produced by `preprocessing.build_processed_table` —
columns needed: src_id, dst_id, timestamp, amount, from_bank_id, to_bank_id,
optionally payment_format_code / payment_currency_code / label.

Design choice: stick to pandas groupby + rolling. NetworkX is reserved for the
small per-pattern detectors in `pattern_library.py`. Building a global graph
across millions of edges is intentionally out of scope here — `ml/scripts/build_graph_features.py`
already does the heavy version; this module is the modular, model-ready version.
"""

from __future__ import annotations

import logging
from typing import Iterable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- degree / totals


def degree_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute out/in degree and total sent/received per account, then join
    back so every transaction row carries source_/target_ aggregates.
    """
    df = df.copy()

    out_counts = df.groupby("src_id").size().rename("source_out_degree")
    in_counts = df.groupby("dst_id").size().rename("target_in_degree")
    src_in_counts = df.groupby("dst_id").size().rename("source_in_degree")  # same series, joined on src_id
    dst_out_counts = df.groupby("src_id").size().rename("target_out_degree")

    sent = df.groupby("src_id")["amount"].sum().rename("source_total_sent")
    rcvd = df.groupby("dst_id")["amount"].sum().rename("target_total_received")
    src_rcvd = df.groupby("dst_id")["amount"].sum().rename("source_total_received")
    dst_sent = df.groupby("src_id")["amount"].sum().rename("target_total_sent")

    df = df.join(out_counts, on="src_id")
    df = df.join(in_counts, on="dst_id")
    df = df.join(src_in_counts, on="src_id")    # in-degree of the source account
    df = df.join(dst_out_counts, on="dst_id")   # out-degree of the target account
    df = df.join(sent, on="src_id")
    df = df.join(rcvd, on="dst_id")
    df = df.join(src_rcvd, on="src_id")
    df = df.join(dst_sent, on="dst_id")

    for col in (
        "source_out_degree", "target_in_degree", "source_in_degree", "target_out_degree",
        "source_total_sent", "target_total_received",
        "source_total_received", "target_total_sent",
    ):
        df[col] = df[col].fillna(0)

    return df


# ---------------------------------------------------------------- time-window velocity


def velocity_features(df: pd.DataFrame, windows: Iterable[str] = ("1h", "24h")) -> pd.DataFrame:
    """Rolling counts and amount-sums per source account over time windows.

    Adds columns: velocity_count_<w>, velocity_amount_<w>,
    unique_targets_<w>, unique_sources_<w>.

    Implementation note: pandas' time-based rolling on a groupby produces a
    MultiIndex (group, timestamp) that is easy to lose track of. We sort once,
    use `rolling(... on="timestamp")` so the original RangeIndex is preserved,
    and write the results back positionally.
    """
    if "timestamp" not in df.columns:
        logger.warning("velocity_features: no 'timestamp' column; skipping.")
        return df.copy()

    df = df.sort_values("timestamp").reset_index(drop=True).copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Encode counterparty IDs once for fast nunique-on-codes.
    src_codes = pd.Categorical(df["src_id"].astype("string").fillna("__NA__")).codes
    dst_codes = pd.Categorical(df["dst_id"].astype("string").fillna("__NA__")).codes

    for w in windows:
        suffix = w.replace(" ", "")
        src_grouped = df.groupby("src_id", sort=False, group_keys=False)
        dst_grouped = df.groupby("dst_id", sort=False, group_keys=False)

        df[f"velocity_count_{suffix}"] = (
            src_grouped.rolling(w, on="timestamp")["amount"].count().reset_index(drop=True)
        )
        df[f"velocity_amount_{suffix}"] = (
            src_grouped.rolling(w, on="timestamp")["amount"].sum().reset_index(drop=True)
        )

        # Rolling nunique via a helper column of integer codes + lambda.
        df["_dst_code"] = dst_codes
        df[f"unique_targets_{suffix}"] = (
            src_grouped.rolling(w, on="timestamp")["_dst_code"]
            .apply(lambda s: int(np.unique(s.values).size), raw=False)
            .reset_index(drop=True)
            .fillna(1)
            .astype("int64")
        )
        df["_src_code"] = src_codes
        df[f"unique_sources_{suffix}"] = (
            dst_grouped.rolling(w, on="timestamp")["_src_code"]
            .apply(lambda s: int(np.unique(s.values).size), raw=False)
            .reset_index(drop=True)
            .fillna(1)
            .astype("int64")
        )
        df = df.drop(columns=["_dst_code", "_src_code"])

    return df


# ---------------------------------------------------------------- shape scores


def shape_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Cheap heuristic shape scores derivable from degree / velocity columns.

    fan_in_score: high target_in_degree relative to its out_degree.
    fan_out_score: high source_out_degree relative to its in_degree.
    gather_scatter_score: target gathers many small in-flows and disperses
        them (proxy: target_in_degree * target_out_degree).
    scatter_gather_score: source disperses then re-collects (proxy: source_out_degree * source_in_degree).
    """
    df = df.copy()
    eps = 1.0
    df["fan_in_score"] = df["target_in_degree"] / (df.get("target_out_degree", 0) + eps)
    df["fan_out_score"] = df["source_out_degree"] / (df.get("source_in_degree", 0) + eps)
    df["gather_scatter_score"] = df["target_in_degree"] * df.get("target_out_degree", 0)
    df["scatter_gather_score"] = df["source_out_degree"] * df.get("source_in_degree", 0)
    return df


# ---------------------------------------------------------------- top-level builder


FEATURE_COLUMNS: tuple[str, ...] = (
    "amount",
    "hour_of_day",
    "day_of_week",
    "same_bank_transfer",
    "cross_bank_transfer",
    "from_bank_id",
    "to_bank_id",
    "payment_format_code",
    "payment_currency_code",
    "source_out_degree",
    "source_in_degree",
    "target_out_degree",
    "target_in_degree",
    "source_total_sent",
    "source_total_received",
    "target_total_sent",
    "target_total_received",
    "velocity_count_1h",
    "velocity_amount_1h",
    "unique_targets_24h",
    "unique_sources_24h",
    "fan_in_score",
    "fan_out_score",
    "gather_scatter_score",
    "scatter_gather_score",
)


def build_features(df: pd.DataFrame, *, with_velocity: bool = True) -> pd.DataFrame:
    """Apply degree -> velocity -> shape scores. Returns the full enriched
    DataFrame (including label, src_id, dst_id, timestamp).
    """
    df = degree_features(df)
    if with_velocity:
        df = velocity_features(df, windows=("1h", "24h"))
    df = shape_scores(df)
    return df


def select_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the numeric feature columns present in `df`. Useful before
    handing data to a model.
    """
    keep = [c for c in FEATURE_COLUMNS if c in df.columns]
    out = df[keep].copy()
    return out.fillna(0)


__all__ = [
    "degree_features",
    "velocity_features",
    "shape_scores",
    "build_features",
    "select_feature_matrix",
    "FEATURE_COLUMNS",
]
