'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Eye, EyeOff, CheckCircle2, XCircle, Loader2, ArrowRight, ScrollText, X } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// Password validation helper
function validatePassword(password: string): { isValid: boolean; errors: string[] } {
  const errors: string[] = []
  
  if (password.length < 6) errors.push('At least 6 characters')
  if (!/[A-Z]/.test(password)) errors.push('One uppercase letter')
  if (!/[0-9]/.test(password)) errors.push('One number')
  if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?~`]/.test(password)) errors.push('One special character')
  
  return { isValid: errors.length === 0, errors }
}

export default function SetupPasswordPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [acceptedTerms, setAcceptedTerms] = useState(false)
  const [showTerms, setShowTerms] = useState(false)
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  
  const [accessToken, setAccessToken] = useState<string | null>(null)
  
  // Extract access_token from URL fragment (#access_token=...)
  useEffect(() => {
    // Check URL hash for Supabase invitation token
    const hash = window.location.hash
    if (hash) {
      const params = new URLSearchParams(hash.substring(1))
      const token = params.get('access_token')
      if (token) {
        setAccessToken(token)
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname)
      }
    }
    
    // Also check query params as fallback
    const token = searchParams?.get('access_token')
    if (token) {
      setAccessToken(token)
    }
  }, [searchParams])
  
  const passwordValidation = validatePassword(password)
  const passwordsMatch = password === confirmPassword && password.length > 0
  const canSubmit = passwordValidation.isValid && passwordsMatch && acceptedTerms && accessToken
  
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    
    if (!canSubmit) return
    
    setError('')
    setLoading(true)
    
    try {
      const res = await fetch(`${API_BASE}/api/auth/setup-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          access_token: accessToken,
          new_password: password,
          accepted_terms: acceptedTerms,
        }),
      })
      
      const data = await res.json()
      
      if (!res.ok) {
        setError(data.detail || 'Failed to set password. Please try again.')
        return
      }
      
      setSuccess(true)
      
      // Redirect to home page with login prompt after 2 seconds
      setTimeout(() => {
        router.push('/?auth=login')
      }, 2000)
      
    } catch {
      setError('Could not reach the server. Please check your connection.')
    } finally {
      setLoading(false)
    }
  }
  
  // Show error if no token
  if (!accessToken && typeof window !== 'undefined') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem', background: '#ffffff' }}>
        <div style={{ maxWidth: '480px', width: '100%', background: '#fff', borderRadius: '16px', padding: '2.5rem 2rem', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', border: '1px solid #e5e7eb' }}>
          <div style={{ textAlign: 'center' }}>
            <XCircle style={{ width: 56, height: 56, color: '#ef4444', margin: '0 auto 1.25rem' }} />
            <h1 style={{ fontSize: '1.375rem', fontWeight: 700, color: '#1f2937', margin: '0 0 0.75rem' }}>
              Invalid Invitation Link
            </h1>
            <p style={{ color: '#6b7280', margin: '0 0 1.25rem', lineHeight: 1.6, fontSize: '0.875rem' }}>
              This invitation link is invalid or has expired. Invitation links are valid for 6 hours after they are sent.
            </p>
            <p style={{ color: '#9ca3af', fontSize: '0.8125rem', margin: '0 0 1.5rem' }}>
              Please contact the administrator to request a new invitation.
            </p>
            <button
              onClick={() => router.push('/')}
              style={{
                width: '100%',
                padding: '0.75rem',
                background: '#667eea',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                fontSize: '0.9375rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'background 0.2s',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = '#5568d3')}
              onMouseLeave={e => (e.currentTarget.style.background = '#667eea')}
            >
              Go to Homepage
            </button>
          </div>
        </div>
      </div>
    )
  }
  
  if (success) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem', background: '#ffffff' }}>
        <div style={{ maxWidth: '480px', width: '100%', background: '#fff', borderRadius: '16px', padding: '2.5rem 2rem', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', border: '1px solid #e5e7eb' }}>
          <div style={{ textAlign: 'center' }}>
            <CheckCircle2 style={{ width: 56, height: 56, color: '#10b981', margin: '0 auto 1.25rem' }} />
            <h1 style={{ fontSize: '1.375rem', fontWeight: 700, color: '#1f2937', margin: '0 0 0.75rem' }}>
              Password Set Successfully!
            </h1>
            <p style={{ color: '#6b7280', margin: '0 0 0.75rem', lineHeight: 1.6, fontSize: '0.875rem' }}>
              Your password has been set and your <strong>7-day beta access period</strong> has started.
            </p>
            <p style={{ color: '#9ca3af', fontSize: '0.8125rem', margin: '0 0 1.5rem' }}>
              Redirecting to login page...
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', margin: '1rem 0 0' }}>
              <Loader2 style={{ width: 24, height: 24, color: '#667eea', animation: 'spin 1s linear infinite' }} />
            </div>
          </div>
        </div>
      </div>
    )
  }
  
  return (
    <div style={{ 
      minHeight: '100vh', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center', 
      padding: '1.5rem', 
      background: '#ffffff'
    }}>
      <div style={{ 
        maxWidth: '500px', 
        width: '100%', 
        background: '#fff', 
        borderRadius: '16px', 
        padding: '2rem 2rem 2rem', 
        boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
        border: '1px solid #e5e7eb'
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <h1 style={{ 
            fontFamily: 'var(--font-display, system-ui)', 
            fontSize: '2.5rem', 
            fontWeight: 900, 
            margin: '0 0 0.25rem',
            color: '#000000'
          }}>
            ARIA
          </h1>
          <p style={{ color: '#6b7280', fontSize: '0.8125rem', margin: '0 0 0.75rem' }}>
            Agentic Retail Intelligence &amp; Analytics
          </p>
          <div style={{ 
            height: '1px', 
            background: 'linear-gradient(90deg, transparent, #e5e7eb 20%, #e5e7eb 80%, transparent)', 
            margin: '0.75rem 0' 
          }} />
          <p style={{ fontSize: '1.125rem', fontWeight: 600, color: '#1f2937', margin: '0.5rem 0 0.25rem' }}>
            Set Your Password
          </p>
          <p style={{ fontSize: '0.8125rem', color: '#6b7280', margin: 0 }}>
            Welcome to the ARIA Beta Programme
          </p>
        </div>
        
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Password field */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#374151', marginBottom: '0.375rem' }}>
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Create a secure password"
                required
                style={{
                  width: '100%',
                  padding: '0.625rem 2.5rem 0.625rem 0.875rem',
                  fontSize: '0.875rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '8px',
                  outline: 'none',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => (e.currentTarget.style.borderColor = '#667eea')}
                onBlur={e => (e.currentTarget.style.borderColor = '#d1d5db')}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '0.875rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#9ca3af',
                  padding: 0,
                }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            
            {/* Compact password requirements */}
            {password && (
              <div style={{ 
                margin: '0.5rem 0 0', 
                display: 'grid', 
                gridTemplateColumns: '1fr 1fr', 
                gap: '0.25rem',
                fontSize: '0.75rem'
              }}>
                {[
                  { check: password.length >= 6, text: '6+ chars' },
                  { check: /[A-Z]/.test(password), text: 'Uppercase' },
                  { check: /[0-9]/.test(password), text: 'Number' },
                  { check: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?~`]/.test(password), text: 'Special' },
                ].map((req, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: req.check ? '#10b981' : '#9ca3af' }}>
                    {req.check ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                    {req.text}
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {/* Confirm password field */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: '#374151', marginBottom: '0.375rem' }}>
              Confirm Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showConfirm ? 'text' : 'password'}
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="Repeat your password"
                required
                style={{
                  width: '100%',
                  padding: '0.625rem 2.5rem 0.625rem 0.875rem',
                  fontSize: '0.875rem',
                  border: '1px solid #d1d5db',
                  borderRadius: '8px',
                  outline: 'none',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => (e.currentTarget.style.borderColor = '#667eea')}
                onBlur={e => (e.currentTarget.style.borderColor = '#d1d5db')}
              />
              <button
                type="button"
                onClick={() => setShowConfirm(!showConfirm)}
                style={{
                  position: 'absolute',
                  right: '0.875rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#9ca3af',
                  padding: 0,
                }}
              >
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            
            {confirmPassword && (
              <div style={{ margin: '0.375rem 0 0', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.375rem', color: passwordsMatch ? '#10b981' : '#ef4444' }}>
                {passwordsMatch ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                {passwordsMatch ? 'Passwords match' : 'Passwords do not match'}
              </div>
            )}
          </div>
          
          {/* Compact Terms & Conditions */}
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', cursor: 'pointer', userSelect: 'none', marginTop: '0.25rem' }}>
            <input
              type="checkbox"
              checked={acceptedTerms}
              onChange={e => setAcceptedTerms(e.target.checked)}
              style={{ marginTop: '0.125rem', width: 15, height: 15, accentColor: '#667eea', flexShrink: 0, cursor: 'pointer' }}
            />
            <span style={{ fontSize: '0.75rem', color: '#6b7280', lineHeight: 1.4 }}>
              I accept the{' '}
              <button
                type="button"
                onClick={() => setShowTerms(true)}
                style={{ background: 'none', border: 'none', padding: 0, color: '#667eea', fontWeight: 600, cursor: 'pointer', fontSize: 'inherit', textDecoration: 'underline', textUnderlineOffset: '2px' }}
              >
                Terms &amp; Conditions
              </button>
              {' '}and understand this is a beta testing platform
            </span>
          </label>
          
          {/* Error message */}
          {error && (
            <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', borderRadius: '6px', padding: '0.625rem 0.875rem', fontSize: '0.8125rem' }}>
              {error}
            </div>
          )}
          
          {/* Submit button */}
          <button
            type="submit"
            disabled={!canSubmit || loading}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              padding: '0.75rem',
              background: canSubmit && !loading ? '#000000' : '#e5e7eb',
              color: canSubmit && !loading ? '#fff' : '#9ca3af',
              fontSize: '0.9375rem',
              fontWeight: 600,
              border: 'none',
              borderRadius: '8px',
              cursor: canSubmit && !loading ? 'pointer' : 'not-allowed',
              transition: 'all 0.2s',
              marginTop: '0.5rem'
            }}
            onMouseEnter={e => {
              if (canSubmit && !loading) e.currentTarget.style.background = '#1f2937'
            }}
            onMouseLeave={e => {
              if (canSubmit && !loading) e.currentTarget.style.background = '#000000'
            }}
          >
            {loading ? (
              <Loader2 style={{ width: 18, height: 18, animation: 'spin 1s linear infinite' }} />
            ) : (
              <>
                Set Password & Continue <ArrowRight size={18} />
              </>
            )}
          </button>
        </form>
        
        <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '8px', fontSize: '0.75rem', color: '#92400e', lineHeight: 1.5 }}>
          <strong>Beta Access:</strong> Your 7-day trial period begins when you set your password.
        </div>
      </div>
      
      {/* Terms modal */}
      {showTerms && <TermsModal onClose={() => setShowTerms(false)} onAccept={() => { setAcceptedTerms(true); setShowTerms(false) }} />}
    </div>
  )
}


// Terms & Conditions Modal (copied from AuthModal)
const TERMS: { title: string; body: string }[] = [
  {
    title: '1. Nature of the Tool',
    body:  'ARIA (Agentic Retail Intelligence & Analytics) is a research prototype and AI-powered simulation platform provided strictly for exploratory and academic purposes. It is currently in beta and has not been validated as a commercial decision-making product.',
  },
  {
    title: '2. No Guarantee of Results',
    body:  'All simulation outputs — including visit rates, churn rates, revenue estimates, risk levels, and recommendations — are generated by AI models using synthetic customer data. They are indicative only and do not constitute professional business, financial, legal, or marketing advice. ARIA makes no warranty, express or implied, that simulation results will reflect actual real-world outcomes.',
  },
  {
    title: '3. Limitation of Liability',
    body:  'The ARIA development team, its supervisors, affiliated institutions, and contributors shall not be held responsible or liable for any business loss, financial loss, reputational damage, or any other adverse outcome arising directly or indirectly from reliance on ARIA\'s simulation results or recommendations. You use ARIA\'s output entirely at your own discretion and risk.',
  },
  {
    title: '4. Your Responsibility',
    body:  'You acknowledge that any business decision you make remains your own responsibility. ARIA\'s output should be considered as one exploratory input among multiple sources of information and professional judgment. Do not make significant financial or operational decisions based solely on ARIA\'s results.',
  },
  {
    title: '5. Beta Feedback',
    body:  'As a beta tester, you agree to provide honest feedback on your experience. Feedback may be used to improve the platform. No personally identifiable business information will be published or shared without your explicit consent.',
  },
  {
    title: '6. Data Usage',
    body:  'Business information you provide during onboarding and testing is stored securely and used solely to run simulations and improve the platform. It will not be sold or shared with third parties. Simulations run on a local AI model — your data does not leave to external AI providers.',
  },
  {
    title: '7. Beta Access Duration',
    body:  'Beta access is time-limited to 7 days from the date you set your password. After this period, access will be automatically revoked. Extensions may be granted at the sole discretion of the ARIA team.',
  },
  {
    title: '8. Changes to Terms',
    body:  'These terms may be updated as the product evolves. Continued use of the platform constitutes acceptance of any revised terms. You will be notified of material changes.',
  },
]

function TermsModal({ onClose, onAccept }: { onClose: () => void; onAccept: () => void }) {
  return (
    <div
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
      style={{
        position: 'fixed', inset: 0, zIndex: 1100,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '1rem',
        background: 'rgba(0,0,0,0.6)',
        backdropFilter: 'blur(4px)',
      }}
    >
      <div
        style={{
          position: 'relative',
          width: '100%', maxWidth: '560px',
          background: '#fff',
          borderRadius: '12px',
          boxShadow: '0 24px 64px rgba(0,0,0,0.3)',
          display: 'flex', flexDirection: 'column',
          maxHeight: '90vh',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '1.25rem 1.5rem',
          borderBottom: '1px solid #e5e7eb',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <ScrollText style={{ width: 20, height: 20, color: '#000000', flexShrink: 0 }} />
            <div>
              <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#1f2937' }}>
                Terms &amp; Conditions
              </h2>
              <p style={{ margin: 0, fontSize: '0.75rem', color: '#9ca3af' }}>
                ARIA Beta Programme — please read before continuing
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: '#9ca3af', padding: '0.25rem',
              borderRadius: '4px', display: 'flex', alignItems: 'center',
              transition: 'color 0.2s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = '#000000')}
            onMouseLeave={e => (e.currentTarget.style.color = '#9ca3af')}
          >
            <X style={{ width: 18, height: 18 }} />
          </button>
        </div>

        {/* Scrollable body */}
        <div style={{
          overflowY: 'auto', padding: '1.5rem',
          display: 'flex', flexDirection: 'column', gap: '1.25rem',
          flex: 1,
        }}>
          {/* Disclaimer banner */}
          <div style={{
            background: '#fffbeb', border: '1px solid #fde68a',
            borderRadius: 8, padding: '0.875rem 1rem',
            fontSize: '0.8125rem', color: '#92400e', lineHeight: 1.6,
          }}>
            <strong>Important:</strong> ARIA is a simulation tool for exploratory purposes only. Results are AI-generated estimates based on synthetic data — they are not professional business advice and do not guarantee real-world outcomes.
          </div>

          {TERMS.map(section => (
            <div key={section.title}>
              <h3 style={{
                margin: '0 0 0.375rem',
                fontSize: '0.875rem', fontWeight: 700,
                color: '#1f2937',
              }}>
                {section.title}
              </h3>
              <p style={{
                margin: 0, fontSize: '0.8125rem',
                color: '#6b7280', lineHeight: 1.65,
              }}>
                {section.body}
              </p>
            </div>
          ))}
        </div>

        {/* Footer actions */}
        <div style={{
          padding: '1rem 1.5rem',
          borderTop: '1px solid #e5e7eb',
          display: 'flex', gap: '0.75rem',
          flexShrink: 0,
          background: '#f9fafb',
        }}>
          <button
            onClick={onClose}
            style={{
              flex: 1,
              padding: '0.75rem',
              background: 'none',
              border: '2px solid #e5e7eb',
              borderRadius: 8, cursor: 'pointer',
              fontSize: '0.9rem', fontWeight: 600,
              color: '#6b7280',
              transition: 'border-color 0.2s, color 0.2s',
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = '#9ca3af'; e.currentTarget.style.color = '#1f2937' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#e5e7eb'; e.currentTarget.style.color = '#6b7280' }}
          >
            Decline
          </button>
          <button
            onClick={onAccept}
            style={{
              flex: 2,
              padding: '0.75rem',
              background: '#000000',
              border: 'none', borderRadius: 8,
              cursor: 'pointer',
              fontSize: '0.9rem', fontWeight: 600,
              color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem',
              transition: 'background 0.2s',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = '#1f2937')}
            onMouseLeave={e => (e.currentTarget.style.background = '#000000')}
          >
            I Agree &amp; Continue <ArrowRight style={{ width: 16, height: 16, strokeWidth: 2.5 }} />
          </button>
        </div>
      </div>
    </div>
  )
}
