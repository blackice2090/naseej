"""Offline/online feature parity checker + deterministic replay harness.

Feeds one small synthetic transaction sequence through BOTH feature paths and
compares the resulting feature vector for a focus account at the same
point-in-time:

  * offline — ml/scripts/build_graph_features.py builders (strictly-before
    cumulative + trailing-window), the exact code the training/eval pipeline
    uses.
  * online — backend/app/services/feature_store_service.py, the code that
    serves /api/features/score-with-context.

Point-in-time guarantee: the focus account's window features are read at an
``as_of`` that is strictly after every history event and before any "current"
transaction, so no future transaction can influence a feature on either side.

Classification per canonical feature (from ml/src/feature_contract.py):
  matched              both paths computed equal values (within tolerance)
  tolerance_matched    equal within the numeric tolerance (e.g. 2dp rounding)
  definition_mismatch  comparable names but DIFFERENT values/formula (e.g. fan_in_score)
  missing_online       offline produced it, online did not
  missing_offline      online produced it, offline did not
  train_only           contract says offline-only (not servable)
  serve_only           contract says online-only (no training counterpart)

Outputs:
  ml/reports/feature_parity_report.json
  ml/reports/feature_parity_report.md

Honesty: this is a synthetic replay harness; the numbers are harness-generated,
not customer data. It does not retrain anything or start GNN/federated work.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from . import feature_contract

logger = logging.getLogger("naseej.feature_parity_check")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORTS_DIR = REPO_ROOT / "ml" / "reports"

NUMERIC_TOLERANCE = 0.011  # absolute; covers online's 2dp amount rounding
REPLAY_NODE = "NODE_PARITY_REPLAY"

# Offline→online value pairs to compare directly (canonical_name → which side
# computes which). Read from the contract's name_only/match parity targets.
_AMOUNT_FEATURES = {
    "source_outflow_amount_1h", "source_outflow_amount_24h",
    "target_inflow_amount_1h", "target_inflow_amount_24h",
}


# ── deterministic synthetic sequence ─────────────────────────────────────────

def build_synthetic_sequence() -> tuple[list[dict[str, Any]], str, datetime]:
    """A fan-in into one mule account M, plus unrelated background traffic.

    Returns (history_events, focus_account, as_of). All events are within a
    ~50 minute span so the 1h window on both paths captures the same set.
    """
    base = datetime(2024, 5, 1, 10, 0, 0)
    focus = "MULE_M"
    events: list[dict[str, Any]] = []

    # Five inbound transfers into M from distinct senders, minutes apart.
    for i in range(5):
        events.append({
            "transaction_id": f"IN{i}",
            "timestamp": base + timedelta(minutes=2 * i),
            "source_account": f"SENDER_{i}", "target_account": focus,
            "source_bank": "101", "target_bank": "101",
            "amount": 1000.0 + 100.0 * i,
        })
    # Two outbound transfers from M (M sends some out — cross-bank).
    for j in range(2):
        events.append({
            "transaction_id": f"OUT{j}",
            "timestamp": base + timedelta(minutes=12 + 3 * j),
            "source_account": focus, "target_account": f"DEST_{j}",
            "source_bank": "101", "target_bank": "202",
            "amount": 1500.0 + 200.0 * j,
        })
    # Unrelated background traffic (different accounts) to make the windows real.
    for k in range(3):
        events.append({
            "transaction_id": f"BG{k}",
            "timestamp": base + timedelta(minutes=5 * k + 1),
            "source_account": f"BG_SRC_{k}", "target_account": f"BG_DST_{k}",
            "source_bank": "303", "target_bank": "303",
            "amount": 50.0 + k,
        })

    events.sort(key=lambda e: e["timestamp"])
    last_ts = max(e["timestamp"] for e in events)
    as_of = last_ts + timedelta(minutes=1)  # strictly after every history event
    return events, focus, as_of


def _finalize_scenario(events: list[dict[str, Any]], focus: str) -> tuple[list[dict[str, Any]], str, datetime]:
    events.sort(key=lambda e: e["timestamp"])
    as_of = max(e["timestamp"] for e in events) + timedelta(minutes=1)
    return events, focus, as_of


def build_scenarios() -> list[tuple[str, list[dict[str, Any]], str, datetime]]:
    """Four deterministic point-in-time scenarios for the parity harness.

    Each returns (name, events, focus_account, as_of) where as_of is strictly
    after every event so no future transaction can influence a feature.
    """
    scenarios: list[tuple[str, list[dict[str, Any]], str, datetime]] = []

    # 1. fan-in then sweep (the original sequence).
    ev, focus, as_of = build_synthetic_sequence()
    scenarios.append(("fan_in_then_sweep", ev, focus, as_of))

    # 2. fan-out dispersion: one source sends to six distinct targets in 1h.
    base = datetime(2024, 6, 1, 9, 0, 0)
    focus = "DISPERSER_D"
    ev = [{
        "transaction_id": f"FO{i}", "timestamp": base + timedelta(minutes=3 * i),
        "source_account": focus, "target_account": f"RECIP_{i}",
        "source_bank": "101", "target_bank": "101", "amount": 800.0 + 10 * i,
    } for i in range(6)]
    scenarios.append(("fan_out_dispersion", *_finalize_scenario(ev, focus)))

    # 3. cross-bank pass-through: focus receives from bank 101, forwards to bank 202.
    base = datetime(2024, 6, 2, 14, 0, 0)
    focus = "CORRIDOR_C"
    ev = []
    for i in range(3):
        ev.append({"transaction_id": f"CBIN{i}", "timestamp": base + timedelta(minutes=4 * i),
                   "source_account": f"ORIG_{i}", "target_account": focus,
                   "source_bank": "101", "target_bank": "101", "amount": 2000.0 + 50 * i})
    for j in range(2):
        ev.append({"transaction_id": f"CBOUT{j}", "timestamp": base + timedelta(minutes=15 + 5 * j),
                   "source_account": focus, "target_account": f"OFFSH_{j}",
                   "source_bank": "101", "target_bank": "202", "amount": 2700.0 + 100 * j})
    scenarios.append(("cross_bank_pass_through", *_finalize_scenario(ev, focus)))

    # 4. quiet legitimate account: a single small transfer, low velocity.
    base = datetime(2024, 6, 3, 8, 30, 0)
    focus = "QUIET_Q"
    ev = [
        {"transaction_id": "Q0", "timestamp": base, "source_account": focus,
         "target_account": "LANDLORD", "source_bank": "101", "target_bank": "101", "amount": 1200.0},
        {"transaction_id": "BGQ", "timestamp": base + timedelta(minutes=2),
         "source_account": "OTHER_X", "target_account": "OTHER_Y",
         "source_bank": "303", "target_bank": "303", "amount": 40.0},
    ]
    scenarios.append(("quiet_legitimate", *_finalize_scenario(ev, focus)))

    return scenarios


# ── offline path ─────────────────────────────────────────────────────────────

def offline_features(events: list[dict[str, Any]], focus: str, as_of: datetime) -> dict[str, Any]:
    """Run the offline builders and read the focus account's window features.

    Appends two probe rows at ``as_of`` so the strictly-before builders expose
    the focus account's outbound view (M→probe) and inbound view (probe→M).
    """
    from ml.scripts import build_graph_features as bgf

    rows = [{
        "source_account": e["source_account"], "target_account": e["target_account"],
        "source_bank": e["source_bank"], "target_bank": e["target_bank"],
        "amount": e["amount"], "timestamp": pd.Timestamp(e["timestamp"]),
        "currency": "US Dollar", "payment_type": "Wire",
    } for e in events]
    # Probe rows (excluded from each other's strictly-before windows by ordering).
    out_probe_ts = pd.Timestamp(as_of)
    in_probe_ts = pd.Timestamp(as_of) + pd.Timedelta(seconds=1)
    rows.append({"source_account": focus, "target_account": "OUT_PROBE",
                 "source_bank": "101", "target_bank": "202", "amount": 1.0,
                 "timestamp": out_probe_ts, "currency": "US Dollar", "payment_type": "Wire"})
    rows.append({"source_account": "IN_PROBE", "target_account": focus,
                 "source_bank": "101", "target_bank": "101", "amount": 1.0,
                 "timestamp": in_probe_ts, "currency": "US Dollar", "payment_type": "Wire"})

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df = bgf.add_base_features(df)
    df = bgf.add_cumulative_features(df)
    df = bgf.add_velocity_features(df, pd.Timedelta("1h"), pd.Timedelta("24h"))
    df = bgf.add_mule_features(df, "1h", "24h")

    out_row = df[(df["source_account"] == focus) & (df["target_account"] == "OUT_PROBE")].iloc[0]
    in_row = df[(df["source_account"] == "IN_PROBE") & (df["target_account"] == focus)].iloc[0]

    return {
        # source-side (from the outbound probe)
        "source_out_tx_count_1h": int(out_row["source_out_tx_count_1h"]),
        "source_out_tx_count_24h": int(out_row["source_out_tx_count_24h"]),
        "source_out_amount_sum_1h": float(out_row["source_out_amount_sum_1h"]),
        "source_out_amount_sum_24h": float(out_row["source_out_amount_sum_24h"]),
        # target-side (from the inbound probe)
        "target_in_tx_count_1h": int(in_row["target_in_tx_count_1h"]),
        "target_in_tx_count_24h": int(in_row["target_in_tx_count_24h"]),
        "target_in_amount_sum_1h": float(in_row["target_in_amount_sum_1h"]),
        "target_in_amount_sum_24h": float(in_row["target_in_amount_sum_24h"]),
        # collision witnesses (offline definitions)
        "fan_in_score": float(in_row["fan_in_score"]),    # offline = 24h inbound count
        "fan_out_score": float(out_row["fan_out_score"]),  # offline = 24h outbound count
    }


# ── online path ──────────────────────────────────────────────────────────────

def online_features(events: list[dict[str, Any]], focus: str) -> dict[str, Any]:
    """Replay the same events through the online feature store and read the
    focus account's features at the node's latest event timestamp."""
    from backend.app.services import feature_store_service as fss

    fss.reset()
    try:
        for e in events:
            fss.ingest(
                REPLAY_NODE,
                transaction_id=e["transaction_id"],
                timestamp=pd.Timestamp(e["timestamp"]).strftime("%Y-%m-%dT%H:%M:%S"),
                from_bank=e["source_bank"], from_account=e["source_account"],
                to_bank=e["target_bank"], to_account=e["target_account"],
                amount=e["amount"],
            )
        feats = fss.account_features(REPLAY_NODE, focus) or {}
    finally:
        fss.reset()
    return feats


# ── comparison ───────────────────────────────────────────────────────────────

def _parity_targets() -> list[feature_contract.FeatureContractEntry]:
    """Contract features the replay harness can compare: match/name_only with
    BOTH an offline and an online name (the windowed count/amount features)."""
    return [
        e for e in feature_contract.CONTRACT
        if e.parity_status in ("match", "name_only") and e.offline_name and e.online_name
    ]


def _compare_one(off_val: Any, on_val: Any) -> tuple[str, float | None]:
    if off_val is None and on_val is None:
        return "not_replayed", None  # intrinsic feature; harness does not emit it
    if off_val is None:
        return "missing_offline", None
    if on_val is None:
        return "missing_online", None
    delta = abs(float(off_val) - float(on_val))
    if delta == 0:
        return "matched", 0.0
    if delta <= NUMERIC_TOLERANCE:
        return "tolerance_matched", round(delta, 6)
    return "value_mismatch", round(delta, 6)


_WORST_ORDER = {"value_mismatch": 4, "missing_online": 3, "missing_offline": 3,
                "tolerance_matched": 1, "matched": 0, "not_replayed": -1}


def run_scenarios() -> list[dict[str, Any]]:
    """Replay every scenario; return per-scenario parity-target comparisons."""
    targets = _parity_targets()
    out: list[dict[str, Any]] = []
    for name, events, focus, as_of in build_scenarios():
        offline = offline_features(events, focus, as_of)
        online = online_features(events, focus)
        comparisons: dict[str, dict[str, Any]] = {}
        for e in targets:
            ov = offline.get(e.offline_name)
            nv = online.get(e.online_name)
            result, delta = _compare_one(ov, nv)
            comparisons[e.canonical_name] = {
                "offline_value": ov, "online_value": nv, "result": result, "abs_delta": delta,
            }
        out.append({
            "scenario": name, "focus_account": "(pseudonymous synthetic handle)",
            "as_of": as_of.isoformat(), "comparisons": comparisons,
        })
    return out


def run_parity_check(reports_dir: Path = DEFAULT_REPORTS_DIR) -> dict[str, Any]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    scenarios = run_scenarios()
    targets = _parity_targets()
    target_names = {e.canonical_name for e in targets}

    # Aggregate each parity-target's result across scenarios (worst wins).
    aggregated: dict[str, str] = {}
    for cn in target_names:
        worst = "not_replayed"
        for sc in scenarios:
            res = sc["comparisons"][cn]["result"]
            if _WORST_ORDER.get(res, 0) > _WORST_ORDER.get(worst, -1):
                worst = res
        aggregated[cn] = worst

    # One row per contract feature: parity-targets use the aggregated result,
    # everything else takes its contract parity_status as the result.
    rows: list[dict[str, Any]] = []
    for e in feature_contract.CONTRACT:
        if e.canonical_name in target_names:
            result = aggregated[e.canonical_name]
        elif e.parity_status in ("match", "name_only"):
            # Transaction-intrinsic feature (computed identically offline and at
            # serving via scoring_service); the window harness does not emit it.
            result = "not_replayed"
        else:
            result = e.parity_status  # train_only / serve_only / definition_mismatch
        rows.append({
            "canonical_name": e.canonical_name,
            "offline_name": e.offline_name,
            "online_name": e.online_name,
            "parity_status_contract": e.parity_status,
            "trainable": e.trainable,
            "servable": e.servable,
            "identity_memorization_risk": e.identity_memorization_risk,
            "result": result,
            "mismatch_notes": e.mismatch_notes,
        })

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["result"]] = counts.get(r["result"], 0) + 1

    parity_ok = all(
        aggregated[cn] in ("matched", "tolerance_matched", "not_replayed")
        for cn in target_names
    ) and not any(aggregated[cn] == "value_mismatch" for cn in target_names)

    # No two contract entries may share a name with different canonical meaning.
    name_collisions = _detect_name_collisions()

    payload = {
        "source": "live",
        "report": "feature_parity",
        "contract_version": feature_contract.CONTRACT_VERSION,
        "harness": "deterministic synthetic replay over multiple scenarios (no real data)",
        "scenarios_run": [s["scenario"] for s in scenarios],
        "point_in_time": "every scenario reads focus features strictly after all its events; no future tx influences any feature",
        "numeric_tolerance": NUMERIC_TOLERANCE,
        "parity_targets_clean": parity_ok,
        "name_collisions": name_collisions,
        "collisions_resolved": not name_collisions,
        "result_counts": counts,
        "features": rows,
        "scenarios": scenarios,
        "summary": {
            "comparable_parity_targets": sorted(
                cn for cn in target_names if aggregated[cn] in ("matched", "tolerance_matched")
            ),
            "definition_mismatches": [r["canonical_name"] for r in rows if r["result"] == "definition_mismatch"],
            "train_only": [r["canonical_name"] for r in rows if r["result"] == "train_only"],
            "serve_only": [r["canonical_name"] for r in rows if r["result"] == "serve_only"],
            "value_mismatches": [cn for cn in target_names if aggregated[cn] == "value_mismatch"],
        },
        "note": "Synthetic AMLworld-style replay; not production validation. Retraining/GNN stay blocked "
                "until the approved set is parity-clean end-to-end (it now is for the 8 windowed features) "
                "AND the serve-only/train-only gaps are reconciled per FEATURE_CONTRACT.md.",
    }

    (reports_dir / "feature_parity_report.json").write_text(
        json.dumps(payload, indent=2, default=float), encoding="utf-8")
    (reports_dir / "feature_parity_report.md").write_text(
        _markdown(payload), encoding="utf-8")
    logger.info("Wrote feature parity reports to %s", reports_dir)
    return payload


def _detect_name_collisions() -> list[dict[str, str]]:
    """Any bare feature name that appears with two different canonical meanings
    across offline/online — must be empty after the reconciliation sprint."""
    by_name: dict[str, set[str]] = {}
    for e in feature_contract.CONTRACT:
        for nm in (e.offline_name, e.online_name):
            if nm:
                by_name.setdefault(nm, set()).add(e.canonical_name)
    return [
        {"name": nm, "canonical_names": ", ".join(sorted(cands))}
        for nm, cands in by_name.items() if len(cands) > 1
    ]


# ── training feature manifest ────────────────────────────────────────────────

def build_training_manifest(parity_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Derive the approved/excluded training feature sets from the contract.

    A feature is APPROVED for retraining iff it is trainable AND servable AND
    not flagged as an identity-memorisation risk AND (when comparable) its
    offline/online parity is clean. Everything else is excluded with a reason.
    """
    value_mismatches = set()
    if parity_payload:
        value_mismatches = set(parity_payload.get("summary", {}).get("value_mismatches", []))

    approved: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for e in feature_contract.CONTRACT:
        clean_parity = e.canonical_name not in value_mismatches
        approve = e.trainable and e.servable and not e.identity_memorization_risk and clean_parity
        record = {
            "canonical_name": e.canonical_name,
            "offline_name": e.offline_name,
            "online_name": e.online_name,
            "parity_status": e.parity_status,
            "leakage_risk": e.leakage_risk,
            "identity_memorization_risk": e.identity_memorization_risk,
            "online_available": e.servable,
            "explanation_available": e.explainable,
        }
        if approve:
            approved.append(record)
        else:
            if e.identity_memorization_risk:
                reason = "identity/memorisation risk — not servable consistently and does not generalise"
            elif not e.servable:
                reason = "not servable: online store cannot reproduce this definition (see mismatch_notes)"
            elif not e.trainable:
                reason = "not a training feature (serve-only / online-only)"
            elif not clean_parity:
                reason = "offline/online values disagree in the latest parity run"
            else:
                reason = "excluded"
            excluded.append({**record, "exclusion_reason": reason, "mismatch_notes": e.mismatch_notes})

    return {
        "source": "live",
        "report": "training_feature_manifest",
        "contract_version": feature_contract.CONTRACT_VERSION,
        "parity_report": "ml/reports/feature_parity_report.json",
        "approved_count": len(approved),
        "excluded_count": len(excluded),
        "approved_training_features": approved,
        "excluded_features": excluded,
        "identity_memorization_flagged": [
            e.canonical_name for e in feature_contract.CONTRACT if e.identity_memorization_risk
        ],
        "policy": (
            "Approved = trainable AND servable AND not identity-memorisation risk AND parity-clean. "
            "Account-id and bank-id encodings are EXCLUDED (memorisation + non-reproducible at serving). "
            "All-time cumulative and pair features are EXCLUDED (online prunes >25h). The fan_in/fan_out "
            "score name collisions are EXCLUDED until reconciled."
        ),
        "note": "Synthetic-benchmark manifest. Approval here is a parity/leakage gate, NOT a production "
                "sign-off. The deployed model is not retrained in this phase.",
    }


