import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function AutopilotPage() {
  const [status, setStatus] = useState(null)
  const [minWinRate, setMinWinRate] = useState(60)
  const [minTrades, setMinTrades] = useState(15)
  const [stake, setStake] = useState(1)
  const [stopLoss, setStopLoss] = useState('')
  const [takeProfit, setTakeProfit] = useState('')
  const [maxDailyLoss, setMaxDailyLoss] = useState('')
  const [scanInterval, setScanInterval] = useState(360)
  const [lookback, setLookback] = useState(3000)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [lastRun, setLastRun] = useState(null)

  async function load() {
    try {
      const s = await api.autopilotStatus()
      setStatus(s)
      const c = s.config
      setMinWinRate(Math.round(c.min_win_rate * 100))
      setMinTrades(c.min_trades)
      setStake(c.base_stake)
      setStopLoss(c.stop_loss ?? '')
      setTakeProfit(c.take_profit ?? '')
      setMaxDailyLoss(c.max_daily_loss ?? '')
      setScanInterval(c.scan_interval_minutes)
      setLookback(c.lookback_candles)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [])

  async function handleStart(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const res = await api.autopilotStart({
        min_win_rate: minWinRate / 100,
        min_trades: parseInt(minTrades, 10),
        base_stake: parseFloat(stake),
        stop_loss: stopLoss ? parseFloat(stopLoss) : null,
        take_profit: takeProfit ? parseFloat(takeProfit) : null,
        max_daily_loss: maxDailyLoss ? parseFloat(maxDailyLoss) : null,
        scan_interval_minutes: parseInt(scanInterval, 10),
        lookback_candles: parseInt(lookback, 10),
      })
      setLastRun(res.first_run)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleStop() {
    setBusy(true)
    setError('')
    try {
      await api.autopilotStop()
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const enabled = status?.config?.enabled

  return (
    <div>
      <div className="disclaimer">
        <span>&#9432;</span>
        <span>
          Set your numbers once, click Start. From then on it re-scans on its own schedule,
          keeps bots running for whatever currently clears your win-rate bar, and stops
          anything that stops qualifying — no manual clicking needed. This is systematic
          backtesting run automatically, not an AI predicting the market. <b>Demo only</b> —
          this never touches real money, by design.
        </span>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="page-panel">
        <div className="section-head">
          <h2>Status</h2>
          <span className="tag" style={{ background: enabled ? 'var(--success-dim)' : 'var(--surface-3)', color: enabled ? 'var(--success)' : 'var(--text-faint)' }}>
            {enabled ? 'Running' : 'Stopped'}
          </span>
        </div>

        {status?.config?.last_result_summary && (
          <div className="strategy-desc" style={{ marginBottom: 14 }}>
            Last check: {status.config.last_result_summary}
            {status.config.last_run_at && ` — ${new Date(status.config.last_run_at).toLocaleString()}`}
          </div>
        )}

        {status?.managed_bots?.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div className="metric-label" style={{ marginBottom: 8 }}>Currently managing</div>
            {status.managed_bots.map((b) => (
              <div key={b.id} className="balance-row">
                <span className="balance-lbl">{b.strategy} / {b.asset}</span>
                <span className={`status-dot status-${b.status}`} style={{ marginLeft: 6 }} />
                <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{b.status}</span>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleStart}>
          <div className="form-row">
            <div className="field">
              <label>Stake</label>
              <input type="number" step="0.01" min="0.01" value={stake} onChange={(e) => setStake(e.target.value)} required />
            </div>
            <div className="field">
              <label>Minimum win rate to qualify (%)</label>
              <input type="number" min="1" max="100" value={minWinRate} onChange={(e) => setMinWinRate(e.target.value)} />
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

          <div className="form-row">
            <div className="field">
              <label>Re-scan every (minutes)</label>
              <input type="number" min="15" value={scanInterval} onChange={(e) => setScanInterval(e.target.value)} />
            </div>
            <div className="field">
              <label>Lookback candles</label>
              <input type="number" min="200" value={lookback} onChange={(e) => setLookback(e.target.value)} />
            </div>
          </div>

          {enabled ? (
            <button type="button" className="btn btn-danger" onClick={handleStop} disabled={busy} style={{ width: '100%' }}>
              {busy ? '…' : '■ Stop autopilot'}
            </button>
          ) : (
            <button type="submit" className="btn btn-primary" disabled={busy} style={{ width: '100%' }}>
              {busy ? 'Running first scan…' : '▶ Start autopilot'}
            </button>
          )}
        </form>
      </div>

      {lastRun && (
        <>
          <div className="section-head"><h2>What just happened</h2></div>
          <div className="page-panel">
            <div className="strategy-desc">
              {lastRun.qualifying_count} combo(s) currently qualify. Started {lastRun.started.length},
              stopped {lastRun.stopped.length}, kept {lastRun.kept.length} already running.
            </div>
            {lastRun.started.map((s) => (
              <div key={`${s.strategy}-${s.asset}`} className="balance-row">
                <span className="balance-lbl">{s.strategy} / {s.asset}</span>
                <span style={{ fontSize: 12 }}>{(s.win_rate * 100).toFixed(1)}% win rate</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
