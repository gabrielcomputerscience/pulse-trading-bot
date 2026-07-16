"""
Runs one live bot: builds a rolling candle window from Deriv's tick stream,
calls the strategy each time a candle closes, and executes trades through
DerivClient. Enforces the safety rails that must never be bypassable by
config: forced demo period on new bots, stop-loss / take-profit / max daily
loss, and Martingale's hard stake caps.

This is deliberately synchronous-looking (one candle -> one decision) even
though ticks arrive continuously — we aggregate ticks into fixed-interval
candles ourselves since Deriv's raw tick stream doesn't group them for us.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.database import Bot, Trade
from app.deriv_client import DerivClient
from app.strategies import get_strategy
from app.strategies.base import Candle, StrategyContext

logger = logging.getLogger("bot_engine")

CANDLE_INTERVAL_SECONDS = 60  # 1-minute candles built from raw ticks


class RunningBot:
    def __init__(self, bot: Bot, api_token: str, account_id: str, db_session_factory):
        self.bot_config = bot
        self.api_token = api_token
        self.account_id = account_id
        self.db_session_factory = db_session_factory
        self.strategy = get_strategy(bot.strategy)
        self.ctx = StrategyContext(candles=[])
        self.client: DerivClient | None = None
        self._task: asyncio.Task | None = None
        self._stop_requested = False
        self.daily_pnl = 0.0
        self.daily_pnl_date = dt.date.today()

    def is_forced_demo(self) -> bool:
        if not self.bot_config.demo_started_at:
            return True
        elapsed = dt.datetime.utcnow() - self.bot_config.demo_started_at
        return elapsed < dt.timedelta(hours=settings.forced_demo_hours)

    async def start(self):
        self.client = DerivClient(api_token=self.api_token)
        await self.client.connect(account_id=self.account_id)
        await self._seed_history()
        self._task = asyncio.create_task(self._run())

    async def _seed_history(self):
        """Pulls recent real candles from Deriv on startup instead of
        waiting for enough live ticks to accumulate — this is what cuts
        the old 25-45 minute warm-up down to roughly one candle interval
        (about a minute). Uses the same 1-minute-candle timeframe the
        backtester measures against, so live behavior still matches what
        was actually backtested — only the wait is shorter, not the
        underlying strategy logic."""
        needed = self.strategy.min_candles + 10  # small buffer above the strict minimum
        try:
            raw = await self.client.ticks_history(self.bot_config.asset, count=needed, style="candles")
        except Exception:
            logger.exception("Bot %s: history seed failed, falling back to live warm-up", self.bot_config.id)
            return

        for c in raw:
            self.ctx.candles.append(Candle(
                epoch=c["epoch"], open=float(c["open"]), high=float(c["high"]),
                low=float(c["low"]), close=float(c["close"]),
            ))

        if len(self.ctx.candles) >= self.strategy.min_candles:
            await self._on_candle_closed()  # check for an immediate signal using the seeded history

    async def stop(self):
        self._stop_requested = True
        if self._task:
            self._task.cancel()
        if self.client:
            await self.client.close()

    async def _run(self):
        symbol = self.bot_config.asset
        current_bucket_start = None
        bucket_ticks: list[float] = []
        bucket_open = None

        try:
            async for tick in self.client.subscribe_ticks(symbol):
                if self._stop_requested:
                    break

                price = float(tick["quote"])
                epoch = int(tick["epoch"])
                bucket_start = epoch - (epoch % CANDLE_INTERVAL_SECONDS)

                if current_bucket_start is None:
                    current_bucket_start = bucket_start
                    bucket_open = price
                    bucket_ticks = [price]
                    continue

                if bucket_start != current_bucket_start:
                    # bucket closed -> form a candle and let the strategy react
                    candle = Candle(
                        epoch=current_bucket_start,
                        open=bucket_open,
                        high=max(bucket_ticks),
                        low=min(bucket_ticks),
                        close=bucket_ticks[-1],
                    )
                    self.ctx.candles.append(candle)
                    await self._on_candle_closed()

                    current_bucket_start = bucket_start
                    bucket_open = price
                    bucket_ticks = [price]
                else:
                    bucket_ticks.append(price)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Bot %s crashed", self.bot_config.id)
            self._set_status("stopped")

    async def _on_candle_closed(self):
        if len(self.ctx.candles) < self.strategy.min_candles:
            return

        self._reset_daily_pnl_if_new_day()
        if self.bot_config.max_daily_loss and self.daily_pnl <= -abs(self.bot_config.max_daily_loss):
            logger.warning("Bot %s hit max daily loss, halting for today", self.bot_config.id)
            return
        if self.bot_config.stop_loss and self.bot_config.realized_pnl <= -abs(self.bot_config.stop_loss):
            logger.warning("Bot %s hit stop loss, stopping", self.bot_config.id)
            await self._auto_stop("stop_loss")
            return
        if self.bot_config.take_profit and self.bot_config.realized_pnl >= self.bot_config.take_profit:
            logger.info("Bot %s hit take profit, stopping", self.bot_config.id)
            await self._auto_stop("take_profit")
            return

        signal = self.strategy.generate_signal(self.ctx)
        if signal == "HOLD":
            return

        stake = self.strategy.next_stake(self.bot_config.stake, self.ctx)
        contract_type = "CALL" if signal == "BUY" else "PUT"

        try:
            prop = await self.client.proposal(self.bot_config.asset, contract_type, stake)
            if not prop or "id" not in prop:
                return
            result = await self.client.buy(prop["id"], float(prop["ask_price"]))
        except Exception:
            logger.exception("Trade execution failed for bot %s", self.bot_config.id)
            return

        trade_id = self._record_trade(contract_type, stake, result)
        contract_id = result.get("contract_id")
        if trade_id and contract_id:
            asyncio.create_task(self._resolve_trade(trade_id, contract_id))

    def _record_trade(self, contract_type: str, stake: float, buy_result: dict) -> int | None:
        db: Session = self.db_session_factory()
        try:
            trade = Trade(
                bot_id=self.bot_config.id,
                symbol=self.bot_config.asset,
                trade_type=contract_type,
                stake=stake,
                entry_price=buy_result.get("buy_price"),
                is_demo=self.is_forced_demo() or self.bot_config.account_mode == "demo",
                contract_id=str(buy_result.get("contract_id")) if buy_result.get("contract_id") else None,
            )
            db.add(trade)
            db.commit()
            db.refresh(trade)
            return trade.id
        finally:
            db.close()

    async def _resolve_trade(self, trade_id: int, contract_id: int,
                              poll_interval: float = 3.0, max_attempts: int = 200):
        """Polls the contract until Deriv marks it sold, then records the
        real outcome and checks stop-loss/take-profit. Not yet confirmed
        against a real trade the way balance/ticks_history were — this is
        the piece most worth watching closely on your first live bot run."""
        for _ in range(max_attempts):
            await asyncio.sleep(poll_interval)
            try:
                status = await self.client.check_open_contract(contract_id)
            except Exception:
                logger.exception("Failed checking contract %s for bot %s", contract_id, self.bot_config.id)
                continue

            if not status.get("is_sold"):
                continue

            profit_loss = status.get("profit")
            if profit_loss is None:
                sell_price = status.get("sell_price")
                buy_price = status.get("buy_price")
                if sell_price is not None and buy_price is not None:
                    profit_loss = float(sell_price) - float(buy_price)

            db: Session = self.db_session_factory()
            try:
                trade = db.query(Trade).filter(Trade.id == trade_id).first()
                if trade:
                    trade.profit_loss = profit_loss
                    trade.exit_price = status.get("sell_price")
                    trade.closed_at = dt.datetime.utcnow()
                    db.commit()
            finally:
                db.close()

            if profit_loss is not None:
                won = profit_loss > 0
                self.strategy.on_trade_closed(self.ctx, won=won, profit_loss=profit_loss)
                self.daily_pnl += profit_loss

                db2: Session = self.db_session_factory()
                try:
                    bot = db2.query(Bot).filter(Bot.id == self.bot_config.id).first()
                    if bot:
                        bot.realized_pnl = (bot.realized_pnl or 0.0) + profit_loss
                        db2.commit()
                        self.bot_config.realized_pnl = bot.realized_pnl
                finally:
                    db2.close()
            return

        logger.warning("Contract %s for bot %s never resolved after %d attempts",
                        contract_id, self.bot_config.id, max_attempts)

    async def _auto_stop(self, reason: str):
        self._stop_requested = True
        if self._task:
            self._task.cancel()
        if self.client:
            await self.client.close()
        db: Session = self.db_session_factory()
        try:
            bot = db.query(Bot).filter(Bot.id == self.bot_config.id).first()
            if bot:
                bot.status = "stopped"
                db.commit()
        finally:
            db.close()
        logger.info("Bot %s auto-stopped: %s", self.bot_config.id, reason)

    def _reset_daily_pnl_if_new_day(self):
        today = dt.date.today()
        if today != self.daily_pnl_date:
            self.daily_pnl_date = today
            self.daily_pnl = 0.0

    def _set_status(self, status: str):
        db: Session = self.db_session_factory()
        try:
            bot = db.query(Bot).get(self.bot_config.id)
            if bot:
                bot.status = status
                db.commit()
        finally:
            db.close()


class BotManager:
    """Process-local registry of running bots. For multi-worker deployment,
    swap this for a proper job queue (Celery/RQ) keyed by bot_id so only one
    worker ever runs a given bot at a time."""

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self._running: dict[int, RunningBot] = {}

    async def start_bot(self, bot: Bot, api_token: str, account_id: str):
        if bot.id in self._running:
            return
        running = RunningBot(bot, api_token, account_id, self.db_session_factory)
        await running.start()
        self._running[bot.id] = running

    async def stop_bot(self, bot_id: int):
        running = self._running.pop(bot_id, None)
        if running:
            await running.stop()

    def is_running(self, bot_id: int) -> bool:
        return bot_id in self._running
