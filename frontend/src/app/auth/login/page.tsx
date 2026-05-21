'use client'

/**
 * Standalone login page — redirects to landing which has the modal.
 * Kept for direct-link access; mirrors the modal behaviour.
 */

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const router = useRouter()

  // Just redirect to landing — the auth modal opens there
  useEffect(() => {
    router.replace('/?auth=login')
  }, [router])

  return null
}
