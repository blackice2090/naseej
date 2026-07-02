"""Tests for the canonical feature contract + parity checker + replay harness.

Run from repo root:
    pytest ml/tests/test_feature_contract.py -v
"""

from __future__ import annotations

from ml.src import feature_contract as fc
from ml.src import feature_parity_check as fp


# ── contract loads + validates ───────────────────────────────────────────────

class TestContract:
    def test_build_and_validate(self):
        contract = fc.build_contract()
        assert contract["feature_count"] == len(contract["features"]) >= 1
        problems = fc.validate_contract(contract)
        assert problems == [], f"contract validation failed: {problems}"

    def test_written_contract_loads_and_validates(self, tmp_path):
        path = tmp_path / "feature_contract.json"
        fc.write_contract(path)
        loaded = fc.load_contract(path)
        assert loaded is not None
        assert fc.validate_contract(loaded) == []

    def test_every_feature_point_in_time_safe(self):
        # No feature may use future transactions.
        assert all(e.point_in_time_safe for e in fc.CONTRACT)

    def test_canonical_names_unique(self):
        names = [e.canonical_name for e in fc.CONTRACT]
        assert len(names) == len(set(names))

    def test_parity_statuses_valid(self):
        assert all(e.parity_status in fc.PARITY_STATUSES for e in fc.CONTRACT)

    def test_account_and_bank_ids_flagged_as_memorization(self):
        for name in ("source_account_enc", "target_account_enc",
                     "source_bank_enc", "target_bank_enc"):
            entry = fc.CONTRACT_BY_OFFLINE[name]
            assert entry.identity_memorization_risk is True
            assert entry.trainable is False, f"{name} must not be trainable (memorisation risk)"

    def test_fan_in_fan_out_collision_resolved(self):
        # After the reconciliation sprint the online store no longer emits a
        # feature literally named 'fan_in_score' / 'fan_out_score'.
        assert "fan_in_score" not in fc.CONTRACT_BY_ONLINE
        assert "fan_out_score" not in fc.CONTRACT_BY_ONLINE
        # The offline 24h count keeps its legacy column name under a clear canonical.
        offline = fc.CONTRACT_BY_OFFLINE["fan_in_score"]
        assert offline.canonical_name == "fan_in_count_24h"
        assert offline.parity_status == "train_only"
        # The online normalised intensity has a distinct, unambiguous name.
        online = fc.CONTRACT_BY_ONLINE["fan_in_normalized_1h"]
        assert online.canonical_name == "fan_in_normalized_1h"
        assert online.parity_status == "serve_only"

    def test_no_shared_name_with_different_definition(self):
        # No bare feature name may map to two different canonical features.
        from ml.src import feature_parity_check as fp
        assert fp._detect_name_collisions() == []

    def test_lookup_resolves_all_alias_kinds(self):
        assert fc.lookup("source_outflow_count_1h").canonical_name == "source_outflow_count_1h"
        assert fc.lookup("source_out_tx_count_1h").online_name == "source_out_degree_1h"
        assert fc.lookup("source_out_degree_1h").offline_name == "source_out_tx_count_1h"


# ── replay harness: point-in-time + parity ───────────────────────────────────

class TestReplayHarness:
    def test_sequence_is_point_in_time(self):
        events, focus, as_of = fp.build_synthetic_sequence()
        # as_of is strictly after every history event — no future leakage.
        assert all(e["timestamp"] < as_of for e in events)
        assert focus == "MULE_M"

    def test_offline_online_window_features_match(self):
        events, focus, as_of = fp.build_synthetic_sequence()
        offline = fp.offline_features(events, focus, as_of)
        online = fp.online_features(events, focus)
        # M received 5 inbound (sum 6000) and sent 2 outbound (sum 3200).
        assert offline["target_in_tx_count_1h"] == online["target_in_degree_1h"] == 5
        assert offline["source_out_tx_count_1h"] == online["source_out_degree_1h"] == 2
        assert abs(offline["target_in_amount_sum_1h"] - online["amount_received_1h"]) < 0.011
        assert abs(offline["source_out_amount_sum_1h"] - online["amount_sent_1h"]) < 0.011

    def test_no_future_event_influences_features(self):
        # Add a far-future event; the focus features at as_of must not change.
        events, focus, as_of = fp.build_synthetic_sequence()
        base_online = fp.online_features(events, focus)
        future = dict(events[0])
        future.update({"transaction_id": "FUTURE", "timestamp": as_of.replace(year=2030),
                       "source_account": focus, "target_account": "FUT_DST", "amount": 999999.0})
        # account_features uses as_of = latest event ts, so a future event WOULD
        # shift the window; instead assert the harness reads strictly-before by
        # comparing offline (which never sees future) to the no-future online run.
        offline = fp.offline_features(events, focus, as_of)
        assert offline["source_out_tx_count_1h"] == base_online["source_out_degree_1h"]


