'use client'

/**
 * Password Reset page — handles the Supabase recovery redirect.
 *
 * Supabase fires a PASSWORD_RECOVERY event on onAuthStateChange when the user
 * arrives via a reset link (both implicit fragment flow and PKCE code flow).
 * Listening to that event is the only reliable cross-version way to get the
 * session — reading window.location.hash or useSearchParams() breaks in Next.js
 * App Router because fragments are stripped server-side and useSearchParams()
 * needs a Suspense boundary to work correctly.
 *
 * Flow:
 *   1. Page mounts → start listening to onAuthStateChange
 *   2. Supabase JS processes the URL (fragment or ?code=) automatically
 *   3. It fires PASSWORD_RECOVERY with a valid session → we store the token
 *   4. User fills in new password → POST to our backend with the token
 */

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight, Loader2, Eye, EyeOff, CheckCircle } from 'lucide-react'
import { createClient } from '@supabase/supabase-js'

// Create the Supabase client once at module level
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
)

// ─── helpers ──────────────────────────────────────────────────────────────────

function validatePassword(password: string): string | null {
  if (password.length < 6) return 'Password must be at least 6 characters.'
  if (!/[A-Z]/.test(password)) return 'Password must include at least one uppercase letter.'
  if (!/[0-9]/.test(password)) return 'Password must include at least one number.'
  if (!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?~`]/.test(password))
    return 'Password must include at least one special character.'
  return null
}

// ─── sub-components ───────────────────────────────────────────────────────────

const inputBase: React.CSSProperties = {
  width: '100%',
  padding: '0.875rem 1.125rem',
  fontFamily: 'var(--font-family)',
  fontSize: '1rem',
  borderWidth: 2,
  borderStyle: 'solid',
  borderColor: 'var(--gray-200, #e5e7eb)',
  borderRadius: 10,
  background: 'var(--gray-50, #f9fafb)',
  outline: 'none',
  boxSizing: 'border-box',
  transition: 'all 0.25s ease',
  color: 'var(--gray-900, #111827)',
}

function PasswordInput(
  props: React.InputHTMLAttributes<HTMLInputElement> & { hasError?: boolean },
) {
  const { hasError, ...rest } = props
  const [focused, setFocused] = useState(false)
  const [visible, setVisible] = useState(false)
  return (
    <div style={{ position: 'relative' }}>
      <input
        {...rest}
        type={visible ? 'text' : 'password'}
        style={{
          ...inputBase,
          paddingRight: '3rem',
          borderColor: hasError
            ? '#dc2626'
            : focused
            ? 'var(--accent, #7c2d3e)'
            : 'var(--gray-200, #e5e7eb)',
          background: focused ? '#fff' : 'var(--gray-50, #f9fafb)',
          boxShadow: focused
            ? '0 0 0 4px color-mix(in srgb, var(--accent, #7c2d3e) 10%, transparent)'
            : 'none',
        }}
        onFocus={e => { setFocused(true); rest.onFocus?.(e) }}
        onBlur={e => { setFocused(false); rest.onBlur?.(e) }}
      />
      <button
        type="button"
        tabIndex={-1}
        aria-label={visible ? 'Hide password' : 'Show password'}
        onClick={() => setVisible(v => !v)}
        style={{
          position: 'absolute', right: '0.875rem', top: '50%',
          transform: 'translateY(-50%)',
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--gray-400, #9ca3af)',
          display: 'flex', alignItems: 'center', padding: 0,
        }}
      >
        {visible
          ? <EyeOff style={{ width: 18, height: 18 }} />
          : <Eye    style={{ width: 18, height: 18 }} />}
      </button>
    </div>
  )
}

// ─── page ─────────────────────────────────────────────────────────────────────

type PageState = 'loading' | 'ready' | 'invalid' | 'success'

export default function ResetPasswordPage() {
  const router = useRouter()

  const [pageState,   setPageState]   = useState<PageState>('loading')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPw,   setConfirmPw]   = useState('')
  const [error,       setError]       = useState('')
  const [submitting,  setSubmitting]  = useState(false)

  // ── Resolve the recovery token from the URL ───────────────────────────────
  useEffect(() => {
    async function resolveToken() {
      const hash   = window.location.hash
      const search = window.location.search

      // ── Path A: implicit flow  (#access_token=...&type=recovery) ──────────
      if (hash) {
        const params = Object.fromEntries(
          new URLSearchParams(hash.startsWith('#') ? hash.slice(1) : hash),
        )
        if (params['access_token'] && params['type'] === 'recovery') {
          await supabase.auth.setSession({
            access_token:  params['access_token'],
            refresh_token: params['refresh_token'] ?? '',
          })
          window.history.replaceState(null, '', window.location.pathname)
          setPageState('ready')
          return
        }
      }

      // ── Path B: PKCE flow  (?code=...) ────────────────────────────────────
      const code = new URLSearchParams(search).get('code')
      if (code) {
        try {
          const { data, error: exchangeError } =
            await supabase.auth.exchangeCodeForSession(code)
          if (!exchangeError && data.session?.access_token) {
            window.history.replaceState(null, '', window.location.pathname)
            setPageState('ready')
            return
          }
          setError(exchangeError?.message ?? 'Reset link expired. Please request a new one.')
          setPageState('invalid')
        } catch {
          setError('Failed to validate the reset link. Please request a new one.')
          setPageState('invalid')
        }
        return
      }

      // ── Path C: onAuthStateChange fallback ────────────────────────────────
      const timeout = setTimeout(() => {
        setPageState(prev => {
          if (prev === 'loading') {
            setError(
              'The reset link appears to be missing its token. ' +
              'Make sure http://localhost:3000/auth/reset-password is added to ' +
              'Redirect URLs in your Supabase Dashboard (Authentication → URL Configuration).',
            )
            return 'invalid'
          }
          return prev
        })
      }, 5000)

      const { data: { subscription } } = supabase.auth.onAuthStateChange(
        (event, session) => {
          if (event === 'PASSWORD_RECOVERY' && session) {
            clearTimeout(timeout)
            window.history.replaceState(null, '', window.location.pathname)
            setPageState('ready')
          }
        },
      )

      return () => {
        clearTimeout(timeout)
        subscription.unsubscribe()
      }
    }

    resolveToken()
  }, [])

  // ── Submit new password directly via Supabase JS ──────────────────────────
  // The Supabase client already holds the recovery session (established when
  // it processed the URL fragment or exchanged the PKCE code). We call
  // supabase.auth.updateUser() directly — no backend round-trip needed.
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (newPassword !== confirmPw) {
      setError('Passwords do not match.')
      return
    }
    const pwError = validatePassword(newPassword)
    if (pwError) { setError(pwError); return }

    setSubmitting(true)
    try {
      const { error: updateError } = await supabase.auth.updateUser({
        password: newPassword,
      })
      if (updateError) {
        console.error('[reset-password] updateUser error:', updateError)
        setError(updateError.message || 'Failed to reset password. The link may have expired.')
        return
      }
      // Sign out so the recovery session doesn't linger
      await supabase.auth.signOut()
      setPageState('success')
    } catch (err) {
      console.error('[reset-password] unexpected error:', err)
      setError('Could not connect to Supabase. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--gray-50, #f9fafb)',
      padding: '1rem',
    }}>
      <div style={{
        width: '100%', maxWidth: 420,
        background: '#fff',
        borderRadius: 16,
        boxShadow: '0 20px 60px rgba(0,0,0,0.10)',
        padding: '2.5rem 2rem',
      }}>
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: '1.75rem' }}>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontSize: '2rem', fontWeight: 900, margin: 0,
            background: 'linear-gradient(135deg, var(--accent, #7c2d3e), var(--accent-warm, #a0413c))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}>
            ARIA
          </h1>
          <h2 style={{
            fontSize: '1.1rem', fontWeight: 700,
            color: 'var(--gray-900, #111827)',
            margin: '0.75rem 0 0.25rem',
          }}>
            {pageState === 'success' ? 'Password Updated' : 'Set New Password'}
          </h2>
          {pageState === 'ready' && (
            <p style={{ fontSize: '0.85rem', color: 'var(--gray-500, #6b7280)', margin: 0 }}>
              Choose a strong password for your account.
            </p>
          )}
          {pageState === 'loading' && (
            <p style={{ fontSize: '0.85rem', color: 'var(--gray-500, #6b7280)', margin: 0 }}>
              Verifying your reset link…
            </p>
          )}
        </div>

        {/* ── Loading ── */}
        {pageState === 'loading' && (
          <div style={{
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', gap: '0.75rem',
            padding: '1.5rem 0',
            color: 'var(--gray-500, #6b7280)',
          }}>
            <Loader2 style={{ width: 32, height: 32, animation: 'spin 1s linear infinite' }} />
          </div>
        )}

        {/* ── Invalid ── */}
        {pageState === 'invalid' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{
              padding: '1rem',
              background: '#fef2f2', border: '1px solid #fecaca',
              borderRadius: 8, color: '#dc2626',
              fontSize: '0.875rem', textAlign: 'center',
            }}>
              {error}
            </div>
            <button
              onClick={() => router.push('/?auth=login')}
              style={{
                width: '100%', padding: '0.875rem',
                background: 'var(--accent, #7c2d3e)', color: '#fff',
                fontWeight: 600, fontSize: '0.95rem',
                border: 'none', borderRadius: 8, cursor: 'pointer',
              }}
            >
              Request New Reset Link
            </button>
          </div>
        )}

        {/* ── Form ── */}
        {pageState === 'ready' && (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <label htmlFor="new-password" style={{
                fontSize: '0.9375rem', fontWeight: 600,
                color: 'var(--gray-900, #111827)',
              }}>
                New Password
              </label>
              <PasswordInput
                id="new-password"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                placeholder="Min 6 chars, uppercase, number, special"
                required minLength={6} autoComplete="new-password"
                hasError={!!error && error.toLowerCase().includes('password')}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--gray-500, #6b7280)', marginTop: '-0.25rem' }}>
                Must include uppercase, number, and special character
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <label htmlFor="confirm-password" style={{
                fontSize: '0.9375rem', fontWeight: 600,
                color: 'var(--gray-900, #111827)',
              }}>
                Confirm Password
              </label>
              <PasswordInput
                id="confirm-password"
                value={confirmPw}
                onChange={e => setConfirmPw(e.target.value)}
                placeholder="Repeat your new password"
                required autoComplete="new-password"
                hasError={!!error && error.toLowerCase().includes('match')}
              />
            </div>

            {error && (
              <div style={{
                background: '#fef2f2', border: '1px solid #fecaca',
                color: '#dc2626', borderRadius: 6,
                padding: '0.6rem 0.9rem', fontSize: '0.875rem',
              }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              style={{
                width: '100%',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                background: 'var(--accent, #7c2d3e)', color: '#fff',
                fontFamily: 'var(--font-family)',
                fontSize: '1.125rem', fontWeight: 600,
                padding: '1rem', border: 'none', borderRadius: 8,
                cursor: submitting ? 'not-allowed' : 'pointer',
                opacity: submitting ? 0.6 : 1,
                boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                marginTop: '0.5rem', transition: 'opacity 0.2s',
              }}
            >
              {submitting
                ? <Loader2 style={{ width: 20, height: 20, animation: 'spin 1s linear infinite' }} />
                : <>Reset Password <ArrowRight style={{ width: 20, height: 20, strokeWidth: 2.5 }} /></>}
            </button>
          </form>
        )}

        {/* ── Success ── */}
        {pageState === 'success' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', alignItems: 'center' }}>
            <div style={{
              width: 56, height: 56, borderRadius: '50%',
              background: '#f0fdf4',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <CheckCircle style={{ width: 30, height: 30, color: '#16a34a' }} />
            </div>
            <div style={{
              padding: '1rem',
              background: '#f0fdf4', border: '1px solid #bbf7d0',
              borderRadius: 8, color: '#166534',
              fontSize: '0.9rem', textAlign: 'center', width: '100%',
            }}>
              <strong>Password reset successfully!</strong>
              <p style={{ margin: '0.4rem 0 0', fontSize: '0.82rem' }}>
                You can now sign in with your new password.
              </p>
            </div>
            <button
              onClick={() => router.push('/?auth=login')}
              style={{
                width: '100%',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                background: 'var(--accent, #7c2d3e)', color: '#fff',
                fontWeight: 600, fontSize: '1rem',
                padding: '0.9rem', border: 'none', borderRadius: 8,
                cursor: 'pointer', boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
              }}
            >
              Go to Sign In <ArrowRight style={{ width: 18, height: 18 }} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
