'use client'

import { useState } from 'react'
import { X, ArrowRight, Loader2, Eye, EyeOff, ScrollText } from 'lucide-react'

interface Props {
  defaultTab?: 'login' | 'register'
  onClose: () => void
  onSuccess: (user: {
    id: string
    email: string
    created_at: string
    access_token: string
    refresh_token?: string
    email_confirmed?: boolean
  }) => void
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

/* Input style matching the original web/styles.css .form-group input */
const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.875rem 1.125rem',
  fontFamily: 'var(--font-family)',
  fontSize: '1rem',
  borderWidth: '2px',
  borderStyle: 'solid',
  borderColor: 'var(--gray-200)',
  borderRadius: '10px',
  background: 'var(--gray-50)',
  outline: 'none',
  transition: 'all 0.3s cubic-bezier(0.16,1,0.3,1)',
  color: 'var(--gray-900)',
}

function AuthInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const [focused, setFocused] = useState(false)
  return (
    <input
      {...props}
      style={{
        ...inputStyle,
        borderColor: focused ? 'var(--accent)' : 'var(--gray-200)',
        background: focused ? '#fff' : 'var(--gray-50)',
        boxShadow: focused ? '0 0 0 4px color-mix(in srgb, var(--accent) 10%, transparent)' : 'none',
        transform: focused ? 'translateY(-1px)' : 'none',
      }}
      onFocus={e => { setFocused(true); props.onFocus?.(e) }}
      onBlur={e => { setFocused(false); props.onBlur?.(e) }}
    />
  )
}

function PasswordInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const [focused, setFocused] = useState(false)
  const [visible, setVisible] = useState(false)
  return (
    <div style={{ position: 'relative' }}>
      <input
        {...props}
        type={visible ? 'text' : 'password'}
        style={{
          ...inputStyle,
          paddingRight: '3rem',
          borderColor: focused ? 'var(--accent)' : 'var(--gray-200)',
          background: focused ? '#fff' : 'var(--gray-50)',
          boxShadow: focused ? '0 0 0 4px color-mix(in srgb, var(--accent) 10%, transparent)' : 'none',
          transform: focused ? 'translateY(-1px)' : 'none',
          width: '100%',
        }}
        onFocus={e => { setFocused(true); props.onFocus?.(e) }}
        onBlur={e => { setFocused(false); props.onBlur?.(e) }}
      />
      <button
        type="button"
        onClick={() => setVisible(v => !v)}
        tabIndex={-1}
        aria-label={visible ? 'Hide password' : 'Show password'}
        style={{
          position: 'absolute', right: '0.875rem', top: '50%',
          transform: 'translateY(-50%)',
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--gray-400)', display: 'flex', alignItems: 'center',
          padding: 0, transition: 'color 0.15s',
        }}
        onMouseEnter={e => (e.currentTarget.style.color = 'var(--gray-700)')}
        onMouseLeave={e => (e.currentTarget.style.color = 'var(--gray-400)')}
      >
        {visible
          ? <EyeOff style={{ width: 18, height: 18 }} />
          : <Eye    style={{ width: 18, height: 18 }} />}
      </button>
    </div>
  )
}

