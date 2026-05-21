'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import { useSession } from '@/context/SessionContext'
import { DISTRICTS } from '@/lib/districts'
import type { BusinessFormData } from './OnboardingFlow'
import FormCard from './FormCard'
import * as S from './styles'

interface Props {
  data: BusinessFormData
  onFinish: () => void
  onBack: () => void
}

export default function StepReview({ data, onFinish, onBack }: Props) {
  const { session } = useSession()
  const [saving, setSaving] = useState(false)
  const districtLabel = data.district ? DISTRICTS[data.district]?.label ?? data.district : '—'

  async function handleFinish() {
    setSaving(true)
    try {
      if (session?.id) {
        // Check if we're editing an existing profile
        const existingProfileId = localStorage.getItem('aria_profile_id')
        
        let result
        if (existingProfileId) {
          // Update existing profile
          result = await api.updateBusinessProfile(existingProfileId, {
            user_id: session.id, business_name: data.businessName, business_type: data.businessType,
            business_category_id: data.businessCategoryId, location: `${data.city}, ${data.state}`,
            district: data.district, years_operating: data.yearsOperating ? parseInt(data.yearsOperating) : undefined,
            unique_selling_points: data.uniqueSellingPoints,
            price_range_min: data.customerProfile?.price_range?.min, price_range_max: data.customerProfile?.price_range?.max,
            customer_profile: data.customerProfile ?? undefined,
          })
        } else {
          // Create new profile
          result = await api.createBusinessProfile({
            user_id: session.id, business_name: data.businessName, business_type: data.businessType,
            business_category_id: data.businessCategoryId, location: `${data.city}, ${data.state}`,
            district: data.district, years_operating: data.yearsOperating ? parseInt(data.yearsOperating) : undefined,
            unique_selling_points: data.uniqueSellingPoints,
            price_range_min: data.customerProfile?.price_range?.min, price_range_max: data.customerProfile?.price_range?.max,
            customer_profile: data.customerProfile ?? undefined,
          })
        }
        
        // Save full profile (including customer_profile) to localStorage
        const fullProfile = {
          ...result,
          customer_profile: data.customerProfile,
        }
        localStorage.setItem('aria_profile', JSON.stringify(fullProfile))
        localStorage.setItem('aria_profile_id', result.id)
      }
    } catch (e) { console.warn('Profile save failed (non-fatal):', e) }
    finally { setSaving(false); onFinish() }
  }

  return (
    <FormCard title="✅ Review Your Business Profile">

      <ReviewSection title="📋 Business Information">
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1rem' }}>
          <ReviewItem label="Name"                 value={data.businessName} />
          <ReviewItem label="Type"                 value={data.businessType} />
          <ReviewItem label="Unique Selling Points" value={data.uniqueSellingPoints || '—'} />
          <ReviewItem label="Years Operating"      value={data.yearsOperating || '0'} />
        </div>
      </ReviewSection>

      <ReviewSection title="📍 Location">
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1rem' }}>
          <ReviewItem label="State"    value={data.state} />
          <ReviewItem label="District" value={districtLabel} />
          <ReviewItem label="City"     value={data.city} />
        </div>
      </ReviewSection>

      {data.customerProfile && (
        <ReviewSection title="👥 Customer Profile">
          <ReviewItem label="Type"        value={data.customerProfile.customer_type} />
          <ReviewItem label="Target Customers" value={data.customerProfile.target_customers} />
          {data.customerProfile.price_range && (
            <ReviewItem label="Price Range" value={`RM ${data.customerProfile.price_range.min.toFixed(2)} – RM ${data.customerProfile.price_range.max.toFixed(2)}`} />
          )}
        </ReviewSection>
      )}

      {/* Success box */}
      <div style={{ display:'flex', gap:'1rem', alignItems:'flex-start', background:'#f0fdf4', borderLeft:'4px solid #10b981', borderRadius:12, padding:'1rem 1.25rem', marginBottom:'1.5rem' }}>
        <span style={{ fontSize:'1.25rem' }}>🎉</span>
        <div>
          <strong style={{ display:'block', marginBottom:'0.25rem', color:'var(--gray-900)' }}>Great! Your business profile is ready.</strong>
          <p style={{ margin:0, color:'var(--gray-700)', fontSize:'0.9375rem', lineHeight:1.6 }}>Click "Complete Setup" to save your profile and start using ARIA. You can always update this information later in the settings.</p>
        </div>
      </div>

      <div style={S.formActions}>
        <HoverBtn style={S.btnSecondary} onClick={onBack}>← Back</HoverBtn>
        <HoverBtn style={{ ...S.btnPrimary, flex:1 }} onClick={handleFinish} disabled={saving}>
          {saving ? 'Saving...' : 'Complete Setup →'}
        </HoverBtn>
      </div>
    </FormCard>
  )
}

function ReviewSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom:'2rem' }}>
      <h3 style={{ fontSize:'1.25rem', fontWeight:600, color:'var(--gray-900)', marginBottom:'1rem', paddingBottom:'0.75rem', borderBottom:'2px solid var(--gray-200)' }}>{title}</h3>
      {children}
    </div>
  )
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:'0.25rem', marginBottom:'0.5rem' }}>
      <span style={{ fontWeight:600, color:'var(--gray-700)', fontSize:'0.875rem' }}>{label}</span>
      <span style={{ color:'var(--gray-900)', fontSize:'1rem' }}>{value}</span>
    </div>
  )
}

function HoverBtn({ style, onClick, children, disabled }: { style: React.CSSProperties; onClick?: () => void; children: React.ReactNode; disabled?: boolean }) {
  const [hov, setHov] = useState(false)
  const isSecondary = style.background === 'white'
  return (
    <button onClick={onClick} disabled={disabled} onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{ ...style, background: hov ? (isSecondary ? 'var(--gray-50)' : 'var(--accent)') : style.background, borderColor: hov && isSecondary ? 'var(--gray-900)' : style.borderColor, opacity: disabled ? 0.6 : 1 }}>
      {children}
    </button>
  )
}
