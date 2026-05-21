'use client'

import { useState, useEffect, useRef } from 'react'
import type { BusinessFormData } from './OnboardingFlow'
import FormCard from './FormCard'
import * as S from './styles'

interface Props {
  data: BusinessFormData
  update: (p: Partial<BusinessFormData>) => void
  onNext: () => void
}

interface Category { 'Category Name': string; GCID: string }

const POPULAR = [
  'Restaurant','Cafe','Coffee shop','Bakery','Convenience store',
  'Clothing store','Beauty salon','Car repair','Accounting firm',
  'Tuition centre','Retail store','Barber shop',
]

function searchCats(cats: Category[], q: string, max = 10) {
  if (!q.trim()) return []
  const ql = q.toLowerCase().trim()
  const r: { name: string; id: string; score: number }[] = []
  for (const c of cats) {
    const n = c['Category Name'], l = n.toLowerCase()
    if (ql === l)          { r.push({ name: n, id: c.GCID, score: 1 });    continue }
    if (l.startsWith(ql))  { r.push({ name: n, id: c.GCID, score: 0.95 }); continue }
    if (l.includes(ql))    { r.push({ name: n, id: c.GCID, score: 0.85 }); continue }
    const ws = ql.split(' ')
    if (ws.every(w => l.includes(w))) { r.push({ name: n, id: c.GCID, score: 0.8 }); continue }
    const m = ws.filter(w => l.includes(w))
    if (m.length) r.push({ name: n, id: c.GCID, score: (m.length / ws.length) * 0.7 })
  }
  return r.sort((a, b) => b.score - a.score).slice(0, max)
}

