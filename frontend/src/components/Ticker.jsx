import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const REFRESH_MS = 20000

export default function Ticker() {
  const [entries, setEntries] = useState([])

  async function load() {
    try {
      const data = await api.marketTicker()
      setEntries(data.filter((e) => e.price !== null))
    } catch (_) {
      // Ticker is decorative context, not critical path — fail silently
      // rather than throwing an error banner over the whole page.
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, REFRESH_MS)
    return () => clearInterval(id)
  }, [])

  if (entries.length === 0) {
    return (
      <div className="ticker-wrap">
        <span className="spinner-text" style={{ paddingLeft: 20 }}>Loading live quotes…</span>
      </div>
    )
  }

  const doubled = [...entries, ...entries]

  return (
    <div className="ticker-wrap">
      <div className="ticker-track">
        {doubled.map((e, i) => (
          <div className="tick" key={`${e.symbol}-${i}`}>
            <span className="tick-name">{e.name}</span>
            <span className="tick-val">{e.price}</span>
            <span className={`tick-chg ${e.change_pct >= 0 ? 'up' : 'down'}`}>
              {e.change_pct >= 0 ? '+' : ''}{e.change_pct}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
