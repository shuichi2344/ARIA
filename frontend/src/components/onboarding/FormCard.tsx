interface Props {
  title: string
  children: React.ReactNode
}

export default function FormCard({ title, children }: Props) {
  return (
    <div style={{
      background: 'white',
      borderRadius: 16,
      padding: '2rem',
      boxShadow: '0 8px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.08)',
      border: '1px solid var(--gray-200)',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Top accent bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 4,
        background: 'linear-gradient(90deg, var(--accent), var(--accent-light))',
        borderRadius: '16px 16px 0 0',
      }} />
      <h2 style={{
        fontSize: '1.5rem', fontWeight: 700, color: 'var(--primary)',
        marginBottom: '1rem', paddingBottom: '0.5rem',
        borderBottom: '2px solid var(--gray-100)',
        display: 'flex', alignItems: 'center', gap: '0.75rem',
      }}>
        {title}
      </h2>
      {children}
    </div>
  )
}
