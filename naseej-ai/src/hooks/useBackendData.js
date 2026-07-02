// Naseej demo — backend enrichment data (model metrics + cross-bank results
// + feature-store availability). Fetched once on mount; the demo never
// blocks on these.

import { useState, useEffect } from 'react'
import {
  fetchModelMetrics, fetchCrossBankResults, fetchFeatureStatus,
  fetchModelComparison, fetchPerTypologyRecall, fetchThresholdAnalysis,
  fetchCandidateMetrics, fetchShadowMonitoring, fetchCalibrationDataset,
  fetchGovernanceEvidence,
} from '../lib/api'

// Condense the governance evidence pack into the compact strip's flags. Always
// returns an object (with safe defaults) so the strip can render a static
// evidence summary even when the backend is offline — these are design
// properties of the prototype, not live-only facts.
function buildGovernance(report) {
  const live = report?.source === 'live'
  const byName = {}
  for (const e of report?.evidence ?? []) byName[e.evidence_name] = e.status
  const cal = byName.calibration_status
  return {
    live,
    zeroPii: byName.zero_pii_posture ?? 'active',
    humanInLoop: byName.human_in_the_loop ?? 'active',
    auditTrail: byName.audit_trail ?? 'active',
    rbac: byName.node_isolation_rbac ?? 'active',
    shadowModel: 'not deployed',
    calibration: cal === 'prototype_ready' ? 'dataset only' : 'not production calibrated',
    productionReady: false,
  }
}

// Condense node-scoped shadow monitoring + calibration into a tiny row object.
// Returns null unless there is at least one observation OR labeled record — so
// the row stays hidden (safe empty state) until there is something to show.
function buildMonitoring(report, calibration) {
  const all = report?.windows?.all
  const hasObs = report?.source === 'live' && all && all.total_shadow_requests >= 1
  const hasLabels = calibration?.source === 'live' && (calibration.labeled_count ?? 0) >= 1
  if (!hasObs && !hasLabels) return null
  return {
    total: all?.total_shadow_requests ?? 0,
    agreementRate: all?.agreement_rate ?? null,
    candidateAlertRate: all?.candidate_alert_rate ?? null,
    missingFeatureRate: all?.missing_feature_rate ?? null,
    driftSignal: report?.drift?.signal ?? 'unavailable',
    // Calibration dataset (CALIBRATION DATASET — NOT PRODUCTION CALIBRATION).
    labeledCount: calibration?.labeled_count ?? 0,
    thresholdMet: calibration?.minimum_label_threshold_met ?? false,
    calibrationStatus: calibration?.status ?? (calibration?.source === 'live' ? 'insufficient_labels' : 'unavailable'),
  }
}

// Condense the shadow-candidate metrics report into a tiny card object.
// Returns null unless the live report is present — the card stays hidden
// when no candidate has been evaluated, so the demo never invents one.
function buildCandidate(report) {
  if (report?.source !== 'live' || !report?.selected_model) return null
  const t = report.selected_test_metrics || {}
  return {
    selectedModel: report.selected_model,
    prAuc: t.pr_auc ?? null,
    f1: t.f1 ?? null,
    featureCount: report.protocol?.feature_count ?? (report.approved_features?.length ?? null),
    deploymentRecommended: report.deployment_recommended === true,
  }
}

// Condense the three evaluation reports into the small evidence object the
// ResearchStrip shows. Live only when the comparison report exists on the
// backend; otherwise null → the UI falls back to the offline snapshot.
function buildEvidence(comparison, typology, thresholds) {
  if (comparison?.source !== 'live' || !comparison?.best_model) return null
  // "Best model by PR-AUC" = the held-out test leader (the unbiased ranking),
  // which the report exposes separately from the validation-selected model.
  const headlineModel = comparison.test_leader || comparison.best_model
  const row = comparison.models?.find(r => r.model === headlineModel)
  const balanced = thresholds?.thresholds?.find(t => t.mode === 'balanced')
  return {
    bestModel: headlineModel,
    prAuc: row?.test?.pr_auc ?? comparison.test_leader_pr_auc ?? null,
    f1: row?.test?.f1 ?? null,
    thresholdMode: balanced ? 'balanced' : null,
    weakestTypology: typology?.weakest_typology ?? null,
    lightgbmEvaluated: comparison.availability?.lightgbm?.available === true,
  }
}

export function useBackendData() {
  const [connected, setConnected] = useState(false)
  const [metrics, setMetrics] = useState(null)
  const [crossBank, setCrossBank] = useState(null)
  const [contextLive, setContextLive] = useState(false)
  const [evidence, setEvidence] = useState(null)
  const [candidate, setCandidate] = useState(null)
  const [monitoring, setMonitoring] = useState(null)
  // Governance flags default to the prototype's design properties so the strip
  // renders even offline; replaced with live status when the backend responds.
  const [governance, setGovernance] = useState(() => buildGovernance(null))

  useEffect(() => {
    Promise.all([
      fetchModelMetrics(), fetchCrossBankResults(), fetchFeatureStatus(),
      fetchModelComparison(), fetchPerTypologyRecall(), fetchThresholdAnalysis(),
      fetchCandidateMetrics(), fetchShadowMonitoring(), fetchCalibrationDataset(),
      fetchGovernanceEvidence(),
    ])
      .then(([m, cb, fs, mc, pt, ta, cand, mon, cal, gov]) => {
        if (m || cb) setConnected(true)
        if (m?.pr_auc != null) setMetrics(m)
        if (cb?.summary?.avg_recall_C_naseej != null) setCrossBank(cb.summary)
        if (fs?.feature_store === 'active') setContextLive(true)
        const ev = buildEvidence(mc, pt, ta)
        if (ev) setEvidence(ev)
        const c = buildCandidate(cand)
        if (c) setCandidate(c)
        const mo = buildMonitoring(mon, cal)
        if (mo) setMonitoring(mo)
        if (gov) setGovernance(buildGovernance(gov))
      })
  }, [])

  return { connected, metrics, crossBank, contextLive, evidence, candidate, monitoring, governance }
}
