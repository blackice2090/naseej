"""Tests for ml/src/evaluation_suite.py.

Uses tiny synthetic raw splits (same schema as ml/data/processed) so the
full suite runs end-to-end in seconds without touching the real dataset
or the real ml/reports directory.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import pytest

from ml.src import evaluation_suite as es


# ----------------------------------------------------------------- synthetic data


def _tx(ts, src, dst, amount, *, src_bank=101, dst_bank=101, label=0):
    return {
        "timestamp": pd.Timestamp(ts),
        "source_bank": src_bank,
        "source_account": src,
        "target_bank": dst_bank,
        "target_account": dst,
        "amount_received": float(amount),
        "receiving_currency": "USD",
        "amount": float(amount),
        "currency": "USD",
        "payment_type": "wire",
        "is_laundering": label,
    }


def _background(start, days, n, rng, accounts):
    rows = []
    base = pd.Timestamp(start)
    for i in range(n):
        src, dst = rng.choice(accounts, size=2, replace=False)
        rows.append(_tx(
            base + pd.Timedelta(minutes=int(rng.integers(0, days * 24 * 60))),
            src, dst, float(rng.integers(50, 5000)),
            src_bank=int(rng.choice([101, 202])),
            dst_bank=int(rng.choice([101, 202])),
        ))
    return rows


@pytest.fixture(scope="module")
def synthetic_splits():
    """Three temporally ordered raw splits with laundering in each period.

    Test period contains a clean fan-in cluster (5 sources -> one mule, hours
    apart so mule_velocity does not outrank it) and one isolated laundering
    transfer that no detector should match (-> unknown_unmatched).
    """
    rng = np.random.default_rng(7)
    accounts = [f"ACC{i:03d}" for i in range(40)]

    train_rows = _background("2024-01-01", 7, 700, rng, accounts)
    # Train-period laundering: small fan-in so the model has positives to learn.
    for i, src in enumerate(["TRS01", "TRS02", "TRS03", "TRS04"]):
        train_rows.append(_tx(f"2024-01-05 0{i+1}:00", src, "TRMULE", 900 + 40 * i, label=1))

    val_rows = _background("2024-01-08", 2, 150, rng, accounts)
    for i, src in enumerate(["VLS01", "VLS02", "VLS03"]):
        val_rows.append(_tx(f"2024-01-09 0{i+2}:30", src, "VLMULE", 700 + 55 * i, label=1))

    test_rows = _background("2024-01-10", 2, 150, rng, accounts)
    # Fan-in typology: five sources, two hours apart, no sweep-out afterwards.
    for i, src in enumerate(["FNS01", "FNS02", "FNS03", "FNS04", "FNS05"]):
        test_rows.append(_tx(
            f"2024-01-10 {2 * i + 8:02d}:00", src, "FNMULE", 120 + 10 * i,
            src_bank=101, dst_bank=202, label=1,
        ))
    # Isolated laundering transfer between otherwise inactive accounts.
    test_rows.append(_tx("2024-01-11 11:30", "LONERS", "LONERT", 4_321, label=1))

    def frame(rows):
        return (
            pd.DataFrame(rows)
            .sort_values("timestamp", kind="mergesort")
            .reset_index(drop=True)
        )

    return {"train": frame(train_rows), "val": frame(val_rows), "test": frame(test_rows)}


# ----------------------------------------------------------------- unit tests


def test_feature_sets_are_nested_and_clean():
    a = set(es.FEATURE_SETS["transaction_only"])
    b = set(es.FEATURE_SETS["graph"])
    c = set(es.FEATURE_SETS["graph_context"])
    full = set(es.FEATURE_SETS["full_with_account_ids"])
    assert a < b < c < full
    forbidden = {"is_laundering", "label", "timestamp", "source_account", "target_account"}
    assert not (full & forbidden)
    # Every set has a human-readable description for the report.
    assert set(es.FEATURE_SET_DESCRIPTIONS) == set(es.FEATURE_SETS)


def test_temporal_split_is_ordered_and_disjoint():
    rng = np.random.default_rng(3)
    rows = _background("2024-03-01", 10, 400, rng, [f"A{i}" for i in range(10)])
    df = pd.DataFrame(rows)
    splits = es.temporal_split(df, train_frac=0.7, val_frac=0.15)
    assert len(splits["train"]) + len(splits["val"]) + len(splits["test"]) == len(df)
    assert splits["train"]["timestamp"].max() <= splits["val"]["timestamp"].min()
    assert splits["val"]["timestamp"].max() <= splits["test"]["timestamp"].min()


def test_threshold_by_fbeta_tradeoff():
    y = np.array([0] * 90 + [1] * 10)
    scores = np.concatenate([np.linspace(0.0, 0.4, 90), np.linspace(0.3, 0.9, 10)])
    thr_precision, _ = es.threshold_by_fbeta(y, scores, beta=0.5)
    thr_recall, _ = es.threshold_by_fbeta(y, scores, beta=2.0)
    assert thr_recall <= thr_precision  # recall-leaning mode alerts more


def test_build_competitors_reports_availability():
    models, availability = es.build_competitors(seed=0)
    names = [n for n, _ in models]
    assert "logistic_regression" in names and "random_forest" in names
    for lib in ("xgboost", "lightgbm"):
        assert lib in availability
        if availability[lib]["available"]:
            assert lib in names
        else:
            assert lib not in names
            assert "reason" in availability[lib]


def test_lightgbm_graceful_skip(monkeypatch):
    """If lightgbm cannot be imported the suite must skip it with a recorded
    reason instead of failing or fabricating results."""
    monkeypatch.setitem(sys.modules, "lightgbm", None)  # forces ImportError
    models, availability = es.build_competitors(seed=0)
    assert "lightgbm" not in [n for n, _ in models]
    assert availability["lightgbm"]["available"] is False
    assert "skipped" in availability["lightgbm"]["reason"]


def test_infer_typology_labels(synthetic_splits):
    feats = es.build_features(synthetic_splits)
    positives = es.infer_typology_labels(feats["test"])
    assert len(positives) == 6
    by_account = positives.set_index("target_account")["typology"]
    assert (by_account.loc["FNMULE"] == "fan_in").all()
    assert by_account.loc["LONERT"] == es.UNKNOWN_TYPOLOGY


# ----------------------------------------------------------------- end-to-end


EXPECTED_REPORTS = (
    "model_comparison.json", "model_comparison.md",
    "per_typology_recall.json", "per_typology_recall.md",
    "threshold_analysis.json", "threshold_analysis.md",
    "ablation_report.json", "ablation_report.md",
)


@pytest.fixture(scope="module")
def suite_run(synthetic_splits, tmp_path_factory):
    reports_dir = tmp_path_factory.mktemp("reports")
    summary = es.run_suite(
        splits_raw=synthetic_splits,
        reports_dir=reports_dir,
        train_sample=0,
        seed=42,
        model_names=["logistic_regression", "random_forest"],
    )
    return reports_dir, summary


def test_suite_writes_exactly_the_expected_reports(suite_run):
    reports_dir, summary = suite_run
    written = sorted(f.name for f in reports_dir.iterdir())
    assert written == sorted(EXPECTED_REPORTS)
    # The suite must never write the deployed-baseline report.
    assert "model_metrics.json" not in written
    assert summary["best_model"] in ("logistic_regression", "random_forest")


def test_model_comparison_report_shape(suite_run):
    reports_dir, _ = suite_run
    data = json.loads((reports_dir / "model_comparison.json").read_text(encoding="utf-8"))
    assert data["source"] == "live"
    assert data["primary_metric"] == "pr_auc"
    assert data["deployed_baseline_untouched"] is True
    assert "lightgbm" in data["availability"]
    assert {"split", "leakage_note", "threshold_selection"} <= set(data["protocol"])
    for row in data["models"]:
        for split in ("val", "test"):
            m = row[split]
            assert {"pr_auc", "roc_auc", "precision", "recall", "f1", "fpr",
                    "n_alerts", "alerts_per_100k", "confusion_matrix"} <= set(m)
    assert data["best_model"] == max(data["models"], key=lambda r: r["val"]["pr_auc"])["model"]
    # test_leader is the unbiased held-out winner, reported alongside the
    # validation-selected model so a val/test flip is visible, not hidden.
    assert data["test_leader"] == max(data["models"], key=lambda r: r["test"]["pr_auc"])["model"]
    assert "validation PR-AUC" in data["selection_note"]


def test_per_typology_recall_report_shape(suite_run):
    reports_dir, _ = suite_run
    data = json.loads((reports_dir / "per_typology_recall.json").read_text(encoding="utf-8"))
    assert "HEURISTIC" in data["label_method"]
    names = [r["typology"] for r in data["typologies"]]
    assert set(names) == set(es.TYPOLOGY_PRIORITY) | {es.UNKNOWN_TYPOLOGY}
    for row in data["typologies"]:
        assert {"typology", "sample_count", "detected_count", "recall",
                "false_negative_count", "best_model", "recall_by_model", "notes"} <= set(row)
        if row["sample_count"]:
            assert row["detected_count"] + row["false_negative_count"] == row["sample_count"]
    fan_in = next(r for r in data["typologies"] if r["typology"] == "fan_in")
    unknown = next(r for r in data["typologies"] if r["typology"] == es.UNKNOWN_TYPOLOGY)
    assert fan_in["sample_count"] == 5
    assert unknown["sample_count"] == 1


def test_threshold_analysis_report_shape(suite_run):
    reports_dir, _ = suite_run
    data = json.loads((reports_dir / "threshold_analysis.json").read_text(encoding="utf-8"))
    modes = [r["mode"] for r in data["thresholds"]]
    assert modes == ["high_precision", "balanced", "high_recall"]
    for row in data["thresholds"]:
        assert {"threshold", "precision", "recall", "f1", "fpr",
                "alerts_per_100k", "recommended_use"} <= set(row)
    by_mode = {r["mode"]: r for r in data["thresholds"]}
    assert by_mode["high_recall"]["threshold"] <= by_mode["high_precision"]["threshold"]


def test_ablation_report_shape(suite_run):
    reports_dir, _ = suite_run
    data = json.loads((reports_dir / "ablation_report.json").read_text(encoding="utf-8"))
    sets = [r["feature_set"] for r in data["feature_sets"]]
    assert sets == list(es.FEATURE_SETS)
    for row in data["feature_sets"]:
        assert row["n_features"] == len(es.FEATURE_SETS[row["feature_set"]])
        assert "test_pr_auc_delta_vs_transaction_only" in row
    assert "point-in-time" in data["leakage_note"]
