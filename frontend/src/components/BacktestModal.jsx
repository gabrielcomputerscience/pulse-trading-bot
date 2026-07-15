import React, { useState } from 'react'
import { api } from '../api.js'

export default function BacktestModal({ bot, onClose }) {
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [lookback, setLookback] = useState(3000)

  async function runBacktest() {
    setError('')
    setLoading(true)
    setResult(null)
    try {
      const res = await api.backtestBot(bot.id, { lookback_candles: parseInt(lookback, 10), assumed_payout_ratio: 0.85 })
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Backtest — {bot.name}</h3>
        <div className="info-banner">
          Runs the strategy against real historical candles pulled from Deriv for {bot.asset}.
          This is a measured result, not a promise about future performance.
        </div>

        {error && <div className="error-banner">{error}</div>}

        <div className="field">
          <label>Lookback candles</label>
          <input type="number" min="200" value={lookback} onChange={(e) => setLookback(e.target.value)} />
        </div>

        <button className="btn btn-primary" onClick={runBacktest} disabled={loading} style={{ width: '100%' }}>
          {loading ? 'Running backtest…' : 'Run backtest'}
        </button>

        {result && (
          <>
            <div className="metric-grid">
              <div className="metric">
                <div className="metric-label">Win rate</div>
                <div className="metric-value">{(result.win_rate * 100).toFixed(1)}%</div>
              </div>
              <div className="metric">
                <div className="metric-label">Total trades</div>
                <div className="metric-value">{result.total_trades}</div>
              </div>
              <div className="metric">
                <div className="metric-label">Net P/L (sim.)</div>
                <div className={`metric-value ${result.total_profit_loss >= 0 ? 'positive' : 'negative'}`}>
                  {result.total_profit_loss >= 0 ? '+' : ''}{result.total_profit_loss}
                </div>
              </div>
              <div className="metric">
                <div className="metric-label">Max drawdown</div>
                <div className="metric-value negative">{result.max_drawdown}</div>
              </div>
            </div>
            <div className="strategy-desc">{result.disclaimer}</div>
          </>
        )}

        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose} style={{ flex: 1 }}>Close</button>
        </div>
      </div>
    </div>
  )
}
