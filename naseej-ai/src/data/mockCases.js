// Offline fallback cases for the investigator view — shown when the
// backend is unreachable. Shape mirrors the backend case object exactly.
// Zero PII: pattern links, bucketed evidence, and role labels only.
// All mock cases are owned by Bank A (the mock identity), matching the
// backend's partitioning rule that a node only sees cases it owns or that
// are explicitly visible to it.

import { THREAT_HASH } from '../config/constants'

export const MOCK_CASES = [
  {
    case_id: 'a1f4c2e8-0d3b-4f6a-9c81-2e5d7b9f0a13',
    pattern_id: '7f3c9a1e-2b4d-4e8f-9a6c-1d5e8b3f7a20',
    pattern_hash: THREAT_HASH,
    typology: 'mule_velocity',
    risk_tier: 'critical',
    risk_score: 0.91,
    confidence: 0.87,
    source_node_id: 'NODE_A7C2F9E1',
    owner_node_id: 'NODE_A7C2F9E1',
    visible_to_node_ids: ['NODE_A7C2F9E1'],
    sharing_scope: 'network_all',
    status: 'open',
    recommended_action: 'freeze_for_review',
    created_at: '2026-06-11T09:44:00.000+00:00',
    updated_at: '2026-06-11T09:44:00.000+00:00',
    assigned_to: null,
    evidence_summary:
      'Fan-in of 5 sub-threshold transfers into a single account within 40 minutes, followed by an international wire sweep of the accumulated balance.',
    analyst_notes: [],
    decision_history: [],
    false_positive_flag: false,
    audit_refs: ['3f6b1a9c2e8d4a7b5c0e9f3d1a8b6c4e2f7a9d3b5e1c8f4a6b2d9e7c3a5f1b8d'],
  },
  {
    case_id: 'b2e5d3f9-1c4a-4b7e-8d92-3f6e8c0a1b24',
    pattern_id: '9a1b3c5d-7e9f-4a2b-8c4d-6e8f0a2b4c6d',
    pattern_hash: 'NSJ_CROSS_BANK_PASS_THROUGH_4e2a9c7f1b8d3e6a',
    typology: 'cross_bank_pass_through',
    risk_tier: 'high',
    risk_score: 0.78,
    confidence: 0.81,
    // Cross-bank story: pattern detected and broadcast by Bank B; this
    // bank (A) matched it locally and opened — and owns — the case.
    source_node_id: 'NODE_B3D8E2F4',
    owner_node_id: 'NODE_A7C2F9E1',
    visible_to_node_ids: ['NODE_A7C2F9E1', 'NODE_B3D8E2F4'],
    sharing_scope: 'network_all',
    status: 'under_review',
    recommended_action: 'escalate_to_compliance',
    created_at: '2026-06-10T14:02:00.000+00:00',
    updated_at: '2026-06-11T08:15:00.000+00:00',
    assigned_to: 'NODE_A7C2F9E1',
    evidence_summary:
      'Inbound institutional transfer forwarded to a second institution within nine minutes of arrival; dwell time inconsistent with stated account purpose.',
    analyst_notes: [
      {
        timestamp: '2026-06-11T08:15:00.000+00:00',
        node_id: 'NODE_A7C2F9E1',
        analyst_role: 'analyst',
        note: 'Pass-through dwell time under ten minutes across three sessions this week. Requesting peer-node pattern statistics before escalation.',
      },
    ],
    decision_history: [
      {
        timestamp: '2026-06-11T08:14:00.000+00:00',
        node_id: 'NODE_A7C2F9E1',
        decision: 'take_under_review',
        reason: 'Matches received network hash; dwell-time bucket warrants manual review.',
        previous_status: 'open',
        new_status: 'under_review',
        analyst_role: 'analyst',
        audit_ref: '5d2c8f1a4b7e9c3d6a0f2b8e4c1d7a9f3e5b0c6d8a2f4e7b1c9d3a5e8f0b2c4d',
      },
    ],
    false_positive_flag: false,
    audit_refs: [
      '8c4e1f7a3b9d5c2e6a8f0d4b7c1e9a3f5d2b8e6c0a4f7d1b9e3c5a8f2d6b0e4c',
      '5d2c8f1a4b7e9c3d6a0f2b8e4c1d7a9f3e5b0c6d8a2f4e7b1c9d3a5e8f0b2c4d',
    ],
  },
  {
    case_id: 'c3f6e4a0-2d5b-4c8f-9ea3-4a7f9d1b2c35',
    pattern_id: 'b2c4d6e8-0a2c-4e6a-9b1d-3c5e7a9b1d3f',
    pattern_hash: 'NSJ_SCATTER_GATHER_9b3e5c7a1d4f8b2e',
    typology: 'scatter_gather',
    risk_tier: 'medium',
    risk_score: 0.46,
    confidence: 0.62,
    source_node_id: 'NODE_A7C2F9E1',
    owner_node_id: 'NODE_A7C2F9E1',
    visible_to_node_ids: ['NODE_A7C2F9E1'],
    sharing_scope: 'local_only',
    status: 'closed_false_positive',
    recommended_action: 'request_step_up_verification',
    created_at: '2026-06-09T11:30:00.000+00:00',
    updated_at: '2026-06-10T10:05:00.000+00:00',
    assigned_to: 'NODE_A7C2F9E1',
    evidence_summary:
      'Outbound split across four recipients followed by reconvergence at a new account within one day; amount buckets consistent across legs.',
    analyst_notes: [
      {
        timestamp: '2026-06-10T10:04:00.000+00:00',
        node_id: 'NODE_A7C2F9E1',
        analyst_role: 'senior_analyst',
        note: 'Pattern explained by a recurring corporate payroll split-and-pool arrangement. Documented as legitimate business behaviour for this segment.',
      },
    ],
    decision_history: [
      {
        timestamp: '2026-06-09T15:20:00.000+00:00',
        node_id: 'NODE_A7C2F9E1',
        decision: 'take_under_review',
        reason: 'Scatter-gather shape with consistent buckets — needs context check.',
        previous_status: 'open',
        new_status: 'under_review',
        analyst_role: 'analyst',
        audit_ref: '2a7d4f9b1e6c8a3d5f0b2e7c9a4d6f1b8e3c5a0d7f2b9e4c6a1d8f3b5e0c7a9d',
      },
      {
        timestamp: '2026-06-10T10:05:00.000+00:00',
        node_id: 'NODE_A7C2F9E1',
        decision: 'mark_false_positive',
        reason: 'Recurring payroll arrangement; structure matches documented business model.',
        previous_status: 'under_review',
        new_status: 'closed_false_positive',
        analyst_role: 'senior_analyst',
        audit_ref: '6e1b8d3f5a9c2e7b4d0f6a8c1e3b9d5f7a2c4e6b8d0f1a3c5e7b9d2f4a6c8e0b',
      },
    ],
    false_positive_flag: true,
    audit_refs: [
      '9f2e5b8c1d4a7f0e3b6c9d2a5f8b1e4c7d0a3f6b9e2c5d8a1f4b7e0c3d6a9f2b',
      '2a7d4f9b1e6c8a3d5f0b2e7c9a4d6f1b8e3c5a0d7f2b9e4c6a1d8f3b5e0c7a9d',
      '6e1b8d3f5a9c2e7b4d0f6a8c1e3b9d5f7a2c4e6b8d0f1a3c5e7b9d2f4a6c8e0b',
    ],
  },
]

