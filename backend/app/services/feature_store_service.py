"""Node-scoped in-memory feature store with rolling velocity windows.

Fixes the single-transaction scoring limitation: the existing scorer fills
every history-dependent feature with 0 ("first-time transaction"). This
store keeps a short window of *locally ingested, pseudonymous* transaction
events per node and computes the velocity / counterparty / graph-window
features declared in ``feature_catalogue.py`` on demand.

Privacy boundaries (hard rules, enforced here):

  * State is partitioned by ``node_id``. Bank A's events and features are
    invisible to Bank B — there is no API, public or private, that reads
    across partitions. ``account_seen()`` is the only membership check and
    it is node-scoped.
  * Events carry pseudonymous handles and structural fields only
    (banks, amount, timestamp). Names, IBANs, national IDs, phone numbers
    and free text are rejected upstream by the transaction PII guard and
    have no field to land in here.
  * Feature values never cross the bank boundary. They feed node-local
    scoring and analyst explanations; only the existing zero-PII pattern
    hashes are exchanged.

Time model: all windows are computed relative to the node's latest observed
event timestamp (not the wall clock), so replayed synthetic histories give
reproducible features in tests and demos.

Retention: raw events are pruned past a ~25h horizon (the 24h window plus
margin); first-seen registries are pruned past 30 days. This is in-memory
pruning at demo scale, not a storage retention policy.

Snapshot (optional): when ``NASEEJ_FEATURE_SNAPSHOT`` points at a file,
every accepted event is appended as one JSONL line (same pseudonymous
fields, nothing more) and ``restore_from_snapshot()`` can rebuild the
in-memory state — used for reproducible tests, not as a database.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ..core import config

logger = logging.getLogger(__name__)

WINDOW_1H = timedelta(hours=1)
WINDOW_24H = timedelta(hours=24)
EVENT_HORIZON = timedelta(hours=25)  # 24h window + margin
FIRST_SEEN_HORIZON = timedelta(days=30)

# Sweep-after-fan-in rule: 3+ inbound in 1h, then outbound ≥ 60% of inflow.
FAN_IN_MIN_DEGREE = 3
SWEEP_OUTFLOW_RATIO = 0.6

# Cap on cycle-search work per lookup — demo-scale graphs only.
_CYCLE_EDGE_CAP = 2_000


@dataclass(frozen=True)
class TxEvent:
    transaction_id: str
    ts: datetime
    from_bank: str
    from_account: str
    to_bank: str
    to_account: str
    amount: float

    def snapshot_dict(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "ts": self.ts.isoformat(),
            "from_bank": self.from_bank,
            "from_account": self.from_account,
            "to_bank": self.to_bank,
            "to_account": self.to_account,
            "amount": self.amount,
        }


class _NodeStore:
    """One bank node's private window state. Never read across nodes."""

    def __init__(self) -> None:
        self.events: deque[TxEvent] = deque()
        self.first_seen: dict[str, datetime] = {}
        self.pair_first_seen: dict[tuple[str, str], datetime] = {}
        self.latest_ts: datetime | None = None

    def add(self, ev: TxEvent) -> None:
        self.events.append(ev)
        if self.latest_ts is None or ev.ts > self.latest_ts:
            self.latest_ts = ev.ts
        for handle in (ev.from_account, ev.to_account):
            self.first_seen.setdefault(handle, ev.ts)
        self.pair_first_seen.setdefault((ev.from_account, ev.to_account), ev.ts)
        self._prune()

    def _prune(self) -> None:
        if self.latest_ts is None:
            return
        event_cutoff = self.latest_ts - EVENT_HORIZON
        while self.events and self.events[0].ts < event_cutoff:
            self.events.popleft()
        seen_cutoff = self.latest_ts - FIRST_SEEN_HORIZON
        if len(self.first_seen) > 10_000:
            self.first_seen = {k: v for k, v in self.first_seen.items() if v >= seen_cutoff}
            self.pair_first_seen = {
                k: v for k, v in self.pair_first_seen.items() if v >= seen_cutoff
            }


_lock = threading.Lock()
_stores: dict[str, _NodeStore] = {}


def _store(node_id: str) -> _NodeStore:
    if node_id not in _stores:
        _stores[node_id] = _NodeStore()
    return _stores[node_id]


def reset() -> None:
    """Drop all in-memory state (test isolation; never called by routes)."""
    with _lock:
        _stores.clear()


