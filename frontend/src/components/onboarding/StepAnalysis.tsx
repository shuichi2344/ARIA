'use client'

import { useEffect, useState } from 'react'
import { api, type CustomerProfileResponse } from '@/lib/api'
import type { BusinessFormData } from './OnboardingFlow'
import FormCard from './FormCard'
import * as S from './styles'

interface Props {
  data: BusinessFormData
  update: (p: Partial<BusinessFormData>) => void
  onNext: () => void
  onBack: () => void
}

// ── Types for the editable draft ──────────────────────────────────────────────

interface EditDraft {
  customer_type: string
  target_customers: string
  price_min: string
  price_max: string
  // B2C
  b2c_avg_transaction: string
  // B2B
  target_businesses: string
  business_size: string[]
  b2b_frequency: string
  b2b_avg_transaction: string
  b2b_decision_factors: string[]
}

const ALL_BIZ_SIZES     = ['Micro','Small','Medium']
const FREQUENCIES       = ['daily','2-3 times/week','weekly','bi-weekly','monthly','quarterly','yearly','one-time']
const DECISION_FACTORS  = ['price','quality','reliability','delivery_speed','product_range','relationship','convenience']

function profileToDraft(p: CustomerProfileResponse): EditDraft {
  // Normalize customer_type: LLM may return "Both" but UI expects "HYBRID"
  let customerType = p.customer_type
  if (customerType?.toLowerCase() === 'both' || customerType?.toLowerCase() === 'mixed') {
    customerType = 'HYBRID'
  }
  
  return {
    customer_type:        customerType,
    target_customers:     p.target_customers,
    price_min:            String(p.price_range?.min ?? ''),
    price_max:            String(p.price_range?.max ?? ''),
    b2c_avg_transaction:  String(p.b2c_profile?.avg_transaction_rm ?? ''),
    target_businesses:    p.b2b_profile?.target_business_types?.join(', ') ?? '',
    business_size:        p.b2b_profile?.business_size         ?? [],
    b2b_frequency:        p.b2b_profile?.purchase_frequency    ?? 'monthly',
    b2b_avg_transaction:  String(p.b2b_profile?.avg_transaction_rm ?? '500'),
    b2b_decision_factors: (p.b2b_profile as any)?.decision_factors ?? ['price', 'quality', 'reliability'],
  }
}

function draftToProfile(d: EditDraft, original: CustomerProfileResponse): CustomerProfileResponse {
  const type = d.customer_type as 'B2C' | 'B2B' | 'HYBRID'
  return {
    ...original,
    customer_type:        type,
    target_customers:     d.target_customers,
    price_range: d.price_min && d.price_max
      ? { min: parseFloat(d.price_min), max: parseFloat(d.price_max) }
      : original.price_range,
    b2c_profile: (type === 'B2C' || type === 'HYBRID') ? {
      target_segments:       d.target_customers.split(',').map(s => s.trim()).filter(Boolean),
      typical_income_levels: ['B40', 'M40', 'T20'],
      avg_transaction_rm:    parseFloat(d.b2c_avg_transaction) || 0,
    } : undefined,
    b2b_profile: (type === 'B2B' || type === 'HYBRID') ? {
      target_business_types: d.target_businesses.split(',').map(s => s.trim()).filter(Boolean),
      business_size:         d.business_size,
      purchase_frequency:    d.b2b_frequency,
      avg_transaction_rm:    parseFloat(d.b2b_avg_transaction) || 500,
      price_sensitivity:     'medium',
      decision_factors:      d.b2b_decision_factors,
    } : undefined,
    reasoning: 'Profile adjusted by user based on AI analysis.',
  }
}

// ── Mock fallback ─────────────────────────────────────────────────────────────

