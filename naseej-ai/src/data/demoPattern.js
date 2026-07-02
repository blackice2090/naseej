// Builds a schema-valid threat pattern object from the demo's live
// /api/analyze-pattern result, so the BLOCKED stage can exercise the real
// pipeline: register pattern (schema + zero-PII gates) → open case.
//
// Everything here is bucketed/structural — the demo attack's fixed shape
// (5-source fan-in + sweep) expressed in the contract's vocabulary.

const VALID_TYPOLOGIES = [
  'fan_in', 'fan_out', 'simple_cycle', 'mule_velocity',
  'rapid_sweep', 'cross_bank_pass_through', 'scatter_gather', 'gather_scatter',
]

export function buildDemoPattern(livePattern) {
  const top = livePattern?.detected_patterns?.[0]
  const typology = VALID_TYPOLOGIES.includes(top?.pattern_type)
    ? top.pattern_type
    : 'mule_velocity'
  // Minute-rounded per the contract (no correlation with a specific tx).
  const detectionTs = new Date().toISOString().slice(0, 16) + ':00Z'

  return {
    pattern_id: crypto.randomUUID(),
    pattern_hash: livePattern.pattern_hash,
    typology,
    graph_signature: {
      node_count: 7,
      edge_count: 6,
      in_degree_sequence: [0, 0, 0, 0, 0, 1, 5],
      out_degree_sequence: [0, 0, 1, 1, 1, 1, 2],
      diameter: 2,
      is_cross_bank: true,
    },
    velocity_features: {
      window_bucket: 'under_1h',
      tx_count_bucket: '2_to_5',
      amount_bucket: '5k_to_25k',
      burst_score_bucket: 'high',
    },
    risk_score: Math.min(Math.max(livePattern.risk_score ?? 0.74, 0), 1),
    confidence: 0.87,
    detection_timestamp: detectionTs,
    source_node_id: 'NODE_A7C2F9E1',
    evidence_summary:
      'Fan-in of 5 sub-threshold transfers into a single account within 40 minutes, followed by an international wire sweep of the accumulated balance.',
    privacy_guarantees: {
      zero_pii_verified: true,
      bucketing_version: 'buckets-v1',
      hash_algorithm: 'sha256-canonical-json-v1',
      k_anonymity_floor: 5,
    },
    governance_tags: {
      sharing_scope: 'network_all',
      retention_days: 90,
      requires_human_review: true,
      regulatory_basis: 'SAMA-CFF-early-warning',
    },
  }
}
