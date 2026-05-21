import type { CSSProperties } from 'react'

export const input: CSSProperties = {
  width: '100%',
  padding: '0.875rem 1.125rem',
  fontFamily: 'var(--font-family)',
  fontSize: '1rem',
  borderWidth: '2px',
  borderStyle: 'solid',
  borderColor: 'var(--gray-200)',
  borderRadius: 10,
  background: 'var(--gray-50)',
  color: 'var(--gray-900)',
  outline: 'none',
  transition: 'all 0.3s cubic-bezier(0.16,1,0.3,1)',
  boxSizing: 'border-box',
}

export const inputError: CSSProperties = {
  ...input,
  borderColor: '#dc2626',
  background: 'rgba(220,38,38,0.05)',
}

export const label: CSSProperties = {
  display: 'block',
  fontSize: '0.9375rem',
  fontWeight: 600,
  color: 'var(--gray-900)',
  marginBottom: '0.5rem',
}

export const helpText: CSSProperties = {
  display: 'block',
  fontSize: '0.875rem',
  color: 'var(--gray-600)',
  marginTop: '0.5rem',
}

export const errorText: CSSProperties = {
  display: 'block',
  fontSize: '0.875rem',
  color: '#dc2626',
  marginTop: '0.5rem',
  fontWeight: 500,
}

export const formGroup: CSSProperties = {
  marginBottom: '1rem',
  position: 'relative',
}

export const formActions: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  gap: '1rem',
  marginTop: '1.5rem',
  paddingTop: '1.25rem',
  borderTop: '2px solid var(--gray-100)',
}

export const btnPrimary: CSSProperties = {
  flex: 1,
  background: 'var(--primary)',
  color: 'white',
  fontWeight: 600,
  padding: '1rem 2rem',
  borderWidth: 0,
  borderStyle: 'solid',
  borderColor: 'transparent',
  borderRadius: 8,
  cursor: 'pointer',
  fontSize: '1rem',
  fontFamily: 'var(--font-family)',
  transition: 'all 0.3s cubic-bezier(0.16,1,0.3,1)',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '0.5rem',
}

export const btnSecondary: CSSProperties = {
  flex: 1,
  background: 'white',
  color: 'var(--gray-900)',
  fontWeight: 600,
  padding: '1rem 2rem',
  borderWidth: '2px',
  borderStyle: 'solid',
  borderColor: 'var(--gray-300)',
  borderRadius: 8,
  cursor: 'pointer',
  fontSize: '1rem',
  fontFamily: 'var(--font-family)',
  transition: 'all 0.3s cubic-bezier(0.16,1,0.3,1)',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '0.5rem',
}
