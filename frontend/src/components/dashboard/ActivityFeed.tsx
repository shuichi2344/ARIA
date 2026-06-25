'use client'

import { useEffect, useRef, useState, useMemo } from 'react'
import type { FeedItem } from './types'

interface Props {
  items: FeedItem[]
  onAgentClick?: (agentId: number | null) => void
  highlightedAgentId?: number | null
}

const BG: Record<string, string> = {
  visit:  '#f0fdf4',
  skip:   '#fffbeb',
  churn:  '#fef2f2',
  week:   'var(--gray-50)',
  system: 'var(--gray-50)',
}
const DOT: Record<string, string> = {
  visit:  '#22c55e',
  skip:   '#f59e0b',
  churn:  '#ef4444',
  week:   'var(--accent)',
  system: 'var(--gray-400)',
}

// Split feed items into pages by run dividers (━━━ Run X of Y ━━━)
// The first page includes everything before AND after the first run divider
function splitByRun(items: FeedItem[]): FeedItem[][] {
  const pages: FeedItem[][] = []
  let current: FeedItem[] = []
  let foundFirstRun = false

  for (const item of items) {
    // Detect run divider (the ━━━ Run X of Y ━━━ system message)
    if (item.type === 'system' && item.html.includes('━━━ Run')) {
      if (!foundFirstRun) {
        // First run divider — keep everything on the same page
        foundFirstRun = true
        current.push(item)
      } else {
        // Subsequent run dividers — start a new page
        if (current.length > 0) {
          pages.push(current)
        }
        current = [item]
      }
    } else {
      current.push(item)
    }
  }
  if (current.length > 0) {
    pages.push(current)
  }
  return pages
}

export default function ActivityFeed({ items, onAgentClick, highlightedAgentId }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [currentPage, setCurrentPage] = useState(0)

  // Split items into pages (one per run)
  const pages = useMemo(() => splitByRun(items), [items])
  const totalPages = pages.length

  // Auto-advance to latest page when new runs start
  useEffect(() => {
    if (totalPages > 0) {
      setCurrentPage(totalPages - 1)
    }
  }, [totalPages])

  // Auto-scroll to bottom within current page
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [items, currentPage])

  const displayItems = pages[currentPage] || items

  function handleClick(item: FeedItem) {
    if (item.agentId != null && onAgentClick) {
      if (highlightedAgentId === item.agentId) {
        onAgentClick(null)
      } else {
        onAgentClick(item.agentId)
      }
    }
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
      background: 'var(--white)', borderRadius: 8,
      border: '1px solid var(--gray-200)', padding: '0.75rem',
    }}>
      {/* Header with pagination */}
      <div style={{
        fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.05em', color: 'var(--gray-600)',
        display: 'flex', alignItems: 'center', gap: '0.4rem',
        marginBottom: '0.6rem', flexShrink: 0,
      }}>
        <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        Live Activity
        {highlightedAgentId != null && (
          <span style={{
            marginLeft: 'auto', fontSize: '0.68rem', fontWeight: 500,
            color: 'var(--accent)', textTransform: 'none', letterSpacing: 0,
          }}>
            Customer {highlightedAgentId} selected
          </span>
        )}
      </div>

      {/* Run pagination — only show when there are multiple runs */}
      {totalPages > 1 && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: '0.5rem', marginBottom: '0.5rem', flexShrink: 0,
        }}>
          <button
            onClick={() => setCurrentPage(p => Math.max(0, p - 1))}
            disabled={currentPage === 0}
            style={{
              background: 'none', border: 'none', cursor: currentPage === 0 ? 'default' : 'pointer',
              color: currentPage === 0 ? 'var(--gray-300)' : 'var(--gray-700)',
              padding: '0.2rem', borderRadius: 4, display: 'flex',
              transition: 'color 0.15s',
            }}
          >
            <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--gray-600)' }}>
            Run {currentPage + 1} of {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage(p => Math.min(totalPages - 1, p + 1))}
            disabled={currentPage === totalPages - 1}
            style={{
              background: 'none', border: 'none', cursor: currentPage === totalPages - 1 ? 'default' : 'pointer',
              color: currentPage === totalPages - 1 ? 'var(--gray-300)' : 'var(--gray-700)',
              padding: '0.2rem', borderRadius: 4, display: 'flex',
              transition: 'color 0.15s',
            }}
          >
            <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </button>
        </div>
      )}

      <div ref={ref} style={{
        flex: 1, overflowY: 'auto',
        display: 'flex', flexDirection: 'column', gap: '0.4rem',
      }}>
        {displayItems.map((item, idx) => {
          const isClickable = item.agentId != null

          return (
            <div
              key={`${item.id}-${idx}`}
              onClick={() => handleClick(item)}
              style={{
                display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
                padding: '0.4rem 0.5rem', borderRadius: 4,
                fontSize: '0.78rem', lineHeight: 1.4,
                background: BG[item.type] ?? 'var(--gray-50)',
                fontWeight: item.type === 'week' ? 700 : 400,
                animation: 'feed-in 0.3s ease',
                cursor: isClickable ? 'pointer' : 'default',
                transition: 'background 0.15s',
              }}
            >
              <span style={{
                width: 7, height: 7, borderRadius: '50%',
                background: DOT[item.type] ?? 'var(--gray-400)',
                flexShrink: 0, marginTop: 4, display: 'inline-block',
              }} />
              <span style={{ color: 'var(--gray-900)', flex: 1 }}
                dangerouslySetInnerHTML={{ __html: item.html }} />
            </div>
          )
        })}
      </div>

      <style>{`
        @keyframes feed-in {
          from { opacity: 0; transform: translateX(8px); }
          to   { opacity: 1; transform: translateX(0); }
        }
        .reasoning {
          display: block;
          color: var(--gray-600);
          font-size: 0.72rem;
          margin-top: 1px;
        }
      `}</style>
    </div>
  )
}