function mockProfile(businessType: string): CustomerProfileResponse {
  const l = businessType.toLowerCase()
  const isB2B = ['wholesale','supplier','distributor'].some(t => l.includes(t))
  const mn = l.includes('restaurant')||l.includes('cafe') ? 8
    : l.includes('coffee')||l.includes('bakery') ? 3
    : l.includes('salon')||l.includes('barber') ? 15
    : l.includes('repair') ? 50
    : l.includes('accounting')||l.includes('law') ? 200 : 10
  const mx = mn * 4
  if (isB2B) return {
    customer_type:'B2B',
    target_customers:'Retail Shops, Small Enterprises',
    price_range:{min:100,max:1000},
    b2b_profile:{target_business_types:['Retail Shops','Small Enterprises'],business_size:['Micro','Small'],purchase_frequency:'weekly',avg_transaction_rm:300,price_sensitivity:'medium'},
    b2c_profile:undefined,
    reasoning:'Based on business type and typical customer patterns for wholesale/supplier businesses.',
  }
  return {
    customer_type:'B2C',
    target_customers:'working professionals, students, families',
    price_range:{min:mn,max:mx},
    b2c_profile:{target_segments:['working professionals','students','families'],typical_income_levels:['B40','M40'],avg_transaction_rm:Math.round((mn+mx)/2)},
    b2b_profile:undefined,
    reasoning:'Based on business type and location demographics for consumer-facing businesses.',
  }
}

const LOAD_LABELS = [
  'Analyzing business type',
  'Considering location demographics',
  'Identifying customer patterns',
  'Generating profile',
]

// ── Main component ────────────────────────────────────────────────────────────

