"""AML pattern detectors (Phase 3).

Each detector accepts a small DataFrame of candidate transactions (already
through `preprocessing.build_processed_table`) and returns a list of
findings, each shaped:

    {
        "pattern_type": "...",
        "risk_score": 0.0-1.0,
        "reason": "...",
        "accounts_involved": [...],
        "features": {...},
    }

The detectors are intentionally simple and explainable — they produce
explanations the dashboard can render. They are not the model. The model
sits in Phase 4; the pattern library complements it for the privacy-hash
engine (Phase 6) and the explanation panel (Phase 8).
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

import numpy as np
import pandas as pd

try:  # NetworkX is in backend/requirements.txt; degrade gracefully otherwise.
    import networkx as nx
except Exception:  # pragma: no cover
    nx = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

Finding = dict[str, Any]


# ----------------------------------------------------------------- helpers


def _ensure_columns(df: pd.DataFrame, cols: Iterable[str]) -> bool:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        logger.debug("Pattern detector missing columns: %s", missing)
        return False
    return True


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _build_digraph(df: pd.DataFrame):
    """Build a small directed multigraph for cycle / shape detection."""
    if nx is None:
        return None
    g = nx.MultiDiGraph()
    for _, row in df.iterrows():
        g.add_edge(
            row["src_id"], row["dst_id"],
            amount=float(row.get("amount", 0.0)),
            timestamp=row.get("timestamp"),
            from_bank=row.get("from_bank_id"),
            to_bank=row.get("to_bank_id"),
        )
    return g


# ----------------------------------------------------------------- detectors


def detect_fan_in(df: pd.DataFrame, *, min_sources: int = 3) -> list[Finding]:
    if not _ensure_columns(df, ("src_id", "dst_id", "amount")):
        return []
    findings: list[Finding] = []
    grouped = df.groupby("dst_id")
    for dst, sub in grouped:
        n_src = sub["src_id"].nunique()
        if n_src >= min_sources:
            total = float(sub["amount"].sum())
            findings.append({
                "pattern_type": "fan_in",
                "risk_score": _clip01(0.5 + 0.1 * (n_src - min_sources)),
                "reason": f"Account received funds from {n_src} distinct sources (>={min_sources}).",
                "accounts_involved": [dst, *sub["src_id"].unique().tolist()],
                "features": {"target": dst, "n_sources": int(n_src), "total_in": total},
            })
    return findings


def detect_fan_out(df: pd.DataFrame, *, min_targets: int = 3) -> list[Finding]:
    if not _ensure_columns(df, ("src_id", "dst_id", "amount")):
        return []
    findings: list[Finding] = []
    for src, sub in df.groupby("src_id"):
        n_dst = sub["dst_id"].nunique()
        if n_dst >= min_targets:
            total = float(sub["amount"].sum())
            findings.append({
                "pattern_type": "fan_out",
                "risk_score": _clip01(0.5 + 0.1 * (n_dst - min_targets)),
                "reason": f"Account sent funds to {n_dst} distinct targets (>={min_targets}).",
                "accounts_involved": [src, *sub["dst_id"].unique().tolist()],
                "features": {"source": src, "n_targets": int(n_dst), "total_out": total},
            })
    return findings


def detect_simple_cycle(df: pd.DataFrame, *, max_len: int = 4) -> list[Finding]:
    if nx is None or not _ensure_columns(df, ("src_id", "dst_id")):
        return []
    g = _build_digraph(df)
    if g is None:
        return []
    findings: list[Finding] = []
    try:
        # Convert to simple DiGraph for cycle search; multi-edges collapse.
        simple = nx.DiGraph(g)
        cycles = nx.simple_cycles(simple)
        for cyc in cycles:
            if 2 <= len(cyc) <= max_len:
                findings.append({
                    "pattern_type": "simple_cycle",
                    "risk_score": _clip01(0.6 + 0.1 * (max_len - len(cyc))),
                    "reason": f"Detected funds cycle of length {len(cyc)}.",
                    "accounts_involved": cyc,
                    "features": {"length": len(cyc)},
                })
            if len(findings) >= 10:  # bound output for the dashboard
                break
    except Exception as exc:  # pragma: no cover
        logger.debug("simple_cycle detector error: %s", exc)
    return findings


def detect_mule_velocity(
    df: pd.DataFrame,
    *,
    window_minutes: int = 60,
    min_inflows: int = 3,
    min_total: float = 5_000.0,
) -> list[Finding]:
    """Account receives >= min_inflows in a short window, totalling >= min_total."""
    if not _ensure_columns(df, ("dst_id", "timestamp", "amount")):
        return []
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    findings: list[Finding] = []
    window = pd.Timedelta(minutes=window_minutes)
    for dst, sub in df.groupby("dst_id"):
        if len(sub) < min_inflows:
            continue
        sub = sub.sort_values("timestamp")
        # Sliding window — for each row, check the trailing `window`.
        amounts = sub["amount"].to_numpy()
        times = sub["timestamp"].to_numpy()
        left = 0
        for right in range(len(sub)):
            while times[right] - times[left] > window:
                left += 1
            if right - left + 1 >= min_inflows:
                total = float(amounts[left:right + 1].sum())
                if total >= min_total:
                    n = right - left + 1
                    findings.append({
                        "pattern_type": "mule_velocity",
                        "risk_score": _clip01(0.7 + min(0.3, 0.05 * (n - min_inflows))),
                        "reason": (
                            f"{n} inflows totalling {total:.0f} within {window_minutes}m "
                            f"on a single account."
                        ),
                        "accounts_involved": [dst, *sub.iloc[left:right + 1]["src_id"].unique().tolist()],
                        "features": {
                            "target": dst,
                            "window_minutes": window_minutes,
                            "n_inflows": int(n),
                            "total_amount": total,
                        },
                    })
                    break  # one finding per account is enough
    return findings


def detect_rapid_sweep(
    df: pd.DataFrame,
    *,
    window_minutes: int = 60,
    ratio: float = 0.8,
) -> list[Finding]:
    """Account receives inflows then quickly sends >= ratio of them out."""
    if not _ensure_columns(df, ("src_id", "dst_id", "amount", "timestamp")):
        return []
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    findings: list[Finding] = []
    window = pd.Timedelta(minutes=window_minutes)

    # Treat every account that is both a src and a dst as a candidate.
    candidates = set(df["src_id"]) & set(df["dst_id"])
    for acct in candidates:
        ins = df[df["dst_id"] == acct].sort_values("timestamp")
        outs = df[df["src_id"] == acct].sort_values("timestamp")
        if ins.empty or outs.empty:
            continue
        in_total = float(ins["amount"].sum())
        if in_total <= 0:
            continue
        # For each outflow, check if matching inflows happened within window.
        for _, out_row in outs.iterrows():
            window_in = ins[(ins["timestamp"] >= out_row["timestamp"] - window) &
                            (ins["timestamp"] <= out_row["timestamp"])]
            if window_in.empty:
                continue
            window_total = float(window_in["amount"].sum())
            if window_total > 0 and float(out_row["amount"]) / window_total >= ratio:
                findings.append({
                    "pattern_type": "rapid_sweep",
                    "risk_score": _clip01(0.65 + 0.3 * min(1.0, float(out_row["amount"]) / window_total - ratio)),
                    "reason": (
                        f"Account swept {out_row['amount']:.0f} out within {window_minutes}m "
                        f"of receiving {window_total:.0f}."
                    ),
                    "accounts_involved": [acct, out_row["dst_id"]],
                    "features": {
                        "account": acct,
                        "out_amount": float(out_row["amount"]),
                        "in_window_total": window_total,
                        "ratio": float(out_row["amount"]) / window_total,
                    },
                })
                break
    return findings


def detect_cross_bank_pass_through(df: pd.DataFrame) -> list[Finding]:
    """Account receives from Bank X and sends to Bank Y on different banks."""
    if not _ensure_columns(df, ("src_id", "dst_id", "from_bank_id", "to_bank_id")):
        return []
    findings: list[Finding] = []
    candidates = set(df["src_id"]) & set(df["dst_id"])
    for acct in candidates:
        ins = df[df["dst_id"] == acct]
        outs = df[df["src_id"] == acct]
        if ins.empty or outs.empty:
            continue
        in_banks = sorted(int(b) for b in ins["from_bank_id"].dropna().unique())
        out_banks = sorted(int(b) for b in outs["to_bank_id"].dropna().unique())
        crossing = set(in_banks) - set(out_banks)
        if crossing and (set(in_banks) != set(out_banks)):
            findings.append({
                "pattern_type": "cross_bank_pass_through",
                "risk_score": 0.7,
                "reason": (
                    f"Account routed funds between banks: in={in_banks} out={out_banks}."
                ),
                "accounts_involved": [acct],
                "features": {
                    "account": acct,
                    "in_banks": in_banks,
                    "out_banks": out_banks,
                },
            })
    return findings


def detect_scatter_gather(df: pd.DataFrame, *, min_legs: int = 3) -> list[Finding]:
    """Approximation: a single source disperses to many intermediaries that
    later converge on one target.
    """
    if not _ensure_columns(df, ("src_id", "dst_id", "amount")):
        return []
    findings: list[Finding] = []
    # For each source, find dst_ids that themselves later send to a common target.
    for src, sub_src in df.groupby("src_id"):
        intermediaries = set(sub_src["dst_id"].unique())
        if len(intermediaries) < min_legs:
            continue
        downstream = df[df["src_id"].isin(intermediaries)]
        target_counts = downstream.groupby("dst_id")["src_id"].nunique()
        target_counts = target_counts[target_counts >= min_legs]
        for target, n in target_counts.items():
            findings.append({
                "pattern_type": "scatter_gather",
                "risk_score": _clip01(0.6 + 0.05 * (int(n) - min_legs)),
                "reason": (
                    f"Source dispersed funds to {len(intermediaries)} legs that "
                    f"converged on a single target ({int(n)} of them)."
                ),
                "accounts_involved": [src, target, *list(intermediaries)[:5]],
                "features": {"source": src, "target": target, "n_legs": int(n)},
            })
    return findings


def detect_gather_scatter(df: pd.DataFrame, *, min_legs: int = 3) -> list[Finding]:
    """Inverse: many sources converge on one collector that then disperses."""
    if not _ensure_columns(df, ("src_id", "dst_id", "amount")):
        return []
    findings: list[Finding] = []
    for collector, sub in df.groupby("dst_id"):
        sources = set(sub["src_id"].unique())
        if len(sources) < min_legs:
            continue
        downstream = df[df["src_id"] == collector]
        if downstream["dst_id"].nunique() < min_legs:
            continue
        findings.append({
            "pattern_type": "gather_scatter",
            "risk_score": _clip01(0.6 + 0.05 * (len(sources) - min_legs)),
            "reason": (
                f"Collector gathered from {len(sources)} sources and dispersed "
                f"to {downstream['dst_id'].nunique()} targets."
            ),
            "accounts_involved": [collector, *list(sources)[:5]],
            "features": {
                "collector": collector,
                "n_sources": len(sources),
                "n_targets": int(downstream["dst_id"].nunique()),
            },
        })
    return findings


# ----------------------------------------------------------------- batch runner


ALL_DETECTORS = (
    ("fan_in", detect_fan_in),
    ("fan_out", detect_fan_out),
    ("simple_cycle", detect_simple_cycle),
    ("mule_velocity", detect_mule_velocity),
    ("rapid_sweep", detect_rapid_sweep),
    ("cross_bank_pass_through", detect_cross_bank_pass_through),
    ("scatter_gather", detect_scatter_gather),
    ("gather_scatter", detect_gather_scatter),
)


def run_all(df: pd.DataFrame) -> list[Finding]:
    out: list[Finding] = []
    for name, fn in ALL_DETECTORS:
        try:
            findings = fn(df)
            out.extend(findings)
        except Exception as exc:  # pragma: no cover
            logger.warning("Detector %s failed: %s", name, exc)
    # Sort by risk descending so the dashboard shows the worst first.
    out.sort(key=lambda f: f.get("risk_score", 0.0), reverse=True)
    return out


__all__ = [
    "Finding",
    "ALL_DETECTORS",
    "run_all",
    "detect_fan_in",
    "detect_fan_out",
    "detect_simple_cycle",
    "detect_mule_velocity",
    "detect_rapid_sweep",
    "detect_cross_bank_pass_through",
    "detect_scatter_gather",
    "detect_gather_scatter",
]


# numpy used internally; quiet the linter
_ = np
