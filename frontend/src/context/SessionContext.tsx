'use client'

/**
 * Session context — mirrors the original app.js localStorage-based auth.
 * Talks to the FastAPI backend (/api/auth/*), NOT Supabase Auth.
 */

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

export interface AriaSession {
  id: string
  email: string
  created_at: string
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

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<AriaSession | null>(null)

  // Hydrate from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem('aria_session')
      if (raw) setSessionState(JSON.parse(raw))
    } catch {}
  }, [])

  function setSession(s: AriaSession | null) {
    setSessionState(s)
    if (s) localStorage.setItem('aria_session', JSON.stringify(s))
    else localStorage.removeItem('aria_session')
  }

  function logout() {
    setSession(null)
    localStorage.removeItem('aria_profile')
    localStorage.removeItem('aria_profile_id')
  }

  return (
    <SessionContext.Provider value={{ session, setSession, logout }}>
      {children}
    </SessionContext.Provider>
  )
}

export const useSession = () => useContext(SessionContext)