export default function StepAnalysis({ data, update, onNext, onBack }: Props) {
  const [loadStep,  setLoadStep]  = useState(0)
  const [profile,   setProfile]   = useState<CustomerProfileResponse | null>(data.customerProfile)
  const [offline,   setOffline]   = useState(false)
  const [editMode,  setEditMode]  = useState(false)
  const [draft,     setDraft]     = useState<EditDraft | null>(null)

  // Run analysis only on first mount when no profile exists yet
  useEffect(() => {
    if (profile) return
    const abortController = new AbortController()
    let cancelled = false
    async function run() {
      for (let i = 1; i <= 4; i++) {
        await new Promise(r => setTimeout(r, 700))
        if (cancelled) return
        setLoadStep(i)
      }
      try {
        const r = await api.analyzeCustomerProfile({
          business_name:        data.businessName,
          business_type:        data.businessType,
          business_category_id: data.businessCategoryId,
          location:             `${data.city}, ${data.state}`,
          district:             data.district,
          years_operating:      data.yearsOperating ? parseInt(data.yearsOperating) : undefined,
          unique_selling_points: data.uniqueSellingPoints,
        }, abortController.signal)
        // Normalize customer_type from LLM ("Both" → "HYBRID")
        if (r.customer_type?.toLowerCase() === 'both' || r.customer_type?.toLowerCase() === 'mixed') {
          r.customer_type = 'HYBRID'
        }
        if (!cancelled) { setProfile(r); update({ customerProfile: r }) }
      } catch (e) {
        if (cancelled || (e instanceof DOMException && e.name === 'AbortError')) return
        const m = mockProfile(data.businessType)
        setProfile(m); update({ customerProfile: m }); setOffline(true)
      }
    }
    run()
    return () => { cancelled = true; abortController.abort() }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Enter edit mode — populate draft from current profile, don't re-run AI
  function startEdit() {
    if (!profile) return
    setDraft(profileToDraft(profile))
    setEditMode(true)
  }

  // Save edits back to profile state
  function saveEdit() {
    if (!draft || !profile) return
    const updated = draftToProfile(draft, profile)
    setProfile(updated)
    update({ customerProfile: updated })
    setEditMode(false)
    setDraft(null)
  }

  function cancelEdit() {
    setEditMode(false)
    setDraft(null)
  }

  function patchDraft(partial: Partial<EditDraft>) {
    setDraft(prev => prev ? { ...prev, ...partial } : prev)
  }

  function toggleArr(arr: string[], val: string): string[] {
    return arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]
  }

  const showB2C = draft ? (draft.customer_type === 'B2C' || draft.customer_type === 'HYBRID') : false
  const showB2B = draft ? (draft.customer_type === 'B2B' || draft.customer_type === 'HYBRID') : false

  return (
    <FormCard title="🤖 Understanding Your Customers">

      {/* Info box */}
      <div style={{ display:'flex', gap:'1rem', alignItems:'flex-start', background:'#eff6ff', borderLeft:'4px solid var(--accent)', borderRadius:12, padding:'1rem 1.25rem', marginBottom:'1.5rem' }}>
        <svg style={{ width:20, height:20, flexShrink:0, marginTop:2 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <div>
          <strong style={{ display:'block', marginBottom:'0.25rem' }}>AI-Powered Customer Analysis</strong>
          <p style={{ margin:0, color:'var(--gray-700)', fontSize:'0.9375rem', lineHeight:1.6 }}>
            Our AI will analyze your business information to identify your typical customers — whether they're individual consumers (B2C) or other businesses (B2B).
          </p>
        </div>
      </div>

      {/* ── Loading ── */}
      {!profile && (
        <div style={{ textAlign:'center', padding:'3rem 2rem' }}>
          <div style={{ width:60, height:60, borderWidth:4, borderStyle:'solid', borderColor:'var(--gray-200)', borderTopColor:'var(--accent)', borderRadius:'50%', animation:'spin 1s linear infinite', margin:'0 auto 2rem' }} />
          <h3 style={{ fontSize:'1.5rem', color:'var(--gray-900)', marginBottom:'0.5rem' }}>Analyzing your business...</h3>
          <p style={{ color:'var(--gray-600)', maxWidth:500, margin:'0 auto 2rem' }}>
            Our AI is understanding your business type, location, and unique characteristics.
          </p>
          <div style={{ display:'flex', flexDirection:'column', gap:'1rem', maxWidth:400, margin:'0 auto', textAlign:'left' }}>
            {LOAD_LABELS.map((label, i) => (
              <div key={i} style={{
                display:'flex', alignItems:'center', gap:'0.75rem',
                padding:'0.75rem 1rem',
                background: loadStep === i+1 ? 'var(--accent-light)' : 'var(--gray-50)',
                borderRadius:8, opacity: loadStep < i+1 ? 0.4 : 1,
                transition:'all 0.3s ease',
              }}>
                <span style={{ fontSize:'0.9rem', color:'var(--gray-900)' }}>{label}</span>
                {loadStep > i+1 && <span style={{ marginLeft:'auto', color:'#10b981' }}>✓</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Results (read mode) ── */}
      {profile && !editMode && (
        <>
          {offline && (
            <div style={{ display:'flex', gap:'0.75rem', alignItems:'center', background:'#fffbeb', borderWidth:1, borderStyle:'solid', borderColor:'#fde68a', borderRadius:10, padding:'0.75rem 1rem', marginBottom:'1rem', fontSize:'0.875rem', color:'#92400e' }}>
              ⚠️ Using offline analysis. Start the API server for AI-powered results.
            </div>
          )}

          <div style={{ background:'white', borderWidth:2, borderStyle:'solid', borderColor:'var(--gray-200)', borderRadius:16, padding:'1.5rem', marginBottom:'1rem' }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'1.5rem', paddingBottom:'1rem', borderBottom:'2px solid var(--gray-200)' }}>
              <h3 style={{ fontSize:'1.5rem', fontWeight:700, margin:0 }}>Customer Profile</h3>
            </div>

            <ProfileRow label="Customer Type"><strong style={{ color:'var(--accent)' }}>{profile.customer_type}</strong></ProfileRow>
            <ProfileRow label="Primary Customers"><span>{profile.target_customers}</span></ProfileRow>

            {profile.price_range && (
              <ProfileRow label="Price Range (Products/Services)">
                <span style={{ display:'flex', alignItems:'center', gap:'0.5rem', background:'var(--gray-50)', padding:'0.5rem 0.75rem', borderRadius:8, borderWidth:1, borderStyle:'solid', borderColor:'var(--gray-200)' }}>
                  <span style={{ fontSize:'0.875rem', color:'var(--gray-600)' }}>Min:</span>
                  <strong>RM {profile.price_range.min}</strong>
                  <span style={{ fontSize:'0.875rem', color:'var(--gray-600)' }}>Max:</span>
                  <strong>RM {profile.price_range.max}</strong>
                </span>
              </ProfileRow>
            )}

            {profile.b2c_profile && (
              <ProfileRow label={profile.customer_type === 'HYBRID' ? "Consumer Profile (B2C)" : "Consumer Profile (B2C)"}>
                <div style={{ display:'grid', gap:'0.5rem' }}>
                  <Detail label={profile.customer_type === 'HYBRID' ? "Avg Transaction/Customer" : "Avg Transaction"} value={`RM ${profile.b2c_profile.avg_transaction_rm || '—'}`} />
                </div>
              </ProfileRow>
            )}

            {profile.b2b_profile && (
              <ProfileRow label="Business Profile (B2B)">
                <div style={{ display:'grid', gap:'0.5rem' }}>
                  {profile.customer_type !== 'HYBRID' && (
                    <Detail label="Target Businesses"  value={profile.b2b_profile.target_business_types?.join(', ') || '—'} />
                  )}
                  <Detail label="Target Customer Size" value={profile.b2b_profile.business_size?.join(', ') || '—'} />
                  <Detail label={profile.customer_type === 'HYBRID' ? "Business Purchase Frequency" : "Purchase Frequency"} value={profile.b2b_profile.purchase_frequency || '—'} />
                  <Detail label={profile.customer_type === 'HYBRID' ? "Avg Transaction/Business" : "Avg Transaction/Order"} value={`RM ${profile.b2b_profile.avg_transaction_rm || 0}`} />
                  {(profile.b2b_profile as any)?.decision_factors && (
                    <Detail label="Decision Factors" value={(profile.b2b_profile as any).decision_factors.join(', ')} />
                  )}
                </div>
              </ProfileRow>
            )}

            <div style={{ marginTop:'1rem', paddingTop:'1rem', borderTop:'1px solid var(--gray-100)' }}>
              <span style={{ fontSize:'0.75rem', fontWeight:600, color:'var(--gray-500)', textTransform:'uppercase', letterSpacing:'0.05em', display:'block', marginBottom:'0.25rem' }}>AI Analysis</span>
              <p style={{ fontStyle:'italic', color:'var(--gray-600)', lineHeight:1.6, margin:0 }}>{profile.reasoning}</p>
            </div>
          </div>

          <div style={{ display:'flex', gap:'1rem', marginBottom:'1rem' }}>
            <HoverBtn style={{ ...S.btnSecondary, flex:1 }} onClick={startEdit}>
              ✏️ Make Corrections
            </HoverBtn>
            <HoverBtn style={{ ...S.btnPrimary, flex:1 }} onClick={onNext}>
              ✓ Yes, looks good
            </HoverBtn>
          </div>
        </>
      )}

      {/* ── Edit mode ── */}
      {profile && editMode && draft && (
        <div style={{ borderWidth:2, borderStyle:'solid', borderColor:'var(--accent)', borderRadius:16, padding:'1.5rem', marginBottom:'1rem' }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'1.5rem', paddingBottom:'1rem', borderBottom:'2px solid var(--gray-100)' }}>
            <h3 style={{ fontSize:'1.25rem', fontWeight:700, margin:0 }}>Edit Customer Profile</h3>
          </div>

          {/* Customer type */}
          <EditField label="Customer Type">
            <select value={draft.customer_type} onChange={e => patchDraft({ customer_type: e.target.value })} style={selectStyle}>
              <option value="B2C">🛍️ B2C — Business to Consumer (individual customers)</option>
              <option value="B2B">🏢 B2B — Business to Business (other businesses)</option>
              <option value="HYBRID">🔄 Both — Mixed (individuals and businesses)</option>
            </select>
          </EditField>

          {/* Target Customers — separate inputs for HYBRID */}
          {showB2C && (
            <EditField label={showB2B ? "B2C Target Customers" : "Primary Customers"}>
              <textarea
                rows={2}
                value={draft.target_customers}
                onChange={e => patchDraft({ target_customers: e.target.value })}
                style={{ ...S.input, resize:'none' }}
              />
              <span style={S.helpText}>Separate multiple segments with commas (e.g., students, working professionals, families)</span>
            </EditField>
          )}

          {showB2B && (
            <EditField label={showB2C ? "B2B Target Business Types" : "Primary Customers"}>
              <textarea
                rows={2}
                value={draft.target_businesses}
                onChange={e => patchDraft({ target_businesses: e.target.value })}
                placeholder="e.g., Cafes, Bakeries, Restaurants"
                style={{ ...S.input, resize:'none' }}
              />
              <span style={S.helpText}>Separate multiple business types with commas (e.g., cafes, retail shops, restaurants)</span>
            </EditField>
          )}

          {/* Price range */}
          <EditField label="Price Range of Products/Services (RM)">
            <div style={{ display:'flex', gap:'1rem', alignItems:'center' }}>
              <div style={{ flex:1 }}>
                <label style={{ fontSize:'0.75rem', color:'var(--gray-500)', display:'block', marginBottom:4 }}>Min</label>
                <input type="number" min={0} value={draft.price_min} onChange={e => patchDraft({ price_min: e.target.value })} style={S.input} />
              </div>
              <div style={{ flex:1 }}>
                <label style={{ fontSize:'0.75rem', color:'var(--gray-500)', display:'block', marginBottom:4 }}>Max</label>
                <input type="number" min={0} value={draft.price_max} onChange={e => patchDraft({ price_max: e.target.value })} style={S.input} />
              </div>
            </div>
          </EditField>

          {/* B2C fields */}
          {showB2C && (
            <>
              <EditField label={showB2B ? "Avg Transaction per Customer (RM)" : "Avg Transaction per Visit (RM)"}>
                <input
                  type="number"
                  min={0}
                  value={draft.b2c_avg_transaction}
                  onChange={e => patchDraft({ b2c_avg_transaction: e.target.value })}
                  placeholder="e.g., 15"
                  style={S.input}
                />
                <span style={S.helpText}>Average amount an individual customer spends per visit</span>
              </EditField>
            </>
          )}

          {/* B2B fields */}
          {showB2B && (
            <>
              <EditField label="Target Customer Business Size">
                <div style={{ display:'flex', gap:'0.5rem' }}>
                  {ALL_BIZ_SIZES.map(sz => (
                    <CheckChip key={sz} label={sz} checked={draft.business_size.includes(sz)}
                      onChange={() => patchDraft({ business_size: toggleArr(draft.business_size, sz) })} />
                  ))}
                </div>
              </EditField>

              <EditField label={showB2C ? "Avg Transaction per Business (RM)" : "Avg Transaction per Order (RM)"}>
                <input
                  type="number"
                  min={0}
                  value={draft.b2b_avg_transaction}
                  onChange={e => patchDraft({ b2b_avg_transaction: e.target.value })}
                  placeholder="e.g., 500"
                  style={S.input}
                />
                <span style={S.helpText}>Average amount a business customer spends per order</span>
              </EditField>

              <EditField label={showB2C ? "Business Purchase Frequency" : "Purchase Frequency"}>
                <select value={draft.b2b_frequency} onChange={e => patchDraft({ b2b_frequency: e.target.value })} style={selectStyle}>
                  {FREQUENCIES.map(f => <option key={f} value={f}>{f.charAt(0).toUpperCase()+f.slice(1)}</option>)}
                </select>
              </EditField>

              <EditField label="Key Decision Factors (select up to 3)">
                <div style={{ display:'flex', flexWrap:'wrap', gap:'0.5rem' }}>
                  {DECISION_FACTORS.map(df => {
                    const isSelected = draft.b2b_decision_factors.includes(df)
                    const atLimit = draft.b2b_decision_factors.length >= 3 && !isSelected
                    return (
                      <CheckChip key={df} label={df.replace('_', ' ')} checked={isSelected}
                        onChange={() => {
                          if (atLimit) return
                          patchDraft({ b2b_decision_factors: toggleArr(draft.b2b_decision_factors, df) })
                        }} />
                    )
                  })}
                </div>
                {draft.b2b_decision_factors.length >= 3 && (
                  <span style={{ fontSize: '0.72rem', color: 'var(--gray-500)', marginTop: '0.25rem', display: 'block' }}>Maximum 3 selected. Deselect one to choose another.</span>
                )}
              </EditField>
            </>
          )}

          {/* Edit actions */}
          <div style={{ display:'flex', gap:'1rem', marginTop:'1.5rem', paddingTop:'1.25rem', borderTop:'2px solid var(--gray-100)' }}>
            <HoverBtn style={{ ...S.btnSecondary, flex:1 }} onClick={cancelEdit}>Cancel</HoverBtn>
            <HoverBtn style={{ ...S.btnPrimary, flex:1 }} onClick={saveEdit}>💾 Save Changes</HoverBtn>
          </div>
        </div>
      )}

      <div style={{ ...S.formActions, marginTop:'2rem' }}>
        <HoverBtn style={S.btnSecondary} onClick={onBack}>← Back</HoverBtn>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </FormCard>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

const selectStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.75rem 1rem',
  fontFamily: 'var(--font-family)',
  fontSize: '0.9375rem',
  borderWidth: '2px',
  borderStyle: 'solid',
  borderColor: 'var(--gray-300)',
  borderRadius: 8,
  background: 'var(--white)',
  cursor: 'pointer',
  outline: 'none',
  color: 'var(--gray-900)',
}

function EditField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <label style={{ ...S.label, marginBottom: '0.5rem' }}>{label}</label>
      {children}
    </div>
  )
}

function CheckChip({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <label style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
      padding: '0.4rem 0.75rem',
      background: checked ? 'var(--accent)' : 'var(--gray-50)',
      color: checked ? 'white' : 'var(--gray-900)',
      borderWidth: '1.5px', borderStyle: 'solid',
      borderColor: checked ? 'var(--accent)' : 'var(--gray-200)',
      borderRadius: 6, cursor: 'pointer',
      fontSize: '0.875rem', fontWeight: checked ? 600 : 400,
      transition: 'all 0.15s',
      userSelect: 'none',
    }}>
      <input type="checkbox" checked={checked} onChange={onChange} style={{ display: 'none' }} />
      {label}
    </label>
  )
}

function ProfileRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display:'flex', alignItems:'flex-start', gap:'1rem', padding:'0.75rem 0', borderBottom:'1px solid var(--gray-50)' }}>
      <span style={{ fontSize:'0.75rem', fontWeight:600, color:'var(--gray-500)', textTransform:'uppercase', letterSpacing:'0.05em', width:160, flexShrink:0, paddingTop:2 }}>{label}</span>
      <div style={{ fontSize:'0.9375rem', color:'var(--gray-900)' }}>{children}</div>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display:'flex', gap:'1rem', padding:'0.5rem', background:'var(--gray-50)', borderRadius:8 }}>
      <span style={{ fontWeight:600, color:'var(--gray-700)', minWidth:150 }}>{label}:</span>
      <span style={{ textTransform:'capitalize' }}>{value}</span>
    </div>
  )
}

function HoverBtn({ style, onClick, children, disabled }: { style: React.CSSProperties; onClick?: () => void; children: React.ReactNode; disabled?: boolean }) {
  const [hov, setHov] = useState(false)
  const isSecondary = style.background === 'white'
  return (
    <button
      onClick={onClick} disabled={disabled}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        ...style,
        background: hov ? (isSecondary ? 'var(--gray-50)' : 'var(--accent)') : style.background,
        borderColor: hov && isSecondary ? 'var(--gray-900)' : style.borderColor,
        opacity: disabled ? 0.6 : 1,
      }}
    >
      {children}
    </button>
  )
}
