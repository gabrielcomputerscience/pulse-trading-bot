import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { setAuthToken } from '../api.js'

export default function OAuthCallback({ onDone }) {
  const [error, setError] = useState('')

  useEffect(() => {
    async function exchange() {
      const queryString = window.location.search.replace(/^\?/, '')
      if (!queryString) {
        setError('No account data came back from Deriv. Try Continue with Deriv again.')
        return
      }
      try {
        const res = await api.derivCallback(queryString)
        setAuthToken(res.access_token)
        // Clean the token/account params out of the URL bar before moving on.
        window.history.replaceState({}, '', '/')
        onDone(res)
      } catch (err) {
        setError(err.message)
      }
    }
    exchange()
  }, [])

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="dot" />
          <h1>Pulse</h1>
        </div>
        {error ? (
          <>
            <div className="error-banner">{error}</div>
            <button className="btn btn-ghost" onClick={() => { window.location.href = '/' }} style={{ width: '100%' }}>
              Back to sign in
            </button>
          </>
        ) : (
          <p className="auth-sub">Connecting your Deriv account…</p>
        )}
      </div>
    </div>
  )
}
