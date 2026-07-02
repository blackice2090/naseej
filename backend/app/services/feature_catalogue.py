"""Feature catalogue — the documented contract for every feature the
node-local feature store computes.

Each entry answers, in one place: what the feature means, which entity it
describes, how fresh it is, who owns its definition, where its values come
from (lineage), how sensitive it is, what it may be used for, and what could
go wrong (leakage / bias). The catalogue is the single source of truth: the
store computes only features declared here, and ``docs/FEATURE_STORE.md``
renders this same content for humans.

Privacy levels (most → least restrictive):

  pseudonymous-event      derived from individual pseudonymous transaction
                          events; never leaves the owning node.
  pseudonymous-aggregate  windowed counts/sums keyed on a pseudonymous
                          handle; never leaves the owning node.
  bucketed-aggregate      coarse buckets / flags safe for explanations
                          shown to the node's own analysts.

Nothing in this catalogue is approved for cross-node exchange. Only the
existing zero-PII pattern hashes cross the bank boundary; feature values
stay inside the node that computed them.

Research-prototype caveats: refresh is event-driven (recomputed on each
ingest/lookup, no batch pipeline), the owner is a placeholder team label,
and retention is enforced as in-memory pruning, not a storage policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

ENTITY_TYPES = ("account", "counterparty", "bank_node", "transaction", "graph_window")

# Single owner for the prototype — there is no team split yet. Kept as a
# field so per-feature ownership can diverge later without a schema change.
_OWNER = "naseej-ml-research (prototype placeholder)"

# All window features derive from the same source. Spelled once.
_WINDOW_LINEAGE = (
    "rolling window over pseudonymous transactions ingested locally via "
    "POST /api/features/ingest-transaction; mirrors the train-time windows in "
    "ml/src/graph_features.py"
)

# Raw window events are pruned after ~1 day; first-seen registries after 30.
_WINDOW_RETENTION_DAYS = 1
_FIRST_SEEN_RETENTION_DAYS = 30


@dataclass(frozen=True)
class FeatureSpec:
    feature_name: str
    description: str
    entity_type: str  # one of ENTITY_TYPES
    refresh_interval: str
    owner: str
    lineage: str
    privacy_level: str
    allowed_usage: str
    leakage_risk: str
    bias_risk: str
    retention_days: int


def _window_feature(
    name: str,
    description: str,
    *,
    entity_type: str = "account",
    privacy_level: str = "pseudonymous-aggregate",
    allowed_usage: str = "node-local risk scoring and analyst explanations; never shared cross-node",
    leakage_risk: str,
    bias_risk: str,
    retention_days: int = _WINDOW_RETENTION_DAYS,
) -> FeatureSpec:
    return FeatureSpec(
        feature_name=name,
        description=description,
        entity_type=entity_type,
        refresh_interval="event-driven (recomputed on each ingest/lookup)",
        owner=_OWNER,
        lineage=_WINDOW_LINEAGE,
        privacy_level=privacy_level,
        allowed_usage=allowed_usage,
        leakage_risk=leakage_risk,
        bias_risk=bias_risk,
        retention_days=retention_days,
    )


_DEGREE_LEAKAGE = (
    "counts keyed on a pseudonymous handle; re-identification requires joining "
    "with the node's own ledger, which already holds the raw data"
)
_AMOUNT_LEAKAGE = (
    "windowed sums could reveal an account's turnover if exposed cross-node; "
    "mitigated by node isolation — values never leave the computing node"
)
_VELOCITY_BIAS = (
    "penalises legitimately bursty accounts (payroll, merchants, charity drives); "
    "must stay an alert signal, never an automatic block"
)
_NEWNESS_BIAS = (
    "penalises new customers and the financially excluded whose history is thin; "
    "bucket thresholds need calibration on real population data before any pilot"
)

CATALOGUE: tuple[FeatureSpec, ...] = (
    # ── degree / velocity windows ─────────────────────────────────────────
    _window_feature(
        "source_out_degree_1h",
        "Number of outbound transfers sent by the account in the trailing 1 hour.",
        leakage_risk=_DEGREE_LEAKAGE, bias_risk=_VELOCITY_BIAS,
    ),
    _window_feature(
        "source_out_degree_24h",
        "Number of outbound transfers sent by the account in the trailing 24 hours.",
        leakage_risk=_DEGREE_LEAKAGE, bias_risk=_VELOCITY_BIAS,
    ),
    _window_feature(
        "target_in_degree_1h",
        "Number of inbound transfers received by the account in the trailing 1 hour.",
        leakage_risk=_DEGREE_LEAKAGE, bias_risk=_VELOCITY_BIAS,
    ),
    _window_feature(
        "target_in_degree_24h",
        "Number of inbound transfers received by the account in the trailing 24 hours.",
        leakage_risk=_DEGREE_LEAKAGE, bias_risk=_VELOCITY_BIAS,
    ),
    _window_feature(
        "amount_sent_1h",
        "Total amount sent by the account in the trailing 1 hour.",
        leakage_risk=_AMOUNT_LEAKAGE, bias_risk=_VELOCITY_BIAS,
    ),
    _window_feature(
        "amount_sent_24h",
        "Total amount sent by the account in the trailing 24 hours.",
        leakage_risk=_AMOUNT_LEAKAGE, bias_risk=_VELOCITY_BIAS,
    ),
    _window_feature(
        "amount_received_1h",
        "Total amount received by the account in the trailing 1 hour.",
        leakage_risk=_AMOUNT_LEAKAGE, bias_risk=_VELOCITY_BIAS,
    ),
    _window_feature(
        "amount_received_24h",
        "Total amount received by the account in the trailing 24 hours.",
        leakage_risk=_AMOUNT_LEAKAGE, bias_risk=_VELOCITY_BIAS,
    ),
    _window_feature(
        "unique_targets_1h",
        "Distinct beneficiary accounts the account sent to in the trailing 1 hour.",
        leakage_risk=_DEGREE_LEAKAGE,
        bias_risk="flags one-to-many payers (e.g. small businesses paying suppliers) as fan-out",
    ),
    _window_feature(
        "unique_sources_1h",
        "Distinct counterparty accounts the account received from in the trailing 1 hour.",
        leakage_risk=_DEGREE_LEAKAGE,
        bias_risk="flags many-to-one collectors (e.g. fundraisers, rent pools) as fan-in",
    ),
    _window_feature(
        "cross_bank_transfer_count_24h",
        "Transfers involving the account in the trailing 24 hours whose source and "
        "destination bank differ.",
        leakage_risk="reveals which banks an account transacts across if exposed; node-isolated",
        bias_risk="penalises customers who legitimately bank with several institutions",
    ),
    # ── counterparty / newness ────────────────────────────────────────────
    _window_feature(
        "new_beneficiary_flag",
        "1 if this transaction is the first transfer ever observed (locally) from "
        "this source account to this beneficiary.",
        entity_type="counterparty",
        privacy_level="bucketed-aggregate",
        leakage_risk="pairwise relationship existence; node-isolated, never exchanged",
        bias_risk=_NEWNESS_BIAS,
        retention_days=_FIRST_SEEN_RETENTION_DAYS,
    ),
    _window_feature(
        "beneficiary_age_bucket",
        "Coarse age of the source→beneficiary relationship: unseen | new_0_1h | "
        "recent_1_24h | established_gt_24h.",
        entity_type="counterparty",
        privacy_level="bucketed-aggregate",
        leakage_risk="coarse relationship age only; node-isolated",
        bias_risk=_NEWNESS_BIAS,
        retention_days=_FIRST_SEEN_RETENTION_DAYS,
    ),
    _window_feature(
        "first_seen_delta_bucket",
        "Coarse time since the account was first observed locally: unseen | new_0_1h | "
        "recent_1_24h | established_gt_24h.",
        privacy_level="bucketed-aggregate",
        leakage_risk="coarse account age only; node-isolated",
        bias_risk=_NEWNESS_BIAS,
        retention_days=_FIRST_SEEN_RETENTION_DAYS,
    ),
    # ── mule-pattern scores (graph window) ────────────────────────────────
    _window_feature(
        "sweep_after_fan_in_flag",
        "1 if the account received 3+ inbound transfers in the trailing 1 hour and "
        "then sent out at least 60% of the received amount.",
        entity_type="graph_window",
        privacy_level="bucketed-aggregate",
        leakage_risk="behavioural flag on a pseudonymous handle; node-isolated",
        bias_risk="matches some legitimate flows (event organisers forwarding collected funds)",
    ),
    _window_feature(
        "fan_in_normalized_1h",
        "Normalised fan-in intensity: min(1, target_in_degree_1h / 5). Renamed from "
        "the ambiguous 'fan_in_score' so it no longer collides with the offline 24h "
        "integer count (fan_in_count_24h). See ml/src/feature_contract.py.",
        entity_type="graph_window",
        leakage_risk=_DEGREE_LEAKAGE, bias_risk=_VELOCITY_BIAS,
    ),
    _window_feature(
        "fan_out_normalized_1h",
        "Normalised fan-out intensity: min(1, source_out_degree_1h / 5). Renamed from "
        "the ambiguous 'fan_out_score' (see fan_in_normalized_1h).",
        entity_type="graph_window",
        leakage_risk=_DEGREE_LEAKAGE, bias_risk=_VELOCITY_BIAS,
    ),
    _window_feature(
        "scatter_gather_score",
        "Geometric mean of fan_in_normalized_1h and fan_out_normalized_1h — high when "
        "the account both collects from many sources and disperses to many targets in the window.",
        entity_type="graph_window",
        leakage_risk=_DEGREE_LEAKAGE,
        bias_risk="payment intermediaries and treasury accounts score high by design of their role",
    ),
    _window_feature(
        "simple_cycle_score",
        "1 if the trailing-24h local transfer graph contains a 2- or 3-cycle through "
        "the account (A→B→A or A→B→C→A), else 0.",
        entity_type="graph_window",
        leakage_risk="reveals existence of circular flows among local handles; node-isolated",
        bias_risk="reciprocal payments between family members or business partners form benign cycles",
    ),
    # ── derived statistics ────────────────────────────────────────────────
    _window_feature(
        "account_velocity_zscore",
        "Z-score of the current 1-hour outbound count against the account's own "
        "hourly counts over the trailing 24 hours (0 when history is too thin).",
        leakage_risk=_DEGREE_LEAKAGE,
        bias_risk="thin history makes the z-score unstable; gated to 0 below 3 hours of history",
    ),
    _window_feature(
        "rolling_amount_ratio",
        "For a transaction: its amount relative to the source account's average "
        "outbound amount in the trailing 24 hours (1.0 when no history).",
        entity_type="transaction",
        leakage_risk=_AMOUNT_LEAKAGE,
        bias_risk="first large legitimate purchase (car, rent deposit) spikes the ratio",
    ),
)

CATALOGUE_BY_NAME: dict[str, FeatureSpec] = {f.feature_name: f for f in CATALOGUE}


def as_dicts() -> list[dict]:
    """Serializable catalogue for the API and docs."""
    return [asdict(f) for f in CATALOGUE]
