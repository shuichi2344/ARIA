'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import ProfileWidget from '@/components/auth/ProfileWidget'
import ChatPanel from './ChatPanel'
import ActivityFeed from './ActivityFeed'
import InfluenceGraph from './InfluenceGraph'
import HistorySidebar from './HistorySidebar'
import { useSim } from './useSim'
import { useSession } from '@/context/SessionContext'
import type { AriaSession, BusinessProfile } from './types'

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

  // Notify chat when simulation completes
  useEffect(() => {
    if (sim.status === 'done' && sim.metrics) {
      // Call the global callback to add completion message to chat
      if ((window as any).__ariaAddCompletionMessage) {
        const summary = `Simulation complete. ${sim.metrics.active_agents} customers still active, ${sim.metrics.churned_agents} churned.`
        ;(window as any).__ariaAddCompletionMessage(summary)
      }
    }
  }, [sim.status, sim.metrics, sim.totalWeeks])

  function handleLogout() {
    logout()
    router.push('/')
  }

  // Progress based on how many agents have made decisions
  const decidedCount = sim.agents.filter(a => a.last_decision !== null).length
  const progressPct = sim.agents.length > 0
    ? Math.round((decidedCount / sim.agents.length) * 100)
    : 0

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* History sidebar */}
      <HistorySidebar
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        history={sim.history}
        onRestore={snap => { sim.restoreSnapshot(snap); setHistoryOpen(false) }}
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
              background: STATUS_DOT[sim.status] || 'var(--gray-400)',
              display: 'inline-block',
              animation: sim.status === 'running' ? 'pulse-dot 1.2s infinite' : 'none',
            }} />
            {STATUS_LABELS[sim.status] || sim.status}
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
          simulationStatus={sim.status}
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
          {(sim.status !== 'idle' || sim.agents.length > 0) && (
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              overflow: 'hidden', padding: '1rem 1.25rem', gap: '0.75rem',
            }}>
              {/* Top bar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--gray-900)' }}>
                    {sim.scenarioName || '—'}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <CtrlBtn onClick={sim.togglePause} title="Pause / Resume">
                    {sim.isPaused
                      ? <svg style={{ width: 18, height: 18 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                      : <svg style={{ width: 18, height: 18 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                    }
                  </CtrlBtn>
                </div>
              </div>

              {/* Progress bar */}
              <div style={{ height: 6, background: 'var(--gray-200)', borderRadius: 999, overflow: 'hidden', flexShrink: 0 }}>
                <div style={{
                  height: '100%',
                  background: 'linear-gradient(90deg, var(--accent), var(--accent-light))',
                  borderRadius: 999,
                  width: `${progressPct}%`,
                  transition: 'width 0.5s ease',
                }} />
              </div>

              {/* Metrics */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '0.6rem', flexShrink: 0 }}>
                <MetricCard label="Total visits" value={sim.metrics?.total_visits ?? '—'} />
                <MetricCard label="Revenue (RM)"     value={sim.metrics ? sim.metrics.total_revenue.toFixed(0) : '—'} tooltip="Estimated from your business price range (or income-based if not set), adjusted by the scenario's price change. Each visiting customer spends a random amount within your price range per visit." />
                <MetricCard label="Active customers"    value={sim.metrics?.active_agents ?? '—'} />
                <MetricCard label="Churned"          value={sim.metrics?.churned_agents ?? '—'} danger />
              </div>

              {/* Main area: influence graph (full width) + activity feed (collapsible right) */}
              <div style={{
                display: 'grid', gridTemplateColumns: '1fr 260px',
                gap: '0.75rem', flex: 1, overflow: 'hidden', minHeight: 0,
              }}>
                {/* Force-directed agent graph — the main view */}
                <InfluenceGraph agents={sim.agents} influences={sim.influences} highlightedAgentId={highlightedAgentId} onClearHighlight={() => setHighlightedAgentId(null)} />

                {/* Activity feed */}
                <ActivityFeed items={sim.feed} onAgentClick={setHighlightedAgentId} highlightedAgentId={highlightedAgentId} />
              </div>
            </div>
          )}
        </main>
      </div>

      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
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

function CtrlBtn({ onClick, title, children }: { onClick: () => void; title?: string; children: React.ReactNode }) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      title={title}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: '0.3rem',
        background: 'var(--white)',
        border: `1.5px solid ${hov ? 'var(--accent)' : 'var(--gray-200)'}`,
        borderRadius: 6, padding: '0.35rem 0.7rem',
        fontSize: '0.8rem', fontWeight: 600,
        cursor: 'pointer', color: 'var(--gray-900)',
        transition: 'border-color 0.2s',
        fontFamily: 'var(--font-family)',
      }}
    >
      {children}
    </button>
  )
}
