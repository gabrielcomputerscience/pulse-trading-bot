"""
Autopilot: the "just handle it" mode. Set stake/stop-loss/take-profit once,
enable it, and it takes care of the rest — periodically re-scanning every
recommended strategy against every curated asset, keeping bots running for
whatever currently clears your quality bar, and stopping ones that stop
qualifying.

Be clear about what this is NOT: it's not an AI reading the market and
making live judgment calls. It's the same deterministic backtest scanner
from scanner.py, run on a schedule, with mechanical start/stop rules. A
combo "qualifying" means it measured well on recent historical data by the
thresholds you set — not that it's guaranteed to keep working. This module
only ever touches demo accounts and only ever touches bots it created
itself (Bot.managed_by_autopilot) — it will never start, stop, or
otherwise interfere with a bot you created manually.
"""
import datetime as dt

from sqlalchemy.orm import Session

from app.database import AutopilotConfig, Bot, User
from app.scanner import run_scan


async def evaluate_and_reconcile(db: Session, user: User, config: AutopilotConfig,
                                  bot_manager, connection_info_fn) -> dict:
    """Runs one scan-and-adjust cycle for a single user. connection_info_fn
    is passed in (rather than imported) to avoid a circular import with
    main.py, which owns _bot_connection_info and bot_manager."""
    scan = await run_scan(
        base_stake=config.base_stake,
        lookback_candles=config.lookback_candles,
        min_trades=config.min_trades,
    )

    qualifying = [
        c for c in scan["ranked"]
        if c["win_rate"] >= config.min_win_rate and c["total_profit_loss"] > 0
    ]
    desired_keys = {(c["strategy"], c["symbol"]) for c in qualifying}

    managed_bots = (db.query(Bot)
                    .filter(Bot.user_id == user.id, Bot.managed_by_autopilot.is_(True))
                    .all())
    running_keys = {
        (b.strategy, b.asset): b for b in managed_bots
        if b.status in ("demo_running", "real_running")
    }

    stopped, started, kept = [], [], []

    for key, bot in running_keys.items():
        if key not in desired_keys:
            await bot_manager.stop_bot(bot.id)
            bot.status = "stopped"
            db.commit()
            stopped.append({"strategy": bot.strategy, "asset": bot.asset})
        else:
            kept.append({"strategy": bot.strategy, "asset": bot.asset})

    for c in qualifying:
        key = (c["strategy"], c["symbol"])
        if key in running_keys:
            continue

        existing = next((b for b in managed_bots if (b.strategy, b.asset) == key), None)
        if existing:
            bot = existing
            bot.stake = config.base_stake
            bot.stop_loss = config.stop_loss
            bot.take_profit = config.take_profit
            bot.max_daily_loss = config.max_daily_loss
        else:
            bot = Bot(
                user_id=user.id,
                name=f"Autopilot: {c['strategy']} / {c['symbol']}",
                strategy=c["strategy"], asset=c["symbol"], stake=config.base_stake,
                stop_loss=config.stop_loss, take_profit=config.take_profit,
                max_daily_loss=config.max_daily_loss, status="stopped", account_mode="demo",
                managed_by_autopilot=True,
            )
            db.add(bot)
            db.commit()
            db.refresh(bot)

        if not bot.demo_started_at:
            bot.demo_started_at = dt.datetime.utcnow()
        bot.account_mode = "demo"
        bot.status = "demo_running"
        db.commit()

        token, account_id = connection_info_fn(user, "demo")
        await bot_manager.start_bot(bot, token, account_id)
        started.append({"strategy": c["strategy"], "asset": c["symbol"],
                         "win_rate": c["win_rate"], "net_pl": c["total_profit_loss"]})

    config.last_run_at = dt.datetime.utcnow()
    summary_parts = []
    if started:
        summary_parts.append(f"started {len(started)}")
    if stopped:
        summary_parts.append(f"stopped {len(stopped)}")
    if kept:
        summary_parts.append(f"kept {len(kept)} running")
    if not summary_parts:
        summary_parts.append("nothing currently qualifies")
    config.last_result_summary = ", ".join(summary_parts)
    db.commit()

    return {
        "started": started, "stopped": stopped, "kept": kept,
        "qualifying_count": len(qualifying), "scan_note": scan["note"],
    }
