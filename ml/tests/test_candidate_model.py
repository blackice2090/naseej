"""Tests for ml/src/train_candidate_model.py (shadow candidate).

Uses tiny synthetic raw splits so the whole pipeline runs in seconds, writing
to a temp reports/models dir so the real deployed artifacts are never touched.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import pytest

from ml.src import train_candidate_model as tc
from ml.src import feature_contract as fc


def _tx(ts, src, dst, amount, *, src_bank=101, dst_bank=101, label=0):
    return {
        "timestamp": pd.Timestamp(ts), "source_bank": src_bank, "source_account": src,
        "target_bank": dst_bank, "target_account": dst, "amount_received": float(amount),
        "receiving_currency": "USD", "amount": float(amount), "currency": "USD",
        "payment_type": "wire", "is_laundering": label,
    }


def _background(start, days, n, rng, accounts):
    rows = []
    base = pd.Timestamp(start)
    for i in range(n):
        src, dst = rng.choice(accounts, size=2, replace=False)
        rows.append(_tx(base + pd.Timedelta(minutes=int(rng.integers(0, days * 24 * 60))),
                        src, dst, float(rng.integers(50, 5000)),
                        src_bank=int(rng.choice([101, 202])), dst_bank=int(rng.choice([101, 202]))))
    return rows


@pytest.fixture(scope="module")
def synthetic_splits():
    rng = np.random.default_rng(11)
    accounts = [f"ACC{i:03d}" for i in range(40)]
    train = _background("2024-01-01", 7, 700, rng, accounts)
    for i, s in enumerate(["TRS01", "TRS02", "TRS03", "TRS04"]):
        train.append(_tx(f"2024-01-05 0{i+1}:00", s, "TRMULE", 900 + 40 * i, label=1))
    val = _background("2024-01-08", 2, 150, rng, accounts)
    for i, s in enumerate(["VLS01", "VLS02", "VLS03"]):
        val.append(_tx(f"2024-01-09 0{i+2}:30", s, "VLMULE", 700 + 55 * i, label=1))
    test = _background("2024-01-10", 2, 150, rng, accounts)
    for i, s in enumerate(["FNS01", "FNS02", "FNS03", "FNS04", "FNS05"]):
        test.append(_tx(f"2024-01-10 {2*i+8:02d}:00", s, "FNMULE", 120 + 10 * i,
                        src_bank=101, dst_bank=202, label=1))
    test.append(_tx("2024-01-11 11:30", "LONERS", "LONERT", 4321, label=1))

    def frame(rows):
        return pd.DataFrame(rows).sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    return {"train": frame(train), "val": frame(val), "test": frame(test)}


@pytest.fixture(scope="module")
def candidate_run(synthetic_splits, tmp_path_factory):
    reports = tmp_path_factory.mktemp("cand_reports")
    models = tmp_path_factory.mktemp("cand_models")
    summary = tc.run_candidate(
        splits_raw=synthetic_splits, reports_dir=reports, models_dir=models,
        train_sample=0, seed=42, model_names=["logistic_regression", "random_forest"],
    )
    return reports, models, summary


# ── approved feature set / hard blocks ───────────────────────────────────────

class TestApprovedFeatures:
    def test_approved_columns_are_15_and_offline(self):
        cols = tc.load_approved_offline_columns()
        assert len(cols) == 15
        assert "amount" in cols and "source_out_tx_count_1h" in cols
        assert "target_in_amount_sum_24h" in cols

    def test_no_identity_or_excluded_features(self):
        cols = tc.load_approved_offline_columns()
        for forbidden in ("source_account_enc", "target_account_enc",
                          "source_bank_enc", "target_bank_enc",
                          "fan_in_score", "fan_out_score", "sweep_ratio"):
            assert forbidden not in cols
        # No all-time cumulative or pair features.
        assert not any("_total_before" in c or "account_pair_" in c for c in cols)

    def test_assert_no_forbidden_raises(self):
        with pytest.raises(AssertionError):
            tc._assert_no_forbidden(["amount", "source_account_enc"])
        with pytest.raises(AssertionError):
            tc._assert_no_forbidden(["amount", "source_out_amount_sum_total_before"])

    def test_approved_set_is_subset_of_manifest(self):
        manifest = json.loads(tc.MANIFEST_PATH.read_text(encoding="utf-8"))
        approved = {r["offline_name"] for r in manifest["approved_training_features"]}
        assert set(tc.load_approved_offline_columns()) == approved


# ── protected artifacts ──────────────────────────────────────────────────────

class TestProtectedArtifacts:
    def test_baseline_and_metrics_not_overwritten(self, candidate_run):
        reports, models, _ = candidate_run
        # The temp dirs must NOT contain the deployed artifact names.
        assert not (models / "baseline_model.joblib").exists()
        assert not (reports / "model_metrics.json").exists()
        # And the candidate model IS written under its own name.
        assert (models / "candidate_model.joblib").exists()

    def test_real_deployed_artifacts_untouched(self, candidate_run):
        # The real baseline bundle still reports xgboost (not the candidate).
        import joblib
        b = joblib.load(tc.DEFAULT_MODELS_DIR / "baseline_model.joblib")
        assert b["model_name"] == "xgboost"
        m = json.loads((tc.DEFAULT_REPORTS_DIR / "model_metrics.json").read_text(encoding="utf-8"))
        assert m["model_name"] == "xgboost"


# ── report shapes ────────────────────────────────────────────────────────────

class TestReports:
    def test_all_reports_written(self, candidate_run):
        reports, _, _ = candidate_run
        for f in ("candidate_model_metrics.json", "candidate_model_metrics.md",
                  "candidate_model_comparison.json", "candidate_model_comparison.md",
                  "candidate_thresholds.json", "candidate_thresholds.md",
                  "candidate_explainability_check.json", "candidate_explainability_check.md"):
            assert (reports / f).exists(), f

    def test_metrics_report_shape(self, candidate_run):
        reports, _, _ = candidate_run
        d = json.loads((reports / "candidate_model_metrics.json").read_text(encoding="utf-8"))
        assert d["deployed"] is False and d["shadow_only"] is True
        assert d["deployment_recommended"] is False
        assert d["primary_metric"] == "pr_auc"
        assert d["feature_set"] == "approved_parity_clean_only"
        for k in ("pr_auc", "roc_auc", "precision", "recall", "f1", "fpr",
                  "alerts_per_100k", "confusion_matrix"):
            assert k in d["selected_test_metrics"]
        # protocol honesty: flags the non-comparable deployed split
        assert "model_metrics.json" in d["protocol"]["not_comparable_with"]

    def test_comparison_report_shape(self, candidate_run):
        reports, _, _ = candidate_run
        d = json.loads((reports / "candidate_model_comparison.json").read_text(encoding="utf-8"))
        assert d["leaderboard"]
        assert d["selected_model"] in ("logistic_regression", "random_forest")
        # excluded features explicitly listed, incl. identity encodings
        excluded = {e["canonical_name"] for e in d["excluded_features"]}
        assert {"source_account_code", "target_account_code",
                "source_bank_code", "target_bank_code"} <= excluded

    def test_thresholds_report_shape(self, candidate_run):
        reports, _, _ = candidate_run
        d = json.loads((reports / "candidate_thresholds.json").read_text(encoding="utf-8"))
        modes = [r["mode"] for r in d["thresholds"]]
        assert modes == ["high_precision", "balanced", "high_recall"]
        for r in d["thresholds"]:
            assert {"threshold", "precision", "recall", "f1", "fpr",
                    "alerts_per_100k", "recommended_use"} <= set(r)


# ── explainability check (PII-safe, contract-resolved) ───────────────────────

class TestExplainability:
    def test_explainability_pii_safe_buckets(self, candidate_run):
        reports, _, _ = candidate_run
        d = json.loads((reports / "candidate_explainability_check.json").read_text(encoding="utf-8"))
        assert d["pii_safe"] is True
        assert d["all_features_resolve_in_contract"] is True
        for f in d["top_factors"]:
            assert "value_bucket" in f and "raw_value" not in f
            # bucket is a label, never a raw number
            assert not str(f["value_bucket"]).replace(".", "").replace("-", "").isdigit()
        for r in d["feature_resolution"]:
            assert r["resolves_in_contract"] is True
            assert r["canonical_name"]


# ── LightGBM graceful skip ───────────────────────────────────────────────────

class TestLightgbmSkip:
    def test_missing_lightgbm_skips(self, synthetic_splits, tmp_path, monkeypatch):
        monkeypatch.setitem(sys.modules, "lightgbm", None)
        from ml.src import evaluation_suite as es
        _, availability = es.build_competitors(seed=0)
        assert availability["lightgbm"]["available"] is False
        # Candidate run still completes without lightgbm.
        summary = tc.run_candidate(
            splits_raw=synthetic_splits, reports_dir=tmp_path / "r", models_dir=tmp_path / "m",
            train_sample=0, seed=1, model_names=["logistic_regression"],
        )
        assert summary["deployment_recommended"] is False


def test_summary_marks_shadow(candidate_run):
    _, _, summary = candidate_run
    assert summary["deployment_recommended"] is False
    assert summary["n_features"] == 15
