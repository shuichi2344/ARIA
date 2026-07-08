'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import type { Scenario, BusinessProfile } from './types'
import { jsPDF } from 'jspdf'
import SimulationSettings from './SimulationSettings'
import type { SimulationSettingsState } from './SimulationSettings'
import { SIMULATION_MODES } from './SimulationSettings'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

const SCENARIO_ICONS: Record<string, string> = {
  price_change:           '💰',
  demand_surge:           '📈',
  operating_hours_change: '🕐',
  default:                '🔬',
}

// Template scenario definitions with optional user input
interface TemplateScenario extends Scenario {
  requires_input?: {
    field: string
    label: string
    placeholder: string
    hint: string
  }
}

const TEMPLATE_SCENARIOS: TemplateScenario[] = [
  {
    scenario_name: 'Price Change',
    scenario_type: 'price_change',
    description: 'Test how customers react to a price change',
    parameters: {},
    expected_impact: 'Depends on the percentage and your customer income mix',
    requires_input: {
      field: 'price_change_percent',
      label: 'Price change (%)',
      placeholder: 'e.g. 10 or -10',
      hint: 'Positive = increase, Negative = decrease',
    },
  },
  {
    scenario_name: 'Demand Surge',
    scenario_type: 'demand_surge',
    description: 'Simulate a sudden spike in customer demand (e.g. holiday, viral moment)',
    parameters: {},
    expected_impact: 'Tests if your business can handle increased traffic and maintain quality',
    requires_input: {
      field: 'demand_increase_percent',
      label: 'Demand increase (%)',
      placeholder: 'e.g. 50',
      hint: 'How much extra demand you expect (e.g. 50 = 50% more customers)',
    },
  },
  {
    scenario_name: 'Extended Hours',
    scenario_type: 'operating_hours_change',
    description: 'Test impact of extending your operating hours',
    parameters: {},
    expected_impact: 'May capture more customers during extended hours',
    requires_input: {
      field: 'hours_extension',
      label: 'Extra hours per day',
      placeholder: 'e.g. 2',
      hint: 'How many additional hours you plan to stay open (must be a positive whole number)',
    },
  },
]

interface Message {
  id: string | number  // Allow both for backwards compatibility
  role: 'user' | 'aria' | 'typing'
  text?: string
  hint?: string
  showChipPrompt?: boolean
}

// Generate unique message ID
let msgId = 0
const generateMsgId = (): string => {
  return `${Date.now()}-${msgId++}`
}

interface Props {
  profile: BusinessProfile | null
  onLaunch: (scenario: Scenario, agentCount?: number, options?: { income_constraints?: string[] | null; age_constraints?: string[] | null; target_customer_constraints?: string[] | null; business_size_constraints?: string[] | null; b2b_percentage?: number | null; chat_session_id?: string | null }) => void
  onSimulationComplete?: (summary: string) => void
  onReset?: () => void
  simulationStatus?: 'idle' | 'running' | 'paused' | 'done'
}

