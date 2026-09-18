'use client'

import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import ProfileWidget from '@/components/auth/ProfileWidget'
import ChatPanel from './ChatPanel'
import ActivityFeed from './ActivityFeed'
import InfluenceGraph from './InfluenceGraph'
import HistorySidebar from './HistorySidebar'
import { useSim } from './useSim'
import type { MonteCarloState } from './useSim'
import { useSession } from '@/context/SessionContext'
import type { AriaSession, BusinessProfile, SimReport } from './types'

interface Props {
  session: AriaSession
}

const STATUS_LABELS: Record<string, string> = {
  idle: 'Ready', running: 'Running', paused: 'Paused', done: 'Complete',
}
const STATUS_DOT: Record<string, string> = {
  idle: 'var(--gray-400)', running: '#22c55e', paused: '#f59e0b', done: 'var(--accent)',
}

export default function DashboardPage({ session }: Props) {
  const router = useRouter()
  const { logout } = useSession()
  const [profile, setProfile] = useState<BusinessProfile | null>(null)

  // Apply saved theme
  useEffect(() => {
    const saved = localStorage.getItem('aria-theme') || 'burgundy'
    document.body.dataset.theme = saved
  }, [])

  // Load profile from localStorage (same as dashboard.js)
  useEffect(() => {
    try {
      const raw = localStorage.getItem('aria_profile')
      if (raw) setProfile(JSON.parse(raw))
    } catch {}
  }, [])

  const sim = useSim(session.id, profile?.id)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [highlightedAgentId, setHighlightedAgentId] = useState<number | null>(null)
  // Track which run the user is viewing via the Activity Feed pagination
  const [activityFeedPage, setActivityFeedPage] = useState<number>(0)
  // Report from the most recently completed live simulation — shown in the right panel
  const [completedReport, setCompletedReport] = useState<SimReport | null>(null)
  const [completedDescription, setCompletedDescription] = useState<string>('')
  // Controls whether the "thought process" (agent graph + feed) is visible over the loading screen
  // This is user-controlled and should NOT auto-reset when new runs start
  const [showThoughtProcess, setShowThoughtProcess] = useState(false)
  const showThoughtProcessRef = useRef(false) // Persist across runs
  
  // Sync state and ref
  useEffect(() => {
    setShowThoughtProcess(showThoughtProcessRef.current)
  }, [sim.monteCarloState?.current_run])

  // Capture report when a live simulation finishes
  useEffect(() => {
    if (sim.status === 'done' && !sim.isRestoredFromHistory) {
      // Pull the report from the last completed sim snapshot (which contains averaged data for MC)
      const last = sim.completedSims[sim.completedSims.length - 1]
      if (last?.report) {
        const r = last.report
        const rs = r.risk_summary || {}
        setCompletedReport({
          risk_level:          rs.risk_level || 'Unknown',
          churn_rate:          rs.churn_rate ?? 0,
          visit_rate:          rs.visit_rate ?? 0,
          estimated_revenue:   rs.estimated_revenue ?? 0,
          total_agents:        rs.total_agents ?? 0,
          archetype_breakdown: r.archetype_breakdown || {},
          recommendations:     r.recommendations || [],
          analysis:            r.analysis || '',
          key_reasons:         r.key_reasons || [],
        })
        setCompletedDescription(last.scenarioName || '')
      }
    }
    // When a new sim starts, hide thought process and clear report
    if (sim.status === 'running' && sim.agents.length === 0) {
      // Brand new simulation starting
      setShowThoughtProcess(false)
      showThoughtProcessRef.current = false
      setCompletedReport(null)
      setCompletedDescription('')
    }
    // Clear report when state resets to idle
    if (sim.status === 'idle') {
      setCompletedReport(null)
      setCompletedDescription('')
    }
  }, [sim.status, sim.completedSims, sim.isRestoredFromHistory, sim.agents.length])

  function handleLogout() {
    logout()
    router.push('/')
  }

  // Fallback for old simulations that have no saved session_id:
  // inject the report card directly into chat so something is visible
  function injectRestoredReport(snap: typeof sim.history[0]) {
    if (!snap.report || !(window as any).__ariaRestoreMessages) return
    const r = snap.report
    // Use __ariaRestoreMessages with all messages including report metadata
    // so it renders as a rich card (bypasses __ariaAddCompletionMessage which 
    // is guarded by viewingHistoryRef)
    ;(window as any).__ariaRestoreMessages([
      { role: 'user', content: `Run simulation: ${snap.scenarioName}` },
      { role: 'aria', content: `Starting simulation for "${snap.scenarioName}"…\n${snap.description || ''}` },
      {
        role: 'aria',
        content: `Restored: "${snap.scenarioName}"`,
        metadata: {
          report: {
            risk_summary: {
              risk_level:        r.risk_level,
              churn_rate:        r.churn_rate,
              visit_rate:        r.visit_rate,
              estimated_revenue: r.estimated_revenue,
              total_agents:      r.total_agents,
            },
            archetype_breakdown: r.archetype_breakdown,
            breakdown_type:      'income',
            recommendations:     r.recommendations,
            analysis:            r.analysis || '',
            key_reasons:         r.key_reasons || [],
            disclaimer:          "Revenue is estimated from your business price range, adjusted by the scenario's price change.",
            scenario:            { name: snap.scenarioName, description: snap.description },
          },
        },
      },
    ])
  }

  // Progress — accounts for Monte Carlo multi-run structure
  const decidedCount = sim.agents.filter(a => a.last_decision !== null).length
  const mc = sim.monteCarloState
  const progressPct = (() => {
    if (mc && mc.max_runs > 0) {
      // Each run is one equal slice. Within the current run, agent decisions fill the slice.
      const completedRuns = Math.max(0, mc.current_run - 1)  // runs fully finished
      const runSlice = 100 / mc.max_runs
      const withinRunPct = sim.agents.length > 0
        ? (decidedCount / sim.agents.length) * runSlice
        : 0
      return Math.min(99, Math.round(completedRuns * runSlice + withinRunPct))
    }
    // No Monte Carlo — straight agent-decision progress
    return sim.agents.length > 0
      ? Math.round((decidedCount / sim.agents.length) * 100)
      : 0
  })()

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* History sidebar */}
      <HistorySidebar
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        history={sim.history}
        currentSimName={sim.liveScenarioName || undefined}
        currentSimStatus={sim.status !== 'idle' ? sim.status : undefined}
        onGoToCurrent={() => {
          // Resume viewing the live/current simulation
          sim.resumeLive()
          // Restore the live chat panel that was snapshotted when viewing history
          if ((window as any).__ariaRestoreLiveChat) (window as any).__ariaRestoreLiveChat()
        }}
        onRestore={snap => {
          // Always snapshot the live chat before switching to history view
          // so we can restore it when the user goes back to current
          if (!sim.isRestoredFromHistory) {
            if ((window as any).__ariaSnapshotLiveChat) (window as any).__ariaSnapshotLiveChat()
          }

          sim.restoreSnapshot(snap)

          // Signal chat to clear and prepare for restored content
          if ((window as any).__ariaClearForRestore) (window as any).__ariaClearForRestore()

          // Always show the scenario prompt + report directly.
          // Don't fetch full session messages — sessions can contain multiple sims
          // which causes mixed/confusing conversation threads.
          if ((window as any).__ariaRestoreMessages) {
            if (snap.report) {
              // Inject prompt + report as a single batch via injectRestoredReport
              injectRestoredReport(snap)
            } else {
              // No report — just show the scenario prompt
              ;(window as any).__ariaRestoreMessages([
                { role: 'user', content: `Run simulation: ${snap.scenarioName}` },
                { role: 'aria', content: snap.description
                  ? `Starting simulation for "${snap.scenarioName}"…\n${snap.description}`
                  : `Simulation: "${snap.scenarioName}" (no report available for this run)` },
              ])
            }
          }

          setHistoryOpen(false)
        }}
        onDelete={sim.deleteSnapshot}
        onNewChat={() => {
          sim.reset()
          if ((window as any).__ariaNewChat) (window as any).__ariaNewChat()
        }}
      />

      {/* ── Top bar ── matches .dash-header */}
      <header style={{
        position: 'fixed', top: 0, left: 0, right: 0, height: 56,
        background: 'var(--white)',
        borderBottom: '1px solid var(--gray-200)',
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 1.5rem', zIndex: 100,
      }}>
        {/* Left */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {/* History toggle */}
          <button
            onClick={() => setHistoryOpen(o => !o)}
            title="Simulation history"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: historyOpen ? 'var(--accent)' : 'var(--gray-600)',
              padding: '0.25rem', borderRadius: 6,
              display: 'flex', alignItems: 'center',
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--accent)')}
            onMouseLeave={e => (e.currentTarget.style.color = historyOpen ? 'var(--accent)' : 'var(--gray-600)')}
          >
            <svg style={{ width: 20, height: 20 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>

          <Link href="/" style={{
            fontFamily: 'var(--font-display)',
            fontSize: '1.25rem', fontWeight: 900,
            background: 'linear-gradient(135deg, var(--accent), var(--accent-warm))',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            backgroundClip: 'text', textDecoration: 'none',
          }}>
            ARIA
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', color: 'var(--gray-600)' }}>
            <span>{profile?.business_name || 'Your Business'}</span>
            <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
            <span>Simulation</span>
          </div>
        </div>

        {/* Right */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {/* Status pill */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            background: 'var(--gray-100)', borderRadius: 999,
            padding: '0.3rem 0.8rem', fontSize: '0.8rem', fontWeight: 600,
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: sim.isRestoredFromHistory ? 'var(--accent)' : (STATUS_DOT[sim.status] || 'var(--gray-400)'),
              display: 'inline-block',
              animation: (!sim.isRestoredFromHistory && sim.status === 'running') ? 'pulse-dot 1.2s infinite' : 'none',
            }} />
            {sim.isRestoredFromHistory ? 'Viewing History' : (STATUS_LABELS[sim.status] || sim.status)}
          </div>

          {/* Home */}
          <Link href="/" style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: 32, height: 32, borderRadius: 6,
            color: 'var(--gray-600)', textDecoration: 'none',
            transition: 'background 0.15s, color 0.15s',
          }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'var(--gray-100)'; (e.currentTarget as HTMLElement).style.color = 'var(--accent)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; (e.currentTarget as HTMLElement).style.color = 'var(--gray-600)' }}
          >
            <svg style={{ width: 18, height: 18 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
          </Link>

          {/* Profile widget — inline in header, not fixed */}
          <div style={{ position: 'relative' }}>
            <ProfileWidget
              session={session}
              onLogout={handleLogout}
              onEditProfile={() => router.push('/onboarding?edit=1')}
            />
          </div>
        </div>
      </header>

      {/* ── Split layout ── matches .dash-layout */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '380px 1fr',
        height: '100vh',
        paddingTop: 56,
        overflow: 'hidden',
      }}>
        {/* Chat panel */}
        <ChatPanel 
          profile={profile} 
          onLaunch={sim.launch}
          onSimulationComplete={() => {}}
          onReset={sim.reset}
          simulationStatus={sim.isRestoredFromHistory ? 'done' : sim.status}
        />

        {/* Sim panel */}
        <main style={{
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden', background: 'var(--gray-50)',
          position: 'relative',
        }}>
          {/* Idle state */}
          {sim.status === 'idle' && sim.agents.length === 0 && (
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              gap: '1rem', color: 'var(--gray-600)',
              textAlign: 'center', padding: '2rem',
            }}>
              <svg style={{ width: 64, height: 64, color: 'var(--gray-300)' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="12" cy="12" r="10"/>
                <polygon points="10 8 16 12 10 16 10 8"/>
              </svg>
              <h3 style={{ fontSize: '1.1rem', color: 'var(--gray-900)', margin: 0 }}>No simulation running</h3>
              <p style={{ fontSize: '0.875rem', maxWidth: 320, margin: 0 }}>
                Describe a scenario in the chat to get started. ARIA will suggest scenarios and run the simulation here.
              </p>
            </div>
          )}

          {/* Active simulation */}
          {(sim.status !== 'idle' || sim.agents.length > 0) && (() => {
            // CRITICAL: When viewing history, freeze ALL display to historical snapshot
            // This prevents live simulation updates from triggering re-renders that switch the view
            if (sim.isRestoredFromHistory) {
              // Show frozen historical view - ignore all live state
              const displayMetrics = sim.metrics
              const displayAgents = sim.agents
              const displayInfluences = sim.influences
              const displayName = sim.scenarioName
              const displayFeed = sim.feed
              const showReportPanel = sim.restoredReport !== null
              
              return (
                <div style={{
                  flex: 1, display: 'flex', flexDirection: 'column',
                  overflow: 'hidden', padding: '1rem 1.25rem', gap: '0.75rem',
                }}>
                  {/* Top bar */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1, minWidth: 0 }}>
                      <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--gray-900)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {displayName || '—'}
                      </span>
                    </div>
                  </div>

                  {/* Metrics */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '0.6rem', flexShrink: 0 }}>
                    <MetricCard label="Total visits" value={displayMetrics?.total_visits ?? '—'} />
                    <MetricCard label="Revenue (RM)" value={displayMetrics ? displayMetrics.total_revenue.toFixed(0) : '—'} tooltip="Estimated from your business price range (or income-based if not set), adjusted by the scenario's price change. Each visiting customer spends a random amount within your price range per visit." />
                    <MetricCard label="Active customers" value={displayMetrics?.active_agents ?? '—'} />
                    <MetricCard label="Churned" value={displayMetrics?.churned_agents ?? '—'} danger />
                  </div>

                  {/* Main area */}
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: displayFeed.length > 0 && !showReportPanel ? '1fr 260px' : '1fr',
                    gap: '0.75rem', flex: 1, overflow: 'hidden', minHeight: 0,
                  }}>
                    {showReportPanel ? (
                      <RestoredSummaryPanel
                        report={sim.restoredReport!}
                        description={sim.restoredDescription}
                      />
                    ) : (
                      <InfluenceGraph
                        key={`graph-history-${displayInfluences.length}`}
                        agents={displayAgents}
                        influences={displayInfluences}
                        highlightedAgentId={highlightedAgentId}
                        onClearHighlight={() => setHighlightedAgentId(null)}
                      />
                    )}
                    {displayFeed.length > 0 && !showReportPanel && (
                      <ActivityFeed 
                        items={displayFeed} 
                        onAgentClick={setHighlightedAgentId} 
                        highlightedAgentId={highlightedAgentId}
                        onPageChange={setActivityFeedPage}
                      />
                    )}
                  </div>
                </div>
              )
            }
            
            // LIVE simulation view (not viewing history)
            // Determine which run to display based on Activity Feed pagination
            // For Monte Carlo: completedSims has all individual runs + summary at the end
            // ActivityFeed pages correspond to individual runs only
            const mcState = sim.monteCarloState
            const isMonteCarlo = mcState && mcState.max_runs > 1
            
            // Find the summary (last entry with scenarioName containing "Summary")
            const summaryIndex = sim.completedSims.findIndex(s => s.scenarioName.includes('Summary'))
            const hasSummary = summaryIndex >= 0
            
            // Check if we're showing the report panel
            const showRestoredSummary = sim.isRestoredFromHistory && sim.restoredReport && sim.completedSims.length === 0
            const justCompletedSim = !sim.isRestoredFromHistory && sim.status === 'done' && completedReport
            const showReportPanel = showRestoredSummary || justCompletedSim
            
            // Determine which completed run to view
            let viewingCompletedRun: typeof sim.completedSims[0] | null = null
            
            // When report panel is showing, always use summary data for metrics
            if (showReportPanel && hasSummary) {
              viewingCompletedRun = sim.completedSims[summaryIndex]
            } else if (activityFeedPage < sim.completedSims.length) {
              // Otherwise show the specific run based on activity feed page
              viewingCompletedRun = sim.completedSims[activityFeedPage]
            }

            const displayMetrics  = viewingCompletedRun ? viewingCompletedRun.metrics   : sim.metrics
            const displayAgents   = viewingCompletedRun ? viewingCompletedRun.agents    : sim.agents
            const displayInfluences = viewingCompletedRun ? viewingCompletedRun.influences : sim.influences
            const displayName     = viewingCompletedRun ? viewingCompletedRun.scenarioName : sim.scenarioName
            
            // For ActivityFeed, always pass the complete feed so it can handle pagination internally
            const displayFeed = sim.feed

            // Show simplified loading screen while sim is running (unless user opened thought process)
            const isRunningLive = sim.status === 'running' || sim.status === 'paused'

            return (
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              overflow: 'hidden', padding: '1rem 1.25rem', gap: '0.75rem',
            }}>
              {/* Top bar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1, minWidth: 0 }}>
                  <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--gray-900)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {displayName || '—'}
                  </span>
                  {/* Show which run is being viewed via Activity Feed */}
                  {viewingCompletedRun && !viewingCompletedRun.scenarioName.includes('Summary') && (
                    <span style={{
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      padding: '0.15rem 0.5rem',
                      borderRadius: 4,
                      background: 'var(--gray-100)',
                      color: 'var(--gray-600)',
                    }}>
                      Viewing Run {activityFeedPage + 1}
                    </span>
                  )}
                  {/* Monte Carlo badge — shows live run progress and convergence */}
                  {sim.monteCarloState && !sim.isRestoredFromHistory && isRunningLive && (sim.status === 'running' || sim.status === 'paused') && (
                    <MonteCarloBadge mc={sim.monteCarloState} />
                  )}
                </div>
                {isRunningLive && !viewingCompletedRun && !sim.isRestoredFromHistory && (sim.status === 'running' || sim.status === 'paused') && (
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <CtrlBtn onClick={sim.togglePause} title={sim.isPaused ? 'Resume' : 'Pause'}>
                      {sim.isPaused
                        ? <svg style={{ width: 18, height: 18 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                        : <svg style={{ width: 18, height: 18 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                      }
                    </CtrlBtn>
                    <TerminateBtn onClick={sim.terminate} />
                  </div>
                )}
              </div>

              {/* Loading screen layer — shown while sim is running, hidden when user peeks at thought process */}
              {isRunningLive && !sim.isRestoredFromHistory && !showThoughtProcess && !showThoughtProcessRef.current && (
                <SimLoadingScreen
                  scenarioName={displayName}
                  message={sim.loadingMessage}
                  progressPct={progressPct}
                  agentCount={sim.agents.length}
                  decidedCount={decidedCount}
                  monteCarloState={sim.monteCarloState}
                  simStartTime={sim.simStartTime.current}
                  isPaused={sim.isPaused}
                  onShowThoughtProcess={() => {
                    setShowThoughtProcess(true)
                    showThoughtProcessRef.current = true
                  }}
                />
              )}

              {/* Thought-process toggle strip — shown when user has peeked inside */}
              {isRunningLive && !sim.isRestoredFromHistory && (showThoughtProcess || showThoughtProcessRef.current) && (
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '0.45rem 0.75rem',
                  background: 'var(--gray-100)', borderRadius: 8,
                  border: '1px solid var(--gray-200)', flexShrink: 0,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.78rem', color: 'var(--gray-600)' }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#22c55e', display: 'inline-block', animation: 'pulse-dot 1.2s infinite' }} />
                    <span style={{ fontWeight: 600 }}>{sim.loadingMessage}</span>
                  </div>
                  <button
                    onClick={() => {
                      setShowThoughtProcess(false)
                      showThoughtProcessRef.current = false
                    }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '0.35rem',
                      padding: '0.25rem 0.65rem', borderRadius: 6, border: '1.5px solid var(--gray-300)',
                      background: 'white', fontSize: '0.75rem', fontWeight: 600,
                      color: 'var(--gray-700)', cursor: 'pointer', fontFamily: 'var(--font-family)',
                    }}
                  >
                    <svg style={{ width: 13, height: 13 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/>
                    </svg>
                    Hide thought process
                  </button>
                </div>
              )}

              {/* Thought-process content / metrics / report — hidden behind loading screen unless revealed */}
              {(!isRunningLive || showThoughtProcess || showThoughtProcessRef.current) && (
                <>
                  {/* Metrics */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '0.6rem', flexShrink: 0 }}>
                    <MetricCard label="Total visits" value={displayMetrics?.total_visits ?? '—'} />
                    <MetricCard label="Revenue (RM)" value={displayMetrics ? displayMetrics.total_revenue.toFixed(0) : '—'} tooltip="Estimated from your business price range (or income-based if not set), adjusted by the scenario's price change. Each visiting customer spends a random amount within your price range per visit." />
                    <MetricCard label="Active customers" value={displayMetrics?.active_agents ?? '—'} />
                    <MetricCard label="Churned" value={displayMetrics?.churned_agents ?? '—'} danger />
                  </div>

                  {/* Main area */}
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: displayFeed.length > 0 && !showReportPanel ? '1fr 260px' : '1fr',
                    gap: '0.75rem', flex: 1, overflow: 'hidden', minHeight: 0,
                  }}>
                    {showReportPanel ? (
                      <RestoredSummaryPanel
                        report={sim.isRestoredFromHistory ? sim.restoredReport! : completedReport!}
                        description={sim.isRestoredFromHistory ? sim.restoredDescription : completedDescription}
                      />
                    ) : (
                      <InfluenceGraph
                        key={`graph-run${activityFeedPage}-v${displayInfluences.length}`}
                        agents={displayAgents}
                        influences={displayInfluences}
                        highlightedAgentId={highlightedAgentId}
                        onClearHighlight={() => setHighlightedAgentId(null)}
                      />
                    )}
                    {displayFeed.length > 0 && !showReportPanel && (
                      <ActivityFeed 
                        items={displayFeed} 
                        onAgentClick={setHighlightedAgentId} 
                        highlightedAgentId={highlightedAgentId}
                        onPageChange={setActivityFeedPage}
                      />
                    )}
                  </div>
                </>
              )}
            </div>
            )
          })()}
        </main>
      </div>

      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @keyframes spin-slow {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @keyframes loading-shimmer {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        @keyframes fade-up {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes orbit {
          from { transform: rotate(0deg) translateX(28px) rotate(0deg); }
          to   { transform: rotate(360deg) translateX(28px) rotate(-360deg); }
        }
        @keyframes pulse-ring {
          0% {
            transform: scale(1);
            opacity: 0.4;
          }
          50% {
            transform: scale(1.15);
            opacity: 0.2;
          }
          100% {
            transform: scale(1.3);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  )
}

// ─── SimLoadingScreen ────────────────────────────────────────────────────────
interface SimLoadingScreenProps {
  scenarioName: string
  message: string
  progressPct: number
  agentCount: number
  decidedCount: number
  monteCarloState: MonteCarloState | null
  simStartTime: number | null
  isPaused: boolean
  onShowThoughtProcess: () => void
}

function SimLoadingScreen({
  scenarioName, message, progressPct, agentCount, decidedCount,
  monteCarloState, simStartTime, isPaused, onShowThoughtProcess,
}: SimLoadingScreenProps) {
  const [elapsed, setElapsed] = useState(0)

  // Tick every second to keep ETA fresh
  useEffect(() => {
    if (!simStartTime || isPaused) return
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - simStartTime) / 1000))
    }, 1000)
    return () => clearInterval(id)
  }, [simStartTime, isPaused])

  // ETA: extrapolate from current pace
  function formatEta(): string {
    if (progressPct <= 0 || progressPct >= 100 || elapsed <= 2) return 'Estimating…'
    const totalSec = Math.round((elapsed / progressPct) * 100)
    const remaining = totalSec - elapsed
    if (remaining <= 0) return 'Almost done…'
    if (remaining < 60) return `~${remaining}s remaining`
    return `~${Math.ceil(remaining / 60)}min remaining`
  }

  function formatElapsed(): string {
    if (elapsed < 60) return `${elapsed}s`
    return `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`
  }

  // Monte Carlo label
  const mcLabel = monteCarloState
    ? monteCarloState.current_run > 0
      ? `Run ${monteCarloState.current_run} of ${monteCarloState.max_runs}`
      : `Up to ${monteCarloState.max_runs} runs planned`
    : null

  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      gap: '1.75rem', padding: '2rem',
      background: 'var(--white)', borderRadius: 12,
      border: '1px solid var(--gray-200)',
      overflow: 'hidden', position: 'relative',
    }}>
      {/* Subtle animated background rings */}
      <div style={{
        position: 'absolute', width: 320, height: 320,
        borderRadius: '50%', border: '1.5px solid var(--gray-100)',
        animation: 'spin-slow 18s linear infinite',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', width: 220, height: 220,
        borderRadius: '50%', border: '1.5px solid var(--gray-100)',
        animation: 'spin-slow 12s linear infinite reverse',
        pointerEvents: 'none',
      }} />

      {/* Orbiting dot */}
      <div style={{
        position: 'absolute', width: 10, height: 10,
        borderRadius: '50%', background: 'var(--accent)',
        opacity: 0.35,
        animation: 'orbit 3.5s linear infinite',
        pointerEvents: 'none',
      }} />

      {/* Scenario name + status */}
      <div style={{ textAlign: 'center', zIndex: 1, animation: 'fade-up 0.4s ease' }}>
        <p style={{ margin: '0 0 0.35rem', fontSize: '0.72rem', fontWeight: 600, color: 'var(--gray-400)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {isPaused ? 'Paused' : 'Simulating'}
        </p>
        <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: 'var(--gray-900)', fontFamily: 'var(--font-display)' }}>
          {scenarioName || 'Running simulation…'}
        </h2>
      </div>

      {/* Status message — updates with SSE events */}
      <div
        key={message}
        style={{
          zIndex: 1, padding: '0.6rem 1.1rem',
          background: 'var(--gray-50)', borderRadius: 999,
          border: '1px solid var(--gray-200)',
          display: 'flex', alignItems: 'center', gap: '0.5rem',
          maxWidth: 420, textAlign: 'center',
          animation: 'fade-up 0.3s ease',
        }}>
        {!isPaused && (
          <span style={{
            width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
            background: '#22c55e',
            animation: 'pulse-dot 1.2s infinite',
          }} />
        )}
        <span style={{ fontSize: '0.85rem', color: 'var(--gray-700)', fontWeight: 500 }}>
          {isPaused ? '⏸ Simulation paused' : message}
        </span>
      </div>

      {/* Monte Carlo badge (when running multiple runs) */}
      {mcLabel && (
        <div style={{
          zIndex: 1,
          padding: '0.25rem 0.75rem', borderRadius: 999,
          background: '#eff6ff', border: '1.5px solid #3b82f6',
          fontSize: '0.75rem', fontWeight: 600, color: '#1d4ed8',
          display: 'flex', alignItems: 'center', gap: '0.6rem',
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#3b82f6', display: 'inline-block', animation: 'pulse-dot 1.2s infinite' }} />
          {mcLabel}
          {monteCarloState && monteCarloState.wci_cv > 0 && (
            <>
              <span style={{ opacity: 0.35 }}>·</span>
              <span
                title="Result variation (CV) — lower means more consistent results"
                style={{
                  color: monteCarloState.wci_cv <= monteCarloState.cv_threshold
                    ? '#15803d'
                    : monteCarloState.wci_cv <= monteCarloState.cv_threshold * 2
                    ? '#a16207'
                    : '#b91c1c',
                  cursor: 'help',
                }}
              >
                {monteCarloState.wci_cv.toFixed(1)}% variation
              </span>
            </>
          )}
        </div>
      )}

      {/* Show thought process button */}
      <button
        onClick={onShowThoughtProcess}
        style={{
          zIndex: 1,
          display: 'flex', alignItems: 'center', gap: '0.5rem',
          padding: '0.55rem 1.1rem', borderRadius: 8,
          border: '1.5px solid var(--gray-300)',
          background: 'white', cursor: 'pointer',
          fontSize: '0.82rem', fontWeight: 600, color: 'var(--gray-700)',
          fontFamily: 'var(--font-family)',
          transition: 'border-color 0.15s, color 0.15s, box-shadow 0.15s',
          boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
        }}
        onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)' }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--gray-300)'; e.currentTarget.style.color = 'var(--gray-700)' }}
      >
        <svg style={{ width: 15, height: 15 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
        </svg>
        Show thought process
      </button>
    </div>
  )
}

