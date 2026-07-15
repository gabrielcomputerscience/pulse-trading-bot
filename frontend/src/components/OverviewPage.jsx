import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import BotCard from './BotCard.jsx'

export default function OverviewPage({ onBacktest, onViewTrades }) {
  const [bots, setBots] = useState(null)
  const [tradesByBot, setTradesByBot] = useState({})
  const [error, setError] = useState('')

  async function load() {
    try {
      const list = await api.listBots()
      setBots(list)
      const entries = await Promise.all(
        list.map(async (b) => [b.id, await api.botTrades(b.id).catch(() => [])])
      )
      setTradesByBot(Object.fromEntries(entries))
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => { load() }, [])

  if (error) return <div className="error-banner">{error}</div>
  if (!bots) return <div className="spinner-text">Loading…</div>

  const runningBots = bots.filter((b) => b.status === 'demo_running' || b.status === 'real_running')
  const allTrades = Object.values(tradesByBot).flat()
  const closedTrades = allTrades.filter((t) => t.profit_loss !== null && t.profit_loss !== undefined)
  const wins = closedTrades.filter((t) => t.profit_loss > 0).length
  const winRate = closedTrades.length ? (wins / closedTrades.length) * 100 : null
  const netPnl = closedTrades.reduce((sum, t) => sum + (t.profit_loss || 0), 0)

  return (
    <div>
      <div className="disclaimer">
        <span>&#9432;</span>
        <span>
          <b>Live account, real numbers.</b> Stats below come from your actual bots and trade
          history — nothing here is simulated or hardcoded.
        </span>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-lbl">Active bots</div>
          <div className="stat-val">{runningBots.length}</div>
          <div className="stat-sub">of {bots.length} total</div>
        </div>
        <div className="stat-card">
          <div className="stat-lbl">Total trades</div>
          <div className="stat-val">{allTrades.length}</div>
          <div className="stat-sub">{closedTrades.length} closed</div>
        </div>
        <div className="stat-card">
          <div className="stat-lbl">Win rate</div>
          <div className="stat-val">{winRate === null ? '—' : `${winRate.toFixed(1)}%`}</div>
          <div className="stat-sub">across closed trades</div>
        </div>
        <div className="stat-card">
          <div className="stat-lbl">Net P/L</div>
          <div className={`stat-val ${netPnl >= 0 ? 'positive' : 'negative'}`}>
            {netPnl >= 0 ? '+' : ''}{netPnl.toFixed(2)}
          </div>
          <div className="stat-sub">demo + real combined</div>
        </div>
      </div>

      <div className="section-head"><h2>Running now</h2></div>
      {runningBots.length === 0 && (
        <div className="empty-state">No bots running. Head to My Bots to start one on demo.</div>
      )}
      {runningBots.length > 0 && (
        <div className="bot-grid">
          {runningBots.map((bot) => (
            <BotCard key={bot.id} bot={bot} onChanged={load} onBacktest={onBacktest} onViewTrades={onViewTrades} />
          ))}
        </div>
      )}
    </div>
  )
}
