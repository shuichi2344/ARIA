/**
 * ARIA API client — wraps the FastAPI backend at NEXT_PUBLIC_API_URL.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export interface BusinessAnalyzeRequest {
  business_name: string
  business_type: string
  business_category_id?: string
  location: string
  district?: string
  years_operating?: number
  unique_selling_points?: string
}

export interface CustomerProfileResponse {
  customer_type: 'B2C' | 'B2B' | 'HYBRID'
  target_customers: string
  price_range?: { min: number; max: number }
  b2c_profile?: {
    target_segments?: string[]
    typical_age_groups?: string[]
    typical_income_levels: string[]
    purchase_frequency?: string
    avg_transaction_rm: number
    price_sensitivity?: string
  }
  b2b_profile?: {
    target_business_types: string[]
    business_size: string[]
    purchase_frequency: string
    avg_transaction_rm: number
    price_sensitivity?: string
    decision_factors?: string[]
  }
  reasoning: string
}

export interface BusinessProfileCreateRequest extends BusinessAnalyzeRequest {
  user_id: string
  target_audience?: string
  price_range_min?: number
  price_range_max?: number
  customer_profile?: CustomerProfileResponse
}

export interface BusinessProfileResponse {
  id: string
  business_name: string
  business_type: string
  location: string
  district?: string
  years_operating?: number
  unique_selling_points?: string
  customer_profile?: CustomerProfileResponse
  created_at: string
}

export interface DemographicsResponse {
  district: string
  income_distribution: Record<string, { percentage: number; description: string }>
  age_distribution: Record<string, { percentage: number }>
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => apiFetch<{ status: string }>('/api/health'),

  analyzeCustomerProfile: (data: BusinessAnalyzeRequest, signal?: AbortSignal) =>
    apiFetch<CustomerProfileResponse>('/api/business/analyze', {
      method: 'POST',
      body: JSON.stringify(data),
      signal,
    }),

  createBusinessProfile: (data: BusinessProfileCreateRequest) =>
    apiFetch<BusinessProfileResponse>('/api/business/profile', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateBusinessProfile: (profileId: string, data: BusinessProfileCreateRequest) =>
    apiFetch<BusinessProfileResponse>(`/api/business/profile/${profileId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getProfileByUser: (userId: string) =>
    apiFetch<BusinessProfileResponse>(`/api/business/profile/user/${userId}`),

  suggestScenarios: (userQuestion: string, businessProfile: object) =>
    apiFetch<{ scenarios: object[] }>('/api/simulation/suggest', {
      method: 'POST',
      body: JSON.stringify({ user_question: userQuestion, business_profile: businessProfile }),
    }),

  startSimulation: (payload: object) =>
    apiFetch<{ simulation_id: string; agents: object[] }>('/api/simulation/start', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getDemographics: (district: string) =>
    apiFetch<DemographicsResponse>(`/api/demographics/${encodeURIComponent(district)}`),
}
