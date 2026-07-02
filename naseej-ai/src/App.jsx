// نسيج | Naseej — privacy-preserving cross-bank AML & fraud intelligence demo.
//
// Two views behind one TopNav:
//   DEMO         — the Bank A → Bank B detect/hash/broadcast/block story
//   INVESTIGATOR — analyst case queue (human-in-the-loop review)
//
// When the demo reaches BLOCKED, the detection becomes a reviewable case:
// live backend → register pattern + open case through the real gated API;
// offline → a local mock case, so the story holds either way.

import { useState, useEffect, useRef } from 'react'
import { STAGES } from './config/constants'
import { useSimulation } from './hooks/useSimulation'
import { useBackendData } from './hooks/useBackendData'
import { useCases } from './hooks/useCases'
import TopNav from './components/panels/TopNav'
import MLValidationCard from './components/panels/MLValidationCard'
import ModelEvidenceCard from './components/panels/ModelEvidenceCard'
import CandidateModelCard from './components/panels/CandidateModelCard'
import ShadowMonitoringCard from './components/panels/ShadowMonitoringCard'
import GovernanceEvidenceCard from './components/panels/GovernanceEvidenceCard'
import ResearchStrip from './components/panels/ResearchStrip'
import BankAPanel from './components/panels/BankAPanel'
import BankBPanel from './components/panels/BankBPanel'
import ControlBar from './components/panels/ControlBar'
import BroadcastPulse from './components/graph/BroadcastPulse'
import InvestigatorView from './components/investigator/InvestigatorView'

export default function App() {
  const [view, setView] = useState('demo')
  const {
    stage, bankATxs, bankBTxs, blockedTx,
    liveScore, livePattern, liveContextScore, liveShadowScore, run, reset,
  } = useSimulation()
  const { connected, metrics, crossBank, contextLive, evidence, candidate, monitoring, governance } = useBackendData()
  const { cases, identity, usingMock, openCount, decide, addNote, ingestDemoDetection } = useCases()

  // Demo → case bridge: one case per simulation run, created when the
  // block fires. Guarded by a ref so re-renders cannot duplicate it.
  const ingestedRef = useRef(false)
  useEffect(() => {
    if (stage === STAGES.BLOCKED && !ingestedRef.current) {
      ingestedRef.current = true
      ingestDemoDetection(livePattern)
    }
    if (stage === STAGES.IDLE) ingestedRef.current = false
  }, [stage, livePattern, ingestDemoDetection])

  return (
    <div
      className="flex flex-col overflow-hidden select-none"
      style={{ height: '100vh', background: '#07090f', color: 'white' }}
    >
      <TopNav view={view} onViewChange={setView} openCaseCount={openCount} />

      {view === 'demo' ? (
        <>
          <MLValidationCard metrics={metrics} />

          <ModelEvidenceCard evidence={evidence} />

          <CandidateModelCard candidate={candidate} shadow={liveShadowScore} />

          <ShadowMonitoringCard monitoring={monitoring} />

          <GovernanceEvidenceCard governance={governance} />

          <ResearchStrip
            cbData={crossBank}
            scoreData={liveScore}
            patternData={livePattern}
            contextScore={liveContextScore}
            contextLive={contextLive}
            connected={connected}
            stage={stage}
          />

          {/* Split screen: Bank A detects, Bank B blocks */}
          <div className="flex-1 grid grid-cols-2 relative overflow-hidden">
            <BankAPanel
              stage={stage}
              txList={bankATxs}
              metrics={metrics}
              liveHash={livePattern?.pattern_hash}
            />
            <BankBPanel stage={stage} txList={bankBTxs} blockedTx={blockedTx} />
            <BroadcastPulse active={stage === STAGES.BROADCASTING} />
          </div>

          <ControlBar stage={stage} onRun={run} onReset={reset} />
        </>
      ) : (
        <InvestigatorView
          cases={cases}
          usingMock={usingMock}
          onDecide={decide}
          onAddNote={addNote}
          identity={identity}
        />
      )}
    </div>
  )
}
