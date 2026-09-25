'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Brain, BarChart3, Zap } from 'lucide-react'
import AuthModal from '@/components/auth/AuthModal'
import ProfileWidget from '@/components/auth/ProfileWidget'
import { useSession } from '@/context/SessionContext'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export default function LandingPage() {
  const router = useRouter()
  const { session, setSession, logout } = useSession()
  const [authOpen, setAuthOpen] = useState(false)
  const [authTab,  setAuthTab]  = useState<'login' | 'register'>('login')
  const [navigating, setNavigating] = useState(false)
  
  // Check for auth errors in URL
  const [authError, setAuthError] = useState<string | null>(null)
  
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const error = params.get('error')
    if (error) {
      setAuthError(decodeURIComponent(error))
    }
  }, [])

  // Apply saved theme on every mount — same as initThemeSwitcher() / applyTheme()
  useEffect(() => {
    const saved = localStorage.getItem('aria-theme') || 'burgundy'
    document.body.dataset.theme = saved
  }, [])

  // Handle auth-related query params and URL hash
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const hash = window.location.hash
    
    // Check for error parameter (from Supabase or callback failures)
    const error = params.get('error')
    const errorDescription = params.get('error_description')
    
    // Also check hash for errors (Supabase sometimes puts errors in hash)
    const hashParams = new URLSearchParams(hash.substring(1))
    const hashError = hashParams.get('error')
    const hashErrorCode = hashParams.get('error_code')
    const hashErrorDesc = hashParams.get('error_description')
    
    // Check if it's an expired invite error
    const isExpiredInvite = 
      hashErrorCode === 'otp_expired' ||
      hashError === 'access_denied' ||
      hashErrorDesc?.toLowerCase().includes('expired') ||
      hashErrorDesc?.toLowerCase().includes('invalid')
    
    if (hashError && isExpiredInvite) {
      console.log('[Home] Expired invitation detected in hash, redirecting to error page')
      const errorParams = new URLSearchParams({
        error: hashError,
        error_code: hashErrorCode || '',
        error_description: hashErrorDesc || hashError
      })
      router.push(`/auth/error?${errorParams.toString()}`)
      return
    }
    
    if (error) {
      console.log('[Home] Auth error detected:', error, errorDescription)
      // Don't redirect - let the page show the error
      // The error will be displayed by checking the URL params below
      return
    }
    
    // Parse hash parameters (Supabase auth tokens come in the hash)
    const hasAccessToken = hashParams.has('access_token')
    const type = params.get('type') || hashParams.get('type')
    
    console.log('[Home] Auth check:', { 
      hasToken: params.has('token_hash') || hasAccessToken,
      type,
      hash: hash.substring(0, 50) 
    })
    
    // Check for Supabase auth tokens
    if (params.has('token_hash') || hasAccessToken) {
      console.log('[Home] Supabase auth token detected, type:', type)
      
      // Redirect to appropriate page based on type, preserving the hash
      if (type === 'invite') {
        console.log('[Home] Invitation detected, redirecting to setup-password')
        router.push(`/auth/setup-password${window.location.search}${hash}`)
        return
      } else if (type === 'recovery') {
        console.log('[Home] Password recovery detected, redirecting to reset-password')
        router.push(`/auth/reset-password${window.location.search}${hash}`)
        return
      } else if (hasAccessToken) {
        // Generic access token - redirect to setup-password as fallback
        console.log('[Home] Generic access token, redirecting to setup-password')
        router.push(`/auth/setup-password${window.location.search}${hash}`)
        return
      }
    }
    
    // Handle ?auth= query param (from /auth/login redirect)
    const authParam = params.get('auth')
    if (authParam === 'login' || authParam === 'register') {
      setAuthTab(authParam)
      setAuthOpen(true)
      window.history.replaceState({}, '', '/')
    }
  }, [router])

  // Scroll animations — same as initScrollAnimations()
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
          setTimeout(() => entry.target.classList.add('visible'), i * 150)
          observer.unobserve(entry.target)
        }
      }),
      { threshold: 0.15, rootMargin: '0px 0px -80px 0px' }
    )
    document.querySelectorAll('.feature-card, .step-card').forEach(el => observer.observe(el))
    return () => observer.disconnect()
  }, [])

  /**
   * After login/register — same as routeAfterAuth():
   * 1. Show profile widget (set session)
   * 2. Check DB for existing business profile
   * 3. If found → go to dashboard
   * 4. If not → go to onboarding
   */
  async function routeAfterAuth(user: {
    id: string
    email: string
    created_at: string
    access_token: string
    refresh_token?: string
    email_confirmed?: boolean
    beta_access_expires_at?: string
  }) {
    console.log('[Auth] routeAfterAuth called for user:', user.email)
    setAuthError(null)
    setSession(user)
    setAuthOpen(false)
    setNavigating(true)

    // IMPORTANT: Save session to localStorage immediately so it's available on next page
    try {
      localStorage.setItem('aria_session', JSON.stringify(user))
      console.log('[Auth] Session saved to localStorage')
    } catch (err) {
      console.error('[Auth] Failed to save session to localStorage:', err)
    }

    let confirmedNoProfile = false
    try {
      console.log('[Auth] Checking for existing business profile...')
      const controller = new AbortController()
      const timeout = setTimeout(() => {
        console.warn('[Auth] Profile check timed out after 5s')
        controller.abort()
      }, 5000)
      
      const res = await fetch(`${API_BASE}/api/business/profile/user/${user.id}`, {
        signal: controller.signal,
        headers: {
          'Authorization': `Bearer ${user.access_token}`,
          'Content-Type': 'application/json',
        },
      })
      clearTimeout(timeout)
      
      console.log('[Auth] Profile check response status:', res.status)
      
      if (res.ok) {
        const profile = await res.json()
        console.log('[Auth] Profile data received:', { id: profile?.id, name: profile?.business_name })
        if (profile?.id) {
          localStorage.setItem('aria_profile',    JSON.stringify(profile))
          localStorage.setItem('aria_profile_id', profile.id)
          console.log('[Auth] Profile saved to localStorage, redirecting to dashboard')
          // Give a tiny delay to ensure localStorage is written before navigation
          await new Promise(resolve => setTimeout(resolve, 100))
          router.push('/dashboard')
          return
        } else {
          console.warn('[Auth] Profile response OK but no profile.id found:', profile)
          setAuthError('Your account was verified, but ARIA could not load your saved business profile. Please select Get Started to retry.')
          return
        }
      } else if (res.status === 404) {
        const errorBody = await res.json().catch(() => null)
        if (errorBody?.detail === 'No profile found for this user') {
          // Only this explicit response means the account genuinely has no profile.
          console.log('[Auth] No profile found - redirecting to onboarding')
          confirmedNoProfile = true
        } else {
          console.warn('[Auth] Profile endpoint returned an unexpected 404:', errorBody)
          setAuthError('ARIA could not verify your saved business profile. Your existing data has not been changed. Please select Get Started to retry.')
          return
        }
      } else {
        const errorText = await res.text().catch(() => '')
        console.warn('[Auth] Profile check failed with status:', res.status, errorText)
        setAuthError('ARIA could not load your saved business profile. Your existing data has not been changed. Please select Get Started to retry.')
        return
      }
    } catch (err) {
      if (err instanceof Error) {
        console.warn('[Auth] Profile check error:', err.message)
      } else {
        console.warn('[Auth] Profile check failed with unknown error')
      }
      setAuthError('ARIA could not reach the server to load your saved business profile. Your existing data has not been changed. Please select Get Started to retry.')
      return
    } finally {
      setNavigating(false)
    }

    // New users enter onboarding only after the API explicitly confirms no profile exists.
    if (!confirmedNoProfile) return
    console.log('[Auth] Redirecting to onboarding')
    // Give a tiny delay to ensure localStorage is written before navigation
    await new Promise(resolve => setTimeout(resolve, 100))
    router.push('/onboarding')
  }

  /** "Get Started" — same as startOnboarding() */
  function startOnboarding() {
    if (!session?.id) {
      setAuthTab('register')
      setAuthOpen(true)
      return
    }
    routeAfterAuth(session)
  }

  /**
   * Edit Business Profile — same as openEditBusinessProfile():
   * navigates to onboarding with ?edit=1 so the form can pre-fill
   */
  function handleEditProfile() {
    router.push('/onboarding?edit=1')
  }

  /** Sign Out — same as handleLogout() */
  function handleLogout() {
    logout()
    // Stay on landing (widget hides because session is cleared)
  }

  return (
    <>
      {/* Profile widget — only shown when logged in, fixed top-right */}
      {session && (
        <div style={{ position: 'fixed', top: '1rem', right: '1rem', zIndex: 900 }}>
          <ProfileWidget
            session={session}
            onLogout={handleLogout}
            onEditProfile={handleEditProfile}
          />
        </div>
      )}

      {/* Auth error notification */}
      {authError && (
        <div style={{
          position: 'fixed',
          top: '1rem',
          left: '50%',
          transform: 'translateX(-50%)',
          maxWidth: '500px',
          width: 'calc(100% - 2rem)',
          background: '#fef2f2',
          border: '1px solid #fecaca',
          borderRadius: '12px',
          padding: '1rem 1.25rem',
          boxShadow: '0 4px 12px rgba(220, 38, 38, 0.15)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'flex-start',
          gap: '0.75rem'
        }}>
          <div style={{ 
            background: '#fee2e2', 
            borderRadius: '50%', 
            padding: '0.5rem', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            flexShrink: 0
          }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          </div>
          <div style={{ flex: 1 }}>
            <h3 style={{ margin: '0 0 0.25rem', fontSize: '0.9375rem', fontWeight: 600, color: '#991b1b' }}>
              Authentication Error
            </h3>
            <p style={{ margin: 0, fontSize: '0.8125rem', color: '#dc2626', lineHeight: 1.5 }}>
              {authError}
            </p>
          </div>
          <button
            onClick={() => {
              setAuthError(null)
              window.history.replaceState({}, '', '/')
            }}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#dc2626',
              padding: '0.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '4px',
              transition: 'background 0.2s',
              flexShrink: 0
            }}
            onMouseEnter={e => (e.currentTarget.style.background = '#fee2e2')}
            onMouseLeave={e => (e.currentTarget.style.background = 'none')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      )}

      {/* Auth modal overlay */}
      {authOpen && (
        <AuthModal
          defaultTab={authTab}
          onClose={() => setAuthOpen(false)}
          onSuccess={routeAfterAuth}
        />
      )}

      <main className="landing-page">
        {/* ── Hero ── */}
        <section className="hero">
          <div className="hero-content">
            <h1 className="hero-title" data-text="ARIA">
              {['A', 'R', 'I', 'A'].map((l, i) => (
                <span
                  key={i}
                  className="hero-letter"
                  style={{ '--i': i } as React.CSSProperties}
                >
                  {l}
                </span>
              ))}
            </h1>
            <p className="hero-subtitle">Agentic Retail Intelligence &amp; Analytics</p>
            <p className="hero-description">
              Predict customer behavior before it happens. ARIA uses AI-powered agent-based
              simulations to help Malaysian SMEs understand how customers will react to business
              decisions.
            </p>
            <button className="btn-cta" onClick={startOnboarding} disabled={navigating}>
              <span>{navigating ? 'Loading...' : 'Get Started'}</span>
              {!navigating && (
                <svg className="icon-btn" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              )}
            </button>
          </div>
        </section>

        {/* ── Features ── */}
        <section className="features">
          <h2>Why Choose <span className="cursive-accent">ARIA</span>?</h2>
          <div className="feature-grid">
            {[
              {
                Icon: Brain,
                title: 'AI-Powered Agents',
                desc: 'Each virtual customer is an intelligent agent with unique demographics, preferences, and decision-making patterns based on real Malaysian data.',
              },
              {
                Icon: BarChart3,
                title: 'Real Demographics',
                desc: 'Built on actual demographic data from DOSM (Department of Statistics Malaysia), ensuring your simulations reflect real population distributions.',
              },
              {
                Icon: Zap,
                title: 'Scenario Testing',
                desc: 'Test price changes, new products, competitor actions, and marketing campaigns before implementing them in the real world.',
              },
            ].map(({ Icon, title, desc }) => (
              <div key={title} className="feature-card">
                <div className="feature-icon">
                  <Icon className="icon-feature" strokeWidth={1.5} />
                </div>
                <h3 className="feature-title">{title}</h3>
                <p className="feature-description">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── How It Works ── */}
        <section className="how-it-works">
          <h2>How <span className="cursive-accent">ARIA</span> Works</h2>
          <div className="steps">
            {[
              {
                n: 1,
                title: 'Create Your Business Profile',
                desc: 'Tell us about your business - location, type, products, and target market. ARIA will use this to understand your context.',
                icon: (
                  <svg className="icon-step" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
                    <polyline points="9 22 9 12 15 12 15 22"/>
                  </svg>
                ),
              },
              {
                n: 2,
                title: 'Generate Customer Archetypes',
                desc: 'ARIA creates realistic customer personas based on demographic data from your area.',
                icon: (
                  <svg className="icon-step" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>
                  </svg>
                ),
              },
              {
                n: 3,
                title: 'Run Simulation',
                desc: 'Test scenarios and see how virtual customers react to your business decisions.',
                icon: (
                  <svg className="icon-step" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <circle cx="12" cy="12" r="10"/>
                    <polygon points="10 8 16 12 10 16 10 8"/>
                  </svg>
                ),
              },
            ].map(({ n, title, desc, icon }) => (
              <div key={n} className="step-card">
                <span className="step-number">{n}</span>
                <div className="step-content">
                  <h3>{title}</h3>
                  <p>{desc}</p>
                </div>
                <div className="step-icon">{icon}</div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </>
  )
}