function MetricCard({ label, value, danger, tooltip }: { label: string; value: string | number; danger?: boolean; tooltip?: string }) {
  return (
    <div style={{
      background: 'var(--white)', borderRadius: 8,
      padding: '0.65rem 0.9rem', border: '1px solid var(--gray-200)',
      position: 'relative',
    }}>
      <span style={{
        fontSize: '0.72rem', color: 'var(--gray-600)', fontWeight: 500,
        display: 'flex', alignItems: 'center', gap: '0.3rem',
        marginBottom: '0.25rem',
        textTransform: 'uppercase', letterSpacing: '0.03em',
      }}>
        {label}
        {tooltip && <InfoTooltip text={tooltip} />}
      </span>
      <span style={{
        fontSize: '1.35rem', fontWeight: 800,
        fontFamily: 'var(--font-display)',
        color: danger ? '#ef4444' : 'var(--gray-900)',
      }}>
        {value}
      </span>
    </div>
  )
}

function InfoTooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false)
  return (
    <span
      style={{ position: 'relative', display: 'inline-flex', cursor: 'help' }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <svg style={{ width: 12, height: 12, color: 'var(--gray-400)' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
      </svg>
      {show && (
        <span style={{
          position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)',
          background: 'var(--gray-900)', color: 'white', fontSize: '0.68rem', fontWeight: 400,
          padding: '0.5rem 0.65rem', borderRadius: 6, whiteSpace: 'normal',
          width: 220, lineHeight: 1.4, zIndex: 50, textTransform: 'none', letterSpacing: 0,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)', marginTop: 4,
        }}>
          {text}
        </span>
      )}
    </span>
  )
}

