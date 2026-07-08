'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from '@/context/SessionContext'
import SalesPage from '@/components/sales/SalesPage'

export default function Sales() {
  const router = useRouter()
  const { session } = useSession()

  useEffect(() => {
    if (session === null) {
      router.replace('/?auth=login')
    }
  }, [session, router])

  if (!session) return null
  return <SalesPage session={session} />
}
