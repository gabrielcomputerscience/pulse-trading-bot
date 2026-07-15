import React, { useState } from 'react'
import { api } from '../api.js'

export default function AddAccountModal({ onClose, onLinked }) {
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.derivPatAddAccount(token)
      onLinked()
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Link another account</h3>
        <div className="info-banner">
          Paste a token from your other Deriv account (e.g. your real account, if you logged in
          with demo first). It must belong to the same Deriv login as your current session.
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
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Linking…' : 'Link account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