# ── ingest ──────────────────────────────────────────────────────────────────

_TS_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M",
)


def parse_timestamp(ts: str) -> datetime | None:
    for fmt in _TS_FORMATS:
        try:
            parsed = datetime.strptime(ts, fmt)
            # Windows are computed from deltas, so keep everything naive.
            return parsed.replace(tzinfo=None)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def ingest(node_id: str, *, transaction_id: str, timestamp: str,
           from_bank: str, from_account: str, to_bank: str, to_account: str,
           amount: float) -> dict[str, Any]:
    """Record one pseudonymous event into the node's window state.

    The caller (route layer) has already authenticated the node and run the
    transaction PII guard; this function assumes clean input.
    Raises ValueError on an unparseable timestamp.
    """
    ts = parse_timestamp(timestamp)
    if ts is None:
        raise ValueError("unparseable timestamp")
    ev = TxEvent(
        transaction_id=transaction_id, ts=ts,
        from_bank=str(from_bank), from_account=from_account,
        to_bank=str(to_bank), to_account=to_account, amount=float(amount),
    )
    with _lock:
        store = _store(node_id)
        store.add(ev)
        stats = {
            "events_in_window": len(store.events),
            "accounts_tracked": len(store.first_seen),
        }
    _snapshot_append(node_id, ev)
    return stats


# ── snapshot (optional JSONL, reproducible tests) ───────────────────────────

def _snapshot_path():
    return config.feature_snapshot_path()


