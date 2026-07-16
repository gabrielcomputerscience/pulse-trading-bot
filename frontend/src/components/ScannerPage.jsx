import React, { useState } from 'react'
import { api } from '../api.js'

export default function ScannerPage() {
  const [stake, setStake] = useState(1)
  const [stopLoss, setStopLoss] = useState('')
  const [takeProfit, setTakeProfit] = useState('')
  const [maxDailyLoss, setMaxDailyLoss] = useState('')
  const [lookback, setLookback] = useState(3000)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [launching, setLaunching] = useState(null)
  const [launchMessage, setLaunchMessage] = useState('')

  async function runScan(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    setLaunchMessage('')
    setScanning(true)
    try {
      const res = await api.runScan({
        base_stake: parseFloat(stake),
        lookback_candles: parseInt(lookback, 10),
      })
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setScanning(false)
    }
  }

  async function launch(candidate) {
    const key = `${candidate.strategy}-${candidate.symbol}`
    setLaunching(key)
    setError('')
    try {
      await api.launchScanResult({
        strategy: candidate.strategy,
        asset: candidate.symbol,
        stake: parseFloat(stake),
        stop_loss: stopLoss ? parseFloat(stopLoss) : null,
        take_profit: takeProfit ? parseFloat(takeProfit) : null,
        max_daily_loss: maxDailyLoss ? parseFloat(maxDailyLoss) : null,
      })
      setLaunchMessage(`Launched "${candidate.strategy} / ${candidate.symbol}" on demo — check My Bots.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLaunching(null)
    }
  }

  return (
    <div>
      <div className="disclaimer">
        <span>&#9432;</span>
        <span>
          This runs real backtests across every recommended strategy and a curated set of
          assets, then ranks them by actual measured results. It's systematic backtesting, not
          an AI predicting the market — a "winner" here measured well on recent historical
          data, which is not a guarantee it keeps working. Martingale is never included.
        </span>
      </div>

      <div className="page-panel">
        {error && <div className="error-banner">{error}</div>}
        {launchMessage && (
          <div className="info-banner" style={{ borderColor: 'var(--success)', color: '#9de8cd' }}>
            {launchMessage}
          </div>
        )}

        <form onSubmit={runScan}>
          <div className="form-row">
            <div className="field">
              <label>Stake</label>
              <input type="number" step="0.01" min="0.01" value={stake} onChange={(e) => setStake(e.target.value)} required />
            </div>
            <div className="field">
              <label>Lookback candles</label>
              <input type="number" min="200" value={lookback} onChange={(e) => setLookback(e.target.value)} />
            </div>
          </div>

          <div className="form-row">
            <div className="field">
              <label>Stop loss (optional)</label>
              <input type="number" step="0.01" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} />
            </div>
            <div className="field">
              <label>Take profit (optional)</label>
              <input type="number" step="0.01" value={takeProfit} onChange={(e) => setTakeProfit(e.target.value)} />
            </div>
          </div>

          <div className="field">
            <label>Max daily loss (optional)</label>
            <input type="number" step="0.01" value={maxDailyLoss} onChange={(e) => setMaxDailyLoss(e.target.value)} />
          </div>

          <button type="submit" className="btn btn-primary" disabled={scanning} style={{ width: '100%' }}>
            {scanning ? 'Scanning strategies × assets…' : 'Scan for the best current combo'}
          </button>
        </form>
      </div>

      {result && (
        <>
          {result.top_pick ? (
            <>
              <div className="section-head"><h2>Top pick</h2></div>
              <div className="page-panel" style={{ borderColor: 'var(--success)' }}>
                <div className="metric-grid">
                  <div className="metric">
                    <div className="metric-label">Strategy / Asset</div>
                    <div className="metric-value" style={{ fontSize: 16 }}>
                      {result.top_pick.strategy} / {result.top_pick.symbol}
                    </div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">Win rate</div>
                    <div className="metric-value">{(result.top_pick.win_rate * 100).toFixed(1)}%</div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">Net P/L (sim.)</div>
                    <div className="metric-value positive">+{result.top_pick.total_profit_loss}</div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">Trades / Drawdown</div>
                    <div className="metric-value" style={{ fontSize: 16 }}>
                      {result.top_pick.total_trades} / {result.top_pick.max_drawdown}
                    </div>
                  </div>
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => launch(result.top_pick)}
                  disabled={launching !== null}
                  style={{ width: '100%', marginTop: 8 }}
                >
                  {launching === `${result.top_pick.strategy}-${result.top_pick.symbol}`
                    ? 'Launching…' : 'Launch this on demo'}
                </button>
              </div>
            </>
          ) : (
            <div className="empty-state">{result.note}</div>
          )}

          {result.ranked.length > 1 && (
            <>
              <div className="section-head"><h2>All results, ranked</h2></div>
              <table className="bt-table">
                <thead>
                  <tr>
                    <th>Strategy</th>
                    <th>Asset</th>
                    <th>Trades</th>
                    <th>Win rate</th>
                    <th>Net P/L</th>
                    <th>Drawdown</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {result.ranked.map((c) => {
                    const key = `${c.strategy}-${c.symbol}`
                    return (
                      <tr key={key}>
                        <td>{c.strategy}</td>
                        <td>{c.symbol}</td>
                        <td>{c.total_trades}</td>
                        <td>{(c.win_rate * 100).toFixed(1)}%</td>
                        <td style={{ color: c.total_profit_loss >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                          {c.total_profit_loss >= 0 ? '+' : ''}{c.total_profit_loss}
                        </td>
                        <td style={{ color: 'var(--danger)' }}>{c.max_drawdown}</td>
                        <td>
                          <button
                            className="btn btn-ghost"
                            onClick={() => launch(c)}
                            disabled={launching !== null}
                            style={{ padding: '5px 10px', fontSize: 11.5 }}
                          >
                            {launching === key ? '…' : 'Launch'}
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </>
          )}

          {result.insufficient_data.length > 0 && (
            <>
              <div className="section-head"><h2>Not enough trades to judge</h2></div>
              <div className="strategy-desc" style={{ marginBottom: 12 }}>
                These fired too rarely in this window to mean anything — not a fail, just inconclusive.
              </div>
              <table className="bt-table">
                <tbody>
                  {result.insufficient_data.map((c) => (
                    <tr key={`${c.strategy}-${c.symbol}`}>
                      <th>{c.strategy} / {c.symbol}</th>
                      <td>{c.total_trades} trade{c.total_trades === 1 ? '' : 's'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </>
      )}
    </div>
  )
}
