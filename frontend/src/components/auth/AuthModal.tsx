'use client'

import { useState } from 'react'
import { X, ArrowRight, Loader2 } from 'lucide-react'

interface Props {
  defaultTab?: 'login' | 'register'
  onClose: () => void
  onSuccess: (user: { id: string; email: string; created_at: string }) => void
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
      if (!res.ok) { setLoginError(data.detail || 'Login failed.'); return }
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
    // Validate password strength
    const pwError = validatePassword(regPassword)
    if (pwError) { setRegError(pwError); return }
    setRegLoading(true)
    try {
      const res  = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: regEmail.trim(), password: regPassword }),
      })
      const data = await res.json()
      if (!res.ok) { setRegError(data.detail || 'Registration failed.'); return }
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
              <AuthInput
                type="password" value={loginPassword}
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
              <AuthInput
                type="password" value={regPassword}
                onChange={e => setRegPassword(e.target.value)}
                placeholder="Min 6 chars, uppercase, number, special" required minLength={6} autoComplete="new-password"
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--gray-500)', marginTop: '-0.25rem' }}>
                Must include uppercase, number, and special character
              </span>
            </FormField>
            <FormField label="Confirm Password">
              <AuthInput
                type="password" value={regConfirm}
                onChange={e => setRegConfirm(e.target.value)}
                placeholder="Repeat your password" required autoComplete="new-password"
              />
            </FormField>
            {regError && <AuthError>{regError}</AuthError>}
            <SubmitBtn loading={regLoading}>Create Account</SubmitBtn>
          </form>
        )}
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
