from app.strategies.base import Strategy
from app.strategies.candlestick_indicator import CandlestickIndicatorStrategy
from app.strategies.martingale import MartingaleStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.trend_following import TrendFollowingStrategy

STRATEGY_REGISTRY: dict[str, type[Strategy]] = {
    "mean_reversion": MeanReversionStrategy,
    "trend_following": TrendFollowingStrategy,
    "candlestick_indicator": CandlestickIndicatorStrategy,
    "martingale": MartingaleStrategy,
}

# Strategies eligible to appear in "recommended" / general listings.
# Martingale is deliberately excluded — it requires its own explicit,
# separately-labeled opt-in flow in the API/UI, never a peer dropdown item.
RECOMMENDED_STRATEGIES = [n for n, cls in STRATEGY_REGISTRY.items()
                          if cls.risk_label != "high_risk"]


def get_strategy(name: str, **kwargs) -> Strategy:
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy '{name}'. Valid options: {list(STRATEGY_REGISTRY)}")
    return STRATEGY_REGISTRY[name](**kwargs)
