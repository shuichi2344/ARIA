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
  'Tutoring service','Retail store','Barber shop',
]

// Malaysian-specific aliases for common business types
const MALAYSIAN_ALIASES: Record<string, string> = {
  'tuition centre': 'tutoring service',
  'tuition center': 'tutoring service',
  'tuition': 'tutoring service',
  'tuisyen': 'tutoring service',
  'kopitiam': 'coffee shop',
  'mamak': 'restaurant',
  'kedai runcit': 'convenience store',
  'sundry shop': 'convenience store',
  'mini market': 'convenience store',
  'laundry': 'laundromat',
  'dobi': 'laundromat',
  'workshop': 'car repair',
  'bengkel': 'car repair',
  'salon kecantikan': 'beauty salon',
}

function searchCats(cats: Category[], q: string, max = 10) {
  if (!q.trim()) return []
  let ql = q.toLowerCase().trim()
  
  // Check if query matches a Malaysian alias (exact or partial)
  let aliasMatched = false
  for (const [key, value] of Object.entries(MALAYSIAN_ALIASES)) {
    if (key.includes(ql) || ql.includes(key)) {
      ql = value
      aliasMatched = true
      break
    }
  }
  
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
  
  // If alias matched but no results, show a helpful suggestion
  if (aliasMatched && r.length === 0) {
    // This shouldn't happen, but just in case
    console.log(`Alias matched for "${q}" -> "${ql}" but no results found`)
  }
  
  // Sort by score first (best matches on top), then alphabetically within same score
  return r.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score
    return a.name.localeCompare(b.name)
  }).slice(0, max)
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
  const debounceTimer = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    fetch('/business_categories_clean.json').then(r => r.json()).then(d => setCats(d.categories ?? [])).catch(() => {})
  }, [])

  // Debounced search - search as user types (from first character)
  useEffect(() => {
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current)
    }
    
    if (query.length >= 1) {
      // Show results immediately for first character, then debounce subsequent typing
      if (query.length === 1) {
        setResults(searchCats(cats, query, 20)) // Show more results for single letter
        setShowDrop(true)
      } else {
        debounceTimer.current = setTimeout(() => {
          setResults(searchCats(cats, query))
          setShowDrop(true)
        }, 150) // Shorter delay (150ms) for faster feel
      }
    } else {
      setResults([])
      setShowDrop(true)
    }
    
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current)
      }
    }
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
    if (!data.uniqueSellingPoints.trim()) e.uniqueSellingPoints = 'Please describe what makes your business unique'
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
        <label style={S.label}>What makes your business unique? <span style={{ color: '#dc2626' }}>*</span></label>
        <textarea
          rows={4} value={data.uniqueSellingPoints} required maxLength={2000}
          aria-invalid={Boolean(errors.uniqueSellingPoints)}
          onChange={e => {
            update({ uniqueSellingPoints: e.target.value })
            setErrors(p => ({ ...p, uniqueSellingPoints: '' }))
          }}
          placeholder="Tell us what customers can get from your business that they may not find elsewhere. For example: signature products, ingredients or sourcing, pricing, customisation, expertise, service speed, or a guarantee."
          style={{ ...(errors.uniqueSellingPoints ? S.inputError : S.input), resize: 'vertical', ...(uspFocus ? focusStyle : {}) }}
          onFocus={() => setUspFocus(true)} onBlur={() => setUspFocus(false)}
        />
        {errors.uniqueSellingPoints
          ? <span style={S.errorText}>{errors.uniqueSellingPoints}</span>
          : <span style={S.helpText}>Add as much detail as you can—specific products, ingredients, prices, service, expertise, or customer benefits help ARIA create a more accurate profile and simulation. Avoid broad claims like “great quality” unless you explain what makes it great.</span>}
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
