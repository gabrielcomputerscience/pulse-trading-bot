import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

const REFRESH_MS = 8000 // fast enough to feel live without hammering the API

function formatBalance(raw) {
  const num = parseFloat(raw)
  return Number.isFinite(num) ? num.toFixed(2) : null
}

export default function AccountBalances() {
  const [balances, setBalances] = useState(null)
  const [error, setError] = useState('')
  const [deltas, setDeltas] = useState({ demo: null, real: null })
  const prevRef = useRef({ demo: null, real: null })

  async function load() {
    try {
      const data = await api.accountBalances()
      const newDeltas = { demo: null, real: null }

      for (const mode of ['demo', 'real']) {
        const raw = data[mode]?.balance
        const num = formatBalance(raw)
        if (num !== null && prevRef.current[mode] !== null) {
          const diff = parseFloat(num) - prevRef.current[mode]
          if (Math.abs(diff) > 0.0001) newDeltas[mode] = diff
        }
        if (num !== null) prevRef.current[mode] = parseFloat(num)
      }

      setDeltas(newDeltas)
      setBalances(data)
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, REFRESH_MS)
    return () => clearInterval(id)
  }, [])

  if (error) return null // sidebar stays quiet on transient errors, no need to alarm
  if (!balances) return <div className="spinner-text">Loading balances…</div>

  function renderRow(mode, label, cssClass) {
    const acct = balances[mode]
    if (!acct) return null
    const formatted = formatBalance(acct.balance)
    const delta = deltas[mode]

    return (
      <div className="balance-row">
        <span className="balance-lbl">{label}</span>
        <span className={`balance-val ${cssClass}`}>
          {acct.error ? '—' : `${formatted ?? '—'} ${acct.currency}`}
          {delta !== null && (
            <span style={{
              marginLeft: 6, fontSize: 10.5,
              color: delta >= 0 ? 'var(--success)' : 'var(--danger)',
            }}>
              {delta >= 0 ? '+' : ''}{delta.toFixed(2)}
            </span>
          )}
        </span>
      </div>
    )
  }

  return (
    <div style={{ marginBottom: 14 }}>
      {renderRow('demo', 'Demo', '')}
      {renderRow('real', 'Real', 'real')}
      {!balances.demo && !balances.real && (
        <div className="spinner-text">No accounts connected</div>
      )}
    </div>
  )
}
