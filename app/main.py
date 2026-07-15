"""
Pulse backend API.

Every endpoint that touches Deriv does so through DerivClient using the
user's own encrypted, decrypted-at-request-time token — the token is never
returned in any response, never logged, and this file never writes it to
disk anywhere other than the encrypted DB column.
"""
import datetime as dt

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import (create_access_token, create_access_token_for_user,
                       get_current_user, hash_password, verify_password)
from app.backtest import run_backtest
from app.bot_engine import BotManager
from app.config import settings
from app.database import Bot, SessionLocal, Trade, User, decrypt_token, encrypt_token, get_db, init_db
from app.deriv_client import DerivClient
from app.deriv_oauth import build_authorize_url, exchange_code_for_token
from app.market_data import fetch_ticker
from app.strategies import RECOMMENDED_STRATEGIES, STRATEGY_REGISTRY

app = FastAPI(title="Pulse Trading Platform API")

# Allow the local Vite dev server (and any origin you deploy the frontend to)
# to call this API. Tighten allow_origins to your real frontend domain(s)
# before hosting this for anyone but yourself.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bot_manager = BotManager(db_session_factory=SessionLocal)


@app.on_event("startup")
def on_startup():
    init_db()


# ---------------------------------------------------------------------------
# Auth — Personal Access Token login (primary flow)
#
# Deriv currently runs two separate, incompatible API systems: a newer
# REST + WebSocket "Options" API (what OAuth 2.0 access tokens are for),
# and the older WebSocket trading API that this whole backend is built on
# (what Deriv's own docs now label "Options Trading (Legacy)"). OAuth
# access tokens are not accepted by the legacy `authorize` command — they're
# a different token system entirely. Personal Access Tokens (PATs), which
# users generate themselves in Deriv's dashboard, DO work with the legacy
# API, so that's what this app uses for login. No password, no separate
# signup — same as before, just a pasted token instead of an OAuth redirect.
# ---------------------------------------------------------------------------

async def _discover_and_upsert_deriv_user(db: Session, token: str) -> tuple[User, dict]:
    """Authorizes over the (legacy) WebSocket API with the given token to
    discover which Deriv account it belongs to, then creates or updates the
    matching local User row. Shared by the PAT login endpoint below."""
    client = DerivClient(api_token=token)
    try:
        await client.connect()
        info = client.account_info
    except Exception as e:
        raise HTTPException(400, f"Deriv rejected that token: {e}")
    finally:
        await client.close()

    loginid = info.get("loginid")
    if not loginid:
        raise HTTPException(400, "Deriv accepted the token but returned no account info.")
    is_virtual = bool(info.get("is_virtual"))
    currency = info.get("currency", "USD")

    user = (db.query(User)
            .filter((User.deriv_loginid == loginid)
                    | (User.deriv_demo_loginid == loginid)
                    | (User.deriv_real_loginid == loginid))
            .first())
    if not user:
        user = User(deriv_loginid=loginid)
        db.add(user)

    user.deriv_currency = currency
    if is_virtual:
        user.deriv_demo_loginid = loginid
        user.deriv_demo_token_encrypted = encrypt_token(token)
    else:
        user.deriv_real_loginid = loginid
        user.deriv_real_token_encrypted = encrypt_token(token)
        if not user.deriv_loginid:
            user.deriv_loginid = loginid

    db.commit()
    db.refresh(user)
    return user, info


class DerivPatLoginRequest(BaseModel):
    token: str


@app.post("/auth/deriv-pat")
async def deriv_pat_login(req: DerivPatLoginRequest, db: Session = Depends(get_db)):
    """Log in (or link an additional account) using a Deriv Personal Access
    Token. Generate one at Deriv → Settings → API Token, scoped to Read +
    Trade only — paste it here directly, it's encrypted at rest and never
    logged or returned in any response after this."""
    user, info = await _discover_and_upsert_deriv_user(db, req.token)
    return {
        "access_token": create_access_token_for_user(user),
        "token_type": "bearer",
        "deriv_loginid": user.deriv_loginid,
        "has_demo": bool(user.deriv_demo_token_encrypted),
        "has_real": bool(user.deriv_real_token_encrypted),
        "connected_account_is_demo": bool(info.get("is_virtual")),
    }


