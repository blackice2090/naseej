// Naseej demo — all user-facing copy, kept honest by design.
//
// Wording rules (enforced here, not scattered through components):
//  - This is a research prototype: say "aligned" / "by design", never
//    "certified" or "compliant" as a finished claim.
//  - The network shares zero-PII pattern hashes; it is not federated
//    learning, so the copy must not claim FL.

import { STAGES } from './constants'

export const BRAND = {
  nameEn: 'NASEEJ',
  nameAr: 'نسيج',
  tagline: 'PRIVACY-PRESERVING CROSS-BANK AML & FRAUD INTELLIGENCE',
  status: 'RESEARCH PROTOTYPE · SYNTHETIC DATA',
}

export const COMPLIANCE_FOOTER = 'PDPL-BY-DESIGN · SAMA COUNTER-FRAUD ALIGNED · ZERO-PII EXCHANGE'

export const NETWORK_STATUS = 'PATTERN NETWORK · SIMULATED · 2 NODES'

// Network Intelligence view spans four fictional bank nodes (the demo itself
// is a two-node Bank A → Bank B story, so that wording stays on the Demo tab).
export const NETWORK_STATUS_INTEL = 'PATTERN NETWORK · SIMULATED · 4 NODES'

export const STAGE_LABELS = {
  [STAGES.IDLE]:         'IDLE — Normal transactions flowing',
  [STAGES.ATTACK]:       'ATTACK — Mule pattern injection in progress',
  [STAGES.DETECTED]:     'DETECTED — Graph analytics engine triggered',
  [STAGES.BROADCASTING]: 'BROADCASTING — Zero-PII pattern hash propagating',
  [STAGES.BLOCKED]:      'FLAGGED — Matching transaction escalated at Bank B',
}

export const ALERT_BANNER = {
  title: 'MULE PATTERN DETECTED — Coordinated Velocity Breach',
  subtitle: 'Graph Analytics Engine Triggered · Topological Anomaly Confirmed · Generating Zero-PII Pattern Hash',
}

export const HASH_PANEL = {
  label: 'PATTERN HASH ENGINE · CRYPTOGRAPHIC OUTPUT',
  verified: 'ZERO-PII VERIFIED · No names, accounts, or identities in this hash',
}

export const BANK_A = {
  title: 'BANK A — DETECTING NODE',
  monitoring: 'MONITORING',
  feedLabel: 'LIVE TRANSACTION FEED',
  graphLabel: 'GRAPH ANALYTICS — MULE NETWORK MAP',
}

export const BANK_B = {
  title: 'BANK B — RECEIVING NODE',
  logLabel: 'NASEEJ THREAT INTELLIGENCE FEED',
  feedLabel: 'LIVE TRANSACTION FEED',
  statusByStage: {
    idle: 'LISTENING',
    ingesting: 'INGESTING PATTERN',
    blocked: 'MATCH FLAGGED',
  },
  blockedTitle: 'HIGH-RISK MATCH FLAGGED — Cross-Bank Pattern Match',
  blockedSubtitle: 'Zero PII transmitted · Hash matched before execution · PDPL-aligned by design',
  listeningFooter: 'NASEEJ NETWORK LISTENING · Zero PII exchanged · Pattern hashes only',
}

// Bank B intelligence feed lines, keyed by simulation stage.
export const INTEL_FEED = {
  [STAGES.IDLE]: [
    { text: '► Naseej node sync... OK',                              color: '#7c4dff' },
    { text: '► Awaiting threat hashes from network...',              color: '#7c4dff' },
    { text: '► No threats ingested · Privacy preserved',             color: '#444' },
  ],
  [STAGES.ATTACK]: [
    { text: '► Naseej node sync... OK',                              color: '#7c4dff' },
    { text: '► Elevated activity detected at peer node...',          color: '#aaa' },
  ],
  [STAGES.DETECTED]: [
    { text: '► Naseej node sync... OK',                              color: '#7c4dff' },
    { text: '► Receiving threat intelligence package...',            color: '#aaa' },
    { text: '► Validating cryptographic hash signature...',          color: '#aaa', pulse: true },
  ],
  [STAGES.BROADCASTING]: [
    { text: '► Naseej pattern hash received from Bank A',            color: '#00e676' },
    { text: '► Topological pattern match initiated...',              color: '#7c4dff', pulse: true },
    { text: '► Zero PII received · PDPL-aligned exchange',           color: '#00e676' },
  ],
  [STAGES.BLOCKED]: [
    { text: '► Naseej pattern hash received from Bank A',            color: '#00e676' },
    { text: '► Topological match CONFIRMED on TX#ACC_01',            color: '#00e676' },
    { text: '► HIGH-RISK MATCH FLAGGED — Human review required',      color: '#ff4d6b', bold: true },
    { text: '► Privacy maintained · Zero PII crossed the boundary',  color: '#00e676' },
  ],
}

