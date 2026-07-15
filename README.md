# Pulse — Deriv Multi-Bot Trading Platform (Backend)

## What this is, honestly

This is a real, working backend that:
- Authenticates to Deriv over WebSocket using a per-user API token
- Streams live tick data for synthetic indices (and other Deriv-tradable assets)
- Runs 4 distinct strategies (3 legitimate, 1 quarantined) that generate BUY/SELL/HOLD signals
- Backtests those strategies against **real historical ticks pulled from Deriv**, so win rate is measured, not guessed
- Places trades via Deriv's `proposal` → `buy` flow, defaulting to your **demo account**
- Never claims a guaranteed accuracy number, because no honest system can

**No strategy here is "more accurate than any other bot out there."** That claim isn't measurable and anyone selling it to you is selling snake oil. What you get instead: clean, non-overfit strategy logic, an honest backtester, and demo-first execution so you find out the real numbers before risking money.

## Project structure

```
pulse-trading-bot/
├── app/
│   ├── config.py           # env-based settings
│   ├── database.py         # SQLAlchemy models (users, tokens, bots, trades)
│   ├── deriv_client.py     # Deriv WebSocket client (auth, ticks, proposal, buy)
│   ├── bot_engine.py       # runs one bot: strategy -> signal -> trade
│   ├── backtest.py         # pulls real history, replays strategy, reports win rate
│   ├── main.py             # FastAPI app: auth, bot CRUD, start/stop, backtest endpoint
│   └── strategies/
│       ├── base.py
│       ├── indicators.py         # SMA/EMA/RSI/Bollinger/ADX helpers
│       ├── mean_reversion.py     # Bollinger + RSI, range-bound conditions
│       ├── trend_following.py    # EMA crossover + ADX filter, trending conditions
│       ├── candlestick_indicator.py  # pattern + RSI/MACD confirmation
│       └── martingale.py         # QUARANTINED: staking scheme, not an "accuracy" strategy
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

1. **Create a Deriv app** at https://developers.deriv.com (free) — note the App ID.
2. **Register a Redirect URI** on that app, exactly: `http://localhost:5173/oauth/callback` for local dev (add your real production frontend URL too once you deploy). OAuth login fails with a generic error if this doesn't match exactly.
3. Copy `.env.example` to `.env` and fill in:
   ```
   DERIV_APP_ID=your_app_id
   DERIV_REDIRECT_URI=http://localhost:5173/oauth/callback
   DERIV_ACCOUNT_MODE=demo             # demo | real  (starts on demo, always)
   DATABASE_URL=sqlite:///./pulse.db
   SECRET_KEY=generate_a_random_string
   TOKEN_ENCRYPTION_KEY=generate_a_fernet_key
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the API:
   ```bash
   uvicorn app.main:app --reload
   ```
6. API docs at `http://localhost:8000/docs`.

## Using it

There's no separate account to create — logging in *is* connecting your Deriv account.

1. **"Continue with Deriv"** in the frontend redirects to Deriv's own login/approval page. Approve access, and Deriv redirects back with your account(s) — usually a demo and a real account, each with their own scoped token. Pulse never sees your Deriv password, and you never see or paste a raw token.
2. The backend exchanges that for its own session token (`POST /auth/deriv/callback`) and creates or finds your local `User` row keyed by your Deriv login ID — no username/password anywhere.
3. **Balances** (`GET /account/balances`) are pulled live from Deriv every time they're requested — not cached, not stored numbers.
4. **Create a bot** (`POST /bots`): pick a strategy (`mean_reversion`, `trend_following`, `candlestick_indicator`, or `martingale`), an asset (e.g. `R_100`, `1HZ100V`, `BOOM1000`), stake, and risk limits.
5. **Backtest first** (`POST /bots/{id}/backtest` or the free-form `POST /backtest`): pulls real historical ticks from Deriv, replays the strategy, returns actual win rate, drawdown, and trade count. **Do this before starting the bot live.**
6. **Start the bot** (`POST /bots/{id}/start`): runs on your **demo balance** by default, using the demo token Deriv gave you at login. Every new bot spends its first 24h in forced demo mode — hardcoded, not a suggestion.
7. **Switching to real money** requires an explicit `confirm_real_money=true` flag *after* the 24h demo window, `DERIV_ACCOUNT_MODE=real` in your env, and a real account token to actually exist (i.e. you approved a real account during login).

**Manual-token fallback:** `/auth/signup`, `/auth/login`, and `/auth/deriv-token` still exist (visible in `/docs`) for testing without going through OAuth, but the frontend no longer shows this path — Deriv OAuth is the only flow a real visitor sees.

## The 4 strategies, honestly described