@app.post("/auth/deriv-pat/add")
async def deriv_pat_add_account(req: DerivPatLoginRequest, user: User = Depends(get_current_user),
                                 db: Session = Depends(get_db)):
    """Link a second account (e.g. add a real-money token when you first
    logged in with only a demo token) to the currently signed-in user."""
    updated_user, info = await _discover_and_upsert_deriv_user(db, req.token)
    if updated_user.id != user.id:
        raise HTTPException(
            400,
            "That token belongs to a different Deriv login than the one you're signed in as."
        )
    return {
        "has_demo": bool(updated_user.deriv_demo_token_encrypted),
        "has_real": bool(updated_user.deriv_real_token_encrypted),
        "connected_account_is_demo": bool(info.get("is_virtual")),
    }


# ---------------------------------------------------------------------------
# Auth — Deriv OAuth (kept, but NOT wired to trading — see note above).
# The token this produces is only verified to work for the exchange itself;
# it is not usable with the legacy WebSocket API the rest of this backend
# relies on. Left here in case a future REST+WS migration revisits this.
# ---------------------------------------------------------------------------

@app.get("/auth/deriv/login")
def deriv_login_url():
    """Frontend redirects the browser to this URL. No backend redirect
    needed here — returning the URL as JSON keeps this endpoint simple and
    lets the frontend do the actual navigation."""
    return {"url": build_authorize_url()}


class DerivCallbackRequest(BaseModel):
    code: str
    state: str


@app.post("/auth/deriv/callback")
async def deriv_callback(req: DerivCallbackRequest, db: Session = Depends(get_db)):
    """NOTE: functional for the OAuth exchange itself, but the resulting
    access_token is not currently usable for trading (see module note
    above) — not used by the frontend's primary login flow."""
    try:
        token_data = await exchange_code_for_token(req.code, req.state)
    except ValueError as e:
        raise HTTPException(400, str(e))

    access_token = token_data["access_token"]
    user, info = await _discover_and_upsert_deriv_user(db, access_token)

    return {
        "access_token": create_access_token_for_user(user),
        "token_type": "bearer",
        "deriv_loginid": user.deriv_loginid,
        "has_demo": bool(user.deriv_demo_token_encrypted),
        "has_real": bool(user.deriv_real_token_encrypted),
        "connected_account_is_demo": bool(info.get("is_virtual")),
    }


@app.get("/account/balances")
async def account_balances(user: User = Depends(get_current_user)):
    """Live balances pulled directly from Deriv for whichever account types
    this user connected — not stored/cached numbers."""
    result = {"demo": None, "real": None}

    for mode, loginid, token_encrypted in [
        ("demo", user.deriv_demo_loginid, user.deriv_demo_token_encrypted),
        ("real", user.deriv_real_loginid, user.deriv_real_token_encrypted),
    ]:
        if not token_encrypted:
            continue
        client = DerivClient(api_token=decrypt_token(token_encrypted))
        try:
            await client.connect()
            bal = await client.balance()
            result[mode] = {
                "loginid": loginid,
                "balance": bal.get("balance"),
                "currency": bal.get("currency"),
            }
        except Exception as e:
            result[mode] = {"loginid": loginid, "error": str(e)}
        finally:
            await client.close()

    return result


def _token_for_bot_mode(user: User, mode: str) -> str:
    encrypted = user.token_for_mode(mode)
    if not encrypted:
        raise HTTPException(
            400,
            f"No {mode} Deriv account connected. Sign in with Deriv again and approve a {mode} account, "
            "or switch this bot's mode."
        )
    return decrypt_token(encrypted)


def _any_token(user: User) -> str:
    """For backtesting: historical market data access doesn't depend on
    demo vs real, so use whichever token is available."""
    encrypted = (user.deriv_demo_token_encrypted or user.deriv_real_token_encrypted
                 or user.deriv_token_encrypted)
    if not encrypted:
        raise HTTPException(400, "Connect your Deriv account first via Continue with Deriv.")
    return decrypt_token(encrypted)


