import React, { useEffect, useRef, useState } from 'react'
import { api, setAuthToken } from '../api.js'

export default function OAuthCallback({ onDone }) {
  const [error, setError] = useState('')
  const startedRef = useRef(false) // guards against double-submitting the same code

  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true

    async function exchange() {
      const params = new URLSearchParams(window.location.search)
      const errorParam = params.get('error')
      if (errorParam) {
        const description = params.get('error_description') || errorParam
        window.history.replaceState({}, '', '/')
        setError(`Deriv login was not completed: ${description}`)
        return
      }

      const code = params.get('code')
      const state = params.get('state')
      if (!code || !state) {
        setError('No authorization code came back from Deriv. Try Continue with Deriv again.')
        return
      }

      // Clear code/state from the URL immediately, before the exchange —
      // an authorization code is single-use, so if this tab gets reloaded
      // mid-request we must not resubmit the same code to Deriv.
      window.history.replaceState({}, '', '/')

      try {
        const res = await api.derivCallback(code, state)
        setAuthToken(res.access_token)
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