| Strategy | Best suited for | What it actually does |
|---|---|---|
| `mean_reversion` | Range-bound / choppy volatility indices | Bollinger Band touch + RSI extreme + confirmation candle. Bets price snaps back to the mean. Loses money in strong trends. |
| `trend_following` | Trending Boom/Crash/Step runs | EMA(9/21) crossover filtered by ADX > 20 (real trend, not noise). Bets the move continues. Loses money in choppy/ranging markets — this is the natural complement to mean reversion. |
| `candlestick_indicator` | General purpose, lower frequency | Recognizes a handful of well-defined candlestick patterns (hammer, engulfing, doji) and only signals when RSI/MACD agree. Fewer trades, higher signal quality by design. |
| `martingale` | **Nobody, recommended off** | Doubles stake after each loss to recover + profit on the next win. This produces a high *apparent* win rate right up until a losing streak wipes the account — it is a bet-sizing scheme, not a predictive strategy. Implemented because you asked for it, hard-capped at a configurable max stake and max consecutive doublings, and flagged everywhere in the UI/API as high-risk. It is never included in "recommended" or "best" bot listings. |

None of these get a manufactured "accuracy %" claim in the code. `backtest.py` computes win rate directly from real historical replay — whatever number comes out is the number, good or bad.

## Frontend

`frontend/` is a real React app (Vite) that talks to this API. Login is a
single **"Continue with Deriv"** button — no signup form, no password, no
manual token paste. After approving on Deriv's site, the frontend shows
your real Overview stats, a live ticker of Deriv synthetic indices, real
demo/real balances pulled straight from Deriv, My Bots, Bot Builder, and
Backtest Lab.

**Run it locally:**
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`. It expects the backend running at
`http://127.0.0.1:8000` by default — override with a `.env` file in
`frontend/` containing `VITE_API_URL=https://your-backend-host`.

The backend's CORS config in `app/main.py` currently only allows
`localhost:5173` — add your real frontend domain to `allow_origins` before
deploying either piece.

**Build for production:**
```bash
npm run build
```
Outputs static files to `frontend/dist/` — deploy that folder to any static
host (see below).

## Deployment — step by step (Railway backend + Vercel frontend)

This is the fastest path to a real HTTPS URL, which you need anyway since
Deriv rejects `localhost` redirect URIs. Any similar pair of hosts works
the same way (Render/Fly.io instead of Railway, Netlify/Cloudflare Pages
instead of Vercel) — the steps below are illustrative.

**1. Push this project to a GitHub repo** (both `app/` and `frontend/` in
the same repo is fine). Make sure `.env` and `frontend/.env` are **not**
committed — check `.gitignore` already excludes them.

**2. Deploy the backend (Railway):**
   - New Project → Deploy from GitHub repo → select this repo
   - Root directory: leave at repo root (it'll find `requirements.txt`)
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Add a Postgres database from Railway's "+ New" menu, and copy its
     connection string into `DATABASE_URL`
   - Set these environment variables in Railway's dashboard:
     ```
     DERIV_APP_ID=your_app_id
     DERIV_ACCOUNT_MODE=demo
     DATABASE_URL=<railway's postgres url>
     SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(32))">
     TOKEN_ENCRYPTION_KEY=<generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
     ALLOWED_ORIGINS=<fill in after step 3, once you know the Vercel URL>
     DERIV_REDIRECT_URI=<fill in after step 3, once you know the Vercel URL>
     ```
   - Deploy. Railway gives you a URL like `https://pulse-backend-production.up.railway.app` — that's your backend's live URL.

**3. Deploy the frontend (Vercel):**
   - New Project → import the same GitHub repo
   - Root directory: `frontend`
   - Build command: `npm run build`, output directory: `dist` (Vercel usually detects this automatically for Vite)
   - Environment variable: `VITE_API_URL=https://pulse-backend-production.up.railway.app` (your Railway URL from step 2)
   - Deploy. Vercel gives you a URL like `https://pulse-console.vercel.app`.

**4. Wire the two together:** go back to Railway and set:
   ```
   ALLOWED_ORIGINS=https://pulse-console.vercel.app
   DERIV_REDIRECT_URI=https://pulse-console.vercel.app/oauth/callback
   ```
   Redeploy the backend for these to take effect.

**5. Register the redirect URL with Deriv:** in your app's settings at
https://developers.deriv.com, add this exact Redirect URL:
   ```
   https://pulse-console.vercel.app/oauth/callback
   ```

**6. Test it:** open `https://pulse-console.vercel.app`, click "Continue
with Deriv," approve access, and you should land back in the app with your
real Overview and live balances.

**Ongoing notes:**
- Vercel/Netlify already fall back to `index.html` for unknown client-side routes like `/oauth/callback`, so no extra config needed there.
- Every time you change the frontend's domain (custom domain, etc.), update both `ALLOWED_ORIGINS` in Railway and the Redirect URL in Deriv's dashboard to match — they have to be exact.
- Terminate TLS is handled automatically by both Railway and Vercel — you don't need to set up your own HTTPS certs for this setup.

## Critical safety disclaimers

- **This is a tool for testing trading ideas, not a money-making guarantee.** Every strategy can and will lose money under some market conditions.
- **Always backtest, then run on demo, before ever touching real funds.** The 24h forced-demo period on new bots exists for this reason — don't bypass it.
- **Martingale-mode can blow up an account.** It is included because it was requested, not because it's recommended. Leave it off unless you fully understand and accept that risk.
- **Past/backtested performance does not predict future results.** Deriv's synthetic indices are algorithmically generated; historical patterns can and do stop working with no warning.
- **Never share your Deriv API token** with anyone, in any chat, prompt, or unencrypted store. Revoke and regenerate immediately if you ever suspect it's been exposed.
