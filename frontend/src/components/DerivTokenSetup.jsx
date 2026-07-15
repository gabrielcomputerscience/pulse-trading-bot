import React, { useState } from 'react'
import { api } from '../api.js'

export default function DerivTokenSetup({ onDone }) {
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.setDerivToken(token)
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card" style={{ width: 440 }}>
        <div className="auth-brand">
          <span className="dot" />
          <h1>Pulse</h1>
        </div>
        <p className="auth-sub">Link your Deriv account</p>

        <div className="info-banner">
          Generate a fresh token at Deriv → Settings → API Token, scoped to
          <strong> Read + Trade only</strong> (leave out Payments/Withdraw). It's stored
          encrypted and is never shown again after this screen.
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Deriv API token</label>
            <input
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="paste your token"
              required
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? 'Saving…' : 'Save & continue'}
          </button>
        </form>
      </div>
    </div>
  )
}
