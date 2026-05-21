interface Props {
  step: number
  labels: string[]
}

export default function ProgressBar({ step, labels }: Props) {
  const total = labels.length
  const progressPct = ((step - 1) / (total - 1)) * 100

  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between',
      maxWidth: 700, margin: '1.5rem auto 2rem',
      position: 'relative', padding: '1.5rem',
      background: 'white', borderRadius: 16,
    }}>
      {/* Track */}
      <div style={{
        position: 'absolute',
        top: 'calc(1.5rem + 24px)',
        left: 'calc(12.5% + 1.5rem)',
        right: 'calc(12.5% + 1.5rem)',
        height: 3, background: 'var(--gray-200)', zIndex: 0,
      }} />
      {/* Fill */}
      <div style={{
        position: 'absolute',
        top: 'calc(1.5rem + 24px)',
        left: 'calc(12.5% + 1.5rem)',
        height: 3,
        background: 'var(--accent)',
        zIndex: 1,
        width: `calc(${progressPct}% * 0.75)`,
        transition: 'width 0.5s cubic-bezier(0.16,1,0.3,1)',
      }} />

      {labels.map((label, i) => {
        const n      = i + 1
        const done   = n < step
        const active = n === step
        return (
          <div key={label} style={{
            flex: 1, textAlign: 'center', position: 'relative', zIndex: 2,
          }}>
            <div style={{
              width: 48, height: 48, borderRadius: '50%',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 600, fontSize: '0.9rem',
              marginBottom: '0.5rem',
              border: '3px solid white',
              boxShadow: active ? '0 4px 16px rgba(0,0,0,0.2)' : '0 2px 8px rgba(0,0,0,0.1)',
              background: done   ? '#10b981'
                        : active ? 'var(--accent)'
                        : 'var(--gray-200)',
              color: (done || active) ? 'white' : 'var(--gray-700)',
              transform: active ? 'scale(1.15)' : 'scale(1)',
              transition: 'all 0.3s cubic-bezier(0.16,1,0.3,1)',
            }}>
              {done ? '✓' : n}
            </div>
            <div style={{
              fontSize: '0.875rem', fontWeight: active ? 600 : 500,
              color: active ? 'var(--accent)' : done ? '#10b981' : 'var(--gray-700)',
              display: 'block',
            }}>
              {label}
            </div>
          </div>
        )
      })}
    </div>
  )
}