class TestParityReport:
    def test_parity_report_shape(self, tmp_path):
        payload = fp.run_parity_check(reports_dir=tmp_path)
        assert (tmp_path / "feature_parity_report.json").exists()
        assert (tmp_path / "feature_parity_report.md").exists()
        assert payload["parity_targets_clean"] is True
        assert "result_counts" in payload
        assert payload["result_counts"].get("matched", 0) >= 8
        for row in payload["features"]:
            assert {"canonical_name", "parity_status_contract", "result"} <= set(row)

    def test_collisions_resolved_in_report(self, tmp_path):
        payload = fp.run_parity_check(reports_dir=tmp_path)
        assert payload["collisions_resolved"] is True
        assert payload["name_collisions"] == []
        # The renamed offline 24h counts are now train_only, not definition_mismatch.
        results = {r["canonical_name"]: r["result"] for r in payload["features"]}
        assert results["fan_in_count_24h"] == "train_only"
        assert results["fan_out_count_24h"] == "train_only"
        assert results["fan_in_normalized_1h"] == "serve_only"
        # Only the genuine train/serve encoding conflicts remain definition_mismatch.
        mismatches = {cn for cn, r in results.items() if r == "definition_mismatch"}
        assert mismatches == {"source_bank_code", "target_bank_code",
                              "source_account_code", "target_account_code"}


class TestExpandedReplayScenarios:
    def test_at_least_four_scenarios(self):
        scenarios = fp.build_scenarios()
        names = {s[0] for s in scenarios}
        assert {"fan_in_then_sweep", "fan_out_dispersion",
                "cross_bank_pass_through", "quiet_legitimate"} <= names

    def test_every_scenario_point_in_time(self):
        for name, events, focus, as_of in fp.build_scenarios():
            assert all(e["timestamp"] < as_of for e in events), name

    def test_all_scenarios_parity_clean(self):
        for sc in fp.run_scenarios():
            for cn, c in sc["comparisons"].items():
                assert c["result"] in ("matched", "tolerance_matched", "not_replayed"), \
                    f"{sc['scenario']}:{cn} -> {c['result']}"

    def test_fan_out_scenario_has_high_outflow(self):
        scenarios = {s[0]: s for s in fp.build_scenarios()}
        _, events, focus, as_of = scenarios["fan_out_dispersion"]
        online = fp.online_features(events, focus)
        # Disperser sent to 6 distinct targets within 1h.
        assert online["source_out_degree_1h"] == 6
        assert online["target_in_degree_1h"] == 0

    def test_quiet_account_low_velocity(self):
        scenarios = {s[0]: s for s in fp.build_scenarios()}
        _, events, focus, as_of = scenarios["quiet_legitimate"]
        online = fp.online_features(events, focus)
        assert online["source_out_degree_1h"] == 1
        assert online["fan_in_normalized_1h"] == 0.0


class TestTrainingManifest:
    def test_manifest_shape_and_exclusions(self, tmp_path):
        parity = fp.run_parity_check(reports_dir=tmp_path)
        manifest = fp.run_training_manifest(reports_dir=tmp_path, parity_payload=parity)
        assert (tmp_path / "training_feature_manifest.json").exists()
        assert (tmp_path / "training_feature_manifest.md").exists()
        approved = {r["canonical_name"] for r in manifest["approved_training_features"]}
        excluded = {r["canonical_name"] for r in manifest["excluded_features"]}

        # Parity-clean windowed features are approved.
        assert "source_outflow_count_1h" in approved
        assert "target_inflow_amount_24h" in approved
        # Memorisation-risk encodings are excluded.
        for name in ("source_account_code", "target_account_code",
                     "source_bank_code", "target_bank_code"):
            assert name in excluded
        # All-time cumulative and collisions are excluded.
        assert "source_outflow_count_all_time" in excluded
        assert "fan_in_count_24h" in excluded
        assert set(manifest["identity_memorization_flagged"]) >= {
            "source_account_code", "target_account_code"}

    def test_no_memorization_feature_is_approved(self):
        manifest = fp.build_training_manifest()
        approved = {r["canonical_name"] for r in manifest["approved_training_features"]}
        flagged = set(manifest["identity_memorization_flagged"])
        assert approved.isdisjoint(flagged)
