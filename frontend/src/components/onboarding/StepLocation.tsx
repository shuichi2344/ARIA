'use client'

import { useState } from 'react'
import { DISTRICTS } from '@/lib/districts'
import type { BusinessFormData } from './OnboardingFlow'
import FormCard from './FormCard'
import * as S from './styles'

interface Props {
  data: BusinessFormData
  update: (p: Partial<BusinessFormData>) => void
  onNext: () => void
  onBack: () => void
}

export default function StepLocation({ data, update, onNext, onBack }: Props) {
  const [errors,       setErrors]       = useState<Record<string, string>>({})
  const [distFocus,    setDistFocus]    = useState(false)
  const [cityFocus,    setCityFocus]    = useState(false)
  const areas = data.district ? DISTRICTS[data.district]?.areas ?? [] : []

  const focusStyle = {
    borderColor: 'var(--accent)',
    background: 'white',
    boxShadow: '0 0 0 4px color-mix(in srgb, var(--accent) 10%, transparent)',
  }

  function validate() {
    const e: Record<string, string> = {}
    if (!data.district) e.district = 'Please select a district'
    if (!data.city)     e.city     = 'Please select an area'
    setErrors(e); return !Object.keys(e).length
  }

  return (
    <FormCard title="📍 Where is Your Business Located in Penang?">

      {/* Info box */}
      <div style={{
        display: 'flex', gap: '1rem', alignItems: 'flex-start',
        background: '#eff6ff', borderLeft: '4px solid var(--accent)',
        borderRadius: 12, padding: '1rem 1.25rem', marginBottom: '1.5rem',
      }}>
        <svg style={{ width: 20, height: 20, flexShrink: 0, color: 'var(--accent)', marginTop: 2 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/>
        </svg>
        <div>
          <strong style={{ display: 'block', marginBottom: '0.25rem', color: 'var(--gray-900)' }}>Location: Penang, Malaysia</strong>
          <p style={{ margin: 0, color: 'var(--gray-700)', fontSize: '0.9375rem', lineHeight: 1.6 }}>ARIA currently focuses on Penang businesses. Select your district below.</p>
        </div>
      </div>

      {/* District */}
      <div style={S.formGroup}>
        <label style={S.label}>District <span style={{ color: '#dc2626' }}>*</span></label>
        <select
          value={data.district}
          onChange={e => { update({ district: e.target.value, city: '' }); setErrors(p => ({ ...p, district: '' })) }}
          style={{ ...( errors.district ? S.inputError : S.input), ...(distFocus ? focusStyle : {}) }}
          onFocus={() => setDistFocus(true)} onBlur={() => setDistFocus(false)}
        >
          <option value="">Select your district…</option>
          {Object.entries(DISTRICTS).map(([key, val]) => (
            <option key={key} value={key}>{val.label}</option>
          ))}
        </select>
        {errors.district
          ? <span style={S.errorText}>{errors.district}</span>
          : <span style={S.helpText}>Choose the district where your business operates</span>}
      </div>

      {/* Area */}
      <div style={{ ...S.formGroup, marginBottom: '1.5rem' }}>
        <label style={S.label}>Area / Town <span style={{ color: '#dc2626' }}>*</span></label>
        <select
          value={data.city} disabled={!data.district}
          onChange={e => { update({ city: e.target.value }); setErrors(p => ({ ...p, city: '' })) }}
          style={{ ...( errors.city ? S.inputError : S.input), ...(cityFocus ? focusStyle : {}), opacity: !data.district ? 0.5 : 1, cursor: !data.district ? 'not-allowed' : 'pointer' }}
          onFocus={() => setCityFocus(true)} onBlur={() => setCityFocus(false)}
        >
          <option value="">{data.district ? 'Select area…' : 'Select district first…'}</option>
          {areas.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        {errors.city
          ? <span style={S.errorText}>{errors.city}</span>
          : <span style={S.helpText}>Choose the specific area within your district</span>}
      </div>

      <div style={S.formActions}>
        <HoverBtn style={S.btnSecondary} onClick={onBack}>← Back</HoverBtn>
        <HoverBtn style={S.btnPrimary}   onClick={() => { if (validate()) onNext() }}>Next →</HoverBtn>
      </div>
    </FormCard>
  )
}

function HoverBtn({ style, onClick, children }: { style: React.CSSProperties; onClick?: () => void; children: React.ReactNode }) {
  const [hov, setHov] = useState(false)
  return (
    <button onClick={onClick} onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{ ...style, background: hov ? (style.background === 'white' ? 'var(--gray-50)' : 'var(--accent)') : style.background,
               borderColor: hov && style.background === 'white' ? 'var(--gray-900)' : style.borderColor }}>
      {children}
    </button>
  )
}
