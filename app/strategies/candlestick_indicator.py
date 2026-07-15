"""
Strategy: Candlestick Pattern + Indicator Confirmation

Thesis: raw candlestick patterns (hammer, engulfing, doji) are individually
weak/noisy signals — plenty of hammers appear and go nowhere. Requiring an
indicator (RSI or MACD histogram) to agree cuts down false positives at the
cost of trading less often. This is a deliberately lower-frequency, higher
signal-quality approach rather than a high-win-rate claim.

Signal logic:
  1. Detect a small set of well-defined patterns on the latest candle(s):
     hammer, bullish/bearish engulfing, doji.
  2. Only emit BUY/SELL if RSI or MACD histogram direction agrees with the
     pattern's implied direction. A hammer with no RSI/MACD confirmation
     is discarded as HOLD, not traded on pattern alone.
"""
from app.strategies.base import Signal, Strategy, StrategyContext
from app.strategies.indicators import macd, rsi


def _is_hammer(c) -> bool:
    body = abs(c.close - c.open)
    lower_wick = min(c.open, c.close) - c.low
    upper_wick = c.high - max(c.open, c.close)
    total_range = c.high - c.low
    if total_range <= 0 or body == 0:
        return False
    return lower_wick >= body * 2 and upper_wick <= body * 0.5


def _is_bullish_engulfing(prev, curr) -> bool:
    prev_bearish = prev.close < prev.open
    curr_bullish = curr.close > curr.open
    return prev_bearish and curr_bullish and curr.open <= prev.close and curr.close >= prev.open


def _is_bearish_engulfing(prev, curr) -> bool:
    prev_bullish = prev.close > prev.open
    curr_bearish = curr.close < curr.open
    return prev_bullish and curr_bearish and curr.open >= prev.close and curr.close <= prev.open


def _is_doji(c) -> bool:
    total_range = c.high - c.low
    if total_range <= 0:
        return False
    return abs(c.close - c.open) / total_range < 0.1


class CandlestickIndicatorStrategy(Strategy):
    name = "candlestick_indicator"
    description = ("Hammer / engulfing / doji pattern detection, only acted on when "
                    "RSI or MACD histogram direction agrees. Lower trade frequency by "
                    "design, aiming for fewer, better-confirmed signals.")
    risk_label = "standard"
    min_candles = 30

    def __init__(self, rsi_period: int = 14, rsi_midline: float = 50.0):
        self.rsi_period = rsi_period
        self.rsi_midline = rsi_midline

    def generate_signal(self, ctx: StrategyContext) -> Signal:
        closes = ctx.closes
        if len(closes) < max(self.min_candles, self.rsi_period + 1, 26 + 9):
            return "HOLD"

        curr = ctx.candles[-1]
        prev = ctx.candles[-2]

        rsi_vals = rsi(closes, self.rsi_period)
        macd_data = macd(closes)

        current_rsi = rsi_vals[-1]
        current_hist = macd_data["histogram"][-1]
        if current_rsi != current_rsi or current_hist != current_hist:
            return "HOLD"

        bullish_pattern = _is_hammer(curr) or _is_bullish_engulfing(prev, curr)
        bearish_pattern = _is_bearish_engulfing(prev, curr)
        # doji alone is indecision, not directional — only used to veto, not to fire

        if _is_doji(curr):
            return "HOLD"

        bullish_confirmed = current_rsi > self.rsi_midline or current_hist > 0
        bearish_confirmed = current_rsi < self.rsi_midline or current_hist < 0

        if bullish_pattern and bullish_confirmed:
            return "BUY"
        if bearish_pattern and bearish_confirmed:
            return "SELL"
        return "HOLD"
