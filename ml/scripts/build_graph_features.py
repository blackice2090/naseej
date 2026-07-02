"""
build_graph_features.py  (vectorized rewrite)
----------------------------------------------
Engineers transaction-level and account-level features for AML detection.
Replaces the original row-by-row iteration with vectorized Pandas operations:

  Cumulative features   O(n)       groupby cumcount / cumsum
  Velocity features     O(n log n) cumulative stats + merge_asof lookback
  Mule pattern features O(n)       derived arithmetic on the above

Leakage prevention
------------------
All features are computed using PAST transactions only:
  - cumcount() gives the 0-indexed position within a group (= count before current row)
  - cumsum() - current_value gives sum of all prior rows
  - Velocity windows use lookback time = t - window_td, so the window is
    (t - window_td, t) — strictly before the current row's timestamp
  - Validation / test splits include train (and train+val) as historical context,
    prepended before computing features, then stripped from the output

Usage
-----
  # Quick sanity check on 1 percent sample
  python ml/scripts/build_graph_features.py --sample-frac 0.01

  # Full run
  python ml/scripts/build_graph_features.py

  # Custom windows
  python ml/scripts/build_graph_features.py --window-short 2H --window-long 48H
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

LABEL_COL = "is_laundering"
ENCODE_COLS = ["currency", "payment_type", "source_bank", "target_bank", "source_account", "target_account"]

OUTPUT_FEATURE_COLS = [
    # ── base ──────────────────────────────────────────────────────────────────
    "amount",
    "currency_enc", "payment_type_enc",
    "source_bank_enc", "target_bank_enc",
    "source_account_enc", "target_account_enc",
    "is_cross_bank", "cross_bank_flow_flag",
    "hour", "day_of_week", "is_weekend",
    # ── cumulative (total before current row) ─────────────────────────────────
    "source_out_tx_count_total_before",
    "source_out_amount_sum_total_before",
    "source_unique_targets_total_before",
    "target_in_tx_count_total_before",
    "target_in_amount_sum_total_before",
    "target_unique_sources_total_before",
    "account_pair_tx_count_before",
    "account_pair_amount_sum_before",
    # ── velocity (rolling window, past only) ──────────────────────────────────
    "source_out_tx_count_1h",
    "source_out_amount_sum_1h",
    "target_in_tx_count_1h",
    "target_in_amount_sum_1h",
    "source_out_tx_count_24h",
    "source_out_amount_sum_24h",
    "target_in_tx_count_24h",
    "target_in_amount_sum_24h",
    # ── mule pattern ──────────────────────────────────────────────────────────
    "fan_in_score",
    "fan_out_score",
    "sweep_ratio",
    "rapid_movement_flag",
]


# ─────────────────────────────────────────────────────────────────────────────
# I/O helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_parquet(path: Path, sample_frac: float | None = None) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if sample_frac is not None:
        df = df.sample(frac=sample_frac, random_state=42).reset_index(drop=True)
        log.info("  Sampled %.1f%% → %d rows from %s", sample_frac * 100, len(df), path.name)
    else:
        log.info("  Loaded %d rows from %s", len(df), path.name)
    return df


def optimise_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes("int64").columns:
        df[col] = df[col].astype(np.int32)
    for col in df.select_dtypes("float64").columns:
        df[col] = df[col].astype(np.float32)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Categorical encoding
# ─────────────────────────────────────────────────────────────────────────────

def fit_encoders(df: pd.DataFrame) -> dict[str, LabelEncoder]:
    encoders: dict[str, LabelEncoder] = {}
    for col in ENCODE_COLS:
        le = LabelEncoder()
        le.fit(df[col].astype(str).fillna("__null__"))
        encoders[col] = le
    log.info("Encoders fitted on %d training rows.", len(df))
    return encoders


def apply_encoders(df: pd.DataFrame, encoders: dict[str, LabelEncoder]) -> pd.DataFrame:
    df = df.copy()
    for col, le in encoders.items():
        vals = df[col].astype(str).fillna("__null__")
        known = vals.isin(le.classes_)
        enc = np.full(len(df), -1, dtype=np.int32)
        enc[known.to_numpy()] = le.transform(vals[known]).astype(np.int32)
        df[f"{col}_enc"] = enc
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Base features
# ─────────────────────────────────────────────────────────────────────────────

def add_base_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    ts = pd.to_datetime(df["timestamp"])
    df["hour"]        = ts.dt.hour.astype(np.int8)
    df["day_of_week"] = ts.dt.dayofweek.astype(np.int8)
    df["is_weekend"]  = (df["day_of_week"] >= 5).astype(np.int8)
    flag = (df["source_bank"].astype(str) != df["target_bank"].astype(str)).astype(np.int8)
    df["is_cross_bank"]       = flag
    df["cross_bank_flow_flag"] = flag
    df["amount"] = df["amount"].astype(np.float32)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Cumulative features  (O(n), vectorized groupby)
# ─────────────────────────────────────────────────────────────────────────────

def add_cumulative_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    All values reflect activity STRICTLY BEFORE the current row.
    Requires df to be sorted by timestamp before calling.

    Unique-count approximation (source_unique_targets, target_unique_sources):
      Mark the first global occurrence of each (source, target) pair using
      duplicated(..., keep='first'), then cumsum within the source/target group.
      This correctly counts distinct counterparties seen up to each row in O(n).
    """
    df = df.copy()

    # ── source outgoing ───────────────────────────────────────────────────────
    df["source_out_tx_count_total_before"] = (
        df.groupby("source_account").cumcount().astype(np.int32)
    )
    df["source_out_amount_sum_total_before"] = (
        df.groupby("source_account")["amount"].cumsum() - df["amount"]
    ).astype(np.float32)

    # unique targets per source (first-occurrence trick)
    df["__fp"] = (~df.duplicated(["source_account", "target_account"], keep="first")).astype(np.int32)
    df["__fp_cs"] = df.groupby("source_account")["__fp"].cumsum()
    df["source_unique_targets_total_before"] = (df["__fp_cs"] - df["__fp"]).astype(np.int32)

    # ── target incoming ───────────────────────────────────────────────────────
    df["target_in_tx_count_total_before"] = (
        df.groupby("target_account").cumcount().astype(np.int32)
    )
    df["target_in_amount_sum_total_before"] = (
        df.groupby("target_account")["amount"].cumsum() - df["amount"]
    ).astype(np.float32)

    # unique sources per target
    df["__fs"] = (~df.duplicated(["target_account", "source_account"], keep="first")).astype(np.int32)
    df["__fs_cs"] = df.groupby("target_account")["__fs"].cumsum()
    df["target_unique_sources_total_before"] = (df["__fs_cs"] - df["__fs"]).astype(np.int32)

    # ── account pair (source → target) ────────────────────────────────────────
    df["account_pair_tx_count_before"] = (
        df.groupby(["source_account", "target_account"]).cumcount().astype(np.int32)
    )
    df["account_pair_amount_sum_before"] = (
        df.groupby(["source_account", "target_account"])["amount"].cumsum() - df["amount"]
    ).astype(np.float32)

    df.drop(columns=["__fp", "__fp_cs", "__fs", "__fs_cs"], inplace=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Velocity features  (O(n log n), merge_asof lookback)
# ─────────────────────────────────────────────────────────────────────────────

def _rolling_count_sum(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    window_td: pd.Timedelta,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Vectorized rolling count and sum using cumulative stats + merge_asof.

    Algorithm
    ---------
    1. Compute cumulative count/sum BEFORE each row (exclusive of current row).
    2. Build a reference table: (group, timestamp) → cumulative stats up to that row.
    3. For each row, compute lookback_time = timestamp - window_td.
    4. merge_asof(lookback_times, reference, direction='backward') to find the
       cumulative state at lookback_time within the same group.
    5. Rolling value = current_cumulative - state_at_lookback.

    Window semantics: (t - window_td, t) — open on both sides, meaning no row
    at exactly t - window_td is counted. Rows at exactly t (current row) are
    excluded by using cumulative stats BEFORE the current row.

    Returns
    -------
    (count_array, sum_array) in the same row order as the input df.
    df must be sorted by timestamp and have a clean RangeIndex before calling.
    """
    n = len(df)
    pos = np.arange(n)

    # Cumulative stats BEFORE each row (0 for the first row in each group)
    cum_n = df.groupby(group_col).cumcount().to_numpy(dtype=np.int64)
    cum_s = (df.groupby(group_col)[value_col].cumsum() - df[value_col]).to_numpy(dtype=np.float64)

    # Reference: cumulative state UP TO AND INCLUDING each row
    ref = pd.DataFrame({
        group_col:   df[group_col].to_numpy(),
        "ts":        df["timestamp"].to_numpy(),
        "_rn":       cum_n + 1,
        "_rs":       cum_s + df[value_col].to_numpy(dtype=np.float64),
    }).sort_values("ts").reset_index(drop=True)

    # Lookback table: for each row we query at ts - window
    lb = pd.DataFrame({
        group_col: df[group_col].to_numpy(),
        "lb_ts":   (df["timestamp"] - window_td).to_numpy(),
        "cur_n":   cum_n,
        "cur_s":   cum_s,
        "pos":     pos,
    }).sort_values("lb_ts").reset_index(drop=True)

    # For each lb_ts, find the last reference row with ts <= lb_ts, per group
    merged = pd.merge_asof(
        lb,
        ref.rename(columns={"ts": "lb_ts", "_rn": "lb_n", "_rs": "lb_s"}),
        on="lb_ts",
        by=group_col,
        direction="backward",
    )

    counts = (merged["cur_n"] - merged["lb_n"].fillna(0)).clip(lower=0).astype(np.int32)
    sums   = (merged["cur_s"] - merged["lb_s"].fillna(0)).clip(lower=0).astype(np.float32)

    # Restore original row order using saved positions
    order = merged["pos"].to_numpy()
    out_counts = np.empty(n, dtype=np.int32)
    out_sums   = np.empty(n, dtype=np.float32)
    out_counts[order] = counts.to_numpy()
    out_sums[order]   = sums.to_numpy()

    return out_counts, out_sums


def add_velocity_features(
    df: pd.DataFrame,
    window_short: pd.Timedelta,
    window_long: pd.Timedelta,
) -> pd.DataFrame:
    # df must be sorted by timestamp with a clean RangeIndex
    short_label = f"{int(window_short.total_seconds() // 3600)}h"
    long_label  = f"{int(window_long.total_seconds() // 3600)}h"

    log.info("  velocity: source outgoing %s ...", short_label)
    c, s = _rolling_count_sum(df, "source_account", "amount", window_short)
    df[f"source_out_tx_count_{short_label}"]    = c
    df[f"source_out_amount_sum_{short_label}"]  = s

    log.info("  velocity: source outgoing %s ...", long_label)
    c, s = _rolling_count_sum(df, "source_account", "amount", window_long)
    df[f"source_out_tx_count_{long_label}"]    = c
    df[f"source_out_amount_sum_{long_label}"]  = s

    log.info("  velocity: target incoming %s ...", short_label)
    c, s = _rolling_count_sum(df, "target_account", "amount", window_short)
    df[f"target_in_tx_count_{short_label}"]    = c
    df[f"target_in_amount_sum_{short_label}"]  = s

    log.info("  velocity: target incoming %s ...", long_label)
    c, s = _rolling_count_sum(df, "target_account", "amount", window_long)
    df[f"target_in_tx_count_{long_label}"]    = c
    df[f"target_in_amount_sum_{long_label}"]  = s

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Mule pattern features  (O(n), derived arithmetic)
# ─────────────────────────────────────────────────────────────────────────────

def add_mule_features(df: pd.DataFrame, short_label: str, long_label: str) -> pd.DataFrame:
    """
    fan_in_score
        Rolling count of incoming transactions to target_account in the long window.
        This is an upper bound on the true unique-sender count; exact rolling-window
        unique counts require an O(n * window) self-join which is impractical at scale.
        The count is highly correlated with the unique count and sufficient for
        gradient-boosted models which learn monotone transformations.

    fan_out_score
        Rolling count of outgoing transactions from source_account in the long window.
        Same approximation rationale as fan_in_score.

    sweep_ratio
        current_amount / (source's historical average outgoing amount + ε).
        Detects unusually large transactions relative to the source's baseline.
        High values suggest a "sweep" event where an account drains its balance.

    rapid_movement_flag
        1 if the source account sent ≥ 2 transactions in the short window OR
        sent ≥ 3 transactions in the long window with above-average total amounts.
        Captures high-frequency forwarding behaviour typical of mule accounts.
    """
    df = df.copy()

    src_count_long = df[f"source_out_tx_count_{long_label}"]
    tgt_count_long = df[f"target_in_tx_count_{long_label}"]
    src_count_short = df[f"source_out_tx_count_{short_label}"]
    src_sum_long    = df[f"source_out_amount_sum_{long_label}"]

    df["fan_in_score"]  = tgt_count_long.astype(np.int32)
    df["fan_out_score"] = src_count_long.astype(np.int32)

    avg_out = (
        df["source_out_amount_sum_total_before"]
        / (df["source_out_tx_count_total_before"] + 1)
    )
    df["sweep_ratio"] = (df["amount"] / (avg_out + 1e-6)).clip(0, 1000).astype(np.float32)

    df["rapid_movement_flag"] = (
        (src_count_short >= 2)
        | ((src_count_long >= 3) & (src_sum_long > avg_out * 2))
    ).astype(np.int8)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Per-split processing
# ─────────────────────────────────────────────────────────────────────────────

def process_split(
    target_df: pd.DataFrame,
    history_df: pd.DataFrame | None,
    encoders: dict[str, LabelEncoder],
    window_short: pd.Timedelta,
    window_long: pd.Timedelta,
    split_name: str,
) -> pd.DataFrame:
    """
    1. Prepend history rows (marked _tgt=0) to the target split (marked _tgt=1).
    2. Sort the combined frame by timestamp.
    3. Compute all features on the combined frame — history rows provide prior
       context so that the first target row already has accurate cumulative stats.
    4. Filter to target rows only before returning, preventing any history data
       from appearing in the output files.
    """
    short_label = f"{int(window_short.total_seconds() // 3600)}h"
    long_label  = f"{int(window_long.total_seconds() // 3600)}h"

    if history_df is not None:
        log.info("  Prepending %d history rows to %s ...", len(history_df), split_name)
        combined = pd.concat(
            [history_df.assign(__tgt=0), target_df.assign(__tgt=1)],
            ignore_index=True,
        )
    else:
        combined = target_df.assign(__tgt=1)

    combined = combined.sort_values("timestamp").reset_index(drop=True)
    log.info("  Combined: %d rows (history + target)", len(combined))

    log.info("  Encoding categoricals...")
    combined = apply_encoders(combined, encoders)

    log.info("  Base features...")
    combined = add_base_features(combined)

    log.info("  Cumulative features...")
    combined = add_cumulative_features(combined)

    log.info("  Velocity features...")
    combined = add_velocity_features(combined, window_short, window_long)

    log.info("  Mule pattern features...")
    combined = add_mule_features(combined, short_label, long_label)

    result = (
        combined[combined["__tgt"] == 1]
        .drop(columns=["__tgt"])
        .reset_index(drop=True)
    )
    log.info("  %s output: %d rows", split_name, len(result))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Summary report
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(df: pd.DataFrame, split_name: str, out_path: Path, feature_cols: list[str]) -> None:
    missing = {c: int(df[c].isnull().sum()) for c in feature_cols if df[c].isnull().any()}
    mem_mb  = df.memory_usage(deep=True).sum() / 1024 / 1024
    launder = int(df[LABEL_COL].sum()) if LABEL_COL in df.columns else -1
    label_pct = (launder / len(df) * 100) if launder >= 0 else float("nan")

    print(f"\n{'=' * 60}")
    print(f"  Split            : {split_name.upper()}")
    print(f"{'=' * 60}")
    print(f"  Rows             : {len(df):>12,}")
    print(f"  Feature columns  : {len(feature_cols):>12,}")
    print(f"  Laundering rows  : {launder:>12,}  ({label_pct:.3f}%)")
    if missing:
        print("  Missing values   :")
        for col, cnt in missing.items():
            print(f"    {col}: {cnt:,}")
    else:
        print("  Missing values   :         none")
    print(f"  Memory           : {mem_mb:>10.1f} MB")
    print(f"  Output           : {out_path}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vectorized AML feature engineering — no row-by-row iteration."
    )
    parser.add_argument("--input-dir",    type=Path,  default=Path("ml/data/processed"),
                        help="Directory containing train/val/test .parquet files")
    parser.add_argument("--output-dir",   type=Path,  default=Path("ml/data/features"),
                        help="Directory to write feature parquet files")
    parser.add_argument("--window-short", type=str,   default="1h",
                        help="Short rolling window, e.g. '1h' (default: 1h)")
    parser.add_argument("--window-long",  type=str,   default="24h",
                        help="Long rolling window, e.g. '24h' (default: 24h)")
    parser.add_argument("--sample-frac",  type=float, default=None,
                        help="Fraction of rows to sample per split (e.g. 0.01). "
                             "Omit for full dataset.")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    short_td = pd.Timedelta(args.window_short)
    long_td  = pd.Timedelta(args.window_long)
    short_label = f"{int(short_td.total_seconds() // 3600)}h"
    long_label  = f"{int(long_td.total_seconds() // 3600)}h"

    # Rename generic column labels in OUTPUT_FEATURE_COLS to match actual window args
    feature_cols = [
        c.replace("_1h", f"_{short_label}").replace("_24h", f"_{long_label}")
        for c in OUTPUT_FEATURE_COLS
    ]

    t0 = time.time()

    # ── Load ─────────────────────────────────────────────────────────────────
    log.info("Loading splits from %s ...", args.input_dir)
    train_df = load_parquet(args.input_dir / "train.parquet", args.sample_frac)
    val_df   = load_parquet(args.input_dir / "val.parquet",   args.sample_frac)
    test_df  = load_parquet(args.input_dir / "test.parquet",  args.sample_frac)

    # ── Fit encoders on train ─────────────────────────────────────────────────
    log.info("Fitting label encoders on training split ...")
    encoders = fit_encoders(train_df)

    # ── Process each split ────────────────────────────────────────────────────
    log.info("=" * 55)
    log.info("Processing TRAIN split ...")
    t1 = time.time()
    train_out = process_split(train_df, None, encoders, short_td, long_td, "train")
    train_out = optimise_dtypes(train_out)
    log.info("TRAIN done in %.1f s", time.time() - t1)

    log.info("=" * 55)
    log.info("Processing VAL split (train as history) ...")
    t1 = time.time()
    val_out = process_split(val_df, train_df, encoders, short_td, long_td, "val")
    val_out = optimise_dtypes(val_out)
    log.info("VAL done in %.1f s", time.time() - t1)

    log.info("=" * 55)
    log.info("Processing TEST split (train + val as history) ...")
    t1 = time.time()
    test_out = process_split(
        test_df,
        pd.concat([train_df, val_df], ignore_index=True),
        encoders, short_td, long_td, "test",
    )
    test_out = optimise_dtypes(test_out)
    log.info("TEST done in %.1f s", time.time() - t1)

    # ── Save ─────────────────────────────────────────────────────────────────
    out_paths = {
        "train": args.output_dir / "train_features.parquet",
        "val":   args.output_dir / "val_features.parquet",
        "test":  args.output_dir / "test_features.parquet",
    }

    for name, df_out, path in [
        ("train", train_out, out_paths["train"]),
        ("val",   val_out,   out_paths["val"]),
        ("test",  test_out,  out_paths["test"]),
    ]:
        present_features = [c for c in feature_cols if c in df_out.columns]
        save_cols = present_features + [LABEL_COL] if LABEL_COL in df_out.columns else present_features
        df_out[save_cols].to_parquet(path, index=False)
        print_summary(df_out, name, path, present_features)

    total = time.time() - t0
    log.info("All splits complete. Total elapsed: %.1f s (%.1f min)", total, total / 60)


if __name__ == "__main__":
    main()
