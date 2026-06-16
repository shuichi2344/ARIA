'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import type { Agent, Scenario, SimStatus, WeekSummary, FeedItem, InfluenceEdge, SimSnapshot, SimReport } from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
let feedCounter = 0

// Sentinel ID for the "live" tab (currently running simulation)
export const LIVE_TAB_ID = '__live__'

export interface MonteCarloState {
  current_run: number
  max_runs: number
  min_runs: number
  cv_threshold: number
  wci_cv: number
  converged: boolean
  completed: boolean
}

export interface CompletedSim {
  id: string           // simulation_id from backend
  scenarioName: string
  scenarioType: string
  metrics: WeekSummary | null
  agents: Agent[]
  feed: FeedItem[]
  influences: InfluenceEdge[]
  report: any          // raw report from simulation_complete event
}

function mapHistoryItem(h: any): SimSnapshot {
  const r = h.report
  const agentCount = h.agent_count || 0
  const report: SimReport | null = r ? {
    risk_level:            r.risk_level || 'Unknown',
    churn_rate:            r.churn_rate ?? 0,
    visit_rate:            r.visit_rate ?? 0,
    estimated_revenue:     r.estimated_revenue ?? 0,
    total_agents:          agentCount,
    archetype_breakdown:   r.archetype_breakdown || {},
    recommendations:       r.recommendations || [],
    analysis:              r.analysis || '',
  } : null

  const finalMetrics: import('./types').WeekSummary | null = r ? {
    week:           1,
    total_visits:   r.visit_rate != null ? Math.round((r.visit_rate / 100) * agentCount) : 0,
    total_revenue:  r.estimated_revenue ?? 0,
    active_agents:  r.churn_rate != null ? Math.round(((100 - r.churn_rate) / 100) * agentCount) : agentCount,
    churned_agents: r.churn_rate != null ? Math.round((r.churn_rate / 100) * agentCount) : 0,
  } : null

  // Reconstruct agents from saved events (backend now provides this)
  const agents: Agent[] = (h.agents || []).map((a: any) => ({
    agent_id:       a.agent_id,
    persona_name:   a.persona_name || `Customer ${a.agent_id}`,
    income_level:   a.income_level || 'M40',
    age_range:      a.age_range || '',
    is_active:      a.is_active ?? (a.last_decision !== 'churn'),
    last_decision:  a.last_decision ?? null,
    reasoning:      a.reasoning ?? null,
    personality:    a.personality || '',
    personality_type: a.personality_type || '',
  }))

  // Reconstruct activity feed from saved events (backend now provides this)
  const feed: FeedItem[] = (h.feed || []).map((f: any, idx: number) => ({
    id:      f.id ?? idx,
    type:    f.type as FeedItem['type'],
    html:    f.html || '',
    agentId: f.agentId ?? f.agent_id,
  }))

  return {
    id:           h.simulation_id,
    scenarioName: h.scenario_name,
    scenarioType: h.scenario_type,
    description:  h.description || '',
    completedAt:  h.completed_at,
    totalWeeks:   1,
    finalMetrics,
    report,
    sessionId:    h.session_id || null,
    agents,
    feed,
    influences:   [],  // not persisted — peer influence edges are ephemeral
  }
}

