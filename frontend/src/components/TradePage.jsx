import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import PriceChart from './PriceChart.jsx'
import Toast from './Toast.jsx'

const ASSET_GROUPS = [
  {
    label: 'Volatility indices',
    assets: [
      { symbol: 'R_10', name: 'Volatility 10' },
      { symbol: 'R_25', name: 'Volatility 25' },
      { symbol: 'R_50', name: 'Volatility 50' },
      { symbol: 'R_75', name: 'Volatility 75' },
      { symbol: 'R_100', name: 'Volatility 100' },
    ],
  },
  {
    label: 'Boom / Crash',
    assets: [
      { symbol: 'BOOM1000', name: 'Boom 1000' },
      { symbol: 'CRASH1000', name: 'Crash 1000' },
    ],
  },
  {
    label: 'Jump indices',
    assets: [
      { symbol: 'JD10', name: 'Jump 10' },
      { symbol: 'JD25', name: 'Jump 25' },
      { symbol: 'JD50', name: 'Jump 50' },
      { symbol: 'JD75', name: 'Jump 75' },
    ],
  },
  {
    label: 'Step indices',
    assets: [
      { symbol: 'stpRNG', name: 'Step Index' },
    ],
  },
]

const TRADE_TYPES = {
  rise_fall: { label: 'Rise / Fall', options: [['rise', '▲ Rise'], ['fall', '▼ Fall']], verified: true },
  even_odd: { label: 'Even / Odd (last digit)', options: [['even', 'Even'], ['odd', 'Odd']], verified: false },
}

const FEED_POLL_MS = 6000
const ITERATION_POLL_MS = 5000
const ACTIVE_BOT_STORAGE_KEY = 'pulse_active_smart_trade_bot'

