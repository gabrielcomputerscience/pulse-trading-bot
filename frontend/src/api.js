const BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

let authToken = null

export function setAuthToken(token) {
  authToken = token
  if (token) localStorage.setItem('pulse_token', token)
  else localStorage.removeItem('pulse_token')
}

export function loadStoredToken() {
  authToken = localStorage.getItem('pulse_token')
  return authToken
}

async function request(path, { method = 'GET', body, form = false } = {}) {
  const headers = {}
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`

  let payload = body
  if (body && !form) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  const res = await fetch(`${BASE_URL}${path}`, { method, headers, body: payload })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const errJson = await res.json()
      detail = errJson.detail || detail
    } catch (_) {}
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  derivLoginUrl: () => request('/auth/deriv/login'),
  derivCallback: (queryString) =>
    request('/auth/deriv/callback', { method: 'POST', body: { query_string: queryString } }),
  accountBalances: () => request('/account/balances'),

  // Legacy manual-signup path — kept for /docs testing, not used by the UI.
  signup: (username, password) =>
    request('/auth/signup', { method: 'POST', body: { username, password } }),
  login: (username, password) => {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    return request('/auth/login', { method: 'POST', body: form, form: true })
  },
  setDerivToken: (deriv_api_token) =>
    request('/auth/deriv-token', { method: 'POST', body: { deriv_api_token } }),

  listStrategies: () => request('/strategies'),
  martingaleInfo: () => request('/strategies/martingale'),

  marketTicker: () => request('/market/ticker'),

  listBots: () => request('/bots'),
  createBot: (bot) => request('/bots', { method: 'POST', body: bot }),
  backtestBot: (id, params) => request(`/bots/${id}/backtest`, { method: 'POST', body: params }),
  freeformBacktest: (params) => request('/backtest', { method: 'POST', body: params }),
  startBot: (id, confirmRealMoney = false) =>
    request(`/bots/${id}/start?confirm_real_money=${confirmRealMoney}`, { method: 'POST' }),
  stopBot: (id) => request(`/bots/${id}/stop`, { method: 'POST' }),
  botStatus: (id) => request(`/bots/${id}/status`),
  botTrades: (id) => request(`/bots/${id}/trades`),
}
