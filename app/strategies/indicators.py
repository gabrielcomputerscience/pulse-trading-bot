"""
Plain, auditable indicator math — no black boxes. Every strategy's
"why did it fire" question should be answerable by reading this file.
All functions take a list/array of closing prices (or OHLC dicts) and
return either a scalar (latest value) or a list aligned to the input.
"""
from __future__ import annotations

import numpy as np


def sma(prices: list[float], period: int) -> list[float]:
    prices = np.asarray(prices, dtype=float)
    if len(prices) < period:
        return [np.nan] * len(prices)
    kernel = np.ones(period) / period
    out = np.convolve(prices, kernel, mode="valid")
    return [np.nan] * (period - 1) + out.tolist()


def ema(prices: list[float], period: int) -> list[float]:
    prices = np.asarray(prices, dtype=float)
    if len(prices) == 0:
        return []
    alpha = 2 / (period + 1)
    out = np.empty_like(prices)
    out[0] = prices[0]
    for i in range(1, len(prices)):
        out[i] = alpha * prices[i] + (1 - alpha) * out[i - 1]
    return out.tolist()


def rsi(prices: list[float], period: int = 14) -> list[float]:
    prices = np.asarray(prices, dtype=float)
    if len(prices) < period + 1:
        return [np.nan] * len(prices)
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.zeros(len(prices))
    avg_loss = np.zeros(len(prices))
    avg_gain[period] = gains[:period].mean()
    avg_loss[period] = losses[:period].mean()

    for i in range(period + 1, len(prices)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period

    rs = np.divide(avg_gain, avg_loss, out=np.full_like(avg_gain, np.inf), where=avg_loss != 0)
    rsi_vals = 100 - (100 / (1 + rs))
    rsi_vals[:period] = np.nan
    return rsi_vals.tolist()


def bollinger_bands(prices: list[float], period: int = 20, num_std: float = 2.0) -> dict:
    prices_arr = np.asarray(prices, dtype=float)
    mid = sma(prices, period)
    if len(prices) < period:
        return {"upper": [np.nan] * len(prices), "mid": mid, "lower": [np.nan] * len(prices)}

    upper, lower = [], []
    for i in range(len(prices)):
        if i < period - 1:
            upper.append(np.nan)
            lower.append(np.nan)
            continue
        window = prices_arr[i - period + 1: i + 1]
        std = window.std()
        upper.append(mid[i] + num_std * std)
        lower.append(mid[i] - num_std * std)
    return {"upper": upper, "mid": mid, "lower": lower}


def adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float]:
    """Average Directional Index — trend-strength filter. High ADX = real
    trend (good for trend_following); low ADX = chop (good for mean_reversion,
    bad for trend_following)."""
    n = len(closes)
    if n < period * 2:
        return [np.nan] * n

    highs, lows, closes = map(lambda x: np.asarray(x, dtype=float), (highs, lows, closes))
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    tr = np.zeros(n)

    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0.0
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))

    def wilder_smooth(x):
        out = np.zeros(n)
        out[period] = x[1:period + 1].sum()
        for i in range(period + 1, n):
            out[i] = out[i - 1] - (out[i - 1] / period) + x[i]
        return out

    tr_smooth = wilder_smooth(tr)
    plus_dm_smooth = wilder_smooth(plus_dm)
    minus_dm_smooth = wilder_smooth(minus_dm)

    plus_di = 100 * np.divide(plus_dm_smooth, tr_smooth, out=np.zeros(n), where=tr_smooth != 0)
    minus_di = 100 * np.divide(minus_dm_smooth, tr_smooth, out=np.zeros(n), where=tr_smooth != 0)
    dx = 100 * np.divide(np.abs(plus_di - minus_di), (plus_di + minus_di),
                          out=np.zeros(n), where=(plus_di + minus_di) != 0)

    adx_vals = np.zeros(n)
    start = period * 2
    if start < n:
        adx_vals[start] = dx[period:start].mean()
        for i in range(start + 1, n):
            adx_vals[i] = (adx_vals[i - 1] * (period - 1) + dx[i]) / period
    adx_vals[:start] = np.nan
    return adx_vals.tolist()


def macd(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ema_fast = np.asarray(ema(prices, fast))
    ema_slow = np.asarray(ema(prices, slow))
    macd_line = ema_fast - ema_slow
    signal_line = np.asarray(ema(macd_line.tolist(), signal))
    histogram = macd_line - signal_line
    return {"macd": macd_line.tolist(), "signal": signal_line.tolist(), "histogram": histogram.tolist()}
