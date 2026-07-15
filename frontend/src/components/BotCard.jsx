import React, { useState } from 'react'
import { api } from '../api.js'

const STATUS_LABELS = {
  stopped: 'Paused',
  demo_running: 'Running · demo',
  real_running: 'Running · real money',
  paused: 'Paused',
}

export default function BotCard({ bot, onChanged, onBacktest, onViewTrades }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const isRunning = bot.status === 'demo_running' || bot.status === 'real_running'

  async function handleToggle() {
    setBusy(true)
    setError('')
    try {
      if (isRunning) {
        await api.stopBot(bot.id)
      } else {
        await api.startBot(bot.id, false)
      }
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
        <div className={`toggle ${isRunning ? 'on' : ''} ${busy ? 'busy' : ''}`} onClick={handleToggle}>
          <div className="knob" />
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="status-label">
        <span className={`status-dot status-${bot.status}`} />
        {STATUS_LABELS[bot.status] || bot.status}
      </div>

      <div className="bot-actions">
        <button className="btn btn-ghost" onClick={() => onBacktest(bot)}>Backtest</button>
        <button className="btn btn-ghost" onClick={() => onViewTrades(bot)}>Trades</button>
      </div>
    </div>
  )
}
