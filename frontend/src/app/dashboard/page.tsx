'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useSession } from '@/context/SessionContext'
import DashboardPage from '@/components/dashboard/DashboardPage'

export default function Dashboard() {
  const router = useRouter()
  const { session } = useSession()

  useEffect(() => {
    if (session === null) {
      router.replace('/?auth=login')
    }
  }, [session, router])

  if (!session) return null
  return <DashboardPage session={session} />
}
