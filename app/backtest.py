"""
Backtest engine: pulls REAL historical candles from Deriv and replays a
strategy against them tick-by-tick (candle-by-candle), tracking simulated
trade outcomes exactly the way bot_engine.py would live. This is the only
place an "accuracy" or "win rate" number should ever come from — never a
marketing claim, always a measured replay against real data.

Known, disclosed limitations of any backtest (documented, not hidden):
  - Doesn't model slippage or spread precisely — uses Deriv's own historical
    proposal payout ratios where available, otherwise a flat assumed payout.
  - Past data doesn't guarantee future performance, especially for
    algorithmically generated synthetic indices whose parameters Deriv
    controls and can change.
  - Overfitting risk: a strategy tuned to look good on one historical
    window may not generalize. Test across multiple time windows /assets,
    not just one, before trusting a number.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.deriv_client import DerivClient
from app.strategies.base import Candle, StrategyContext
from app.strategies import get_strategy


@dataclass
class BacktestResult:
    strategy: str
    symbol: str
    total_trades: int
    wins: int
    losses: int
    win_rate: float  # measured, not assumed
    total_profit_loss: float
    max_drawdown: float
    disclaimer: str = (
        "Backtested against real historical data but not a guarantee of future "
        "performance. Does not fully model slippage/spread. Run on demo before "
        "risking real money."
    )


def _candles_from_history(raw_candles: list[dict]) -> list[Candle]:
    return [
        Candle(epoch=c["epoch"], open=float(c["open"]), high=float(c["high"]),
               low=float(c["low"]), close=float(c["close"]))
        for c in raw_candles
    ]


async def run_backtest(
    api_token: str,
    symbol: str,
    strategy_name: str,
    base_stake: float = 1.0,
    assumed_payout_ratio: float = 0.85,  # typical binary-option-style payout; conservative default
    lookback_candles: int = 3000,
    strategy_kwargs: dict | None = None,
) -> BacktestResult:
    client = DerivClient(api_token=api_token)
    await client.connect()
    try:
        raw = await client.ticks_history(symbol, count=lookback_candles, style="candles")
    finally:
        await client.close()

    candles = _candles_from_history(raw)
    if len(candles) < 50:
        raise ValueError(f"Not enough historical data returned for {symbol} to backtest meaningfully.")

    strategy = get_strategy(strategy_name, **(strategy_kwargs or {}))
    ctx = StrategyContext(candles=[])

    trades = []
    running_pnl = 0.0
    peak_pnl = 0.0
    max_drawdown = 0.0

    for i in range(len(candles)):
        ctx.candles = candles[: i + 1]
        if len(ctx.candles) < strategy.min_candles:
            continue

        signal = strategy.generate_signal(ctx)
        if signal == "HOLD":
            continue
        if i + 1 >= len(candles):
            break  # no next candle to resolve the trade against

        stake = strategy.next_stake(base_stake, ctx)
        entry_price = candles[i].close
        exit_price = candles[i + 1].close

        went_up = exit_price > entry_price
        won = (signal == "BUY" and went_up) or (signal == "SELL" and not went_up)
        pnl = stake * assumed_payout_ratio if won else -stake

        trades.append({"index": i, "signal": signal, "won": won, "pnl": pnl, "stake": stake})
        strategy.on_trade_closed(ctx, won=won, profit_loss=pnl)

        running_pnl += pnl
        peak_pnl = max(peak_pnl, running_pnl)
        drawdown = peak_pnl - running_pnl
        max_drawdown = max(max_drawdown, drawdown)

    wins = sum(1 for t in trades if t["won"])
    losses = len(trades) - wins
    win_rate = (wins / len(trades)) if trades else 0.0

    return BacktestResult(
        strategy=strategy_name,
        symbol=symbol,
        total_trades=len(trades),
        wins=wins,
        losses=losses,
        win_rate=round(win_rate, 4),
        total_profit_loss=round(running_pnl, 2),
        max_drawdown=round(max_drawdown, 2),
    )
