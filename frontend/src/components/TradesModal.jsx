import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function TradesModal({ bot, onClose }) {
  const [trades, setTrades] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.botTrades(bot.id).then(setTrades).catch((err) => setError(err.message))
  }, [bot.id])

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ width: 560 }} onClick={(e) => e.stopPropagation()}>
        <h3>Trade history — {bot.name}</h3>

        {error && <div className="error-banner">{error}</div>}

        {!trades && !error && <div className="spinner-text">Loading…</div>}

        {trades && trades.length === 0 && (
          <div className="empty-state">No trades yet. Start the bot to begin trading on demo.</div>
        )}

        {trades && trades.length > 0 && (
          <table className="trades">
            <thead>
              <tr>
                <th>Type</th>
                <th>Stake</th>
                <th>P/L</th>
                <th>Mode</th>
                <th>Opened</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.id}>
                  <td>{t.type}</td>
                  <td>{t.stake}</td>
                  <td className={t.profit_loss > 0 ? 'positive' : t.profit_loss < 0 ? 'negative' : ''}>
                    {t.profit_loss ?? '—'}
                  </td>
                  <td>{t.is_demo ? 'demo' : 'real'}</td>
                  <td>{new Date(t.opened_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose} style={{ flex: 1 }}>Close</button>
        </div>
      </div>
    </div>
  )
}
