'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import type { Agent, Scenario, SimStatus, WeekSummary, FeedItem, InfluenceEdge, SimSnapshot } from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
let feedCounter = 0

export function useSim(sessionId: string, profileId?: string) {
  const [status,        setStatus]        = useState<SimStatus>('idle')
  const [agents,        setAgents]        = useState<Agent[]>([])
  const [metrics,       setMetrics]       = useState<WeekSummary | null>(null)
  const [currentWeek,   setCurrentWeek]   = useState(0)
  const [totalWeeks,    setTotalWeeks]    = useState(4)
  const [isPaused,      setIsPaused]      = useState(false)
  const [feed,          setFeed]          = useState<FeedItem[]>([])
  const [scenarioName,  setScenarioName]  = useState('')
  const [scenarioType,  setScenarioType]  = useState('')
  const [influences,    setInfluences]    = useState<InfluenceEdge[]>([])
  const [history,       setHistory]       = useState<SimSnapshot[]>([])

  // Fetch history from database on mount
  useEffect(() => {
    if (!profileId) return
    fetch(`${API_BASE}/api/simulation/history/${profileId}`)
      .then(res => res.ok ? res.json() : { history: [] })
      .then(data => {
        const items: SimSnapshot[] = (data.history || []).map((h: any) => ({
          id:           h.simulation_id,
          scenarioName: h.scenario_name,
          scenarioType: h.scenario_type,
          completedAt:  h.completed_at,
          totalWeeks:   1,
          finalMetrics: h.report ? {
            total_visits:    0,
            total_revenue:   h.report.estimated_revenue || 0,
            active_agents:   h.agent_count || 0,
            churned_agents:  0,
            week:            1,
          } : null,
          agents:       [],
          feed:         [],
          influences:   [],
        }))
        setHistory(items)
      })
      .catch(() => {})
  }, [profileId])

  // refs to capture latest state inside SSE callbacks
  const feedRef       = useRef<FeedItem[]>([])
  const agentsRef     = useRef<Agent[]>([])
  const influencesRef = useRef<InfluenceEdge[]>([])
  const metricsRef    = useRef<WeekSummary | null>(null)
  const totalWeeksRef = useRef(4)
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

  const launch = useCallback(async (scenario: Scenario, agentCount: number = 25, options?: { income_constraints?: string[] | null; age_constraints?: string[] | null; target_customer_constraints?: string[] | null; business_size_constraints?: string[] | null; b2b_percentage?: number | null }) => {
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

    setStatus('running')
    setScenarioName(scenario.scenario_name)
    setScenarioType(scenario.scenario_type)
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
          duration_weeks: 4,
          agent_count:    agentCount,
          income_constraints: options?.income_constraints ?? null,
          age_constraints:    options?.age_constraints ?? null,
          target_customer_constraints: options?.target_customer_constraints ?? null,
          business_size_constraints:   options?.business_size_constraints ?? null,
          b2b_percentage:              options?.b2b_percentage ?? null,
        }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to start simulation')
      }
      const data = await res.json()
      simIdRef.current = data.simulation_id
      setTotalWeeks(data.duration_weeks || 4)
      setCurrentWeek(0)
      setIsPaused(false)
      if (data.agents) { setAgents(data.agents); agentsRef.current = data.agents }
      setInfluences([]); influencesRef.current = []
      setMetrics(null);  metricsRef.current = null
      totalWeeksRef.current = data.duration_weeks || 4

      // SSE stream
      const es = new EventSource(`${API_BASE}/api/simulation/${data.simulation_id}/stream`)
      esRef.current = es
      const thisSimId = data.simulation_id  // Capture for closure

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
      es.addEventListener('simulation_complete', e => {
        const d = JSON.parse((e as MessageEvent).data)
        setStatus('done')
        addFeed('system', `Simulation complete! ${d.summary || ''}`)
        es.close()

        // Pass report to chat via global callback
        if ((window as any).__ariaAddCompletionMessage) {
          ;(window as any).__ariaAddCompletionMessage(d.summary, d.report)
        }

        // Re-fetch history from database to get the saved record with correct ID
        if (profileId) {
          fetch(`${API_BASE}/api/simulation/history/${profileId}`)
            .then(res => res.ok ? res.json() : { history: [] })
            .then(data => {
              const items: SimSnapshot[] = (data.history || []).map((h: any) => ({
                id:           h.simulation_id,
                scenarioName: h.scenario_name,
                scenarioType: h.scenario_type,
                completedAt:  h.completed_at,
                totalWeeks:   1,
                finalMetrics: h.report ? {
                  total_visits:    0,
                  total_revenue:   h.report.estimated_revenue || 0,
                  active_agents:   h.agent_count || 0,
                  churned_agents:  0,
                  week:            1,
                } : null,
                agents:       [],
                feed:         [],
                influences:   [],
              }))
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
    if (esRef.current) { esRef.current.close(); esRef.current = null }
    setStatus('done')
    setScenarioName(snap.scenarioName)
    setScenarioType(snap.scenarioType)
    setTotalWeeks(snap.totalWeeks)
    setCurrentWeek(snap.totalWeeks)
    setMetrics(snap.finalMetrics)
    setAgents(snap.agents)
    setFeed(snap.feed)
    setInfluences(snap.influences)
    setIsPaused(false)
    agentsRef.current     = snap.agents
    feedRef.current       = snap.feed
    influencesRef.current = snap.influences
    metricsRef.current    = snap.finalMetrics
  }, [])

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
    setTotalWeeks(4)
    setIsPaused(false)
    setFeed([])
    setScenarioName('')
    setScenarioType('')
    setInfluences([])
    feedRef.current = []
    agentsRef.current = []
    influencesRef.current = []
    metricsRef.current = null
    totalWeeksRef.current = 4
    scenarioNameRef.current = ''
    scenarioTypeRef.current = ''
  }, [])

  return {
    status, agents, metrics, currentWeek, totalWeeks,
    isPaused, feed, scenarioName, influences,
    history, restoreSnapshot, deleteSnapshot,
    launch, togglePause, reset,
  }
}

function esc(s: string) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}
