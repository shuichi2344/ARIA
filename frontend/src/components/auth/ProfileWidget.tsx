'use client'

/**
 * ProfileWidget — exact port of the original web/index.html profile-widget.
 *
 * Behaviour:
 * - Only rendered when user is logged in (parent controls this)
 * - Shows email, Edit Business Profile, theme switcher, Sign Out
 * - Theme switching updates document.body.dataset.theme + localStorage
 * - Edit Business Profile navigates to /onboarding?edit=1
 * - Sign Out clears session and returns to landing
 */

import { useState, useEffect, useRef } from 'react'
import { UserCircle, Building2, Palette, LogOut, KeyRound } from 'lucide-react'

export interface AriaSession {
  id: string
  email: string
  created_at: string
}

interface Props {
  session: AriaSession
  onLogout: () => void
  onEditProfile: () => void
}

const THEMES = [
  { key: 'burgundy', label: 'Cyan & Pink',       gradient: 'linear-gradient(135deg,#06b6d4 0%,#ec4899 100%)' },
  { key: 'navy',     label: 'Navy & Amber',       gradient: 'linear-gradient(135deg,#1e3a8a 0%,#f59e0b 100%)' },
  { key: 'teal',     label: 'Rose & Lavender',    gradient: 'linear-gradient(135deg,#db2777 0%,#a78bfa 100%)' },
  { key: 'plum',     label: 'Coral & Periwinkle', gradient: 'linear-gradient(135deg,#f43f5e 0%,#818cf8 100%)' },
]

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export default function ProfileWidget({ session, onLogout, onEditProfile }: Props) {
  const [open, setOpen]             = useState(false)
  const [activeTheme, setActiveTheme] = useState('burgundy')
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Hydrate saved theme on mount
  useEffect(() => {
    const saved = localStorage.getItem('aria-theme') || 'burgundy'
    setActiveTheme(saved)
    document.body.dataset.theme = saved
  }, [])

  // Close dropdown on outside click — same as original document.addEventListener('click')
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  /** Matches original setTheme() */
  function applyTheme(key: string) {
    setActiveTheme(key)
    document.body.dataset.theme = key
    localStorage.setItem('aria-theme', key)
  }

  return (
    /* .profile-widget */
    <div ref={ref} style={{ position: 'relative' }}>

      {/* .profile-icon-btn */}
      <button
        onClick={() => setOpen(o => !o)}
        aria-label="Account menu"
        style={{
          background: 'var(--white)',
          borderWidth: '2px',
          borderStyle: 'solid',
          borderColor: 'var(--gray-200)',
          borderRadius: '50%',
          width: 42, height: 42,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          transition: 'border-color 0.2s, box-shadow 0.2s',
        }}
        onMouseEnter={e => {
          e.currentTarget.style.borderColor = 'var(--accent)'
          e.currentTarget.style.boxShadow   = '0 4px 16px rgba(0,0,0,0.15)'
        }}
        onMouseLeave={e => {
          e.currentTarget.style.borderColor = 'var(--gray-200)'
          e.currentTarget.style.boxShadow   = '0 2px 8px rgba(0,0,0,0.1)'
        }}
      >
        <UserCircle style={{ width: 22, height: 22, color: 'var(--gray-600)' }} />
      </button>

      {/* .profile-dropdown */}
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 0.5rem)', right: 0,
          background: 'var(--white)',
          border: '1px solid var(--gray-200)',
          borderRadius: 'var(--radius-md)',
          boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
          minWidth: 220,
          overflow: 'hidden',
          animation: 'slideUp 0.15s ease',
        }}>

          {/* .profile-dropdown-header */}
          <div style={{ padding: '0.75rem 1rem', background: 'var(--gray-50)' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--gray-600)', wordBreak: 'break-all' }}>
              {session.email}
            </span>
          </div>

          <Divider />

          {/* Edit Business Profile — matches openAccountSettings() → openEditBusinessProfile() */}
          <DropdownBtn
            icon={<Building2 style={{ width: 16, height: 16 }} />}
            onClick={() => { setOpen(false); onEditProfile() }}
          >
            Edit Business Profile
          </DropdownBtn>

          {/* Update Profile — change password */}
          <DropdownBtn
            icon={<KeyRound style={{ width: 16, height: 16 }} />}
            onClick={() => { setOpen(false); setShowPasswordModal(true) }}
          >
            Update Profile
          </DropdownBtn>

          <Divider />

          {/* .profile-dropdown-theme */}
          <div style={{ padding: '0.6rem 1rem 0.75rem' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.4rem',
              fontSize: '0.75rem', fontWeight: 600,
              color: 'var(--gray-600)',
              textTransform: 'uppercase', letterSpacing: '0.04em',
              marginBottom: '0.5rem',
            }}>
              <Palette style={{ width: 14, height: 14 }} />
              Theme
            </div>

            {/* .theme-picker-row */}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {THEMES.map(t => (
                <button
                  key={t.key}
                  title={t.label}
                  onClick={() => applyTheme(t.key)}
                  style={{
                    width: 28, height: 28,
                    borderRadius: '50%',
                    background: t.gradient,
                    /* .theme-swatch.active uses border-color: var(--text-primary) */
                    border: activeTheme === t.key
                      ? '2.5px solid var(--primary)'
                      : '2.5px solid transparent',
                    cursor: 'pointer',
                    transform: activeTheme === t.key ? 'scale(1.1)' : 'scale(1)',
                    transition: 'transform 0.15s, border-color 0.15s',
                    outline: 'none',
                    flexShrink: 0,
                  }}
                />
              ))}
            </div>
          </div>

          <Divider />

          {/* Sign Out — matches handleLogout() */}
          <DropdownBtn
            icon={<LogOut style={{ width: 16, height: 16 }} />}
            onClick={() => { setOpen(false); onLogout() }}
            danger
          >
            Sign Out
          </DropdownBtn>
        </div>
      )}

      {/* Password Change Modal */}
      {showPasswordModal && (
        <ChangePasswordModal
          userId={session.id}
          onClose={() => setShowPasswordModal(false)}
        />
      )}
    </div>
  )
}