// ── Network Intelligence dashboard → Investigator adapter ────────────────────
// Maps a synthetic Priority-Queue row (NSJ-1042 …) onto the exact case shape
// the Investigator view expects, so clicking a dashboard case opens it there
// with full detail. It reuses the existing mock case structure — no duplicate
// case system. The case_id is deterministic (dedupe on repeat clicks) and the
// evidence line is explicitly labelled synthetic so it can't be mistaken for a
// backend case. Owned by the mock identity (Bank A) so it is viewable offline.

const DASH_TYPOLOGY = {
  'Fan-in': 'fan_in',
  'Gather-Scatter': 'gather_scatter',
  Cycle: 'simple_cycle',
}
const DASH_TIER = { Critical: 'critical', High: 'high', Medium: 'medium' }
const DASH_ACTION = {
  'Review Now': 'freeze_for_review',
  Escalate: 'escalate_to_compliance',
  'Analyst Review': 'request_step_up_verification',
  Monitor: 'monitor',
  Observe: 'monitor',
}

export function dashboardCaseId(dashCase) {
  return `dashboard-${dashCase.id}`
}

export function buildDashboardCase(dashCase) {
  const now = new Date().toISOString()
  return {
    case_id: dashboardCaseId(dashCase),
    pattern_id: `dashboard-pattern-${dashCase.id}`,
    pattern_hash: `NSJ_${(dashCase.patternTag || 'velocity_anomaly').toUpperCase().replace(/[^A-Z]/g, '_')}_synthetic`,
    typology: DASH_TYPOLOGY[dashCase.patternTag] || 'mule_velocity',
    risk_tier: DASH_TIER[dashCase.status] || 'medium',
    risk_score: dashCase.risk,
    confidence: dashCase.risk,
    source_node_id: 'NODE_A7C2F9E1',
    owner_node_id: 'NODE_A7C2F9E1',
    visible_to_node_ids: ['NODE_A7C2F9E1'],
    sharing_scope: dashCase.crossBank ? 'network_all' : 'local_only',
    status: 'open',
    recommended_action: DASH_ACTION[dashCase.action] || 'monitor',
    created_at: now,
    updated_at: now,
    assigned_to: null,
    evidence_summary:
      `[SYNTHETIC DASHBOARD CASE — illustrative, not a backend case] ${dashCase.bank} · ${dashCase.pattern} pattern` +
      `${dashCase.crossBank ? ' with a confirmed cross-bank match' : ' (local detection only)'}. ` +
      'Bucketed, zero-PII synthetic evidence for demonstration of the analyst hand-off.',
    analyst_notes: [],
    decision_history: [],
    false_positive_flag: false,
    audit_refs: [],
    synthetic_dashboard: true,
  }
}

// Locally-built case used when the demo's BLOCKED stage fires while the
// backend is offline — keeps the demo → investigator story intact.
export function buildLocalDemoCase() {
  const now = new Date().toISOString()
  return {
    case_id: (crypto.randomUUID && crypto.randomUUID()) || `local-${Date.now()}`,
    pattern_id: (crypto.randomUUID && crypto.randomUUID()) || `local-p-${Date.now()}`,
    pattern_hash: THREAT_HASH,
    typology: 'mule_velocity',
    risk_tier: 'critical',
    risk_score: 0.91,
    confidence: 0.87,
    source_node_id: 'NODE_A7C2F9E1',
    owner_node_id: 'NODE_A7C2F9E1',
    visible_to_node_ids: ['NODE_A7C2F9E1'],
    sharing_scope: 'network_all',
    status: 'open',
    recommended_action: 'freeze_for_review',
    created_at: now,
    updated_at: now,
    assigned_to: null,
    evidence_summary:
      'Live simulation detection: fan-in of 5 sub-threshold transfers into a single account, followed by an international wire sweep flagged at the receiving node for analyst review.',
    analyst_notes: [],
    decision_history: [],
    false_positive_flag: false,
    audit_refs: [],
  }
}