function validatePassword(password: string): string | null {
  if (password.length < 6) return 'Password must be at least 6 characters.'
  if (!/[A-Z]/.test(password)) return 'Password must include at least one uppercase letter.'
  if (!/[0-9]/.test(password)) return 'Password must include at least one number.'
  if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?~`]/.test(password)) return 'Password must include at least one special character.'
  return null
}

export default function AuthModal({ defaultTab = 'login', onClose, onSuccess }: Props) {
  const [tab, setTab] = useState<'login' | 'register' | 'forgot'>(defaultTab)

  const [loginEmail, setLoginEmail]       = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginError, setLoginError]       = useState('')
  const [loginLoading, setLoginLoading]   = useState(false)

  const [regEmail, setRegEmail]       = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regConfirm, setRegConfirm]   = useState('')
  const [regError, setRegError]       = useState('')
  const [regLoading, setRegLoading]   = useState(false)
  const [regTerms, setRegTerms]       = useState(false)
  const [showTerms, setShowTerms]     = useState(false)

  const [forgotEmail, setForgotEmail]     = useState('')
  const [forgotError, setForgotError]     = useState('')
  const [forgotSuccess, setForgotSuccess] = useState(false)
  const [forgotLoading, setForgotLoading] = useState(false)

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoginError('')
    setLoginLoading(true)
    try {
      const res  = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail.trim(), password: loginPassword }),
      })
      const data = await res.json()
      if (!res.ok) {
        if (data.detail === 'EMAIL_NOT_CONFIRMED') {
          setLoginError('Please confirm your email address before signing in. Check your inbox for a confirmation link.')
          return
        }
        setLoginError(data.detail || 'Login failed.')
        return
      }
      if (!data.access_token) {
        setLoginError('Login succeeded but no session token was returned. Please try again.')
        return
      }
      onSuccess(data)
    } catch {
      setLoginError('Could not reach the server. Make sure the API is running.')
    } finally {
      setLoginLoading(false)
    }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    setRegError('')
    if (regPassword !== regConfirm) { setRegError('Passwords do not match.'); return }
    const pwError = validatePassword(regPassword)
    if (pwError) { setRegError(pwError); return }
    if (!regTerms) { setRegError('You must agree to the Terms & Conditions to create an account.'); return }
    setRegLoading(true)
    try {
      const res  = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: regEmail.trim(), password: regPassword }),
      })
      const data = await res.json()
      if (!res.ok) { setRegError(data.detail || 'Registration failed.'); return }
      // If email confirmation is required, access_token is null until confirmed
      if (data.email_confirmed === false || !data.access_token) {
        setRegError('Account created! Please check your email to confirm your address before logging in.')
        return
      }
      onSuccess(data)
    } catch {
      setRegError('Could not reach the server. Make sure the API is running.')
    } finally {
      setRegLoading(false)
    }
  }

  async function handleForgotPassword(e: React.FormEvent) {
    e.preventDefault()
    setForgotError('')
    setForgotSuccess(false)
    setForgotLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: forgotEmail.trim() }),
      })
      const data = await res.json()
      if (!res.ok) { setForgotError(data.detail || 'Request failed.'); return }
      setForgotSuccess(true)
    } catch {
      setForgotError('Could not reach the server. Make sure the API is running.')
    } finally {
      setForgotLoading(false)
    }
  }

  return (
    /* Backdrop — matches .auth-overlay */
    <div
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '1rem',
        background: 'rgba(0,0,0,0.55)',
        backdropFilter: 'blur(4px)',
        animation: 'fadeIn 0.2s ease',
      }}
    >
      {/* Card — matches .auth-container */}
      <div
        style={{
          position: 'relative',
          width: '100%', maxWidth: '420px',
          background: 'var(--white)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
          padding: '2.5rem 2rem',
          display: 'flex', flexDirection: 'column', gap: '1.5rem',
          animation: 'slideUp 0.25s ease',
        }}
      >
        {/* Close — matches .auth-close */}
        <button
          onClick={onClose}
          aria-label="Close"
          style={{
            position: 'absolute', top: '1rem', right: '1rem',
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--gray-400)', padding: '0.25rem',
            borderRadius: '4px', display: 'flex', alignItems: 'center',
            transition: 'color 0.2s',
          }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--gray-900)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--gray-400)')}
        >
          <X style={{ width: 20, height: 20 }} />
        </button>

        {/* Brand — matches .auth-brand / .auth-logo */}
        <div style={{ textAlign: 'center' }}>
          <h1
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: '2.5rem',
              fontWeight: 900,
              lineHeight: 1,
              margin: 0,
              background: 'linear-gradient(135deg, var(--accent), var(--accent-warm))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            ARIA
          </h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--gray-600)', margin: '0.4rem 0 0' }}>
            Agentic Retail Intelligence &amp; Analytics
          </p>
        </div>

        {/* Tabs — matches .auth-tabs / .auth-tab */}
        <div style={{ display: 'flex', borderBottom: '2px solid var(--gray-200)' }}>
          {(['login', 'register'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                flex: 1,
                background: 'none', border: 'none',
                padding: '0.75rem 1rem',
                fontSize: '0.95rem', fontWeight: 600,
                cursor: 'pointer',
                color: (tab === t || (tab === 'forgot' && t === 'login')) ? 'var(--accent)' : 'var(--gray-600)',
                borderBottom: (tab === t || (tab === 'forgot' && t === 'login')) ? '2px solid var(--accent)' : '2px solid transparent',
                marginBottom: '-2px',
                transition: 'color 0.2s, border-color 0.2s',
              }}
            >
              {t === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          ))}
        </div>

        {/* Login form */}
        {tab === 'login' && (
          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <FormField label="Email">
              <AuthInput
                type="email" value={loginEmail}
                onChange={e => setLoginEmail(e.target.value)}
                placeholder="you@example.com" required autoComplete="email"
              />
            </FormField>
            <FormField label="Password">
              <PasswordInput
                value={loginPassword}
                onChange={e => setLoginPassword(e.target.value)}
                placeholder="••••••••" required autoComplete="current-password"
              />
            </FormField>
            <button
              type="button"
              onClick={() => { setTab('forgot'); setForgotEmail(loginEmail); setForgotSuccess(false); setForgotError('') }}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--accent)', fontSize: '0.85rem', fontWeight: 500,
                textAlign: 'right', padding: 0, marginTop: '-0.5rem',
              }}
            >
              Forgot password?
            </button>
            {loginError && <AuthError>{loginError}</AuthError>}
            <SubmitBtn loading={loginLoading}>Sign In</SubmitBtn>
          </form>
        )}

        {/* Forgot password form */}
        {tab === 'forgot' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <p style={{ fontSize: '0.875rem', color: 'var(--gray-600)', margin: 0 }}>
              Enter your email address and we&apos;ll send you a link to reset your password.
            </p>
            {forgotSuccess ? (
              <div style={{
                padding: '1rem', background: '#f0fdf4', border: '1px solid #bbf7d0',
                borderRadius: 8, color: '#166534', fontSize: '0.875rem', textAlign: 'center',
              }}>
                ✓ If an account with that email exists, a reset link has been sent. Check your inbox.
              </div>
            ) : (
              <form onSubmit={handleForgotPassword} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <FormField label="Email">
                  <AuthInput
                    type="email" value={forgotEmail}
                    onChange={e => setForgotEmail(e.target.value)}
                    placeholder="you@example.com" required autoComplete="email"
                  />
                </FormField>
                {forgotError && <AuthError>{forgotError}</AuthError>}
                <SubmitBtn loading={forgotLoading}>Send Reset Link</SubmitBtn>
              </form>
            )}
            <button
              type="button"
              onClick={() => setTab('login')}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--gray-600)', fontSize: '0.85rem', fontWeight: 500,
                textAlign: 'center', padding: 0,
              }}
            >
              ← Back to Sign In
            </button>
          </div>
        )}

        {/* Register form */}
        {tab === 'register' && (
          <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <FormField label="Email">
              <AuthInput
                type="email" value={regEmail}
                onChange={e => setRegEmail(e.target.value)}
                placeholder="you@example.com" required autoComplete="email"
              />
            </FormField>
            <FormField label="Password">
              <PasswordInput
                value={regPassword}
                onChange={e => setRegPassword(e.target.value)}
                placeholder="Min 6 chars, uppercase, number, special" required minLength={6} autoComplete="new-password"
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--gray-500)', marginTop: '-0.25rem' }}>
                Must include uppercase, number, and special character
              </span>
            </FormField>
            <FormField label="Confirm Password">
              <PasswordInput
                value={regConfirm}
                onChange={e => setRegConfirm(e.target.value)}
                placeholder="Repeat your password" required autoComplete="new-password"
              />
            </FormField>

            {/* T&C checkbox */}
            <label
              style={{
                display: 'flex', alignItems: 'flex-start', gap: '0.625rem',
                cursor: 'pointer', userSelect: 'none',
              }}
            >
              <input
                type="checkbox"
                checked={regTerms}
                onChange={e => setRegTerms(e.target.checked)}
                style={{
                  marginTop: '0.15rem',
                  width: 16, height: 16,
                  accentColor: 'var(--accent)',
                  flexShrink: 0, cursor: 'pointer',
                }}
              />
              <span style={{ fontSize: '0.8125rem', color: 'var(--gray-600)', lineHeight: 1.5 }}>
                I have read and agree to the{' '}
                <button
                  type="button"
                  onClick={() => setShowTerms(true)}
                  style={{
                    background: 'none', border: 'none', padding: 0,
                    color: 'var(--accent)', fontWeight: 600,
                    cursor: 'pointer', fontSize: 'inherit',
                    textDecoration: 'underline', textUnderlineOffset: '2px',
                  }}
                >
                  Terms &amp; Conditions
                </button>
                {' '}of the ARIA Beta Programme. I understand that simulation results are indicative only and ARIA is not liable for any business outcomes.
              </span>
            </label>

            {regError && <AuthError>{regError}</AuthError>}
            <SubmitBtn loading={regLoading}>Create Account</SubmitBtn>
          </form>
        )}

        {/* T&C modal */}
        {showTerms && <TermsModal onClose={() => setShowTerms(false)} onAccept={() => { setRegTerms(true); setShowTerms(false) }} />}
      </div>
    </div>
  )
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <label style={{ fontSize: '0.9375rem', fontWeight: 600, color: 'var(--gray-900)' }}>
        {label}
      </label>
      {children}
    </div>
  )
}

function AuthError({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      background: '#fef2f2', border: '1px solid #fecaca',
      color: '#dc2626', borderRadius: '6px',
      padding: '0.6rem 0.9rem', fontSize: '0.875rem',
    }}>
      {children}
    </div>
  )
}

function SubmitBtn({ loading, children }: { loading: boolean; children: React.ReactNode }) {
  const [hovered, setHovered] = useState(false)
  return (
    <button
      type="submit"
      disabled={loading}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: '100%',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
        background: hovered ? 'var(--accent)' : 'var(--primary)',
        color: '#fff',
        fontFamily: 'var(--font-family)',
        fontSize: '1.125rem', fontWeight: 600,
        padding: '1rem 3rem',
        border: 'none', borderRadius: '8px',
        cursor: loading ? 'not-allowed' : 'pointer',
        opacity: loading ? 0.6 : 1,
        boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
        transition: 'all 0.3s cubic-bezier(0.16,1,0.3,1)',
        marginTop: '0.5rem',
        letterSpacing: '-0.01em',
      }}
    >
      {loading
        ? <Loader2 style={{ width: 20, height: 20, animation: 'spin 1s linear infinite' }} />
        : <>{children} <ArrowRight style={{ width: 20, height: 20, strokeWidth: 2.5 }} /></>
      }
    </button>
  )
}

// ---------------------------------------------------------------------------
// Terms & Conditions Modal
// ---------------------------------------------------------------------------

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
    title: '7. Changes to Terms',
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
          background: 'var(--white)',
          borderRadius: 'var(--radius-lg)',
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
          borderBottom: '1px solid var(--gray-200)',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <ScrollText style={{ width: 20, height: 20, color: 'var(--accent)', flexShrink: 0 }} />
            <div>
              <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: 'var(--gray-900)' }}>
                Terms &amp; Conditions
              </h2>
              <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--gray-500)' }}>
                ARIA Beta Programme — please read before continuing
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--gray-400)', padding: '0.25rem',
              borderRadius: '4px', display: 'flex', alignItems: 'center',
              transition: 'color 0.2s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--gray-900)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--gray-400)')}
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
                color: 'var(--gray-900)',
              }}>
                {section.title}
              </h3>
              <p style={{
                margin: 0, fontSize: '0.8125rem',
                color: 'var(--gray-600)', lineHeight: 1.65,
              }}>
                {section.body}
              </p>
            </div>
          ))}
        </div>

        {/* Footer actions */}
        <div style={{
          padding: '1rem 1.5rem',
          borderTop: '1px solid var(--gray-200)',
          display: 'flex', gap: '0.75rem',
          flexShrink: 0,
          background: 'var(--gray-50)',
        }}>
          <button
            onClick={onClose}
            style={{
              flex: 1,
              padding: '0.75rem',
              background: 'none',
              border: '2px solid var(--gray-200)',
              borderRadius: 8, cursor: 'pointer',
              fontSize: '0.9rem', fontWeight: 600,
              color: 'var(--gray-600)',
              transition: 'border-color 0.2s, color 0.2s',
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--gray-400)'; e.currentTarget.style.color = 'var(--gray-900)' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--gray-200)'; e.currentTarget.style.color = 'var(--gray-600)' }}
          >
            Decline
          </button>
          <button
            onClick={onAccept}
            style={{
              flex: 2,
              padding: '0.75rem',
              background: 'var(--primary)',
              border: 'none', borderRadius: 8,
              cursor: 'pointer',
              fontSize: '0.9rem', fontWeight: 600,
              color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem',
              transition: 'background 0.2s',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'var(--primary)')}
          >
            I Agree &amp; Continue <ArrowRight style={{ width: 16, height: 16, strokeWidth: 2.5 }} />
          </button>
        </div>
      </div>
    </div>
  )
}
