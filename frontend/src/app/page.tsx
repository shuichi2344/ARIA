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

  // Apply saved theme on every mount — same as initThemeSwitcher() / applyTheme()
  useEffect(() => {
    const saved = localStorage.getItem('aria-theme') || 'burgundy'
    document.body.dataset.theme = saved
  }, [])

  // Handle ?auth= query param (from /auth/login redirect)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const authParam = params.get('auth')
    if (authParam === 'login' || authParam === 'register') {
      setAuthTab(authParam)
      setAuthOpen(true)
      window.history.replaceState({}, '', '/')
    }
  }, [])

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
  async function routeAfterAuth(user: { id: string; email: string; created_at: string }) {
    setSession(user)
    setAuthOpen(false)
    setNavigating(true)

    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 5000)
      const res = await fetch(`${API_BASE}/api/business/profile/user/${user.id}`, {
        signal: controller.signal,
      })
      clearTimeout(timeout)
      if (res.ok) {
        const profile = await res.json()
        if (profile?.id) {
          localStorage.setItem('aria_profile',    JSON.stringify(profile))
          localStorage.setItem('aria_profile_id', profile.id)
          router.push('/dashboard')
          return
        }
      }
    } catch { /* API unreachable or timed out — fall through to onboarding */ }

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