function CtrlBtn({ onClick, title, children, danger }: { onClick: () => void; title?: string; children: React.ReactNode; danger?: boolean }) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      title={title}
      style={{
        background: 'none',
        border: `1.5px solid ${danger ? '#ef4444' : 'var(--gray-300)'}`,
        borderRadius: 6,
        padding: '0.3rem 0.5rem',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        color: danger ? (hov ? '#dc2626' : '#ef4444') : (hov ? 'var(--accent)' : 'var(--gray-700)'),
        transition: 'all 0.15s',
        fontFamily: 'var(--font-family)',
      }}
    >
      {children}
    </button>
  )
}

function TerminateBtn({ onClick }: { onClick: () => void }) {
  const [hov, setHov] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  
  const handleConfirm = () => {
    setShowConfirm(false)
    onClick()
  }
  
  return (
    <>
      <button
        onClick={() => setShowConfirm(true)}
        onMouseEnter={() => setHov(true)}
        onMouseLeave={() => setHov(false)}
        title="Stop simulation"
        style={{
          background: hov ? '#ef4444' : 'transparent',
          border: '1.5px solid #ef4444',
          borderRadius: 6,
          padding: '0.3rem 0.75rem',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          color: hov ? 'white' : '#ef4444',
          fontSize: '0.8rem',
          fontWeight: 600,
          transition: 'all 0.15s',
          fontFamily: 'var(--font-family)',
        }}
      >
        Terminate
      </button>
      
      {showConfirm && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          animation: 'fadeIn 0.15s ease',
        }}>
          <div style={{
            background: 'white',
            borderRadius: 12,
            padding: '1.5rem',
            maxWidth: 420,
            width: '90%',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            animation: 'slideUp 0.2s ease',
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              marginBottom: '1rem',
            }}>
              <div style={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                background: '#fef2f2',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                <svg style={{ width: 20, height: 20, color: '#ef4444' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                  <line x1="12" y1="9" x2="12" y2="13"/>
                  <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
              </div>
              <h3 style={{
                margin: 0,
                fontSize: '1.1rem',
                fontWeight: 700,
                color: 'var(--gray-900)',
              }}>
                Terminate Simulation?
              </h3>
            </div>
            
            <p style={{
              margin: '0 0 1.5rem 0',
              fontSize: '0.9rem',
              lineHeight: 1.6,
              color: 'var(--gray-700)',
            }}>
              This will stop the current simulation and remove all progress. This action cannot be undone.
            </p>
            
            <div style={{
              display: 'flex',
              gap: '0.75rem',
              justifyContent: 'flex-end',
            }}>
              <button
                onClick={() => setShowConfirm(false)}
                style={{
                  background: 'var(--gray-100)',
                  border: 'none',
                  borderRadius: 6,
                  padding: '0.5rem 1rem',
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  color: 'var(--gray-700)',
                  transition: 'background 0.15s',
                  fontFamily: 'var(--font-family)',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--gray-200)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'var(--gray-100)'}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                style={{
                  background: '#ef4444',
                  border: 'none',
                  borderRadius: 6,
                  padding: '0.5rem 1rem',
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  color: 'white',
                  transition: 'background 0.15s',
                  fontFamily: 'var(--font-family)',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#dc2626'}
                onMouseLeave={(e) => e.currentTarget.style.background = '#ef4444'}
              >
                Terminate
              </button>
            </div>
          </div>
          
          <style>{`
            @keyframes fadeIn {
              from { opacity: 0; }
              to { opacity: 1; }
            }
            @keyframes slideUp {
              from { opacity: 0; transform: translateY(10px); }
              to { opacity: 1; transform: translateY(0); }
            }
          `}</style>
        </div>
      )}
    </>
  )
}

function MonteCarloBadge({ mc }: { mc: MonteCarloState }) {
  const [hov, setHov] = useState(false)

  // Determine badge color based on state
  const isComplete = mc.completed
  const hasConverged = mc.converged
  const isRunning = !mc.completed && mc.current_run > 0

  let bgColor: string, borderColor: string, textColor: string, dotColor: string
  if (isComplete && hasConverged) {
    bgColor = '#f0fdf4'; borderColor = '#22c55e'; textColor = '#15803d'; dotColor = '#22c55e'
  } else if (isComplete && !hasConverged) {
    bgColor = '#fef3c7'; borderColor = '#f59e0b'; textColor = '#a16207'; dotColor = '#f59e0b'
  } else if (isRunning) {
    bgColor = '#eff6ff'; borderColor = '#3b82f6'; textColor = '#1d4ed8'; dotColor = '#3b82f6'
  } else {
    bgColor = 'var(--gray-100)'; borderColor = 'var(--gray-300)'; textColor = 'var(--gray-600)'; dotColor = 'var(--gray-400)'
  }

  // Build progress percentage based on min_runs (not max_runs) so badge fills near convergence
  const targetRuns = isComplete ? mc.current_run : Math.max(mc.min_runs, mc.current_run)
  const progressPct = mc.max_runs > 0 ? Math.min(100, (mc.current_run / targetRuns) * 100) : 0

  // Tooltip content - using business-friendly language
  // CV (coefficient of variation) is a measure of how much results vary across runs
  // Lower CV = more consistent results = more reliable predictions
  const tooltip = isComplete
    ? hasConverged
      ? `Results are reliable.\nCompleted ${mc.current_run} runs with consistent outcomes.\nResult variation: ${mc.wci_cv.toFixed(1)}% (lower is better)`
      : `Results may vary.\nCompleted ${mc.current_run} runs but outcomes weren't fully consistent.\nResult variation: ${mc.wci_cv.toFixed(1)}%`
    : mc.current_run === 0
      ? `Running this scenario ${mc.min_runs}-${mc.max_runs} times to make sure results are reliable. We'll stop early once results stabilize.`
      : mc.wci_cv > 0
        ? `Run ${mc.current_run} of ${mc.max_runs}\nResult variation so far: ${mc.wci_cv.toFixed(1)}% (need ≤${mc.cv_threshold.toFixed(0)}% to confirm reliable)`
        : `Run ${mc.current_run} of ${mc.max_runs}\nGathering initial data (need at least ${mc.min_runs} runs)`

  return (
    <div
      title={tooltip}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: '0.4rem',
        padding: '0.25rem 0.6rem',
        background: bgColor,
        border: `1.5px solid ${borderColor}`,
        borderRadius: 999,
        fontSize: '0.72rem',
        fontWeight: 600,
        color: textColor,
        whiteSpace: 'nowrap',
        cursor: 'help',
        position: 'relative',
        overflow: 'hidden',
        transition: 'all 0.2s ease',
        boxShadow: hov ? '0 2px 8px rgba(0,0,0,0.08)' : 'none',
      }}
    >
      {/* Subtle progress fill background */}
      {!isComplete && (
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0,
          width: `${progressPct}%`,
          background: 'rgba(59, 130, 246, 0.08)',
          transition: 'width 0.4s ease',
          pointerEvents: 'none',
        }} />
      )}

      {/* Status dot */}
      <span style={{
        width: 7, height: 7, borderRadius: '50%',
        background: dotColor,
        position: 'relative', zIndex: 1,
        animation: isRunning ? 'pulse-dot 1.2s infinite' : 'none',
      }} />

      {/* Label */}
      <span style={{ position: 'relative', zIndex: 1 }}>
        {isComplete ? (
          hasConverged ? (
            <>✓ Completed · {mc.current_run} runs</>
          ) : (
            <>⚠ Completed · {mc.current_run} runs</>
          )
        ) : (
          <>
            🔁 Run {mc.current_run || 0} of {mc.max_runs}
            {mc.wci_cv > 0 && (
              <span style={{ marginLeft: '0.35rem', opacity: 0.8 }}>
                · {mc.wci_cv.toFixed(1)}% variation
              </span>
            )}
          </>
        )}
      </span>
    </div>
  )
}