def _snapshot_append(node_id: str, ev: TxEvent) -> None:
    path = _snapshot_path()
    if path is None:
        return
    try:
        line = json.dumps({"node_id": node_id, **ev.snapshot_dict()},
                          ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:  # snapshot is best-effort; the store stays in memory
        logger.warning("feature snapshot append failed: %s", exc)


def restore_from_snapshot() -> int:
    """Rebuild in-memory state from the snapshot file. Returns events loaded."""
    path = _snapshot_path()
    if path is None or not path.exists():
        return 0
    loaded = 0
    with _lock:
        _stores.clear()
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                    ts = parse_timestamp(rec["ts"])
                    if ts is None:
                        continue
                    _store(rec["node_id"]).add(TxEvent(
                        transaction_id=rec["transaction_id"], ts=ts,
                        from_bank=rec["from_bank"], from_account=rec["from_account"],
                        to_bank=rec["to_bank"], to_account=rec["to_account"],
                        amount=float(rec["amount"]),
                    ))
                    loaded += 1
                except (KeyError, ValueError, json.JSONDecodeError):
                    logger.warning("feature snapshot: skipping malformed line")
    return loaded


# ── feature computation ─────────────────────────────────────────────────────

def account_seen(node_id: str, account_id: str) -> bool:
    """Has *this node* locally observed the handle? The route layer turns
    False into a generic 403 — cross-node probing gets the same answer as
    a nonexistent account."""
    with _lock:
        store = _stores.get(node_id)
        return bool(store and account_id in store.first_seen)


def _delta_bucket(delta: timedelta | None) -> str:
    if delta is None:
        return "unseen"
    if delta <= WINDOW_1H:
        return "new_0_1h"
    if delta <= WINDOW_24H:
        return "recent_1_24h"
    return "established_gt_24h"


def _cycle_score(events: list[TxEvent], account: str) -> float:
    """1.0 if a 2- or 3-cycle through *account* exists in the window."""
    edges: set[tuple[str, str]] = set()
    for ev in events[-_CYCLE_EDGE_CAP:]:
        edges.add((ev.from_account, ev.to_account))
    out_of = [b for (a, b) in edges if a == account]
    for b in out_of:
        if (b, account) in edges:
            return 1.0  # A→B→A
        for (c1, c2) in edges:
            if c1 == b and (c2, account) in edges:
                return 1.0  # A→B→C→A
    return 0.0


def _compute(store: _NodeStore, account: str, as_of: datetime) -> dict[str, Any]:
    """All catalogue features for one account, as of *as_of*. Lock held."""
    h1 = as_of - WINDOW_1H
    h24 = as_of - WINDOW_24H
    win24 = [ev for ev in store.events if h24 < ev.ts <= as_of]

    out24 = [ev for ev in win24 if ev.from_account == account]
    in24 = [ev for ev in win24 if ev.to_account == account]
    out1 = [ev for ev in out24 if ev.ts > h1]
    in1 = [ev for ev in in24 if ev.ts > h1]

    amount_sent_1h = sum(ev.amount for ev in out1)
    amount_sent_24h = sum(ev.amount for ev in out24)
    amount_received_1h = sum(ev.amount for ev in in1)
    amount_received_24h = sum(ev.amount for ev in in24)

    cross_bank_24h = sum(
        1 for ev in win24
        if account in (ev.from_account, ev.to_account) and ev.from_bank != ev.to_bank
    )

    fan_in = min(1.0, len(in1) / 5.0)
    fan_out = min(1.0, len(out1) / 5.0)

    # Sweep-after-fan-in: meaningful inflow burst, then most of it sent out.
    sweep_flag = 0
    if len(in1) >= FAN_IN_MIN_DEGREE and amount_received_1h > 0:
        if amount_sent_1h >= SWEEP_OUTFLOW_RATIO * amount_received_1h:
            sweep_flag = 1

    # Velocity z-score: current 1h outbound count vs the account's own
    # hourly bins over the prior 24h. Needs ≥3 prior hours to be stable.
    hourly: dict[int, int] = {}
    for ev in out24:
        if ev.ts <= h1:  # prior hours only — exclude the current hour
            bin_idx = int((as_of - ev.ts).total_seconds() // 3600)
            hourly[bin_idx] = hourly.get(bin_idx, 0) + 1
    zscore = 0.0
    if len(hourly) >= 3:
        counts = [hourly.get(i, 0) for i in range(1, 24)]
        mean = sum(counts) / len(counts)
        var = sum((c - mean) ** 2 for c in counts) / len(counts)
        std = math.sqrt(var)
        if std > 0:
            zscore = (len(out1) - mean) / std

    avg_out_amount_24h = (amount_sent_24h / len(out24)) if out24 else 0.0

    first = store.first_seen.get(account)

    return {
        "source_out_degree_1h": len(out1),
        "source_out_degree_24h": len(out24),
        "target_in_degree_1h": len(in1),
        "target_in_degree_24h": len(in24),
        "amount_sent_1h": round(amount_sent_1h, 2),
        "amount_sent_24h": round(amount_sent_24h, 2),
        "amount_received_1h": round(amount_received_1h, 2),
        "amount_received_24h": round(amount_received_24h, 2),
        "unique_targets_1h": len({ev.to_account for ev in out1}),
        "unique_sources_1h": len({ev.from_account for ev in in1}),
        "cross_bank_transfer_count_24h": cross_bank_24h,
        "sweep_after_fan_in_flag": sweep_flag,
        # Renamed (feature-reconciliation sprint) so the online normalised 1h
        # intensity no longer collides with the offline 24h integer count that
        # also used to be called "fan_in_score". See ml/src/feature_contract.py.
        "fan_in_normalized_1h": round(fan_in, 4),
        "fan_out_normalized_1h": round(fan_out, 4),
        "scatter_gather_score": round(math.sqrt(fan_in * fan_out), 4),
        "simple_cycle_score": _cycle_score(win24, account),
        "account_velocity_zscore": round(zscore, 4),
        "first_seen_delta_bucket": _delta_bucket(as_of - first if first else None),
        # Internal helper for transaction-context ratios (not in catalogue).
        "_avg_out_amount_24h": avg_out_amount_24h,
    }


def account_features(node_id: str, account_id: str) -> dict[str, Any] | None:
    """Catalogue features for a locally-seen account, or None if unseen.

    ``as_of`` is the node's latest event timestamp, keeping replayed
    synthetic histories reproducible.
    """
    with _lock:
        store = _stores.get(node_id)
        if store is None or account_id not in store.first_seen or store.latest_ts is None:
            return None
        as_of = store.latest_ts
        feats = _compute(store, account_id, as_of)
    feats.pop("_avg_out_amount_24h", None)
    feats["as_of"] = as_of.isoformat()
    return feats


def transaction_context(node_id: str, *, from_account: str, to_account: str,
                        amount: float, timestamp: str | None,
                        cross_bank: bool) -> dict[str, Any]:
    """Context features for scoring one transaction against the node's
    local history. Always returns a dict; ``history_available`` is False
    when the store has nothing for the source account (the caller then
    falls back to plain single-transaction behaviour)."""
    as_of = parse_timestamp(timestamp) if timestamp else None
    with _lock:
        store = _stores.get(node_id)
        if store is None or store.latest_ts is None:
            return {"history_available": False}
        if as_of is None or as_of < store.latest_ts:
            as_of = store.latest_ts
        src = _compute(store, from_account, as_of) \
            if from_account in store.first_seen else None
        pair_first = store.pair_first_seen.get((from_account, to_account))
        beneficiary_known = to_account in store.first_seen

    if src is None:
        return {"history_available": False}

    avg_out = src.pop("_avg_out_amount_24h", 0.0)
    rolling_ratio = (amount / avg_out) if avg_out > 0 else 1.0

    # The current transaction is not in the store yet (scoring precedes
    # ingestion), so evaluate the sweep rule with it included.
    sweep_now = 0
    received_1h = src["amount_received_1h"]
    if src["target_in_degree_1h"] >= FAN_IN_MIN_DEGREE and received_1h > 0:
        if (src["amount_sent_1h"] + amount) >= SWEEP_OUTFLOW_RATIO * received_1h:
            sweep_now = 1

    beneficiary_bucket = _delta_bucket(
        (as_of - pair_first) if pair_first is not None else None
    )
    # "New" covers both orderings: the pair was never seen (score-then-
    # ingest) or was first seen within the last hour (ingest-then-score).
    new_beneficiary = 1 if beneficiary_bucket in ("unseen", "new_0_1h") else 0

    return {
        "history_available": True,
        "as_of": as_of.isoformat(),
        **{k: v for k, v in src.items() if not k.startswith("_")},
        "sweep_after_fan_in_flag": max(sweep_now, src["sweep_after_fan_in_flag"]),
        "rolling_amount_ratio": round(rolling_ratio, 4),
        "new_beneficiary_flag": new_beneficiary,
        "beneficiary_age_bucket": beneficiary_bucket,
        "beneficiary_seen_locally": beneficiary_known,
        "tx_is_cross_bank": bool(cross_bank),
    }


def node_status(node_id: str) -> dict[str, Any]:
    """Node-scoped store status (the caller sees only its own partition)."""
    with _lock:
        store = _stores.get(node_id)
        if store is None:
            return {"active": True, "events_in_window": 0, "accounts_tracked": 0,
                    "latest_event_ts": None}
        return {
            "active": True,
            "events_in_window": len(store.events),
            "accounts_tracked": len(store.first_seen),
            "latest_event_ts": store.latest_ts.isoformat() if store.latest_ts else None,
        }


# ── pattern-analysis enrichment (used by /api/analyze-pattern) ─────────────

def enrich_pattern_analysis(node_id: str, txs: list[Any]) -> dict[str, Any] | None:
    """Window-based context for a submitted transaction batch.

    Looks at the batch's most central account (highest in-degree within the
    batch) and reports what the node's *local history* adds: fan-in window
    state, sweep-after-fan-in, velocity spikes, cross-bank pass-through.
    Returns None when the store holds no relevant history — the caller then
    keeps the original behaviour unchanged.
    """
    try:
        in_deg: dict[str, int] = {}
        for t in txs:
            in_deg[t.to_account] = in_deg.get(t.to_account, 0) + 1
        if not in_deg:
            return None
        central = max(in_deg, key=lambda k: in_deg[k])
        if not account_seen(node_id, central):
            return None
        feats = account_features(node_id, central)
        if feats is None:
            return None
        return {
            "source": "feature_store",
            "central_account_in_batch": "(pseudonymous, node-local)",
            "fan_in_window": {
                "target_in_degree_1h": feats["target_in_degree_1h"],
                "unique_sources_1h": feats["unique_sources_1h"],
                "fan_in_normalized_1h": feats["fan_in_normalized_1h"],
            },
            "sweep_after_fan_in_flag": feats["sweep_after_fan_in_flag"],
            "high_velocity": feats["account_velocity_zscore"] > 2.0
            or feats["source_out_degree_1h"] + feats["target_in_degree_1h"] >= 6,
            "cross_bank_pass_through": feats["cross_bank_transfer_count_24h"] >= 2
            and feats["sweep_after_fan_in_flag"] == 1,
            "account_velocity_zscore": feats["account_velocity_zscore"],
            "cross_bank_transfer_count_24h": feats["cross_bank_transfer_count_24h"],
        }
    except Exception as exc:  # enrichment must never break the endpoint
        logger.warning("feature-store enrichment failed: %s", exc)
        return None
