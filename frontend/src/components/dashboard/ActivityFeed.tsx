'use client'

import { useEffect, useRef } from 'react'
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

export default function ActivityFeed({ items, onAgentClick, highlightedAgentId }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [items])

  function handleClick(item: FeedItem) {
    if (item.agentId != null && onAgentClick) {
      // Toggle: click same agent again to deselect
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

      <div ref={ref} style={{
        flex: 1, overflowY: 'auto',
        display: 'flex', flexDirection: 'column', gap: '0.4rem',
      }}>
        {items.map(item => {
          const isClickable = item.agentId != null

          return (
            <div
              key={item.id}
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
