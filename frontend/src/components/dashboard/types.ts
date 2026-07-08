export interface AriaSession {
  id: string
  email: string
  created_at: string
}

export interface BusinessProfile {
  id?: string
  business_name?: string
  business_type?: string
  location?: string
  district?: string
  years_operating?: number
  unique_selling_points?: string
  price_range_min?: number
  price_range_max?: number
  customer_profile?: Record<string, unknown>
}

export interface Scenario {
  scenario_name: string
  scenario_type: string
  description: string
  expected_impact?: string
  parameters?: Record<string, unknown>
  business_profile?: BusinessProfile
}

export interface Agent {
  agent_id: number
  persona_name: string
  income_level: string
  age_range: string
  is_active: boolean
  last_decision: string | null
  reasoning: string | null
  personality?: string
  personality_type?: string
}

export type SimStatus = 'idle' | 'running' | 'paused' | 'done'

export interface WeekSummary {
  week: number
  total_visits: number
  total_revenue: number
  active_agents: number
  churned_agents: number
}

export interface FeedItem {
  id: number
  type: 'visit' | 'skip' | 'churn' | 'week' | 'system'
  html: string
  agentId?: number  // Agent associated with this event (for click-to-highlight)
}

export interface InfluenceEdge {
  from_agent_id: number
  to_agent_id: number
  influence_type: 'reinforced' | 'contrasted' | 'message_propagation'
  from_decision: string
  to_decision: string
  week: number
  original_message?: string
  altered_message?: string
  influence_probability?: number
}

export interface SimSnapshot {
  id: string                  // uuid
  scenarioName: string
  scenarioType: string
  description: string
  completedAt: string         // ISO string
  totalWeeks: number
  finalMetrics: WeekSummary | null
  report: SimReport | null
  sessionId: string | null    // chat session to restore messages from
  agents: Agent[]
  feed: FeedItem[]
  influences: InfluenceEdge[]
}

export interface SimReport {
  risk_level: string
  churn_rate: number
  visit_rate: number
  estimated_revenue: number
  total_agents: number
  archetype_breakdown: Record<string, { visit_pct: number; skip_pct: number; churn_pct: number }>
  recommendations: string[]
  analysis?: string
  key_reasons?: string[]
}

