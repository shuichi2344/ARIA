'use client'

import { useState } from 'react'
import type { SimSnapshot } from './types'

interface Props {
  open: boolean
  onClose: () => void
  history: SimSnapshot[]
  onRestore: (snap: SimSnapshot) => void
  onDelete: (id: string) => void
  onNewChat: () => void
}

const SCENARIO_ICONS: Record<string, string> = {
  price_change:           '💰',
  new_competitor:         '🏪',
  marketing_campaign:     '📣',
  operating_hours_change: '🕐',
  product_launch:         '🚀',
  default:                '🔬',
}

function groupByDate(history: SimSnapshot[]): { label: string; items: SimSnapshot[] }[] {
  const now   = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo   = new Date(today.getTime() - 7 * 86400000)

  const groups: Record<string, SimSnapshot[]> = {
    Today:          [],
    Yesterday:      [],
    'Last 7 days':  [],
    Older:          [],
  }

  for (const snap of [...history].reverse()) {
    const d = new Date(snap.completedAt)
    const day = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    if (day >= today)         groups['Today'].push(snap)
    else if (day >= yesterday) groups['Yesterday'].push(snap)
    else if (day >= weekAgo)   groups['Last 7 days'].push(snap)
    else                       groups['Older'].push(snap)
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }))
}

function fmt(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function HistorySidebar({ open, onClose, history, onRestore, onDelete, onNewChat }: Props) {
  const [hoverId, setHoverId] = useState<string | null>(null)
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const groups = groupByDate(history)

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            background: 'rgba(0,0,0,0.25)',
            animation: 'fadeIn 0.15s ease',
          }}
        />
      )}

      {/* Sidebar panel */}
      <div style={{
        position: 'fixed', top: 0, left: 0, bottom: 0,
        width: 280, zIndex: 201,
        background: 'var(--white)',
        borderRight: '1px solid var(--gray-200)',
        display: 'flex', flexDirection: 'column',
        transform: open ? 'translateX(0)' : 'translateX(-100%)',
        transition: 'transform 0.25s cubic-bezier(0.16,1,0.3,1)',
        boxShadow: open ? '4px 0 24px rgba(0,0,0,0.1)' : 'none',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '1rem 1.25rem',
          borderBottom: '1px solid var(--gray-100)',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <svg style={{ width: 16, height: 16, color: 'var(--accent)' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--gray-900)' }}>
              Simulation History
            </span>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--gray-400)', padding: '0.25rem', borderRadius: 4,
            display: 'flex', alignItems: 'center',
            transition: 'color 0.15s',
          }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--gray-900)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--gray-400)')}
          >
            <svg style={{ width: 18, height: 18 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* List */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem 0' }}>
          {groups.length === 0 ? (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', height: '100%', gap: '0.75rem',
              color: 'var(--gray-400)', padding: '2rem', textAlign: 'center',
            }}>
              <svg style={{ width: 40, height: 40, opacity: 0.4 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
              <p style={{ fontSize: '0.85rem', margin: 0 }}>
                No simulations yet.<br />Run one to see it here.
              </p>
            </div>
          ) : (
            groups.map(({ label, items }) => (
              <div key={label}>
                {/* Date group label */}
                <div style={{
                  padding: '0.5rem 1.25rem 0.25rem',
                  fontSize: '0.7rem', fontWeight: 700,
                  color: 'var(--gray-400)',
                  textTransform: 'uppercase', letterSpacing: '0.06em',
                }}>
                  {label}
                </div>

                {items.map(snap => (
                  <div
                    key={snap.id}
                    onMouseEnter={() => setHoverId(snap.id)}
                    onMouseLeave={() => setHoverId(null)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '0.5rem',
                      padding: '0.6rem 1.25rem',
                      background: hoverId === snap.id ? 'var(--gray-50)' : 'transparent',
                      cursor: 'pointer',
                      transition: 'background 0.1s',
                      position: 'relative',
                    }}
                    onClick={() => onRestore(snap)}
                  >
                    {/* Icon */}
                    <span style={{ fontSize: '1rem', flexShrink: 0 }}>
                      {SCENARIO_ICONS[snap.scenarioType] ?? SCENARIO_ICONS.default}
                    </span>

                    {/* Text */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: '0.85rem', fontWeight: 500,
                        color: 'var(--gray-900)',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>
                        {snap.scenarioName}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--gray-500)', marginTop: 1 }}>
                        {fmt(snap.completedAt)}
                        {snap.finalMetrics && ` · RM ${snap.finalMetrics.total_revenue.toFixed(0)}`}
                      </div>
                    </div>

                    {/* Delete button — shown on hover */}
                    {hoverId === snap.id && (
                      <button
                        onClick={e => { e.stopPropagation(); setConfirmId(snap.id) }}
                        style={{
                          background: 'none', border: 'none', cursor: 'pointer',
                          color: 'var(--gray-400)', padding: '0.2rem', borderRadius: 4,
                          display: 'flex', alignItems: 'center', flexShrink: 0,
                          transition: 'color 0.15s',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.color = '#ef4444')}
                        onMouseLeave={e => (e.currentTarget.style.color = 'var(--gray-400)')}
                        title="Delete"
                      >
                        <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
                        </svg>
                      </button>
                    )}
                  </div>
                ))}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '0.75rem 1.25rem',
          borderTop: '1px solid var(--gray-100)',
          display: 'flex', flexDirection: 'column', gap: '0.6rem',
          flexShrink: 0,
        }}>
          <button
            onClick={() => { onNewChat(); onClose() }}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
              width: '100%', padding: '0.6rem',
              background: 'var(--accent)', color: 'white',
              border: 'none', borderRadius: 8,
              fontSize: '0.82rem', fontWeight: 600,
              cursor: 'pointer', fontFamily: 'var(--font-family)',
              transition: 'opacity 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.opacity = '0.88')}
            onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
          >
            <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            New Chat
          </button>
          <div style={{ fontSize: '0.72rem', color: 'var(--gray-400)', textAlign: 'center' }}>
            {history.length} simulation{history.length !== 1 ? 's' : ''} saved
          </div>
        </div>
      </div>

      {/* Delete confirmation modal */}
      {confirmId && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 300,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0,0,0,0.4)',
        }}>
          <div style={{
            background: 'white', borderRadius: 12, padding: '1.5rem',
            maxWidth: 320, width: '90%',
            boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
          }}>
            <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>Delete simulation?</h3>
            <p style={{ margin: '0 0 1.25rem', fontSize: '0.875rem', color: 'var(--gray-600)' }}>
              This will remove it from your history. This cannot be undone.
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button onClick={() => setConfirmId(null)} style={{
                padding: '0.5rem 1rem', border: '1.5px solid var(--gray-300)',
                borderRadius: 8, background: 'white', cursor: 'pointer',
                fontSize: '0.875rem', fontWeight: 600, fontFamily: 'var(--font-family)',
              }}>
                Cancel
              </button>
              <button onClick={() => { onDelete(confirmId); setConfirmId(null) }} style={{
                padding: '0.5rem 1rem', border: 'none',
                borderRadius: 8, background: '#ef4444', color: 'white',
                cursor: 'pointer', fontSize: '0.875rem', fontWeight: 600,
                fontFamily: 'var(--font-family)',
              }}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
