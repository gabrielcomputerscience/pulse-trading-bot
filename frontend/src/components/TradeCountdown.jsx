import React, { useEffect, useState } from 'react'

// Deriv doesn't give us a precise tick-based clock, so tick-duration
// contracts show an estimate (labeled as such) rather than a false
// precise countdown. Seconds/minutes contracts get a real countdown.
const TICK_ESTIMATE_SECONDS = 2

export default function TradeCountdown({ openedAt, duration, durationUnit }) {
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  if (!openedAt || !duration || !durationUnit) return null

  const startMs = new Date(openedAt).getTime()
  const unitSeconds = durationUnit === 'm' ? 60 : durationUnit === 's' ? 1 : TICK_ESTIMATE_SECONDS
  const totalMs = duration * unitSeconds * 1000
  const endMs = startMs + totalMs
  const remainingMs = Math.max(0, endMs - now)
  const remainingSec = Math.ceil(remainingMs / 1000)

  const isEstimate = durationUnit === 't'

  if (remainingMs <= 0) {
    return <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>resolving…</span>
  }

  const mins = Math.floor(remainingSec / 60)
  const secs = remainingSec % 60
  const label = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`

  return (
    <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
      {isEstimate ? '~' : ''}{label} left{isEstimate ? ' (est.)' : ''}
    </span>
  )
}
