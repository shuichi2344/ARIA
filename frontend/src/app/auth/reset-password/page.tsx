'use client'

import { useState, useEffect } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { ArrowRight, Loader2 } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

function validatePassword(password: string): string | null {
  if (password.length < 6) return 'Password must be at least 6 characters.'
  if (!/[A-Z]/.test(password)) return 'Password must include at least one uppercase letter.'
  if (!/[0-9]/.test(password)) return 'Password must include at least one number.'
  if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?~`]/.test(password)) return 'Password must include at least one special character.'
  return null
}

export default function ResetPasswordPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const token = searchParams.get('token')

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!token) {
      setError('Invalid reset link. No token provided.')
    }
  }, [token])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    const pwError = validatePassword(newPassword)
    if (pwError) {
      setError(pwError)
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: newPassword }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Failed to reset password.')
        return
      }
      setSuccess(true)
      setTimeout(() => router.push('/'), 3000)
    } catch {
      setError('Could not connect to server. Please try again.')
    } finally {
      setLoading(false)
    }
  }

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
        boxShadow: '0 20px 60px rgba(0,0,0,0.1)',
        padding: '2.5rem 2rem',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
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
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1a1a2e', margin: '0.75rem 0 0.25rem' }}>
            Set New Password
          </h2>
          <p style={{ fontSize: '0.85rem', color: '#666', margin: 0 }}>
            Choose a strong password for your account.
          </p>
        </div>

        {success ? (
          <div style={{
            padding: '1.25rem', background: '#f0fdf4', border: '1px solid #bbf7d0',
            borderRadius: 8, color: '#166534', fontSize: '0.9rem', textAlign: 'center',
          }}>
            <strong>✓ Password reset successfully!</strong>
            <p style={{ margin: '0.5rem 0 0', fontSize: '0.82rem' }}>
              Redirecting to login...
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#1a1a2e' }}>
                New Password
              </label>
              <input
                type="password"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                placeholder="Min 6 chars, uppercase, number, special"
                required
                minLength={6}
                autoComplete="new-password"
                style={{
                  width: '100%', padding: '0.875rem 1.125rem',
                  fontSize: '1rem', border: '2px solid #e5e7eb',
                  borderRadius: 10, background: '#f9fafb', outline: 'none',
                }}
              />
              <span style={{ fontSize: '0.72rem', color: '#888' }}>
                Must include uppercase, number, and special character
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#1a1a2e' }}>
                Confirm Password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="Repeat your new password"
                required
                autoComplete="new-password"
                style={{
                  width: '100%', padding: '0.875rem 1.125rem',
                  fontSize: '1rem', border: '2px solid #e5e7eb',
                  borderRadius: 10, background: '#f9fafb', outline: 'none',
                }}
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
              disabled={loading || !token}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                background: 'var(--accent, #7c2d3e)', color: '#fff',
                fontSize: '1.125rem', fontWeight: 600,
                padding: '1rem', border: 'none', borderRadius: 8,
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1,
                boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                marginTop: '0.5rem',
              }}
            >
              {loading
                ? <Loader2 style={{ width: 20, height: 20, animation: 'spin 1s linear infinite' }} />
                : <>Reset Password <ArrowRight style={{ width: 20, height: 20 }} /></>
              }
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