export default function StepBusinessInfo({ data, update, onNext }: Props) {
  const [cats,         setCats]         = useState<Category[]>([])
  const [query,        setQuery]        = useState('')
  const [results,      setResults]      = useState<{ name: string; id: string }[]>([])
  const [showDrop,     setShowDrop]     = useState(false)
  const [errors,       setErrors]       = useState<Record<string, string>>({})
  const [nameFocus,    setNameFocus]    = useState(false)
  const [queryFocus,   setQueryFocus]   = useState(false)
  const [yearsFocus,   setYearsFocus]   = useState(false)
  const [uspFocus,     setUspFocus]     = useState(false)
  const dropRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch('/business_categories_clean.json').then(r => r.json()).then(d => setCats(d.categories ?? [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (query.length >= 2) { setResults(searchCats(cats, query)); setShowDrop(true) }
    else if (query.length === 0) { setResults([]); setShowDrop(true) }
    else setShowDrop(false)
  }, [query, cats])

  useEffect(() => {
    const h = (e: MouseEvent) => { if (dropRef.current && !dropRef.current.contains(e.target as Node)) setShowDrop(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  function selectType(name: string, id: string) {
    update({ businessType: name, businessCategoryId: id })
    setQuery(''); setShowDrop(false); setErrors(p => ({ ...p, businessType: '' }))
  }

  function validate() {
    const e: Record<string, string> = {}
    if (!data.businessName.trim()) e.businessName = 'Business name is required'
    if (!data.businessType)        e.businessType  = 'Please select a business type'
    setErrors(e)
    return !Object.keys(e).length
  }

  const focusStyle = {
    borderColor: 'var(--accent)',
    background: 'white',
    boxShadow: '0 0 0 4px color-mix(in srgb, var(--accent) 10%, transparent)',
    transform: 'translateY(-1px)',
  }

  return (
    <FormCard title="📋 Tell Us About Your Business">

      {/* Business Name */}
      <div style={S.formGroup}>
        <label style={S.label}>Business Name <span style={{ color: '#dc2626' }}>*</span></label>
        <input
          type="text" value={data.businessName}
          onChange={e => { update({ businessName: e.target.value }); setErrors(p => ({ ...p, businessName: '' })) }}
          placeholder="e.g., Nasi Kandar Pelita, Kopitiam Uncle Lee"
          style={{ ...( errors.businessName ? S.inputError : S.input), ...(nameFocus ? focusStyle : {}) }}
          onFocus={() => setNameFocus(true)} onBlur={() => setNameFocus(false)}
        />
        {errors.businessName
          ? <span style={S.errorText}>{errors.businessName}</span>
          : <span style={S.helpText}>The name of your business</span>}
      </div>

      {/* Business Type */}
      <div style={S.formGroup} ref={dropRef}>
        <label style={S.label}>Business Type <span style={{ color: '#dc2626' }}>*</span></label>

        {data.businessType ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '0.75rem 1rem',
            background: 'var(--accent)', color: 'white',
            borderRadius: 8, marginTop: '0.25rem',
          }}>
            <span style={{ fontWeight: 600 }}>{data.businessType}</span>
            <button
              type="button" onClick={() => { update({ businessType: '', businessCategoryId: '' }); setQuery('') }}
              style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer', padding: '0.25rem', borderRadius: 4, fontSize: '1rem', lineHeight: 1 }}
            >✕</button>
          </div>
        ) : (
          <>
            <input
              type="text" value={query}
              onChange={e => setQuery(e.target.value)}
              onFocus={() => { setQueryFocus(true); setShowDrop(true) }}
              onBlur={() => setQueryFocus(false)}
              placeholder="Type to search (e.g., 'coffee shop', 'car repair')…"
              autoComplete="off"
              style={{
                ...(errors.businessType ? S.inputError : S.input),
                ...(queryFocus ? focusStyle : {}),
                borderRadius: showDrop ? '10px 10px 0 0' : 10,
              }}
            />
            {showDrop && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0,
                background: 'white', border: '2px solid var(--gray-300)',
                borderTop: 'none', borderRadius: '0 0 12px 12px',
                maxHeight: 320, overflowY: 'auto', zIndex: 1000,
                boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
              }}>
                {(results.length > 0 ? results : POPULAR.map(n => ({ name: n, id: n.toLowerCase().replace(/\s+/g,'_') }))).map(r => (
                  <div
                    key={r.id}
                    onMouseDown={() => selectType(r.name, r.id)}
                    style={{
                      padding: '0.875rem 1.125rem', cursor: 'pointer',
                      borderBottom: '1px solid var(--gray-100)',
                      fontSize: '0.9375rem', color: 'var(--gray-900)',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--gray-50)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'white')}
                  >
                    {r.name}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
        {errors.businessType
          ? <span style={S.errorText}>{errors.businessType}</span>
          : <span style={S.helpText}>Start typing to search from 1000+ business categories</span>}
      </div>

      {/* Years Operating */}
      <div style={S.formGroup}>
        <label style={S.label}>Years in Operation</label>
        <input
          type="number" min={0} max={100} value={data.yearsOperating}
          onChange={e => update({ yearsOperating: e.target.value })}
          placeholder="0"
          style={{ ...S.input, ...(yearsFocus ? focusStyle : {}) }}
          onFocus={() => setYearsFocus(true)} onBlur={() => setYearsFocus(false)}
        />
        <span style={S.helpText}>How long has your business been operating?</span>
      </div>

      {/* USP */}
      <div style={{ ...S.formGroup, marginBottom: '1.5rem' }}>
        <label style={S.label}>What makes your business unique?</label>
        <textarea
          rows={3} value={data.uniqueSellingPoints}
          onChange={e => update({ uniqueSellingPoints: e.target.value })}
          placeholder="e.g., 'Authentic family recipes', 'Wholesale prices for workshops', 'Fast service'"
          style={{ ...S.input, resize: 'none', ...(uspFocus ? focusStyle : {}) }}
          onFocus={() => setUspFocus(true)} onBlur={() => setUspFocus(false)}
        />
        <span style={S.helpText}>Your unique selling points help our AI understand your business better</span>
      </div>

      <div style={S.formActions}>
        <HoverBtn style={S.btnPrimary} onClick={() => { if (validate()) onNext() }}>Next →</HoverBtn>
      </div>
    </FormCard>
  )
}

function HoverBtn({ style, onClick, children, disabled }: { style: React.CSSProperties; onClick?: () => void; children: React.ReactNode; disabled?: boolean }) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick} disabled={disabled}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{ ...style, background: hov ? 'var(--accent)' : style.background, opacity: disabled ? 0.6 : 1 }}
    >{children}</button>
  )
}
