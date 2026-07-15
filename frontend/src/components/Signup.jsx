import React, { useState } from 'react'
import { api } from '../api.js'

export default function Signup({ onSignedUp, onSwitchToLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Password needs at least 8 characters.')
      return
    }
    setLoading(true)
    try {
      await api.signup(username, password)
      onSignedUp(username)
    } catch (err) {
      setError(err.message)
    } finally {
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
        <p className="auth-sub">Create your console account</p>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} required />
          </div>
          <div className="field">
            <label>Password (min 8 characters)</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? 'Creating…' : 'Create account'}
          </button>
        </form>

        <div className="auth-switch">
          Already have one? <button onClick={onSwitchToLogin}>Sign in</button>
        </div>
      </div>
    </div>
  )
}
