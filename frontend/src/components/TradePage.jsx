import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const COMMON_ASSETS = [
  { symbol: 'R_75', name: 'Volatility 75' },
  { symbol: 'R_100', name: 'Volatility 100' },
  { symbol: 'R_50', name: 'Volatility 50' },
  { symbol: 'BOOM1000', name: 'Boom 1000' },
  { symbol: 'CRASH1000', name: 'Crash 1000' },
  { symbol: 'stpRNG', name: 'Step Index' },
  { symbol: 'JD25', name: 'Jump 25' },
]

export default function TradePage() {
  const [mode, setMode] = useState('demo')
  const [symbol, setSymbol] = useState('R_75')
  const [stake, setStake] = useState(1)
  const [duration, setDuration] = useState(5)
  const [durationUnit, setDurationUnit] = useState('t')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [lastResult, setLastResult] = useState(null)
  const [history, setHistory] = useState(null)

  async function loadHistory() {
    try {
      const h = await api.manualTradeHistory()
      setHistory(h)
    } catch (_) {
      // non-critical, silently retry next refresh
    }
  }

  useEffect(() => { loadHistory() }, [])

  async function placeTrade(direction) {
    setError('')
    setBusy(true)
    try {
      const res = await api.executeManualTrade({
        mode, symbol, direction,
        stake: parseFloat(stake),
        duration: parseInt(duration, 10),
        duration_unit: durationUnit,
      })
      setLastResult({ direction, ...res })
      loadHistory()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="disclaimer">
        <span>&#9432;</span>
        <span>
          Instant Rise/Fall trades — no strategy warm-up, executes immediately at the current
          price. This is manual trading, separate from your automated bots. Only Rise/Fall is
          available right now; more contract types are coming once verified against Deriv's
          current API.
        </span>
      </div>

      <div className="page-panel" style={{ maxWidth: 480 }}>
        <div className="field">
          <label>Account</label>
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="demo">Demo</option>
            <option value="real">Real</option>
          </select>
        </div>

        <div className="field">
          <label>Asset</label>
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
            {COMMON_ASSETS.map((a) => (
              <option key={a.symbol} value={a.symbol}>{a.name} ({a.symbol})</option>
            ))}
          </select>
        </div>

        <div className="form-row">
          <div className="field">
            <label>Stake</label>
            <input type="number" step="0.01" min="0.01" value={stake} onChange={(e) => setStake(e.target.value)} />
          </div>
          <div className="field">
            <label>Duration</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input type="number" min="1" value={duration} onChange={(e) => setDuration(e.target.value)} style={{ flex: 1 }} />
              <select value={durationUnit} onChange={(e) => setDurationUnit(e.target.value)} style={{ width: 90 }}>
                <option value="t">ticks</option>
                <option value="s">sec</option>
                <option value="m">min</option>
              </select>
            </div>
          </div>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
          <button
            className="btn"
            onClick={() => placeTrade('rise')}
            disabled={busy}
            style={{ flex: 1, background: 'var(--success)', color: '#06231a', fontWeight: 700, padding: '14px 0', fontSize: 15 }}
          >
            {busy ? '…' : '▲ Rise'}
          </button>
          <button
            className="btn"
            onClick={() => placeTrade('fall')}
            disabled={busy}
            style={{ flex: 1, background: 'var(--danger)', color: '#2a0a0a', fontWeight: 700, padding: '14px 0', fontSize: 15 }}
          >
            {busy ? '…' : '▼ Fall'}
          </button>
        </div>

        {lastResult && (
          <div className="info-banner" style={{ marginTop: 16, borderColor: lastResult.direction === 'rise' ? 'var(--success)' : 'var(--danger)' }}>
            Bought {lastResult.direction === 'rise' ? 'Rise' : 'Fall'} on {symbol} — stake {lastResult.buy_price},
            potential payout {lastResult.payout}. {lastResult.longcode}
          </div>
        )}
      </div>

      <div className="section-head"><h2>Recent manual trades</h2></div>
      {!history && <div className="spinner-text">Loading…</div>}
      {history && history.length === 0 && (
        <div className="empty-state">No manual trades yet — place one above.</div>
      )}
      {history && history.length > 0 && (
        <table className="trades">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Type</th>
              <th>Stake</th>
              <th>P/L</th>
              <th>Mode</th>
              <th>Opened</th>
            </tr>
          </thead>
          <tbody>
            {history.map((t) => (
              <tr key={t.id}>
                <td>{t.symbol}</td>
                <td>{t.type}</td>
                <td>{t.stake}</td>
                <td className={t.profit_loss > 0 ? 'positive' : t.profit_loss < 0 ? 'negative' : ''}>
                  {t.profit_loss ?? '—'}
                </td>
                <td>{t.is_demo ? 'demo' : 'real'}</td>
                <td>{new Date(t.opened_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
