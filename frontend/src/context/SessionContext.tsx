'use client'

/**
 * Session context — manages Supabase Auth JWTs with automatic token refresh.
 *
 * Token lifecycle:
 * - Supabase JWTs expire after 1 hour (this is separate from the 7-day beta period)
 * - We silently refresh the access_token using the refresh_token before it expires
 * - Token refresh runs every 45 minutes (before the 1-hour expiry)
 * - Beta access expiry (7 days) is checked separately via /api/auth/me every 60s
 * - A 401 on /api/auth/me triggers a token refresh attempt, NOT a logout
 * - Only a 403 BETA_ACCESS_EXPIRED causes an actual sign-out
 */

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'

export interface AriaSession {
  id: string
  email: string
  created_at: string
  access_token: string
  refresh_token?: string
  email_confirmed?: boolean
  beta_access_expires_at?: string
}

interface SessionContextValue {
  session: AriaSession | null
  setSession: (s: AriaSession | null) => void
  logout: () => void
}

const SessionContext = createContext<SessionContextValue>({
  session: null,
  setSession: () => {},
  logout: () => {},
})

const SUPABASE_URL  = process.env.NEXT_PUBLIC_SUPABASE_URL  ?? ''
const SUPABASE_KEY  = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? ''
const API_BASE      = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

const TOKEN_REFRESH_INTERVAL_MS = 45 * 60 * 1000  // 45 min — before 1-hr JWT expiry
const BETA_CHECK_INTERVAL_MS    = 60 * 1000        // 60 s — beta access check

