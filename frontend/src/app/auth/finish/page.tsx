'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { createClient, type EmailOtpType, type Session } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
)

export default function FinishAuthPage() {
  const [message, setMessage] = useState('Verifying your email link…')

  useEffect(() => {
    let cancelled = false

    async function finishAuth() {
      const params = new URLSearchParams(window.location.search)
      const code = params.get('code')
      const tokenHash = params.get('token_hash')
      const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''))
      const type = params.get('type') || fragment.get('type') || ''

      try {
        let session: Session | null = null
        let verificationError: Error | null = null

        const accessToken = fragment.get('access_token')
        const refreshToken = fragment.get('refresh_token')
        if (accessToken && refreshToken) {
          const result = await supabase.auth.setSession({
            access_token: accessToken,
            refresh_token: refreshToken,
          })
          session = result.data.session
          verificationError = result.error
        } else if (code) {
          const result = await supabase.auth.exchangeCodeForSession(code)
          session = result.data.session
          verificationError = result.error
        } else if (tokenHash && type) {
          const result = await supabase.auth.verifyOtp({
            token_hash: tokenHash,
            type: type as EmailOtpType,
          })
          session = result.data.session
          verificationError = result.error
        } else {
          verificationError = new Error('The confirmation link is incomplete.')
        }

        if (verificationError || !session) {
          throw verificationError || new Error('Supabase did not create a session.')
        }

        const authFragment = new URLSearchParams({
          access_token: session.access_token,
          refresh_token: session.refresh_token,
          type,
        }).toString()

        if (type === 'invite') {
          window.location.replace(`/auth/setup-password#${authFragment}`)
          return
        }

        if (type === 'recovery') {
          window.location.replace(`/auth/reset-password#${authFragment}`)
          return
        }

        const user = session.user
        localStorage.setItem('aria_session', JSON.stringify({
          id: user.id,
          email: user.email || '',
          created_at: user.created_at,
          access_token: session.access_token,
          refresh_token: session.refresh_token,
          email_confirmed: Boolean(user.email_confirmed_at),
        }))

        window.location.replace(type === 'signup' || type === 'email_confirmation'
          ? '/onboarding'
          : '/dashboard')
      } catch (error) {
        console.error('[Auth Finish] Link verification failed:', error)
        if (!cancelled) {
          setMessage('This email link is invalid or has expired. Please request a new link and try again.')
        }
      }
    }

    void finishAuth()
    return () => { cancelled = true }
  }, [])

  return (
    <main style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: '1.5rem' }}>
      <section style={{ maxWidth: 440, textAlign: 'center' }}>
        <h1 style={{ marginBottom: '0.75rem' }}>ARIA</h1>
        <p role="status" style={{ color: '#4b5563', lineHeight: 1.6 }}>{message}</p>
        {message.startsWith('This email link') && (
          <Link href="/" style={{ color: '#4f46e5' }}>Return to ARIA</Link>
        )}
      </section>
    </main>
  )
}
