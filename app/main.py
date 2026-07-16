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
from app.scanner import run_scan
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
# Verified live against Deriv's own API Playground: a single Bearer token
# (a PAT generated at developers.deriv.com/dashboard/tokens, or an OAuth
# access_token) authenticates REST calls to list every account — demo and
# real — under that login in one shot. No separate per-account token
# needed; only the account_id differs between demo/real when opening a
# trading WebSocket connection later. See deriv_client.py for the full
# picture of how the current API works.
# ---------------------------------------------------------------------------

async def _discover_and_upsert_deriv_user(db: Session, token: str) -> tuple[User, list[dict]]:
    """Lists accounts for the given token via REST, then creates or updates
    the matching local User row. Shared by the PAT login endpoint below."""
    client = DerivClient(api_token=token)
    try:
        accounts = await client.list_accounts()
    except Exception as e:
        raise HTTPException(400, f"Deriv rejected that token: {e}")

    if not accounts:
        raise HTTPException(400, "Deriv accepted the token but returned no accounts.")

    demo = next((a for a in accounts if a.get("account_type") == "demo"), None)
    real = next((a for a in accounts if a.get("account_type") != "demo"), None)
    primary = real or demo
    loginid = primary["account_id"]

    user = (db.query(User)
            .filter((User.deriv_loginid == loginid)
                    | (User.deriv_demo_account_id == (demo["account_id"] if demo else None))
                    | (User.deriv_real_account_id == (real["account_id"] if real else None)))
            .first())
    if not user:
        user = User(deriv_loginid=loginid)
        db.add(user)

    user.deriv_bearer_token_encrypted = encrypt_token(token)
    user.deriv_currency = primary.get("currency", "USD")
    if demo:
        user.deriv_demo_account_id = demo["account_id"]
    if real:
        user.deriv_real_account_id = real["account_id"]
    if not user.deriv_loginid:
        user.deriv_loginid = loginid

    db.commit()
    db.refresh(user)
    return user, accounts


class DerivPatLoginRequest(BaseModel):
    token: str


@app.post("/auth/deriv-pat")
async def deriv_pat_login(req: DerivPatLoginRequest, db: Session = Depends(get_db)):
    """Log in using a Deriv Personal Access Token. Generate one at
    developers.deriv.com → API tokens, scoped to Trade + Account
    management — paste it here directly, it's encrypted at rest and never
    logged or returned in any response after this."""
    user, accounts = await _discover_and_upsert_deriv_user(db, req.token)
    return {
        "access_token": create_access_token_for_user(user),
        "token_type": "bearer",
        "deriv_loginid": user.deriv_loginid,
        "has_demo": bool(user.deriv_demo_account_id),
        "has_real": bool(user.deriv_real_account_id),
    }


@app.post("/auth/deriv-pat/add")
async def deriv_pat_add_account(req: DerivPatLoginRequest, user: User = Depends(get_current_user),
                                 db: Session = Depends(get_db)):
    """Re-run discovery with a token from a different Deriv login, linking
    it to the currently signed-in user. Rarely needed now — one token
    already reveals both demo and real accounts for its own login."""
    updated_user, accounts = await _discover_and_upsert_deriv_user(db, req.token)
    if updated_user.id != user.id:
        raise HTTPException(
            400,
            "That token belongs to a different Deriv login than the one you're signed in as."
        )
    return {
        "has_demo": bool(updated_user.deriv_demo_account_id),
        "has_real": bool(updated_user.deriv_real_account_id),
    }


# ---------------------------------------------------------------------------
# Auth — Deriv OAuth (kept, functional for the exchange itself — the
# resulting access_token works the same as a PAT for REST calls, so it's
# actually usable here too; just not wired into the primary login screen).
# ---------------------------------------------------------------------------

@app.get("/auth/deriv/login")
def deriv_login_url():
    return {"url": build_authorize_url()}


class DerivCallbackRequest(BaseModel):
    code: str
    state: str


@app.post("/auth/deriv/callback")
async def deriv_callback(req: DerivCallbackRequest, db: Session = Depends(get_db)):
    try:
        token_data = await exchange_code_for_token(req.code, req.state)
    except ValueError as e:
        raise HTTPException(400, str(e))

    access_token = token_data["access_token"]
    user, accounts = await _discover_and_upsert_deriv_user(db, access_token)

    return {
        "access_token": create_access_token_for_user(user),
        "token_type": "bearer",
        "deriv_loginid": user.deriv_loginid,
        "has_demo": bool(user.deriv_demo_account_id),
        "has_real": bool(user.deriv_real_account_id),
    }


