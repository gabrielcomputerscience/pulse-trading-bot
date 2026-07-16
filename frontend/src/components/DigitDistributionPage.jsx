import React, { useState } from 'react'
import { api } from '../api.js'

const ASSETS = [
  { symbol: 'R_10', name: 'Volatility 10' },
  { symbol: 'R_25', name: 'Volatility 25' },
  { symbol: 'R_50', name: 'Volatility 50' },
  { symbol: 'R_75', name: 'Volatility 75' },
  { symbol: 'R_100', name: 'Volatility 100' },
  { symbol: 'BOOM1000', name: 'Boom 1000' },
  { symbol: 'CRASH1000', name: 'Crash 1000' },
  { symbol: 'JD25', name: 'Jump 25' },
  { symbol: 'stpRNG', name: 'Step Index' },
]

export default function DigitDistributionPage() {
  const [symbol, setSymbol] = useState('R_100')
  const [count, setCount] = useState(3000)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  async function runTest(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const res = await api.digitDistribution(symbol, parseInt(count, 10))
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const maxPct = result ? Math.max(...result.digit_percentages, 10) : 10

  return (
    <div>
      <div className="disclaimer">
        <span>&#9432;</span>
        <span>
          Tests whether the last digit of real tick prices is actually close to uniform (10%
          each, as it should be on a well-built RNG) or shows measurable skew — using a real
          chi-square goodness-of-fit test against real historical ticks, not a guess. This
          directly answers whether any "digit prediction" strategy could ever have a real edge
          here.
        </span>
      </div>

      <div className="page-panel">
        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={runTest}>
          <div className="form-row">
            <div className="field">
              <label>Asset</label>
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
                {ASSETS.map((a) => (
                  <option key={a.symbol} value={a.symbol}>{a.name} ({a.symbol})</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Sample size (ticks)</label>
              <input type="number" min="200" max="5000" value={count} onChange={(e) => setCount(e.target.value)} />
            </div>
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? 'Pulling real ticks & testing…' : 'Run digit distribution test'}
          </button>
        </form>
      </div>

      {result && (
        <>
          <div className="page-panel">
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 160, marginBottom: 16 }}>
              {result.digit_percentages.map((pct, digit) => (
                <div key={digit} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                  <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
                    {pct.toFixed(1)}%
                  </div>
                  <div style={{
                    width: '100%',
                    height: `${(pct / maxPct) * 110}px`,
                    background: Math.abs(pct - 10) > 3 ? 'var(--danger)' : 'var(--amber)',
                    borderRadius: '3px 3px 0 0',
                    minHeight: 4,
                  }} />
                  <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)' }}>{digit}</div>
                </div>
              ))}
            </div>
            <div className="strategy-desc" style={{ textAlign: 'center' }}>
              Dashed line = expected 10% per digit if genuinely uniform · sample size {result.sample_size} ticks
            </div>
          </div>

          <div className="page-panel">
            <div className="metric-grid">
              <div className="metric">
                <div className="metric-label">Chi-square statistic</div>
                <div className="metric-value">{result.chi_square_statistic}</div>
              </div>
              <div className="metric">
                <div className="metric-label">95% significance threshold</div>
                <div className="metric-value">{result.critical_value_95pct}</div>
              </div>
            </div>
            <div className="info-banner" style={{
              marginTop: 12,
              borderColor: result.chi_square_statistic < result.critical_value_95pct ? 'var(--success)' : 'var(--danger)',
              color: result.chi_square_statistic < result.critical_value_95pct ? '#9de8cd' : '#f2b5b1',
            }}>
              {result.verdict}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
