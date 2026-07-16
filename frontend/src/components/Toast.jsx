import React, { useEffect } from 'react'

export default function Toast({ toasts, onDismiss }) {
  return (
    <div style={{
      position: 'fixed', top: 20, right: 20, zIndex: 100,
      display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={() => onDismiss(t.id)} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onDismiss }) {
  useEffect(() => {
    const id = setTimeout(onDismiss, 6000)
    return () => clearTimeout(id)
  }, [])

  const won = toast.profitLoss > 0

  return (
    <div
      style={{
        minWidth: 260,
        background: 'var(--surface)',
        border: `1px solid ${won ? 'var(--success)' : 'var(--danger)'}`,
        borderRadius: 8,
        padding: '14px 16px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        cursor: 'pointer',
      }}
      onClick={onDismiss}
    >
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600,
        color: won ? 'var(--success)' : 'var(--danger)', marginBottom: 4,
      }}>
        {won ? '▲ Trade won' : '▼ Trade lost'}
      </div>
      <div style={{ fontSize: 12.5, color: 'var(--text-dim)' }}>
        {toast.symbol} — {won ? '+' : ''}{toast.profitLoss.toFixed(2)} {toast.source ? `(${toast.source})` : ''}
      </div>
    </div>
  )
}
