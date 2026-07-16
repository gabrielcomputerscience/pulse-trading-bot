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

export default function TradePage() {
  const [mode, setMode] = useState('demo')
  const [symbol, setSymbol] = useState('R_75')
  const [tradeType, setTradeType] = useState('rise_fall')
  const [stake, setStake] = useState(1)
  const [duration, setDuration] = useState(5)
  const [durationUnit, setDurationUnit] = useState('t')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [lastResult, setLastResult] = useState(null)

  // Scan & auto-trade panel
  const [scanStopLoss, setScanStopLoss] = useState('')
  const [scanTakeProfit, setScanTakeProfit] = useState('')
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState(null)
  const [launching, setLaunching] = useState(null)
  const [launchMessage, setLaunchMessage] = useState('')

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
    } catch (_) {
      // non-critical, retry next poll
    }
  }

  useEffect(() => {
    loadFeed()
    const id = setInterval(loadFeed, FEED_POLL_MS)
    return () => clearInterval(id)
  }, [])

  function dismissToast(id) {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  const activeType = TRADE_TYPES[tradeType]

  async function placeTrade(direction) {
    setError('')
    setBusy(true)
    try {
      const res = await api.executeManualTrade({
        mode, symbol, trade_type: tradeType, direction,
        stake: parseFloat(stake),
        duration: parseInt(duration, 10),
        duration_unit: durationUnit,
      })
      setLastResult({ direction, ...res })
      loadFeed()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function runScan() {
    setError('')
    setScanResult(null)
    setLaunchMessage('')
    setScanning(true)
    try {
      const res = await api.runScan({ base_stake: parseFloat(stake), lookback_candles: 3000 })
      setScanResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setScanning(false)
    }
  }

  async function launchCandidate(candidate) {
    const key = `${candidate.strategy}-${candidate.symbol}`
    setLaunching(key)
    setError('')
    try {
      await api.launchScanResult({
        strategy: candidate.strategy,
        asset: candidate.symbol,
        stake: parseFloat(stake),
        stop_loss: scanStopLoss ? parseFloat(scanStopLoss) : null,
        take_profit: scanTakeProfit ? parseFloat(scanTakeProfit) : null,
      })
      setLaunchMessage(`Launched "${candidate.strategy} / ${candidate.symbol}" on demo — watch the feed below.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLaunching(null)
    }
  }

  return (
    <div>
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <div className="disclaimer">
        <span>&#9432;</span>
        <span>
          Manual trades execute instantly at the current price. The scan panel below runs real
          backtests across every strategy and asset, then can launch the best one as a bot for
          you — same engine as Auto Scanner, right here. Only <b>Rise/Fall</b> manual trades are
          confirmed against a real trade; <b>Even/Odd</b> is unverified.
        </span>
      </div>

      <div className="page-panel" style={{ maxWidth: 900 }}>
        <div className="section-head" style={{ marginBottom: 12 }}>
          <h2>{symbol}</h2>
        </div>
        <PriceChart symbol={symbol} />
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
          {!activeType.verified && (
            <div className="strategy-desc" style={{ color: 'var(--danger)' }}>
              Not yet confirmed against a real trade. Test with a $1 demo stake first.
            </div>
          )}
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
          {activeType.options.map(([direction, label]) => (
            <button
              key={direction}
              className="btn"
              onClick={() => placeTrade(direction)}
              disabled={busy}
              style={{
                flex: 1,
                background: direction === 'rise' || direction === 'even' ? 'var(--success)' : 'var(--danger)',
                color: direction === 'rise' || direction === 'even' ? '#06231a' : '#2a0a0a',
                fontWeight: 700, padding: '14px 0', fontSize: 15,
              }}
            >
              {busy ? '…' : label}
            </button>
          ))}
        </div>

        {lastResult && (
          <div className="info-banner" style={{ marginTop: 16 }}>
            Bought {lastResult.direction} on {symbol} — stake {lastResult.buy_price},
            potential payout {lastResult.payout}. {lastResult.longcode}
          </div>
        )}
      </div>

      <div className="section-head"><h2>Scan &amp; auto-trade</h2></div>
      <div className="page-panel">
        <div className="strategy-desc" style={{ marginBottom: 12 }}>
          Runs real backtests across every strategy and asset, ranks by measured results — same
          engine as Auto Scanner. Launches on demo. Uses the stake set above.
        </div>
        <div className="form-row" style={{ marginBottom: 10 }}>
          <div className="field">
            <label>Stop loss (optional, for launched bots)</label>
            <input type="number" step="0.01" value={scanStopLoss} onChange={(e) => setScanStopLoss(e.target.value)} />
          </div>
          <div className="field">
            <label>Take profit (optional, for launched bots)</label>
            <input type="number" step="0.01" value={scanTakeProfit} onChange={(e) => setScanTakeProfit(e.target.value)} />
          </div>
        </div>
        <button className="btn btn-primary" onClick={runScan} disabled={scanning} style={{ width: '100%' }}>
          {scanning ? 'Scanning…' : 'Scan for the best current combo'}
        </button>

        {launchMessage && (
          <div className="info-banner" style={{ marginTop: 12, borderColor: 'var(--success)', color: '#9de8cd' }}>
            {launchMessage}
          </div>
        )}

        {scanResult && (
          scanResult.top_pick ? (
            <table className="bt-table" style={{ marginTop: 14 }}>
              <thead>
                <tr>
                  <th>Strategy</th><th>Asset</th><th>Trades</th><th>Win rate</th><th>Net P/L</th><th></th>
                </tr>
              </thead>
              <tbody>
                {scanResult.ranked.slice(0, 5).map((c) => {
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
                      <td>
                        <button className="btn btn-ghost" onClick={() => launchCandidate(c)}
                                disabled={launching !== null} style={{ padding: '5px 10px', fontSize: 11.5 }}>
                          {launching === key ? '…' : 'Launch'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          ) : (
            <div className="empty-state" style={{ marginTop: 14 }}>{scanResult.note}</div>
          )
        )}
      </div>

      <div className="section-head"><h2>Transaction feed</h2></div>
      {!feed && <div className="spinner-text">Loading…</div>}
      {feed && feed.length === 0 && (
        <div className="empty-state">No trades yet — place one above or launch a scan result.</div>
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
