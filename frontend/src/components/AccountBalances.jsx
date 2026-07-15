import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const REFRESH_MS = 30000

export default function AccountBalances() {
  const [balances, setBalances] = useState(null)
  const [error, setError] = useState('')

  async function load() {
    try {
      const data = await api.accountBalances()
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

  return (
    <div style={{ marginBottom: 14 }}>
      {balances.demo && (
        <div className="balance-row">
          <span className="balance-lbl">Demo</span>
          <span className="balance-val">
            {balances.demo.error ? '—' : `${balances.demo.balance?.toFixed(2)} ${balances.demo.currency}`}
          </span>
        </div>
      )}
      {balances.real && (
        <div className="balance-row">
          <span className="balance-lbl">Real</span>
          <span className="balance-val real">
            {balances.real.error ? '—' : `${balances.real.balance?.toFixed(2)} ${balances.real.currency}`}
          </span>
        </div>
      )}
      {!balances.demo && !balances.real && (
        <div className="spinner-text">No accounts connected</div>
      )}
    </div>
  )
}