@app.get("/account/balances")
async def account_balances(user: User = Depends(get_current_user)):
    """Live balances pulled directly from Deriv via REST — a single call
    returns both demo and real in one shot, no WebSocket connection needed
    at all for this."""
    if not user.deriv_bearer_token_encrypted:
        raise HTTPException(400, "Connect your Deriv account first.")

    client = DerivClient(api_token=decrypt_token(user.deriv_bearer_token_encrypted))
    try:
        accounts = await client.list_accounts()
    except Exception as e:
        raise HTTPException(400, f"Failed to fetch accounts: {e}")

    result = {"demo": None, "real": None}
    for a in accounts:
        entry = {"loginid": a["account_id"], "balance": a.get("balance"), "currency": a.get("currency")}
        if a.get("account_type") == "demo":
            result["demo"] = entry
        else:
            result["real"] = entry
    return result


def _bot_connection_info(user: User, mode: str) -> tuple[str, str]:
    """Returns (decrypted_bearer_token, account_id) for opening a trading
    connection in the given mode."""
    if not user.deriv_bearer_token_encrypted:
        raise HTTPException(400, "Connect your Deriv account first.")
    account_id = user.account_id_for_mode(mode)
    if not account_id:
        raise HTTPException(
            400,
            f"No {mode} Deriv account linked to this login. Log in again or link one from the sidebar."
        )
    return decrypt_token(user.deriv_bearer_token_encrypted), account_id


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
    strategy/asset combination in the Backtest Lab before committing to it.
    Historical market data is public, so this doesn't need your Deriv
    account connected at all — login is required here only to keep the API
    consistently behind auth, not because the data itself needs it."""
    if req.strategy not in STRATEGY_REGISTRY:
        raise HTTPException(400, f"Unknown strategy. Valid: {list(STRATEGY_REGISTRY)}")

    result = await run_backtest(
        symbol=req.asset, strategy_name=req.strategy,
        base_stake=req.base_stake, lookback_candles=req.lookback_candles,
        assumed_payout_ratio=req.assumed_payout_ratio,
    )
    return result.__dict__


@app.post("/bots/{bot_id}/backtest")
async def backtest_bot(bot_id: int, req: BacktestRequest, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    bot = _get_owned_bot(bot_id, user, db)
    result = await run_backtest(
        symbol=bot.asset, strategy_name=bot.strategy,
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

    token, account_id = _bot_connection_info(user, bot.account_mode)
    await bot_manager.start_bot(bot, token, account_id)
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


# ---------------------------------------------------------------------------
# Manual / instant trading — separate from the automated strategy bots
# above. No warm-up period: place a Rise/Fall trade immediately.
#
# Only CALL/PUT (Rise/Fall) is offered here. Deriv's older platform
# supports many more contract types (Higher/Lower, Touch/No Touch,
# Matches/Differs, Even/Odd, etc.), but this backend has only verified
# CALL/PUT proposal+buy actually executes correctly on the current API —
# the message SHAPE matches the old API exactly (confirmed for balance and
# ticks_history), but proposal/buy specifically haven't been confirmed live
# yet. Expand this list only after testing each contract_type on demo.
# ---------------------------------------------------------------------------

class ManualTradeRequest(BaseModel):
    mode: str  # "demo" | "real"
    symbol: str
    trade_type: str = "rise_fall"  # "rise_fall" | "even_odd"
    direction: str  # "rise"/"fall" for rise_fall; "even"/"odd" for even_odd
    stake: float = Field(gt=0)
    duration: int = 5
    duration_unit: str = "t"  # t=ticks, s=seconds, m=minutes


# Rise/Fall (CALL/PUT) is the only combination confirmed to actually place
# and resolve a trade correctly on the current API — verified structurally
# against Deriv's own Playground (message shapes match the older API
# exactly). Even/Odd (DIGITEVEN/DIGITODD) uses the same message format by
# the same logic, but hasn't been confirmed with a real executed trade yet.
# Test with a small demo stake before trusting it.
_CONTRACT_TYPE_MAP = {
    ("rise_fall", "rise"): "CALL",
    ("rise_fall", "fall"): "PUT",
    ("even_odd", "even"): "DIGITEVEN",
    ("even_odd", "odd"): "DIGITODD",
}


@app.post("/trading/execute")
async def execute_manual_trade(req: ManualTradeRequest, user: User = Depends(get_current_user),
                                db: Session = Depends(get_db)):
    contract_type = _CONTRACT_TYPE_MAP.get((req.trade_type, req.direction))
    if not contract_type:
        raise HTTPException(400, f"Unsupported trade_type/direction combination: "
                                  f"{req.trade_type}/{req.direction}")
    if req.mode not in ("demo", "real"):
        raise HTTPException(400, "mode must be 'demo' or 'real'")
    if req.mode == "real" and settings.deriv_account_mode != "real":
        raise HTTPException(
            400,
            "Real-money trading isn't enabled on this deployment (DERIV_ACCOUNT_MODE != 'real')."
        )

    token, account_id = _bot_connection_info(user, req.mode)

    client = DerivClient(api_token=token)
    try:
        await client.connect(account_id=account_id)
        prop = await client.proposal(req.symbol, contract_type, req.stake,
                                      duration=req.duration, duration_unit=req.duration_unit)
        if not prop or "id" not in prop:
            raise HTTPException(400, f"Deriv didn't return a valid quote for {req.symbol}.")
        buy_result = await client.buy(prop["id"], float(prop["ask_price"]))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Trade failed: {e}")
    finally:
        await client.close()

    trade = Trade(
        bot_id=None,
        user_id=user.id,
        symbol=req.symbol,
        trade_type=contract_type,
        stake=req.stake,
        entry_price=buy_result.get("buy_price"),
        is_demo=(req.mode == "demo"),
        contract_id=str(buy_result.get("contract_id")) if buy_result.get("contract_id") else None,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    return {
        "trade_id": trade.id,
        "contract_id": buy_result.get("contract_id"),
        "buy_price": buy_result.get("buy_price"),
        "payout": buy_result.get("payout"),
        "longcode": buy_result.get("longcode"),
    }


@app.get("/trading/history")
def manual_trade_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trades = (db.query(Trade)
              .filter(Trade.user_id == user.id, Trade.bot_id.is_(None))
              .order_by(Trade.opened_at.desc())
              .limit(100)
              .all())
    return [
        {"id": t.id, "symbol": t.symbol, "type": t.trade_type, "stake": t.stake,
         "entry_price": t.entry_price, "profit_loss": t.profit_loss, "is_demo": t.is_demo,
         "opened_at": t.opened_at, "contract_id": t.contract_id}
        for t in trades
    ]


# ---------------------------------------------------------------------------
# Scanner — automated backtesting across strategies/assets, not an AI
# prediction. See app/scanner.py for the full explanation of what this is
# and, importantly, what it isn't.
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    base_stake: float = 1.0
    assets: list[str] | None = None
    lookback_candles: int = 3000
    assumed_payout_ratio: float = 0.85
    min_trades: int = 10


@app.post("/scanner/run")
async def scanner_run(req: ScanRequest, user: User = Depends(get_current_user)):
    """Doesn't need a Deriv token — same as backtesting, this only touches
    public market data."""
    return await run_scan(
        base_stake=req.base_stake, assets=req.assets,
        lookback_candles=req.lookback_candles,
        assumed_payout_ratio=req.assumed_payout_ratio,
        min_trades=req.min_trades,
    )


class ScanLaunchRequest(BaseModel):
    strategy: str
    asset: str
    stake: float = Field(gt=0)
    stop_loss: float | None = None
    take_profit: float | None = None
    max_daily_loss: float | None = None


@app.post("/scanner/launch")
async def scanner_launch(req: ScanLaunchRequest, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """Creates a bot from a scan result and starts it immediately on demo —
    the one-click 'use the winning combo' action. Still subject to the same
    24h forced demo period as any other bot; nothing here bypasses that."""
    if req.strategy not in RECOMMENDED_STRATEGIES:
        raise HTTPException(400, "Scanner only launches recommended (non-high-risk) strategies.")

    bot = Bot(
        user_id=user.id, name=f"Scanner: {req.strategy} / {req.asset}", strategy=req.strategy,
        asset=req.asset, stake=req.stake, stop_loss=req.stop_loss, take_profit=req.take_profit,
        max_daily_loss=req.max_daily_loss, status="stopped", account_mode="demo",
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)

    bot.demo_started_at = dt.datetime.utcnow()
    bot.status = "demo_running"
    db.commit()

    token, account_id = _bot_connection_info(user, "demo")
    await bot_manager.start_bot(bot, token, account_id)

    return {"bot_id": bot.id, "status": bot.status, "message": "Launched on demo."}