function clearAllLocalStorage() {
  localStorage.removeItem('aria_session')
  localStorage.removeItem('aria_profile')
  localStorage.removeItem('aria_profile_id')
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<AriaSession | null>(null)

  // ─── Hydrate from localStorage on mount ───────────────────────────────────
  useEffect(() => {
    try {
      const raw = localStorage.getItem('aria_session')
      if (raw) setSessionState(JSON.parse(raw) as AriaSession)
    } catch {
      clearAllLocalStorage()
    }
  }, [])

  // ─── Token refresh ────────────────────────────────────────────────────────
  // Uses Supabase's /auth/v1/token?grant_type=refresh_token endpoint to get a
  // new access_token. Called automatically every 45 min and whenever a 401 is
  // received from the beta-access check.
  const refreshToken = useCallback(async (currentSession: AriaSession): Promise<AriaSession | null> => {
    if (!currentSession.refresh_token) return null

    try {
      const res = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'apikey': SUPABASE_KEY,
        },
        body: JSON.stringify({ refresh_token: currentSession.refresh_token }),
      })

      if (!res.ok) {
        // Refresh token itself is invalid/revoked — genuine sign-out needed
        console.log('[Session] Refresh token invalid, signing out')
        clearAllLocalStorage()
        setSessionState(null)
        return null
      }

      const body = await res.json()
      const newSession: AriaSession = {
        ...currentSession,
        access_token:  body.access_token,
        refresh_token: body.refresh_token ?? currentSession.refresh_token,
      }

      // Persist updated tokens
      localStorage.setItem('aria_session', JSON.stringify(newSession))
      setSessionState(newSession)
      console.log('[Session] Token refreshed successfully')
      return newSession
    } catch {
      // Network error — keep existing session, will retry next interval
      return null
    }
  }, [])

  // ─── Beta access check ────────────────────────────────────────────────────
  // Only sign out on 403 BETA_ACCESS_EXPIRED.
  // On 401 (expired JWT or invalid alg), refresh token silently — do NOT sign out.
  // The invite token from setup-password uses a different alg and will 401 here —
  // that's expected and we just skip it until the user logs in properly.
  const checkBetaAccess = useCallback(async (currentSession: AriaSession) => {
    if (!currentSession.access_token) return

    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${currentSession.access_token}` },
      })

      if (res.ok) {
        const user = await res.json()
        const expiresAt = user.beta_access_expires_at as string | null | undefined
        if (expiresAt && expiresAt !== currentSession.beta_access_expires_at) {
          const updatedSession = { ...currentSession, beta_access_expires_at: expiresAt }
          localStorage.setItem('aria_session', JSON.stringify(updatedSession))
          setSessionState(current => current?.id === updatedSession.id
            ? { ...current, beta_access_expires_at: expiresAt }
            : current)
        }
        return
      }

      if (res.status === 403) {
        const text = await res.text().catch(() => '')
        if (text.includes('BETA_ACCESS_EXPIRED')) {
          console.log('[Session] Beta access expired — signing out')
          // A full-page navigation is already underway; leave React state alone
          // so the dashboard's generic null-session redirect cannot race it.
          let savedSession: AriaSession | null = null
          try {
            const saved = localStorage.getItem('aria_session')
            savedSession = saved ? JSON.parse(saved) as AriaSession : null
          } catch { /* ignore malformed or already-cleared session data */ }
          if (!savedSession || savedSession.access_token !== currentSession.access_token) return
          clearAllLocalStorage()
          window.location.replace('/auth/error?reason=beta_expired')
        }
        return
      }

      if (res.status === 401) {
        // Could be: expired JWT or invite token with wrong alg
        // Try to refresh — if no refresh token, skip silently (user needs to re-login)
        if (currentSession.refresh_token) {
          console.log('[Session] JWT invalid, attempting refresh...')
          await refreshToken(currentSession)
        }
        // Do NOT sign out — let user re-login naturally
      }
    } catch {
      // Network error — skip silently
    }
  }, [refreshToken])

  // ─── Periodic token refresh (every 45 min) ────────────────────────────────
  useEffect(() => {
    if (!session?.refresh_token) return

    const interval = setInterval(() => {
      refreshToken(session)
    }, TOKEN_REFRESH_INTERVAL_MS)

    return () => clearInterval(interval)
  }, [session?.refresh_token, refreshToken])

  // ─── Periodic beta access check (every 60 s) ──────────────────────────────
  useEffect(() => {
    if (!session?.access_token) return

    const checkSavedSession = () => {
      try {
        const raw = localStorage.getItem('aria_session')
        if (raw) checkBetaAccess(JSON.parse(raw) as AriaSession)
      } catch { /* skip malformed local session data */ }
    }

    // Check immediately and again at the recorded expiry. The server remains
    // authoritative; the timer just ensures an active tab checks promptly.
    checkSavedSession()
    const expiryTime = session.beta_access_expires_at
      ? Date.parse(session.beta_access_expires_at)
      : Number.NaN
    const expiryTimer = Number.isFinite(expiryTime)
      ? window.setTimeout(checkSavedSession, Math.max(0, expiryTime - Date.now()) + 250)
      : undefined

    const interval = setInterval(() => {
      checkSavedSession()
    }, BETA_CHECK_INTERVAL_MS)

    const checkWhenActive = () => {
      if (document.visibilityState === 'visible') checkSavedSession()
    }
    document.addEventListener('visibilitychange', checkWhenActive)
    window.addEventListener('focus', checkWhenActive)

    return () => {
      clearInterval(interval)
      if (expiryTimer !== undefined) clearTimeout(expiryTimer)
      document.removeEventListener('visibilitychange', checkWhenActive)
      window.removeEventListener('focus', checkWhenActive)
    }
  }, [session?.access_token, session?.beta_access_expires_at, checkBetaAccess])

  // ─── setSession / logout ──────────────────────────────────────────────────
  function setSession(s: AriaSession | null) {
    setSessionState(s)
    if (s) localStorage.setItem('aria_session', JSON.stringify(s))
    else clearAllLocalStorage()
  }

  function logout() {
    clearAllLocalStorage()
    setSessionState(null)
  }

  return (
    <SessionContext.Provider value={{ session, setSession, logout }}>
      {children}
    </SessionContext.Provider>
  )
}

export const useSession = () => useContext(SessionContext)
