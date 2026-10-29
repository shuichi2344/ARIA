'use client'

/**
 * Session context — manages Supabase Auth JWTs with automatic token refresh.
 *
 * Token lifecycle:
 * - Supabase JWTs expire after 1 hour
 * - We silently refresh the access_token using the refresh_token before it expires
 * - Token refresh runs every 45 minutes (before the 1-hour expiry)
 */

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'

export interface AriaSession {
  id: string
  email: string
  created_at: string
  access_token: string
  refresh_token?: string
  email_confirmed?: boolean
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
const TOKEN_REFRESH_INTERVAL_MS = 45 * 60 * 1000  // 45 min — before 1-hr JWT expiry

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
  // new access_token. Called automatically every 45 minutes.
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

  // ─── Periodic token refresh (every 45 min) ────────────────────────────────
  useEffect(() => {
    if (!session?.refresh_token) return

    const interval = setInterval(() => {
      refreshToken(session)
    }, TOKEN_REFRESH_INTERVAL_MS)

    return () => clearInterval(interval)
  }, [session?.refresh_token, refreshToken])

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
