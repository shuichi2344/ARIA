'use client'

import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import type { DemographicsResponse } from '@/lib/api'

export interface SimulationSettingsState {
  incomeConstraints: string[]
  ageConstraints: string[]
  agentCount: number
  targetCustomerConstraints: string[]
  businessSizeConstraints: string[]
  b2bPercentage: number | null  // null for non-hybrid
}

interface SimulationSettingsProps {
  district: string
  disabled: boolean
  onSettingsChange: (settings: SimulationSettingsState) => void
  customerProfile?: Record<string, unknown> | null
}

const ALL_INCOME_LEVELS = ['B40', 'M40', 'T20']
const ALL_AGE_GROUPS = ['20-29', '30-39', '40-49', '50-59', '60+']

export default function SimulationSettings({ district, disabled, onSettingsChange, customerProfile }: SimulationSettingsProps) {
  const [demographics, setDemographics] = useState<DemographicsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  // B2C constraints
  const [incomeConstraints, setIncomeConstraints] = useState<string[]>([...ALL_INCOME_LEVELS])
  const [ageConstraints, setAgeConstraints] = useState<string[]>([...ALL_AGE_GROUPS])
  
  // Target customer constraints (works for both B2C and B2B)
  const [targetCustomerConstraints, setTargetCustomerConstraints] = useState<string[]>([])
  const [businessSizeConstraints, setBusinessSizeConstraints] = useState<string[]>([])
  const [customTargetInput, setCustomTargetInput] = useState('')
  
  // Hybrid
  const [b2bPercentage, setB2bPercentage] = useState(50)
  
  const [agentCount, setAgentCount] = useState(25)
  const [validationMsg, setValidationMsg] = useState<string | null>(null)

  // Derive customer type
  const customerType = (customerProfile?.customer_type as string) || 'B2C'
  const isB2B = customerType === 'B2B'
  const isHybrid = customerType === 'HYBRID'
  
  // Parse B2B options
  const b2bProfile = (customerProfile?.b2b_profile as Record<string, unknown>) || {}
  const availableTargetTypes: string[] = (() => {
    const raw = b2bProfile.target_business_types
    if (Array.isArray(raw)) return raw.map(String).filter(Boolean)
    return []
  })()
  const availableBusinessSizes: string[] = (() => {
    const raw = b2bProfile.business_size
    if (Array.isArray(raw)) return raw.map(String).filter(Boolean)
    return []
  })()

  // Parse B2C target segments
  const b2cProfile = (customerProfile?.b2c_profile as Record<string, unknown>) || {}
  const availableTargetSegments: string[] = (() => {
    const raw = b2cProfile.target_segments
    if (Array.isArray(raw)) return raw.map(String).filter(Boolean)
    return []
  })()

  // Initialize constraints when profile loads
  useEffect(() => {
    if (isB2B || isHybrid) {
      if (availableTargetTypes.length > 0 && targetCustomerConstraints.length === 0) {
        setTargetCustomerConstraints([...availableTargetTypes])
      }
      if (availableBusinessSizes.length > 0 && businessSizeConstraints.length === 0) {
        setBusinessSizeConstraints([...availableBusinessSizes])
      }
    }
    if (!isB2B) {
      // B2C or HYBRID: also init B2C target segments
      if (availableTargetSegments.length > 0 && targetCustomerConstraints.length === 0) {
        setTargetCustomerConstraints([...availableTargetSegments])
      }
    }
  }, [customerType]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleToggle = useCallback((
    setter: React.Dispatch<React.SetStateAction<string[]>>,
    item: string,
    minMsg: string
  ) => {
    setter(prev => {
      if (prev.includes(item)) {
        if (prev.length <= 1) {
          setValidationMsg(minMsg)
          return prev
        }
        setValidationMsg(null)
        return prev.filter(i => i !== item)
      } else {
        setValidationMsg(null)
        return [...prev, item]
      }
    })
  }, [])

  const addCustomTarget = useCallback(() => {
    const val = customTargetInput.trim()
    if (val && !targetCustomerConstraints.includes(val)) {
      setTargetCustomerConstraints(prev => [...prev, val])
      setCustomTargetInput('')
    }
  }, [customTargetInput, targetCustomerConstraints])

  // Fetch demographics (for B2C and HYBRID)
  useEffect(() => {
    if (!district || isB2B) {
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(false)
    api.getDemographics(district)
      .then(data => { if (!cancelled) { setDemographics(data); setLoading(false) } })
      .catch(() => { if (!cancelled) { setError(true); setLoading(false) } })
    return () => { cancelled = true }
  }, [district, isB2B])

  // Notify parent
  useEffect(() => {
    onSettingsChange({
      incomeConstraints,
      ageConstraints,
      agentCount,
      targetCustomerConstraints,
      businessSizeConstraints,
      b2bPercentage: isHybrid ? b2bPercentage : null,
    })
  }, [incomeConstraints, ageConstraints, agentCount, targetCustomerConstraints, businessSizeConstraints, b2bPercentage, isHybrid, onSettingsChange])

  if (loading) {
    return (
      <div style={{ padding: '0.75rem', background: 'var(--gray-50)', borderRadius: 8, border: '1px solid var(--gray-200)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--gray-500)' }}>
          <span style={{ animation: 'pulse-dot 1.2s infinite' }}>⏳</span>
          Loading settings...
        </div>
      </div>
    )
  }

  // ─── Shared: Target Customers Section ───
  const renderTargetCustomers = (label: string, items: string[]) => {
    // Merge original items with any custom-added ones from targetCustomerConstraints
    const allItems = [...new Set([...items, ...targetCustomerConstraints])]
    
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        <p style={{ margin: 0, fontSize: '0.7rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {label}
        </p>
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {allItems.map(item => (
            <label key={item} style={{
              display: 'flex', alignItems: 'center', gap: '0.25rem',
              fontSize: '0.75rem', color: 'var(--gray-700)',
              cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: targetCustomerConstraints.includes(item) ? 1 : 0.5,
              background: targetCustomerConstraints.includes(item) ? 'var(--accent-light, #e0f2fe)' : 'transparent',
              padding: '0.15rem 0.4rem', borderRadius: 4,
              border: '1px solid var(--gray-200)',
            }}>
              <input
                type="checkbox"
                checked={targetCustomerConstraints.includes(item)}
              onChange={() => handleToggle(setTargetCustomerConstraints, item, 'At least one target customer is required')}
              disabled={disabled || (targetCustomerConstraints.includes(item) && targetCustomerConstraints.length <= 1)}
              style={{ margin: 0, width: 12, height: 12 }}
            />
            <span>{item}</span>
          </label>
        ))}
      </div>
      {/* Add custom target */}
      <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.2rem' }}>
        <input
          type="text"
          placeholder="Add custom type..."
          value={customTargetInput}
          onChange={e => setCustomTargetInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCustomTarget() } }}
          disabled={disabled}
          style={{
            flex: 1, padding: '0.25rem 0.4rem', fontSize: '0.72rem',
            borderRadius: 4, border: '1px solid var(--gray-300)',
            background: disabled ? 'var(--gray-100)' : 'white',
          }}
        />
        <button
          onClick={addCustomTarget}
          disabled={disabled || !customTargetInput.trim()}
          style={{
            padding: '0.25rem 0.5rem', fontSize: '0.7rem', fontWeight: 600,
            borderRadius: 4, border: '1px solid var(--gray-300)',
            background: 'var(--gray-100)', cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        >+</button>
      </div>
    </div>
    )
  }

  // ─── Shared: Agent Count ───
  const renderAgentCount = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
      <p style={{ margin: 0, fontSize: '0.7rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Agent Count
      </p>
      <input
        type="number" min={15} max={100} value={agentCount} disabled={disabled}
        onChange={e => { const v = parseInt(e.target.value, 10); if (!isNaN(v)) setAgentCount(v) }}
        onBlur={() => setAgentCount(prev => Math.min(100, Math.max(15, prev)))}
        style={{ width: '5rem', padding: '0.3rem 0.5rem', fontSize: '0.78rem', borderRadius: 4, border: '1px solid var(--gray-300)', background: disabled ? 'var(--gray-100)' : 'white' }}
      />
    </div>
  )

  // ─── B2B-only Settings ───
  if (isB2B) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', padding: '0.75rem', background: 'var(--gray-50)', borderRadius: 8, border: '1px solid var(--gray-200)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', fontWeight: 700, color: 'var(--gray-700)' }}>
          <span>🏢</span><span>B2B Customer Settings</span>
        </div>
        {availableTargetTypes.length > 0 && renderTargetCustomers('Target Business Types', availableTargetTypes)}
        {availableBusinessSizes.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <p style={{ margin: 0, fontSize: '0.7rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Business Sizes</p>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {availableBusinessSizes.map(size => (
                <label key={size} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.78rem', cursor: disabled ? 'not-allowed' : 'pointer', opacity: businessSizeConstraints.includes(size) ? 1 : 0.5 }}>
                  <input type="checkbox" checked={businessSizeConstraints.includes(size)} onChange={() => handleToggle(setBusinessSizeConstraints, size, 'At least one size is required')} disabled={disabled || (businessSizeConstraints.includes(size) && businessSizeConstraints.length <= 1)} style={{ margin: 0 }} />
                  <span style={{ fontWeight: 500 }}>{size}</span>
                </label>
              ))}
            </div>
          </div>
        )}
        {validationMsg && <p style={{ margin: 0, fontSize: '0.7rem', color: '#ef4444', fontStyle: 'italic' }} role="alert">{validationMsg}</p>}
        {renderAgentCount()}
      </div>
    )
  }

  // ─── HYBRID Settings ───
  if (isHybrid) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', padding: '0.75rem', background: 'var(--gray-50)', borderRadius: 8, border: '1px solid var(--gray-200)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', fontWeight: 700, color: 'var(--gray-700)' }}>
          <span>🔀</span><span>Hybrid Business Settings</span>
        </div>

        {/* B2B/B2C Split Slider */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
          <p style={{ margin: 0, fontSize: '0.7rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Customer Mix
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--gray-600)', minWidth: '2.5rem' }}>B2B {b2bPercentage}%</span>
            <input
              type="range" min={10} max={90} value={b2bPercentage}
              onChange={e => setB2bPercentage(parseInt(e.target.value, 10))}
              disabled={disabled}
              style={{ flex: 1, cursor: disabled ? 'not-allowed' : 'pointer' }}
            />
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--gray-600)', minWidth: '2.5rem', textAlign: 'right' }}>B2C {100 - b2bPercentage}%</span>
          </div>
        </div>

        {/* B2B Section */}
        <div style={{ padding: '0.5rem', background: 'white', borderRadius: 6, border: '1px solid var(--gray-200)' }}>
          <p style={{ margin: '0 0 0.3rem', fontSize: '0.7rem', fontWeight: 700, color: 'var(--gray-600)' }}>🏢 B2B Customers</p>
          {availableTargetTypes.length > 0 && renderTargetCustomers('Business Types', availableTargetTypes)}
          {availableBusinessSizes.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginTop: '0.3rem' }}>
              <p style={{ margin: 0, fontSize: '0.7rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Sizes</p>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {availableBusinessSizes.map(size => (
                  <label key={size} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', cursor: disabled ? 'not-allowed' : 'pointer', opacity: businessSizeConstraints.includes(size) ? 1 : 0.5 }}>
                    <input type="checkbox" checked={businessSizeConstraints.includes(size)} onChange={() => handleToggle(setBusinessSizeConstraints, size, 'At least one size is required')} disabled={disabled || (businessSizeConstraints.includes(size) && businessSizeConstraints.length <= 1)} style={{ margin: 0, width: 12, height: 12 }} />
                    <span>{size}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* B2C Section */}
        <div style={{ padding: '0.5rem', background: 'white', borderRadius: 6, border: '1px solid var(--gray-200)' }}>
          <p style={{ margin: '0 0 0.3rem', fontSize: '0.7rem', fontWeight: 700, color: 'var(--gray-600)' }}>👤 B2C Customers</p>
          {availableTargetSegments.length > 0 && renderTargetCustomers('Target Segments', availableTargetSegments)}
          {demographics && (
            <>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginTop: '0.3rem' }}>
                <p style={{ margin: 0, fontSize: '0.7rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Income</p>
                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                  {Object.entries(demographics.income_distribution).map(([level, info]) => (
                    <label key={level} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', cursor: disabled ? 'not-allowed' : 'pointer', opacity: incomeConstraints.includes(level) ? 1 : 0.5 }}>
                      <input type="checkbox" checked={incomeConstraints.includes(level)} onChange={() => handleToggle(setIncomeConstraints, level, 'At least one income level is required')} disabled={disabled} style={{ margin: 0, width: 12, height: 12 }} />
                      <span style={{ fontWeight: 600 }}>{level}</span>
                      <span style={{ color: 'var(--gray-400)', fontSize: '0.68rem' }}>{info.percentage.toFixed(0)}%</span>
                    </label>
                  ))}
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginTop: '0.3rem' }}>
                <p style={{ margin: 0, fontSize: '0.7rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Age</p>
                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                  {Object.entries(demographics.age_distribution).map(([group, info]) => (
                    <label key={group} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', cursor: disabled ? 'not-allowed' : 'pointer', opacity: ageConstraints.includes(group) ? 1 : 0.5 }}>
                      <input type="checkbox" checked={ageConstraints.includes(group)} onChange={() => handleToggle(setAgeConstraints, group, 'At least one age group is required')} disabled={disabled} style={{ margin: 0, width: 12, height: 12 }} />
                      <span style={{ fontWeight: 600 }}>{group}</span>
                      <span style={{ color: 'var(--gray-400)', fontSize: '0.68rem' }}>{info.percentage.toFixed(0)}%</span>
                    </label>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {validationMsg && <p style={{ margin: 0, fontSize: '0.7rem', color: '#ef4444', fontStyle: 'italic' }} role="alert">{validationMsg}</p>}
        {renderAgentCount()}
      </div>
    )
  }

  // ─── B2C Settings ───
  if (error || !demographics) {
    return (
      <div style={{ padding: '0.75rem', background: 'var(--gray-50)', borderRadius: 8, border: '1px solid var(--gray-200)' }}>
        <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--gray-500)' }}>Demographics unavailable</p>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', padding: '0.75rem', background: 'var(--gray-50)', borderRadius: 8, border: '1px solid var(--gray-200)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', fontWeight: 700, color: 'var(--gray-700)' }}>
        <span>📊</span><span>{district} Demographics</span>
      </div>

      {/* Target Customers for B2C */}
      {availableTargetSegments.length > 0 && renderTargetCustomers('Target Customers', availableTargetSegments)}

      {/* Income */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        <p style={{ margin: 0, fontSize: '0.7rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Income Levels</p>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {Object.entries(demographics.income_distribution).map(([level, info]) => (
            <label key={level} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.78rem', cursor: disabled ? 'not-allowed' : 'pointer', opacity: incomeConstraints.includes(level) ? 1 : 0.5 }}>
              <input type="checkbox" checked={incomeConstraints.includes(level)} onChange={() => handleToggle(setIncomeConstraints, level, 'At least one income level is required')} disabled={disabled} style={{ margin: 0 }} />
              <span style={{ fontWeight: 600 }}>{level}</span>
              <span style={{ color: 'var(--gray-500)' }}>{info.percentage.toFixed(1)}%</span>
            </label>
          ))}
        </div>
      </div>

      {/* Age */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        <p style={{ margin: 0, fontSize: '0.7rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Age Groups</p>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {Object.entries(demographics.age_distribution).map(([group, info]) => (
            <label key={group} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.78rem', cursor: disabled ? 'not-allowed' : 'pointer', opacity: ageConstraints.includes(group) ? 1 : 0.5 }}>
              <input type="checkbox" checked={ageConstraints.includes(group)} onChange={() => handleToggle(setAgeConstraints, group, 'At least one age group is required')} disabled={disabled} style={{ margin: 0 }} />
              <span style={{ fontWeight: 600 }}>{group}</span>
              <span style={{ color: 'var(--gray-500)' }}>{info.percentage.toFixed(1)}%</span>
            </label>
          ))}
        </div>
      </div>

      {validationMsg && <p style={{ margin: 0, fontSize: '0.7rem', color: '#ef4444', fontStyle: 'italic' }} role="alert">{validationMsg}</p>}
      {renderAgentCount()}
    </div>
  )
}