export const ML_CARD = {
  badge: 'ML BASELINE',
  model: 'XGBoost AML',
  context: 'AMLworld synthetic data · 0.102% laundering prevalence · graph + velocity features.',
  governance: 'Analyst triage only · Human review required before any blocking decision.',
}

// Feature-store context strip. Honesty rules apply: the contextual score is
// a deterministic rule layer over the baseline model — the model has NOT
// been retrained on these features, so the copy never claims it has.
export const CONTEXT_FEATURES = {
  label: 'CONTEXT FEATURES',
  live: 'LIVE',
  offline: 'OFFLINE',
  sectionTitle: 'CONTEXT SCORE',
  simulatedTag: 'SIMULATED',
  honesty: 'Rule layer over baseline · model not retrained',
}

// Model-evidence card. Reads the offline ML evaluation reports
// (ml/reports/model_comparison.json etc.). Honesty rules apply: this is a
// synthetic-benchmark comparison, not production validation, and the numbers
// come from a temporal-split protocol distinct from the deployed baseline.
export const MODEL_EVIDENCE = {
  title: 'EVALUATION EVIDENCE',
  subtitle: 'LightGBM vs XGBoost · per-typology recall · context ablation',
  honesty: 'Synthetic AMLworld benchmark · temporal split · not production validation',
  lightgbmYes: 'LightGBM evaluated',
  lightgbmNo: 'LightGBM skipped (dependency unavailable)',
}

// Shadow-candidate card. Reads ml/reports/candidate_model_metrics.json via
// /api/model/candidate/metrics. Honesty rules apply: the candidate is trained
// on approved parity-clean features only (no identity encodings) and is NOT
// deployed — it never replaces the live baseline model.
export const CANDIDATE_MODEL = {
  title: 'CANDIDATE MODEL',
  status: 'SHADOW ONLY — NOT DEPLOYED',
  featureNote: 'Approved parity-clean features only · identity encodings excluded',
}

// Shadow-monitoring row. Reads node-scoped, bucketed aggregate observations
// from /api/model/candidate/shadow-monitoring. Honesty rules apply: this is
// prototype monitoring on synthetic shadow scores — never a deployment signal,
// and it stores no raw transactions, identifiers, or feature values.
export const SHADOW_MONITORING = {
  title: 'SHADOW MONITORING',
  label: 'PROTOTYPE MONITORING — NO DEPLOYMENT DECISION',
}

// Governance evidence strip. Reads /api/demo/governance-evidence. Honesty
// rules apply: PDPL-by-design and SAMA-aligned prototype only — never
// "certified" or "production-ready". The warning is load-bearing.
export const GOVERNANCE_EVIDENCE = {
  title: 'GOVERNANCE EVIDENCE',
  warning: 'Research prototype · synthetic AMLworld data · not production validation.',
}

// Network Intelligence dashboard. Honesty rules apply: the data is synthetic
// demo data (SYNTHETIC DEMO DATA badge is always shown), the risk status is a
// recommendation only, and no production / certified claims are made.
export const NETWORK_INTEL = {
  titleEn: 'NETWORK INTELLIGENCE',
  titleAr: 'ذكاء الشبكة',
  subtitle: 'A network-level view of suspicious patterns, cross-bank matches, analyst priorities, and privacy compliance.',
  subtitleAr: 'رؤية موحدة للأنماط المشبوهة والتطابقات بين البنوك وأولويات التحقيق والامتثال.',
  syntheticBadgeEn: 'SYNTHETIC DEMO DATA',
  syntheticBadgeAr: 'بيانات تجريبية اصطناعية',
  mapCaption: 'Only fraud-pattern intelligence is exchanged. Raw customer data remains inside each bank.',
  mapCaptionAr: 'يتم تبادل بصمة نمط الاحتيال فقط، بينما تبقى بيانات العملاء داخل كل بنك.',
  decisionArabic: 'توصية النظام: إعطاء الأولوية للحالات الحرجة للمراجعة البشرية دون تنفيذ حظر إنتاجي تلقائي.',
  governanceStatement: 'Every shared payload passes schema validation, zero-PII checks, access control, and audit logging.',
  governanceStatementAr: 'تخضع كل حزمة مشاركة للتحقق من المخطط وفحص البيانات الشخصية والصلاحيات وسجل التدقيق.',
  governanceEvidenceLabel: 'SIMULATED GOVERNANCE EVIDENCE',
  governanceEvidenceLabelAr: 'مؤشرات حوكمة تجريبية',
  storyChips: ['Detect Locally', 'Match Across Banks', 'Review by Analyst'],
}
