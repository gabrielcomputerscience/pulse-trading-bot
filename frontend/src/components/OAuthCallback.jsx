import React, { useEffect, useState } from 'react'
import { api, setAuthToken } from '../api.js'

export default function OAuthCallback({ onDone }) {
  const [error, setError] = useState('')

  useEffect(() => {
    async function exchange() {
      const params = new URLSearchParams(window.location.search)
      const errorParam = params.get('error')
      if (errorParam) {
        const description = params.get('error_description') || errorParam
        setError(`Deriv login was not completed: ${description}`)
        return
      }

      const code = params.get('code')
      const state = params.get('state')
      if (!code || !state) {
        setError('No authorization code came back from Deriv. Try Continue with Deriv again.')
        return
      }

      try {
        const res = await api.derivCallback(code, state)
        setAuthToken(res.access_token)
        // Clean the code/state params out of the URL bar before moving on.
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
