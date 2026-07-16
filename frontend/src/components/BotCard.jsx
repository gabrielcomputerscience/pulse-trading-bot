import React, { useState } from 'react'
import { api } from '../api.js'

const STATUS_LABELS = {
  stopped: 'Stopped',
  demo_running: 'Running · demo',
  real_running: 'Running · real money',
  paused: 'Paused',
}

export default function BotCard({ bot, onChanged, onBacktest, onViewTrades }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const isRunning = bot.status === 'demo_running' || bot.status === 'real_running'

  async function handleStart() {
    setBusy(true)
    setError('')
    try {
      await api.startBot(bot.id, false)
      onChanged()
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
      await api.stopBot(bot.id)
      onChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="bot-card">
      <div className="bot-card-top">
        <div>
          <div className="bot-name">{bot.name}</div>
          <div className="bot-asset">{bot.asset}</div>
          <span className={`tag ${bot.strategy === 'martingale' ? 'tag-risk' : 'tag-strategy'}`} style={{ marginTop: 6, display: 'inline-block' }}>
            {bot.strategy}
          </span>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="status-label">
        <span className={`status-dot status-${bot.status}`} />
        {STATUS_LABELS[bot.status] || bot.status}
        {bot.account_mode && <span style={{ marginLeft: 6, textTransform: 'uppercase', fontSize: 10.5 }}>· {bot.account_mode}</span>}
      </div>

      <div className="bot-actions">
        {isRunning ? (
          <button className="btn btn-danger" onClick={handleStop} disabled={busy} style={{ flex: 1 }}>
            {busy ? '…' : '■ Stop'}
          </button>
        ) : (
          <button className="btn btn-primary" onClick={handleStart} disabled={busy} style={{ flex: 1 }}>
            {busy ? '…' : '▶ Run'}
          </button>
        )}
        <button className="btn btn-ghost" onClick={() => onBacktest(bot)}>Backtest</button>
        <button className="btn btn-ghost" onClick={() => onViewTrades(bot)}>Trades</button>
      </div>
    </div>
  )
}
