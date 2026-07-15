import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function BacktestLabPage() {
  const [strategies, setStrategies] = useState([])
  const [martingale, setMartingale] = useState(null)
  const [strategy, setStrategy] = useState('')
  const [asset, setAsset] = useState('R_75')
  const [stake, setStake] = useState(1)
  const [lookback, setLookback] = useState(3000)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.listStrategies().then((list) => {
      setStrategies(list)
      if (list.length) setStrategy(list[0].name)
    })
    api.martingaleInfo().then(setMartingale)
  }, [])

  const allStrategies = martingale ? [...strategies, martingale] : strategies
  const selected = allStrategies.find((s) => s.name === strategy)

  async function runBacktest(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const res = await api.freeformBacktest({
        strategy, asset, base_stake: parseFloat(stake),
        lookback_candles: parseInt(lookback, 10), assumed_payout_ratio: 0.85,
      })
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="disclaimer">
        <span>&#9432;</span>
        <span>
          Runs against <b>real historical candles pulled live from Deriv</b> for the asset you
          choose. Whatever win rate comes out is measured, not assumed — and still isn't a
          promise about future performance.
        </span>
      </div>

      <div className="page-panel">
        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={runBacktest}>
          <div className="field">
            <label>Strategy</label>
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
              {allStrategies.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}{s.risk_label === 'high_risk' ? ' (high risk)' : ''}
                </option>
              ))}
            </select>
            {selected && <div className="strategy-desc">{selected.description}</div>}
          </div>

          <div className="form-row">
            <div className="field">
              <label>Asset symbol</label>
              <input value={asset} onChange={(e) => setAsset(e.target.value)} placeholder="R_75, BOOM1000…" required />
            </div>
            <div className="field">
              <label>Base stake</label>
              <input type="number" step="0.01" min="0.01" value={stake} onChange={(e) => setStake(e.target.value)} required />
            </div>
          </div>

          <div className="field">
            <label>Lookback candles</label>
            <input type="number" min="200" value={lookback} onChange={(e) => setLookback(e.target.value)} />
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Running backtest…' : 'Run backtest'}
          </button>
        </form>
      </div>

      {result && (
        <>
          <div className="section-head"><h2>Results — {result.strategy}, {result.symbol}</h2></div>
          <div className="page-panel">
            <table className="bt-table">
              <tbody>
                <tr><th>Total trades</th><td>{result.total_trades}</td></tr>
                <tr><th>Win rate</th><td style={{ color: 'var(--success)' }}>{(result.win_rate * 100).toFixed(1)}%</td></tr>
                <tr><th>Wins / Losses</th><td>{result.wins} / {result.losses}</td></tr>
                <tr><th>Net P/L (simulated)</th>
                  <td style={{ color: result.total_profit_loss >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                    {result.total_profit_loss >= 0 ? '+' : ''}{result.total_profit_loss}
                  </td>
                </tr>
                <tr><th>Max drawdown</th><td style={{ color: 'var(--danger)' }}>{result.max_drawdown}</td></tr>
              </tbody>
            </table>
            <div className="disclaimer" style={{ marginTop: 16 }}>
              <span>&#9432;</span>
              <span>{result.disclaimer}</span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
