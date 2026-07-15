"""
Strategy: Volatility Mean Reversion (Bollinger Bands + RSI + rejection candle)

Thesis: on range-bound / choppy synthetic indices, price that stretches far
from its recent average tends to snap back, rather than continue. This is
the opposite bet from trend_following.py — deliberately so, since one of
these two should be "on" depending on current market regime.

Signal logic:
  BUY  when close < lower Bollinger Band AND RSI < 30 (oversold) AND the
       latest candle shows a bullish rejection (long lower wick, close
       near the high of the candle) — i.e. buyers stepped in, not just
       "it's low."
  SELL when the mirror-image conditions hold (upper band, RSI > 70,
       bearish rejection with long upper wick).
  HOLD otherwise.

This will lose money in a strong, sustained trend — bands keep expanding
and RSI can stay pinned at an extreme for a long time ("riding the band").
That's expected; pair with an ADX filter or trend_following for coverage,
or only enable it when trend_following's ADX filter says "not trending."
"""
from app.strategies.base import Signal, Strategy, StrategyContext
from app.strategies.indicators import bollinger_bands, rsi


def _is_bullish_rejection(c) -> bool:
    body = abs(c.close - c.open)
    lower_wick = min(c.open, c.close) - c.low
    total_range = c.high - c.low
    if total_range <= 0:
        return False
    return lower_wick > body * 1.5 and (c.close - c.low) / total_range > 0.6


def _is_bearish_rejection(c) -> bool:
    body = abs(c.close - c.open)
    upper_wick = c.high - max(c.open, c.close)
    total_range = c.high - c.low
    if total_range <= 0:
        return False
    return upper_wick > body * 1.5 and (c.high - c.close) / total_range > 0.6


class MeanReversionStrategy(Strategy):
    name = "mean_reversion"
    description = ("Bollinger Bands + RSI extremes + rejection-candle confirmation. "
                    "Bets price snaps back toward the mean in range-bound conditions. "
                    "Underperforms in strong trends.")
    risk_label = "standard"
    min_candles = 25

    def __init__(self, bb_period: int = 20, bb_std: float = 2.0, rsi_period: int = 14,
                 rsi_oversold: float = 30, rsi_overbought: float = 70):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    def generate_signal(self, ctx: StrategyContext) -> Signal:
        closes = ctx.closes
        if len(closes) < max(self.min_candles, self.bb_period, self.rsi_period + 1):
            return "HOLD"

        bands = bollinger_bands(closes, self.bb_period, self.bb_std)
        rsi_vals = rsi(closes, self.rsi_period)

        current = ctx.candles[-1]
        lower_band = bands["lower"][-1]
        upper_band = bands["upper"][-1]
        current_rsi = rsi_vals[-1]

        if lower_band != lower_band or current_rsi != current_rsi:  # NaN check
            return "HOLD"

        if current.close < lower_band and current_rsi < self.rsi_oversold and _is_bullish_rejection(current):
            return "BUY"
        if current.close > upper_band and current_rsi > self.rsi_overbought and _is_bearish_rejection(current):
            return "SELL"
        return "HOLD"
