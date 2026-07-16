import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

const REFRESH_MS = 6000
const WIDTH = 900
const HEIGHT = 260
const PAD = 24

export default function PriceChart({ symbol }) {
  const [candles, setCandles] = useState(null)
  const [error, setError] = useState('')
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    setCandles(null)
    setError('')

    async function load() {
      try {
        const data = await api.marketHistory(symbol, 100)
        if (mountedRef.current) setCandles(data)
      } catch (err) {
        if (mountedRef.current) setError(err.message)
      }
    }

    load()
    const id = setInterval(load, REFRESH_MS)
    return () => { mountedRef.current = false; clearInterval(id) }
  }, [symbol])

  if (error) {
    return <div className="empty-state" style={{ height: HEIGHT }}>{error}</div>
  }
  if (!candles || candles.length < 2) {
    return <div className="spinner-text" style={{ padding: '100px 0', textAlign: 'center' }}>Loading chart…</div>
  }

  const closes = candles.map((c) => parseFloat(c.close))
  const min = Math.min(...closes)
  const max = Math.max(...closes)
  const range = max - min || 1
  const first = closes[0]
  const last = closes[closes.length - 1]
  const up = last >= first
  const color = up ? 'var(--success)' : 'var(--danger)'

  const points = closes.map((price, i) => {
    const x = PAD + (i / (closes.length - 1)) * (WIDTH - PAD * 2)
    const y = PAD + (1 - (price - min) / range) * (HEIGHT - PAD * 2)
    return [x, y]
  })

  const linePath = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const areaPath = `${linePath} L${points[points.length - 1][0].toFixed(1)},${HEIGHT - PAD} L${points[0][0].toFixed(1)},${HEIGHT - PAD} Z`

  const gradientId = `chart-grad-${symbol}`

  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} style={{ width: '100%', height: HEIGHT, display: 'block' }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.25" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill={`url(#${gradientId})`} />
        <path d={linePath} fill="none" stroke={color} strokeWidth="1.75" />
        <circle cx={points[points.length - 1][0]} cy={points[points.length - 1][1]} r="3.5" fill={color} />
        <text
          x={points[points.length - 1][0] - 6}
          y={points[points.length - 1][1] - 10}
          textAnchor="end"
          fill={color}
          fontSize="12"
          fontFamily="var(--font-mono)"
        >
          {last.toFixed(closes[0] < 10 ? 4 : 2)}
        </text>
      </svg>
    </div>
  )
}
