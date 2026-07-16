import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import BotCard from './BotCard.jsx'

const REFRESH_MS = 15000

export default function OverviewPage({ onBacktest, onViewTrades }) {
  const [bots, setBots] = useState(null)
  const [feed, setFeed] = useState([])
  const [error, setError] = useState('')

  async function load() {
    try {
      const [botList, tradeFeed] = await Promise.all([
        api.listBots(),
        api.transactionFeed().catch(() => []),
      ])
      setBots(botList)
      setFeed(tradeFeed)
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, REFRESH_MS)
    return () => clearInterval(id)
  }, [])

  if (error) return <div className="error-banner">{error}</div>
  if (!bots) return <div className="spinner-text">Loading…</div>

  const runningBots = bots.filter((b) => b.status === 'demo_running' || b.status === 'real_running')
  const closedTrades = feed.filter((t) => t.profit_loss !== null && t.profit_loss !== undefined)
  const wins = closedTrades.filter((t) => t.profit_loss > 0).length
  const winRate = closedTrades.length ? (wins / closedTrades.length) * 100 : null
  const netPnl = closedTrades.reduce((sum, t) => sum + (t.profit_loss || 0), 0)
  const demoPnl = closedTrades.filter((t) => t.is_demo).reduce((sum, t) => sum + (t.profit_loss || 0), 0)
  const realPnl = closedTrades.filter((t) => !t.is_demo).reduce((sum, t) => sum + (t.profit_loss || 0), 0)

  return (
    <div>
      <div className="disclaimer">
        <span>&#9432;</span>
        <span>
          <b>Live account, real numbers.</b> Includes every trade — manual and bot-driven,
          demo and real — nothing here is simulated or hardcoded. Refreshes automatically.
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
          <div className="stat-val">{feed.length}</div>
          <div className="stat-sub">{closedTrades.length} closed</div>
        </div>
        <div className="stat-card">
          <div className="stat-lbl">Win rate</div>
          <div className="stat-val">{winRate === null ? '—' : `${winRate.toFixed(1)}%`}</div>
          <div className="stat-sub">across closed trades</div>
        </div>
        <div className="stat-card">
          <div className="stat-lbl">Net P/L (all)</div>
          <div className={`stat-val ${netPnl >= 0 ? 'positive' : 'negative'}`}>
            {netPnl >= 0 ? '+' : ''}{netPnl.toFixed(2)}
          </div>
          <div className="stat-sub">demo + real combined</div>
        </div>
      </div>

      <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
        <div className="stat-card">
          <div className="stat-lbl">Demo P/L</div>
          <div className={`stat-val ${demoPnl >= 0 ? 'positive' : 'negative'}`}>
            {demoPnl >= 0 ? '+' : ''}{demoPnl.toFixed(2)}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-lbl">Real P/L</div>
          <div className={`stat-val ${realPnl >= 0 ? 'positive' : 'negative'}`}>
            {realPnl >= 0 ? '+' : ''}{realPnl.toFixed(2)}
          </div>
        </div>
      </div>

      <div className="section-head"><h2>Running now</h2></div>
      {runningBots.length === 0 && (
        <div className="empty-state">No bots running. Head to My Bots or Trade to start one on demo.</div>
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