export default function ChatPanel({ profile, onLaunch, onSimulationComplete, onReset, simulationStatus = 'idle' }: Props) {
  const [messages,  setMessages]  = useState<Message[]>([{
    id: generateMsgId(), role: 'aria',
    text: "Hi! I'm ARIA. Tell me about a business scenario you'd like to simulate.",
    hint: 'Try: "What happens if I raise prices by 10%?" or "A new competitor opened nearby."',
  }])
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const chatSessionRef = useRef<string | null>(null)
  
  // Fire-and-forget: save message to backend
  function persistMessage(role: 'user' | 'aria', content: string, metadata?: Record<string, unknown>) {
    let userId = ''
    try {
      const raw = typeof window !== 'undefined' ? localStorage.getItem('aria_session') : null
      if (raw) userId = JSON.parse(raw).id || ''
    } catch {}
    if (!userId) return
    fetch(`${API_BASE}/api/chat/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        profile_id: profile?.id,
        session_id: chatSessionRef.current,
        role,
        content,
        metadata,
      }),
    }).then(res => res.json()).then(data => {
      if (data.session_id) chatSessionRef.current = data.session_id
    }).catch(() => {})
  }  const [input,     setInput]     = useState('')
  const [loading,   setLoading]   = useState(false)
  const [useRealWorldContext, setUseRealWorldContext] = useState(false)
  const [hasStartedConversation, setHasStartedConversation] = useState(false)
  const [pendingTemplate, setPendingTemplate] = useState<TemplateScenario | null>(null)
  const [inputPromptValue, setInputPromptValue] = useState('')
  const [fallbackMode, setFallbackMode] = useState<import('@/components/dashboard/SimulationSettings').SimulationMode>('balanced')
  const [simulationSettings, setSimulationSettings] = useState<SimulationSettingsState | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [lastFailedQuery, setLastFailedQuery] = useState<string | null>(null)
  const [simulationRanInSession, setSimulationRanInSession] = useState(false)
  const feedRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const latestReportRef = useRef<any>(null)
  // Snapshot of the live chat (messages + report) saved when viewing history,
  // so we can restore the live chat when the user returns to the current simulation
  const liveChatSnapshotRef = useRef<{ messages: Message[]; report: any } | null>(null)
  // Tracks whether the user is currently viewing a past simulation (history)
  const viewingHistoryRef = useRef(false)

  // userId helper ref — avoids re-reading localStorage on every render
  const userIdRef = useRef<string>('')

  const handleSettingsChange = useCallback((settings: SimulationSettingsState) => {
    setSimulationSettings(prev => {
      // Clear agent cache if demographics/constraints changed
      if (prev && (
        JSON.stringify(prev.incomeConstraints) !== JSON.stringify(settings.incomeConstraints) ||
        JSON.stringify(prev.ageConstraints) !== JSON.stringify(settings.ageConstraints) ||
        JSON.stringify(prev.targetCustomerConstraints) !== JSON.stringify(settings.targetCustomerConstraints) ||
        JSON.stringify(prev.businessSizeConstraints) !== JSON.stringify(settings.businessSizeConstraints) ||
        prev.agentCount !== settings.agentCount ||
        prev.b2bPercentage !== settings.b2bPercentage
      )) {
        fetch(`${API_BASE}/api/simulation/cache/clear`, { method: 'POST' }).catch(() => {})
      }
      return settings
    })
  }, [])

  // Populate userIdRef on mount
  useEffect(() => {
    try {
      const raw = typeof window !== 'undefined' ? localStorage.getItem('aria_session') : null
      if (raw) userIdRef.current = JSON.parse(raw).id || ''
    } catch {}
  }, [])

  // Event delegation for PDF download button — survives re-renders and tab switches
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const target = e.target as HTMLElement
      if (target.id === 'download-report-btn' || target.closest('#download-report-btn')) {
        const report = latestReportRef.current
        if (!report) return
        const risk = report.risk_summary
        const breakdown = report.archetype_breakdown
        const recs = report.recommendations || []

        const doc = new jsPDF()
        const margin = 15
        const pageWidth = 180
        let y = 20

        // Helper: add new page when content would overflow
        function checkPage(needed: number) {
          if (y + needed > 280) {
            doc.addPage()
            y = 20
          }
        }

        // ── Title ──
        doc.setFontSize(18)
        doc.setFont('helvetica', 'bold')
        doc.text('ARIA Simulation Report', margin, y)
        y += 14

        // ── Scenario info ──
        doc.setFontSize(11)
        doc.setFont('helvetica', 'normal')
        doc.text(`Scenario: ${report.scenario?.name || 'Unknown'}`, margin, y); y += 7
        doc.setFontSize(10)
        const descLines: string[] = doc.splitTextToSize(report.scenario?.description || '', pageWidth)
        for (let i = 0; i < descLines.length; i++) {
          checkPage(6)
          doc.text(descLines[i], margin, y)
          y += 5
        }
        y += 10

        // ── Risk Summary ──
        checkPage(50)
        doc.setFontSize(14)
        doc.setFont('helvetica', 'bold')
        doc.text('Risk Summary', margin, y); y += 9
        doc.setFontSize(10)
        doc.setFont('helvetica', 'normal')
        doc.text(`Risk Level: ${risk.risk_level}`, margin + 4, y); y += 6
        doc.text(`Churn Rate: ${risk.churn_rate}%`, margin + 4, y); y += 6
        doc.text(`Visit Rate: ${risk.visit_rate}%`, margin + 4, y); y += 6
        doc.text(`Estimated Revenue: RM${risk.estimated_revenue.toFixed(2)}`, margin + 4, y); y += 6
        doc.text(`Total Customers: ${risk.total_agents}`, margin + 4, y); y += 8
        doc.setFontSize(8)
        doc.setTextColor(120)
        const revNote: string[] = doc.splitTextToSize('Note: Revenue is estimated from your business price range, adjusted by the scenario\'s price change. Each visiting customer spends a random amount within your configured price range.', pageWidth)
        for (let i = 0; i < revNote.length; i++) {
          doc.text(revNote[i], margin, y)
          y += 4
        }
        y += 4
        doc.setTextColor(0)

        // ── Customer/Personality Breakdown ──
        checkPage(60)
        doc.setFontSize(14)
        doc.setFont('helvetica', 'bold')
        doc.text(report.breakdown_type === 'personality' ? 'Personality Breakdown' : 'Customer Breakdown', margin, y); y += 9
        doc.setFontSize(10)
        doc.setFont('helvetica', 'normal')
        Object.entries(breakdown).forEach(([level, data]: [string, any]) => {
          doc.text(`${level}: ${data.visit_pct}% visit, ${data.skip_pct}% skip, ${data.churn_pct}% churn`, margin + 4, y)
          y += 6
        })
        y += 6

        // ── Stacked bar chart ──
        const barHeight = 14
        const barMaxWidth = 140
        const barX = margin + 40
        const chartColors = { visit: [34, 197, 94], skip: [234, 179, 8], churn: [239, 68, 68] }

        Object.entries(breakdown).forEach(([level, data]: [string, any]) => {
          checkPage(barHeight + 6)
          doc.setFontSize(9)
          doc.setFont('helvetica', 'normal')
          doc.setTextColor(0)
          doc.text(level, margin, y + barHeight / 2 + 1)

          const visitW = (data.visit_pct / 100) * barMaxWidth
          doc.setFillColor(chartColors.visit[0], chartColors.visit[1], chartColors.visit[2])
          doc.rect(barX, y, visitW, barHeight, 'F')

          const skipW = (data.skip_pct / 100) * barMaxWidth
          doc.setFillColor(chartColors.skip[0], chartColors.skip[1], chartColors.skip[2])
          doc.rect(barX + visitW, y, skipW, barHeight, 'F')

          const churnW = (data.churn_pct / 100) * barMaxWidth
          doc.setFillColor(chartColors.churn[0], chartColors.churn[1], chartColors.churn[2])
          doc.rect(barX + visitW + skipW, y, churnW, barHeight, 'F')

          y += barHeight + 4
        })

        // Legend
        y += 4
        doc.setFontSize(8)
        doc.setFont('helvetica', 'normal')
        doc.setFillColor(34, 197, 94); doc.rect(margin, y, 8, 5, 'F')
        doc.setTextColor(0); doc.text('Visit', margin + 10, y + 4)
        doc.setFillColor(234, 179, 8); doc.rect(margin + 30, y, 8, 5, 'F')
        doc.text('Skip', margin + 40, y + 4)
        doc.setFillColor(239, 68, 68); doc.rect(margin + 60, y, 8, 5, 'F')
        doc.text('Churn', margin + 70, y + 4)
        y += 14

        // ── Analysis ──
        const analysis = report.analysis || ''
        if (analysis) {
          checkPage(30)
          doc.setFontSize(14)
          doc.setFont('helvetica', 'bold')
          doc.setTextColor(0)
          doc.text('Analysis', margin, y); y += 9
          doc.setFontSize(10)
          doc.setFont('helvetica', 'normal')
          const analysisLines: string[] = doc.splitTextToSize(analysis, pageWidth)
          for (let i = 0; i < analysisLines.length; i++) {
            checkPage(6)
            doc.text(analysisLines[i], margin + 4, y)
            y += 5
          }
          y += 8
        }

        // ── Key Reasons ──
        const keyReasons = report.key_reasons || []
        if (keyReasons.length > 0) {
          checkPage(20)
          doc.setFontSize(14)
          doc.setFont('helvetica', 'bold')
          doc.setTextColor(0)
          doc.text('Key Reasons for Skip/Churn', margin, y); y += 9
          doc.setFontSize(10)
          doc.setFont('helvetica', 'normal')
          doc.setTextColor(60)
          keyReasons.forEach((r: string, i: number) => {
            const reasonLines: string[] = doc.splitTextToSize(`${i + 1}. ${r}`, pageWidth - 4)
            for (let j = 0; j < reasonLines.length; j++) {
              checkPage(6)
              doc.text(reasonLines[j], margin + 4, y)
              y += 5
            }
            y += 3
          })
          y += 6
        }

        // ── Recommendations ──
        if (recs.length > 0) {
          checkPage(20)
          doc.setFontSize(14)
          doc.setFont('helvetica', 'bold')
          doc.setTextColor(0)
          doc.text('Recommendations', margin, y); y += 9
          doc.setFontSize(10)
          doc.setFont('helvetica', 'normal')
          doc.setTextColor(0)
          recs.forEach((r: string, i: number) => {
            const clean = r.replace(/\*\*/g, '')
            const lines: string[] = doc.splitTextToSize(`${i + 1}. ${clean}`, pageWidth - 4)
            for (let j = 0; j < lines.length; j++) {
              checkPage(6)
              doc.text(lines[j], margin + 4, y)
              y += 5
            }
            y += 4
          })
          y += 6
        }

        // ── Disclaimer ──
        checkPage(15)
        doc.setFontSize(8)
        doc.setFont('helvetica', 'italic')
        doc.setTextColor(120)
        const disclaimerLines: string[] = doc.splitTextToSize(report.disclaimer || '', pageWidth)
        for (let i = 0; i < disclaimerLines.length; i++) {
          checkPage(5)
          doc.text(disclaimerLines[i], margin, y)
          y += 4
        }

        // Build filename from scenario name and date
        const scenarioSlug = (report.scenario?.name || 'simulation')
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/^-|-$/g, '')
          .slice(0, 50)
        const dateStr = new Date().toISOString().slice(0, 10)
        doc.save(`aria-${scenarioSlug}-${dateStr}.pdf`)
      }
    }

    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [])

  // Listen for simulation completion
  useEffect(() => {
    if (onSimulationComplete) {
      // This will be called from parent when simulation completes
      // We'll add the message through a ref callback
    }
  }, [onSimulationComplete])

  // Expose new chat reset for the history sidebar
  useEffect(() => {
    ;(window as any).__ariaNewChat = () => {
      // Abort any pending API request
      if (abortRef.current) { abortRef.current.abort(); abortRef.current = null }
      // Clear cached agent personalities so next simulation generates fresh ones
      fetch(`${API_BASE}/api/simulation/cache/clear`, { method: 'POST' }).catch(() => {})
      // Reset history-viewing state and any saved live chat snapshot
      viewingHistoryRef.current = false
      liveChatSnapshotRef.current = null
      setMessages([{
        id: generateMsgId(), role: 'aria',
        text: "Hi! I'm ARIA. Tell me about a business scenario you'd like to simulate.",
        hint: 'Try: "What happens if I raise prices by 10%?" or "A new competitor opened nearby."',
      }])
      setScenarios([])
      setHasStartedConversation(false)
      setPendingTemplate(null)
      setInput('')
      setLoading(false)
      setLastFailedQuery(null)
      setSimulationRanInSession(false)
      // Reset simulation dashboard
      if (onReset) onReset()
    }

    // Clear for restore — like __ariaNewChat but sets an empty message list
    // so __ariaRestoreMessages can fill it without the welcome screen flashing
    ;(window as any).__ariaClearForRestore = () => {
      if (abortRef.current) { abortRef.current.abort(); abortRef.current = null }
      // Only mark as viewing history if there's a live snapshot to protect
      // (i.e., a simulation was running/completed). This prevents blocking
      // the injectRestoredReport call that intentionally displays in the history view.
      if (liveChatSnapshotRef.current) {
        viewingHistoryRef.current = true
      }
      setMessages([])
      setScenarios([])
      setHasStartedConversation(true)
      setPendingTemplate(null)
      setInput('')
      setLoading(false)
      setLastFailedQuery(null)
      setSimulationRanInSession(true)
    }

    ;(window as any).__ariaRestoreMessages = (savedMessages: Array<{ role: string; content: string; metadata?: any }>) => {
      if (!savedMessages || savedMessages.length === 0) return
      const restored: Message[] = savedMessages.map(m => {
        // Report messages were saved with metadata.report — rebuild the rich HTML card
        if (m.role === 'aria' && m.metadata?.report) {
          const report = m.metadata.report
          const risk = report.risk_summary
          if (risk) {
            const breakdown = report.archetype_breakdown || {}
            const recs = report.recommendations || []
            const reportHtml = `<div style="display:flex;flex-direction:column;gap:0.75rem;">
              <div style="font-weight:700;font-size:0.95rem;">📊 Simulation Report</div>
              <div style="background:${risk.risk_level === 'High' ? '#fef2f2' : risk.risk_level === 'Medium' ? '#fffbeb' : '#f0fdf4'};padding:0.6rem;border-radius:6px;border:1px solid ${risk.risk_level === 'High' ? '#fecaca' : risk.risk_level === 'Medium' ? '#fde68a' : '#bbf7d0'};">
                <div style="font-weight:600;margin-bottom:0.3rem;">Risk Level: ${risk.risk_level}</div>
                <div style="font-size:0.8rem;">• Churn rate: ${risk.churn_rate}%</div>
                <div style="font-size:0.8rem;">• Visit rate: ${risk.visit_rate}%</div>
                <div style="font-size:0.8rem;">• Est. revenue: RM${Number(risk.estimated_revenue).toFixed(2)}</div>
              </div>
              <div>
                <div style="font-weight:600;margin-bottom:0.3rem;">${report.breakdown_type === 'personality' ? 'Personality Breakdown:' : 'Customer Breakdown:'}</div>
                ${Object.entries(breakdown).map(([level, data]: [string, any]) =>
                  `<div style="font-size:0.8rem;">• ${level}: ${data.visit_pct}% visit, ${data.skip_pct}% skip, ${data.churn_pct}% churn</div>`
                ).join('')}
              </div>
              ${report.analysis ? `<div style="background:var(--gray-50);padding:0.5rem;border-radius:6px;border-left:3px solid var(--accent);">
                <div style="font-weight:600;font-size:0.8rem;margin-bottom:0.2rem;">Analysis:</div>
                <div style="font-size:0.8rem;color:var(--gray-700);">${report.analysis}</div>
              </div>` : ''}
              ${(report.key_reasons || []).length > 0 ? `<div><div style="font-weight:600;margin-bottom:0.5rem;">Key Reasons for Skip/Churn:</div>
                ${report.key_reasons.map((r: string, i: number) => `<div style="font-size:0.8rem;margin-bottom:0.5rem;padding-left:0.5rem;border-left:2px solid var(--accent);">${i + 1}. ${r}</div>`).join('')}</div>` : ''}
              ${recs.length > 0 ? `<div><div style="font-weight:600;margin-bottom:0.5rem;">Recommendations:</div>${recs.map((r: string) => `<div style="font-size:0.8rem;margin-bottom:0.5rem;padding-left:0.5rem;border-left:2px solid var(--accent);">${r.replace(/\*\*/g, '')}</div>`).join('')}</div>` : ''}
              ${report.disclaimer ? `<div style="font-size:0.7rem;color:var(--gray-400);font-style:italic;margin-top:0.25rem;">${report.disclaimer}</div>` : ''}
              <button id="download-report-btn" style="margin-top:0.5rem;padding:0.4rem 0.75rem;border-radius:6px;background:var(--accent);color:#fff;border:none;font-size:0.78rem;font-weight:600;cursor:pointer;">📄 Download PDF</button>
            </div>`
            // Store in ref so PDF download works
            latestReportRef.current = report
            return { id: generateMsgId(), role: 'aria' as const, text: reportHtml }
          }
        }
        return {
          id: generateMsgId(),
          role: (m.role === 'user' ? 'user' : 'aria') as 'user' | 'aria',
          text: m.content,
        }
      })
      setMessages(restored)
      setHasStartedConversation(true)
    }

    // Snapshot the current live chat before viewing history (so we can return to it)
    ;(window as any).__ariaSnapshotLiveChat = () => {
      setMessages(prev => {
        liveChatSnapshotRef.current = { messages: prev, report: latestReportRef.current }
        return prev
      })
      viewingHistoryRef.current = true
    }

    // Restore the live chat after viewing history
    ;(window as any).__ariaRestoreLiveChat = () => {
      viewingHistoryRef.current = false
      const snap = liveChatSnapshotRef.current
      if (snap) {
        setMessages(snap.messages)
        latestReportRef.current = snap.report
        setHasStartedConversation(true)
      }
    }

    return () => {
      delete (window as any).__ariaNewChat
      delete (window as any).__ariaClearForRestore
      delete (window as any).__ariaRestoreMessages
      delete (window as any).__ariaSnapshotLiveChat
      delete (window as any).__ariaRestoreLiveChat
    }
  }, [onReset])

  // Expose a method to add completion message with report
  useEffect(() => {
    if (onSimulationComplete) {
      (window as any).__ariaAddCompletionMessage = (summary: string, report?: any) => {
        if (report) {
          // Build rich report message
          const risk = report.risk_summary
          const breakdown = report.archetype_breakdown
          const recs = report.recommendations || []
          
          let reportHtml = `<div style="display:flex;flex-direction:column;gap:0.75rem;">
            <div style="font-weight:700;font-size:0.95rem;">📊 Simulation Report</div>
            
            <div style="background:${risk.risk_level === 'High' ? '#fef2f2' : risk.risk_level === 'Medium' ? '#fffbeb' : '#f0fdf4'};padding:0.6rem;border-radius:6px;border:1px solid ${risk.risk_level === 'High' ? '#fecaca' : risk.risk_level === 'Medium' ? '#fde68a' : '#bbf7d0'};">
              <div style="font-weight:600;margin-bottom:0.3rem;">Risk Level: ${risk.risk_level}</div>
              <div style="font-size:0.8rem;">• Churn rate: ${risk.churn_rate}%</div>
              <div style="font-size:0.8rem;">• Visit rate: ${risk.visit_rate}%</div>
              <div style="font-size:0.8rem;">• Est. revenue: RM${risk.estimated_revenue.toFixed(2)}</div>
              <div style="font-size:0.68rem;color:var(--gray-500);margin-top:0.25rem;font-style:italic;">Revenue is estimated from your business price range, adjusted by the scenario's price change. Each visiting customer spends a random amount within your configured price range.</div>
            </div>
            
            <div>
              <div style="font-weight:600;margin-bottom:0.3rem;">${report.breakdown_type === 'personality' ? 'Personality Breakdown:' : 'Customer Breakdown:'}</div>
              ${Object.entries(breakdown).map(([level, data]: [string, any]) => 
                `<div style="font-size:0.8rem;">• ${level}: ${data.visit_pct}% visit, ${data.skip_pct}% skip, ${data.churn_pct}% churn</div>`
              ).join('')}
            </div>
            
            ${report.analysis ? `<div style="background:var(--gray-50);padding:0.5rem;border-radius:6px;border-left:3px solid var(--accent);">
              <div style="font-weight:600;font-size:0.8rem;margin-bottom:0.2rem;">Analysis:</div>
              <div style="font-size:0.8rem;color:var(--gray-700);">${report.analysis}</div>
            </div>` : ''}
            
            ${report.key_reasons && report.key_reasons.length > 0 ? `<div>
              <div style="font-weight:600;margin-bottom:0.5rem;">Key Reasons for Skip/Churn:</div>
              ${report.key_reasons.map((r: string, i: number) => `<div style="font-size:0.8rem;margin-bottom:0.5rem;padding-left:0.5rem;border-left:2px solid var(--accent);">${i + 1}. ${r}</div>`).join('')}
            </div>` : ''}
            
            <div>
              <div style="font-weight:600;margin-bottom:0.5rem;">Recommendations:</div>
              ${recs.map((r: string) => `<div style="font-size:0.8rem;margin-bottom:0.5rem;padding-left:0.5rem;border-left:2px solid var(--accent);">${r.replace(/\*\*/g, '')}</div>`).join('')}
            </div>
            
            <div style="font-size:0.7rem;color:var(--gray-400);font-style:italic;margin-top:0.25rem;">${report.disclaimer}</div>
            <button id="download-report-btn" style="margin-top:0.5rem;padding:0.4rem 0.75rem;border-radius:6px;background:var(--accent);color:#fff;border:none;font-size:0.78rem;font-weight:600;cursor:pointer;">📄 Download PDF</button>
          </div>`
          
          setMessages(p => {
            const reportMsg = {
              id: generateMsgId(),
              role: 'aria' as const,
              text: reportHtml,
            }
            // If the user is viewing history, append to the live snapshot instead
            // of the currently-displayed history view
            if (viewingHistoryRef.current && liveChatSnapshotRef.current) {
              liveChatSnapshotRef.current = {
                messages: [...liveChatSnapshotRef.current.messages, reportMsg],
                report,
              }
              return p  // don't touch the displayed history view
            }
            return [...p, reportMsg]
          })
          
          // Persist report to chat history
          persistMessage('aria', 'Simulation report generated', { report })
          
          // Store report in ref for the event delegation handler
          // (only update live ref if not viewing history)
          if (!viewingHistoryRef.current) {
            latestReportRef.current = report
          }
          
          // Mark that a simulation has been completed in this chat session
          setSimulationRanInSession(true)
        } else {
          setMessages(p => [...p, {
            id: generateMsgId(),
            role: 'aria',
            text: '✓ Simulation complete!',
            hint: summary || 'Check the results on the right panel.'
          }])
        }
      }
    }
  }, [onSimulationComplete])

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight
  }, [messages, scenarios])

  async function send(e: React.FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading || simulationStatus === 'running' || simulationStatus === 'paused') return
    
    // Abort any pending request
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller
    
    setInput('')
    setMessages(p => [...p, { id: generateMsgId(), role: 'user', text }])
    persistMessage('user', text)
    setScenarios([])
    setLoading(true)
    setMessages(p => [...p, { id: generateMsgId(), role: 'typing' }])
    
    // Mark that user has started conversation
    setHasStartedConversation(true)

    try {
      console.log('[ChatPanel] Sending request to:', `${API_BASE}/api/simulation/suggest`)
      console.log('[ChatPanel] Request body:', { user_question: text, business_profile: profile })
      
      const res = await fetch(`${API_BASE}/api/simulation/suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_question:    text,
          business_profile: profile || { business_name: 'Unknown', business_type: 'Unknown' },
          use_external_context: useRealWorldContext,
          chat_session_id: chatSessionRef.current,
        }),
        signal: controller.signal,
      })
      
      console.log('[ChatPanel] Response status:', res.status)
      
      if (!res.ok) throw new Error('Suggestion failed')
      const data = await res.json()
      
      console.log('[ChatPanel] Response data:', data)
      console.log('[ChatPanel] Scenarios:', data.scenarios)
      
      if (!data.scenarios || data.scenarios.length === 0) {
        // LLM failed to generate scenarios — show error with retry
        setLastFailedQuery(text)
        const ariaText = data.analysis || "I had trouble generating scenarios for that question."
        setMessages(p => [
          ...p.filter(m => m.role !== 'typing'),
          { id: generateMsgId(), role: 'aria', text: ariaText, hint: "The AI response couldn't be processed. You can retry or rephrase your question." },
        ])
        persistMessage('aria', ariaText)
      } else {
        setLastFailedQuery(null)
        setMessages(p => [
          ...p.filter(m => m.role !== 'typing'),
          { id: generateMsgId(), role: 'aria', text: data.analysis, hint: data.recommended_action, showChipPrompt: true },
        ])
        setScenarios(data.scenarios || [])
        persistMessage('aria', data.analysis, { scenarios: data.scenarios })
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setLastFailedQuery(text)
      setMessages(p => [
        ...p.filter(m => m.role !== 'typing'),
        { id: generateMsgId(), role: 'aria', text: "I couldn't connect to the AI right now.", hint: 'Make sure the API server is running. You can retry below.' },
      ])
    } finally {
      setLoading(false)
    }
  }

  async function handleRetry() {
    if (!lastFailedQuery || loading) return
    const text = lastFailedQuery
    setLastFailedQuery(null)
    setMessages(p => [...p, { id: generateMsgId(), role: 'user', text: `(retry) ${text}` }])
    setScenarios([])
    setLoading(true)
    setMessages(p => [...p, { id: generateMsgId(), role: 'typing' }])

    // Abort any pending request
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await fetch(`${API_BASE}/api/simulation/suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_question: text,
          business_profile: profile || { business_name: 'Unknown', business_type: 'Unknown' },
          use_external_context: useRealWorldContext,
          chat_session_id: chatSessionRef.current,
        }),
        signal: controller.signal,
      })

      if (!res.ok) throw new Error('Suggestion failed')
      const data = await res.json()

      if (!data.scenarios || data.scenarios.length === 0) {
        setLastFailedQuery(text)
        setMessages(p => [
          ...p.filter(m => m.role !== 'typing'),
          { id: generateMsgId(), role: 'aria', text: data.analysis || "Still having trouble generating scenarios.", hint: "The AI couldn't process this. Try rephrasing your question differently." },
        ])
      } else {
        setMessages(p => [
          ...p.filter(m => m.role !== 'typing'),
          { id: generateMsgId(), role: 'aria', text: data.analysis, hint: data.recommended_action, showChipPrompt: true },
        ])
        setScenarios(data.scenarios || [])
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setLastFailedQuery(text)
      setMessages(p => [
        ...p.filter(m => m.role !== 'typing'),
        { id: generateMsgId(), role: 'aria', text: "Still couldn't connect to the AI.", hint: 'Check that the API server and Ollama are running.' },
      ])
    } finally {
      setLoading(false)
    }
  }

  function handleChip(s: Scenario | TemplateScenario) {
    // Don't allow launching if simulation is already running
    if (simulationStatus === 'running' || simulationStatus === 'paused') return
    
    // Check if this template requires user input
    if ('requires_input' in s && s.requires_input) {
      setPendingTemplate(s as TemplateScenario)
      setInputPromptValue('')
      return
    }
    
    launchScenario(s)
  }

  function handleInputPromptSubmit() {
    if (!pendingTemplate || !pendingTemplate.requires_input) return
    
    const value = parseFloat(inputPromptValue)
    if (isNaN(value)) return
    
    const field = pendingTemplate.requires_input.field
    
    // Validate hours_extension: must be a positive integer
    if (field === 'hours_extension') {
      if (value <= 0 || !Number.isInteger(value)) {
        alert('Extended hours must be a positive whole number (e.g., 1, 2, 3)')
        return
      }
    }
    
    let scenarioName: string
    let description: string
    
    if (field === 'price_change_percent') {
      scenarioName = `${value > 0 ? '+' : ''}${value}% Price Change`
      description = value > 0
        ? `Prices are increased by ${value}% across all products/services`
        : `Prices are reduced by ${Math.abs(value)}% across all products/services`
    } else if (field === 'demand_increase_percent') {
      scenarioName = `Demand Surge (+${value}%)`
      description = `Customer demand increases by ${value}%, simulating a holiday rush, viral moment, or seasonal peak`
    } else {
      scenarioName = `Extended Hours (+${value}h)`
      description = `Operating hours are extended by ${value} hours daily, providing more availability for customers`
    }
    
    const scenario: Scenario = {
      ...pendingTemplate,
      parameters: { ...pendingTemplate.parameters, [field]: value },
      scenario_name: scenarioName,
      description,
    }
    
    setPendingTemplate(null)
    setInputPromptValue('')
    launchScenario(scenario)
  }

  function launchScenario(s: Scenario) {
    // Starting a fresh simulation — no longer viewing history
    viewingHistoryRef.current = false
    liveChatSnapshotRef.current = null
    // Mark that user has started conversation
    setHasStartedConversation(true)
    
    // Add user message showing selected scenario
    const userMsg = `Run simulation: ${s.scenario_name}`
    setMessages(p => [...p, { 
      id: generateMsgId(), 
      role: 'user', 
      text: userMsg
    }])
    persistMessage('user', userMsg)
    
    // Add ARIA confirmation message
    const ariaMsg = `Starting simulation for "${s.scenario_name}"…\n${s.description || ''}`
    setMessages(p => [...p, { 
      id: generateMsgId(), 
      role: 'aria', 
      text: `Starting simulation for "${s.scenario_name}"…`,
      hint: s.description
    }])
    persistMessage('aria', ariaMsg)
    
    // Attach business_profile (including customer_profile) to scenario
    const scenarioWithProfile = {
      ...s,
      business_profile: profile || undefined,
    }
    
    // Determine constraints: omit (pass null) when all levels/groups are enabled
    const ALL_INCOME_LEVELS = ['B40', 'M40', 'T20']
    const ALL_AGE_GROUPS = ['20-29', '30-39', '40-49', '50-59', '60+']
    
    const incomeConstraints = simulationSettings
      && simulationSettings.incomeConstraints.length < ALL_INCOME_LEVELS.length
      ? simulationSettings.incomeConstraints
      : null
    
    const ageConstraints = simulationSettings
      && simulationSettings.ageConstraints.length < ALL_AGE_GROUPS.length
      ? simulationSettings.ageConstraints
      : null
    
    // B2B constraints
    const targetCustomerConstraints = simulationSettings?.targetCustomerConstraints?.length
      ? simulationSettings.targetCustomerConstraints
      : null
    
    const businessSizeConstraints = simulationSettings?.businessSizeConstraints?.length
      ? simulationSettings.businessSizeConstraints
      : null
    
    setScenarios([])
    const resolvedAgentCount = simulationSettings?.agentCount ?? SIMULATION_MODES[fallbackMode].agentCount
    onLaunch(scenarioWithProfile, resolvedAgentCount, {
      income_constraints: incomeConstraints,
      age_constraints: ageConstraints,
      target_customer_constraints: targetCustomerConstraints,
      business_size_constraints: businessSizeConstraints,
      b2b_percentage: simulationSettings?.b2bPercentage ?? null,
      chat_session_id: chatSessionRef.current,
    })
  }

  return (
    <aside style={{
      display: 'flex', flexDirection: 'column',
      borderRight: '1px solid var(--gray-200)',
      background: 'var(--white)', overflow: 'hidden',
      position: 'relative',
    }}>
      {/* Settings drawer — slides in from the right over the chat panel */}
      {/* Settings drawer — always mounted to preserve state, visibility toggled via CSS */}
      {profile?.district && (
        <>
          {/* Backdrop — only interactive when open */}
          <div
            onClick={() => setSettingsOpen(false)}
            style={{
              position: 'absolute', inset: 0, zIndex: 10,
              background: 'rgba(0,0,0,0.15)',
              opacity: settingsOpen ? 1 : 0,
              pointerEvents: settingsOpen ? 'auto' : 'none',
              transition: 'opacity 0.2s ease',
            }}
          />
          {/* Drawer */}
          <div style={{
            position: 'absolute', top: 0, right: 0, bottom: 0,
            width: '100%', zIndex: 11,
            background: 'var(--white)',
            borderLeft: '1px solid var(--gray-200)',
            display: 'flex', flexDirection: 'column',
            boxShadow: '-4px 0 16px rgba(0,0,0,0.08)',
            transform: settingsOpen ? 'translateX(0)' : 'translateX(100%)',
            transition: 'transform 0.2s ease',
          }}>
            {/* Drawer header */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '1rem 1.25rem',
              borderBottom: '1px solid var(--gray-100)',
              flexShrink: 0,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '0.95rem', color: 'var(--gray-900)' }}>
                <svg style={{ width: 18, height: 18 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3"/>
                  <path d="M19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14"/>
                  <path d="M12 2v2M12 20v2M2 12h2M20 12h2"/>
                </svg>
                Simulation Settings
              </div>
              <button
                onClick={() => setSettingsOpen(false)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--gray-500)', padding: '0.25rem', borderRadius: 4,
                  display: 'flex', alignItems: 'center',
                  transition: 'color 0.15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.color = 'var(--gray-900)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'var(--gray-500)')}
                aria-label="Close settings"
              >
                <svg style={{ width: 18, height: 18 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
            {/* Drawer content */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <SimulationSettings
                district={profile.district}
                disabled={simulationStatus === 'running' || simulationStatus === 'paused'}
                onSettingsChange={handleSettingsChange}
                customerProfile={profile.customer_profile as Record<string, unknown> | undefined}
              />

            </div>
          </div>
        </>
      )}

      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '1rem 1.25rem',
        borderBottom: '1px solid var(--gray-100)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontWeight: 700, fontSize: '0.95rem', color: 'var(--gray-900)' }}>
          <svg style={{ width: 20, height: 20 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
          Scenario Chat
        </div>
        {/* Settings button — only shown when a district profile is loaded */}
        {profile?.district && (
          <button
            onClick={() => setSettingsOpen(o => !o)}
            title="Simulation settings"
            style={{
              background: settingsOpen ? 'var(--accent)' : 'none',
              border: `1.5px solid ${settingsOpen ? 'var(--accent)' : 'var(--gray-200)'}`,
              borderRadius: 6, cursor: 'pointer',
              color: settingsOpen ? 'white' : 'var(--gray-600)',
              padding: '0.3rem 0.6rem',
              display: 'flex', alignItems: 'center', gap: '0.35rem',
              fontSize: '0.75rem', fontWeight: 600,
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
              if (!settingsOpen) {
                (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)'
                ;(e.currentTarget as HTMLElement).style.color = 'var(--accent)'
              }
            }}
            onMouseLeave={e => {
              if (!settingsOpen) {
                (e.currentTarget as HTMLElement).style.borderColor = 'var(--gray-200)'
                ;(e.currentTarget as HTMLElement).style.color = 'var(--gray-600)'
              }
            }}
          >
            <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3"/>
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
            </svg>
            Settings
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={feedRef} style={{
        flex: 1, overflowY: 'auto', padding: '1rem',
        display: 'flex', flexDirection: 'column', gap: '0.75rem',
        scrollBehavior: 'smooth',
      }}>
        {messages.map(m => (
          <div key={m.id} style={{
            display: 'flex', gap: '0.6rem', alignItems: 'flex-start',
            flexDirection: m.role === 'user' ? 'row-reverse' : 'row',
          }}>
            {/* Avatar */}
            <div style={{
              width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: m.role === 'user' ? 'var(--gray-200)'
                : 'linear-gradient(135deg, var(--accent), var(--accent-warm))',
              color: m.role === 'user' ? 'var(--gray-600)' : 'white',
              fontSize: 11,
            }}>
              {m.role === 'user' ? '👤' : '🤖'}
            </div>

            {/* Bubble */}
            {m.role === 'typing' ? (
              <div style={{
                background: 'var(--gray-50)', borderRadius: '12px 12px 12px 4px',
                padding: '0.75rem 1rem', display: 'flex', gap: 4, alignItems: 'center',
              }}>
                {[0, 200, 400].map(d => (
                  <span key={d} style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: 'var(--gray-400)',
                    display: 'inline-block',
                    animation: `typing-bounce 1.2s ${d}ms infinite`,
                  }} />
                ))}
              </div>
            ) : (
              <div style={{
                maxWidth: '85%',
                background: m.role === 'user' ? 'var(--accent)' : 'var(--gray-50)',
                borderRadius: m.role === 'user' ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
                padding: '0.65rem 0.9rem',
                fontSize: '0.875rem', lineHeight: 1.5,
                color: m.role === 'user' ? 'white' : 'var(--gray-900)',
              }}>
                {m.text && (
                  m.text.startsWith('<div')
                    ? <div style={{ margin: '0 0 0.4rem' }} dangerouslySetInnerHTML={{ __html: m.text }} />
                    : <p style={{ margin: '0 0 0.4rem' }}>{m.text}</p>
                )}
                {m.hint && (
                  <p style={{
                    margin: 0, fontSize: '0.8rem',
                    color: m.role === 'user' ? 'rgba(255,255,255,0.75)' : 'var(--gray-600)',
                  }}>
                    {m.hint}
                  </p>
                )}
                {m.showChipPrompt && (
                  <p style={{ margin: '0.4rem 0 0', fontSize: '0.8rem', color: 'var(--gray-600)' }}>
                    Choose a scenario below to run the simulation:
                  </p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Retry button — shown when scenario generation failed */}
      {lastFailedQuery && !loading && (simulationStatus === 'idle' || simulationStatus === 'done') && (
        <div style={{
          padding: '0.5rem 1rem',
          borderTop: '1px solid var(--gray-100)',
          display: 'flex', alignItems: 'center', gap: '0.75rem',
          flexShrink: 0,
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#ef4444', flexShrink: 0,
          }} />
          <span style={{ fontSize: '0.78rem', color: 'var(--gray-600)', flex: 1 }}>
            Scenario generation failed
          </span>
          <button
            type="button"
            onClick={handleRetry}
            style={{
              padding: '0.35rem 0.75rem', borderRadius: 6,
              background: 'var(--accent)', color: '#fff',
              border: 'none', fontWeight: 600, fontSize: '0.75rem',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem',
              transition: 'opacity 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
            onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
          >
            <svg style={{ width: 12, height: 12 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
            </svg>
            Retry
          </button>
        </div>
      )}

      {/* Scenario chips — scrollable, capped height so messages stay visible */}
      {scenarios.length > 0 && !simulationRanInSession && (simulationStatus === 'idle' || simulationStatus === 'done') && (
        <div style={{
          padding: '0.75rem 1rem',
          borderTop: '1px solid var(--gray-100)',
          display: 'flex', flexDirection: 'column', gap: '0.5rem',
          flexShrink: 0,
          maxHeight: '45%',   /* never eat more than 45% of the panel */
          overflowY: 'auto',
        }}>
          <p style={{
            margin: 0, fontSize: '0.72rem', fontWeight: 600,
            color: 'var(--gray-500)', textTransform: 'uppercase',
            letterSpacing: '0.05em', flexShrink: 0,
          }}>
            Choose a scenario
          </p>
          {scenarios.slice(0, 4).map((s, i) => (
            <ScenarioChip key={i} scenario={s} onClick={() => handleChip(s)} />
          ))}
        </div>
      )}

      {/* One simulation per chat: show prompt to start new chat after sim completes */}
      {simulationRanInSession && simulationStatus !== 'running' && simulationStatus !== 'paused' ? (
        <div style={{
          padding: '1rem',
          borderTop: '1px solid var(--gray-200)',
          display: 'flex', flexDirection: 'column', gap: '0.75rem',
          flexShrink: 0,
        }}>
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: '0.6rem',
            background: 'var(--gray-50)', borderRadius: 8,
            border: '1px solid var(--gray-200)',
            padding: '0.75rem',
          }}>
            <span style={{ fontSize: '1rem', flexShrink: 0 }}>💡</span>
            <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--gray-700)', lineHeight: 1.5 }}>
              Each chat supports one simulation scenario. Start a new chat to run a different scenario.
            </p>
          </div>
          <button
            type="button"
            onClick={() => (window as any).__ariaNewChat?.()}
            style={{
              padding: '0.6rem 1rem', borderRadius: 8,
              background: 'var(--accent)', color: '#fff',
              border: 'none', fontWeight: 600, fontSize: '0.85rem',
              cursor: 'pointer', width: '100%',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem',
              transition: 'opacity 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
            onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
          >
            <svg style={{ width: 15, height: 15 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Start New Chat
          </button>
        </div>
      ) : (
      <>
      {/* Input */}
      <form onSubmit={send} style={{
        display: 'flex', flexDirection: 'column', gap: '0.75rem',
        padding: '0.75rem 1rem',
        borderTop: '1px solid var(--gray-200)', flexShrink: 0,
      }}>
        {/* Template Scenarios Carousel - only show before any interaction and when no input prompt is active */}
        {!hasStartedConversation && !pendingTemplate && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {/* Simulation mode — shown as compact buttons when no district profile */}
            {(!profile || !profile.district) && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <label style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Simulation Mode
              </label>
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                {(Object.entries(SIMULATION_MODES) as [import('@/components/dashboard/SimulationSettings').SimulationMode, typeof SIMULATION_MODES[keyof typeof SIMULATION_MODES]][]).map(([mode, config]) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setFallbackMode(mode)}
                    title={config.description}
                    style={{
                      flex: 1, padding: '0.4rem 0.4rem', fontSize: '0.75rem',
                      fontWeight: fallbackMode === mode ? 700 : 500,
                      borderRadius: 6,
                      border: `1.5px solid ${fallbackMode === mode ? config.colorBorder : '#e5e7eb'}`,
                      background: fallbackMode === mode ? config.colorLight : 'white',
                      color: fallbackMode === mode ? config.colorText : 'var(--gray-500)',
                      cursor: 'pointer',
                    }}
                  >
                    {config.label}
                  </button>
                ))}
              </div>
              <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--gray-400)', fontStyle: 'italic' }}>
                {SIMULATION_MODES[fallbackMode].description} · {SIMULATION_MODES[fallbackMode].agentCount} agents
              </p>
            </div>
            )}

            <p style={{
              margin: 0, fontSize: '0.72rem', fontWeight: 600,
              color: 'var(--gray-500)', textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}>
              Quick Suggestions
            </p>
            <div style={{
              display: 'flex', gap: '0.5rem',
              overflowX: 'auto', overflowY: 'hidden',
              paddingBottom: '0.5rem',
              scrollbarWidth: 'thin',
              scrollbarColor: 'var(--gray-300) transparent',
            }}>
              {TEMPLATE_SCENARIOS.map((s, i) => (
                <TemplateScenarioCard key={i} scenario={s} onClick={() => handleChip(s)} />
              ))}
            </div>
          </div>
        )}

        {/* Input prompt for templates that require user input */}
        {pendingTemplate && pendingTemplate.requires_input && (
          <div style={{
            display: 'flex', flexDirection: 'column', gap: '0.5rem',
            padding: '0.75rem',
            background: 'var(--gray-50)',
            borderRadius: 8,
            border: '1px solid var(--accent)',
          }}>
            <p style={{ margin: 0, fontSize: '0.82rem', fontWeight: 600, color: 'var(--gray-800)' }}>
              {pendingTemplate.requires_input.label}
            </p>
            <p style={{ margin: 0, fontSize: '0.72rem', color: 'var(--gray-500)' }}>
              {pendingTemplate.requires_input.hint}
            </p>
            <input
              type="number"
              value={inputPromptValue}
              onChange={e => setInputPromptValue(e.target.value)}
              placeholder={pendingTemplate.requires_input.placeholder}
              autoFocus
              onKeyDown={e => { if (e.key === 'Enter') handleInputPromptSubmit() }}
              // Add validation attributes for hours_extension
              min={pendingTemplate.requires_input.field === 'hours_extension' ? 1 : undefined}
              step={pendingTemplate.requires_input.field === 'hours_extension' ? 1 : undefined}
              style={{
                width: '100%', padding: '0.5rem 0.75rem', borderRadius: 6,
                border: '1px solid var(--gray-300)', fontSize: '0.85rem',
                outline: 'none', boxSizing: 'border-box',
              }}
            />
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={handleInputPromptSubmit}
                disabled={!inputPromptValue || isNaN(parseFloat(inputPromptValue))}
                style={{
                  flex: 1, padding: '0.5rem', borderRadius: 6,
                  background: 'var(--accent)', color: '#fff',
                  border: 'none', fontWeight: 600, fontSize: '0.82rem',
                  cursor: 'pointer', opacity: (!inputPromptValue || isNaN(parseFloat(inputPromptValue))) ? 0.5 : 1,
                }}
              >
                Run Simulation
              </button>
              <button
                type="button"
                onClick={() => setPendingTemplate(null)}
                style={{
                  padding: '0.5rem 0.75rem', borderRadius: 6,
                  background: 'var(--gray-200)', color: 'var(--gray-600)',
                  border: 'none', fontSize: '0.82rem', cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Simulation running indicator */}
        {(simulationStatus === 'running' || simulationStatus === 'paused') && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.75rem',
            background: 'var(--gray-50)',
            borderRadius: 8,
            border: '1px solid var(--gray-200)',
          }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: simulationStatus === 'running' ? '#22c55e' : '#f59e0b',
              animation: simulationStatus === 'running' ? 'pulse-dot 1.2s infinite' : 'none',
            }} />
            <span style={{ fontSize: '0.8rem', color: 'var(--gray-600)' }}>
              {simulationStatus === 'running' ? 'Simulation running...' : 'Simulation paused'}
            </span>
          </div>
        )}

        {/* Input Row */}
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {/* Real-world context toggle — inline with input */}
          <button
            type="button"
            onClick={() => setUseRealWorldContext(v => !v)}
            disabled={simulationStatus === 'running' || simulationStatus === 'paused'}
            title="Turn this on when your question involves external factors like price changes, economic trends, or market conditions. This pulls recent news and economic data to make scenarios more realistic."
            style={{
              width: 36, height: 36, borderRadius: 8, flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              border: `1.5px solid ${useRealWorldContext ? 'var(--accent)' : 'var(--gray-200)'}`,
              background: useRealWorldContext ? 'rgba(99, 102, 241, 0.1)' : 'transparent',
              cursor: (simulationStatus === 'running' || simulationStatus === 'paused') ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
              opacity: (simulationStatus === 'running' || simulationStatus === 'paused') ? 0.5 : 1,
              position: 'relative',
            }}
            aria-label={useRealWorldContext ? 'Real-world context enabled' : 'Enable real-world context'}
          >
            <span style={{ fontSize: '1rem', lineHeight: 1 }}>🌐</span>
            {/* Active indicator dot */}
            {useRealWorldContext && (
              <span style={{
                position: 'absolute', top: 4, right: 4,
                width: 6, height: 6, borderRadius: '50%',
                background: 'var(--accent)',
              }} />
            )}
          </button>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={
              simulationStatus === 'running' || simulationStatus === 'paused'
                ? 'Wait for simulation to complete...'
                : useRealWorldContext
                  ? 'Ask about market trends, economic factors...'
                  : 'Describe your scenario...'
            }
            maxLength={500}
            disabled={loading || simulationStatus === 'running' || simulationStatus === 'paused'}
            style={{
              flex: 1,
            borderWidth: '2px',
            borderStyle: 'solid',
            borderColor: 'var(--gray-200)',
            borderRadius: 8,
              padding: '0.6rem 0.9rem', fontSize: '0.875rem',
              fontFamily: 'var(--font-family)', color: 'var(--gray-900)',
              background: (simulationStatus === 'running' || simulationStatus === 'paused') ? 'var(--gray-50)' : 'var(--white)',
              outline: 'none',
              transition: 'border-color 0.2s, background 0.2s',
              cursor: (simulationStatus === 'running' || simulationStatus === 'paused') ? 'not-allowed' : 'text',
            }}
            onFocus={e => {
              if (simulationStatus === 'idle' || simulationStatus === 'done') {
                e.target.style.borderColor = 'var(--accent)'
              }
            }}
            onBlur={e => (e.target.style.borderColor = 'var(--gray-200)')}
          />
          <button
            type="submit"
            disabled={loading || !input.trim() || simulationStatus === 'running' || simulationStatus === 'paused'}
            style={{
              width: 40, height: 40, borderRadius: 8,
              background: 'var(--accent)', border: 'none',
              color: 'white', 
              cursor: (loading || !input.trim() || simulationStatus === 'running' || simulationStatus === 'paused') ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0, 
              opacity: (loading || !input.trim() || simulationStatus === 'running' || simulationStatus === 'paused') ? 0.4 : 1,
              transition: 'opacity 0.2s',
            }}
          >
            <svg style={{ width: 18, height: 18 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
      </form>
      </>
      )}

      <style>{`
        @keyframes typing-bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-6px); }
        }
        
        /* Custom scrollbar for horizontal scroll */
        div::-webkit-scrollbar {
          height: 6px;
        }
        div::-webkit-scrollbar-track {
          background: transparent;
        }
        div::-webkit-scrollbar-thumb {
          background: var(--gray-300);
          border-radius: 3px;
        }
        div::-webkit-scrollbar-thumb:hover {
          background: var(--gray-400);
        }
      `}</style>
    </aside>
  )
}

function TemplateScenarioCard({ scenario, onClick }: { scenario: Scenario; onClick: () => void }) {
  const [hov, setHov] = useState(false)
  const icon = SCENARIO_ICONS[scenario.scenario_type] || SCENARIO_ICONS.default
  
  return (
    <button
      type="button"  // Prevent form submission
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', flexDirection: 'column', gap: '0.4rem',
        background: hov ? 'var(--white)' : 'var(--gray-50)',
        border: `1.5px solid ${hov ? 'var(--accent)' : 'var(--gray-200)'}`,
        borderRadius: 8, padding: '0.75rem',
        cursor: 'pointer', textAlign: 'left',
        minWidth: 180, maxWidth: 180,
        flexShrink: 0,
        transition: 'all 0.2s',
        fontFamily: 'var(--font-family)',
        transform: hov ? 'translateY(-2px)' : 'translateY(0)',
        boxShadow: hov ? '0 4px 12px rgba(0,0,0,0.08)' : 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span style={{ fontSize: '1.2rem' }}>{icon}</span>
        <span style={{ 
          fontSize: '0.8rem', 
          fontWeight: 700, 
          color: 'var(--gray-900)',
          lineHeight: 1.2,
          flex: 1,
        }}>
          {scenario.scenario_name}
        </span>
      </div>
      <span style={{ 
        fontSize: '0.72rem', 
        color: 'var(--gray-600)', 
        lineHeight: 1.3,
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden',
      }}>
        {scenario.description}
      </span>
    </button>
  )
}

function ScenarioChip({ scenario, onClick }: { scenario: Scenario; onClick: () => void }) {
  const [hov, setHov] = useState(false)
  const icon = SCENARIO_ICONS[scenario.scenario_type] || SCENARIO_ICONS.default
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'flex-start', gap: '0.6rem',
        background: hov ? 'var(--white)' : 'var(--gray-50)',
        border: `1.5px solid ${hov ? 'var(--accent)' : 'var(--gray-200)'}`,
        borderRadius: 8, padding: '0.6rem 0.8rem',
        cursor: 'pointer', textAlign: 'left', width: '100%',
        transition: 'border-color 0.2s, background 0.2s',
        fontFamily: 'var(--font-family)',
      }}
    >
      <span style={{ fontSize: '1.1rem', flexShrink: 0, marginTop: 1 }}>{icon}</span>
      <span style={{ flex: 1 }}>
        <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--gray-900)', display: 'block' }}>
          {scenario.scenario_name}
        </span>
        <span style={{ fontSize: '0.78rem', color: 'var(--gray-600)', marginTop: '0.15rem', display: 'block' }}>
          {scenario.description}
        </span>
        {scenario.expected_impact && (
          <span style={{ fontSize: '0.75rem', color: 'var(--accent)', marginTop: '0.2rem', display: 'block', fontWeight: 500 }}>
            {scenario.expected_impact}
          </span>
        )}
      </span>
    </button>
  )
}
