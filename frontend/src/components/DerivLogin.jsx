import React, { useState } from 'react'
import { api } from '../api.js'

export default function DerivLogin() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleContinue() {
    setError('')
    setLoading(true)
    try {
      const { url } = await api.derivLoginUrl()
      window.location.href = url
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="dot" />
          <h1>Pulse</h1>
        </div>
        <p className="auth-sub">AI bot terminal for Deriv</p>

        {error && <div className="error-banner">{error}</div>}

        <div className="info-banner">
          No separate account to create. Sign in with your Deriv login and Pulse sees your
          real and demo balances directly — nothing is typed or pasted here.
        </div>

        <button className="btn btn-primary" onClick={handleContinue} disabled={loading} style={{ width: '100%' }}>
          {loading ? 'Redirecting…' : 'Continue with Deriv'}
        </button>
      </div>
    </div>
  )
}