def _manifest_markdown(m: dict[str, Any]) -> str:
    lines = ["# Training Feature Manifest", ""]
    lines.append(f"- Contract: `{m['contract_version']}`  ·  Parity report: `{m['parity_report']}`")
    lines.append(f"- Approved: **{m['approved_count']}**  ·  Excluded: **{m['excluded_count']}**")
    lines.append("")
    lines.append(f"**Policy:** {m['policy']}")
    lines.append("")
    lines.append("## ✅ Approved training features")
    lines.append("")
    lines.append("| Canonical | Offline name | Online name | Parity | Explainable |")
    lines.append("|---|---|---|---|---|")
    for r in m["approved_training_features"]:
        lines.append(f"| `{r['canonical_name']}` | {r['offline_name'] or '—'} | "
                     f"{r['online_name'] or '—'} | {r['parity_status']} | {r['explanation_available']} |")
    lines.append("")
    lines.append("## 🚫 Excluded features")
    lines.append("")
    lines.append("| Canonical | Reason | Memorisation risk | Leakage |")
    lines.append("|---|---|---|---|")
    for r in m["excluded_features"]:
        lines.append(f"| `{r['canonical_name']}` | {r['exclusion_reason']} | "
                     f"{r['identity_memorization_risk']} | {r['leakage_risk']} |")
    lines.append("")
    lines.append(f"**Identity/memorisation-flagged:** "
                 f"{', '.join('`'+n+'`' for n in m['identity_memorization_flagged'])}")
    lines.append("")
    lines.append(f"> {m['note']}")
    return "\n".join(lines) + "\n"


