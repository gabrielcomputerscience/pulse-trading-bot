import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function BotBuilderPage({ onCreated }) {
  const [strategies, setStrategies] = useState([])
  const [martingale, setMartingale] = useState(null)
  const [name, setName] = useState('')
  const [strategy, setStrategy] = useState('')
  const [asset, setAsset] = useState('R_100')
  const [stake, setStake] = useState(1)
  const [stopLoss, setStopLoss] = useState('')
  const [takeProfit, setTakeProfit] = useState('')
  const [maxDailyLoss, setMaxDailyLoss] = useState('')
  const [ackHighRisk, setAckHighRisk] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
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
  const isHighRisk = selected?.risk_label === 'high_risk'

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (isHighRisk && !ackHighRisk) {
      setError('You must acknowledge the high-risk warning to use Martingale.')
      return
    }
    setLoading(true)
    try {
      await api.createBot({
        name,
        strategy,
        asset,
        stake: parseFloat(stake),
        stop_loss: stopLoss ? parseFloat(stopLoss) : null,
        take_profit: takeProfit ? parseFloat(takeProfit) : null,
        max_daily_loss: maxDailyLoss ? parseFloat(maxDailyLoss) : null,
        acknowledge_high_risk: ackHighRisk,
      })
      setSuccess(`"${name}" created — head to My Bots to backtest it, then start it on demo.`)
      setName('')
      setStake(1)
      setStopLoss('')
      setTakeProfit('')
      setMaxDailyLoss('')
      setAckHighRisk(false)
      onCreated?.()
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
          Every new bot starts in <b>forced demo mode for 24h</b> regardless of what you pick
          here — real money requires an explicit confirmation after that window.
        </span>
      </div>

      <div className="page-panel">
        {error && <div className="error-banner">{error}</div>}
        {success && <div className="info-banner" style={{ borderColor: 'var(--success)', color: '#9de8cd' }}>{success}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="e.g. Vol75 Reversion" />
          </div>

          <div className="field">
            <label>Strategy</label>
            <select value={strategy} onChange={(e) => { setStrategy(e.target.value); setAckHighRisk(false) }}>
              {allStrategies.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}{s.risk_label === 'high_risk' ? ' (high risk)' : ''}
                </option>
              ))}
            </select>
            {selected && <div className="strategy-desc">{selected.description}</div>}
          </div>

          {isHighRisk && (
            <>
              <div className="info-banner" style={{ borderColor: 'var(--danger)', color: '#f2b5b1' }}>
                {martingale?.warning}
              </div>
              <div className="checkbox-row">
                <input
                  type="checkbox"
                  id="ack"
                  checked={ackHighRisk}
                  onChange={(e) => setAckHighRisk(e.target.checked)}
                />
                <label htmlFor="ack">
                  I understand Martingale is a bet-sizing scheme that can blow up my account,
                  not an accuracy strategy, and want to enable it anyway.
                </label>
              </div>
            </>
          )}

          <div className="form-row">
            <div className="field">
              <label>Asset symbol</label>
              <input value={asset} onChange={(e) => setAsset(e.target.value)} placeholder="R_100, BOOM1000…" required />
            </div>
            <div className="field">
              <label>Base stake</label>
              <input type="number" step="0.01" min="0.01" value={stake} onChange={(e) => setStake(e.target.value)} required />
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

          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%', marginTop: 6 }}>
            {loading ? 'Creating…' : 'Create bot'}
          </button>
        </form>
      </div>
    </div>
  )
}
