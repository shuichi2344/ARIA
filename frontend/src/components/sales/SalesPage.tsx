'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import ProfileWidget from '@/components/auth/ProfileWidget'
import { useSession } from '@/context/SessionContext'
import type { AriaSession } from '@/components/dashboard/types'
import SalesChart from './SalesChart'

interface SalesRecord {
  record_id: string
  sale_date: string
  total_sales: number
  transaction_count: number | null
  source: string
  notes: string | null
}

type FilterMode = 'daily' | 'monthly' | 'yearly'

interface Props { session: AriaSession }

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export default function SalesPage({ session }: Props) {
  const router = useRouter()
  const { logout } = useSession()

  const [records, setRecords] = useState<SalesRecord[]>([])
  const [filter, setFilter] = useState<FilterMode>('daily')
  const [error, setError] = useState<string | null>(null)
  const [profileId, setProfileId] = useState<string | null>(null)
  const [showManualEntry, setShowManualEntry] = useState(false)
  const [manualDate, setManualDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [manualSales, setManualSales] = useState('')
  const [manualCount, setManualCount] = useState('')
  const [manualSaving, setManualSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    try {
      const id = localStorage.getItem('aria_profile_id')
      if (id) setProfileId(id)
    } catch {}
  }, [])

  const fetchRecords = useCallback(async () => {
    if (!profileId) return
    try {
      const res = await fetch(`${API_BASE}/api/sales/records?profile_id=${profileId}`)
      if (!res.ok) throw new Error('Failed to fetch')
      const data = await res.json()
      setRecords(data.records || [])
    } catch (e) { console.error('Failed to fetch records:', e) }
  }, [profileId])

  useEffect(() => { fetchRecords() }, [fetchRecords])

  async function handleManualSave() {
    if (!profileId || !manualDate || !manualSales) return
    const sales = parseFloat(manualSales)
    if (isNaN(sales) || sales < 0) { setError('Please enter a valid sales amount'); return }
    setManualSaving(true)
    setError(null)
    setSaveStatus(null)
    try {
      const res = await fetch(`${API_BASE}/api/sales/manual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile_id: profileId,
          sale_date: manualDate,
          total_sales: sales,
          transaction_count: manualCount ? parseInt(manualCount) : null,
        }),
      })
      if (!res.ok) { const t = await res.text(); throw new Error(t || 'Failed to save') }
      setSaveStatus(`✓ Recorded RM ${sales.toFixed(2)} for ${manualDate}`)
      setManualSales('')
      setManualCount('')
      setShowManualEntry(false)
      await fetchRecords()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setManualSaving(false)
    }
  }

  async function handleDeleteRecord(recordId: string) {
    if (!profileId) return
    if (!window.confirm('Delete this sales record? This cannot be undone.')) return
    setDeletingId(recordId)
    try {
      const res = await fetch(
        `${API_BASE}/api/sales/records/${recordId}?profile_id=${encodeURIComponent(profileId)}`,
        { method: 'DELETE' }
      )
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail || 'Delete failed') }
      await fetchRecords()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to delete record')
    } finally {
      setDeletingId(null)
    }
  }

  function handleLogout() { logout(); router.push('/') }

  useEffect(() => {
    const saved = localStorage.getItem('aria-theme') || 'burgundy'
    document.body.dataset.theme = saved
  }, [])

  const inputStyle: React.CSSProperties = {
    padding: '0.6rem 0.75rem', borderRadius: 8,
    border: '1.5px solid var(--gray-200)', fontSize: '0.875rem',
    outline: 'none', width: '100%', background: 'white',
  }
  const labelStyle: React.CSSProperties = { fontSize: '0.8rem', fontWeight: 600, color: 'var(--gray-700)' }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <header style={{ position: 'fixed', top: 0, left: 0, right: 0, height: 56, background: 'var(--white)', borderBottom: '1px solid var(--gray-200)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 1.5rem', zIndex: 100 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <Link href="/dashboard" style={{ fontFamily: 'var(--font-display)', fontSize: '1.25rem', fontWeight: 900, background: 'linear-gradient(135deg, var(--accent), var(--accent-warm))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text', textDecoration: 'none' }}>ARIA</Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', color: 'var(--gray-600)' }}>
            <Link href="/dashboard" style={{ color: 'var(--gray-600)', textDecoration: 'none' }}>Dashboard</Link>
            <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
            <span style={{ color: 'var(--gray-900)', fontWeight: 600 }}>Sales Insights</span>
          </div>
        </div>
        <ProfileWidget session={session} onLogout={handleLogout} onEditProfile={() => router.push('/onboarding?edit=1')} />
      </header>

      <main style={{ flex: 1, paddingTop: 56, overflow: 'auto', background: 'var(--gray-50)' }}>
        <div style={{ padding: '2rem' }}>

          {/* Page header */}
          <div style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--gray-900)', margin: 0 }}>Sales Trend</h1>
              <p style={{ fontSize: '0.875rem', color: 'var(--gray-500)', margin: '0.25rem 0 0' }}>Track your sales performance over time</p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              {/* Add Manually button */}
              <button
                onClick={() => setShowManualEntry(v => !v)}
                disabled={!profileId}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', borderRadius: 8, border: showManualEntry ? '1.5px solid var(--accent)' : '1.5px solid var(--gray-200)', background: showManualEntry ? 'color-mix(in srgb, var(--accent) 6%, white)' : 'white', cursor: !profileId ? 'not-allowed' : 'pointer', transition: 'all 0.15s', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}
              >
                <svg style={{ width: 16, height: 16, color: 'var(--accent)' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent)' }}>Add Record</span>
              </button>
              {/* Filter toggle */}
              <div style={{ display: 'flex', gap: '0.25rem', background: 'var(--gray-100)', borderRadius: 8, padding: '0.2rem' }}>
                {(['daily', 'monthly', 'yearly'] as FilterMode[]).map(mode => (
                  <button key={mode} onClick={() => setFilter(mode)} style={{ padding: '0.4rem 0.9rem', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: '0.825rem', fontWeight: 600, background: filter === mode ? 'white' : 'transparent', color: filter === mode ? 'var(--accent)' : 'var(--gray-600)', boxShadow: filter === mode ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', transition: 'all 0.15s' }}>
                    {mode.charAt(0).toUpperCase() + mode.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Status / error messages */}
          {(saveStatus || error || !profileId) && (
            <div style={{ marginBottom: '1rem' }}>
              {saveStatus && <div style={{ padding: '0.5rem 0.75rem', borderRadius: 6, background: '#f0fdf4', border: '1px solid #bbf7d0', fontSize: '0.8rem', fontWeight: 500, color: '#15803d', marginBottom: '0.5rem' }}>{saveStatus}</div>}
              {error && <div style={{ padding: '0.5rem 0.75rem', borderRadius: 6, background: '#fef2f2', color: '#dc2626', fontSize: '0.8rem', fontWeight: 500, whiteSpace: 'pre-line', marginBottom: '0.5rem' }}>{error}</div>}
              {!profileId && <div style={{ padding: '0.5rem 0.75rem', borderRadius: 6, background: '#fffbeb', color: '#92400e', fontSize: '0.8rem', fontWeight: 500 }}>Complete your business profile first to add sales data.</div>}
            </div>
          )}

          {/* Manual entry modal */}
          {showManualEntry && (
            <div onClick={e => { if (e.target === e.currentTarget) setShowManualEntry(false) }} style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(3px)', padding: '1rem' }}>
              <div style={{ background: 'white', borderRadius: 14, padding: '2rem', width: '100%', maxWidth: 380, boxShadow: '0 20px 60px rgba(0,0,0,0.2)', display: 'flex', flexDirection: 'column', gap: '1.25rem', position: 'relative' }}>
                <button onClick={() => setShowManualEntry(false)} style={{ position: 'absolute', top: '0.75rem', right: '0.75rem', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-400)', padding: '0.25rem', borderRadius: 4, display: 'flex', alignItems: 'center' }}>
                  <svg style={{ width: 18, height: 18 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--gray-900)' }}>Add Sales Record</h3>
                  <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: 'var(--gray-500)' }}>Enter your sales data for a specific date.</p>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  <label style={labelStyle}>Date</label>
                  <input type="date" value={manualDate} onChange={e => setManualDate(e.target.value)} style={inputStyle} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  <label style={labelStyle}>Total Sales (RM)</label>
                  <input type="number" min="0" step="0.01" placeholder="0.00" value={manualSales} onChange={e => setManualSales(e.target.value)} style={inputStyle} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                  <label style={labelStyle}>Number of Transactions <span style={{ fontWeight: 400, color: 'var(--gray-400)' }}>(optional)</span></label>
                  <input type="number" min="0" step="1" placeholder="—" value={manualCount} onChange={e => setManualCount(e.target.value)} style={inputStyle} />
                </div>
                <button onClick={handleManualSave} disabled={manualSaving || !manualSales || !manualDate} style={{ padding: '0.7rem 1rem', borderRadius: 8, border: 'none', cursor: manualSaving || !manualSales ? 'not-allowed' : 'pointer', background: manualSaving || !manualSales ? 'var(--gray-200)' : 'var(--accent)', color: manualSaving || !manualSales ? 'var(--gray-500)' : 'white', fontSize: '0.9rem', fontWeight: 600, width: '100%' }}>
                  {manualSaving ? 'Saving...' : 'Save Record'}
                </button>
              </div>
            </div>
          )}

          {/* Chart */}
          <div style={{ background: 'white', borderRadius: 12, padding: '1.5rem', border: '1px solid var(--gray-200)', marginBottom: '1.5rem' }}>
            {records.length === 0
              ? (
                <div style={{ height: 360, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--gray-400)', gap: '0.75rem' }}>
                  <svg style={{ width: 48, height: 48 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                  <div style={{ textAlign: 'center' }}>
                    <p style={{ margin: 0, fontSize: '0.875rem', fontWeight: 500 }}>No sales data yet</p>
                    <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem' }}>Click &ldquo;Add Record&rdquo; to start tracking your sales.</p>
                  </div>
                </div>
              )
              : <SalesChart records={records} filter={filter} />}
          </div>

          {/* Records table */}
          {records.length > 0 && (
            <div style={{ background: 'white', borderRadius: 12, padding: '1.5rem', border: '1px solid var(--gray-200)' }}>
              <h2 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--gray-900)', margin: '0 0 1rem' }}>Records ({records.length})</h2>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--gray-200)' }}>
                      <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', color: 'var(--gray-600)', fontWeight: 600 }}>Date</th>
                      <th style={{ textAlign: 'right', padding: '0.5rem 0.75rem', color: 'var(--gray-600)', fontWeight: 600 }}>Total Sales (RM)</th>
                      <th style={{ textAlign: 'right', padding: '0.5rem 0.75rem', color: 'var(--gray-600)', fontWeight: 600 }}>Transactions</th>
                      <th style={{ padding: '0.5rem 0.75rem' }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.slice(0, 50).map(r => (
                      <tr key={r.record_id} style={{ borderBottom: '1px solid var(--gray-100)' }}>
                        <td style={{ padding: '0.5rem 0.75rem' }}>{r.sale_date}</td>
                        <td style={{ padding: '0.5rem 0.75rem', textAlign: 'right', fontWeight: 500 }}>
                          {r.total_sales.toLocaleString('en-MY', { minimumFractionDigits: 2 })}
                        </td>
                        <td style={{ padding: '0.5rem 0.75rem', textAlign: 'right', color: 'var(--gray-600)' }}>
                          {r.transaction_count ?? '—'}
                        </td>
                        <td style={{ padding: '0.5rem 0.75rem' }}>
                          <button
                            onClick={() => handleDeleteRecord(r.record_id)}
                            disabled={deletingId === r.record_id}
                            title="Delete record"
                            style={{ background: 'none', border: 'none', cursor: deletingId === r.record_id ? 'not-allowed' : 'pointer', padding: '0.25rem', borderRadius: 4, color: 'var(--gray-400)', display: 'flex', alignItems: 'center', opacity: deletingId === r.record_id ? 0.4 : 1 }}
                          >
                            <svg style={{ width: 15, height: 15 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
                            </svg>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
