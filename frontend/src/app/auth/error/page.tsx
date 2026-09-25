'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Mail, MessageSquareText } from 'lucide-react'

const BETA_FEEDBACK_URL = process.env.NEXT_PUBLIC_BETA_FEEDBACK_URL?.trim() ?? ''

export default function AuthErrorPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [error, setError] = useState<string>('')
  const [errorCode, setErrorCode] = useState<string>('')
  const [errorDescription, setErrorDescription] = useState<string>('')

  useEffect(() => {
    // Apply saved theme
    const saved = localStorage.getItem('aria-theme') || 'burgundy'
    document.body.dataset.theme = saved

    // Parse error parameters from URL
    const errorParam = searchParams.get('error') || ''
    const errorCodeParam = searchParams.get('error_code') || ''
    const errorDescParam = searchParams.get('error_description') || ''
    const reasonParam = searchParams.get('reason') || ''

    setError(errorParam)
    setErrorCode(errorCodeParam)
    setErrorDescription(errorDescParam)

    console.log('[AuthError] Error params:', { errorParam, errorCodeParam, errorDescParam, reasonParam })
  }, [searchParams])

  // Check if this is beta access expiry
  const isBetaExpired = searchParams.get('reason') === 'beta_expired'

  // Check if this is an expired OTP/invitation error
  const isExpiredInvite = 
    errorCode === 'otp_expired' || 
    error === 'access_denied' || 
    errorDescription.toLowerCase().includes('expired') ||
    errorDescription.toLowerCase().includes('invalid')

  const getErrorMessage = () => {
    if (isBetaExpired) {
      return {
        title: 'Beta Access Expired',
        description: 'Your beta testing period has ended. Thank you for participating in the ARIA beta programme.',
      }
    }

    if (isExpiredInvite) {
      return {
        title: 'Invitation Link Expired',
        description: 'The invitation link you clicked has expired or is no longer valid.',
      }
    }

    // Generic error handling
    if (errorDescription) {
      return {
        title: 'Authentication Error',
        description: errorDescription.replace(/\+/g, ' '),
      }
    }

    return {
      title: 'Authentication Error',
      description: 'An error occurred during authentication. Please try again.',
    }
  }

  const errorInfo = getErrorMessage()

  const handleContactSupport = () => {
    const isBetaExpired = searchParams.get('reason') === 'beta_expired'
    if (isBetaExpired) {
      if (BETA_FEEDBACK_URL) window.location.assign(BETA_FEEDBACK_URL)
      return
    }

    const body = 'Hello%2C%0A%0AI%20received%20an%20expired%20invitation%20link%20and%20would%20like%20to%20request%20a%20new%20one.%0A%0AThank%20you.'
    
    window.location.href = `mailto:aria.fypsupport@gmail.com?subject=New%20Invitation%20Request&body=${body}`
  }

  return (
    <main style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem',
      background: 'linear-gradient(135deg, var(--gray-50) 0%, var(--gray-100) 100%)',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '480px',
        background: 'var(--white)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        overflow: 'hidden',
      }}>
        {/* Header with brand only */}
        <div style={{
          background: '#ffffff',
          padding: '2.5rem 2rem 1.5rem',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '1rem',
          borderBottom: '1px solid #e5e7eb',
        }}>
          <div style={{ textAlign: 'center' }}>
            <h1 style={{
              fontFamily: 'var(--font-display)',
              fontSize: '2rem',
              fontWeight: 900,
              lineHeight: 1,
              margin: 0,
              color: '#000000',
            }}>
              ARIA
            </h1>
          </div>
        </div>

        {/* Error content */}
        <div style={{
          padding: '2rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.5rem',
        }}>
          <div style={{ textAlign: 'center' }}>
            <h2 style={{
              fontSize: '1.25rem',
              fontWeight: 700,
              color: '#1f2937',
              margin: '0 0 0.5rem',
            }}>
              {errorInfo.title}
            </h2>
            <p style={{
              fontSize: '0.9375rem',
              color: '#6b7280',
              lineHeight: 1.6,
              margin: 0,
            }}>
              {errorInfo.description}
            </p>
          </div>

          {/* Show invite-specific message */}
          {(isExpiredInvite || isBetaExpired) && (
            <div style={{
              background: '#fffbeb',
              border: '1px solid #fde68a',
              borderRadius: '8px',
              padding: '1rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.625rem',
              }}>
                {isBetaExpired
                  ? <MessageSquareText style={{ width: 20, height: 20, color: '#92400e', flexShrink: 0, marginTop: '2px' }} />
                  : <Mail style={{ width: 20, height: 20, color: '#92400e', flexShrink: 0, marginTop: '2px' }} />}
                <div style={{ flex: 1 }}>
                  <p style={{
                    fontSize: '0.875rem',
                    color: '#92400e',
                    lineHeight: 1.5,
                    margin: 0,
                  }}>
                    {isBetaExpired
                      ? 'We’d appreciate your feedback about the ARIA beta programme.'
                      : 'To request a new invitation link, please send an email to:'}
                  </p>
                  {!isBetaExpired && <a
                      href="mailto:aria.fypsupport@gmail.com"
                      style={{
                        fontSize: '0.9375rem',
                        fontWeight: 600,
                        color: 'var(--accent)',
                        textDecoration: 'none',
                        display: 'block',
                        marginTop: '0.25rem',
                        wordBreak: 'break-word',
                      }}
                    >
                      aria.fypsupport@gmail.com
                    </a>}
                </div>
              </div>
            </div>
          )}

          {/* Action button */}
          {(isExpiredInvite || isBetaExpired) && (
            <div style={{ marginTop: '0.5rem' }}>
              <button
                onClick={handleContactSupport}
                disabled={isBetaExpired && !BETA_FEEDBACK_URL}
                title={isBetaExpired && !BETA_FEEDBACK_URL ? 'Feedback form link will be added soon.' : undefined}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  background: isBetaExpired && !BETA_FEEDBACK_URL ? '#6b7280' : '#000000',
                  color: '#fff',
                  fontFamily: 'var(--font-family)',
                  fontSize: '1rem',
                  fontWeight: 600,
                  padding: '1rem',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: isBetaExpired && !BETA_FEEDBACK_URL ? 'not-allowed' : 'pointer',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                  transition: 'all 0.3s cubic-bezier(0.16,1,0.3,1)',
                }}
                onMouseEnter={e => {
                  if (isBetaExpired && !BETA_FEEDBACK_URL) return
                  e.currentTarget.style.background = '#1f2937'
                  e.currentTarget.style.transform = 'translateY(-2px)'
                  e.currentTarget.style.boxShadow = '0 6px 20px rgba(0,0,0,0.2)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = isBetaExpired && !BETA_FEEDBACK_URL ? '#6b7280' : '#000000'
                  e.currentTarget.style.transform = 'translateY(0)'
                  e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.15)'
                }}
              >
                {isBetaExpired ? <MessageSquareText style={{ width: 20, height: 20 }} /> : <Mail style={{ width: 20, height: 20 }} />}
                {isBetaExpired ? 'Send Feedback' : 'Request New Invitation'}
              </button>
            </div>
          )}

          {isBetaExpired && (
            <button
              type="button"
              onClick={() => router.replace('/')}
              style={{
                alignSelf: 'center',
                background: 'transparent',
                border: 'none',
                color: 'var(--accent)',
                cursor: 'pointer',
                font: 'inherit',
                fontSize: '0.875rem',
                padding: '0.25rem 0.5rem',
                textDecoration: 'underline',
              }}
            >
              Return to ARIA home
            </button>
          )}

          {/* Error details (for debugging) */}
          {(error || errorCode) && (
            <details style={{
              marginTop: '1rem',
              padding: '0.75rem',
              background: 'var(--gray-50)',
              borderRadius: '6px',
              fontSize: '0.75rem',
              color: 'var(--gray-600)',
            }}>
              <summary style={{
                cursor: 'pointer',
                fontWeight: 600,
                userSelect: 'none',
              }}>
                Technical Details
              </summary>
              <div style={{
                marginTop: '0.5rem',
                fontFamily: 'monospace',
                fontSize: '0.7rem',
                wordBreak: 'break-all',
              }}>
                {error && <div><strong>Error:</strong> {error}</div>}
                {errorCode && <div><strong>Code:</strong> {errorCode}</div>}
                {errorDescription && <div><strong>Description:</strong> {errorDescription}</div>}
              </div>
            </details>
          )}
        </div>
      </div>

      <style jsx>{`
        /* Removed pulse animation */
      `}</style>
    </main>
  )
}