export default function TradePage() {
  const [symbol, setSymbol] = useState('R_75')

  // Smart trade — the primary, simplified flow
  const [stake, setStake] = useState(1)
  const [stopLoss, setStopLoss] = useState('')
  const [takeProfit, setTakeProfit] = useState('')
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState('')
  const [activeBot, setActiveBotRaw] = useState(() => {
    try {
      const saved = localStorage.getItem(ACTIVE_BOT_STORAGE_KEY)
      return saved ? JSON.parse(saved) : null
    } catch (_) {
      return null
    }
  })
  const [iterations, setIterations] = useState([])
  const [stopping, setStopping] = useState(false)
  const [restoring, setRestoring] = useState(true)

  function setActiveBot(bot) {
    setActiveBotRaw(bot)
    if (bot) localStorage.setItem(ACTIVE_BOT_STORAGE_KEY, JSON.stringify(bot))
    else localStorage.removeItem(ACTIVE_BOT_STORAGE_KEY)
  }

  // On mount (including after navigating back to this page), verify the
  // saved active bot is actually still running server-side — the bot
  // itself never stopped just because you left the page, but if you (or
  // its stop-loss/take-profit) stopped it while you were elsewhere, clear
  // the stale reference here.
  useEffect(() => {
    async function verify() {
      if (activeBot) {
        try {
          const status = await api.botStatus(activeBot.id)
          if (status.status !== 'demo_running' && status.status !== 'real_running') {
            setActiveBot(null)
          }
        } catch (_) {
          setActiveBot(null)
        }
      }
      setRestoring(false)
    }
    verify()
  }, [])

  // Manual trade — secondary, simple panel
  const [mode, setMode] = useState('demo')
  const [tradeType, setTradeType] = useState('rise_fall')
  const [manualStake, setManualStake] = useState(1)
  const [duration, setDuration] = useState(5)
  const [durationUnit, setDurationUnit] = useState('t')
  const [manualBusy, setManualBusy] = useState(false)
  const [manualError, setManualError] = useState('')
  const [lastResult, setLastResult] = useState(null)

  // Live combined transaction feed + win/loss toasts
  const [feed, setFeed] = useState(null)
  const [toasts, setToasts] = useState([])
  const seenResolvedRef = useRef(new Set())
  const firstFeedLoadRef = useRef(true)

  async function loadFeed() {
    try {
      const data = await api.transactionFeed()
      if (!firstFeedLoadRef.current) {
        for (const t of data) {
          const alreadySeen = seenResolvedRef.current.has(t.id)
          if (t.profit_loss !== null && t.profit_loss !== undefined && !alreadySeen) {
            setToasts((prev) => [...prev, {
              id: `${t.id}-${Date.now()}`, symbol: t.symbol,
              profitLoss: t.profit_loss, source: t.source,
            }])
          }
        }
      }
      data.forEach((t) => {
        if (t.profit_loss !== null && t.profit_loss !== undefined) seenResolvedRef.current.add(t.id)
      })
      firstFeedLoadRef.current = false
      setFeed(data)
    } catch (_) { /* retry next poll */ }
  }

  useEffect(() => {
    loadFeed()
    const id = setInterval(loadFeed, FEED_POLL_MS)
    return () => clearInterval(id)
  }, [])

  // Poll the active auto-trade bot's own trades for the iteration list
  useEffect(() => {
    if (!activeBot) return
    async function loadIterations() {
      try {
        const trades = await api.botTrades(activeBot.id)
        setIterations(trades.slice().reverse()) // oldest first, so "Iteration 1" reads naturally
      } catch (_) { /* retry next poll */ }
    }
    loadIterations()
    const id = setInterval(loadIterations, ITERATION_POLL_MS)
    return () => clearInterval(id)
  }, [activeBot])

  function dismissToast(id) {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  async function startSmartTrade() {
    setScanError('')
    setScanning(true)
    try {
      const scan = await api.runScan({ base_stake: parseFloat(stake), lookback_candles: 3000 })
      if (!scan.top_pick) {
        setScanError(scan.note || 'Nothing currently qualifies — try again later or adjust your stake.')
        return
      }
      const launch = await api.launchScanResult({
        strategy: scan.top_pick.strategy,
        asset: scan.top_pick.symbol,
        stake: parseFloat(stake),
        stop_loss: stopLoss ? parseFloat(stopLoss) : null,
        take_profit: takeProfit ? parseFloat(takeProfit) : null,
      })
      setActiveBot({
        id: launch.bot_id, strategy: scan.top_pick.strategy,
        asset: scan.top_pick.symbol, winRate: scan.top_pick.win_rate,
      })
      setIterations([])
    } catch (err) {
      setScanError(err.message)
    } finally {
      setScanning(false)
    }
  }

  async function stopSmartTrade() {
    if (!activeBot) return
    setStopping(true)
    try {
      await api.stopBot(activeBot.id)
    } catch (_) { /* ignore, still clear locally */ } finally {
      setStopping(false)
      setActiveBot(null)
    }
  }

  const activeType = TRADE_TYPES[tradeType]

  async function placeManualTrade(direction) {
    setManualError('')
    setManualBusy(true)
    try {
      const res = await api.executeManualTrade({
        mode, symbol, trade_type: tradeType, direction,
        stake: parseFloat(manualStake),
        duration: parseInt(duration, 10),
        duration_unit: durationUnit,
      })
      setLastResult({ direction, ...res })
      loadFeed()
    } catch (err) {
      setManualError(err.message)
    } finally {
      setManualBusy(false)
    }
  }

  const resolvedIterations = iterations.filter((t) => t.profit_loss !== null && t.profit_loss !== undefined)
  const runningTotal = resolvedIterations.reduce((sum, t) => sum + t.profit_loss, 0)

  return (
    <div>
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <div className="disclaimer">
        <span>&#9432;</span>
        <span>
          Set your stake and risk limits, click one button — it scans every strategy and asset
          for the best current measured result and starts trading it on demo automatically.
          Each trade appears below as it resolves, with a running total. This is systematic
          backtesting run automatically, not an AI predicting the market.
        </span>
      </div>

      <div className="page-panel" style={{ maxWidth: 640 }}>
        <div className="section-head">
          <h2>Smart trade</h2>
          {activeBot && (
            <span className="tag tag-strategy">{activeBot.strategy} / {activeBot.asset}</span>
          )}
        </div>

        {restoring ? (
          <div className="spinner-text">Checking for a running trade…</div>
        ) : !activeBot ? (
          <>
            <div className="form-row">
              <div className="field">
                <label>Stake</label>
                <input type="number" step="0.01" min="0.01" value={stake} onChange={(e) => setStake(e.target.value)} />
              </div>
              <div className="field">
                <label>Stop loss (optional)</label>
                <input type="number" step="0.01" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} />
              </div>
            </div>
            <div className="field">
              <label>Take profit (optional)</label>
              <input type="number" step="0.01" value={takeProfit} onChange={(e) => setTakeProfit(e.target.value)} />
            </div>

            {scanError && <div className="error-banner">{scanError}</div>}

            <button className="btn btn-primary" onClick={startSmartTrade} disabled={scanning} style={{ width: '100%', padding: '14px 0', fontSize: 15, fontWeight: 700 }}>
              {scanning ? 'Scanning for the best combo…' : '▶ Scan & Trade'}
            </button>
          </>
        ) : (
          <>
            <div className="metric-grid">
              <div className="metric">
                <div className="metric-label">Backtested win rate</div>
                <div className="metric-value">{(activeBot.winRate * 100).toFixed(1)}%</div>
              </div>
              <div className="metric">
                <div className="metric-label">Running total (demo)</div>
                <div className={`metric-value ${runningTotal >= 0 ? 'positive' : 'negative'}`}>
                  {runningTotal >= 0 ? '+' : ''}{runningTotal.toFixed(2)}
                </div>
              </div>
            </div>

            <div style={{ margin: '14px 0' }}>
              {iterations.length === 0 && (
                <div className="empty-state">No trades yet — waiting for a signal. This can take 25-45 minutes.</div>
              )}
              {iterations.map((t, i) => (
                <div key={t.id} className="balance-row">
                  <span className="balance-lbl">Iteration {i + 1}</span>
                  <span className={`balance-val ${t.profit_loss > 0 ? '' : t.profit_loss < 0 ? 'real' : ''}`}
                        style={{ color: t.profit_loss > 0 ? 'var(--success)' : t.profit_loss < 0 ? 'var(--danger)' : 'var(--text-faint)' }}>
                    {t.profit_loss === null || t.profit_loss === undefined
                      ? 'pending…'
                      : `${t.profit_loss >= 0 ? '+' : ''}${t.profit_loss.toFixed(2)}`}
                  </span>
                </div>
              ))}
            </div>

            <button className="btn btn-danger" onClick={stopSmartTrade} disabled={stopping} style={{ width: '100%', padding: '12px 0', fontWeight: 700 }}>
              {stopping ? '…' : '■ Stop'}
            </button>
          </>
        )}
      </div>

      <div className="page-panel" style={{ maxWidth: 900 }}>
        <div className="section-head" style={{ marginBottom: 12 }}>
          <h2>{symbol}</h2>
        </div>
        <PriceChart symbol={symbol} />
      </div>

      <div className="section-head"><h2>Manual trade</h2></div>
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
            {ASSET_GROUPS.map((group) => (
              <optgroup key={group.label} label={group.label}>
                {group.assets.map((a) => (
                  <option key={a.symbol} value={a.symbol}>{a.name} ({a.symbol})</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Trade type</label>
          <select value={tradeType} onChange={(e) => setTradeType(e.target.value)}>
            {Object.entries(TRADE_TYPES).map(([key, t]) => (
              <option key={key} value={key}>{t.label}{t.verified ? '' : ' (unverified)'}</option>
            ))}
          </select>
        </div>

        <div className="form-row">
          <div className="field">
            <label>Stake</label>
            <input type="number" step="0.01" min="0.01" value={manualStake} onChange={(e) => setManualStake(e.target.value)} />
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

        {manualError && <div className="error-banner">{manualError}</div>}

        <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
          {activeType.options.map(([direction, label]) => (
            <button
              key={direction}
              className="btn"
              onClick={() => placeManualTrade(direction)}
              disabled={manualBusy}
              style={{
                flex: 1,
                background: direction === 'rise' || direction === 'even' ? 'var(--success)' : 'var(--danger)',
                color: direction === 'rise' || direction === 'even' ? '#06231a' : '#2a0a0a',
                fontWeight: 700, padding: '14px 0', fontSize: 15,
              }}
            >
              {manualBusy ? '…' : label}
            </button>
          ))}
        </div>

        {lastResult && (
          <div className="info-banner" style={{ marginTop: 16 }}>
            Bought {lastResult.direction} on {symbol} — stake {lastResult.buy_price},
            potential payout {lastResult.payout}.
          </div>
        )}
      </div>

      <div className="section-head"><h2>Transaction feed</h2></div>
      {!feed && <div className="spinner-text">Loading…</div>}
      {feed && feed.length === 0 && (
        <div className="empty-state">No trades yet.</div>
      )}
      {feed && feed.length > 0 && (
        <table className="trades">
          <thead>
            <tr>
              <th>Source</th>
              <th>Symbol</th>
              <th>Type</th>
              <th>Stake</th>
              <th>P/L</th>
              <th>Mode</th>
              <th>Opened</th>
            </tr>
          </thead>
          <tbody>
            {feed.map((t) => (
              <tr key={t.id}>
                <td>{t.source}</td>
                <td>{t.symbol}</td>
                <td>{t.type}</td>
                <td>{t.stake}</td>
                <td className={t.profit_loss > 0 ? 'positive' : t.profit_loss < 0 ? 'negative' : ''}>
                  {t.profit_loss ?? 'pending'}
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