# ---------------------------------------------------------------------------
# Auth — legacy manual signup/login (kept for /docs testing; the frontend
# no longer shows this flow now that Deriv OAuth is the primary path).
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    username: str
    password: str = Field(min_length=8)


@app.post("/auth/signup")
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(400, "Username already taken")
    user = User(username=req.username, hashed_password=hash_password(req.password))
    db.add(user)
    db.commit()
    return {"message": "Account created. Now add your Deriv API token via /auth/deriv-token."}


@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Invalid username or password")
    return {"access_token": create_access_token_for_user(user), "token_type": "bearer"}


class DerivTokenRequest(BaseModel):
    deriv_api_token: str


@app.post("/auth/deriv-token")
def set_deriv_token(req: DerivTokenRequest, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """Manual fallback: paste a token generated yourself in Deriv's
    dashboard. Not needed if you signed in via /auth/deriv/login."""
    user.deriv_token_encrypted = encrypt_token(req.deriv_api_token)
    db.commit()
    return {"message": "Deriv token stored securely."}


# ---------------------------------------------------------------------------
# Strategy catalogue
# ---------------------------------------------------------------------------

@app.get("/strategies")
def list_strategies():
    """Recommended strategies only. Martingale is intentionally excluded
    here — see /strategies/martingale for its separate high-risk opt-in."""
    return [
        {"name": name, "description": cls.description, "risk_label": cls.risk_label}
        for name, cls in STRATEGY_REGISTRY.items() if name in RECOMMENDED_STRATEGIES
    ]


@app.get("/strategies/martingale")
def martingale_info():
    cls = STRATEGY_REGISTRY["martingale"]
    return {
        "name": "martingale",
        "description": cls.description,
        "risk_label": "high_risk",
        "warning": ("This is a bet-sizing scheme, not a market-prediction strategy. It is "
                    "mathematically guaranteed to eventually hit a losing streak that exceeds "
                    "any stake cap or balance. Hard-capped doublings and absolute stake ceiling "
                    "are enforced server-side and cannot be disabled via this API."),
        "max_doublings": settings.martingale_max_doublings,
        "absolute_stake_cap": settings.martingale_absolute_stake_cap,
    }


# ---------------------------------------------------------------------------
# Market data (public — no auth, no user Deriv token needed)
# ---------------------------------------------------------------------------

@app.get("/market/ticker")
async def market_ticker():
    """Real quotes pulled live from Deriv for a fixed set of synthetic
    indices. Public endpoint — doesn't need a logged-in user or their token,
    since this is just market data, not an account action."""
    entries = await fetch_ticker()
    return [
        {"symbol": e.symbol, "name": e.display_name, "price": e.price,
         "change_pct": e.change_pct, "error": e.error}
        for e in entries
    ]


# ---------------------------------------------------------------------------
# Bots
# ---------------------------------------------------------------------------

class BotCreateRequest(BaseModel):
    name: str
    strategy: str
    asset: str
    stake: float = Field(gt=0)
    stop_loss: float | None = None
    take_profit: float | None = None
    max_daily_loss: float | None = None
    acknowledge_high_risk: bool = False  # must be true if strategy == "martingale"


@app.post("/bots")
def create_bot(req: BotCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.strategy not in STRATEGY_REGISTRY:
        raise HTTPException(400, f"Unknown strategy. Valid: {list(STRATEGY_REGISTRY)}")
    if req.strategy == "martingale" and not req.acknowledge_high_risk:
        raise HTTPException(
            400,
            "Martingale requires acknowledge_high_risk=true. Read GET /strategies/martingale "
            "first — this is a staking scheme that can blow up an account, not an accuracy play."
        )

    bot = Bot(
        user_id=user.id, name=req.name, strategy=req.strategy, asset=req.asset,
        stake=req.stake, stop_loss=req.stop_loss, take_profit=req.take_profit,
        max_daily_loss=req.max_daily_loss, status="stopped", account_mode="demo",
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return {"id": bot.id, "message": "Bot created. Backtest it before starting: POST /bots/{id}/backtest"}


@app.get("/bots")
def list_bots(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bots = db.query(Bot).filter(Bot.user_id == user.id).all()
    return [
        {"id": b.id, "name": b.name, "strategy": b.strategy, "asset": b.asset,
         "status": b.status, "account_mode": b.account_mode}
        for b in bots
    ]


def _get_owned_bot(bot_id: int, user: User, db: Session) -> Bot:
    bot = db.query(Bot).filter(Bot.id == bot_id, Bot.user_id == user.id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    return bot


class BacktestRequest(BaseModel):
    lookback_candles: int = 3000
    assumed_payout_ratio: float = 0.85


class FreeformBacktestRequest(BaseModel):
    strategy: str
    asset: str
    base_stake: float = 1.0
    lookback_candles: int = 3000
    assumed_payout_ratio: float = 0.85


@app.post("/backtest")
async def freeform_backtest(req: FreeformBacktestRequest, user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """Run a backtest without first saving a bot — for exploring a
    strategy/asset combination in the Backtest Lab before committing to it."""
    if req.strategy not in STRATEGY_REGISTRY:
        raise HTTPException(400, f"Unknown strategy. Valid: {list(STRATEGY_REGISTRY)}")

    token = _any_token(user)
    result = await run_backtest(
        api_token=token, symbol=req.asset, strategy_name=req.strategy,
        base_stake=req.base_stake, lookback_candles=req.lookback_candles,
        assumed_payout_ratio=req.assumed_payout_ratio,
    )
    return result.__dict__


@app.post("/bots/{bot_id}/backtest")
async def backtest_bot(bot_id: int, req: BacktestRequest, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    bot = _get_owned_bot(bot_id, user, db)
    token = _any_token(user)
    result = await run_backtest(
        api_token=token, symbol=bot.asset, strategy_name=bot.strategy,
        base_stake=bot.stake, lookback_candles=req.lookback_candles,
        assumed_payout_ratio=req.assumed_payout_ratio,
    )
    return result.__dict__


@app.post("/bots/{bot_id}/start")
async def start_bot(bot_id: int, confirm_real_money: bool = False,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bot = _get_owned_bot(bot_id, user, db)

    if not bot.demo_started_at:
        bot.demo_started_at = dt.datetime.utcnow()
        bot.account_mode = "demo"
        db.commit()

    elapsed = dt.datetime.utcnow() - bot.demo_started_at
    in_forced_demo = elapsed < dt.timedelta(hours=settings.forced_demo_hours)

    if in_forced_demo:
        bot.status = "demo_running"
        bot.account_mode = "demo"
    else:
        if confirm_real_money and settings.deriv_account_mode == "real":
            bot.status = "real_running"
            bot.account_mode = "real"
        else:
            bot.status = "demo_running"
            bot.account_mode = "demo"
    db.commit()

    token = _token_for_bot_mode(user, bot.account_mode)
    await bot_manager.start_bot(bot, token)
    return {"status": bot.status, "forced_demo_remaining_hours": max(
        0, settings.forced_demo_hours - elapsed.total_seconds() / 3600)}


@app.post("/bots/{bot_id}/stop")
async def stop_bot(bot_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bot = _get_owned_bot(bot_id, user, db)
    await bot_manager.stop_bot(bot_id)
    bot.status = "stopped"
    db.commit()
    return {"status": "stopped"}


@app.get("/bots/{bot_id}/trades")
def bot_trades(bot_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bot = _get_owned_bot(bot_id, user, db)
    trades = db.query(Trade).filter(Trade.bot_id == bot.id).order_by(Trade.opened_at.desc()).all()
    return [
        {"id": t.id, "symbol": t.symbol, "type": t.trade_type, "stake": t.stake,
         "profit_loss": t.profit_loss, "is_demo": t.is_demo, "opened_at": t.opened_at}
        for t in trades
    ]


@app.get("/bots/{bot_id}/status")
def bot_status(bot_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bot = _get_owned_bot(bot_id, user, db)
    return {
        "status": bot.status, "account_mode": bot.account_mode,
        "is_running": bot_manager.is_running(bot.id),
    }