export function useSim(sessionId: string, profileId?: string) {
  const [status,        setStatus]        = useState<SimStatus>('idle')
  const [agents,        setAgents]        = useState<Agent[]>([])
  const [metrics,       setMetrics]       = useState<WeekSummary | null>(null)
  const [currentWeek,   setCurrentWeek]   = useState(0)
  const [isPaused,      setIsPaused]      = useState(false)
  const [feed,          setFeed]          = useState<FeedItem[]>([])
  const [scenarioName,  setScenarioName]  = useState('')
  const [influences,    setInfluences]    = useState<InfluenceEdge[]>([])
  const [history,       setHistory]       = useState<SimSnapshot[]>([])
  const [restoredReport, setRestoredReport] = useState<SimReport | null>(null)
  const [restoredDescription, setRestoredDescription] = useState<string>('')
  const [isRestoredFromHistory, setIsRestoredFromHistory] = useState(false)

  // Monte Carlo state
  const [monteCarloState, setMonteCarloState] = useState<MonteCarloState | null>(null)

  // In-session completed simulations — drives the tab bar
  const [completedSims, setCompletedSims] = useState<CompletedSim[]>([])
  const [activeTabId,   setActiveTabId]   = useState<string | null>(null)

  // Fetch history from database on mount
  useEffect(() => {
    if (!profileId) return
    fetch(`${API_BASE}/api/simulation/history/${profileId}`)
      .then(res => res.ok ? res.json() : { history: [] })
      .then(data => {
        const items: SimSnapshot[] = (data.history || []).map((h: any) => mapHistoryItem(h))
        setHistory(items)
      })
      .catch(() => {})
  }, [profileId])

  // refs to capture latest state inside SSE callbacks
  const feedRef       = useRef<FeedItem[]>([])
  const agentsRef     = useRef<Agent[]>([])
  const influencesRef = useRef<InfluenceEdge[]>([])
  const metricsRef    = useRef<WeekSummary | null>(null)
  const scenarioNameRef = useRef('')
  const scenarioTypeRef = useRef('')

  const simIdRef = useRef<string | null>(null)
  const esRef    = useRef<EventSource | null>(null)

  // Cleanup on unmount: cancel running simulation and close SSE
  useEffect(() => {
    return () => {
      if (esRef.current) { esRef.current.close(); esRef.current = null }
      if (simIdRef.current) {
        fetch(`${API_BASE}/api/simulation/${simIdRef.current}/cancel`, { method: 'POST' }).catch(() => {})
      }
    }
  }, [])

  function addFeed(type: FeedItem['type'], html: string, agentId?: number) {
    setFeed(prev => {
      const next = [...prev, { id: feedCounter++, type, html, agentId }]
      const trimmed = next.length > 80 ? next.slice(next.length - 80) : next
      feedRef.current = trimmed
      return trimmed
    })
  }

  function updateAgentDecision(event: {
    agent_id: number
    decision: string
    reasoning: string
  }) {
    setAgents(prev => {
      const next = prev.map(a =>
        a.agent_id === event.agent_id
          ? { ...a, last_decision: event.decision, reasoning: event.reasoning, is_active: event.decision !== 'churn' }
          : a
      )
      agentsRef.current = next
      return next
    })
  }

  const launch = useCallback(async (scenario: Scenario, agentCount: number = 25, options?: { income_constraints?: string[] | null; age_constraints?: string[] | null; target_customer_constraints?: string[] | null; business_size_constraints?: string[] | null; b2b_percentage?: number | null; chat_session_id?: string | null }) => {
    // Cancel the previous simulation on the backend before starting a new one
    if (simIdRef.current) {
      fetch(`${API_BASE}/api/simulation/${simIdRef.current}/cancel`, { method: 'POST' }).catch(() => {})
    }
    // Close any existing SSE connection BEFORE changing state
    // Use a flag to prevent the old error handler from resetting status
    if (esRef.current) {
      const oldEs = esRef.current
      esRef.current = null  // Clear ref first so error handler is a no-op
      oldEs.close()
    }

    // Reset state for new simulation
    setFeed([])
    feedRef.current = []
    setInfluences([])
    influencesRef.current = []
    setMetrics(null)
    metricsRef.current = null
    setRestoredReport(null)
    setRestoredDescription('')
    setIsRestoredFromHistory(false)
    setActiveTabId(LIVE_TAB_ID)
    setMonteCarloState(null)

    setStatus('running')
    setScenarioName(scenario.scenario_name)
    scenarioNameRef.current = scenario.scenario_name
    scenarioTypeRef.current = scenario.scenario_type
    addFeed('system', `Starting simulation: "${scenario.scenario_name}" with ${agentCount} agents…`)

    try {
      const res = await fetch(`${API_BASE}/api/simulation/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id:        sessionId,
          profile_id:     profileId,
          scenario,
          agent_count:    agentCount,
          income_constraints: options?.income_constraints ?? null,
          age_constraints:    options?.age_constraints ?? null,
          target_customer_constraints: options?.target_customer_constraints ?? null,
          business_size_constraints:   options?.business_size_constraints ?? null,
          b2b_percentage:              options?.b2b_percentage ?? null,
          chat_session_id:             options?.chat_session_id ?? null,
        }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to start simulation')
      }
      const data = await res.json()
      simIdRef.current = data.simulation_id
      setCurrentWeek(0)
      setIsPaused(false)
      if (data.agents) { setAgents(data.agents); agentsRef.current = data.agents }
      setInfluences([]); influencesRef.current = []
      setMetrics(null);  metricsRef.current = null

      // SSE stream
      const es = new EventSource(`${API_BASE}/api/simulation/${data.simulation_id}/stream`)
      esRef.current = es

      es.addEventListener('week_start', e => {
        const d = JSON.parse((e as MessageEvent).data)
        setCurrentWeek(d.week)
      })
      es.addEventListener('agent_profile_ready', e => {
        const d = JSON.parse((e as MessageEvent).data)
        setAgents(prev => {
          const next = prev.map(a =>
            a.agent_id === d.agent_id
              ? { ...a, profile_text: d.profile_text, personality: d.profile_text }
              : a
          )
          agentsRef.current = next
          return next
        })
      })
      es.addEventListener('profile_generation_complete', () => {
        addFeed('system', `✅ All agent personalities generated. Starting simulation...`)
      })
      es.addEventListener('agent_decision', e => {
        const d = JSON.parse((e as MessageEvent).data)
        updateAgentDecision(d)
        const verb = d.decision === 'visit' ? 'visited 🟢'
                   : d.decision === 'churn' ? 'churned 🔴' : 'skipped 🟡'
        addFeed(d.decision as FeedItem['type'],
          `<strong>Customer ${d.agent_id}</strong> ${verb}<span class="reasoning">${esc(d.reasoning || '')}</span>`, d.agent_id)
      })
      es.addEventListener('peer_influence', e => {
        const d = JSON.parse((e as MessageEvent).data) as InfluenceEdge
        setInfluences(prev => { const next = [...prev, d]; influencesRef.current = next; return next })
        addFeed('system', `🗣️ <strong>Customer ${d.from_agent_id}</strong> influenced <strong>Customer ${d.to_agent_id}</strong> via word-of-mouth`, d.to_agent_id)
      })
      es.addEventListener('peer_evaluation', e => {
        const d = JSON.parse((e as MessageEvent).data) as {
          agent_id: number; income_level: string; current_decision: string;
          direction: string; num_peers: number; probability: number; flipped: boolean
        }
        if (d.flipped) {
          const newDec = d.direction === 'negative' ? 'skip' : 'visit'
          const emoji = newDec === 'visit' ? '🟢' : '🟡'
          addFeed(newDec as FeedItem['type'],
            `🗣️ <strong>Customer ${d.agent_id}</strong> (${d.income_level}) changed to ${newDec} ${emoji} after hearing from ${d.num_peers} friend${d.num_peers > 1 ? 's' : ''}`, d.agent_id)
        } else {
          addFeed('system',
            `<span style="opacity:0.6">🗣️ Customer ${d.agent_id} (${d.income_level}) heard from ${d.num_peers} ${d.direction} peer${d.num_peers > 1 ? 's' : ''} — stayed with ${d.current_decision}</span>`, d.agent_id)
        }
      })
      es.addEventListener('phase_label', e => {
        const d = JSON.parse((e as MessageEvent).data) as { label: string; description: string }
        addFeed('system', `<span style="font-weight:700;color:var(--accent)">── ${esc(d.label)} ──</span> <span style="opacity:0.7">${esc(d.description)}</span>`)
      })
      es.addEventListener('week_summary', e => {
        const d = JSON.parse((e as MessageEvent).data)
        setMetrics(d); metricsRef.current = d
        setCurrentWeek(d.week)
      })

      // Monte Carlo events
      es.addEventListener('monte_carlo_start', e => {
        const d = JSON.parse((e as MessageEvent).data)
        setMonteCarloState({
          current_run: 0,
          max_runs: d.max_runs,
          min_runs: d.min_runs,
          cv_threshold: d.cv_threshold,
          wci_cv: 0,
          converged: false,
          completed: false,
        })
        addFeed('system', `🔁 <strong>Running multiple times for accuracy</strong> — running this scenario ${d.min_runs}-${d.max_runs} times to make sure results are reliable`)
      })

      es.addEventListener('monte_carlo_run_start', e => {
        const d = JSON.parse((e as MessageEvent).data)
        setMonteCarloState(prev => prev ? { ...prev, current_run: d.run_number } : prev)
        addFeed('system', `<span style="font-weight:700;color:var(--accent)">━━━ Run ${d.run_number} of ${d.max_runs} ━━━</span>`)
      })

      es.addEventListener('monte_carlo_progress', e => {
        const d = JSON.parse((e as MessageEvent).data)
        setMonteCarloState(prev => prev ? {
          ...prev,
          current_run: d.run_number,
          wci_cv: d.wci_cv,
          converged: d.converged,
        } : prev)
      })

      es.addEventListener('monte_carlo_complete', e => {
        const d = JSON.parse((e as MessageEvent).data)
        setMonteCarloState(prev => prev ? {
          ...prev,
          completed: true,
          converged: d.converged,
          current_run: d.total_runs,
          wci_cv: d.wci_cv,
        } : prev)
        addFeed('system', d.converged
          ? `✅ <strong>Results are reliable</strong> — got consistent outcomes after ${d.total_runs} runs`
          : `⚠️ <strong>Results may vary</strong> — completed ${d.total_runs} runs but outcomes weren't fully consistent`
        )
      })

      es.addEventListener('simulation_complete', e => {
        const d = JSON.parse((e as MessageEvent).data)
        setStatus('done')
        addFeed('system', `Simulation complete! ${d.summary || ''}`)
        es.close()

        // Snapshot the completed simulation for the tab bar
        const completedId = simIdRef.current || data.simulation_id
        setCompletedSims(() => {
          const snap: CompletedSim = {
            id:           completedId,
            scenarioName: scenarioNameRef.current,
            scenarioType: scenarioTypeRef.current,
            metrics:      metricsRef.current,
            agents:       agentsRef.current,
            feed:         feedRef.current,
            influences:   influencesRef.current,
            report:       d.report,
          }
          // Always keep only one completed sim per chat session
          return [snap]
        })
        setActiveTabId(completedId)

        // Pass report to chat via global callback
        if ((window as any).__ariaAddCompletionMessage) {
          ;(window as any).__ariaAddCompletionMessage(d.summary, d.report)
        }

        // Re-fetch history from database to get the saved record with correct ID
        if (profileId) {
          fetch(`${API_BASE}/api/simulation/history/${profileId}`)
            .then(res => res.ok ? res.json() : { history: [] })
            .then(data => {
              const items: SimSnapshot[] = (data.history || []).map((h: any) => mapHistoryItem(h))
              setHistory(items)
            })
            .catch(() => {})
        }
      })
      es.addEventListener('error', () => {
        // Only handle if this is still the active connection
        if (esRef.current !== es) return
        es.close()
        esRef.current = null
        setStatus('idle')
        addFeed('system', 'Simulation stream disconnected.')
      })

    } catch (err: unknown) {
      setStatus('idle')
      addFeed('system', `Error: ${err instanceof Error ? err.message : String(err)}`)
    }
  }, [sessionId, profileId])

  const togglePause = useCallback(() => {
    if (!simIdRef.current) return
    const next = !isPaused
    setIsPaused(next)
    setStatus(next ? 'paused' : 'running')
    fetch(`${API_BASE}/api/simulation/${simIdRef.current}/${next ? 'pause' : 'resume'}`, { method: 'POST' }).catch(() => {})
  }, [isPaused])

  const restoreSnapshot = useCallback((snap: SimSnapshot) => {
    // If a simulation is currently running, DON'T close the SSE or destroy live state.
    // Instead, just overlay the history view. The live sim continues in the background.
    const isRunning = status === 'running' || status === 'paused'
    
    if (!isRunning) {
      // No active sim — safe to fully replace state
      if (esRef.current) { esRef.current.close(); esRef.current = null }
      setStatus('done')
    }
    
    // Store the viewed snapshot for display (this overlays the live sim panel)
    setScenarioName(snap.scenarioName)
    setCurrentWeek(snap.totalWeeks)
    setMetrics(snap.finalMetrics)
    setAgents(snap.agents)
    setFeed(snap.feed)
    setInfluences(snap.influences)
    setIsPaused(false)
    setRestoredReport(snap.report)
    setRestoredDescription(snap.description || '')
    setIsRestoredFromHistory(true)
    setCompletedSims([])
    setActiveTabId(null)
    setMonteCarloState(null)
    agentsRef.current     = snap.agents
    feedRef.current       = snap.feed
    influencesRef.current = snap.influences
    metricsRef.current    = snap.finalMetrics
  }, [status])

  const deleteSnapshot = useCallback((id: string) => {
    setHistory(prev => prev.filter(s => s.id !== id))
    // Delete from database
    fetch(`${API_BASE}/api/simulation/history/${id}`, { method: 'DELETE' }).catch(() => {})
  }, [])

  const reset = useCallback(() => {
    // Cancel the running simulation on the backend
    if (simIdRef.current) {
      fetch(`${API_BASE}/api/simulation/${simIdRef.current}/cancel`, { method: 'POST' }).catch(() => {})
    }
    // Close any active SSE connection
    if (esRef.current) { esRef.current.close(); esRef.current = null }
    simIdRef.current = null
    setStatus('idle')
    setAgents([])
    setMetrics(null)
    setCurrentWeek(0)
    setIsPaused(false)
    setFeed([])
    setScenarioName('')
    setInfluences([])
    setRestoredReport(null)
    setRestoredDescription('')
    setIsRestoredFromHistory(false)
    setCompletedSims([])
    setActiveTabId(null)
    setMonteCarloState(null)
    feedRef.current = []
    agentsRef.current = []
    influencesRef.current = []
    metricsRef.current = null
    scenarioNameRef.current = ''
    scenarioTypeRef.current = ''
  }, [])

  // Resume viewing the live/current simulation (after viewing history)
  const resumeLive = useCallback(() => {
    setAgents(agentsRef.current)
    setFeed(feedRef.current)
    setMetrics(metricsRef.current)
    setInfluences(influencesRef.current)
    setScenarioName(scenarioNameRef.current)
    setRestoredReport(null)
    setRestoredDescription('')
    setIsRestoredFromHistory(false)
    setActiveTabId(LIVE_TAB_ID)
    setMonteCarloState(prev => prev)  // keep current MC state
  }, [])

  return {
    status, agents, metrics, currentWeek,
    isPaused, feed, scenarioName, influences,
    history, restoreSnapshot, deleteSnapshot,
    launch, togglePause, reset, resumeLive,
    restoredReport, restoredDescription, isRestoredFromHistory,
    completedSims, activeTabId, setActiveTabId,
    monteCarloState,
  }
}

function esc(s: string) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}