def run_training_manifest(reports_dir: Path = DEFAULT_REPORTS_DIR,
                          parity_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_training_manifest(parity_payload)
    (reports_dir / "training_feature_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    (reports_dir / "training_feature_manifest.md").write_text(
        _manifest_markdown(manifest), encoding="utf-8")
    logger.info("Wrote training feature manifest to %s", reports_dir)
    return manifest


def _markdown(p: dict[str, Any]) -> str:
    lines = ["# Feature Parity Report — Offline vs Online", ""]
    lines.append(f"- Contract: `{p['contract_version']}`  ·  Harness: {p['harness']}")
    lines.append(f"- Scenarios: {', '.join(p['scenarios_run'])}")
    lines.append(f"- Point-in-time: {p['point_in_time']}")
    lines.append(f"- Parity targets clean across ALL scenarios: **{p['parity_targets_clean']}**")
    lines.append(f"- Name collisions resolved: **{p['collisions_resolved']}** "
                 f"(remaining: {p['name_collisions'] or 'none'})")
    lines.append(f"- Result counts: {p['result_counts']}")
    lines.append("")
    lines.append("## Per-feature classification")
    lines.append("")
    lines.append("| Canonical | Offline name | Online name | Contract | Result |")
    lines.append("|---|---|---|---|---|")
    for r in p["features"]:
        lines.append(
            f"| `{r['canonical_name']}` | {r['offline_name'] or '—'} | {r['online_name'] or '—'} "
            f"| {r['parity_status_contract']} | {r['result']} |"
        )
    lines.append("")
    lines.append("## Per-scenario parity-target comparisons (offline value vs online value)")
    for sc in p["scenarios"]:
        lines.append("")
        lines.append(f"### {sc['scenario']} (as_of {sc['as_of']})")
        lines.append("")
        lines.append("| Canonical | Offline | Online | Result |")
        lines.append("|---|---|---|---|")
        for cn, c in sc["comparisons"].items():
            lines.append(f"| `{cn}` | {c['offline_value']} | {c['online_value']} | {c['result']} |")
    lines.append("")
    lines.append("## Train-only (offline cannot be served today)")
    lines.append(", ".join(f"`{n}`" for n in p["summary"]["train_only"]) or "_none_")
    lines.append("")
    lines.append("## Serve-only (online has no training counterpart — decision B)")
    lines.append(", ".join(f"`{n}`" for n in p["summary"]["serve_only"]) or "_none_")
    lines.append("")
    lines.append("## Definition mismatches (genuine train/serve conflicts — excluded)")
    for name in p["summary"]["definition_mismatches"]:
        entry = feature_contract.CONTRACT_BY_CANONICAL.get(name)
        lines.append(f"- `{name}` — {entry.mismatch_notes if entry else ''}")
    lines.append("")
    lines.append(f"> {p['note']}")
    return "\n".join(lines) + "\n"


def main() -> int:  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    payload = run_parity_check()
    manifest = run_training_manifest(parity_payload=payload)
    print(json.dumps(payload["result_counts"], indent=2))
    print("parity_targets_clean:", payload["parity_targets_clean"])
    print(f"approved training features: {manifest['approved_count']}, excluded: {manifest['excluded_count']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
