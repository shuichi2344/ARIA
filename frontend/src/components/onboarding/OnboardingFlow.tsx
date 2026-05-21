'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import StepBusinessInfo from './StepBusinessInfo'
import StepLocation from './StepLocation'
import StepAnalysis from './StepAnalysis'
import StepReview from './StepReview'
import ProgressBar from './ProgressBar'
import ProfileWidget from '@/components/auth/ProfileWidget'
import { useSession } from '@/context/SessionContext'
import type { CustomerProfileResponse } from '@/lib/api'

export interface BusinessFormData {
  businessName: string
  businessType: string
  businessCategoryId: string
  yearsOperating: string
  uniqueSellingPoints: string
  state: string
  district: string
  city: string
  customerProfile: CustomerProfileResponse | null
}

const INITIAL: BusinessFormData = {
  businessName: '',
  businessType: '',
  businessCategoryId: '',
  yearsOperating: '',
  uniqueSellingPoints: '',
  state: 'Penang',
  district: '',
  city: '',
  customerProfile: null,
}

const STEP_LABELS = ['Business Info', 'Location', 'AI Analysis', 'Review']

export default function OnboardingFlow() {
  const router       = useRouter()
  const searchParams = useSearchParams()
  const { session, logout } = useSession()

  const [step, setStep] = useState(1)
  const [data, setData] = useState<BusinessFormData>(INITIAL)

  // Apply saved theme
  useEffect(() => {
    const saved = localStorage.getItem('aria-theme') || 'burgundy'
    document.body.dataset.theme = saved
  }, [])

  /**
   * If ?edit=1, pre-fill from localStorage — same as openEditBusinessProfile()
   */
  useEffect(() => {
    if (searchParams.get('edit') !== '1') return
    try {
      const raw = localStorage.getItem('aria_profile')
      if (!raw) return
      const profile = JSON.parse(raw)
      setData(prev => ({
        ...prev,
        businessName:        profile.business_name        ?? prev.businessName,
        businessType:        profile.business_type        ?? prev.businessType,
        yearsOperating:      String(profile.years_operating ?? prev.yearsOperating),
        uniqueSellingPoints: profile.unique_selling_points ?? prev.uniqueSellingPoints,
        district:            profile.district              ?? prev.district,
        city:                profile.location?.split(',')[0]?.trim() ?? prev.city,
      }))
    } catch {}
  }, [searchParams])

  function update(partial: Partial<BusinessFormData>) {
    setData(prev => ({ ...prev, ...partial }))
  }

  function next() { setStep(s => Math.min(s + 1, 4)) }
  function back() { setStep(s => Math.max(s - 1, 1)) }

  function finish() {
    router.push('/dashboard')
  }

  function handleLogout() {
    logout()
    router.push('/')
  }

  const isEditMode = searchParams.get('edit') === '1'

  return (
    <>
      {/* Profile widget visible on onboarding too when logged in */}
      {session && (
        <div style={{ position: 'fixed', top: '1rem', right: '1rem', zIndex: 900 }}>
          <ProfileWidget
            session={session}
            onLogout={handleLogout}
            onEditProfile={() => router.push('/onboarding?edit=1')}
          />
        </div>
      )}

      {/* Back arrow when editing — returns to dashboard */}
      {isEditMode && (
        <button
          onClick={() => router.back()}
          style={{
            position: 'fixed',
            top: '1.25rem',
            left: '1.25rem',
            zIndex: 900,
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            background: 'white',
            border: '1px solid var(--gray-200)',
            borderRadius: 8,
            padding: '0.5rem 0.85rem',
            cursor: 'pointer',
            fontSize: '0.82rem',
            fontWeight: 600,
            color: 'var(--gray-700)',
            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
            transition: 'background 0.15s, box-shadow 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--gray-50)'; e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'white'; e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.06)' }}
          aria-label="Go back"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5" /><path d="M12 19l-7-7 7-7" />
          </svg>
          Back
        </button>
      )}

      <div style={{
        minHeight: '100vh',
        padding: '2rem',
        background: 'linear-gradient(135deg, var(--gray-50) 0%, var(--white) 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <div style={{ width: '100%', maxWidth: 900 }}>
          {/* Header */}
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <h1 style={{
              fontFamily: 'var(--font-display)',
              fontSize: 'clamp(2rem,4vw,2.75rem)',
              fontWeight: 800,
              letterSpacing: '-0.02em',
              color: 'var(--primary)',
              marginBottom: '0.75rem',
            }}>
              Get Started with ARIA
            </h1>
            <ProgressBar step={step} labels={STEP_LABELS} />
          </div>

          {step === 1 && <StepBusinessInfo data={data} update={update} onNext={next} />}
          {step === 2 && <StepLocation     data={data} update={update} onNext={next} onBack={back} />}
          {step === 3 && <StepAnalysis     data={data} update={update} onNext={next} onBack={back} />}
          {step === 4 && <StepReview       data={data} onFinish={finish} onBack={back} />}
        </div>
      </div>    </>
  )
}
