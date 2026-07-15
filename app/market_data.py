"""
Public market data — real quotes pulled from Deriv, no user token required
(Deriv exposes market data unauthenticated; only trading/account actions
need a token). Used for the ticker strip on the frontend.
"""
from dataclasses import dataclass

from app.deriv_client import DerivClient

# A fixed, curated set of Deriv's synthetic indices — not the full symbol
# list, just the ones worth showing at a glance.
DEFAULT_SYMBOLS = [
    ("R_75", "Volatility 75"),
    ("R_100", "Volatility 100"),
    ("BOOM1000", "Boom 1000"),
    ("CRASH1000", "Crash 1000"),
    ("stpRNG", "Step Index"),
    ("JD25", "Jump 25"),
]


@dataclass
class TickerEntry:
    symbol: str
    display_name: str
    price: float | None
    change_pct: float | None
    error: str | None = None


async def fetch_ticker(symbols: list[tuple[str, str]] | None = None) -> list[TickerEntry]:
    symbols = symbols or DEFAULT_SYMBOLS
    client = DerivClient(api_token="")  # no token needed for public candle data
    entries: list[TickerEntry] = []

    await client.connect(authorize=False)
    try:
        for symbol, display_name in symbols:
            try:
                candles = await client.ticks_history(symbol, count=2, style="candles")
                if len(candles) < 2:
                    entries.append(TickerEntry(symbol, display_name, None, None, "insufficient data"))
                    continue
                prev_close = float(candles[-2]["close"])
                last_close = float(candles[-1]["close"])
                change_pct = ((last_close - prev_close) / prev_close * 100) if prev_close else 0.0
                entries.append(TickerEntry(symbol, display_name, round(last_close, 2), round(change_pct, 2)))
            except Exception as e:
                entries.append(TickerEntry(symbol, display_name, None, None, str(e)))
    finally:
        await client.close()

    return entries