/* ── helpers ── */

function ChangePasswordModal({ userId, onClose }: { userId: string; onClose: () => void }) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (newPassword.length < 6) {
      setError('New password must be at least 6 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('New passwords do not match.')
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/auth/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          current_password: currentPassword,
          new_password: newPassword,
        }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || 'Failed to change password.')
        return
      }

      setSuccess(true)
      setTimeout(onClose, 1500)
    } catch {
      setError('Could not connect to server. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        animation: 'fadeIn 0.15s ease',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--white)',
          borderRadius: 'var(--radius-md, 12px)',
          boxShadow: '0 16px 48px rgba(0,0,0,0.18)',
          width: '100%', maxWidth: 400,
          padding: '2rem',
          animation: 'slideUp 0.2s ease',
        }}
      >
        <h3 style={{
          margin: '0 0 0.25rem',
          fontSize: '1.1rem',
          fontWeight: 700,
          color: 'var(--gray-900)',
        }}>
          Update Password
        </h3>
        <p style={{ margin: '0 0 1.5rem', fontSize: '0.82rem', color: 'var(--gray-500)' }}>
          Enter your current password and choose a new one.
        </p>

        {success ? (
          <div style={{
            padding: '1rem',
            background: '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: 8,
            color: '#166534',
            fontSize: '0.875rem',
            fontWeight: 500,
            textAlign: 'center',
          }}>
            ✓ Password updated successfully!
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <PasswordField
              label="Current Password"
              value={currentPassword}
              onChange={setCurrentPassword}
              placeholder="Enter current password"
            />
            <PasswordField
              label="New Password"
              value={newPassword}
              onChange={setNewPassword}
              placeholder="At least 6 characters"
            />
            <PasswordField
              label="Confirm New Password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              placeholder="Re-enter new password"
            />

            {error && (
              <div style={{
                padding: '0.6rem 0.75rem',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: 6,
                color: '#dc2626',
                fontSize: '0.8rem',
              }}>
                {error}
              </div>
            )}

            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  flex: 1, padding: '0.7rem',
                  background: 'var(--gray-100)',
                  border: '1px solid var(--gray-200)',
                  borderRadius: 8,
                  fontSize: '0.85rem', fontWeight: 600,
                  color: 'var(--gray-700)',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                style={{
                  flex: 1, padding: '0.7rem',
                  background: 'var(--accent, #7c2d3e)',
                  border: 'none',
                  borderRadius: 8,
                  fontSize: '0.85rem', fontWeight: 600,
                  color: '#fff',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.7 : 1,
                }}
              >
                {loading ? 'Updating...' : 'Update Password'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function PasswordField({ label, value, onChange, placeholder }: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder: string
}) {
  return (
    <div>
      <label style={{
        display: 'block',
        fontSize: '0.78rem', fontWeight: 600,
        color: 'var(--gray-700)',
        marginBottom: '0.3rem',
      }}>
        {label}
      </label>
      <input
        type="password"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        required
        style={{
          width: '100%',
          padding: '0.6rem 0.75rem',
          border: '1.5px solid var(--gray-200)',
          borderRadius: 8,
          fontSize: '0.875rem',
          outline: 'none',
          transition: 'border-color 0.15s',
          fontFamily: 'var(--font-family)',
          boxSizing: 'border-box',
        }}
        onFocus={e => e.currentTarget.style.borderColor = 'var(--accent, #7c2d3e)'}
        onBlur={e => e.currentTarget.style.borderColor = 'var(--gray-200)'}
      />
    </div>
  )
}

function Divider() {
  return <div style={{ height: 1, background: 'var(--gray-200)' }} />
}

function DropdownBtn({
  icon, children, onClick, danger = false,
}: {
  icon: React.ReactNode
  children: React.ReactNode
  onClick: () => void
  danger?: boolean
}) {
  const [hov, setHov] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: '0.6rem',
        width: '100%',
        background: hov ? (danger ? '#fef2f2' : 'var(--gray-50)') : 'none',
        border: 'none',
        padding: '0.75rem 1rem',
        fontSize: '0.875rem', fontWeight: 500,
        color: danger ? '#dc2626' : 'var(--gray-900)',
        cursor: 'pointer', textAlign: 'left',
        transition: 'background 0.15s',
        fontFamily: 'var(--font-family)',
      }}
    >
      {icon}
      {children}
    </button>
  )
}
