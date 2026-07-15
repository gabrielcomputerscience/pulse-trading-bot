"""
Strategy: Martingale (QUARANTINED — this is a staking scheme, not an edge)

Read this before you enable it.

Martingale is not a predictive strategy. It has no opinion about market
direction — it just doubles (or multiplies) the stake after every loss, on
the theory that the next win recovers all prior losses plus one unit of
profit. On paper, over a small sample, this produces a very high apparent
win rate, because most losing streaks are short. The problem is the
streaks that aren't short: a run of N consecutive losses requires a stake
of base_stake * multiplier^N, which grows exponentially and will blow
through any realistic account balance or exchange stake limit long before
"the next win" arrives. There is no length of losing streak that this
scheme is immune to — it is mathematically guaranteed to fail given
enough time, unlike the other three strategies here whose failure modes
are "wrong market regime" rather than "certain eventual ruin."

Because of that, this module:
  - Is never included in "recommended" or "best strategy" listings anywhere
    in the platform.
  - Has a hard-capped number of consecutive doublings (config:
    MARTINGALE_MAX_DOUBLINGS, default 4) after which it stops increasing
    stake and simply halts the bot rather than doubling further.
  - Has an absolute stake ceiling (config: MARTINGALE_ABSOLUTE_STAKE_CAP)
    that can never be exceeded regardless of streak length.
  - Requires its own explicit opt-in separate from picking a "strategy" —
    the API/UI should surface a distinct high-risk confirmation, not just
    a dropdown item next to the other three.

The underlying directional signal it trades on on is intentionally simple
(alternate CALL/PUT, or optionally wired to another strategy's signal) —
the interesting part of this file is the stake sizing, not signal
generation, because that is the actual mechanism at play.
"""
from app.config import settings
from app.strategies.base import Signal, Strategy, StrategyContext


class MartingaleStrategy(Strategy):
    name = "martingale"
    description = ("HIGH RISK. Doubles stake after each loss to recover losses on the "
                    "next win. Produces a high apparent win rate short-term; "
                    "mathematically guaranteed to eventually hit a losing streak that "
                    "exceeds the stake cap or account balance. Not a market-direction "
                    "strategy. Hard-capped doublings and absolute stake ceiling enforced "
                    "in code, not just documentation.")
    risk_label = "high_risk"
    min_candles = 5

    def __init__(self, multiplier: float = 2.0,
                 max_doublings: int | None = None,
                 absolute_cap: float | None = None,
                 direction: str = "alternate"):
        self.multiplier = multiplier
        self.max_doublings = max_doublings or settings.martingale_max_doublings
        self.absolute_cap = absolute_cap or settings.martingale_absolute_stake_cap
        self.direction = direction  # "alternate" | "always_call" | "always_put"

    def generate_signal(self, ctx: StrategyContext) -> Signal:
        # Deliberately trivial: this strategy's "edge" (such as it is) lives
        # in stake sizing, not signal quality. Alternating direction avoids
        # betting the same way forever with no market read at all.
        streak = ctx.state.get("consecutive_losses", 0)
        if streak >= self.max_doublings:
            return "HOLD"  # halted: hit the hard doubling cap, refuse to trade further
        if self.direction == "always_call":
            return "BUY"
        if self.direction == "always_put":
            return "SELL"
        # alternate based on trade count parity
        trade_count = ctx.state.get("trade_count", 0)
        return "BUY" if trade_count % 2 == 0 else "SELL"

    def next_stake(self, base_stake: float, ctx: StrategyContext) -> float:
        streak = ctx.state.get("consecutive_losses", 0)
        proposed = base_stake * (self.multiplier ** streak)
        return min(proposed, self.absolute_cap)

    def on_trade_closed(self, ctx: StrategyContext, won: bool, profit_loss: float) -> None:
        ctx.state["trade_count"] = ctx.state.get("trade_count", 0) + 1
        if won:
            ctx.state["consecutive_losses"] = 0
        else:
            ctx.state["consecutive_losses"] = ctx.state.get("consecutive_losses", 0) + 1
