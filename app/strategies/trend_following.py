"""
Strategy: Trend Following (EMA 9/21 crossover, ADX-filtered)

Thesis: on trending runs (common on Boom/Crash/Step indices after a
volatility spike), momentum tends to continue for a while rather than
mean-revert immediately. This is the complement to mean_reversion.py.

Signal logic:
  1. Compute EMA(9) and EMA(21).
  2. Compute ADX(14) as a trend-strength filter — a crossover in a flat,
     choppy market (low ADX) is noise, not a trend; we ignore it.
  BUY  when EMA(9) crosses above EMA(21) AND ADX > adx_threshold (real trend).
  SELL when EMA(9) crosses below EMA(21) AND ADX > adx_threshold.
  HOLD otherwise, including all crossovers that happen while ADX is low.

This will whipsaw (repeated small losses) in genuinely range-bound
conditions if the ADX filter is set too low — that's the known failure
mode, and it's the mirror of mean_reversion's failure mode in trends.
"""
from app.strategies.base import Signal, Strategy, StrategyContext
from app.strategies.indicators import adx, ema


class TrendFollowingStrategy(Strategy):
    name = "trend_following"
    description = ("EMA(9/21) crossover confirmed by ADX > threshold to filter out "
                    "chop. Bets an established move continues. Whipsaws in range-bound "
                    "markets if ADX threshold is too permissive.")
    risk_label = "standard"
    min_candles = 45

    def __init__(self, fast_period: int = 9, slow_period: int = 21,
                 adx_period: int = 14, adx_threshold: float = 20.0):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold

    def generate_signal(self, ctx: StrategyContext) -> Signal:
        closes = ctx.closes
        if len(closes) < max(self.min_candles, self.slow_period + 2, self.adx_period * 2 + 2):
            return "HOLD"

        ema_fast = ema(closes, self.fast_period)
        ema_slow = ema(closes, self.slow_period)
        adx_vals = adx(ctx.highs, ctx.lows, closes, self.adx_period)

        current_adx = adx_vals[-1]
        if current_adx != current_adx:  # NaN
            return "HOLD"
        if current_adx < self.adx_threshold:
            return "HOLD"  # not trending enough to trust a crossover

        prev_diff = ema_fast[-2] - ema_slow[-2]
        curr_diff = ema_fast[-1] - ema_slow[-1]

        crossed_up = prev_diff <= 0 < curr_diff
        crossed_down = prev_diff >= 0 > curr_diff

        if crossed_up:
            return "BUY"
        if crossed_down:
            return "SELL"
        return "HOLD"
