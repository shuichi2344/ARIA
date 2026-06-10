'use client'

import { useState } from 'react'
import type { SparkRecord } from './types'

const TEMPLATE_META: Record<string, { label: string; icon: string }> = {
  competitive_context: { label: 'Competitive Context', icon: '⚔️' },
  location_context: { label: 'Location Context', icon: '📍' },
  business_hours_seasonality: { label: 'Hours & Seasonality', icon: '🕐' },
}

interface SparkPickerProps {
  userId: string
  sessionId: string | null
  activeSpark: SparkRecord | null
  savedSparks: SparkRecord[]
  simulationStatus: 'idle' | 'running' | 'paused' | 'done'
  onSelectTemplate: (templateId: string) => void
  onActivateSpark: (sparkId: string) => void
  onDeactivateSpark: () => void
  onDeleteSpark: (sparkId: string) => void
}

export default function SparkPicker({
  userId, sessionId, activeSpark, savedSparks, simulationStatus,
  onSelectTemplate, onActivateSpark, onDeactivateSpark, onDeleteSpark,
}: SparkPickerProps) {
  const isDisabled = simulationStatus === 'running' || simulationStatus === 'paused'
  const [showTemplates, setShowTemplates] = useState(false)

  // State 1: No saved sparks → show template cards
  if (savedSparks.length === 0 && !showTemplates) {
    return (
      <div style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--gray-200)', background: 'var(--white)' }}>
        <p style={{ margin: '0 0 0.4rem', fontSize: '0.7rem', fontWeight: 600, color: 'var(--gray-500)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Add Context Spark
        </p>
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {Object.entries(TEMPLATE_META).map(([id, meta]) => (
            <button
              key={id}
              onClick={() => !isDisabled && onSelectTemplate(id)}
              disabled={isDisabled}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.3rem',
                padding: '0.3rem 0.6rem', borderRadius: 6,
                border: '1px solid var(--gray-300)',
                background: 'var(--gray-50)',
                fontSize: '0.75rem', fontWeight: 500, color: 'var(--gray-700)',
                cursor: isDisabled ? 'not-allowed' : 'pointer',
                opacity: isDisabled ? 0.5 : 1,
                transition: 'all 0.15s',
              }}
            >
              <span>{meta.icon}</span>
              <span>+ {meta.label}</span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  // State 2/3/4: Has saved sparks (or showing template picker)
  return (
    <div style={{ padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--gray-200)', background: 'var(--white)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
        {/* Spark pills */}
        {savedSparks.map(spark => {
          const isActive = activeSpark?.spark_id === spark.spark_id
          return (
            <div
              key={spark.spark_id}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.3rem',
                padding: '0.2rem 0.5rem', borderRadius: 999,
                border: `1.5px solid ${isActive ? '#0d9488' : 'var(--gray-300)'}`,
                background: isActive ? '#f0fdfa' : 'var(--gray-50)',
                fontSize: '0.75rem', fontWeight: isActive ? 700 : 500,
                color: isActive ? '#0d9488' : 'var(--gray-700)',
              }}
            >
              {isActive && <span style={{ fontSize: '0.6rem' }}>●</span>}
              <button
                onClick={() => !isDisabled && !isActive && onActivateSpark(spark.spark_id)}
                style={{
                  background: 'none', border: 'none', padding: 0,
                  cursor: isDisabled || isActive ? 'default' : 'pointer',
                  color: 'inherit', fontWeight: 'inherit', fontSize: 'inherit',
                }}
              >
                {spark.name}
                {isActive && <span style={{ marginLeft: '0.25rem', fontSize: '0.65rem' }}>Active</span>}
              </button>
              {/* Deactivate button when active */}
              {isActive && (
                <button
                  onClick={() => !isDisabled && onDeactivateSpark()}
                  disabled={isDisabled}
                  title="Deactivate"
                  style={{
                    background: 'none', border: 'none', cursor: isDisabled ? 'not-allowed' : 'pointer',
                    padding: '0 0.1rem', color: '#0d9488', fontSize: '0.7rem',
                  }}
                >
                  ✕
                </button>
              )}
              {/* Delete button when not active */}
              {!isActive && (
                <button
                  onClick={() => !isDisabled && onDeleteSpark(spark.spark_id)}
                  disabled={isDisabled}
                  title="Delete spark"
                  style={{
                    background: 'none', border: 'none',
                    cursor: isDisabled ? 'not-allowed' : 'pointer',
                    padding: '0 0.1rem', color: 'var(--gray-400)', fontSize: '0.65rem',
                  }}
                >
                  🗑
                </button>
              )}
            </div>
          )
        })}

        {/* No spark active indicator */}
        {!activeSpark && savedSparks.length > 0 && (
          <span style={{ fontSize: '0.7rem', color: 'var(--gray-400)', fontStyle: 'italic' }}>
            No spark active
          </span>
        )}

        {/* New Spark + button / template picker */}
        {showTemplates ? (
          <>
            {Object.entries(TEMPLATE_META).map(([id, meta]) => (
              <button
                key={id}
                onClick={() => { setShowTemplates(false); !isDisabled && onSelectTemplate(id) }}
                disabled={isDisabled}
                style={{
                  padding: '0.2rem 0.5rem', borderRadius: 6,
                  border: '1px dashed var(--gray-400)',
                  background: 'white', fontSize: '0.72rem',
                  cursor: isDisabled ? 'not-allowed' : 'pointer',
                  color: 'var(--gray-600)', opacity: isDisabled ? 0.5 : 1,
                }}
              >
                {meta.icon} {meta.label}
              </button>
            ))}
            <button
              onClick={() => setShowTemplates(false)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.75rem', color: 'var(--gray-500)' }}
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            onClick={() => !isDisabled && setShowTemplates(true)}
            disabled={isDisabled}
            style={{
              padding: '0.2rem 0.5rem', borderRadius: 6,
              border: '1px dashed var(--gray-400)',
              background: 'white', fontSize: '0.72rem',
              cursor: isDisabled ? 'not-allowed' : 'pointer',
              color: 'var(--gray-600)', opacity: isDisabled ? 0.5 : 1,
            }}
          >
            + New Spark
          </button>
        )}
      </div>
    </div>
  )
}
