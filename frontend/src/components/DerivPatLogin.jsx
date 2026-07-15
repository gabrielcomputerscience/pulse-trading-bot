import React, { useState } from 'react'
import { api, setAuthToken } from '../api.js'

export default function DerivPatLogin({ onLoggedIn }) {
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await api.derivPatLogin(token)
      setAuthToken(res.access_token)
      setToken('')
      onLoggedIn(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card" style={{ width: 420 }}>
        <div className="auth-brand">
          <span className="dot" />
          <h1>Pulse</h1>
        </div>
        <p className="auth-sub">AI bot terminal for Deriv</p>

        <div className="info-banner">
          Generate a Personal Access Token at Deriv → Settings → API Token, scoped to
          <strong> Read + Trade only</strong> (leave out Payments/Withdraw). Paste it below —
          it's encrypted at rest and this is the only screen that ever sees it.
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Deriv API token</label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="paste your token"
              required
              autoFocus
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Connecting…' : 'Connect to Deriv'}
          </button>
        </form>

        <p style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 14, fontFamily: 'var(--font-mono)', lineHeight: 1.5 }}>
          Have both a demo and a real account? Log in with one token now — you can link the
          other from the sidebar afterward.
        </p>
      </div>
    </div>
  )
}
