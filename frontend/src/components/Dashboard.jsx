import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import BotCard from './BotCard.jsx'
import CreateBotModal from './CreateBotModal.jsx'
import BacktestModal from './BacktestModal.jsx'
import TradesModal from './TradesModal.jsx'

export default function Dashboard() {
  const [bots, setBots] = useState(null)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
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
      <div className="page-header">
        <div>
          <h2>Bots</h2>
          <p>Every new bot starts in forced demo mode for 24h before real money is possible.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ New bot</button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {bots && bots.length === 0 && (
        <div className="empty-state">
          No bots yet. Create one, backtest it against real Deriv history, then start it on demo.
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

      {showCreate && (
        <CreateBotModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); refresh() }}
        />
      )}

      {backtestBot && <BacktestModal bot={backtestBot} onClose={() => setBacktestBot(null)} />}
      {tradesBot && <TradesModal bot={tradesBot} onClose={() => setTradesBot(null)} />}
    </div>
  )
}
