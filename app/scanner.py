"""
Automated scanner: runs real backtests across every recommended strategy
(martingale excluded — same reasoning as everywhere else in this app) and
a curated set of assets, then ranks the results by measured performance.

This is NOT an AI or LLM making predictions about market direction — it's
systematic backtesting, automated. No strategy or ranking here claims to
predict the future; a combo that ranks first is the one that measured best
on historical data just now, nothing more. Deliberately excludes
low-sample results (below `min_trades`) from ranking, since a strategy
that only fired 1-2 times can look artificially perfect by chance — see
the mean_reversion 1-trade/100%-win-rate case that came up in testing.
"""
import asyncio
from dataclasses import dataclass

from app.backtest import BacktestResult, run_backtest
from app.market_data import DEFAULT_SYMBOLS
from app.strategies import RECOMMENDED_STRATEGIES


@dataclass
class ScanCandidate:
    strategy: str
    symbol: str
    result: BacktestResult | None
    error: str | None = None


async def _run_one(strategy: str, symbol: str, base_stake: float,
                    lookback_candles: int, assumed_payout_ratio: float) -> ScanCandidate:
    try:
        result = await run_backtest(
            symbol=symbol, strategy_name=strategy, base_stake=base_stake,
            lookback_candles=lookback_candles, assumed_payout_ratio=assumed_payout_ratio,
        )
        return ScanCandidate(strategy=strategy, symbol=symbol, result=result)
    except Exception as e:
        return ScanCandidate(strategy=strategy, symbol=symbol, result=None, error=str(e))


async def run_scan(
    base_stake: float = 1.0,
    assets: list[str] | None = None,
    lookback_candles: int = 3000,
    assumed_payout_ratio: float = 0.85,
    min_trades: int = 10,
) -> dict:
    """Runs every (recommended strategy × asset) combination concurrently,
    ranks the results, and returns both the full set and a clear top pick
    (or none, if nothing cleared the min_trades bar)."""
    symbols = assets or [s for s, _ in DEFAULT_SYMBOLS]

    tasks = [
        _run_one(strategy, symbol, base_stake, lookback_candles, assumed_payout_ratio)
        for strategy in RECOMMENDED_STRATEGIES
        for symbol in symbols
    ]
    candidates = await asyncio.gather(*tasks)

    scored = [c for c in candidates if c.result and c.result.total_trades >= min_trades]
    too_few_data = [c for c in candidates if c.result and c.result.total_trades < min_trades]
    failed = [c for c in candidates if c.error]

    # Rank by net simulated P/L first (what actually matters), win rate as tiebreaker.
    scored.sort(key=lambda c: (c.result.total_profit_loss, c.result.win_rate), reverse=True)

    top_pick = scored[0] if scored and scored[0].result.total_profit_loss > 0 else None

    return {
        "top_pick": _serialize(top_pick) if top_pick else None,
        "ranked": [_serialize(c) for c in scored],
        "insufficient_data": [_serialize(c) for c in too_few_data],
        "failed": [{"strategy": c.strategy, "symbol": c.symbol, "error": c.error} for c in failed],
        "note": (
            "Ranked by measured backtest results only — this is systematic backtesting, "
            "not a prediction. A positive top pick means it measured well on recent "
            "historical data, not that it's guaranteed to keep working."
            if top_pick else
            "No combination showed a positive simulated result with enough trades to be "
            "meaningful. That's a real, useful answer — it means nothing tested currently "
            "has a measurable edge, not that the scan failed."
        ),
    }


def _serialize(c: ScanCandidate) -> dict:
    r = c.result
    return {
        "strategy": c.strategy,
        "symbol": c.symbol,
        "total_trades": r.total_trades,
        "win_rate": r.win_rate,
        "total_profit_loss": r.total_profit_loss,
        "max_drawdown": r.max_drawdown,
    }
