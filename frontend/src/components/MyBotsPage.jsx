import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import BotCard from './BotCard.jsx'
import BacktestModal from './BacktestModal.jsx'
import TradesModal from './TradesModal.jsx'

export default function MyBotsPage({ onGoToBuilder }) {
  const [bots, setBots] = useState(null)
  const [error, setError] = useState('')
  const [backtestBot, setBacktestBot] = useState(null)
  const [tradesBot, setTradesBot] = useState(null)

  async function refresh() {
    try {
      const list = await api.listBots()
      setBots(list)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { refresh() }, [])

  return (
    <div>
      <div className="section-head">
        <h2>All bots</h2>
        <button className="btn btn-primary" onClick={onGoToBuilder}>+ New bot</button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {bots && bots.length === 0 && (
        <div className="empty-state">
          No bots yet. Head to Bot Builder to create one, backtest it, then start it on demo.
        </div>
      )}

      {bots && bots.length > 0 && (
        <div className="bot-grid">
          {bots.map((bot) => (
            <BotCard
              key={bot.id}
              bot={bot}
              onChanged={refresh}
              onBacktest={setBacktestBot}
              onViewTrades={setTradesBot}
            />
          ))}
        </div>
      )}

      {backtestBot && <BacktestModal bot={backtestBot} onClose={() => setBacktestBot(null)} />}
      {tradesBot && <TradesModal bot={tradesBot} onClose={() => setTradesBot(null)} />}
    </div>
  )
}
