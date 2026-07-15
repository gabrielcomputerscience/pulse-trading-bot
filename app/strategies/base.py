"""
Every strategy implements the same interface so bot_engine.py and
backtest.py can treat them interchangeably. A strategy is a pure function
of the data it's given — it never talks to Deriv directly, never sees the
account balance, and never decides stake size (that's the bot's risk
config, applied outside the strategy). This separation is what makes
backtesting honest: the same code path runs in backtest and live.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Signal = Literal["BUY", "SELL", "HOLD"]


@dataclass
class Candle:
    epoch: int
    open: float
    high: float
    low: float
    close: float


@dataclass
class StrategyContext:
    """Rolling window of recent candles/closes handed to a strategy each
    time a new candle closes. `state` is strategy-private scratch space
    that persists between calls (e.g. Martingale's loss streak counter)."""
    candles: list[Candle]
    state: dict = field(default_factory=dict)

    @property
    def closes(self) -> list[float]:
        return [c.close for c in self.candles]

    @property
    def highs(self) -> list[float]:
        return [c.high for c in self.candles]

    @property
    def lows(self) -> list[float]:
        return [c.low for c in self.candles]


class Strategy:
    name: str = "base"
    description: str = ""
    risk_label: str = "standard"  # "standard" | "high_risk"
    min_candles: int = 30  # minimum history needed before it will produce a signal

    def generate_signal(self, ctx: StrategyContext) -> Signal:
        raise NotImplementedError

    def next_stake(self, base_stake: float, ctx: StrategyContext) -> float:
        """Default: flat staking. Only martingale overrides this."""
        return base_stake

    def on_trade_closed(self, ctx: StrategyContext, won: bool, profit_loss: float) -> None:
        """Hook for strategies that need to track streaks (martingale)."""
        return