function RestoredSummaryPanel({ report, description }: { report: SimReport; description: string }) {
  const RISK_COLOUR: Record<string, string> = {
    Low:    '#22c55e',
    Medium: '#f59e0b',
    High:   '#ef4444',
  }
  const riskColor = RISK_COLOUR[report.risk_level] || 'var(--gray-500)'

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: '1rem',
      padding: '1.25rem', overflowY: 'auto',
      background: 'var(--white)', borderRadius: 10,
      border: '1px solid var(--gray-200)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
        <svg style={{ width: 20, height: 20, color: 'var(--accent)', flexShrink: 0 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
        <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--gray-900)' }}>
          Simulation Completed
        </span>
        <span style={{
          marginLeft: 'auto', padding: '0.2rem 0.65rem', borderRadius: 999,
          fontSize: '0.72rem', fontWeight: 700,
          background: `${riskColor}1a`, color: riskColor, border: `1px solid ${riskColor}55`,
        }}>
          {report.risk_level} Risk
        </span>
      </div>

      {description && (
        <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--gray-600)', lineHeight: 1.5 }}>
          {description}
        </p>
      )}

      {/* Summary stats — visit and churn rates only (revenue shown in metric cards above) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.6rem' }}>
        <StatBox label="Visit Rate"  value={`${report.visit_rate.toFixed(1)}%`}  color="#22c55e" />
        <StatBox label="Churn Rate"  value={`${report.churn_rate.toFixed(1)}%`}  color="#ef4444" />
      </div>

      {/* Archetype breakdown */}
      {Object.keys(report.archetype_breakdown).length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          <p style={{ margin: 0, fontSize: '0.72rem', fontWeight: 700, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Customer Breakdown
          </p>
          {Object.entries(report.archetype_breakdown).map(([label, data]) => (
            <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--gray-700)' }}>
                <span style={{ fontWeight: 600 }}>{label}</span>
                <span style={{ color: 'var(--gray-500)' }}>
                  {data.visit_pct}% visit · {data.skip_pct}% skip · {data.churn_pct}% churn
                </span>
              </div>
              <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', background: 'var(--gray-100)' }}>
                <div style={{ width: `${data.visit_pct}%`, background: '#22c55e' }} />
                <div style={{ width: `${data.skip_pct}%`, background: '#eab308' }} />
                <div style={{ width: `${data.churn_pct}%`, background: '#ef4444' }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Analysis */}
      {report.analysis && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
          <p style={{ margin: 0, fontSize: '0.72rem', fontWeight: 700, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Analysis
          </p>
          <div style={{
            fontSize: '0.8rem', color: 'var(--gray-700)', lineHeight: 1.5,
            padding: '0.5rem 0.6rem', borderRadius: 6,
            background: 'var(--gray-50)', borderLeft: '3px solid var(--accent)',
          }}>
            {report.analysis}
          </div>
        </div>
      )}

      {/* Key reasons for skip/churn */}
      {report.key_reasons && report.key_reasons.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          <p style={{ margin: 0, fontSize: '0.72rem', fontWeight: 700, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Key Reasons for Skip/Churn
          </p>
          <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.3rem', listStyle: 'none' }}>
            {report.key_reasons.map((reason, i) => (
              <li key={i} style={{ fontSize: '0.8rem', color: 'var(--gray-700)', lineHeight: 1.5 }}>
                {i + 1}. {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommendations */}
      {report.recommendations.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          <p style={{ margin: 0, fontSize: '0.72rem', fontWeight: 700, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Recommendations
          </p>
          <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            {report.recommendations.map((rec, i) => (
              <li key={i} style={{ fontSize: '0.8rem', color: 'var(--gray-700)', lineHeight: 1.5 }}>
                {rec.replace(/\*\*/g, '')}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function StatBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{
      padding: '0.6rem 0.75rem', borderRadius: 8,
      border: '1px solid var(--gray-200)', background: 'var(--gray-50)',
    }}>
      <div style={{ fontSize: '0.68rem', color: 'var(--gray-500)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.2rem' }}>
        {label}
      </div>
      <div style={{ fontSize: '1.15rem', fontWeight: 800, color, fontFamily: 'var(--font-display)' }}>
        {value}
      </div>
    </div>
  )
}
