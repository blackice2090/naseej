"""Feature store + real-time velocity feature tests.

Covers: pseudonymous ingestion, auth and node-match gates, transaction PII
guard, rolling 1h/24h windows, node isolation (Bank B cannot read Bank A's
features), contextual scoring honesty, per-test store isolation, audit
records, and the no-raw-payload-in-audit guarantee.

Run from repo root:
    pytest backend/tests/test_feature_store.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from backend.app.core import config
from backend.app.main import app
from backend.app.services import feature_catalogue, feature_store_service

client = TestClient(app)

KEY_A = {"X-API-Key": "dev-key-bank-a-local-only"}
KEY_B = {"X-API-Key": "dev-key-bank-b-local-only"}
KEY_REG = {"X-API-Key": "dev-key-regulator-local-only"}
NODE_A = "NODE_A7C2F9E1"
NODE_B = "NODE_B3D8E2F4"

BASE_TS = "2026-06-01T10:{m:02d}:00"


def make_tx(i: int = 0, *, minute: int = 0, from_account: str = "PSEUDOSRC1",
            to_account: str = "PSEUDOMULE", amount: float = 2400.0,
            from_bank: str = "101", to_bank: str = "101",
            source_node_id: str = NODE_A, timestamp: str | None = None,
            **overrides) -> dict:
    tx = {
        "transaction_id": f"TX-FS-{i:04d}",
        "timestamp": timestamp or BASE_TS.format(m=minute),
        "source_node_id": source_node_id,
        "from_bank": from_bank,
        "from_account": from_account,
        "to_bank": to_bank,
        "to_account": to_account,
        "amount": amount,
        "currency": "US Dollar",
        "payment_format": "ACH",
    }
    tx.update(overrides)
    return tx


def ingest(tx: dict, headers: dict = KEY_A):
    return client.post("/api/features/ingest-transaction", json=tx, headers=headers)


def ingest_fan_in(n: int = 5, *, to_account: str = "PSEUDOMULE") -> float:
    """n inbound transfers to *to_account* within 10 minutes. Returns total."""
    total = 0.0
    for i in range(n):
        amount = 2000.0 + i * 100
        total += amount
        resp = ingest(make_tx(i, minute=i * 2, from_account=f"PSEUDOSRC{i}",
                              to_account=to_account, amount=amount))
        assert resp.status_code == 201, resp.text
    return total


def read_audit() -> str:
    path = config.audit_log_path()
    return path.read_text(encoding="utf-8") if path.exists() else ""


# ── ingestion: happy path and gates ─────────────────────────────────────────

class TestIngestion:
    def test_valid_pseudonymous_transaction_is_accepted(self):
        resp = ingest(make_tx())
        assert resp.status_code == 201
        body = resp.json()
        assert body["accepted"] is True
        assert body["zero_pii"] is True
        assert body["events_in_window"] == 1
        assert body["accounts_tracked"] == 2

    def test_missing_api_key_is_401(self):
        resp = client.post("/api/features/ingest-transaction", json=make_tx())
        assert resp.status_code == 401

    def test_wrong_api_key_is_401(self):
        resp = ingest(make_tx(), headers={"X-API-Key": "not-a-key"})
        assert resp.status_code == 401

    def test_source_node_mismatch_is_403(self):
        resp = ingest(make_tx(source_node_id=NODE_B))  # signed with key A
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Not authorized for this resource or action."

    def test_regulator_node_cannot_ingest(self):
        resp = ingest(make_tx(source_node_id="NODE_REG5C7A1"), headers=KEY_REG)
        assert resp.status_code == 403


class TestIngestionPiiGuard:
    def test_iban_in_account_field_rejected(self):
        resp = ingest(make_tx(from_account="SA4420000001234567891234"))
        assert resp.status_code == 422
        reasons = " ".join(resp.json()["detail"]["reasons"])
        assert "from_account" in reasons
        # The IBAN value itself must never be echoed back.
        assert "SA4420" not in resp.text

    def test_name_like_account_rejected(self):
        resp = ingest(make_tx(to_account="Mohammed Alqahtani"))
        assert resp.status_code == 422
        assert "Mohammed" not in json.dumps(resp.json()["detail"]["reasons"])

    def test_phone_like_account_rejected(self):
        resp = ingest(make_tx(from_account="+966512345678"))
        assert resp.status_code == 422

    def test_account_number_digit_run_rejected(self):
        resp = ingest(make_tx(to_account="1234567890123456"))
        assert resp.status_code == 422

    def test_extra_pii_field_rejected_by_schema(self):
        tx = make_tx()
        tx["customer_name"] = "anyone"
        resp = ingest(tx)
        assert resp.status_code == 422  # closed schema: extra="forbid"

    def test_arabic_free_text_rejected(self):
        resp = ingest(make_tx(payment_format="حوالة"))
        assert resp.status_code == 422

    def test_negative_amount_rejected(self):
        resp = ingest(make_tx(amount=-5.0))
        assert resp.status_code == 422

    def test_unparseable_timestamp_rejected(self):
        resp = ingest(make_tx(timestamp="12/31/2026 99:99"))
        assert resp.status_code == 422


# ── rolling windows ─────────────────────────────────────────────────────────

class TestRollingWindows:
    def test_1h_and_24h_windows_update_correctly(self):
        # Two inbound transfers 2h before the latest event (24h window only),
        # then three within the last 10 minutes (both windows).
        ingest(make_tx(0, timestamp="2026-06-01T08:00:00",
                       from_account="PSEUDOOLD1", amount=500))
        ingest(make_tx(1, timestamp="2026-06-01T08:05:00",
                       from_account="PSEUDOOLD2", amount=500))
        for i in range(3):
            ingest(make_tx(2 + i, timestamp=f"2026-06-01T09:5{i}:00",
                           from_account=f"PSEUDONEW{i}", amount=1000))

        resp = client.get("/api/features/account/PSEUDOMULE", headers=KEY_A)
        assert resp.status_code == 200
        f = resp.json()["features"]
        assert f["target_in_degree_1h"] == 3
        assert f["target_in_degree_24h"] == 5
        assert f["amount_received_1h"] == 3000.0
        assert f["amount_received_24h"] == 4000.0
        assert f["unique_sources_1h"] == 3

    def test_outbound_and_fan_scores(self):
        total = ingest_fan_in(5)
        # The mule sweeps most of the inflow out, cross-bank.
        ingest(make_tx(99, minute=12, from_account="PSEUDOMULE",
                       to_account="PSEUDOINTL", amount=total * 0.9,
                       to_bank="28856"))
        f = client.get("/api/features/account/PSEUDOMULE", headers=KEY_A).json()["features"]
        assert f["source_out_degree_1h"] == 1
        assert f["fan_in_normalized_1h"] == 1.0  # 5 inbound / 5 cap (renamed from fan_in_score)
        assert f["sweep_after_fan_in_flag"] == 1
        assert f["cross_bank_transfer_count_24h"] == 1
        assert f["unique_targets_1h"] == 1

    def test_events_beyond_24h_are_excluded(self):
        ingest(make_tx(0, timestamp="2026-05-30T10:00:00", amount=9999))
        ingest(make_tx(1, timestamp="2026-06-01T10:00:00", amount=100))
        f = client.get("/api/features/account/PSEUDOMULE", headers=KEY_A).json()["features"]
        assert f["target_in_degree_24h"] == 1
        assert f["amount_received_24h"] == 100.0


# ── node isolation ──────────────────────────────────────────────────────────

class TestNodeIsolation:
    def test_bank_b_cannot_query_bank_a_account(self):
        ingest(make_tx())  # Bank A sees PSEUDOMULE
        resp_a = client.get("/api/features/account/PSEUDOMULE", headers=KEY_A)
        assert resp_a.status_code == 200
        resp_b = client.get("/api/features/account/PSEUDOMULE", headers=KEY_B)
        assert resp_b.status_code == 403
        assert resp_b.json()["detail"] == "Not authorized for this resource or action."

    def test_unknown_account_gets_same_generic_403(self):
        # Cross-node probe and nonexistent account are indistinguishable.
        resp = client.get("/api/features/account/NEVERSEEN", headers=KEY_A)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Not authorized for this resource or action."

    def test_pii_shaped_account_path_is_denied(self):
        resp = client.get("/api/features/account/SA4420000001234567891234",
                          headers=KEY_A)
        assert resp.status_code == 403

    def test_status_is_node_scoped(self):
        ingest(make_tx())
        status_a = client.get("/api/features/status", headers=KEY_A).json()
        status_b = client.get("/api/features/status", headers=KEY_B).json()
        assert status_a["events_in_window"] == 1
        assert status_b["events_in_window"] == 0


# ── contextual scoring ──────────────────────────────────────────────────────

class TestScoreWithContext:
    def _score_sweep(self, amount: float = 11200.0):
        return client.post("/api/features/score-with-context", json={
            "timestamp": BASE_TS.format(m=30),
            "from_bank": "101", "from_account": "PSEUDOMULE",
            "to_bank": "28856", "to_account": "PSEUDOINTL",
            "amount": amount, "currency": "US Dollar", "payment_format": "Wire",
        }, headers=KEY_A)

    def test_requires_api_key(self):
        resp = client.post("/api/features/score-with-context",
                           json={"from_bank": "1", "from_account": "PSEUDOX1",
                                 "to_bank": "1", "to_account": "PSEUDOX2",
                                 "amount": 10.0})
        assert resp.status_code == 401

    def test_returns_contextual_adjustment_after_fan_in(self):
        ingest_fan_in(5)
        resp = self._score_sweep()
        assert resp.status_code == 200
        body = resp.json()
        assert body["contextual_risk_adjustment"] > 0
        assert body["final_contextual_score"] >= body["base_model_score"]
        assert body["final_contextual_score"] == round(
            min(0.99, body["base_model_score"] + body["contextual_risk_adjustment"]), 6
        )
        joined = " ".join(body["explanation"])
        assert "inbound transfers" in joined
        assert "fan-in" in joined
        feats = body["context_features"]
        assert feats["target_in_degree_1h"] == 5
        assert feats["sweep_after_fan_in_flag"] == 1
        assert feats["new_beneficiary_flag"] == 1

    def test_does_not_claim_retraining(self):
        ingest_fan_in(5)
        body = self._score_sweep().json()
        assert body["model_retrained_on_context"] is False
        joined = " ".join(body["explanation"]).lower()
        assert "has not been retrained" in joined

    def test_no_history_falls_back_to_base_score_only(self):
        resp = self._score_sweep()
        assert resp.status_code == 200
        body = resp.json()
        assert body["contextual_risk_adjustment"] == 0.0
        assert body["final_contextual_score"] == body["base_model_score"]
        assert any("No local history" in e for e in body["explanation"])

    def test_source_node_mismatch_is_403(self):
        resp = client.post("/api/features/score-with-context", json={
            "source_node_id": NODE_B,
            "from_bank": "1", "from_account": "PSEUDOX1",
            "to_bank": "1", "to_account": "PSEUDOX2", "amount": 10.0,
        }, headers=KEY_A)
        assert resp.status_code == 403

    def test_pii_in_score_payload_rejected(self):
        resp = client.post("/api/features/score-with-context", json={
            "from_bank": "1", "from_account": "SA4420000001234567891234",
            "to_bank": "1", "to_account": "PSEUDOX2", "amount": 10.0,
        }, headers=KEY_A)
        assert resp.status_code == 422

    def test_response_contains_no_account_handles(self):
        ingest_fan_in(5)
        resp = self._score_sweep()
        assert "PSEUDOMULE" not in resp.text
        assert "PSEUDOINTL" not in resp.text


# ── per-test isolation (paired with the tests above that ingest state) ──────

class TestStoreIsolationBetweenTests:
    def test_store_starts_empty(self):
        # If any previous test's ingests leaked, this account would exist.
        resp = client.get("/api/features/account/PSEUDOMULE", headers=KEY_A)
        assert resp.status_code == 403
        status = client.get("/api/features/status", headers=KEY_A).json()
        assert status["events_in_window"] == 0
        assert status["accounts_tracked"] == 0


# ── snapshot (optional JSONL) ───────────────────────────────────────────────

class TestSnapshot:
    def test_snapshot_roundtrip(self, tmp_path, monkeypatch):
        snap = tmp_path / "features.jsonl"
        monkeypatch.setenv("NASEEJ_FEATURE_SNAPSHOT", str(snap))
        ingest_fan_in(3)
        assert snap.exists()
        # Snapshot lines carry pseudonymous fields only.
        first = json.loads(snap.read_text(encoding="utf-8").splitlines()[0])
        assert set(first) == {"node_id", "transaction_id", "ts", "from_bank",
                              "from_account", "to_bank", "to_account", "amount"}

        feature_store_service.reset()
        assert client.get("/api/features/account/PSEUDOMULE",
                          headers=KEY_A).status_code == 403
        loaded = feature_store_service.restore_from_snapshot()
        assert loaded == 3
        resp = client.get("/api/features/account/PSEUDOMULE", headers=KEY_A)
        assert resp.status_code == 200
        assert resp.json()["features"]["target_in_degree_24h"] == 3


# ── audit log ───────────────────────────────────────────────────────────────

class TestAudit:
    def test_audit_written_for_ingestion_and_scoring(self):
        ingest_fan_in(2)
        client.post("/api/features/score-with-context", json={
            "from_bank": "101", "from_account": "PSEUDOMULE",
            "to_bank": "28856", "to_account": "PSEUDOINTL", "amount": 5000.0,
        }, headers=KEY_A)
        audit = read_audit()
        assert '"action":"feature_ingest"' in audit
        assert '"decision":"accepted"' in audit
        assert '"action":"score_with_context"' in audit

    def test_denials_are_audited(self):
        ingest(make_tx(source_node_id=NODE_B))  # 403
        client.get("/api/features/account/NEVERSEEN", headers=KEY_A)  # 403
        audit = read_audit()
        assert '"decision":"denied"' in audit
        assert "source_node_id does not match" in audit
        assert "not observed locally" in audit

    def test_no_raw_payload_in_audit(self):
        distinctive_amount = 2417.53
        ingest(make_tx(from_account="PSEUDOZQ91", to_account="PSEUDOZQ92",
                       amount=distinctive_amount))
        client.post("/api/features/score-with-context", json={
            "from_bank": "101", "from_account": "PSEUDOZQ91",
            "to_bank": "28856", "to_account": "PSEUDOZQ92",
            "amount": distinctive_amount,
        }, headers=KEY_A)
        audit = read_audit()
        assert "PSEUDOZQ91" not in audit
        assert "PSEUDOZQ92" not in audit
        assert "2417.53" not in audit

    def test_rejected_pii_value_never_reaches_audit(self):
        ingest(make_tx(from_account="SA4420000001234567891234"))
        audit = read_audit()
        assert "SA4420" not in audit
        assert '"decision":"rejected"' in audit


# ── analyze-pattern enrichment ──────────────────────────────────────────────

class TestPatternEnrichment:
    ATTACK = [
        {"from_account": f"PSEUDOSRC{i}", "to_account": "PSEUDOMULE",
         "from_bank": "101", "to_bank": "101", "amount": 2000.0 + i * 100,
         "timestamp": BASE_TS.format(m=i * 2)}
        for i in range(5)
    ] + [{"from_account": "PSEUDOMULE", "to_account": "PSEUDOINTL",
          "from_bank": "101", "to_bank": "28856", "amount": 11200.0,
          "timestamp": BASE_TS.format(m=12)}]

    def test_analyze_pattern_without_store_keeps_old_behaviour(self):
        resp = client.post("/api/analyze-pattern",
                           json={"transactions": self.ATTACK}, headers=KEY_A)
        assert resp.status_code == 200
        assert "context_enrichment" not in resp.json()["graph_summary"]

    def test_analyze_pattern_enriched_after_ingestion(self):
        ingest_fan_in(5)
        ingest(make_tx(99, minute=12, from_account="PSEUDOMULE",
                       to_account="PSEUDOINTL", amount=11200.0, to_bank="28856"))
        resp = client.post("/api/analyze-pattern",
                           json={"transactions": self.ATTACK}, headers=KEY_A)
        assert resp.status_code == 200
        body = resp.json()
        enrichment = body["graph_summary"].get("context_enrichment")
        assert enrichment is not None
        assert enrichment["sweep_after_fan_in_flag"] == 1
        assert enrichment["fan_in_window"]["target_in_degree_1h"] == 5
        types = [p["pattern_type"] for p in body["detected_patterns"]]
        assert "sweep_after_fan_in" in types
        # No handles in the enriched response.
        assert "PSEUDOMULE" not in resp.text

    def test_enrichment_for_other_node_does_not_leak(self):
        ingest_fan_in(5)  # Bank A's history
        resp = client.post("/api/analyze-pattern",
                           json={"transactions": self.ATTACK}, headers=KEY_B)
        assert resp.status_code == 200
        assert "context_enrichment" not in resp.json()["graph_summary"]


# ── catalogue ───────────────────────────────────────────────────────────────

class TestCatalogue:
    def test_catalogue_requires_auth(self):
        assert client.get("/api/features/catalogue").status_code == 401

    def test_catalogue_is_complete(self):
        resp = client.get("/api/features/catalogue", headers=KEY_A)
        assert resp.status_code == 200
        feats = resp.json()["features"]
        assert len(feats) == len(feature_catalogue.CATALOGUE) >= 20
        required = {"feature_name", "description", "entity_type", "refresh_interval",
                    "owner", "lineage", "privacy_level", "allowed_usage",
                    "leakage_risk", "bias_risk", "retention_days"}
        for f in feats:
            assert required <= set(f), f["feature_name"]
            assert f["entity_type"] in feature_catalogue.ENTITY_TYPES
            assert all(str(f[k]).strip() for k in required), f["feature_name"]

    def test_catalogue_covers_spec_features(self):
        names = {f.feature_name for f in feature_catalogue.CATALOGUE}
        for expected in [
            "source_out_degree_1h", "source_out_degree_24h",
            "target_in_degree_1h", "target_in_degree_24h",
            "amount_sent_1h", "amount_sent_24h",
            "amount_received_1h", "amount_received_24h",
            "unique_targets_1h", "unique_sources_1h",
            "cross_bank_transfer_count_24h", "new_beneficiary_flag",
            "beneficiary_age_bucket", "sweep_after_fan_in_flag",
            "fan_in_normalized_1h", "fan_out_normalized_1h", "scatter_gather_score",
            "simple_cycle_score", "account_velocity_zscore",
            "rolling_amount_ratio", "first_seen_delta_bucket",
        ]:
            assert expected in names, expected
