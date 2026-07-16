import React, { useEffect, useState } from 'react'
import DerivPatLogin from './components/DerivPatLogin.jsx'
import AddAccountModal from './components/AddAccountModal.jsx'
import Ticker from './components/Ticker.jsx'
import AccountBalances from './components/AccountBalances.jsx'
import OverviewPage from './components/OverviewPage.jsx'
import MyBotsPage from './components/MyBotsPage.jsx'
import BotBuilderPage from './components/BotBuilderPage.jsx'
import BacktestLabPage from './components/BacktestLabPage.jsx'
import TradePage from './components/TradePage.jsx'
import ScannerPage from './components/ScannerPage.jsx'
import AutopilotPage from './components/AutopilotPage.jsx'
import BacktestModal from './components/BacktestModal.jsx'
import TradesModal from './components/TradesModal.jsx'
import { loadStoredToken, setAuthToken } from './api.js'

const VIEWS = {
  trade: { title: 'Trade', sub: 'Instant Rise/Fall trades — no strategy, executes immediately' },
  autopilot: { title: 'Autopilot', sub: 'Set it once — scans, launches, and manages winning combos automatically on demo' },
  scanner: { title: 'Auto scanner', sub: 'Backtests every strategy across multiple assets and ranks the results' },
  overview: { title: 'Overview', sub: 'Live status across your connected Deriv account and active bots' },
  bots: { title: 'My bots', sub: 'Manage, pause, and inspect every bot on this account' },
  builder: { title: 'Bot builder', sub: 'Configure a strategy, asset, and risk limits' },
  backtest: { title: 'Backtest lab', sub: 'Test a strategy against real historical tick data before it touches funds' },
}

export default function App() {
  const [screen, setScreen] = useState('login') // login | app
  const [derivLoginid, setDerivLoginid] = useState('')
  const [view, setView] = useState('trade')
  const [refreshKey, setRefreshKey] = useState(0)
  const [backtestBot, setBacktestBot] = useState(null)
  const [tradesBot, setTradesBot] = useState(null)
  const [showAddAccount, setShowAddAccount] = useState(false)
  const [balancesKey, setBalancesKey] = useState(0)

  useEffect(() => {
    const token = loadStoredToken()
    if (token) setScreen('app')
  }, [])

  function handleLogout() {
    setAuthToken(null)
    setScreen('login')
  }

  if (screen === 'login') {
    return (
      <DerivPatLogin
        onLoggedIn={(res) => {
          setDerivLoginid(res.deriv_loginid)
          setScreen('app')
        }}
      />
    )
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="dot" />
          <span>Pulse</span>
        </div>
        <nav className="sidebar-nav">
          {Object.entries(VIEWS).map(([key, v]) => (
            <button key={key} className={view === key ? 'active' : ''} onClick={() => setView(key)}>
              {v.title}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <AccountBalances key={balancesKey} />
          <button className="btn btn-ghost" onClick={() => setShowAddAccount(true)} style={{ width: '100%', marginBottom: 8 }}>
            + Link another account
          </button>
          {derivLoginid && <div className="user">{derivLoginid}</div>}
          <button className="btn btn-ghost" onClick={handleLogout} style={{ width: '100%' }}>
            Sign out
          </button>
        </div>
      </aside>

      <div className="main">
        <Ticker />
        <div className="topbar">
          <div>
            <h1>{VIEWS[view].title}</h1>
            <p>{VIEWS[view].sub}</p>
          </div>
        </div>

        <div style={{ padding: '24px 26px 60px' }}>
          {view === 'trade' && <TradePage />}
          {view === 'autopilot' && <AutopilotPage />}
          {view === 'scanner' && <ScannerPage />}
          {view === 'overview' && (
            <OverviewPage key={refreshKey} onBacktest={setBacktestBot} onViewTrades={setTradesBot} />
          )}
          {view === 'bots' && (
            <MyBotsPage key={refreshKey} onGoToBuilder={() => setView('builder')} />
          )}
          {view === 'builder' && (
            <BotBuilderPage onCreated={() => setRefreshKey((k) => k + 1)} />
          )}
          {view === 'backtest' && <BacktestLabPage />}
        </div>
      </div>

      {backtestBot && <BacktestModal bot={backtestBot} onClose={() => setBacktestBot(null)} />}
      {tradesBot && <TradesModal bot={tradesBot} onClose={() => setTradesBot(null)} />}
      {showAddAccount && (
        <AddAccountModal
          onClose={() => setShowAddAccount(false)}
          onLinked={() => setBalancesKey((k) => k + 1)}
        />
      )}
    </div>
  )
}
